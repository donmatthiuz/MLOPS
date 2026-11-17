"""Selección de origen y validación de rutas antes de ejecutar cada capa."""
from __future__ import annotations

import re
from pathlib import Path

from gasolina_gt.config import load_config, resolve_path


def settings(source_overrides: dict[str, str] | None = None) -> dict:
    cfg = load_config()
    source = cfg["source"]
    if source_overrides:
        source.update(source_overrides)
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


_JOB_SOURCE_WIDGETS = {
    "bronze_input_uri": "bronze_input",
    "bronze_output_uri": "bronze_output",
    "silver_output_uri": "silver_output",
    "gold_output_uri": "gold_output",
    "databricks_catalog": "catalog",
}


def job_settings(widgets) -> dict:
    """Configuración explícita de un notebook Job; no depende de un .env en Git."""
    values = {}
    for widget, key in _JOB_SOURCE_WIDGETS.items():
        widgets.text(widget, "", widget)
        values[key] = widgets.get(widget).strip()
    missing = [name for name in _JOB_SOURCE_WIDGETS if not values[_JOB_SOURCE_WIDGETS[name]]]
    if missing:
        raise ValueError(f"Faltan parámetros del Job: {', '.join(missing)}")
    return settings({"mode": "databricks", **values})


def local_silver_path(cfg: dict) -> Path:
    return resolve_path(cfg["paths"]["silver"]) / "precios_reales.csv"
