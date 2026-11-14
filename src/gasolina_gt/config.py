"""Configuración desde .env y variables de entorno (con prioridad para el proceso)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_file() -> dict[str, str]:
    path = PROJECT_ROOT / ".env"
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load_config() -> dict[str, Any]:
    file_values = _env_file()

    def env(key: str, default: str = "") -> str:
        return os.environ.get(key, file_values.get(key, default))

    source = env("DATA_SOURCE", "local").lower()
    if source not in {"local", "databricks"}:
        raise ValueError("DATA_SOURCE debe ser 'local' o 'databricks'.")
    return {
        "source": {
            "mode": source,
            "bronze_input": env("BRONZE_INPUT_URI"),
            "bronze_output": env("BRONZE_OUTPUT_URI"),
            "silver_output": env("SILVER_OUTPUT_URI"),
            "gold_output": env("GOLD_OUTPUT_URI"),
            "catalog": env("DATABRICKS_CATALOG"),
        },
        "paths": {
            "datos_raw": env("LOCAL_DATA_DIR", str(PROJECT_ROOT / "datos")),
            "bronze": env("LOCAL_BRONZE_DIR", "datos_procesados/bronze"),
            "silver": env("LOCAL_SILVER_DIR", "datos_procesados/silver"),
            "gold": env("LOCAL_GOLD_DIR", "datos_procesados/gold"),
            "augmented": "datos_procesados/augmented",
            "models": env("LOCAL_MODELS_DIR", "models"),
            "reports": env("LOCAL_REPORTS_DIR", "reports"),
        },
        "extraccion": {
            "orden_combustibles": ["diesel", "regular", "super", "vpower"],
            "rango_precio_valido_gtq": [10.0, 80.0],
            "confianza_minima": 0.55,
        },
        "negocio": {"combustible_principal": "regular", "horizontes_semanas": [1, 2, 4]},
        "modelado": {
            "test_size_semanas": 6, "semilla": 42, "umbral_tendencia_gtq": 0.15,
            "hiperparametros_xgboost": {
                "n_estimators": [100, 200, 300, 400], "max_depth": [2, 3, 4, 5],
                "learning_rate": [0.02, 0.05, 0.1, 0.2],
                "subsample": [0.7, 0.85, 1.0], "colsample_bytree": [0.7, 0.85, 1.0],
                "reg_lambda": [0.5, 1.0, 2.0],
            },
            "n_iter_busqueda": 25, "cv_splits": 3,
        },
        "evaluacion": {"umbral_mae_gtq": 1.0, "umbral_f1_tendencia": 0.55},
        "recomendacion": {"margen_decision_gtq": 0.10, "horas_pico_ahorro": [6, 7, 8, 17, 18, 19]},
        "scraping": {
            "urls": {
                "gasolina": "https://es.globalpetrolprices.com/Guatemala/gasoline_prices/",
                "diesel": "https://es.globalpetrolprices.com/Guatemala/diesel_prices/",
            },
            "timeout_segundos": 15,
            "fixture_offline": "tests/fixtures/precio_referencia_offline.json",
        },
        "augmentation": {
            "imagenes_por_original": 6, "rotacion_max_grados": 4,
            "brillo_rango": [0.75, 1.25], "contraste_rango": [0.8, 1.2],
            "ruido_gaussiano_sigma": 4, "perspectiva_jitter_px": 6,
        },
    }


def resolve_path(relative: str) -> Path:
    path = Path(relative).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path
