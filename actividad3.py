# %%
!pip install scikit-learn

# %% [markdown]
# ## Librerias

# %%
from sklearn.pipeline import Pipeline
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer, make_column_selector
import numpy as np




# %% [markdown]
# ## Descripción del Dataset
# 
# - Sl_No: (Según google Serial Number) Es un número de serie, sirve para indicar el número de identificiación o la posición consecutiva de un elemento
# 
# - Customer Key: Es un id  único para cada cliente
# 
# - Avg_Credit_Limit: Es el límite de crédito promedio asignado a un cliente
# 
# - Total_Credit_Cards: Es la cantidad total de tarjetas de crédito que un cliente posee
# 
# - Total_visits_online: Es la frecuencia con la que el cliente se conecta a la banca en línea
# 
# - Total_calls_made: Es la cantidad de llamadas que el cliente ha realiado al soporte del banco

# %%
file_id = '10S8JVFiLfCoRB9mb0NJG5YhITyXbH37B'

download_url = f'https://drive.google.com/uc?export=download&id={file_id}'

data = pd.read_csv(download_url)

# %%
print("\nTipos de datos:")
print(data.dtypes)

# %%
X = data.drop(columns=["Sl_No", "Customer Key"])

# %% [markdown]
# ## Extraccion

# %%
class FeatureExtractor(BaseEstimator, TransformerMixin):
    """Selecciona/descarta columnas del dataframe crudo."""

    def __init__(self, columns_to_drop=None):
        self.columns_to_drop = columns_to_drop or []

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = X.copy()
        cols = [c for c in self.columns_to_drop if c in X.columns]
        return X.drop(columns=cols)

# %% [markdown]
# ## Filtrado

# %%
class RowFilter(BaseEstimator, TransformerMixin):
    """Elimina duplicados, filas con exceso de nulos y valores fuera de rango."""

    def __init__(self, max_null_ratio=0.5, numeric_bounds=None):
        self.max_null_ratio = max_null_ratio
        self.numeric_bounds = numeric_bounds or {}

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = X.copy()
        X = X.drop_duplicates()

        null_ratio = X.isnull().mean(axis=1)
        X = X[null_ratio <= self.max_null_ratio]

        for col, (low, high) in self.numeric_bounds.items():
            if col in X.columns:
                X = X[((X[col] >= low) & (X[col] <= high)) | X[col].isnull()]

        return X

# %% [markdown]
# ## Limpieza

# %%
columnas_a_descartar = ["Sl_No", "Customer Key"]
rangos_numericos = {}

cleaning_pipeline = Pipeline(steps=[
    ('extraccion', FeatureExtractor(columns_to_drop=columnas_a_descartar)),
    ('filtrado', RowFilter(max_null_ratio=0.5, numeric_bounds=rangos_numericos)),
])

data_clean = cleaning_pipeline.fit_transform(data)
print('Shape original:', data.shape, '-> Shape limpio:', data_clean.shape)

# %% [markdown]
# ## Split de Datos

# %%
target_column = 'Avg_Credit_Limit'
X = data_clean.drop(columns=[target_column])
y = data_clean[target_column]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

print('X_train:', X_train.shape, ' X_test:', X_test.shape)

# %% [markdown]
# ## Transformacion

# %%
numeric_pipeline = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler()),
])

categorical_pipeline = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='most_frequent')),
    ('onehot', OneHotEncoder(handle_unknown='ignore')),
])

preprocessor = ColumnTransformer(transformers=[
    ('num', numeric_pipeline, make_column_selector(dtype_include=np.number)),
    ('cat', categorical_pipeline, make_column_selector(dtype_include=object)),
])

# %% [markdown]
# ## Pipeline Final

# %%
model_pipeline = Pipeline(steps=[
    ('preprocesamiento', preprocessor)
])

X_train_transformed = model_pipeline.fit_transform(X_train)
X_test_transformed = model_pipeline.transform(X_test)

print('X_train_transformed:', X_train_transformed.shape)
print('X_test_transformed:', X_test_transformed.shape)

# %% [markdown]
# ## Diagrama

# %%
from sklearn import set_config
set_config(display='diagram')

full_pipeline = Pipeline(steps=[
    ('extraccion', FeatureExtractor(columns_to_drop=columnas_a_descartar)),
    ('filtrado', RowFilter(max_null_ratio=0.5, numeric_bounds=rangos_numericos)),
    ('preprocesamiento', preprocessor),
])

full_pipeline

# %% [markdown]
# ## Modeling (CRISP-DM)

# %% [markdown]
# Colocamos aqui el modelo (`RandomForestRegressor`) y usamos `GridSearchCV` sobre el pipeline de preprocesamiento + modelo para calibrar sus hiperparametros (referenciando cada step con la notacion `step__parametro`).

# %%
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV

model_pipeline_final = Pipeline(steps=[
    ('preprocesamiento', preprocessor),
    ('modelo', RandomForestRegressor(random_state=42)),
])

param_grid = {
    'modelo__n_estimators': [100, 200],
    'modelo__max_depth': [None, 5, 10],
    'preprocesamiento__num__imputer__strategy': ['median', 'mean'],
}

search = GridSearchCV(model_pipeline_final, param_grid, cv=3, scoring='r2', n_jobs=-1)
search.fit(X_train, y_train)

print('Mejores hiperparametros:', search.best_params_)

# %% [markdown]
# ## Evaluation (CRISP-DM)

# %% [markdown]
# Evaluamos el mejor modelo encontrado por `GridSearchCV` sobre el set de test.

# %%
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

y_pred = search.predict(X_test)

print('R2:', r2_score(y_test, y_pred))
print('MAE:', mean_absolute_error(y_test, y_pred))
print('RMSE:', mean_squared_error(y_test, y_pred) ** 0.5)

# %% [markdown]
# ## Empaquetado

# %% [markdown]
# Empaquetamos este pipeline como el paquete instalable `credit_pipeline` (`pyproject.toml` + carpeta `src/`) para compartirlo con el equipo. Se instala con `pip install -e .` y se corre con el comando `run-pipeline`.


