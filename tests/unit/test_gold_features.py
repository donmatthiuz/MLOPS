"""Features por semana calendario, objetivo `direccion_siguiente` y ausencia de fuga de información."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from gasolina_gt.gold.features import construir_features
from gasolina_gt.gold.weekly import precio_semanal, variacion_semanal, wti_semanal
from tests.unit.gold_helpers import martes, precios_silver, serie_alternante, wti_crudo

COLUMNAS_FEATURES = ["variacion_lag_1", "variacion_lag_2", "variacion_lag_3", "variacion_lag_4",
                     "promedio_movil_4", "dif_super_diesel", "wti_semanal", "wti_variacion"]


def _features(series, wti=None, umbral=0.10):
    var = variacion_semanal(precio_semanal(precios_silver(series)), umbral)
    return construir_features(var, wti_semanal(wti) if wti is not None else None).set_index(["combustible", "semana"])


def test_tiene_las_columnas_esperadas():
    feats = construir_features(variacion_semanal(precio_semanal(precios_silver({"super": {0: 30.0, 1: 31.0}})), 0.10))
    assert {"semana", "combustible", "precio_promedio", "direccion_actual", "direccion_siguiente",
            *COLUMNAS_FEATURES} <= set(feats.columns)


def test_los_rezagos_son_semanas_calendario_no_filas_anteriores():
    # semanas 0,1,2 y 4: falta la 3
    f = _features({"super": {0: 20.0, 1: 20.5, 2: 21.0, 4: 21.2}})
    fila = f.loc[("super", martes(4))]
    assert math.isnan(fila.variacion_lag_1)       # la semana 4 no tiene semana 3 para compararse
    assert math.isnan(fila.variacion_lag_2)       # la semana 3 no existe (con «fila anterior» daría 0.5)
    assert fila.variacion_lag_3 == pytest.approx(0.5)  # variación de la semana 2
    assert fila.variacion_lag_4 == pytest.approx(0.5)  # variación de la semana 1


def test_variacion_lag_1_es_la_variacion_de_la_ultima_semana_conocida():
    f = _features({"super": {0: 20.0, 1: 20.5, 2: 20.2}})
    assert f.loc[("super", martes(2)), "variacion_lag_1"] == pytest.approx(-0.3)
    assert f.loc[("super", martes(2)), "variacion_lag_2"] == pytest.approx(0.5)


def test_promedio_movil_usa_solo_semanas_dentro_de_las_ultimas_cuatro():
    f = _features({"super": {0: 10.0, 1: 20.0, 2: 21.0, 4: 22.0}})
    # ventana de la semana 4 = semanas 1..4; existen 1, 2 y 4
    assert f.loc[("super", martes(4)), "promedio_movil_4"] == pytest.approx((20.0 + 21.0 + 22.0) / 3)


def test_promedio_movil_pide_al_menos_dos_semanas():
    f = _features({"super": {0: 10.0, 5: 22.0}})
    assert math.isnan(f.loc[("super", martes(5)), "promedio_movil_4"])


def test_diferencia_super_diesel_es_de_la_misma_semana():
    f = _features({"super": {0: 30.0, 1: 31.0, 2: 32.0}, "diesel": {0: 25.0, 2: 26.0}})
    assert f.loc[("super", martes(0)), "dif_super_diesel"] == pytest.approx(5.0)
    assert math.isnan(f.loc[("super", martes(1)), "dif_super_diesel"])  # no hay diésel esa semana
    assert f.loc[("diesel", martes(2)), "dif_super_diesel"] == pytest.approx(6.0)


def test_objetivo_es_la_direccion_de_la_semana_mas_siete_dias():
    f = _features({"super": {0: 20.0, 1: 21.0, 2: 20.0, 4: 25.0}})
    assert f.loc[("super", martes(1)), "direccion_siguiente"] == "baja"
    assert f.loc[("super", martes(2)), "direccion_siguiente"] is None  # semana 3 no existe
    assert f.loc[("super", martes(4)), "direccion_siguiente"] is None  # última semana: se predice


def test_direccion_actual_coincide_con_la_variacion_semanal():
    f = _features({"super": {0: 20.0, 1: 21.0, 2: 21.05}})
    assert f.loc[("super", martes(0)), "direccion_actual"] is None
    assert f.loc[("super", martes(1)), "direccion_actual"] == "sube"
    assert f.loc[("super", martes(2)), "direccion_actual"] == "se_mantiene"


def test_wti_semanal_y_su_variacion_contra_la_semana_anterior():
    f = _features({"super": {0: 20.0, 1: 21.0, 3: 22.0}}, wti=wti_crudo(4, 70.0))
    assert f.loc[("super", martes(1)), "wti_semanal"] == pytest.approx(71.0)
    assert f.loc[("super", martes(1)), "wti_variacion"] == pytest.approx(1.0)
    assert f.loc[("super", martes(3)), "wti_variacion"] == pytest.approx(1.0)  # semana 2 del WTI sí existe


def test_wti_variacion_nula_si_falta_la_semana_anterior_del_wti():
    wti = wti_crudo(4)
    wti = wti[~wti["observation_date"].between("2026-01-13", "2026-01-19")]  # sin semana 1
    f = _features({"super": {0: 20.0, 1: 21.0, 2: 22.0}}, wti=wti)
    assert math.isnan(f.loc[("super", martes(2)), "wti_variacion"])


def test_sin_wti_las_columnas_existen_y_son_nulas():
    f = _features({"super": {0: 20.0, 1: 21.0}})
    assert f["wti_semanal"].isna().all() and f["wti_variacion"].isna().all()


def test_sin_fuga_de_informacion_futura():
    """Las variables de la semana k no cambian si se borra todo lo que ocurre después de k."""
    silver = serie_alternante(12)
    wti = wti_crudo(12)
    umbral = 0.10
    completo = construir_features(variacion_semanal(precio_semanal(silver), umbral), wti_semanal(wti))
    corte = martes(6)
    silver_corte = silver[pd.to_datetime(silver["fecha"]) < corte + pd.Timedelta(days=7)]
    wti_corte = wti[pd.to_datetime(wti["observation_date"]) < corte + pd.Timedelta(days=7)]
    recortado = construir_features(variacion_semanal(precio_semanal(silver_corte), umbral), wti_semanal(wti_corte))
    llaves = ["combustible", "semana"]
    a = completo[completo.semana <= corte].set_index(llaves)[["precio_promedio", "direccion_actual", *COLUMNAS_FEATURES]]
    b = recortado.set_index(llaves)[["precio_promedio", "direccion_actual", *COLUMNAS_FEATURES]]
    pd.testing.assert_frame_equal(a.sort_index(), b.sort_index())
