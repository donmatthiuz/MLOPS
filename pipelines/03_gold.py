# Databricks notebook source
"""Oro: indicadores y datos listos para modelado."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


def _setup_imports() -> None:
    candidates = [Path.cwd(), Path.cwd() / "pipelines"]
    if "__file__" in globals():
        candidates.insert(0, Path(__file__).resolve().parent)
    if "dbutils" in globals():
        notebook = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
        path = Path(notebook if notebook.startswith("/Workspace/") else "/Workspace" + notebook)
        candidates.insert(0, path.parent)
    for directory in candidates:
        if (directory / "common.py").is_file() and (directory.parent / "src" / "gasolina_gt").is_dir():
            sys.path[:0] = [str(directory), str(directory.parent / "src")]
            return
    raise RuntimeError("No se encontró pipelines/common.py y src/gasolina_gt en el Git folder")


_setup_imports()
from common import job_settings, local_silver_path, settings


def main() -> None:
    cfg = job_settings(dbutils.widgets) if "dbutils" in globals() else settings()
    if cfg["source"]["mode"] == "databricks":
        from databricks_layers import gold
        gold(cfg)
        return
    from gasolina_gt.data.pipeline import construir_gold
    path = local_silver_path(cfg)
    if not path.is_file():
        raise FileNotFoundError(f"Ejecute primero pipelines/02_silver.py: {path}")
    silver = pd.read_csv(path, parse_dates=["fecha"])
    result = construir_gold(silver, cfg)
    print(f"Oro local: {len(result)} filas (incluye serie sintética de desarrollo)")


if __name__ == "__main__":
    main()
