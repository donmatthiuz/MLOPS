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
    return f"{catalog}.equipo7.{layer}_{name}"


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


def _sync_managed_table(spark, cfg: dict, layer: str, name: str) -> None:
    """Actualiza la tabla administrada del equipo desde el Delta de su bucket."""
    view = f"_equipo7_{layer}_{name}_source"
    spark.read.format("delta").load(_path(cfg, layer, name)).createOrReplaceTempView(view)
    try:
        spark.sql(f"CREATE OR REPLACE TABLE {_table(cfg, layer, name)} USING DELTA AS SELECT * FROM {view}")
    finally:
        spark.catalog.dropTempView(view)


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
    before = 0
    if DeltaTable.isDeltaTable(spark, dest):
        before = spark.read.format("delta").load(dest).count()
        target = DeltaTable.forPath(spark, dest)
        target.alias("t").merge(photos.alias("s"), "t.path = s.path").whenNotMatchedInsertAll().execute()
    else:
        photos.write.format("delta").mode("overwrite").save(dest)
    _sync_managed_table(spark, cfg, "bronze", "fotos_precios")
    # Criterio de aceptación: cada foto de la carpeta está una sola vez en la tabla.
    table = spark.read.format("delta").load(dest)
    source_paths = photos.select("path")  # binaryFile no lee el contenido si no se selecciona
    total, distinct = table.count(), table.select("path").distinct().count()
    missing = source_paths.subtract(table.select("path")).count()
    if missing or total != distinct:
        raise RuntimeError(f"Bronce inconsistente: {missing} fotos sin cargar, {total - distinct} duplicadas")
    print(f"Bronce: {source_paths.count()} fotos en la carpeta, {total} filas en la tabla, {total - before} nuevas en esta carga")
    _bronze_wti(spark, cfg)


WTI_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILWTICO"


