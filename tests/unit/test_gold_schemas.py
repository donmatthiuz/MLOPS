"""Los esquemas, los COMMENT y las tablas generadas deben describir exactamente las mismas columnas."""
from __future__ import annotations

import datetime as dt

import pandas as pd

from gasolina_gt.gold.comments import COLUMNAS, COMENTARIOS_TABLA
from gasolina_gt.gold.schemas import ESQUEMAS, columnas, ddl, registros


def test_esquemas_y_comentarios_describen_las_mismas_columnas():
    assert set(ESQUEMAS) == set(COLUMNAS) == set(COMENTARIOS_TABLA)
    for nombre in ESQUEMAS:
        assert columnas(nombre) == list(COLUMNAS[nombre]), nombre


def test_ddl_para_spark():
    assert ddl("predicciones").startswith("semana DATE, combustible STRING, tipo STRING")


def test_registros_convierten_nan_a_none_y_fechas_a_date():
    df = pd.DataFrame([{"semana": pd.Timestamp("2026-01-06"), "combustible": "super", "tipo": "pronostico",
                        "prediccion": "sube", "probabilidad": float("nan"), "modelo": "linea_base",
                        "direccion_real": None, "_generado_en": pd.Timestamp("2026-11-15 10:00")}])
    fila = registros(df, "predicciones")[0]
    assert fila == (dt.date(2026, 1, 6), "super", "pronostico", "sube", None, "linea_base", None,
                    dt.datetime(2026, 11, 15, 10, 0))


def test_registros_convierten_enteros_y_nat():
    df = pd.DataFrame([{c: None for c in columnas("metricas_modelo")}])
    df.loc[0, ["n_ejemplos", "n_train", "n_test", "semanas_test"]] = [30, 0, 30, 4]
    df.loc[0, "semana_train_inicio"] = pd.NaT
    fila = dict(zip(columnas("metricas_modelo"), registros(df, "metricas_modelo")[0]))
    assert fila["n_ejemplos"] == 30 and isinstance(fila["n_ejemplos"], int)
    assert fila["semana_train_inicio"] is None and fila["run_id_mlflow"] is None
