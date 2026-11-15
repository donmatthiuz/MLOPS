"""Plata: OCR y validación de precios."""
from __future__ import annotations

import argparse

from common import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Procesa la capa Plata")
    parser.add_argument("--reprocess", action="store_true", help="Reprocesa todas las fotos de Bronce")
    args = parser.parse_args()
    cfg = settings()
    if cfg["source"]["mode"] == "databricks":
        from databricks_layers import silver
        silver(cfg, reprocess=args.reprocess)
        return
    if args.reprocess:
        parser.error("--reprocess solo está disponible en modo Databricks")
    from gasolina_gt.data.pipeline import construir_silver
    result = construir_silver(cfg)
    print(f"Plata local: {len(result)} lecturas válidas")


if __name__ == "__main__":
    main()
