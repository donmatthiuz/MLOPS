"""Esquemas de las tablas Oro y conversión de pandas a registros de Spark."""
from __future__ import annotations

import math

import pandas as pd

ESQUEMAS: dict[str, list[tuple[str, str]]] = {
    "precio_semanal": [
        ("semana", "DATE"), ("combustible", "STRING"), ("precio_promedio", "DOUBLE"), ("precio_minimo", "DOUBLE"),
        ("precio_maximo", "DOUBLE"), ("n_lecturas", "INT"), ("_generado_en", "TIMESTAMP"),
    ],
    "variacion_semanal": [
        ("semana", "DATE"), ("combustible", "STRING"), ("precio_promedio", "DOUBLE"), ("precio_minimo", "DOUBLE"),
        ("precio_maximo", "DOUBLE"), ("n_lecturas", "INT"), ("precio_anterior", "DOUBLE"),
        ("diferencia_q", "DOUBLE"), ("diferencia_pct", "DOUBLE"), ("direccion", "STRING"),
        ("semana_anterior_disponible", "BOOLEAN"), ("umbral_q", "DOUBLE"), ("_generado_en", "TIMESTAMP"),
    ],
    "features_modelo": [
        ("semana", "DATE"), ("combustible", "STRING"), ("precio_promedio", "DOUBLE"),
        ("variacion_lag_1", "DOUBLE"), ("variacion_lag_2", "DOUBLE"), ("variacion_lag_3", "DOUBLE"),
        ("variacion_lag_4", "DOUBLE"), ("promedio_movil_4", "DOUBLE"), ("dif_super_diesel", "DOUBLE"),
        ("wti_semanal", "DOUBLE"), ("wti_variacion", "DOUBLE"), ("direccion_actual", "STRING"),
        ("direccion_siguiente", "STRING"), ("_generado_en", "TIMESTAMP"),
    ],
    "predicciones": [
        ("semana", "DATE"), ("combustible", "STRING"), ("tipo", "STRING"), ("prediccion", "STRING"),
        ("probabilidad", "DOUBLE"), ("modelo", "STRING"), ("direccion_real", "STRING"),
        ("_generado_en", "TIMESTAMP"),
    ],
    "metricas_modelo": [
        ("run_id_mlflow", "STRING"), ("modelo_elegido", "STRING"), ("usa_linea_base", "BOOLEAN"),
        ("modo_pocos_datos", "BOOLEAN"), ("motivo", "STRING"), ("candidato", "STRING"),
        ("validado_en_train", "BOOLEAN"), ("cv_f1_regresion_logistica", "DOUBLE"), ("cv_f1_arbol_decision", "DOUBLE"),
        ("n_ejemplos", "INT"), ("n_train", "INT"), ("n_test", "INT"),
        ("semana_train_inicio", "DATE"), ("semana_train_fin", "DATE"),
        ("semana_test_inicio", "DATE"), ("semana_test_fin", "DATE"),
        ("accuracy_modelo", "DOUBLE"), ("f1_macro_modelo", "DOUBLE"),
        ("accuracy_linea_base", "DOUBLE"), ("f1_macro_linea_base", "DOUBLE"),
        ("umbral_q", "DOUBLE"), ("semanas_test", "INT"), ("usa_wti", "BOOLEAN"), ("_generado_en", "TIMESTAMP"),
    ],
    "metricas_combustible": [
        ("criterio", "STRING"), ("combustible", "STRING"), ("modelo", "STRING"), ("n_test", "INT"),
        ("accuracy", "DOUBLE"), ("f1_macro", "DOUBLE"),
        ("semana_inicio", "DATE"), ("semana_fin", "DATE"), ("_generado_en", "TIMESTAMP"),
    ],
}


def columnas(nombre: str) -> list[str]:
    return [c for c, _ in ESQUEMAS[nombre]]


def ddl(nombre: str) -> str:
    return ", ".join(f"{c} {t}" for c, t in ESQUEMAS[nombre])


def ordenar(df: pd.DataFrame, nombre: str) -> pd.DataFrame:
    return df[columnas(nombre)].reset_index(drop=True)


def _nulo(valor) -> bool:
    return valor is None or valor is pd.NaT or (isinstance(valor, float) and math.isnan(valor))


def _convertir(valor, tipo: str):
    if _nulo(valor):
        return None
    if tipo == "DATE":
        return pd.Timestamp(valor).date()
    if tipo == "TIMESTAMP":
        return pd.Timestamp(valor).to_pydatetime()
    if tipo == "INT":
        return int(valor)
    if tipo == "DOUBLE":
        return float(valor)
    if tipo == "BOOLEAN":
        return bool(valor)
    return str(valor)


def registros(df: pd.DataFrame, nombre: str) -> list[tuple]:
    """Filas para `spark.createDataFrame(filas, ddl(nombre))`: NaN → None."""
    esquema = ESQUEMAS[nombre]
    return [tuple(_convertir(fila[c], t) for c, t in esquema) for fila in df.to_dict("records")]

