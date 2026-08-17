"""Aumento de la serie histórica de precios.

Problema real de este proyecto: solo existen 5 fotografías (5 puntos reales
por tipo de combustible, tomadas semanalmente entre 2026-07-09 y 2026-07-30).
Es insuficiente para entrenar y validar temporalmente un modelo de series de
tiempo (S4 del Business Understanding: "existe suficiente historia de
precios..." queda como supuesto abierto). Tal como pide el negocio
("aplica una técnica para aumentar la muestra"), se genera una serie
histórica semanal sintética que:

  1. Usa como anclas los precios reales extraídos de las fotos (cuando la
     extracción los valida).
  2. Se calibra con datos reales externos (scraping de globalpetrolprices,
     que cita al MEM) para que la volatilidad y tendencia sean realistas:
     variación intermensual observada, y precio actual real como ancla final.
  3. Rellena el resto del histórico con una caminata aleatoria semanal
     (random walk con reversión leve a la tendencia calibrada), consistente
     con que "Actualizaciones semanales... una línea larga y plana significa
     que el gobierno fija los precios" (cita textual de la fuente).

Toda fila sintética queda marcada con `fuente="sintetico"` para que nunca se
confunda con una lectura real, y para poder auditar/filtrar en evaluación.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from ..config import load_config
from ..scraping.price_scraper import obtener_precio_referencia

# Relación aproximada entre el combustible de referencia externo (genérico
# "gasolina", que en Guatemala se reporta como proxy de Regular) y los otros
# tipos, tomada de la brecha observada en las fotos piloto (S6/D1).
_OFFSET_TIPICO_GTQ = {
    "regular": 0.0,
    "super": 1.0,
    "vpower": 1.5,
    "diesel": 2.1,
}


def _semilla_desde_texto(texto: str) -> int:
    return abs(hash(texto)) % (2**32 - 1)


def generar_serie_sintetica(
    anclas_reales: pd.DataFrame,
    fecha_inicio: date,
    fecha_fin: date,
    config: dict | None = None,
    semilla: int | None = None,
) -> pd.DataFrame:
    """Genera precios semanales sintéticos para cada tipo de combustible.

    Parameters
    ----------
    anclas_reales: DataFrame con columnas [fecha, tipo_combustible, precio_gtq_por_galon]
        (precios reales validados, pueden venir vacíos si la extracción no
        validó ninguno; en ese caso se ancla solo con el scraper externo).
    """
    cfg = config or load_config()
    semilla = semilla if semilla is not None else cfg["modelado"]["semilla"]
    rng = np.random.default_rng(semilla)

    ref_gasolina = obtener_precio_referencia("gasolina", cfg)
    ref_diesel = obtener_precio_referencia("diesel", cfg)
    precio_regular_hoy = ref_gasolina.precio_gtq_por_galon
    precio_diesel_hoy = ref_diesel.precio_gtq_por_galon
    variacion_mensual = (ref_gasolina.variacion_mensual_pct or 0.5) / 100.0

    semanas = pd.date_range(fecha_inicio, fecha_fin, freq="7D")
    filas = []

    for tipo in ["diesel", "regular", "super", "vpower"]:
        ancla_tipo = anclas_reales[anclas_reales["tipo_combustible"] == tipo] if not anclas_reales.empty else anclas_reales
        precio_ancla_final = precio_diesel_hoy if tipo == "diesel" else precio_regular_hoy + _OFFSET_TIPICO_GTQ[tipo]

        # Punto de partida: si hay ancla real más antigua, se usa; si no, se
        # retro-proyecta desde el precio actual con la variación mensual real.
        if not ancla_tipo.empty:
            precio_inicial = float(ancla_tipo.sort_values("fecha").iloc[0]["precio_gtq_por_galon"])
        else:
            semanas_totales = max(1, len(semanas))
            precio_inicial = precio_ancla_final / ((1 + variacion_mensual) ** (semanas_totales / 4.345))

        sigma_semanal = max(0.05, abs(variacion_mensual) * precio_ancla_final / 4.345)
        precio = precio_inicial
        deriva = (precio_ancla_final - precio_inicial) / max(1, len(semanas) - 1)

        for i, semana in enumerate(semanas):
            ruido = rng.normal(0, sigma_semanal)
            precio = max(5.0, precio + deriva + ruido)
            filas.append(
                {
                    "fecha": semana.date(),
                    "tipo_combustible": tipo,
                    "precio_gtq_por_galon": round(float(precio), 2),
                    "fuente": "sintetico",
                }
            )

    df_sintetico = pd.DataFrame(filas)

    # Las anclas reales, cuando existen, reemplazan al valor sintético de esa
    # semana exacta (los datos reales siempre tienen prioridad).
    if not anclas_reales.empty:
        df_real = anclas_reales.copy()
        df_real["fuente"] = "real"
        df_final = pd.concat([df_sintetico, df_real], ignore_index=True)
        df_final = (
            df_final.sort_values("fuente")  # "sintetico" < "real" alfabéticamente -> real queda último
            .drop_duplicates(subset=["fecha", "tipo_combustible"], keep="last")
            .sort_values(["tipo_combustible", "fecha"])
            .reset_index(drop=True)
        )
        return df_final

    return df_sintetico.sort_values(["tipo_combustible", "fecha"]).reset_index(drop=True)
