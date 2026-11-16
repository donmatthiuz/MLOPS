"""Parámetros de Oro. Prioridad: widgets > argumentos CLI > variables de entorno > valor por defecto."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

WidgetGetter = Callable[[str], Optional[str]]

# campo -> (widget, argumento CLI, variable de entorno)
_ORIGENES = {
    "umbral_q": ("umbral_q", "--umbral-q", "GOLD_UMBRAL_Q"),
    "semanas_test": ("semanas_test", "--semanas-test", "GOLD_SEMANAS_TEST"),
    "experimento_mlflow": ("mlflow_experiment", "--mlflow-experiment", "GOLD_MLFLOW_EXPERIMENT"),
    "usar_wti": ("usar_wti", "--usar-wti", "GOLD_USAR_WTI"),
    "min_ejemplos": ("min_ejemplos", "--min-ejemplos", "GOLD_MIN_EJEMPLOS"),
    "min_train": ("min_train", "--min-train", "GOLD_MIN_TRAIN"),
}


@dataclass(frozen=True)
class GoldParams:
    umbral_q: float = 0.10
    semanas_test: int = 4
    experimento_mlflow: str = "/Shared/equipo7-gasolina"
    usar_wti: bool = True
    min_ejemplos: int = 20
    min_train: int = 12
    semilla: int = 42


_VERDADERO = {"1", "true", "si", "sí", "yes", "y", "s"}
_FALSO = {"0", "false", "no", "n"}


def _a_bool(texto: str) -> bool:
    valor = texto.strip().lower()
    if valor in _VERDADERO:
        return True
    if valor in _FALSO:
        return False
    raise ValueError(f"usar_wti debe ser sí/no, se recibió {texto!r}")


def widgets_databricks() -> Optional[WidgetGetter]:
    """Crea los widgets y devuelve un lector; None fuera de Databricks.

    Van vacíos a propósito: con valor por defecto taparían siempre al CLI y al entorno."""
    try:
        from pyspark.dbutils import DBUtils  # type: ignore
        from pyspark.sql import SparkSession  # type: ignore
        widgets = DBUtils(SparkSession.builder.getOrCreate()).widgets
        defecto = GoldParams()
        for campo, (widget, _, _) in _ORIGENES.items():
            valor = getattr(defecto, campo)
            texto = str(valor).lower() if isinstance(valor, bool) else str(valor)
            widgets.text(widget, "", f"{widget} (vacío = {texto})")
    except Exception:
        return None

    def leer(nombre: str) -> Optional[str]:
        try:
            return widgets.get(nombre)
        except Exception:
            return None

    return leer


def resolver_parametros(widgets: Optional[WidgetGetter] = None, argv: Optional[Sequence[str]] = None,
                        env: Optional[dict] = None) -> GoldParams:
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    for _, flag, _ in _ORIGENES.values():
        parser.add_argument(flag, dest=flag.lstrip("-").replace("-", "_"))
    cli, _desconocidos = parser.parse_known_args(list(argv or []))

    crudos: dict[str, str] = {}
    for campo, (widget, flag, variable) in _ORIGENES.items():
        candidatos = (
            widgets(widget) if widgets else None,
            getattr(cli, flag.lstrip("-").replace("-", "_")),
            env.get(variable),
        )
        for valor in candidatos:
            if valor is not None and str(valor).strip() != "":
                crudos[campo] = str(valor).strip()
                break

    try:
        params = GoldParams(
            umbral_q=float(crudos.get("umbral_q", GoldParams.umbral_q)),
            semanas_test=int(crudos.get("semanas_test", GoldParams.semanas_test)),
            experimento_mlflow=crudos.get("experimento_mlflow", GoldParams.experimento_mlflow),
            usar_wti=_a_bool(crudos["usar_wti"]) if "usar_wti" in crudos else GoldParams.usar_wti,
            min_ejemplos=int(crudos.get("min_ejemplos", GoldParams.min_ejemplos)),
            min_train=int(crudos.get("min_train", GoldParams.min_train)),
        )
    except ValueError as exc:
        raise ValueError(f"Parámetro de Oro inválido: {exc}") from exc
    if params.umbral_q < 0:
        raise ValueError("Parámetro de Oro inválido: umbral_q no puede ser negativo")
    if params.semanas_test < 1:
        raise ValueError("Parámetro de Oro inválido: semanas_test debe ser al menos 1")
    if params.min_train > params.min_ejemplos:
        raise ValueError("Parámetro de Oro inválido: min_train no puede superar a min_ejemplos")
    return params
