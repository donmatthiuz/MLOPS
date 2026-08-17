from __future__ import annotations

from fastapi.testclient import TestClient

from gasolina_gt.serving.api import app


def test_health_endpoint() -> None:
    respuesta = TestClient(app).get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}
