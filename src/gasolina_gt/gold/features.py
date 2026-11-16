"""Variables por semana calendario: solo usan la semana t y anteriores. Objetivo: dirección de t + 7 días."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .weekly import SEMANA

COLUMNAS_NUMERICAS = ["variacion_lag_1", "variacion_lag_2", "variacion_lag_3", "variacion_lag_4",
                      "promedio_movil_4", "dif_super_diesel", "wti_semanal", "wti_variacion"]
COLUMNAS_FEATURES = ["combustible", *COLUMNAS_NUMERICAS]


def _por_semana(df: pd.DataFrame, columna: str, desplazamiento: pd.Timedelta) -> pd.Series:
    """Valor de `columna` en la semana (semana − desplazamiento), alineado a la semana de cada fila."""
    valores = df.set_index(["combustible", "semana"])[columna]
    llaves = pd.MultiIndex.from_arrays([df["combustible"], df["semana"] - desplazamiento])
    return pd.Series(valores.reindex(llaves).to_numpy(), index=df.index)


def construir_features(variacion: pd.DataFrame, wti: pd.DataFrame | None = None) -> pd.DataFrame:
    f = variacion[["semana", "combustible", "precio_promedio", "diferencia_q", "direccion"]].copy()
    f = f.sort_values(["combustible", "semana"]).reset_index(drop=True)

    # variacion_lag_k = variación de la semana t − 7·(k−1) (lag_1 = la variación de la última semana conocida)
    for k in range(1, 5):
        f[f"variacion_lag_{k}"] = _por_semana(f, "diferencia_q", SEMANA * (k - 1))

    # promedio de las semanas que existan entre t−21 días y t; exige al menos 2 para no repetir el precio actual
    ventana = [_por_semana(f, "precio_promedio", SEMANA * k) for k in range(4)]
    tabla = pd.concat(ventana, axis=1)
    f["promedio_movil_4"] = tabla.mean(axis=1).where(tabla.notna().sum(axis=1) >= 2)

    super_, diesel = (f[f["combustible"] == c].set_index("semana")["precio_promedio"] for c in ("super", "diesel"))
    f["dif_super_diesel"] = (super_.reindex(f["semana"]).to_numpy() - diesel.reindex(f["semana"]).to_numpy())

    if wti is not None and len(wti):
        serie = wti.set_index("semana")["wti_semanal"]
        f["wti_semanal"] = serie.reindex(f["semana"]).to_numpy()
        previo = serie.reindex(f["semana"] - SEMANA).to_numpy()
        f["wti_variacion"] = f["wti_semanal"] - previo
    else:
        f["wti_semanal"] = np.nan
        f["wti_variacion"] = np.nan

    f["direccion_actual"] = f["direccion"]
    siguiente = _por_semana(f, "direccion", -SEMANA)   # la semana t + 7 días
    f["direccion_siguiente"] = siguiente.astype(object).where(siguiente.notna(), None)
    f["direccion_actual"] = f["direccion_actual"].astype(object).where(f["direccion_actual"].notna(), None)

    columnas = ["semana", "combustible", "precio_promedio", *COLUMNAS_NUMERICAS,
                "direccion_actual", "direccion_siguiente"]
    return f[columnas]
