"""Clasificador de la dirección semanal con validación temporal y línea base."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from .features import COLUMNAS_FEATURES, COLUMNAS_NUMERICAS
from .params import GoldParams
from .weekly import SEMANA

CANDIDATOS = ("regresion_logistica", "arbol_decision")
LINEA_BASE = "linea_base"
LINEA_BASE_RESPALDO = "linea_base_respaldo"
N_PLIEGUES = 3
COLUMNAS_SALIDA = ["semana", "combustible", "prediccion", "probabilidad", "modelo", "direccion_real", "tipo"]


def ejemplos_etiquetados(features: pd.DataFrame) -> pd.DataFrame:
    return features[features["direccion_actual"].notna() & features["direccion_siguiente"].notna()].copy()


def contar_triples(features: pd.DataFrame) -> dict[str, int]:
    ej = ejemplos_etiquetados(features)
    cuentas = ej.groupby("combustible").size()
    return {c: int(cuentas.get(c, 0)) for c in sorted(features["combustible"].unique())}


def dividir_temporal(ejemplos: pd.DataFrame, semanas_test: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    semanas = np.sort(ejemplos["semana"].unique())
    if len(semanas) == 0:
        return ejemplos.copy(), ejemplos.copy()
    inicio_test = semanas[-semanas_test] if len(semanas) >= semanas_test else semanas[0]
    return ejemplos[ejemplos["semana"] < inicio_test].copy(), ejemplos[ejemplos["semana"] >= inicio_test].copy()


def pliegues_temporales(train: pd.DataFrame, n_pliegues: int = N_PLIEGUES) -> list[tuple[pd.Index, pd.Index]]:
    semanas = np.sort(train["semana"].unique())
    if len(semanas) < n_pliegues + 1:
        return []
    bloques = np.array_split(semanas, n_pliegues + 1)
    pliegues = []
    for i in range(n_pliegues):
        entrena = train[train["semana"].isin(np.concatenate(bloques[: i + 1]))]
        valida = train[train["semana"].isin(bloques[i + 1])]
        if entrena["direccion_siguiente"].nunique() >= 2 and len(valida):
            pliegues.append((entrena.index, valida.index))
    return pliegues


def metricas_clasificacion(y_real, y_pred) -> dict[str, float]:
    return {"accuracy": float(accuracy_score(y_real, y_pred)),
            "f1_macro": float(f1_score(y_real, y_pred, average="macro", zero_division=0))}


def supera_linea_base(modelo: dict, base: dict) -> bool:
    """El modelo se usa solo si mejora el F1 macro de la línea base y no empeora su accuracy."""
    return bool(modelo["f1_macro"] > base["f1_macro"] and modelo["accuracy"] >= base["accuracy"])


def _crear(nombre: str, semilla: int) -> Pipeline:
    numericas = Pipeline([("imputar", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
                          ("escalar", StandardScaler())])
    prep = ColumnTransformer([("num", numericas, COLUMNAS_NUMERICAS),
                              ("combustible", OneHotEncoder(handle_unknown="ignore"), ["combustible"])])
    if nombre == "regresion_logistica":
        clf = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=semilla)
    elif nombre == "arbol_decision":
        clf = DecisionTreeClassifier(max_depth=3, min_samples_leaf=3, class_weight="balanced", random_state=semilla)
    else:
        raise ValueError(nombre)
    return Pipeline([("prep", prep), ("clf", clf)])


def _hiperparametros(nombre: str, semilla: int) -> dict:
    if nombre == "regresion_logistica":
        return {"C": 1.0, "max_iter": 1000, "class_weight": "balanced", "semilla": semilla}
    return {"max_depth": 3, "min_samples_leaf": 3, "class_weight": "balanced", "semilla": semilla}


def _predecir(modelo: Pipeline, filas: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    X = filas[COLUMNAS_FEATURES]
    proba = modelo.predict_proba(X)
    return modelo.classes_[proba.argmax(axis=1)], proba.max(axis=1)


def _salida(filas: pd.DataFrame, prediccion, probabilidad, modelo, tipo: str, con_real: bool) -> pd.DataFrame:
    salida = pd.DataFrame({
        "semana": (filas["semana"] + SEMANA).to_numpy(),
        "combustible": filas["combustible"].to_numpy(),
        "prediccion": list(prediccion),
        "probabilidad": np.asarray(probabilidad, dtype=float),
        "modelo": modelo,
        "direccion_real": list(filas["direccion_siguiente"]) if con_real else [None] * len(filas),
        "tipo": tipo,
    })
    return salida[COLUMNAS_SALIDA].reset_index(drop=True)


def _linea_base(filas: pd.DataFrame, tipo: str, con_real: bool) -> pd.DataFrame:
    filas = filas[filas["direccion_actual"].notna()]
    return _salida(filas, filas["direccion_actual"], np.full(len(filas), np.nan), LINEA_BASE, tipo, con_real)


@dataclass
class ResultadoModelo:
    modelo_elegido: str
    usa_linea_base: bool
    modo_pocos_datos: bool
    motivo: str
    metricas_modelo: Optional[dict]
    metricas_linea_base: Optional[dict]
    candidato: Optional[str]
    validado_en_train: bool
    cv_f1: dict
    n_ejemplos: int
    n_train: int
    n_test: int
    semana_train: tuple
    semana_test: tuple
    backtest: pd.DataFrame
    pronostico: pd.DataFrame
    candidato_test: Optional[pd.DataFrame] = None
    modelo_ajustado: Optional[Pipeline] = None
    hiperparametros: dict = field(default_factory=dict)


def _rango(df: pd.DataFrame) -> tuple:
    return (df["semana"].min(), df["semana"].max()) if len(df) else (pd.NaT, pd.NaT)


def _ajustar(nombre: str, datos: pd.DataFrame, semilla: int) -> Pipeline:
    modelo = _crear(nombre, semilla)
    modelo.fit(datos[COLUMNAS_FEATURES], datos["direccion_siguiente"])
    return modelo


def _elegir_candidato(train: pd.DataFrame, semilla: int) -> tuple[str, bool, dict]:
    pliegues = pliegues_temporales(train)
    if not pliegues:
        return CANDIDATOS[0], False, {}
    puntajes = {}
    for nombre in CANDIDATOS:
        f1s = []
        for idx_train, idx_val in pliegues:
            modelo = _ajustar(nombre, train.loc[idx_train], semilla)
            prediccion, _ = _predecir(modelo, train.loc[idx_val])
            f1s.append(metricas_clasificacion(train.loc[idx_val, "direccion_siguiente"], prediccion)["f1_macro"])
        puntajes[nombre] = float(np.mean(f1s))
    elegido = max(CANDIDATOS, key=lambda n: (puntajes[n], -CANDIDATOS.index(n)))  # empate: logística
    return elegido, True, puntajes


def _ultimas_semanas(features: pd.DataFrame) -> pd.DataFrame:
    return features.loc[features.groupby("combustible")["semana"].idxmax()].sort_values("combustible")


def _pronostico_modelo(features: pd.DataFrame, modelo: Pipeline, nombre: str) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame(columns=COLUMNAS_SALIDA)
    ultimas = _ultimas_semanas(features)
    prediccion, probabilidad = _predecir(modelo, ultimas)
    return _salida(ultimas, prediccion, probabilidad, nombre, "pronostico", con_real=False)


def _pronostico_base(features: pd.DataFrame) -> pd.DataFrame:
    """Una fila por combustible; sin dirección actual usa la última conocida o se_mantiene (respaldo)."""
    if features.empty:
        return pd.DataFrame(columns=COLUMNAS_SALIDA)
    ultimas = _ultimas_semanas(features)
    prediccion, modelos = [], []
    for _, fila in ultimas.iterrows():
        if pd.notna(fila["direccion_actual"]):
            prediccion.append(fila["direccion_actual"])
            modelos.append(LINEA_BASE)
            continue
        conocidas = features.loc[(features["combustible"] == fila["combustible"])
                                 & features["direccion_actual"].notna()].sort_values("semana")["direccion_actual"]
        prediccion.append(conocidas.iloc[-1] if len(conocidas) else "se_mantiene")
        modelos.append(LINEA_BASE_RESPALDO)
    return _salida(ultimas, prediccion, np.full(len(ultimas), np.nan), modelos, "pronostico", con_real=False)


def entrenar_y_evaluar(features: pd.DataFrame, params: GoldParams) -> ResultadoModelo:
    ej = ejemplos_etiquetados(features)
    train, test = dividir_temporal(ej, params.semanas_test)

    razones = []
    if len(ej) < params.min_ejemplos:
        razones.append(f"{len(ej)} ejemplos etiquetados (mínimo {params.min_ejemplos})")
    if len(train) < params.min_train:
        razones.append(f"{len(train)} ejemplos de entrenamiento (mínimo {params.min_train})")
    if train["direccion_siguiente"].nunique() < 2:
        razones.append("el entrenamiento no tiene al menos 2 clases")
    if test.empty:
        razones.append("no hay semanas de prueba")

    if razones:
        base = (metricas_clasificacion(ej["direccion_siguiente"], ej["direccion_actual"]) if len(ej) else None)
        return ResultadoModelo(
            modelo_elegido=LINEA_BASE, usa_linea_base=True, modo_pocos_datos=True,
            motivo="Modo pocos datos: " + "; ".join(razones) + ". Se predice con la línea base, sin entrenar.",
            metricas_modelo=None, metricas_linea_base=base, candidato=None, validado_en_train=False, cv_f1={},
            n_ejemplos=len(ej), n_train=0, n_test=len(ej), semana_train=(pd.NaT, pd.NaT), semana_test=_rango(ej),
            backtest=_linea_base(ej, "backtest", con_real=True), pronostico=_pronostico_base(features),
        )

    candidato, validado, cv_f1 = _elegir_candidato(train, params.semilla)
    ajustado_train = _ajustar(candidato, train, params.semilla)
    prediccion, probabilidad = _predecir(ajustado_train, test)
    candidato_test = _salida(test, prediccion, probabilidad, candidato, "backtest", con_real=True)
    m_modelo = metricas_clasificacion(test["direccion_siguiente"], prediccion)
    m_base = metricas_clasificacion(test["direccion_siguiente"], test["direccion_actual"])
    usa_modelo = supera_linea_base(m_modelo, m_base)

    resumen = (f"{candidato}: F1 macro {m_modelo['f1_macro']:.2f} y accuracy {m_modelo['accuracy']:.2f}; "
               f"línea base: F1 macro {m_base['f1_macro']:.2f} y accuracy {m_base['accuracy']:.2f}")
    if usa_modelo:
        motivo = f"El modelo supera a la línea base en las semanas de prueba ({resumen})."
        final = _ajustar(candidato, ej, params.semilla)
        backtest, pronostico = candidato_test, _pronostico_modelo(features, final, candidato)
    else:
        motivo = f"El modelo no supera a la línea base, se usa la línea base ({resumen})."
        final = None
        backtest, pronostico = _linea_base(test, "backtest", con_real=True), _pronostico_base(features)
    if not validado:
        motivo += (" Limitación: no hubo semanas suficientes para validar dentro de train, "
                   "se usó regresión logística por defecto.")

    return ResultadoModelo(
        modelo_elegido=LINEA_BASE if not usa_modelo else candidato, usa_linea_base=not usa_modelo,
        modo_pocos_datos=False, motivo=motivo, metricas_modelo=m_modelo, metricas_linea_base=m_base,
        candidato=candidato, validado_en_train=validado, cv_f1=cv_f1, n_ejemplos=len(ej), n_train=len(train),
        n_test=len(test), semana_train=_rango(train), semana_test=_rango(test), backtest=backtest,
        pronostico=pronostico, candidato_test=candidato_test, modelo_ajustado=final,
        hiperparametros=_hiperparametros(candidato, params.semilla),
    )
