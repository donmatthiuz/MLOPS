from __future__ import annotations

import pandas as pd

from gasolina_gt.data.features import construir_features
from gasolina_gt.evaluation import evaluar_artefacto
from gasolina_gt.modeling.training import entrenar_modelo


def test_entrenamiento_temporal_y_evaluacion(tmp_path) -> None:
    fechas = pd.date_range("2025-01-05", periods=44, freq="7D")
    serie = pd.DataFrame(
        {
            "fecha": fechas, "tipo_combustible": "regular",
            "precio_gtq_por_galon": [30 + i * 0.08 for i in range(len(fechas))], "fuente": "real",
        }
    )
    cfg = {
        "negocio": {"horizontes_semanas": [1]},
        "modelado": {
            "test_size_semanas": 6, "semilla": 7, "cv_splits": 2, "n_iter_busqueda": 1,
            "umbral_tendencia_gtq": 0.15,
            "hiperparametros_xgboost": {"n_estimators": [10], "max_depth": [2], "learning_rate": [0.1], "subsample": [1.0], "colsample_bytree": [1.0], "reg_lambda": [1.0]},
        },
        "paths": {"models": str(tmp_path / "models")},
        "evaluacion": {"umbral_mae_gtq": 1.0, "umbral_f1_tendencia": 0.55},
    }
    gold = construir_features(serie, cfg)
    artefacto, meta = entrenar_modelo(gold, 1, "regular", cfg)
    evaluacion = evaluar_artefacto(artefacto, cfg)
    assert meta.filas_test == 6
    assert (tmp_path / "models" / "xgboost_regular_h1.joblib").exists()
    assert evaluacion.mae_modelo >= 0
