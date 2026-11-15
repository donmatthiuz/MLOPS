"""Las rutas de producción quedan en las carpetas del equipo y de imágenes."""
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import Mock, patch

from pipelines import databricks_layers


class DatabricksPathsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = {"source": {
            "catalog": "workspace",
            "bronze_input": "s3://bucket-bronce/",
            "bronze_output": "s3://bucket-bronce/",
            "silver_output": "s3://bucket-plata/",
            "gold_output": "s3://bucket-oro/",
        }}

    def test_carpetas_de_entrada_y_salida(self) -> None:
        self.assertEqual(databricks_layers._image_dir(self.cfg), "s3://bucket-bronce/img")
        for layer, bucket in (("bronze", "bronce"), ("silver", "plata"), ("gold", "oro")):
            self.assertEqual(databricks_layers._path(self.cfg, layer, "datos"),
                             f"s3://bucket-{bucket}/equipo7/datos")

        self.cfg["source"]["bronze_input"] = "s3://bucket-bronce/img/"
        self.cfg["source"]["gold_output"] = "s3://bucket-oro/equipo7/"
        self.assertEqual(databricks_layers._image_dir(self.cfg), "s3://bucket-bronce/img")
        self.assertEqual(databricks_layers._path(self.cfg, "gold", "datos"),
                         "s3://bucket-oro/equipo7/datos")

    def test_crea_carpeta_del_equipo_si_falta(self) -> None:
        mkdirs = Mock(return_value=True)
        dbutils_module = types.ModuleType("pyspark.dbutils")
        dbutils_module.DBUtils = Mock(return_value=types.SimpleNamespace(fs=types.SimpleNamespace(mkdirs=mkdirs)))
        with patch.dict(sys.modules, {"pyspark": types.ModuleType("pyspark"),
                                      "pyspark.dbutils": dbutils_module}):
            databricks_layers._ensure_layer_dir(Mock(), self.cfg, "silver")
        mkdirs.assert_called_once_with("s3://bucket-plata/equipo7")

    def test_copia_delta_a_tabla_administrada_del_esquema(self) -> None:
        spark = Mock()
        databricks_layers._sync_managed_table(spark, self.cfg, "bronze", "fotos_precios")
        spark.read.format.assert_called_once_with("delta")
        spark.read.format.return_value.load.assert_called_once_with(
            "s3://bucket-bronce/equipo7/fotos_precios"
        )
        spark.sql.assert_called_once_with(
            "CREATE OR REPLACE TABLE workspace.equipo7.bronze_fotos_precios "
            "USING DELTA AS SELECT * FROM _equipo7_bronze_fotos_precios_source"
        )
        spark.catalog.dropTempView.assert_called_once_with("_equipo7_bronze_fotos_precios_source")

    def test_wti_rechaza_csv_con_formato_inesperado(self) -> None:
        dbutils_module = types.ModuleType("pyspark.dbutils")
        dbutils_module.DBUtils = Mock()
        sql_module = types.ModuleType("pyspark.sql")
        sql_module.functions = Mock()
        response = Mock(text="<html>error</html>")
        with patch.dict(sys.modules, {"pyspark": types.ModuleType("pyspark"), "pyspark.dbutils": dbutils_module,
                                      "pyspark.sql": sql_module}), \
                patch("requests.get", return_value=response):
            with self.assertRaises(RuntimeError):
                databricks_layers._bronze_wti(Mock(), self.cfg)
        dbutils_module.DBUtils.assert_not_called()
