"""Tabla de predicciones: clave (semana, combustible, tipo), relleno de la dirección real e idempotencia."""
from __future__ import annotations

import pandas as pd

from gasolina_gt.gold.predictions import COLUMNAS_PREDICCIONES, combinar_predicciones
from tests.unit.gold_helpers import martes

T0 = pd.Timestamp("2026-11-15 10:00:00")
T1 = pd.Timestamp("2026-11-22 10:00:00")


def _fila(semana, combustible="super", tipo="pronostico", prediccion="sube", real=None, modelo="regresion_logistica",
          probabilidad=0.7):
    return {"semana": martes(semana), "combustible": combustible, "prediccion": prediccion,
            "probabilidad": probabilidad, "modelo": modelo, "direccion_real": real, "tipo": tipo}


def _reales(*filas):
    return pd.DataFrame(filas, columns=["semana", "combustible", "direccion"]).assign(
        semana=lambda d: d["semana"].map(martes))


def _ordenar(df):
    return df.sort_values(["semana", "combustible", "tipo"]).reset_index(drop=True)


def test_primera_ejecucion_crea_la_tabla_con_las_columnas_del_contrato():
    out = combinar_predicciones(None, pd.DataFrame([_fila(5)]), _reales(), T0)
    assert list(out.columns) == COLUMNAS_PREDICCIONES
    assert COLUMNAS_PREDICCIONES == ["semana", "combustible", "tipo", "prediccion", "probabilidad", "modelo",
                                     "direccion_real", "_generado_en"]
    assert (out["_generado_en"] == T0).all()


def test_idempotente_al_repetir_la_misma_ejecucion():
    nuevas = pd.DataFrame([_fila(5), _fila(4, tipo="backtest", real="baja", prediccion="baja")])
    reales = _reales((3, "super", "baja"))
    una = combinar_predicciones(None, nuevas, reales, T0)
    dos = combinar_predicciones(una, nuevas, reales, T0)
    tres = combinar_predicciones(dos, nuevas, reales, T0)
    pd.testing.assert_frame_equal(_ordenar(una), _ordenar(dos))
    pd.testing.assert_frame_equal(_ordenar(dos), _ordenar(tres))
    assert len(tres) == 2


def test_la_clave_incluye_el_tipo_y_permite_backtest_y_pronostico_de_la_misma_semana():
    nuevas = pd.DataFrame([_fila(5, tipo="pronostico"), _fila(5, tipo="backtest", real="sube")])
    out = combinar_predicciones(None, nuevas, _reales(), T0)
    assert sorted(out["tipo"]) == ["backtest", "pronostico"]


def test_rellena_la_direccion_real_cuando_la_semana_ya_ocurrio_y_conserva_la_prediccion_original():
    primera = combinar_predicciones(None, pd.DataFrame([_fila(5, prediccion="sube")]), _reales(), T0)
    assert primera["direccion_real"].isna().all()
    # pasa una semana: ya existe la semana 5 y se pronostica la 6
    segunda = combinar_predicciones(primera, pd.DataFrame([_fila(6, prediccion="baja")]),
                                    _reales((5, "super", "baja")), T1)
    s5 = segunda[segunda.semana == martes(5)].iloc[0]
    assert (s5.prediccion, s5.direccion_real, s5._generado_en) == ("sube", "baja", T0)  # no se reescribe el pasado
    s6 = segunda[segunda.semana == martes(6)].iloc[0]
    assert s6.prediccion == "baja" and pd.isna(s6.direccion_real)


def test_un_pronostico_aun_sin_resultado_se_actualiza_al_reejecutar():
    primera = combinar_predicciones(None, pd.DataFrame([_fila(5, prediccion="sube", probabilidad=0.6)]), _reales(), T0)
    segunda = combinar_predicciones(primera, pd.DataFrame([_fila(5, prediccion="baja", probabilidad=0.9)]),
                                    _reales(), T1)
    assert len(segunda) == 1
    assert (segunda.iloc[0].prediccion, segunda.iloc[0].probabilidad, segunda.iloc[0]._generado_en) == ("baja", 0.9, T1)


def test_un_pronostico_ya_resuelto_no_se_sobrescribe_aunque_el_modelo_cambie():
    primera = combinar_predicciones(None, pd.DataFrame([_fila(5, prediccion="sube")]), _reales(), T0)
    cerrada = combinar_predicciones(primera, pd.DataFrame(columns=COLUMNAS_PREDICCIONES), _reales((5, "super", "sube")), T0)
    reintento = combinar_predicciones(cerrada, pd.DataFrame([_fila(5, prediccion="baja", modelo="arbol_decision")]),
                                      _reales((5, "super", "sube")), T1)
    fila = reintento.iloc[0]
    assert (fila.prediccion, fila.modelo, fila.direccion_real) == ("sube", "regresion_logistica", "sube")


def test_el_backtest_se_recalcula_con_el_modelo_actual():
    primera = combinar_predicciones(None, pd.DataFrame([_fila(4, tipo="backtest", prediccion="sube", real="baja")]),
                                    _reales(), T0)
    segunda = combinar_predicciones(primera, pd.DataFrame([_fila(4, tipo="backtest", prediccion="baja", real="baja",
                                                                  modelo="arbol_decision")]), _reales(), T1)
    assert len(segunda) == 1 and segunda.iloc[0].modelo == "arbol_decision" and segunda.iloc[0].prediccion == "baja"


def test_el_backtest_pasado_que_ya_no_esta_en_test_se_conserva():
    primera = combinar_predicciones(None, pd.DataFrame([_fila(3, tipo="backtest", real="sube")]), _reales(), T0)
    segunda = combinar_predicciones(primera, pd.DataFrame([_fila(4, tipo="backtest", real="baja")]), _reales(), T1)
    assert sorted(segunda["semana"]) == [martes(3), martes(4)]


def test_no_mezcla_combustibles():
    nuevas = pd.DataFrame([_fila(5, "super"), _fila(5, "diesel", prediccion="baja")])
    out = combinar_predicciones(None, nuevas, _reales((4, "diesel", "baja")), T0)
    assert len(out) == 2 and out["direccion_real"].isna().all()
