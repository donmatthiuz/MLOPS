"""Ingeniería de features para el dataset Gold.

Incluye variables de calendario (día de semana, fin de semana), rezagos y
medias móviles (autocorrelación de la serie de precios), y los horizontes
de predicción (1, 2 y 4 semanas, S2 del Business Understanding) como
columnas objetivo separadas — así se entrena un modelo por horizonte sin
usar información futura (requisito explícito: "evitar el uso de información
futura en el entrenamiento, validación temporal estricta, sin leakage").
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def construir_features(serie: pd.DataFrame, config: dict) -> pd.DataFrame:
    horizontes = config["negocio"]["horizontes_semanas"]
    umbral_tendencia = config["modelado"]["umbral_tendencia_gtq"]

    partes = []
    for tipo, grupo in serie.groupby("tipo_combustible"):
        g = grupo.sort_values("fecha").reset_index(drop=True).copy()
        g["fecha"] = pd.to_datetime(g["fecha"])

        g["dia_semana"] = g["fecha"].dt.dayofweek  # 0=lunes
        g["mes"] = g["fecha"].dt.month
        g["es_fin_de_semana"] = (g["dia_semana"] >= 5).astype(int)
        g["semana_del_anio"] = g["fecha"].dt.isocalendar().week.astype(int)

        for lag in (1, 2, 3, 4):
            g[f"lag_{lag}"] = g["precio_gtq_por_galon"].shift(lag)
        g["media_movil_3"] = g["precio_gtq_por_galon"].shift(1).rolling(3).mean()
        g["desviacion_movil_3"] = g["precio_gtq_por_galon"].shift(1).rolling(3).std()
        g["tendencia_reciente"] = g["lag_1"] - g["lag_2"]

        # Objetivos por horizonte: precio N semanas adelante, y su clase de
        # tendencia (alza/baja/estable) respecto al precio actual.
        for h in horizontes:
            g[f"objetivo_precio_h{h}"] = g["precio_gtq_por_galon"].shift(-h)
            delta = g[f"objetivo_precio_h{h}"] - g["precio_gtq_por_galon"]
            g[f"objetivo_tendencia_h{h}"] = np.select(
                [delta > umbral_tendencia, delta < -umbral_tendencia],
                ["alza", "baja"],
                default="estable",
            )

        g["tipo_combustible"] = tipo
        partes.append(g)

    resultado = pd.concat(partes, ignore_index=True)
    columnas_orden = [
        "fecha", "tipo_combustible", "precio_gtq_por_galon", "fuente",
        "dia_semana", "mes", "es_fin_de_semana", "semana_del_anio",
        "lag_1", "lag_2", "lag_3", "lag_4",
        "media_movil_3", "desviacion_movil_3", "tendencia_reciente",
    ] + [c for c in resultado.columns if c.startswith("objetivo_")]
    return resultado[columnas_orden]


FEATURES_MODELO = [
    "dia_semana", "mes", "es_fin_de_semana", "semana_del_anio",
    "lag_1", "lag_2", "lag_3", "lag_4",
    "media_movil_3", "desviacion_movil_3", "tendencia_reciente",
]