def _bronze_wti(spark, cfg: dict) -> None:
    """Fuente complementaria opcional: precio WTI diario (FRED) en su CSV original."""
    import requests
    from pyspark.dbutils import DBUtils
    from pyspark.sql import functions as F

    try:
        response = requests.get(WTI_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Bronce WTI omitido (sin acceso a FRED): {exc}")  # opcional: no detiene las fotos
        return
    if not response.text.startswith("observation_date,DCOILWTICO"):
        raise RuntimeError("FRED cambió el formato del CSV de WTI")
    raw = f"{_layer_dir(cfg, 'bronze')}/fuentes/wti/{date.today().isoformat()}.csv"
    DBUtils(spark).fs.put(raw, response.text, True)
    # Copia completa de la serie en cada carga: reemplazar es idempotente y FRED corrige valores pasados.
    (spark.read.option("header", "true").csv(raw)
     .withColumn("_ingestion_timestamp", F.current_timestamp())
     .withColumn("_source_file", F.lit(raw))
     .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
     .save(_path(cfg, "bronze", "petroleo_wti")))
    _sync_managed_table(spark, cfg, "bronze", "petroleo_wti")
    print(f"Bronce WTI: {spark.read.format('delta').load(_path(cfg, 'bronze', 'petroleo_wti')).count()} días en {raw}")


def _photo_date(path: str, modification_time) -> date:
    match = re.search(r"/(\d{4}-\d{2}-\d{2})/", path)
    if match:
        return date.fromisoformat(match.group(1))
    return modification_time.date()


def silver(cfg: dict, *, reprocess: bool = False) -> None:
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
    if not reprocess:
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
    if reprocess and not accepted:
        raise RuntimeError("El reproceso no produjo precios válidos; se conservaron las tablas Plata anteriores")
    for rows, schema, path, layer_name, condition in (
        (accepted, price_schema, silver_path, "precios", "t.fecha = s.fecha AND t.ubicacion = s.ubicacion AND t.combustible = s.combustible AND t.modalidad = s.modalidad"),
        (rejected, reject_schema, rejected_path, "precios_rejected", "t.foto_origen = s.foto_origen AND t.combustible <=> s.combustible AND t.motivo = s.motivo"),
    ):
        if not rows and not reprocess:
            continue
        incoming = spark.createDataFrame(rows, schema)
        if layer_name == "precios":
            incoming = incoming.dropDuplicates(["fecha", "ubicacion", "combustible", "modalidad"])
        else:
            incoming = incoming.dropDuplicates(["foto_origen", "combustible", "motivo"])
        if reprocess:
            incoming.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(path)
        elif DeltaTable.isDeltaTable(spark, path):
            DeltaTable.forPath(spark, path).alias("t").merge(incoming.alias("s"), condition).whenNotMatchedInsertAll().execute()
        else:
            incoming.write.format("delta").mode("overwrite").save(path)
    for layer_name, path in (("precios", silver_path), ("precios_rejected", rejected_path)):
        if DeltaTable.isDeltaTable(spark, path):
            _sync_managed_table(spark, cfg, "silver", layer_name)
    mode = "reprocesada" if reprocess else "incremental"
    print(f"Plata {mode}: {len(accepted)} lecturas válidas, {len(rejected)} rechazadas en esta ejecución")


def _read_wti(spark, cfg: dict):
    """WTI de Bronce en pandas, o None si no existe. TRY_CAST: en serverless (ANSI) CAST('') falla."""
    table = _table(cfg, "bronze", "petroleo_wti")
    if not spark.catalog.tableExists(table):
        print(f"Oro: no existe {table}; se continúa sin la variable WTI")
        return None
    return spark.sql(f"SELECT observation_date, TRY_CAST(NULLIF(TRIM(DCOILWTICO), '') AS DOUBLE) AS DCOILWTICO FROM {table}").toPandas()


def _apply_gold_comments(spark, cfg: dict, name: str) -> None:
    """COMMENT de la tabla y sus columnas; se reaplica tras cada CREATE OR REPLACE."""
    from gasolina_gt.gold.comments import sentencias_comentarios

    for statement in sentencias_comentarios(_table(cfg, "gold", name), name):
        try:
            spark.sql(statement)
        except Exception as exc:
            print(f"Oro: no se pudo aplicar el comentario ({exc}): {statement[:90]}")


def _write_gold_table(spark, cfg: dict, name: str, frame, *, mode: str = "overwrite") -> None:
    from gasolina_gt.gold.schemas import ddl, registros

    df = spark.createDataFrame(registros(frame, name), ddl(name))
    writer = df.write.format("delta").mode(mode)
    writer = writer.option("mergeSchema", "true") if mode == "append" else writer.option("overwriteSchema", "true")
    writer.save(_path(cfg, "gold", name))


def _merge_predictions(spark, cfg: dict, frame) -> None:
    """MERGE por (semana, combustible, tipo); `frame` ya trae la tabla combinada."""
    from delta.tables import DeltaTable
    from gasolina_gt.gold.schemas import ddl, registros

    path = _path(cfg, "gold", "predicciones")
    source = spark.createDataFrame(registros(frame, "predicciones"), ddl("predicciones"))
    if not DeltaTable.isDeltaTable(spark, path):
        source.write.format("delta").mode("overwrite").save(path)
        return
    (DeltaTable.forPath(spark, path).alias("t")
     .merge(source.alias("s"), "t.semana = s.semana AND t.combustible = s.combustible AND t.tipo = s.tipo")
     .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())


def gold(cfg: dict, params=None) -> None:
    """Oro: lee Plata, calcula con gasolina_gt.gold, escribe, sincroniza y comenta las tablas."""
    import sys
    from functools import partial

    import pandas as pd
    from delta.tables import DeltaTable
    from gasolina_gt.config import resolve_path
    from gasolina_gt.gold.params import resolver_parametros, widgets_databricks
    from gasolina_gt.gold.pipeline import compute_gold
    from gasolina_gt.gold.tracking import registrar_experimento

    spark = _spark()
    _ensure_layer_dir(spark, cfg, "gold")
    silver_path = _path(cfg, "silver", "precios")
    if not DeltaTable.isDeltaTable(spark, silver_path):
        raise RuntimeError("Primero ejecute 02_silver.py y obtenga al menos una lectura válida")
    params = params or resolver_parametros(widgets_databricks(), sys.argv[1:])
    print(f"Oro: parámetros {params}")

    prices = spark.read.format("delta").load(silver_path).select("fecha", "combustible", "precio_q_galon").toPandas()
    wti = _read_wti(spark, cfg) if params.usar_wti else None
    predictions_path = _path(cfg, "gold", "predicciones")
    previous = (spark.read.format("delta").load(predictions_path).toPandas()
                if DeltaTable.isDeltaTable(spark, predictions_path) else None)
    reports = cfg.get("paths", {}).get("reports")
    tracker = partial(registrar_experimento, experimento=params.experimento_mlflow,
                      reports_dir=resolve_path(reports) if reports else None)

    result = compute_gold(prices, wti, params, previas=previous, tracker=tracker)

    for name in ("precio_semanal", "variacion_semanal", "features_modelo"):
        _write_gold_table(spark, cfg, name, getattr(result, name))
    _merge_predictions(spark, cfg, result.predicciones)
    _write_gold_table(spark, cfg, "metricas_modelo", result.metricas_modelo, mode="append")
    for name in ("precio_semanal", "variacion_semanal", "features_modelo", "predicciones", "metricas_modelo"):
        _sync_managed_table(spark, cfg, "gold", name)
        _apply_gold_comments(spark, cfg, name)
    metrics = result.metricas_modelo.iloc[0]
    print(f"Oro: modelo {metrics.modelo_elegido} (pocos datos: {bool(metrics.modo_pocos_datos)}), "
          f"{len(result.predicciones)} predicciones, run MLflow: {metrics.run_id_mlflow}")
