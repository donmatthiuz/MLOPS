"""Oro: indicadores y datos listos para modelado."""
from __future__ import annotations

import pandas as pd

from common import local_silver_path, settings


def main() -> None:
    cfg = settings()
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
