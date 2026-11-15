"""Capas Delta para ejecución dentro de Databricks con external locations autorizadas.

El workspace debe tener instalado el paquete gasolina-gt y los permisos de
Unity Catalog. No se usan llaves AWS en el pipeline.
"""
from __future__ import annotations

import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse


def _spark():
    from pyspark.sql import SparkSession
    return SparkSession.builder.getOrCreate()


def _table(cfg: dict, layer: str, name: str) -> str:
    catalog = cfg["source"]["catalog"]
    return f"{catalog}.{layer}.{name}"


def _path(cfg: dict, layer: str, name: str) -> str:
    return _layer_dir(cfg, layer) + "/" + name


def _layer_dir(cfg: dict, layer: str) -> str:
    base = cfg["source"][f"{layer}_output"].rstrip("/")
    return base if base.rsplit("/", 1)[-1] == "equipo7" else base + "/equipo7"


def _image_dir(cfg: dict) -> str:
    base = cfg["source"]["bronze_input"].rstrip("/")
    return base if base.rsplit("/", 1)[-1] == "img" else base + "/img"


def _ensure_layer_dir(spark, cfg: dict, layer: str) -> None:
    from pyspark.dbutils import DBUtils

    path = _layer_dir(cfg, layer)
    if not DBUtils(spark).fs.mkdirs(path):
        raise RuntimeError(f"No se pudo crear la carpeta de {layer}: {path}")


def _register(spark, cfg: dict, layer: str, name: str) -> None:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {cfg['source']['catalog']}.{layer}")
    spark.sql(f"CREATE TABLE IF NOT EXISTS {_table(cfg, layer, name)} USING DELTA LOCATION '{_path(cfg, layer, name)}'")


def bronze(cfg: dict) -> None:
    from delta.tables import DeltaTable
    from pyspark.sql import functions as F

    spark = _spark()
    _ensure_layer_dir(spark, cfg, "bronze")
    source = _image_dir(cfg)
    dest = _path(cfg, "bronze", "fotos_precios")
    photos = (spark.read.format("binaryFile")
              .option("recursiveFileLookup", "true")
              .load(source)
              .filter(F.lower(F.regexp_extract("path", r"\.([^.]+)$", 1)).isin("heic", "jpg", "jpeg", "png"))
              .withColumn("_ingestion_timestamp", F.current_timestamp())
              .withColumn("_source_file", F.col("path")))
    if DeltaTable.isDeltaTable(spark, dest):
        target = DeltaTable.forPath(spark, dest)
        target.alias("t").merge(photos.alias("s"), "t.path = s.path").whenNotMatchedInsertAll().execute()
    else:
        photos.write.format("delta").mode("overwrite").save(dest)
    _register(spark, cfg, "bronze", "fotos_precios")
    print(f"Bronce: {spark.read.format('delta').load(dest).count()} fotos únicas")


def _photo_date(path: str, modification_time) -> date:
    match = re.search(r"/(\d{4}-\d{2}-\d{2})/", path)
    if match:
        return date.fromisoformat(match.group(1))
    return modification_time.date()


