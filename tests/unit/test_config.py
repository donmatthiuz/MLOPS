"""El cambio de origen no requiere editar código ni config.yaml."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from gasolina_gt.config import load_config


class ConfigSourceTest(unittest.TestCase):
    def test_origen_local_se_puede_cambiar_por_entorno(self) -> None:
        with patch.dict(os.environ, {"DATA_SOURCE": "local", "LOCAL_DATA_DIR": "/tmp/fotos-prueba"}):
            cfg = load_config()
        self.assertEqual(cfg["source"]["mode"], "local")
        self.assertEqual(cfg["paths"]["datos_raw"], "/tmp/fotos-prueba")

    def test_origen_databricks_usa_prefijos_external_location(self) -> None:
        with patch.dict(os.environ, {"DATA_SOURCE": "databricks", "BRONZE_INPUT_URI": "s3://bronce/fotos/"}):
            cfg = load_config()
        self.assertEqual(cfg["source"]["mode"], "databricks")
        self.assertEqual(cfg["source"]["bronze_input"], "s3://bronce/fotos/")

    def test_origen_desconocido_se_rechaza(self) -> None:
        with patch.dict(os.environ, {"DATA_SOURCE": "desconocido"}):
            with self.assertRaises(ValueError):
                load_config()
