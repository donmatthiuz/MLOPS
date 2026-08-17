"""Métricas de evaluación y reporte auditable frente al baseline naive."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, mean_absolute_error

from ..config import load_config, resolve_path


@dataclass
class ResultadoEvaluacion:
    combustible: str
    horizonte: int
    mae_modelo: float
    mae_baseline: float
    mejora_vs_baseline_pct: float
    mape_modelo_pct: float
    wape_modelo_pct: float
    f1_tendencia_modelo: float
    f1_tendencia_baseline: float
    supera_baseline: bool
    cumple_mae: bool
    cumple_f1: bool
    fuente_datos: str


def _tendencia(prediccion: np.ndarray, actual: np.ndarray, umbral: float) -> np.ndarray:
    delta = prediccion - actual
    return np.select([delta > umbral, delta < -umbral], ["alza", "baja"], default="estable")


def evaluar_artefacto(artefacto: dict[str, Any], config: dict | None = None) -> ResultadoEvaluacion:
    cfg = config or load_config()
    test = artefacto["test"].copy()
    objetivo = f"objetivo_precio_h{artefacto['horizonte']}"
    y = test[objetivo].to_numpy(dtype=float)
    actual = test["precio_gtq_por_galon"].to_numpy(dtype=float)
    pred = artefacto["modelo"].predict(test[artefacto["features"]])
    baseline = actual  # persistencia: el último precio conocido al instante t.
    mae = float(mean_absolute_error(y, pred))
    mae_base = float(mean_absolute_error(y, baseline))
    mejora = 0.0 if mae_base == 0 else (mae_base - mae) / mae_base * 100
    mape = float(np.mean(np.abs((y - pred) / y)) * 100)
    wape = float(np.abs(y - pred).sum() / np.abs(y).sum() * 100)
    umbral = float(cfg["modelado"]["umbral_tendencia_gtq"])
    y_tendencia = _tendencia(y, actual, umbral)
    f1 = float(f1_score(y_tendencia, _tendencia(pred, actual, umbral), average="macro", zero_division=0))
    # Baseline de tendencia: proyectar el último cambio observado una semana.
    tendencia_simple = actual + test["tendencia_reciente"].to_numpy(dtype=float)
    f1_base = float(f1_score(y_tendencia, _tendencia(tendencia_simple, actual, umbral), average="macro", zero_division=0))
    fuente = "mixta" if (test.get("fuente") == "real").any() and (test.get("fuente") == "sintetico").any() else str(test.get("fuente", pd.Series(["desconocida"])).iloc[0])
    ev = cfg["evaluacion"]
    return ResultadoEvaluacion(
        combustible=artefacto["combustible"], horizonte=int(artefacto["horizonte"]),
        mae_modelo=round(mae, 4), mae_baseline=round(mae_base, 4), mejora_vs_baseline_pct=round(mejora, 2),
        mape_modelo_pct=round(mape, 3), wape_modelo_pct=round(wape, 3),
        f1_tendencia_modelo=round(f1, 4), f1_tendencia_baseline=round(f1_base, 4),
        supera_baseline=mae < mae_base, cumple_mae=mae <= float(ev["umbral_mae_gtq"]),
        cumple_f1=f1 >= float(ev["umbral_f1_tendencia"]), fuente_datos=fuente,
    )


def guardar_reporte(resultados: list[ResultadoEvaluacion], config: dict | None = None) -> Path:
    cfg = config or load_config()
    reports = resolve_path(cfg["paths"]["reports"])
    reports.mkdir(parents=True, exist_ok=True)
    ruta = reports / "evaluacion_modelos.csv"
    pd.DataFrame([asdict(r) for r in resultados]).to_csv(ruta, index=False)
    return ruta
