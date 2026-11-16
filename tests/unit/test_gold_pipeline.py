"""`compute_gold` de punta a punta en pandas (sin Spark), más COMMENT y ayudantes de Databricks."""
from __future__ import annotations

import pandas as pd
import pytest

from gasolina_gt.gold.comments import COLUMNAS, COMENTARIOS_TABLA, sentencias_comentarios
from gasolina_gt.gold.params import GoldParams
from gasolina_gt.gold.pipeline import compute_gold
from tests.unit.gold_helpers import martes, precios_silver, serie_alternante, wti_crudo

T0 = pd.Timestamp("2026-11-15 10:00:00")
TABLAS = ("precio_semanal", "variacion_semanal", "features_modelo", "predicciones", "metricas_modelo")


def _tablas(res):
    return {"precio_semanal": res.precio_semanal, "variacion_semanal": res.variacion_semanal,
            "features_modelo": res.features_modelo, "predicciones": res.predicciones,
            "metricas_modelo": res.metricas_modelo}


def test_genera_las_cinco_tablas_con_los_datos_alternantes():
    res = compute_gold(serie_alternante(30), wti_crudo(30), GoldParams(), generado_en=T0, log=lambda *_: None)
    tablas = _tablas(res)
    assert all(len(t) > 0 for t in tablas.values())
    pred = res.predicciones
    assert set(pred["tipo"]) == {"backtest", "pronostico"}
    assert set(pred[pred.tipo == "pronostico"]["semana"]) == {martes(30)}


def test_metricas_una_fila_con_los_campos_del_contrato():
    res = compute_gold(serie_alternante(30), None, GoldParams(), generado_en=T0, log=lambda *_: None)
    m = res.metricas_modelo
    assert len(m) == 1
    fila = m.iloc[0]
    assert fila.modo_pocos_datos is False or not fila.modo_pocos_datos
    assert fila.accuracy_linea_base == 0.0 and fila.accuracy_modelo == pytest.approx(1.0)
    assert fila.n_train == 72 and fila.n_test == 12
    assert fila.umbral_q == 0.10 and fila.semanas_test == 4 and not fila.usa_wti
    assert fila["_generado_en"] == T0


def test_el_run_id_de_mlflow_queda_en_las_metricas():
    llamadas = []

    def tracker(parametros, metricas, modelo):
        llamadas.append((parametros, metricas, modelo))
        return "run-xyz"

    res = compute_gold(serie_alternante(30), None, GoldParams(), generado_en=T0, tracker=tracker, log=lambda *_: None)
    assert res.metricas_modelo.iloc[0].run_id_mlflow == "run-xyz"
    parametros, metricas, modelo = llamadas[0]
    assert {"umbral_q", "semanas_test", "features", "usar_wti", "candidato"} <= set(parametros)
    assert metricas["accuracy_linea_base"] == 0.0 and modelo is not None


def test_con_pocos_datos_escribe_todo_predice_con_la_linea_base_y_lo_marca(capsys):
    silver = precios_silver({"super": {0: 20.0, 1: 21.0, 2: 20.0, 3: 22.0}})
    res = compute_gold(silver, None, GoldParams(), generado_en=T0)
    out = capsys.readouterr().out.lower()
    assert "pocos datos" in out
    assert len(res.precio_semanal) == 4 and len(res.variacion_semanal) == 4
    fila = res.metricas_modelo.iloc[0]
    assert fila.modo_pocos_datos and fila.modelo_elegido == "linea_base" and fila.usa_linea_base
    assert (res.predicciones["modelo"] == "linea_base").all()


def test_imprime_el_conteo_de_triples_por_combustible_al_inicio(capsys):
    compute_gold(serie_alternante(10), None, GoldParams(), generado_en=T0)
    primera_linea = capsys.readouterr().out.splitlines()[0].lower()
    assert "triples" in primera_linea and "super=8" in primera_linea and "diesel=8" in primera_linea


def test_usar_wti_false_ignora_la_serie_de_petroleo():
    con = compute_gold(serie_alternante(30), wti_crudo(30), GoldParams(usar_wti=False), generado_en=T0, log=lambda *_: None)
    assert con.features_modelo["wti_semanal"].isna().all()


