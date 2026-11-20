"""Validación temporal, línea base, elección del modelo, modo «pocos datos» y ausencia de fuga."""
from __future__ import annotations

import pandas as pd
import pytest

from gasolina_gt.gold.features import construir_features
from gasolina_gt.gold.modeling import (
    contar_triples, dividir_temporal, ejemplos_etiquetados, entrenar_y_evaluar, metricas_clasificacion,
    pliegues_temporales, supera_linea_base,
)
from gasolina_gt.gold.params import GoldParams
from gasolina_gt.gold.weekly import precio_semanal, variacion_semanal
from tests.unit.gold_helpers import martes, precios_silver, serie_alternante


def _features(silver, umbral=0.10):
    return construir_features(variacion_semanal(precio_semanal(silver), umbral))


@pytest.fixture
def alternante():
    return _features(serie_alternante(30))


def test_triples_cuenta_solo_semanas_t_menos_1_t_y_t_mas_1_consecutivas():
    feats = _features(precios_silver({"super": {0: 20.0, 1: 21.0, 2: 20.0, 3: 22.0},
                                      "diesel": {0: 20.0, 1: 21.0, 3: 22.0, 4: 21.0}}))
    assert contar_triples(feats) == {"diesel": 0, "super": 2}


def test_ejemplos_etiquetados_exigen_direccion_actual_y_siguiente(alternante):
    ej = ejemplos_etiquetados(alternante)
    assert ej["direccion_actual"].notna().all() and ej["direccion_siguiente"].notna().all()
    assert len(ej) == 28 * 3


def test_division_temporal_deja_las_ultimas_semanas_para_test(alternante):
    train, test = dividir_temporal(ejemplos_etiquetados(alternante), semanas_test=4)
    assert test["semana"].nunique() == 4
    assert train["semana"].max() < test["semana"].min()  # nunca aleatoria
    assert len(train) + len(test) == len(ejemplos_etiquetados(alternante))


def test_pliegues_temporales_validan_siempre_en_el_futuro_del_entrenamiento(alternante):
    train, _ = dividir_temporal(ejemplos_etiquetados(alternante), 4)
    pliegues = pliegues_temporales(train, n_pliegues=3)
    assert len(pliegues) == 3
    for idx_train, idx_val in pliegues:
        assert train.loc[idx_train, "semana"].max() < train.loc[idx_val, "semana"].min()


def test_sin_datos_suficientes_no_hay_pliegues():
    feats = _features(precios_silver({"super": {0: 20.0, 1: 21.0, 2: 20.0, 3: 22.0}}))
    assert pliegues_temporales(ejemplos_etiquetados(feats), n_pliegues=3) == []


def test_metricas_accuracy_y_f1_macro():
    m = metricas_clasificacion(["sube", "baja", "sube", "baja"], ["sube", "baja", "baja", "baja"])
    assert m["accuracy"] == pytest.approx(0.75)
    assert m["f1_macro"] == pytest.approx((2 / 3 + 0.8) / 2)


@pytest.mark.parametrize("modelo, base, esperado", [
    ({"accuracy": 0.8, "f1_macro": 0.7}, {"accuracy": 0.6, "f1_macro": 0.5}, True),
    ({"accuracy": 0.6, "f1_macro": 0.5}, {"accuracy": 0.6, "f1_macro": 0.5}, False),   # empate → línea base
    ({"accuracy": 0.5, "f1_macro": 0.7}, {"accuracy": 0.6, "f1_macro": 0.5}, False),   # mejor F1 pero peor accuracy
    ({"accuracy": 0.6, "f1_macro": 0.4}, {"accuracy": 0.5, "f1_macro": 0.5}, False),
])
def test_regla_para_elegir_el_modelo_final(modelo, base, esperado):
    assert supera_linea_base(modelo, base) is esperado


def test_el_modelo_se_usa_cuando_supera_a_la_linea_base(alternante):
    r = entrenar_y_evaluar(alternante, GoldParams())
    assert not r.modo_pocos_datos
    assert r.metricas_linea_base["accuracy"] == 0.0           # la dirección siempre cambia
    assert r.metricas_modelo["accuracy"] == pytest.approx(1.0)
    assert not r.usa_linea_base
    assert r.modelo_elegido in {"regresion_logistica", "arbol_decision"}
    assert r.n_test == 12 and r.n_train == 72
    assert r.validado_en_train and set(r.cv_f1) == {"regresion_logistica", "arbol_decision"}
    clf = r.modelo_ajustado.named_steps["clf"]
    if r.modelo_elegido == "regresion_logistica":
        assert r.hiperparametros["C"] in {0.1, 1.0, 10.0}
        assert clf.C == r.hiperparametros["C"]
    else:
        assert r.hiperparametros["max_depth"] in {2, 3, 4}
        assert r.hiperparametros["min_samples_leaf"] in {2, 3, 5}
        assert clf.max_depth == r.hiperparametros["max_depth"]
        assert clf.min_samples_leaf == r.hiperparametros["min_samples_leaf"]


