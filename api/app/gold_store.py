"""Lectura de las tablas Delta de Oro desde S3, sin operaciones de escritura."""
from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)
TABLES = frozenset({"precio_semanal", "variacion_semanal", "features_modelo", "predicciones", "metricas_modelo"})


class GoldUnavailable(Exception):
    """La configuración o la lectura de Oro falló."""


def table_uri(name: str) -> str:
    if name not in TABLES:
        raise ValueError(f"Tabla Oro no permitida: {name}")
    base = os.environ.get("GOLD_OUTPUT_URI", "").strip().rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise GoldUnavailable("GOLD_OUTPUT_URI debe ser una URI s3:// válida")
    if parsed.path.rstrip("/").split("/")[-1] != "equipo7":
        base += "/equipo7"
    return f"{base}/{name}"


def _delta_table(name: str):
    try:
        from deltalake import DeltaTable

        return DeltaTable(table_uri(name))
    except Exception as exc:
        logger.exception("No se pudo abrir la tabla Oro %s", name)
        raise GoldUnavailable(name) from exc


def check_gold() -> None:
    _delta_table("precio_semanal")


def read_gold(name: str, columns: list[str]) -> list[dict]:
    table = _delta_table(name)
    try:
        return table.to_pyarrow_table(columns=columns).to_pylist()
    except Exception as exc:
        logger.exception("No se pudo leer la tabla Oro %s", name)
        raise GoldUnavailable(name) from exc
