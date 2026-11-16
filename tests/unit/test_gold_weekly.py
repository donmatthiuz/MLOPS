"""Semana martes–lunes, variación contra la semana calendario anterior y umbral."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from gasolina_gt.gold.weekly import (
    etiquetar_direccion, precio_semanal, semana_de, variacion_semanal, wti_semanal,
)
from tests.unit.gold_helpers import martes, precios_silver


def test_la_semana_va_de_martes_a_lunes():
    fechas = pd.to_datetime(["2026-01-06", "2026-01-12", "2026-01-13", "2026-01-05"])
    semanas = semana_de(pd.Series(fechas))
    assert list(semanas) == [martes(0), martes(0), martes(1), pd.Timestamp("2025-12-30")]


def test_semana_acepta_fechas_date_de_spark():
    from datetime import date
    assert semana_de(pd.Series([date(2026, 1, 12)])).iloc[0] == martes(0)


def test_precio_semanal_promedia_y_da_minimo_y_maximo():
    silver = pd.concat([precios_silver({"super": {0: 30.0}}, dia=0),
                        precios_silver({"super": {0: 32.0}}, dia=6)])  # lunes: sigue en la semana 0
    semanal = precio_semanal(silver)
    fila = semanal.iloc[0]
    assert len(semanal) == 1
    assert (fila.precio_promedio, fila.precio_minimo, fila.precio_maximo, fila.n_lecturas) == (31.0, 30.0, 32.0, 2)


def test_variacion_usa_la_semana_calendario_anterior():
    semanal = precio_semanal(precios_silver({"super": {0: 30.0, 1: 30.5}}))
    var = variacion_semanal(semanal, umbral_q=0.10).set_index("semana")
    assert var.loc[martes(1), "diferencia_q"] == pytest.approx(0.5)
    assert var.loc[martes(1), "precio_anterior"] == 30.0
    assert var.loc[martes(1), "semana_anterior_disponible"]
    assert var.loc[martes(1), "direccion"] == "sube"


def test_un_hueco_deja_la_variacion_nula_y_no_compara_con_semanas_lejanas():
    semanal = precio_semanal(precios_silver({"super": {0: 30.0, 1: 30.5, 4: 35.0}}))
    var = variacion_semanal(semanal, umbral_q=0.10).set_index("semana")
    fila = var.loc[martes(4)]
    assert not fila.semana_anterior_disponible
    assert math.isnan(fila.diferencia_q) and math.isnan(fila.diferencia_pct) and math.isnan(fila.precio_anterior)
    assert fila.direccion is None


def test_primera_semana_no_tiene_anterior():
    var = variacion_semanal(precio_semanal(precios_silver({"super": {0: 30.0}})), umbral_q=0.10)
    assert not var.iloc[0].semana_anterior_disponible and var.iloc[0].direccion is None


def test_diferencia_porcentual():
    var = variacion_semanal(precio_semanal(precios_silver({"regular": {0: 20.0, 1: 21.0}})), 0.10)
    assert var.set_index("semana").loc[martes(1), "diferencia_pct"] == pytest.approx(5.0)


def test_cada_combustible_se_compara_solo_con_si_mismo():
    silver = precios_silver({"super": {0: 30.0, 1: 31.0}, "diesel": {1: 25.0, 2: 24.0}})
    var = variacion_semanal(precio_semanal(silver), 0.10).set_index(["combustible", "semana"])
    assert not var.loc[("diesel", martes(1)), "semana_anterior_disponible"]  # súper sí tiene semana 0
    assert var.loc[("diesel", martes(2)), "direccion"] == "baja"


@pytest.mark.parametrize("diferencia, esperado", [
    (0.10, "se_mantiene"),   # justo en el umbral no cuenta como cambio
    (-0.10, "se_mantiene"),
    (0.11, "sube"),
    (-0.11, "baja"),
    (0.0, "se_mantiene"),
])
def test_etiquetas_con_umbral(diferencia, esperado):
    assert etiquetar_direccion(pd.Series([diferencia]), 0.10).iloc[0] == esperado


def test_el_umbral_es_un_parametro():
    diferencia = pd.Series([0.10])
    assert etiquetar_direccion(diferencia, 0.05).iloc[0] == "sube"
    assert etiquetar_direccion(diferencia, 0.50).iloc[0] == "se_mantiene"


def test_error_de_punto_flotante_no_cruza_el_umbral():
    # 20.10 - 20.00 = 0.10000000000000142 en flotante, pero para el negocio es exactamente Q0.10
    var = variacion_semanal(precio_semanal(precios_silver({"super": {0: 20.0, 1: 20.1}})), 0.10)
    assert var.set_index("semana").loc[martes(1), "direccion"] == "se_mantiene"


def test_diferencia_nula_no_tiene_etiqueta():
    assert etiquetar_direccion(pd.Series([float("nan")]), 0.10).iloc[0] is None


def test_wti_semanal_convierte_texto_ignora_vacios_y_promedia_martes_a_lunes():
    raw = pd.DataFrame({
        "observation_date": ["2026-01-06", "2026-01-07", "2026-01-11", "2026-01-12", "2026-01-13"],
        "DCOILWTICO": ["70", "72", "", "74", "80"],
    })
    wti = wti_semanal(raw).set_index("semana")["wti_semanal"]
    assert wti[martes(0)] == pytest.approx(72.0)  # (70 + 72 + 74) / 3, el vacío no cuenta
    assert wti[martes(1)] == pytest.approx(80.0)


def test_wti_semanal_tolera_marcadores_no_numericos_de_fred():
    raw = pd.DataFrame({"observation_date": ["2026-01-06", "2026-01-07"], "DCOILWTICO": [".", "71.5"]})
    assert wti_semanal(raw).iloc[0].wti_semanal == pytest.approx(71.5)
