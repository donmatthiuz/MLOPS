"""Selección de origen y validación de rutas antes de ejecutar cada capa."""
from __future__ import annotations

import re
from pathlib import Path

from gasolina_gt.config import load_config, resolve_path


def settings() -> dict:
    cfg = load_config()
    source = cfg["source"]
    if source["mode"] == "local":
        data_dir = resolve_path(cfg["paths"]["datos_raw"])
        if not data_dir.is_dir():
            raise FileNotFoundError(f"LOCAL_DATA_DIR no existe: {data_dir}")
    else:
        missing = [key for key in ("bronze_input", "bronze_output", "silver_output", "gold_output", "catalog") if not source[key]]
        if missing:
            raise ValueError(f"Faltan variables Databricks: {', '.join(missing)}")
        for key in ("bronze_input", "bronze_output", "silver_output", "gold_output"):
            if not source[key].startswith(("s3://", "abfss://", "gs://")):
                raise ValueError(f"{key} debe ser una ruta cloud autorizada por external location")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", source["catalog"]):
            raise ValueError("DATABRICKS_CATALOG tiene un nombre inválido")
    return cfg


def local_silver_path(cfg: dict) -> Path:
    return resolve_path(cfg["paths"]["silver"]) / "precios_reales.csv"
