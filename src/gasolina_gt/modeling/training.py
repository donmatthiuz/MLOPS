"""Entrenamiento temporal de modelos de precios.

Cada horizonte se entrena y evalúa por separado.  La división nunca mezcla
fechas futuras en entrenamiento: las últimas ``test_size_semanas`` observaciones
se reservan como test y la búsqueda de hiperparámetros usa ``TimeSeriesSplit``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from xgboost import XGBRegressor

from ..config import load_config, resolve_path
from ..data.features import FEATURES_MODELO


@dataclass
class ResultadoEntrenamiento:
    combustible: str
    horizonte: int
    filas_entrenamiento: int
    filas_test: int
    ruta_modelo: str
    mejores_parametros: dict[str, Any]


def _datos_para_horizonte(gold: pd.DataFrame, combustible: str, horizonte: int) -> pd.DataFrame:
    objetivo = f"objetivo_precio_h{horizonte}"
    requeridas = ["fecha", "precio_gtq_por_galon", objetivo, *FEATURES_MODELO]
    faltantes = set(requeridas) - set(gold.columns)
    if faltantes:
        raise ValueError(f"Dataset Gold no tiene columnas requeridas: {sorted(faltantes)}")
    datos = gold[gold["tipo_combustible"] == combustible].copy()
    datos = datos.dropna(subset=[objetivo, *FEATURES_MODELO]).sort_values("fecha").reset_index(drop=True)
    if len(datos) < 12:
        raise ValueError("No hay suficientes filas completas para entrenar (mínimo 12).")
    return datos


def entrenar_modelo(
    gold: pd.DataFrame,
    horizonte: int,
    combustible: str | None = None,
    config: dict | None = None,
) -> tuple[dict[str, Any], ResultadoEntrenamiento]:
    """Entrena XGBoost y devuelve el artefacto junto con sus metadatos."""
    cfg = config or load_config()
    combustible = combustible or cfg["negocio"]["combustible_principal"]
    datos = _datos_para_horizonte(gold, combustible, horizonte)
    n_test = int(cfg["modelado"]["test_size_semanas"])
    if len(datos) <= n_test + 6:
        raise ValueError("No hay historia suficiente después de reservar el test temporal.")

    train, test = datos.iloc[:-n_test], datos.iloc[-n_test:]
    x_train, y_train = train[FEATURES_MODELO], train[f"objetivo_precio_h{horizonte}"]
    params = cfg["modelado"]["hiperparametros_xgboost"]
    # Reduce los folds cuando se usa una serie corta, preservando siempre orden temporal.
    n_splits = min(int(cfg["modelado"]["cv_splits"]), max(2, len(train) // 8))
    modelo = XGBRegressor(
        objective="reg:absoluteerror",
        random_state=int(cfg["modelado"]["semilla"]),
        n_jobs=1,
    )
    busqueda = RandomizedSearchCV(
        modelo,
        param_distributions=params,
        n_iter=min(int(cfg["modelado"]["n_iter_busqueda"]), 25),
        scoring="neg_mean_absolute_error",
        cv=TimeSeriesSplit(n_splits=n_splits),
        random_state=int(cfg["modelado"]["semilla"]),
        n_jobs=1,
        refit=True,
    )
    busqueda.fit(x_train, y_train)
    artefacto = {
        "modelo": busqueda.best_estimator_,
        "features": FEATURES_MODELO,
        "combustible": combustible,
        "horizonte": horizonte,
        "fecha_entrenamiento_final": str(train["fecha"].max()),
        "test": test,
        "mejores_parametros": busqueda.best_params_,
    }
    models_dir = resolve_path(cfg["paths"]["models"])
    models_dir.mkdir(parents=True, exist_ok=True)
    ruta = models_dir / f"xgboost_{combustible}_h{horizonte}.joblib"
    joblib.dump(artefacto, ruta)
    resultado = ResultadoEntrenamiento(
        combustible=combustible,
        horizonte=horizonte,
        filas_entrenamiento=len(train),
        filas_test=len(test),
        ruta_modelo=str(ruta),
        mejores_parametros=busqueda.best_params_,
    )
    return artefacto, resultado


def cargar_modelo(combustible: str, horizonte: int, config: dict | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    ruta = resolve_path(cfg["paths"]["models"]) / f"xgboost_{combustible}_h{horizonte}.joblib"
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el modelo {ruta}. Ejecute primero `gasolina-gt train`.")
    return joblib.load(ruta)


def entrenar_todos_los_horizontes(
    gold: pd.DataFrame, combustible: str | None = None, config: dict | None = None
) -> list[tuple[dict[str, Any], ResultadoEntrenamiento]]:
    cfg = config or load_config()
    return [entrenar_modelo(gold, h, combustible, cfg) for h in cfg["negocio"]["horizontes_semanas"]]
