"""Interfaz de línea de comandos del proyecto."""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict

from .config import load_config
from .data.pipeline import cargar_gold_si_existe, construir_gold, construir_silver
from .evaluation import evaluar_artefacto, guardar_reporte
from .modeling import entrenar_todos_los_horizontes
from .serving import recomendar_recarga


def _gold() -> object:
    gold = cargar_gold_si_existe()
    return gold if gold is not None else construir_gold()


def main() -> None:
    parser = argparse.ArgumentParser(prog="gasolina-gt", description="Predicción de precios de combustible en Guatemala")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("build-data", help="Ejecuta Bronze → Silver → Gold")
    p_train = sub.add_parser("train", help="Entrena y evalúa horizontes configurados")
    p_train.add_argument("--combustible", default=None)
    p_rec = sub.add_parser("recommend", help="Da la recomendación de carga")
    p_rec.add_argument("--combustible", default=None)
    p_rec.add_argument("--horizonte", type=int, default=1, choices=(1, 2, 4))
    p_rec.add_argument("--hora", type=int, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.comando == "build-data":
        silver = construir_silver()
        gold = construir_gold(silver)
        print(json.dumps({"silver_filas": len(silver), "gold_filas": len(gold), "fuentes_gold": gold["fuente"].value_counts().to_dict()}, ensure_ascii=False))
        return
    if args.comando == "train":
        resultados = entrenar_todos_los_horizontes(_gold(), args.combustible)
        evaluaciones = [evaluar_artefacto(artefacto) for artefacto, _ in resultados]
        ruta = guardar_reporte(evaluaciones)
        print(json.dumps({"modelos": [asdict(meta) for _, meta in resultados], "evaluacion": [asdict(x) for x in evaluaciones], "reporte": str(ruta)}, ensure_ascii=False, indent=2))
        return
    print(json.dumps(asdict(recomendar_recarga(_gold(), args.combustible, args.horizonte, args.hora)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
