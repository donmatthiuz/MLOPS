"""Datos sintéticos SOLO para pruebas de la capa Oro (no se usan fuera de tests/)."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

INICIO = date(2026, 1, 6)  # martes
COMBUSTIBLES = ("super", "regular", "diesel")


def martes(n: int) -> pd.Timestamp:
    """Martes con que empieza la semana número n (0 = 2026-01-06)."""
    return pd.Timestamp(INICIO + timedelta(days=7 * n))


def precios_silver(series: dict[str, dict[int, float]], dia: int = 0) -> pd.DataFrame:
    """Filas tipo Plata: {combustible: {semana_n: precio}}; `dia` desplaza dentro de la semana (0=martes)."""
    filas = [
        {"fecha": (INICIO + timedelta(days=7 * n + dia)), "combustible": combustible, "precio_q_galon": precio}
        for combustible, por_semana in series.items()
        for n, precio in por_semana.items()
    ]
    return pd.DataFrame(filas)


def serie_alternante(semanas: int = 30, combustibles=COMBUSTIBLES) -> pd.DataFrame:
    """Cada semana el precio sube Q0.50 y a la siguiente baja Q0.50: la dirección siempre cambia.

    La línea base («se repite la dirección») acierta 0 %; un modelo que use la variación
    de la última semana acierta 100 %.
    """
    series = {
        combustible: {n: 20.0 + i + (0.5 if n % 2 else 0.0) for n in range(semanas)}
        for i, combustible in enumerate(combustibles)
    }
    return precios_silver(series)


def wti_crudo(semanas: int = 6, valor_inicial: float = 70.0) -> pd.DataFrame:
    """CSV de FRED tal como llega a Bronce: todo texto, con días vacíos."""
    filas = []
    for n in range(semanas):
        for d in range(7):
            dia = INICIO + timedelta(days=7 * n + d)
            vacio = d == 5  # fin de semana sin dato
            filas.append({"observation_date": dia.isoformat(),
                          "DCOILWTICO": "" if vacio else str(valor_inicial + n)})
    return pd.DataFrame(filas)