def silver(cfg: dict) -> None:
    from delta.tables import DeltaTable
    from pyspark.sql import types as T
    from gasolina_gt.extraction.extractor import ExtractorPrecios
    from gasolina_gt.extraction.heic_loader import cargar_imagen_generica

    spark = _spark()
    _ensure_layer_dir(spark, cfg, "silver")
    bronze_path = _path(cfg, "bronze", "fotos_precios")
    if not DeltaTable.isDeltaTable(spark, bronze_path):
        raise RuntimeError("Primero ejecute 01_bronze.py")
    silver_path = _path(cfg, "silver", "precios")
    rejected_path = _path(cfg, "silver", "precios_rejected")
    processed = set()
    for path in (silver_path, rejected_path):
        if DeltaTable.isDeltaTable(spark, path):
            processed.update(row.foto_origen for row in spark.read.format("delta").load(path).select("foto_origen").distinct().toLocalIterator())
    extractor = ExtractorPrecios(cfg)
    accepted, rejected = [], []
    for row in spark.read.format("delta").load(bronze_path).toLocalIterator():
        if row.path in processed:
            continue
        suffix = Path(urlparse(row.path).path).suffix.lower()
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / (Path(urlparse(row.path).path).name or f"foto{suffix}")
            local_path.write_bytes(bytes(row.content))
            try:
                record = extractor.extraer_de_imagen(cargar_imagen_generica(local_path))
            except Exception as exc:
                rejected.append((row.path, None, f"imagen_no_procesable: {exc}", datetime.utcnow()))
                continue
        fecha = _photo_date(row.path, row.modificationTime)
        if record.capturada_en:
            fecha = datetime.fromisoformat(record.capturada_en).date()
        for reading in record.lecturas:
            reason = reading.motivo_invalido
            if fecha > date.today():
                reason = "fecha_futura"
            elif reading.tipo_combustible not in {"super", "regular", "diesel"}:
                reason = "combustible_fuera_catalogo"
            elif reading.precio_gtq_por_galon is None or not 10 <= reading.precio_gtq_por_galon <= 80:
                reason = reason or "precio_fuera_rango"
            if reason:
                rejected.append((row.path, reading.tipo_combustible, reason, datetime.utcnow()))
            else:
                accepted.append((fecha, reading.tipo_combustible, float(reading.precio_gtq_por_galon),
                                 "no_especificada", "desconocida", row.path, datetime.utcnow()))
    price_schema = T.StructType([
        T.StructField("fecha", T.DateType()), T.StructField("combustible", T.StringType()),
        T.StructField("precio_q_galon", T.DoubleType()), T.StructField("modalidad", T.StringType()),
        T.StructField("ubicacion", T.StringType()), T.StructField("foto_origen", T.StringType()),
        T.StructField("_processed_timestamp", T.TimestampType()),
    ])
    reject_schema = T.StructType([
        T.StructField("foto_origen", T.StringType()), T.StructField("combustible", T.StringType()),
        T.StructField("motivo", T.StringType()), T.StructField("_processed_timestamp", T.TimestampType()),
    ])
    for rows, schema, path, layer_name, condition in (
        (accepted, price_schema, silver_path, "precios", "t.fecha = s.fecha AND t.ubicacion = s.ubicacion AND t.combustible = s.combustible AND t.modalidad = s.modalidad"),
        (rejected, reject_schema, rejected_path, "precios_rejected", "t.foto_origen = s.foto_origen AND t.combustible <=> s.combustible AND t.motivo = s.motivo"),
    ):
        if not rows:
            continue
        incoming = spark.createDataFrame(rows, schema)
        if layer_name == "precios":
            incoming = incoming.dropDuplicates(["fecha", "ubicacion", "combustible", "modalidad"])
        else:
            incoming = incoming.dropDuplicates(["foto_origen", "combustible", "motivo"])
        if DeltaTable.isDeltaTable(spark, path):
            DeltaTable.forPath(spark, path).alias("t").merge(incoming.alias("s"), condition).whenNotMatchedInsertAll().execute()
        else:
            incoming.write.format("delta").mode("overwrite").save(path)
        _register(spark, cfg, "silver", layer_name)
    print(f"Plata: {len(accepted)} lecturas válidas, {len(rejected)} rechazadas en esta ejecución")


def gold(cfg: dict) -> None:
    from delta.tables import DeltaTable
    from pyspark.sql import Window, functions as F

    spark = _spark()
    _ensure_layer_dir(spark, cfg, "gold")
    silver_path = _path(cfg, "silver", "precios")
    if not DeltaTable.isDeltaTable(spark, silver_path):
        raise RuntimeError("Primero ejecute 02_silver.py y obtenga al menos una lectura válida")
    prices = spark.read.format("delta").load(silver_path)
    weekly = (prices.withColumn("semana", F.date_sub(F.next_day("fecha", "Tue"), 7))
              .groupBy("semana", "combustible")
              .agg(F.avg("precio_q_galon").alias("precio_promedio"),
                   F.min("precio_q_galon").alias("precio_minimo"),
                   F.max("precio_q_galon").alias("precio_maximo")))
    window = Window.partitionBy("combustible").orderBy("semana")
    variations = (weekly.withColumn("precio_anterior", F.lag("precio_promedio").over(window))
                  .withColumn("diferencia_q", F.col("precio_promedio") - F.col("precio_anterior"))
                  .withColumn("diferencia_pct", F.col("diferencia_q") / F.col("precio_anterior") * 100)
                  .withColumn("direccion", F.when(F.col("diferencia_q") > 0.10, "sube")
                              .when(F.col("diferencia_q") < -0.10, "baja").otherwise("se_mantiene")))
    features = variations
    for lag in range(1, 5):
        features = features.withColumn(f"variacion_lag_{lag}", F.lag("diferencia_q", lag).over(window))
    features = features.withColumn("promedio_movil_4", F.avg("precio_promedio").over(window.rowsBetween(-3, 0)))
    for name, frame in (("precio_semanal", weekly), ("variacion_semanal", variations), ("features_modelo", features)):
        path = _path(cfg, "gold", name)
        frame.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(path)
        _register(spark, cfg, "gold", name)
    print("Oro: precio_semanal, variacion_semanal y features_modelo actualizados")
