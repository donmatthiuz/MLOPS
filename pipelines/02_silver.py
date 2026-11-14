"""Plata: OCR y validación de precios."""
from __future__ import annotations

from common import settings


def main() -> None:
    cfg = settings()
    if cfg["source"]["mode"] == "databricks":
        from databricks_layers import silver
        silver(cfg)
        return
    from gasolina_gt.data.pipeline import construir_silver
    result = construir_silver(cfg)
    print(f"Plata local: {len(result)} lecturas válidas")


if __name__ == "__main__":
    main()
