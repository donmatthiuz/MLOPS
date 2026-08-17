"""Pipeline de datos: Bronze (extracción cruda) -> Silver (tabla limpia) ->
Gold (dataset con historia sintética + features, listo para modelar).

Sigue la arquitectura de capas mencionada en el Business Understanding
("arquitectura Bronze/Silver/Gold", recurso clave N2).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from ..augmentation.series_augment import generar_serie_sintetica
from ..config import load_config, resolve_path
from ..extraction.extractor import ExtractorPrecios
from .features import construir_features

logger = logging.getLogger(__name__)


def construir_silver(config: dict | None = None) -> pd.DataFrame:
    """Ejecuta la extracción sobre datos/ y devuelve solo las lecturas
    válidas (que pasaron el umbral de confianza y el rango plausible) como
    tabla limpia: fecha (real, EXIF), tipo_combustible, precio."""
    cfg = config or load_config()
    extractor = ExtractorPrecios(cfg)
    registros = extractor.procesar_directorio()
    extractor.guardar_bronze(registros)

    filas = []
    for r in registros:
        if r.capturada_en is None:
            continue
        fecha = datetime.fromisoformat(r.capturada_en).date()
        for lectura in r.lecturas:
            if lectura.valido:
                filas.append(
                    {
                        "fecha": fecha,
                        "tipo_combustible": lectura.tipo_combustible,
                        "precio_gtq_por_galon": lectura.precio_gtq_por_galon,
                        "confianza": lectura.confianza,
                        "archivo_origen": r.archivo,
                    }
                )
    df = pd.DataFrame(filas, columns=["fecha", "tipo_combustible", "precio_gtq_por_galon", "confianza", "archivo_origen"])

    silver_dir = resolve_path(cfg["paths"]["silver"])
    silver_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(silver_dir / "precios_reales.csv", index=False)
    logger.info("Silver: %d lecturas reales válidas de %d imágenes", len(df), len(registros))
    return df


def construir_gold(
    df_silver: pd.DataFrame | None = None,
    config: dict | None = None,
    fecha_fin: date | None = None,
) -> pd.DataFrame:
    """Combina anclas reales + serie sintética calibrada, y agrega las
    features de modelado (lags, medias móviles, calendario)."""
    cfg = config or load_config()
    df_silver = df_silver if df_silver is not None else construir_silver(cfg)

    fecha_fin = fecha_fin or date.today()
    if not df_silver.empty:
        fecha_inicio = min(df_silver["fecha"]) - timedelta(weeks=8)
    else:
        fecha_inicio = fecha_fin - timedelta(weeks=52)

    serie = generar_serie_sintetica(df_silver, fecha_inicio, fecha_fin, cfg)
    gold = construir_features(serie, cfg)

    gold_dir = resolve_path(cfg["paths"]["gold"])
    gold_dir.mkdir(parents=True, exist_ok=True)
    gold.to_csv(gold_dir / "dataset_modelado.csv", index=False)
    logger.info("Gold: %d filas (%d reales, %d sintéticas)", len(gold), (gold["fuente"] == "real").sum(), (gold["fuente"] == "sintetico").sum())
    return gold


def cargar_gold_si_existe(config: dict | None = None) -> pd.DataFrame | None:
    cfg = config or load_config()
    ruta = resolve_path(cfg["paths"]["gold"]) / "dataset_modelado.csv"
    if not ruta.exists():
        return None
    return pd.read_csv(ruta, parse_dates=["fecha"])
