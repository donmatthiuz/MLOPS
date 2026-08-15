import platform
import socket
from datetime import datetime

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.utils import estimator_html_repr

from .data import load_data
from .pipeline import build_cleaning_pipeline, build_full_pipeline, build_search

TARGET_COLUMN = "Avg_Credit_Limit"


def main():
    print("=" * 60)
    print("Ejecutando credit-pipeline")
    print("Host:", socket.gethostname())
    print("Python:", platform.python_version())
    print("Fecha:", datetime.now().isoformat(timespec="seconds"))
    print("=" * 60)

    data = load_data()

    # Colocamos aqui la limpieza (extraccion + filtrado) sobre el dataframe
    # crudo, antes de separar X/y y de entrar al modelo.
    cleaning = build_cleaning_pipeline()
    data_clean = cleaning.fit_transform(data)
    print(f"\nShape crudo: {data.shape} -> Shape limpio: {data_clean.shape}")

    X = data_clean.drop(columns=[TARGET_COLUMN])
    y = data_clean[TARGET_COLUMN]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Usamos GridSearchCV para calibrar los hiperparametros del pipeline
    # de preprocesamiento + modelo.
    search = build_search(cv=3)
    search.fit(X_train, y_train)

    print("\nMejores hiperparametros encontrados:")
    for param, value in search.best_params_.items():
        print(f"  {param}: {value}")

    y_pred = search.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = mean_squared_error(y_test, y_pred) ** 0.5

    print("\nEvaluacion en test:")
    print(f"  R2:   {r2:.4f}")
    print(f"  MAE:  {mae:.2f}")
    print(f"  RMSE: {rmse:.2f}")

    with open("pipeline_diagram.html", "w") as f:
        f.write(estimator_html_repr(build_full_pipeline()))
    print("\nDiagrama del pipeline guardado en pipeline_diagram.html")
    print("\nPIPELINE EJECUTADO CORRECTAMENTE")


if __name__ == "__main__":
    main()
