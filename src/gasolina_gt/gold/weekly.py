"""Precio semanal (martes a lunes) y variación contra la semana calendario anterior."""
from __future__ import annotations

import numpy as np
import pandas as pd

SEMANA = pd.Timedelta(days=7)


def semana_de(fechas: pd.Series) -> pd.Series:
    """Martes con que empieza la semana (martes–lunes) de cada fecha."""
    dias = pd.to_datetime(fechas).dt.normalize()
    return dias - pd.to_timedelta((dias.dt.dayofweek - 1) % 7, unit="D")


def precio_semanal(silver: pd.DataFrame) -> pd.DataFrame:
    """Promedio, mínimo y máximo por semana y combustible (Plata: fecha, combustible, precio_q_galon)."""
    datos = silver.assign(semana=semana_de(silver["fecha"]))
    semanal = (datos.groupby(["semana", "combustible"], as_index=False)
               .agg(precio_promedio=("precio_q_galon", "mean"),
                    precio_minimo=("precio_q_galon", "min"),
                    precio_maximo=("precio_q_galon", "max"),
                    n_lecturas=("precio_q_galon", "size")))
    return semanal.sort_values(["combustible", "semana"]).reset_index(drop=True)


def etiquetar_direccion(diferencia: pd.Series, umbral_q: float) -> pd.Series:
    """sube / baja / se_mantiene según el umbral; None si no hay diferencia.

    Se redondea a 4 decimales para que 20.10 − 20.00 cuente como Q0.10 exactos y no como 0.10000000000000142.
    """
    d = diferencia.astype(float).round(4)
    etiqueta = pd.Series(np.select([d > umbral_q, d < -umbral_q], ["sube", "baja"], default="se_mantiene"),
                         index=diferencia.index, dtype=object)
    etiqueta[d.isna()] = None
    return etiqueta


def variacion_semanal(semanal: pd.DataFrame, umbral_q: float) -> pd.DataFrame:
    """Compara cada semana SOLO con la semana calendario inmediatamente anterior (semana − 7 días).

    Si esa semana no existe no se inventa nada: diferencias y dirección quedan nulas.
    """
    anterior = semanal[["semana", "combustible", "precio_promedio"]].rename(
        columns={"precio_promedio": "precio_anterior"})
    anterior = anterior.assign(semana=anterior["semana"] + SEMANA)
    var = semanal.merge(anterior, on=["semana", "combustible"], how="left")
    var["semana_anterior_disponible"] = var["precio_anterior"].notna()
    var["diferencia_q"] = var["precio_promedio"] - var["precio_anterior"]
    var["diferencia_pct"] = var["diferencia_q"] / var["precio_anterior"] * 100
    var["direccion"] = etiquetar_direccion(var["diferencia_q"], umbral_q)
    var["umbral_q"] = float(umbral_q)
    return var.sort_values(["combustible", "semana"]).reset_index(drop=True)


def wti_semanal(wti_crudo: pd.DataFrame) -> pd.DataFrame:
    """Promedio semanal (martes–lunes) del WTI. Acepta el CSV de FRED en texto, con días vacíos o '.'."""
    datos = pd.DataFrame({
        "fecha": pd.to_datetime(wti_crudo["observation_date"], errors="coerce"),
        "valor": pd.to_numeric(wti_crudo["DCOILWTICO"], errors="coerce"),
    }).dropna()
    datos["semana"] = semana_de(datos["fecha"])
    return (datos.groupby("semana", as_index=False).agg(wti_semanal=("valor", "mean"))
            .sort_values("semana").reset_index(drop=True))
