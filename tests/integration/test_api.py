from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from api.app import main
from api.app.gold_store import GoldUnavailable, table_uri

client = TestClient(main.app)


def _gold_rows(table: str, columns: list[str]) -> list[dict]:
    prices = [
        {"semana": date(2026, 11, 3), "combustible": "super", "precio_promedio": 35.0,
         "precio_minimo": 34.0, "precio_maximo": 36.0, "n_lecturas": 2,
         "diferencia_q": None, "diferencia_pct": None, "direccion": None},
        {"semana": date(2026, 11, 10), "combustible": "super", "precio_promedio": 34.5,
         "precio_minimo": 34.0, "precio_maximo": 35.0, "n_lecturas": 3,
         "diferencia_q": -0.5, "diferencia_pct": -1.43, "direccion": "baja"},
        {"semana": date(2026, 11, 3), "combustible": "diesel", "precio_promedio": 30.0,
         "precio_minimo": 29.0, "precio_maximo": 31.0, "n_lecturas": 2,
         "diferencia_q": 0.2, "diferencia_pct": 0.67, "direccion": "sube"},
    ]
    predictions = [
        {"semana": date(2026, 11, 10), "combustible": "super", "tipo": "backtest",
         "prediccion": "baja", "probabilidad": 0.7, "modelo": "arbol_decision",
         "_generado_en": datetime(2026, 11, 10, tzinfo=timezone.utc)},
        {"semana": date(2026, 11, 17), "combustible": "super", "tipo": "pronostico",
         "prediccion": "baja", "probabilidad": None, "modelo": "linea_base",
         "_generado_en": datetime(2026, 11, 17, tzinfo=timezone.utc)},
    ]
    metrics = [{"_generado_en": datetime(2026, 11, 17, tzinfo=timezone.utc),
                "run_id_mlflow": "run-1", "modelo_elegido": "linea_base", "modo_pocos_datos": True,
                "accuracy_modelo": None, "accuracy_linea_base": 0.6}]
    rows = {"precio_semanal": prices, "variacion_semanal": prices,
            "predicciones": predictions, "metricas_modelo": metrics}[table]
    return [{key: row.get(key) for key in columns} for row in rows]


def test_endpoints_serve_gold_and_keep_nulls(monkeypatch) -> None:
    monkeypatch.setattr(main, "check_gold", lambda: None)
    monkeypatch.setattr(main, "read_gold", _gold_rows)

    assert client.get("/health").json() == {"status": "ok"}
    current = client.get("/precios/actual")
    assert current.status_code == 200
    assert [(r["combustible"], r["semana"]) for r in current.json()] == [
        ("diesel", "2026-11-03"), ("super", "2026-11-10")]

    history = client.get("/precios?combustible=super&desde=2026-11-03&hasta=2026-11-10&limit=1&offset=1")
    assert history.status_code == 200
    assert history.json()[0]["semana"] == "2026-11-03"
    assert history.json()[0]["direccion"] is None

    prediction = client.get("/prediccion?combustible=super")
    assert prediction.status_code == 200
    assert prediction.json() == {"semana": "2026-11-17", "combustible": "super",
                                 "prediccion": "baja", "probabilidad": None, "modelo": "linea_base"}

    model = client.get("/modelo/metricas")
    assert model.status_code == 200
    assert model.json()["run_id_mlflow"] == "run-1"
    assert model.json()["accuracy_modelo"] is None


def test_validation_and_missing_prediction(monkeypatch) -> None:
    monkeypatch.setattr(main, "read_gold", _gold_rows)
    assert client.get("/precios?combustible=otro").status_code == 422
    assert client.get("/precios?desde=2026-11-10&hasta=2026-11-03").status_code == 422
    assert client.get("/precios?limit=501").status_code == 422
    assert client.get("/prediccion?combustible=diesel").status_code == 404


def test_s3_failure_is_not_exposed_to_public(monkeypatch) -> None:
    def failed(*_args):
        raise GoldUnavailable("s3://private-bucket/secret")

    monkeypatch.setattr(main, "check_gold", failed)
    monkeypatch.setattr(main, "read_gold", failed)
    for url in ("/health", "/precios/actual", "/modelo/metricas"):
        response = client.get(url)
        assert response.status_code == 503
        assert "private-bucket" not in response.text


def test_gold_uri_is_scoped_to_team(monkeypatch) -> None:
    monkeypatch.setenv("GOLD_OUTPUT_URI", "s3://bucket-oro/")
    assert table_uri("predicciones") == "s3://bucket-oro/equipo7/predicciones"
    monkeypatch.setenv("GOLD_OUTPUT_URI", "s3://bucket-oro/equipo7/")
    assert table_uri("predicciones") == "s3://bucket-oro/equipo7/predicciones"
