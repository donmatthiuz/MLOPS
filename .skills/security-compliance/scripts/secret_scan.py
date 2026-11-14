#!/usr/bin/env python3
"""Heuristic secret scanner with safe-by-default behavior.

Security guarantees (defense in depth, see AGENTS.md):

- ``keys/`` is NEVER scanned: any directory named ``keys`` is pruned from
  recursive walks, and an explicit ``keys`` (or ``keys/<file>``) target is
  rejected with a non-zero exit code BEFORE any file is opened.
- ``.env`` and ``.env.*`` files are always skipped.
- Findings NEVER include secret values: reports contain only the file path,
  the line number and the rule identifier that matched. This applies to both
  stdout and JSON output.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

# Each rule is (rule_id, pattern). The rule_id is the ONLY thing reported
# about a match; the matched text is never stored, printed or serialized.
RULES: List[Tuple[str, re.Pattern[str]]] = [
    ("aws-access-key-id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private-key-header", re.compile(r"-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----")),
    ("slack-token", re.compile(r"(?i)\b(xox[baprs]-[0-9A-Za-z-]{10,})\b")),
    ("github-token-classic", re.compile(r"(?i)\bghp_[0-9A-Za-z]{30,}\b")),
    ("github-token-fine-grained", re.compile(r"(?i)\bgithub_pat_[0-9A-Za-z_]{20,}\b")),
    # Possible MongoDB connection URI. Only its existence is reported,
    # never the URI itself (it may embed user/password/host).
    ("mongodb-uri", re.compile(r"(?i)\bmongodb(\+srv)?://")),
]

# Directories that are always pruned from recursive walks. ``keys`` has no
# opt-out: there is no flag to force scanning it.
SKIP_DIRS = {
    ".git",
    "keys",
    "node_modules",
    ".next",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
}

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".mp4"}


def is_skipped_file(path: Path) -> bool:
    """Return True for files that must never be opened by the scanner."""
    name = path.name
    if name == ".env" or name.startswith(".env."):
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    return False


def is_forbidden_target(resolved: Path) -> bool:
    """Return True if the target is (or lives inside) a ``keys`` directory.

    Uses only the resolved path components; no file is opened.
    """
    return "keys" in resolved.parts


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str  # rule identifier only; never a secret value


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if p.is_symlink():
                continue
            if is_skipped_file(p):
                continue
            yield p


def scan_file(path: Path, max_bytes: int) -> List[Finding]:
    try:
        data = path.read_bytes()
    except Exception:
        return []
    if len(data) > max_bytes:
        return []
    text = data.decode("utf-8", errors="replace")
    findings: List[Finding] = []
    for i, line in enumerate(text.splitlines(), start=1):
        for rule_id, pattern in RULES:
            if pattern.search(line):
                findings.append(Finding(str(path), i, rule_id))
    return findings


def collect_findings(root: Path, max_bytes: int) -> List[Finding]:
    findings: List[Finding] = []
    if root.is_file():
        if not is_skipped_file(root):
            findings.extend(scan_file(root, max_bytes))
        return findings
    for f in iter_files(root):
        findings.extend(scan_file(f, max_bytes))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan a directory for likely secrets (heuristic, safe by default)."
    )
    parser.add_argument("target", nargs="?", default=".", help="Directory to scan (default: .)")
    parser.add_argument("--max-bytes", type=int, default=300_000, help="Skip files larger than this (default: 300k)")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--output", help="Write JSON output to a file")
    args = parser.parse_args()

    root = Path(args.target).resolve()

    # Reject keys/ targets BEFORE touching the filesystem content.
    if is_forbidden_target(root):
        print(f"Refusing to scan inside a 'keys' directory: {root}", file=sys.stderr)
        raise SystemExit(2)

    if not root.exists():
        raise SystemExit(f"Target does not exist: {root}")

    findings = collect_findings(root, args.max_bytes)

    payload: Dict[str, object] = {
        "target": str(root),
        "count": len(findings),
        "findings": [f.__dict__ for f in findings],
    }

    if args.json or args.output:
        out = json.dumps(payload, indent=2)
        if args.output:
            Path(args.output).write_text(out, encoding="utf-8")
        else:
            print(out)
        return

    print(f"Target: {root}")
    print(f"Findings: {len(findings)}")
    for f in findings[:50]:
        print(f"- {f.path}:{f.line} [{f.rule}]")
    if len(findings) > 50:
        print(f"(truncated; {len(findings) - 50} more)")


if __name__ == "__main__":
    main()
