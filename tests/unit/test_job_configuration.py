"""Contrato del Job: entradas explícitas y separación segura de las tres capas."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from pipelines.common import job_settings
from pipelines.databricks_layers import silver


ROOT = Path(__file__).resolve().parents[2]


class WidgetsFalsos:
    def __init__(self, values):
        self.values = values

    def text(self, name, default, label):
        self.values.setdefault(name, default)

    def get(self, name):
        return self.values[name]


class JobConfigurationTest(unittest.TestCase):
    def test_parametros_del_job_sustituyen_un_env_local(self):
        values = {
            "bronze_input_uri": "s3://raw/img/",
            "bronze_output_uri": "s3://bronze/",
            "silver_output_uri": "s3://silver/",
            "gold_output_uri": "s3://gold/",
            "databricks_catalog": "workspace",
        }
        with patch("pipelines.common.load_config", return_value={"source": {
            "mode": "local", "bronze_input": "", "bronze_output": "", "silver_output": "",
            "gold_output": "", "catalog": ""}, "paths": {}}):
            cfg = job_settings(WidgetsFalsos(values))
        self.assertEqual(cfg["source"], {
            "mode": "databricks", "bronze_input": "s3://raw/img/",
            "bronze_output": "s3://bronze/", "silver_output": "s3://silver/",
            "gold_output": "s3://gold/", "catalog": "workspace"})

    def test_no_usa_env_del_git_folder_si_falta_un_parametro_del_job(self):
        with self.assertRaisesRegex(ValueError, "gold_output_uri"):
            job_settings(WidgetsFalsos({
                "bronze_input_uri": "s3://raw/img/", "bronze_output_uri": "s3://bronze/",
                "silver_output_uri": "s3://silver/", "databricks_catalog": "workspace"}))

    def test_funcion_antigua_de_plata_no_escribe(self):
        with self.assertRaisesRegex(RuntimeError, "02_silver.py"):
            silver({}, reprocess=True)

    def test_job_tiene_tres_notebooks_ordenados_y_entorno(self):
        job = json.loads((ROOT / "pipelines" / "job.json").read_text())
        tasks = job["tasks"]
        self.assertEqual([t["task_key"] for t in tasks], ["01_bronce", "02_plata", "03_oro"])
        self.assertEqual(tasks[1]["depends_on"], [{"task_key": "01_bronce"}])
        self.assertEqual(tasks[2]["depends_on"], [{"task_key": "02_plata"}])
        self.assertTrue(all(t["notebook_task"]["source"] == "WORKSPACE" for t in tasks))
        self.assertTrue(all(t["environment_key"] == "pipeline_serverless" for t in tasks))
        self.assertEqual(job["schedule"]["pause_status"], "PAUSED")


if __name__ == "__main__":
    unittest.main()
