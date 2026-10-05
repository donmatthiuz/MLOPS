from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

DEFAULT_MODEL_PATH = "models/titanic_survival_pipeline.joblib"
DEFAULT_SOURCE = "https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv"


def train(argv: Sequence[str] | None = None) -> int:
    from .pipeline import train_pipeline

    parser = argparse.ArgumentParser(description="Entrena el pipeline Titanic.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="URL o ruta CSV de entrenamiento.")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH, help="Ruta para guardar el modelo joblib.")
    parser.add_argument("--test-size", type=float, default=0.20, help="Proporcion de datos de prueba.")
    args = parser.parse_args(argv)

    metrics = train_pipeline(
        source=args.source,
        model_path=Path(args.model_path),
        test_size=args.test_size,
    )
    print(json.dumps(metrics, indent=2))
    return 0


def predict(argv: Sequence[str] | None = None) -> int:
    from .pipeline import predict_survival

    parser = argparse.ArgumentParser(description="Predice supervivencia con un pipeline entrenado.")
    parser.add_argument("input_csv", help="CSV con datos crudos para inferencia.")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH, help="Ruta del modelo joblib.")
    parser.add_argument("--output-csv", default=None, help="Ruta opcional para guardar predicciones.")
    args = parser.parse_args(argv)

    result = predict_survival(
        input_csv=Path(args.input_csv),
        model_path=Path(args.model_path),
        output_csv=Path(args.output_csv) if args.output_csv else None,
    )
    print(result.to_string(index=False))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Comandos del pipeline Titanic.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="Entrena y guarda el modelo.")
    train_parser.add_argument("--source", default=DEFAULT_SOURCE)
    train_parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    train_parser.add_argument("--test-size", type=float, default=0.20)

    predict_parser = subparsers.add_parser("predict", help="Genera predicciones.")
    predict_parser.add_argument("input_csv")
    predict_parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    predict_parser.add_argument("--output-csv", default=None)

    args = parser.parse_args(argv)
    if args.command == "train":
        return train(
            [
                "--source",
                args.source,
                "--model-path",
                args.model_path,
                "--test-size",
                str(args.test_size),
            ]
        )
    if args.command == "predict":
        predict_args = [args.input_csv, "--model-path", args.model_path]
        if args.output_csv:
            predict_args.extend(["--output-csv", args.output_csv])
        return predict(predict_args)

    parser.error(f"Comando no soportado: {args.command}")
    return 2
