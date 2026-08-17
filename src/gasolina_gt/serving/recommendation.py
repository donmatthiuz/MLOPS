"""Regla de negocio que convierte un pronóstico en una recomendación clara."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import pandas as pd
import numpy as np

from ..config import load_config
from ..data.features import FEATURES_MODELO
from ..modeling.training import cargar_modelo


@dataclass
class Recomendacion:
    recargar_ahora: bool
    decision: str
    motivo: str
    combustible: str
    horizonte_semanas: int
    precio_actual_gtq_por_galon: float
    precio_estimado_gtq_por_galon: float
    diferencia_estimada_gtq: float
    tendencia: str
    fecha_datos: str
    contexto_hora: str
    advertencia: str | None


def recomendar_recarga(
    gold: pd.DataFrame,
    combustible: str | None = None,
    horizonte: int = 1,
    hora: int | None = None,
    config: dict | None = None,
) -> Recomendacion:
    """Devuelve ``recargar_ahora`` según el cambio estimado del precio.

    La hora aporta contexto operativo (horas de tráfico), no se usa como una
    causa del precio: los datos disponibles son semanales y no sostienen una
    inferencia de variación intradía.
    """
    cfg = config or load_config()
    combustible = combustible or cfg["negocio"]["combustible_principal"]
    hora = datetime.now().hour if hora is None else hora
    if not 0 <= hora <= 23:
        raise ValueError("La hora debe estar entre 0 y 23.")
    artefacto = cargar_modelo(combustible, horizonte, cfg)
    filas = gold[gold["tipo_combustible"] == combustible].dropna(subset=FEATURES_MODELO).sort_values("fecha")
    if filas.empty:
        raise ValueError(f"No hay features listas para recomendar {combustible}.")
    ultima = filas.iloc[-1]
    actual = float(ultima["precio_gtq_por_galon"])
    # Una serie extraída como ``Series`` queda dtype=object al transponerla;
    # se reconstruye explícitamente como fila numérica para XGBoost.
    x_ultima = pd.DataFrame([ultima[artefacto["features"]].astype(float).to_dict()])
    pred = float(artefacto["modelo"].predict(x_ultima)[0])
    # No se despliega un modelo que perdió contra persistencia en su test
    # temporal. En tal caso la predicción operativa segura es el baseline.
    modelo_supera_baseline = True
    if "test" in artefacto:
        test = artefacto["test"]
        objetivo = f"objetivo_precio_h{horizonte}"
        y_test = test[objetivo].to_numpy(dtype=float)
        pred_test = artefacto["modelo"].predict(test[artefacto["features"]])
        mae_modelo = np.abs(y_test - pred_test).mean()
        mae_baseline = np.abs(y_test - test["precio_gtq_por_galon"].to_numpy(dtype=float)).mean()
        modelo_supera_baseline = bool(mae_modelo < mae_baseline)
        if not modelo_supera_baseline:
            pred = actual
    diferencia = pred - actual
    margen = float(cfg["recomendacion"]["margen_decision_gtq"])
    if diferencia > margen:
        decision, recargar, tendencia = "RECARGAR AHORA", True, "alza"
        motivo = "Se estima un alza superior al margen de decisión; cargar ahora evita pagar más después."
    elif diferencia < -margen:
        decision, recargar, tendencia = "ESPERAR", False, "baja"
        motivo = "Se estima una baja superior al margen de decisión; si el nivel de combustible lo permite, espere."
    else:
        decision, recargar, tendencia = "INDIFERENTE", False, "estable"
        motivo = "El cambio esperado está dentro del margen de decisión; no hay ahorro estimado relevante."
    pico = hora in cfg["recomendacion"]["horas_pico_ahorro"]
    contexto = "Hora pico: si puede, prefiera una hora no pico para reducir tiempo de espera." if pico else "Hora no pico: contexto operativo favorable para cargar."
    fuente = str(ultima.get("fuente", "desconocida"))
    advertencias = []
    if fuente != "real":
        advertencias.append("El historial disponible es sintético/calibrado; confirme con precios reales antes de una decisión de alto impacto.")
    if not modelo_supera_baseline:
        advertencias.append("XGBoost no superó al baseline en el último test temporal; se aplicó la predicción conservadora de persistencia.")
    advertencia = " ".join(advertencias) or None
    return Recomendacion(
        recargar_ahora=recargar, decision=decision, motivo=motivo, combustible=combustible,
        horizonte_semanas=horizonte, precio_actual_gtq_por_galon=round(actual, 2),
        precio_estimado_gtq_por_galon=round(pred, 2), diferencia_estimada_gtq=round(diferencia, 2),
        tendencia=tendencia, fecha_datos=str(pd.Timestamp(ultima["fecha"]).date()),
        contexto_hora=contexto, advertencia=advertencia,
    )


def recomendacion_como_dict(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return asdict(recomendar_recarga(*args, **kwargs))
