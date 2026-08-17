from __future__ import annotations

import pandas as pd

from gasolina_gt.data.features import FEATURES_MODELO
from gasolina_gt.serving.recommendation import recomendar_recarga


class _ModeloAlcista:
    def predict(self, x: pd.DataFrame) -> list[float]:
        return [35.50]


def test_recomienda_recargar_si_pronostica_alza(monkeypatch) -> None:
    import gasolina_gt.serving.recommendation as modulo

    monkeypatch.setattr(modulo, "cargar_modelo", lambda *a, **k: {"modelo": _ModeloAlcista(), "features": FEATURES_MODELO})
    fila = {"fecha": "2026-08-16", "tipo_combustible": "regular", "precio_gtq_por_galon": 35.0, "fuente": "real"}
    fila.update({feature: 1.0 for feature in FEATURES_MODELO})
    resultado = recomendar_recarga(pd.DataFrame([fila]), hora=18)
    assert resultado.recargar_ahora is True
    assert resultado.tendencia == "alza"
    assert "Hora pico" in resultado.contexto_hora
