"""Registro opcional en MLflow; sin MLflow o si falla, Oro sigue y deja un reporte."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

NOMBRE_REPORTE = "gold_experimento.json"


def _texto(valor) -> str:
    if isinstance(valor, (list, tuple, set)):
        return ",".join(str(v) for v in valor)
    return str(valor)


def _metricas_validas(metricas: dict) -> dict:
    return {k: float(v) for k, v in metricas.items()
            if v is not None and not (isinstance(v, float) and math.isnan(v))}


def _escribir_reporte(reports_dir, reporte: dict) -> None:
    if reports_dir is None:
        return
    try:
        carpeta = Path(reports_dir)
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / NOMBRE_REPORTE).write_text(json.dumps(reporte, indent=2, ensure_ascii=False, default=str),
                                              encoding="utf-8")
    except OSError as exc:
        print(f"Oro: no se pudo escribir el reporte local ({exc})")


def registrar_experimento(parametros: dict, metricas: dict, modelo, experimento: str, reports_dir=None,
                          nombre_run: str = "gold") -> Optional[str]:
    """run_id de MLflow, o None si no está disponible o falla."""
    reporte = {"experimento": experimento, "parametros": parametros, "metricas": metricas,
               "mlflow": "no disponible"}
    run_id = None
    try:
        import mlflow
        import mlflow.sklearn

        mlflow.set_experiment(experimento)
        with mlflow.start_run(run_name=nombre_run) as run:
            mlflow.log_params({k: _texto(v) for k, v in parametros.items()})
            mlflow.log_metrics(_metricas_validas(metricas))
            mlflow.set_tags({"modelo_registrado": "si" if modelo is not None else "no"})
            if modelo is not None:
                mlflow.sklearn.log_model(modelo, "modelo")
            run_id = run.info.run_id
        reporte["mlflow"] = "registrado"
        reporte["run_id"] = run_id
    except ImportError:
        print("Oro: MLflow no está disponible; se deja el reporte local.")
    except Exception as exc:
        run_id = None
        reporte["mlflow"] = f"falló: {exc}"
        print(f"Oro: MLflow falló ({exc}); se continúa y se deja el reporte local.")
    _escribir_reporte(reports_dir, reporte)
    return run_id
