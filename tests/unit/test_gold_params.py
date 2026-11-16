"""Parámetros de Oro: widgets > argumentos CLI > variables de entorno > valores por defecto."""
from __future__ import annotations

import sys
import types
from unittest.mock import Mock, patch

import pytest

from gasolina_gt.gold.params import GoldParams, resolver_parametros, widgets_databricks


def test_valores_por_defecto():
    p = resolver_parametros(widgets=None, argv=[], env={})
    assert p == GoldParams()
    assert (p.umbral_q, p.semanas_test, p.usar_wti, p.min_ejemplos, p.min_train) == (0.10, 4, True, 20, 12)
    assert p.experimento_mlflow == "/Shared/equipo7-gasolina"


def test_variables_de_entorno():
    env = {"GOLD_UMBRAL_Q": "0.2", "GOLD_SEMANAS_TEST": "3", "GOLD_MLFLOW_EXPERIMENT": "/Shared/otro",
           "GOLD_USAR_WTI": "no", "GOLD_MIN_EJEMPLOS": "30", "GOLD_MIN_TRAIN": "15"}
    p = resolver_parametros(argv=[], env=env)
    assert (p.umbral_q, p.semanas_test, p.experimento_mlflow, p.usar_wti, p.min_ejemplos, p.min_train) == \
           (0.2, 3, "/Shared/otro", False, 30, 15)


def test_argumentos_cli_ganan_a_las_variables_de_entorno():
    p = resolver_parametros(argv=["--umbral-q", "0.3", "--semanas-test", "5", "--usar-wti", "false"],
                            env={"GOLD_UMBRAL_Q": "0.2", "GOLD_USAR_WTI": "true"})
    assert (p.umbral_q, p.semanas_test, p.usar_wti) == (0.3, 5, False)


def test_widgets_ganan_a_todo_y_el_vacio_cuenta_como_no_definido():
    valores = {"umbral_q": "0.5", "semanas_test": ""}
    p = resolver_parametros(widgets=valores.get, argv=["--umbral-q", "0.3", "--semanas-test", "6"], env={})
    assert p.umbral_q == 0.5 and p.semanas_test == 6


def test_ignora_argumentos_que_no_son_de_oro():
    p = resolver_parametros(argv=["--reprocess", "--umbral-q", "0.25"], env={})
    assert p.umbral_q == 0.25


@pytest.mark.parametrize("texto, esperado", [("sí", True), ("si", True), ("true", True), ("1", True),
                                             ("no", False), ("false", False), ("0", False)])
def test_usar_wti_acepta_variantes(texto, esperado):
    assert resolver_parametros(argv=[], env={"GOLD_USAR_WTI": texto}).usar_wti is esperado


@pytest.mark.parametrize("env", [{"GOLD_UMBRAL_Q": "-1"}, {"GOLD_UMBRAL_Q": "abc"}, {"GOLD_SEMANAS_TEST": "0"},
                                 {"GOLD_USAR_WTI": "quizá"}, {"GOLD_MIN_TRAIN": "50", "GOLD_MIN_EJEMPLOS": "20"}])
def test_rechaza_valores_invalidos(env):
    with pytest.raises(ValueError):
        resolver_parametros(argv=[], env=env)


def _con_databricks_falso(valores_pasados=None):
    """pyspark/dbutils simulados. `valores_pasados` = lo que el Job pasó como parámetros (override del defecto)."""
    valores = dict(valores_pasados or {})
    widgets = types.SimpleNamespace(text=lambda nombre, defecto, *a: valores.setdefault(nombre, defecto),
                                    get=lambda nombre: valores[nombre])
    modulo = types.ModuleType("pyspark.dbutils")
    modulo.DBUtils = Mock(return_value=types.SimpleNamespace(widgets=widgets))
    sql = types.ModuleType("pyspark.sql")
    sql.SparkSession = Mock()
    modulos = {"pyspark": types.ModuleType("pyspark"), "pyspark.dbutils": modulo, "pyspark.sql": sql}
    return valores, patch.dict(sys.modules, modulos)


def test_widgets_databricks_se_definen_vacios_para_que_solo_cuente_lo_pasado():
    valores, modulos = _con_databricks_falso()
    with modulos:
        getter = widgets_databricks()
    assert set(valores) == {"umbral_q", "semanas_test", "mlflow_experiment", "usar_wti", "min_ejemplos", "min_train"}
    assert all(v == "" for v in valores.values())
    assert getter("semanas_test") == ""


def test_widgets_sin_valor_no_tapan_los_argumentos_de_una_tarea_de_script_python():
    _, modulos = _con_databricks_falso()          # en una tarea de script nadie llena los widgets
    with modulos:
        getter = widgets_databricks()
    p = resolver_parametros(widgets=getter, argv=["--umbral-q", "0.3", "--usar-wti", "no"],
                            env={"GOLD_SEMANAS_TEST": "6"})
    assert (p.umbral_q, p.usar_wti, p.semanas_test) == (0.3, False, 6)
    assert p.min_ejemplos == GoldParams().min_ejemplos   # lo no pasado sigue en su defecto


def test_parametros_de_un_job_con_tarea_de_notebook_llegan_por_los_widgets():
    _, modulos = _con_databricks_falso({"umbral_q": "0.25", "semanas_test": "3"})
    with modulos:
        getter = widgets_databricks()
    p = resolver_parametros(widgets=getter, argv=[], env={})
    assert (p.umbral_q, p.semanas_test, p.usar_wti) == (0.25, 3, True)


def test_widgets_databricks_devuelve_none_fuera_de_databricks():
    with patch.dict(sys.modules, {"pyspark": None, "pyspark.dbutils": None}):
        assert widgets_databricks() is None
