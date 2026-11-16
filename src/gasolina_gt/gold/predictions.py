"""Tabla gold_predicciones: clave (semana, combustible, tipo), sin reescribir el pasado."""
from __future__ import annotations

import pandas as pd

COLUMNAS_PREDICCIONES = ["semana", "combustible", "tipo", "prediccion", "probabilidad", "modelo",
                         "direccion_real", "_generado_en"]
LLAVE = ["semana", "combustible", "tipo"]


def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reindex(columns=COLUMNAS_PREDICCIONES).copy()
    df["semana"] = pd.to_datetime(df["semana"])
    df["probabilidad"] = df["probabilidad"].astype(float)
    df["_generado_en"] = pd.to_datetime(df["_generado_en"])
    for columna in ("combustible", "tipo", "prediccion", "modelo", "direccion_real"):
        df[columna] = df[columna].astype(object).where(df[columna].notna(), None)
    return df.reset_index(drop=True)


def _rellenar_reales(df: pd.DataFrame, reales: pd.DataFrame) -> pd.DataFrame:
    if df.empty or reales.empty:
        return df
    real = reales.rename(columns={"direccion": "_real"})[["semana", "combustible", "_real"]]
    unido = df.merge(real, on=["semana", "combustible"], how="left")
    pendiente = unido["direccion_real"].isna() & unido["_real"].notna()
    unido.loc[pendiente, "direccion_real"] = unido.loc[pendiente, "_real"]
    return unido.drop(columns="_real")


def combinar_predicciones(existentes: pd.DataFrame | None, nuevas: pd.DataFrame, reales: pd.DataFrame,
                          generado_en) -> pd.DataFrame:
    """MERGE idempotente por (semana, combustible, tipo). Un pronóstico ya resuelto no se reescribe;
    el resto se recalcula y las filas antiguas se conservan. `reales`: semana, combustible, direccion."""
    nuevas = _normalizar(nuevas.assign(_generado_en=generado_en))
    if existentes is None or len(existentes) == 0:
        return _normalizar(_rellenar_reales(nuevas, reales))

    previas = _rellenar_reales(_normalizar(existentes), reales)
    claves_previas = previas.set_index(LLAVE)
    cerradas = claves_previas.index[(claves_previas["direccion_real"].notna()) & (claves_previas.index.get_level_values("tipo") == "pronostico")]
    indice_nuevas = pd.MultiIndex.from_frame(nuevas[LLAVE])
    nuevas = nuevas[~indice_nuevas.isin(cerradas)]

    conservar = previas[~pd.MultiIndex.from_frame(previas[LLAVE]).isin(pd.MultiIndex.from_frame(nuevas[LLAVE]))]
    combinado = pd.concat([conservar, nuevas], ignore_index=True)
    return _normalizar(_rellenar_reales(combinado, reales))
