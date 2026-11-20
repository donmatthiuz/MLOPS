"""Cálculo de la capa Oro en pandas, sin Spark."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from .features import COLUMNAS_FEATURES, construir_features
from .modeling import ResultadoModelo, contar_triples, entrenar_y_evaluar
from .params import GoldParams
from .predictions import combinar_predicciones
from .schemas import ordenar
from .weekly import preferir_observados, precio_semanal, variacion_semanal, wti_semanal

Tracker = Callable[[dict, dict, object], Optional[str]]


@dataclass
class GoldResult:
    precio_semanal: pd.DataFrame
    variacion_semanal: pd.DataFrame
    features_modelo: pd.DataFrame
    predicciones: pd.DataFrame
    metricas_modelo: pd.DataFrame
    resultado: ResultadoModelo


def _metricas(r: ResultadoModelo) -> dict:
    m, b = r.metricas_modelo or {}, r.metricas_linea_base or {}
    return {"accuracy_modelo": m.get("accuracy"), "f1_macro_modelo": m.get("f1_macro"),
            "accuracy_linea_base": b.get("accuracy"), "f1_macro_linea_base": b.get("f1_macro"),
            "cv_f1_regresion_logistica": r.cv_f1.get("regresion_logistica"),
            "cv_f1_arbol_decision": r.cv_f1.get("arbol_decision"),
            "n_ejemplos": r.n_ejemplos, "n_train": r.n_train, "n_test": r.n_test}


def _parametros(params: GoldParams, r: ResultadoModelo, usa_wti: bool,
                evaluacion_observada: bool, referencias_en_datos: bool) -> dict:
    return {"umbral_q": params.umbral_q, "semanas_test": params.semanas_test, "usar_wti": usa_wti,
            "min_ejemplos": params.min_ejemplos, "min_train": params.min_train, "semilla": params.semilla,
            "features": COLUMNAS_FEATURES, "candidato": r.candidato or "ninguno",
            "modelo_elegido": r.modelo_elegido, "modo_pocos_datos": r.modo_pocos_datos,
            "origen_evaluacion": "solo_lecturas_observadas" if evaluacion_observada else "mismos_datos_entrenamiento",
            "referencias_en_datos_modelo": referencias_en_datos,
            "hiperparametros": r.hiperparametros, "motivo": r.motivo}


def compute_gold(silver: pd.DataFrame, wti_crudo: Optional[pd.DataFrame], params: GoldParams, *,
                 silver_modelo: Optional[pd.DataFrame] = None,
                 silver_evaluacion: Optional[pd.DataFrame] = None,
                 previas: Optional[pd.DataFrame] = None,
                 generado_en=None, tracker: Optional[Tracker] = None,
                 log: Callable[[str], None] = print) -> GoldResult:
    """Entrena con respaldo mensual; evalúa con silver_evaluacion si se proporciona."""
    generado_en = pd.Timestamp.now("UTC").tz_localize(None) if generado_en is None else generado_en

    semanal = precio_semanal(preferir_observados(silver))
    variacion = variacion_semanal(semanal, params.umbral_q)
    silver_modelo = silver if silver_modelo is None else silver_modelo
    referencias_en_datos = ("metodo_validacion" in silver_modelo.columns and
                            silver_modelo["metodo_validacion"].fillna("").str.startswith("referencia_").any())
    semanal_modelo = precio_semanal(preferir_observados(silver_modelo))
    variacion_modelo = variacion_semanal(semanal_modelo, params.umbral_q)
    usa_wti = bool(params.usar_wti and wti_crudo is not None and len(wti_crudo))
    wti = wti_semanal(wti_crudo) if usa_wti else None
    features = construir_features(variacion_modelo, wti)
    features_evaluacion = None
    variacion_reales = variacion_modelo
    if silver_evaluacion is not None:
        semanal_evaluacion = precio_semanal(silver_evaluacion)
        variacion_evaluacion = variacion_semanal(semanal_evaluacion, params.umbral_q)
        features_evaluacion = construir_features(variacion_evaluacion, wti)
        variacion_reales = variacion_evaluacion

    triples = contar_triples(features)
    log("Oro: ejemplos válidos (triples t-1, t, t+1) por combustible: "
        + ", ".join(f"{c}={n}" for c, n in triples.items()) + f"; total={sum(triples.values())}")
    if features_evaluacion is not None:
        observados = contar_triples(features_evaluacion)
        log("Oro: ejemplos solo observados para evaluación: "
            + ", ".join(f"{c}={n}" for c, n in observados.items())
            + f"; total={sum(observados.values())}")

    r = entrenar_y_evaluar(features, params, features_evaluacion)
    log(f"Oro: {r.motivo}")

    reales = variacion_reales.loc[variacion_reales["direccion"].notna(),
                                 ["semana", "combustible", "direccion"]]
    predicciones = combinar_predicciones(previas, pd.concat([r.backtest, r.pronostico], ignore_index=True),
                                         reales, generado_en)

    run_id = None
    if tracker is not None:
        run_id = tracker(_parametros(params, r, usa_wti, silver_evaluacion is not None,
                                    bool(referencias_en_datos)), _metricas(r),
                         None if r.usa_linea_base else r.modelo_ajustado)

    m = _metricas(r)
    fila = {
        "run_id_mlflow": run_id, "modelo_elegido": r.modelo_elegido, "usa_linea_base": r.usa_linea_base,
        "modo_pocos_datos": r.modo_pocos_datos, "motivo": r.motivo, "candidato": r.candidato,
        "validado_en_train": r.validado_en_train, **{k: m[k] for k in (
            "cv_f1_regresion_logistica", "cv_f1_arbol_decision", "n_ejemplos", "n_train", "n_test",
            "accuracy_modelo", "f1_macro_modelo", "accuracy_linea_base", "f1_macro_linea_base")},
        "semana_train_inicio": r.semana_train[0], "semana_train_fin": r.semana_train[1],
        "semana_test_inicio": r.semana_test[0], "semana_test_fin": r.semana_test[1],
        "umbral_q": params.umbral_q, "semanas_test": params.semanas_test, "usa_wti": usa_wti,
        "_generado_en": generado_en,
    }
    estampar = lambda df: df.assign(_generado_en=generado_en)  # noqa: E731
    return GoldResult(
        precio_semanal=ordenar(estampar(semanal), "precio_semanal"),
        variacion_semanal=ordenar(estampar(variacion), "variacion_semanal"),
        features_modelo=ordenar(estampar(features), "features_modelo"),
        predicciones=ordenar(predicciones, "predicciones"),
        metricas_modelo=ordenar(pd.DataFrame([fila]), "metricas_modelo"),
        resultado=r,
    )