def test_reejecutar_con_las_mismas_fotos_es_idempotente():
    args = dict(generado_en=T0, log=lambda *_: None)
    uno = compute_gold(serie_alternante(30), wti_crudo(30), GoldParams(), **args)
    dos = compute_gold(serie_alternante(30), wti_crudo(30), GoldParams(), previas=uno.predicciones, **args)
    llaves = ["semana", "combustible", "tipo"]
    pd.testing.assert_frame_equal(uno.predicciones.sort_values(llaves).reset_index(drop=True),
                                  dos.predicciones.sort_values(llaves).reset_index(drop=True))


def test_una_semana_nueva_completa_la_direccion_real_del_pronostico_anterior():
    uno = compute_gold(serie_alternante(30), None, GoldParams(), generado_en=T0, log=lambda *_: None)
    dos = compute_gold(serie_alternante(31), None, GoldParams(), previas=uno.predicciones,
                       generado_en=T0 + pd.Timedelta(days=7), log=lambda *_: None)
    p = dos.predicciones
    anterior = p[(p.tipo == "pronostico") & (p.semana == martes(30)) & (p.combustible == "super")].iloc[0]
    assert anterior.direccion_real == "baja"      # la semana 30 (par) baja respecto a la 29
    assert anterior.prediccion == "baja"          # lo que se había pronosticado una semana antes
    nuevo = p[(p.tipo == "pronostico") & (p.semana == martes(31))]
    assert len(nuevo) == 3 and nuevo["direccion_real"].isna().all()


def test_toda_columna_de_oro_tiene_comentario():
    res = compute_gold(serie_alternante(30), wti_crudo(30), GoldParams(), generado_en=T0, log=lambda *_: None)
    for nombre, tabla in _tablas(res).items():
        assert nombre in COMENTARIOS_TABLA
        faltan = set(tabla.columns) - set(COLUMNAS[nombre])
        assert not faltan, f"{nombre}: columnas sin COMMENT {sorted(faltan)}"


def test_sentencias_de_comentarios_para_unity_catalog():
    sentencias = sentencias_comentarios("workspace.equipo7.gold_predicciones", "predicciones")
    assert sentencias[0].startswith("COMMENT ON TABLE workspace.equipo7.gold_predicciones IS '")
    assert any(s.startswith("ALTER TABLE workspace.equipo7.gold_predicciones ALTER COLUMN tipo COMMENT '")
               for s in sentencias)
    assert len(sentencias) == 1 + len(COLUMNAS["predicciones"])


def test_los_comentarios_escapan_las_comillas_simples():
    from gasolina_gt.gold import comments
    original = dict(comments.COMENTARIOS_TABLA)
    comments.COMENTARIOS_TABLA["precio_semanal"] = "Precio de la semana d'Oro"
    try:
        assert "d''Oro" in comments.sentencias_comentarios("t", "precio_semanal")[0]
    finally:
        comments.COMENTARIOS_TABLA.clear()
        comments.COMENTARIOS_TABLA.update(original)


def test_comentarios_explican_las_metricas():
    textos = " ".join(COLUMNAS["metricas_modelo"].values()).lower()
    for palabra in ("accuracy", "f1", "línea base"):
        assert palabra in textos


def test_siempre_hay_un_pronostico_por_combustible_en_cualquier_modo():
    # súper llega tras un hueco, regular termina antes que los demás y diésel tiene una sola semana
    silver = precios_silver({"super": {0: 20.0, 1: 21.0, 5: 22.0}, "regular": {0: 20.0, 1: 21.0, 2: 21.5},
                             "diesel": {5: 18.0}})
    res = compute_gold(silver, None, GoldParams(), generado_en=T0, log=lambda *_: None)
    pron = res.predicciones[res.predicciones.tipo == "pronostico"].set_index("combustible")
    assert res.metricas_modelo.iloc[0].modo_pocos_datos
    assert pron["semana"].to_dict() == {"super": martes(6), "regular": martes(3), "diesel": martes(6)}
    assert pron.loc["super", "modelo"] == "linea_base_respaldo" and pron.loc["super", "prediccion"] == "sube"
    assert pron.loc["regular", "modelo"] == "linea_base" and pron.loc["regular", "prediccion"] == "sube"
    assert pron.loc["diesel", "modelo"] == "linea_base_respaldo" and pron.loc["diesel", "prediccion"] == "se_mantiene"