def test_si_el_modelo_no_supera_a_la_linea_base_se_usa_la_linea_base():
    # el precio sube cada semana salvo una: en test todo es «sube», la línea base acierta 100 % y el modelo solo la empata
    series = {c: {n: 20.0 + i + 0.5 * n - (3.0 if n >= 14 else 0.0) for n in range(30)}
              for i, c in enumerate(("super", "regular", "diesel"))}
    r = entrenar_y_evaluar(_features(precios_silver(series)), GoldParams())
    assert not r.modo_pocos_datos
    assert r.metricas_linea_base["accuracy"] == 1.0
    assert r.usa_linea_base and r.modelo_elegido == "linea_base"
    assert set(r.backtest["modelo"]) == {"linea_base"}
    assert "línea base" in r.motivo.lower()


def test_pocos_datos_no_falla_y_predice_con_la_linea_base():
    feats = _features(precios_silver({"super": {0: 20.0, 1: 21.0, 2: 20.0, 3: 22.0}}))
    r = entrenar_y_evaluar(feats, GoldParams())
    assert r.modo_pocos_datos and r.usa_linea_base and r.modelo_elegido == "linea_base"
    assert r.metricas_modelo is None
    assert "pocos" in r.motivo.lower()
    fila = r.pronostico.iloc[0]
    assert (fila.combustible, fila.semana, fila.modelo) == ("super", martes(4), "linea_base")
    assert fila.prediccion == "sube"  # la dirección de la última semana (20→22) se repite
    assert pd.isna(fila.probabilidad)


def test_sin_ningun_dato_etiquetado_tampoco_falla():
    feats = _features(precios_silver({"super": {0: 20.0}}))
    r = entrenar_y_evaluar(feats, GoldParams())
    assert r.modo_pocos_datos and r.backtest.empty
    fila = r.pronostico.iloc[0]   # aun así hay un pronóstico: el respaldo
    assert (fila.combustible, fila.semana, fila.prediccion, fila.modelo) == ("super", martes(1), "se_mantiene",
                                                                         "linea_base_respaldo")


def test_el_minimo_de_ejemplos_es_un_parametro(alternante):
    r = entrenar_y_evaluar(alternante, GoldParams(min_ejemplos=500))
    assert r.modo_pocos_datos


def test_pronostico_de_la_semana_siguiente_a_la_ultima_con_datos(alternante):
    r = entrenar_y_evaluar(alternante, GoldParams())
    assert set(r.pronostico["combustible"]) == {"super", "regular", "diesel"}
    assert (r.pronostico["semana"] == martes(30)).all()
    assert r.pronostico["probabilidad"].between(0, 1).all()
    assert r.pronostico["direccion_real"].isna().all()
    assert (r.pronostico["tipo"] == "pronostico").all()
    # la semana 29 fue «sube» → la siguiente «baja»
    assert set(r.pronostico["prediccion"]) == {"baja"}


def test_backtest_cubre_las_semanas_de_test_con_la_direccion_real(alternante):
    r = entrenar_y_evaluar(alternante, GoldParams())
    assert (r.backtest["tipo"] == "backtest").all()
    assert len(r.backtest) == r.n_test
    assert r.backtest["direccion_real"].notna().all()
    assert (r.backtest["prediccion"] == r.backtest["direccion_real"]).all()


def test_sin_fuga_el_test_no_influye_en_la_eleccion_ni_en_el_ajuste(alternante):
    """Cambiar las etiquetas de las semanas de test no puede alterar el candidato ni sus predicciones."""
    base = entrenar_y_evaluar(alternante, GoldParams())
    _, test = dividir_temporal(ejemplos_etiquetados(alternante), 4)
    alterado = alternante.copy()
    marca = alterado.set_index(["combustible", "semana"]).index.isin(list(zip(test.combustible, test.semana)))
    alterado.loc[marca, "direccion_siguiente"] = alterado.loc[marca, "direccion_siguiente"].map(
        {"sube": "baja", "baja": "sube"})
    r2 = entrenar_y_evaluar(alterado, GoldParams())
    assert r2.candidato == base.candidato
    assert r2.cv_f1 == base.cv_f1
    columnas = ["semana", "combustible", "prediccion", "probabilidad"]   # direccion_real sí cambia: es la etiqueta alterada
    pd.testing.assert_frame_equal(r2.candidato_test[columnas].reset_index(drop=True),
                                  base.candidato_test[columnas].reset_index(drop=True))


def test_validacion_observada_usa_mas_semanas_sin_mirar_el_holdout(alternante):
    plata_observada = serie_alternante(30)
    observados = _features(plata_observada.loc[~plata_observada["fecha"].isin(
        [martes(n) for n in range(5, 14)])])
    base = entrenar_y_evaluar(alternante, GoldParams(), observados)
    assert base.validado_en_train
    assert "ejemplos observados de validación interna" in base.motivo
    assert base.n_test == 12
    assert base.n_validacion_cv > base.n_test

    alterado = observados.copy()
    ultimas = sorted(ejemplos_etiquetados(alterado)["semana"].unique())[-4:]
    alterado.loc[alterado["semana"].isin(ultimas), "direccion_siguiente"] = "se_mantiene"
    despues = entrenar_y_evaluar(alternante, GoldParams(), alterado)
    assert despues.candidato == base.candidato
    assert despues.cv_f1 == base.cv_f1
    assert despues.hiperparametros == base.hiperparametros
    columnas = ["semana", "combustible", "prediccion", "probabilidad"]
    pd.testing.assert_frame_equal(despues.candidato_test[columnas], base.candidato_test[columnas])


