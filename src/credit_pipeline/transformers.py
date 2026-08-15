from sklearn.base import BaseEstimator, TransformerMixin


class FeatureExtractor(BaseEstimator, TransformerMixin):
    """Selecciona/descarta columnas del dataframe crudo."""

    def __init__(self, columns_to_drop=None):
        self.columns_to_drop = columns_to_drop

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = X.copy()
        columns_to_drop = self.columns_to_drop or []
        cols = [c for c in columns_to_drop if c in X.columns]
        return X.drop(columns=cols)


class RowFilter(BaseEstimator, TransformerMixin):
    """Elimina duplicados, filas con exceso de nulos y valores fuera de rango."""

    def __init__(self, max_null_ratio=0.5, numeric_bounds=None):
        self.max_null_ratio = max_null_ratio
        self.numeric_bounds = numeric_bounds

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = X.copy()
        X = X.drop_duplicates()

        null_ratio = X.isnull().mean(axis=1)
        X = X[null_ratio <= self.max_null_ratio]

        numeric_bounds = self.numeric_bounds or {}
        for col, (low, high) in numeric_bounds.items():
            if col in X.columns:
                X = X[((X[col] >= low) & (X[col] <= high)) | X[col].isnull()]

        return X
