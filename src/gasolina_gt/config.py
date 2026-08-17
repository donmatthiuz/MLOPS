"""Carga de configuración centralizada del proyecto (config/config.yaml)."""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


@functools.lru_cache(maxsize=1)
def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """Lee config/config.yaml una sola vez (cacheado) y devuelve un dict."""
    cfg_path = Path(path) if path else CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def resolve_path(relative: str) -> Path:
    """Convierte una ruta relativa del config (o cualquier string) en absoluta
    respecto a la raíz del proyecto."""
    p = Path(relative)
    return p if p.is_absolute() else PROJECT_ROOT / p
