"""La ingesta Bronce usa la carpeta declarada en el entorno y es repetible."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class LocalSourceTest(unittest.TestCase):
    def test_bronze_lee_carpeta_configurada_sin_duplicar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            photos = base / "fotos"
            photos.mkdir()
            (photos / "prueba.jpg").write_bytes(b"foto-de-prueba")
            bronze = base / "bronze"
            env = os.environ | {
                "DATA_SOURCE": "local", "LOCAL_DATA_DIR": str(photos),
                "LOCAL_BRONZE_DIR": str(bronze), "PYTHONPATH": str(ROOT / "src"),
            }
            command = [sys.executable, str(ROOT / "pipelines" / "01_bronze.py")]
            subprocess.run(command, cwd=ROOT, env=env, check=True, capture_output=True)
            first = json.loads((bronze / "fotos_precios.json").read_text())
            subprocess.run(command, cwd=ROOT, env=env, check=True, capture_output=True)
            second = json.loads((bronze / "fotos_precios.json").read_text())
            self.assertEqual(len(second), 1)
            self.assertEqual(first, second)
