#!/usr/bin/env python3
"""Tests for secret_scan.py safe-by-default behavior.

All fixtures use fictitious secrets inside temporary directories.
The real ``keys/`` directory is never touched.

Run: python .skills/security-compliance/scripts/test_secret_scan.py
(or: python -m unittest test_secret_scan -v, from the scripts directory)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "secret_scan.py"

# Fictitious secrets, only ever written to temp dirs by these tests.
FAKE_AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
FAKE_GITHUB_TOKEN = "ghp_" + "x" * 32
FAKE_FINE_GRAINED_TOKEN = "github_pat_" + "y" * 24
FAKE_SLACK_TOKEN = "xoxb-123456789012-FAKESECRET"
FAKE_PRIVATE_KEY_HEADER = "-----BEGIN RSA PRIVATE KEY-----"
FAKE_MONGO_URI = "mongodb+srv://fakeuser:fakepass@fakehost.example.com/fakedb"
FAKE_MONGO_PLAIN_URI = "mongodb://fakeuser:fakepass@localhost:27017/fakedb"

ALL_FAKE_VALUES = [
    FAKE_AWS_KEY,
    FAKE_GITHUB_TOKEN,
    FAKE_FINE_GRAINED_TOKEN,
    FAKE_SLACK_TOKEN,
    FAKE_PRIVATE_KEY_HEADER,
    "fakeuser:fakepass@fakehost.example.com",
    "fakeuser:fakepass@localhost:27017",
]


def run_scan(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )


class SecretScanSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, relative: str, content: str) -> Path:
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def test_keys_dir_is_ignored_when_scanning_dot(self) -> None:
        self.write("keys/mongodb_uri", FAKE_MONGO_URI + "\n")
        self.write("keys/other_secret", FAKE_AWS_KEY + "\n")
        self.write("normal.txt", f"token = {FAKE_GITHUB_TOKEN}\n")
        proc = run_scan("--json", cwd=self.root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        paths = [f["path"] for f in payload["findings"]]
        self.assertTrue(any(p.endswith("normal.txt") for p in paths))
        self.assertFalse(any(f"{os.sep}keys{os.sep}" in p for p in paths))
        for value in ALL_FAKE_VALUES:
            self.assertNotIn(value, proc.stdout)

    def test_explicit_keys_dir_is_rejected(self) -> None:
        keys_dir = self.write("keys/mongodb_uri", FAKE_MONGO_URI + "\n").parent
        proc = run_scan(str(keys_dir), cwd=self.root)
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn(FAKE_MONGO_URI, proc.stdout)
        self.assertNotIn(FAKE_MONGO_URI, proc.stderr)

    def test_explicit_keys_file_is_rejected(self) -> None:
        secret_file = self.write("keys/mongodb_uri", FAKE_MONGO_URI + "\n")
        proc = run_scan(str(secret_file), cwd=self.root)
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn(FAKE_MONGO_URI, proc.stdout)
        self.assertNotIn(FAKE_MONGO_URI, proc.stderr)

    def test_detected_secret_never_appears_in_stdout(self) -> None:
        self.write(
            "leak.txt",
            "\n".join(
                [
                    f"aws = {FAKE_AWS_KEY}",
                    f"gh = {FAKE_GITHUB_TOKEN}",
                    f"fine = {FAKE_FINE_GRAINED_TOKEN}",
                    f"slack = {FAKE_SLACK_TOKEN}",
                    FAKE_PRIVATE_KEY_HEADER,
                    f"mongo = {FAKE_MONGO_URI}",
                ]
            )
            + "\n",
        )
        proc = run_scan(cwd=self.root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for value in ALL_FAKE_VALUES:
            self.assertNotIn(value, proc.stdout)
        # Rules are still reported.
        for rule in ("aws-access-key-id", "github-token-classic", "mongodb-uri"):
            self.assertIn(rule, proc.stdout)

    def test_detected_secret_never_appears_in_json(self) -> None:
        self.write("leak.txt", f"mongo = {FAKE_MONGO_URI}\nkey = {FAKE_AWS_KEY}\n")
        proc = run_scan("--json", cwd=self.root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for value in ALL_FAKE_VALUES:
            self.assertNotIn(value, proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertGreaterEqual(payload["count"], 2)
        for finding in payload["findings"]:
            self.assertEqual(set(finding.keys()), {"path", "line", "rule"})

    def test_mongodb_srv_detected_without_exposing_value(self) -> None:
        self.write("config.txt", f"uri={FAKE_MONGO_URI}\n")
        self.write("plain.txt", f"uri={FAKE_MONGO_PLAIN_URI}\n")
        proc = run_scan("--json", cwd=self.root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        rules = [f["rule"] for f in payload["findings"]]
        self.assertEqual(rules.count("mongodb-uri"), 2)
        self.assertNotIn("fakepass", proc.stdout)
        self.assertNotIn("fakehost.example.com", proc.stdout)

    def test_env_files_are_ignored(self) -> None:
        self.write(".env", f"TOKEN={FAKE_GITHUB_TOKEN}\nMONGO={FAKE_MONGO_URI}\n")
        self.write(".env.local", f"TOKEN={FAKE_AWS_KEY}\n")
        self.write("normal.txt", "nothing sensitive here\n")
        proc = run_scan("--json", cwd=self.root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["count"], 0)
        for value in ALL_FAKE_VALUES:
            self.assertNotIn(value, proc.stdout)

    def test_normal_files_are_still_scanned(self) -> None:
        self.write("app.py", f"# token {FAKE_GITHUB_TOKEN}\nprint('hi')\n")
        proc = run_scan("--json", cwd=self.root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["count"], 1)
        finding = payload["findings"][0]
        self.assertTrue(finding["path"].endswith("app.py"))
        self.assertEqual(finding["line"], 1)
        self.assertEqual(finding["rule"], "github-token-classic")


if __name__ == "__main__":
    unittest.main(verbosity=2)
