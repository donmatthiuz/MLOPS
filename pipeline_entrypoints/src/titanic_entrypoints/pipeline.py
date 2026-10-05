from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RANDOM_STATE = 42
TITANIC_URL = "https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv"
TARGET_COLUMN = "Survived"
MODEL_PATH = Path("models") / "titanic_survival_pipeline.joblib"

DROP_COLUMNS = ["PassengerId", "Name", "Ticket", "Cabin"]
NUMERIC_FEATURES = ["Age", "SibSp", "Parch", "Fare"]
CATEGORICAL_FEATURES = ["Pclass", "Sex", "Embarked"]


def load_data(source: str = TITANIC_URL) -> pd.DataFrame:
    """Carga el dataset Titanic desde una URL o ruta local."""
    return pd.read_csv(source)


def split_features_target(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Separa variables predictoras y objetivo con la misma lógica del notebook."""
    data_filtered = data.drop(columns=DROP_COLUMNS)
    X = data_filtered.drop(columns=[TARGET_COLUMN])
    y = data_filtered[TARGET_COLUMN]
    return X, y


def build_preprocessor() -> ColumnTransformer:
    """Construye el preprocesador de variables numéricas y categóricas."""
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    try:
        one_hot_encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        one_hot_encoder = OneHotEncoder(handle_unknown="ignore", sparse=False)

    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", one_hot_encoder),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, NUMERIC_FEATURES),
            ("cat", categorical_transformer, CATEGORICAL_FEATURES),
        ]
    )


def build_pipeline(random_state: int = RANDOM_STATE) -> Pipeline:
    """Crea el pipeline completo de scikit-learn."""
    return Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            ("classifier", LogisticRegression(max_iter=1_000, random_state=random_state)),
        ]
    )


def train_pipeline(
    source: str = TITANIC_URL,
    model_path: str | Path = MODEL_PATH,
    test_size: float = 0.20,
    random_state: int = RANDOM_STATE,
) -> dict[str, Any]:
    """Entrena, evalúa y guarda el pipeline."""
    data = load_data(source)
    X, y = split_features_target(data)
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    model = build_pipeline(random_state=random_state)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)

    return {
        "model_path": str(model_path),
        "accuracy": accuracy_score(y_test, y_pred),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "classification_report": classification_report(
            y_test,
            y_pred,
            target_names=["No sobrevivio", "Sobrevivio"],
            output_dict=True,
        ),
    }


def predict_survival(
    input_csv: str | Path,
    model_path: str | Path = MODEL_PATH,
    output_csv: str | Path | None = None,
) -> pd.DataFrame:
    """Carga un pipeline entrenado y genera predicciones sobre datos crudos."""
    model = joblib.load(model_path)
    data = pd.read_csv(input_csv)
    predictions = model.predict(data)
    probabilities = model.predict_proba(data)[:, 1]

    result = data.copy()
    result["prediccion_survive"] = predictions
    result["probabilidad_survive"] = probabilities.round(3)

    if output_csv is not None:
        output_csv = Path(output_csv)
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_csv, index=False)

    return result
