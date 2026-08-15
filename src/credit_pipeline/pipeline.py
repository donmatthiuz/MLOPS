import numpy as np
from sklearn import set_config
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .transformers import FeatureExtractor, RowFilter

set_config(display="diagram")

COLUMNS_TO_DROP = ["Sl_No", "Customer Key"]


def build_cleaning_pipeline() -> Pipeline:
    """Colocamos aqui la extraccion de columnas y el filtrado de filas.
    Se corre sobre el dataframe crudo (con el target incluido) y antes del
    split, porque filtra filas y eso desalinearia X/y si fuera parte del
    pipeline de modelado."""
    return Pipeline(steps=[
        ("extraccion", FeatureExtractor(columns_to_drop=COLUMNS_TO_DROP)),
        ("filtrado", RowFilter(max_null_ratio=0.5, numeric_bounds={})),
    ])


def build_preprocessor() -> ColumnTransformer:
    numeric_pipeline = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    categorical_pipeline = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])

    return ColumnTransformer(transformers=[
        ("num", numeric_pipeline, make_column_selector(dtype_include=np.number)),
        ("cat", categorical_pipeline, make_column_selector(dtype_include=object)),
    ])


def build_model_pipeline() -> Pipeline:
    """Usamos este pipeline (preprocesamiento + modelo) para la calibracion
    de hiperparametros con GridSearchCV, ya sobre datos limpios."""
    return Pipeline(steps=[
        ("preprocesamiento", build_preprocessor()),
        ("modelo", RandomForestRegressor(random_state=42)),
    ])


def build_full_pipeline() -> Pipeline:
    """Pipeline completo solo para fines de diagrama/documentacion."""
    return Pipeline(steps=[
        ("extraccion", FeatureExtractor(columns_to_drop=COLUMNS_TO_DROP)),
        ("filtrado", RowFilter(max_null_ratio=0.5, numeric_bounds={})),
        ("preprocesamiento", build_preprocessor()),
        ("modelo", RandomForestRegressor(random_state=42)),
    ])


PARAM_GRID = {
    "modelo__n_estimators": [100, 200],
    "modelo__max_depth": [None, 5, 10],
    "preprocesamiento__num__imputer__strategy": ["median", "mean"],
}


def build_search(pipeline: Pipeline = None, param_grid: dict = None, cv: int = 5) -> GridSearchCV:
    """Usamos GridSearchCV sobre el pipeline para calibrar hiperparametros
    del modelo y de las etapas de preprocesamiento (los steps se referencian
    con la notacion step__parametro que expone Pipeline.get_params())."""
    pipeline = pipeline or build_model_pipeline()
    param_grid = param_grid or PARAM_GRID
    return GridSearchCV(
        estimator=pipeline,
        param_grid=param_grid,
        cv=cv,
        scoring="r2",
        n_jobs=-1,
    )
