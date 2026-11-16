"""MLflow opcional: registra en Databricks y, si no está disponible, deja un reporte y no falla."""
from __future__ import annotations

import json
import sys
import types
from contextlib import contextmanager

import pytest

from gasolina_gt.gold.tracking import registrar_experimento

PARAMS = {"umbral_q": 0.1, "semanas_test": 4, "features": ["variacion_lag_1", "wti_semanal"], "usar_wti": True}
METRICAS = {"accuracy_modelo": 0.8, "f1_macro_modelo": 0.7, "accuracy_linea_base": 0.5, "f1_macro_linea_base": None}


class FakeMlflow(types.ModuleType):
    def __init__(self, falla_en_log=False):
        super().__init__("mlflow")
        self.llamadas, self.falla_en_log = [], falla_en_log
        self.sklearn = types.SimpleNamespace(log_model=lambda modelo, nombre, **kw: self.llamadas.append(("modelo", nombre)))

    def set_experiment(self, nombre):
        self.llamadas.append(("experimento", nombre))

    @contextmanager
    def start_run(self, run_name=None):
        self.llamadas.append(("run", run_name))
        yield types.SimpleNamespace(info=types.SimpleNamespace(run_id="run-123"))

    def log_params(self, params):
        if self.falla_en_log:
            raise RuntimeError("sin permisos en el workspace")
        self.llamadas.append(("params", params))

    def log_metrics(self, metricas):
        self.llamadas.append(("metricas", metricas))

    def set_tags(self, tags):
        self.llamadas.append(("tags", tags))


@pytest.fixture
def fake_mlflow(monkeypatch):
    modulo = FakeMlflow()
    monkeypatch.setitem(sys.modules, "mlflow", modulo)
    monkeypatch.setitem(sys.modules, "mlflow.sklearn", modulo.sklearn)
    return modulo


def test_registra_experimento_parametros_metricas_y_modelo(fake_mlflow, tmp_path):
    run_id = registrar_experimento(PARAMS, METRICAS, modelo=object(), experimento="/Shared/equipo7-gasolina",
                                   reports_dir=tmp_path, nombre_run="oro")
    assert run_id == "run-123"
    llamadas = dict((k, v) for k, v in fake_mlflow.llamadas)
    assert llamadas["experimento"] == "/Shared/equipo7-gasolina"
    assert llamadas["params"]["umbral_q"] == "0.1"
    assert llamadas["params"]["features"] == "variacion_lag_1,wti_semanal"
    assert llamadas["metricas"] == {"accuracy_modelo": 0.8, "f1_macro_modelo": 0.7, "accuracy_linea_base": 0.5}  # sin None
    assert llamadas["modelo"] == "modelo"


def test_si_gana_la_linea_base_no_hay_modelo_que_registrar(fake_mlflow, tmp_path):
    registrar_experimento(PARAMS, METRICAS, modelo=None, experimento="/Shared/x", reports_dir=tmp_path)
    assert "modelo" not in dict(fake_mlflow.llamadas)
    assert dict(fake_mlflow.llamadas)["tags"]["modelo_registrado"] == "no"


def test_sin_mlflow_no_falla_y_deja_un_reporte(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "mlflow", None)  # fuerza ImportError
    assert registrar_experimento(PARAMS, METRICAS, modelo=object(), experimento="/Shared/x", reports_dir=tmp_path) is None
    reporte = json.loads((tmp_path / "gold_experimento.json").read_text(encoding="utf-8"))
    assert reporte["parametros"]["umbral_q"] == 0.1
    assert reporte["metricas"]["accuracy_modelo"] == 0.8
    assert reporte["mlflow"] == "no disponible"


def test_si_mlflow_falla_el_pipeline_sigue(monkeypatch, tmp_path, capsys):
    modulo = FakeMlflow(falla_en_log=True)
    monkeypatch.setitem(sys.modules, "mlflow", modulo)
    monkeypatch.setitem(sys.modules, "mlflow.sklearn", modulo.sklearn)
    assert registrar_experimento(PARAMS, METRICAS, modelo=object(), experimento="/Shared/x", reports_dir=tmp_path) is None
    assert "sin permisos" in capsys.readouterr().out
    assert (tmp_path / "gold_experimento.json").is_file()


def test_si_no_se_puede_escribir_el_reporte_tampoco_falla(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "mlflow", None)
    archivo = tmp_path / "es_un_archivo"
    archivo.write_text("x")
    assert registrar_experimento(PARAMS, METRICAS, None, "/Shared/x", reports_dir=archivo / "reports") is None
