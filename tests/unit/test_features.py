from __future__ import annotations

import pandas as pd

from gasolina_gt.data.features import FEATURES_MODELO, construir_features


def test_features_usa_solo_historia_y_crea_objetivos() -> None:
    serie = pd.DataFrame(
        {
            "fecha": pd.date_range("2026-01-04", periods=10, freq="7D"),
            "tipo_combustible": "regular",
            "precio_gtq_por_galon": range(30, 40),
            "fuente": "real",
        }
    )
    cfg = {"negocio": {"horizontes_semanas": [1, 2, 4]}, "modelado": {"umbral_tendencia_gtq": 0.15}}
    resultado = construir_features(serie, cfg)
    assert set(FEATURES_MODELO).issubset(resultado.columns)
    assert resultado.loc[4, "lag_1"] == 33
    assert resultado.loc[0, "objetivo_precio_h1"] == 31
    assert pd.isna(resultado.loc[len(resultado) - 1, "objetivo_precio_h1"])