def test_no_optimiza_con_menos_de_seis_ejemplos_observados(alternante):
    observados = alternante[alternante["semana"].isin([martes(n) for n in range(19, 25)])]
    r = entrenar_y_evaluar(alternante, GoldParams(), observados)
    assert not r.validado_en_train
    assert r.cv_f1 == {}
    assert r.candidato == "regresion_logistica"
    assert r.n_validacion_cv < 6


def test_mismo_resultado_en_dos_ejecuciones(alternante):
    a, b = entrenar_y_evaluar(alternante, GoldParams()), entrenar_y_evaluar(alternante, GoldParams())
    pd.testing.assert_frame_equal(a.pronostico, b.pronostico)
    assert a.metricas_modelo == b.metricas_modelo


def test_si_no_se_puede_validar_dentro_de_train_se_usa_la_logistica():
    # 32 ejemplos (8 combustibles × 4 semanas): alcanza el mínimo, pero train solo tiene 3 semanas distintas
    combustibles = tuple(f"c{i}" for i in range(8))
    feats = _features(serie_alternante(6, combustibles=combustibles))
    r = entrenar_y_evaluar(feats, GoldParams(semanas_test=1))
    assert not r.modo_pocos_datos
    assert not r.validado_en_train and r.cv_f1 == {}
    assert r.candidato == "regresion_logistica"
    assert "limitación" in r.motivo.lower()


def _pronosticos(r):
    return r.pronostico.set_index("combustible")


def test_sin_direccion_actual_usa_la_ultima_direccion_conocida_del_combustible():
    # la semana 4 llega tras un hueco: no tiene semana anterior, pero la semana 1 subió
    r = entrenar_y_evaluar(_features(precios_silver({"super": {0: 20.0, 1: 21.0, 4: 25.0}})), GoldParams())
    fila = _pronosticos(r).loc["super"]
    assert (fila.semana, fila.prediccion, fila.modelo) == (martes(5), "sube", "linea_base_respaldo")
    assert pd.isna(fila.probabilidad) and pd.isna(fila.direccion_real)


def test_sin_ninguna_direccion_conocida_el_respaldo_es_se_mantiene():
    r = entrenar_y_evaluar(_features(precios_silver({"diesel": {3: 25.0}})), GoldParams())
    fila = _pronosticos(r).loc["diesel"]
    assert (fila.semana, fila.prediccion, fila.modelo) == (martes(4), "se_mantiene", "linea_base_respaldo")


def test_cada_combustible_se_pronostica_desde_su_propia_ultima_semana():
    series = {"super": {n: 20.0 + n for n in range(6)}, "diesel": {n: 25.0 - n for n in range(3)}}
    r = entrenar_y_evaluar(_features(precios_silver(series)), GoldParams())
    pron = _pronosticos(r)
    assert pron.loc["super", "semana"] == martes(6) and pron.loc["super", "modelo"] == "linea_base"
    assert pron.loc["diesel", "semana"] == martes(3) and pron.loc["diesel", "prediccion"] == "baja"   # no queda sin fila
    assert len(r.pronostico) == 2 and (r.pronostico["tipo"] == "pronostico").all()


def test_con_modelo_entrenado_tambien_hay_una_fila_por_combustible_desde_su_ultima_semana():
    series = {c: {n: 20.0 + i + (0.5 if n % 2 else 0.0) for n in range(30)} for i, c in enumerate(("super", "regular"))}
    series["diesel"] = {n: 22.0 + (0.5 if n % 2 else 0.0) for n in range(21)}   # su última semana es la 20
    r = entrenar_y_evaluar(_features(precios_silver(series)), GoldParams())
    assert not r.modo_pocos_datos and not r.usa_linea_base
    pron = _pronosticos(r)
    assert set(pron.index) == {"super", "regular", "diesel"}
    assert pron.loc["diesel", "semana"] == martes(21) and pron.loc["super", "semana"] == martes(30)
    assert set(pron["modelo"]) == {r.modelo_elegido}


def test_con_modelo_un_combustible_sin_semana_anterior_tambien_recibe_pronostico():
    series = {c: {n: 20.0 + i + (0.5 if n % 2 else 0.0) for n in range(30)} for i, c in enumerate(("super", "regular"))}
    series["diesel"] = {**{n: 22.0 + (0.5 if n % 2 else 0.0) for n in range(25)}, 29: 22.5}   # la 29 llega tras un hueco
    r = entrenar_y_evaluar(_features(precios_silver(series)), GoldParams())
    assert not r.modo_pocos_datos
    fila = _pronosticos(r).loc["diesel"]
    assert fila.semana == martes(30) and fila.prediccion in {"sube", "baja", "se_mantiene"}
