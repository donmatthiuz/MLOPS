# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Plata — extracción de precios y reglas de calidad
# MAGIC
# MAGIC Convierte cada foto de Bronce en filas limpias de precio (una por fecha, ubicación, combustible y modalidad).
# MAGIC
# MAGIC 1. **Extracción**: un modelo de visión servido en Databricks lee cada foto **dos veces** (dos resoluciones).
# MAGIC 2. **Conciliación**: un precio se acepta si ambas lecturas coinciden, o si una coincide con el precio que se deduce
# MAGIC    del display de la bomba (monto ÷ galones).
# MAGIC 3. **Calidad**: fecha EXIF conocida, no futura y coherente con la carpeta del año; combustible del catálogo
# MAGIC    (súper, regular, diésel); precio en rango; lecturas consistentes; súper ≥ regular.
# MAGIC    Lo que falla va a `precios_rejected` con su motivo.
# MAGIC 4. **Carga idempotente**: `MERGE` por `fecha + ubicacion + combustible + modalidad`; las fotos ya procesadas se omiten.
# MAGIC
# MAGIC **Modos** (`modo`):
# MAGIC - `incremental`: solo fotos nuevas de Bronce (lo normal en el Job).
# MAGIC - `reaplicar_reglas`: **no llama al modelo**; vuelve a aplicar las reglas a las respuestas guardadas en `extracciones`
# MAGIC   y reemplaza `precios` y `precios_rejected`. Útil cuando cambia una regla.
# MAGIC - `reprocesar_todo`: vuelve a enviar todas las fotos al modelo y reemplaza las tres tablas (~20 min para 110 fotos).
# MAGIC
# MAGIC Las tablas Delta viven en S3 (`<silver_uri>/<tabla>`) y se copian a tablas administradas
# MAGIC `workspace.equipo7.silver_<tabla>` para consultarlas en Catalog Explorer.

# COMMAND ----------

# MAGIC %md
# MAGIC Dependencias (`pillow-heif`, `openai`) definidas en el entorno serverless del Job.

# COMMAND ----------

import sys

EN_DATABRICKS = "dbutils" in globals()

if not EN_DATABRICKS:
    # Ejecución local (python pipelines/02_silver.py): flujo original con OCR de 7 segmentos sobre LOCAL_DATA_DIR.
    from common import settings
    from gasolina_gt.data.pipeline import construir_silver

    _cfg = settings()
    if _cfg["source"]["mode"] == "databricks":
        sys.exit("En Databricks, ejecute este archivo como notebook o tarea de notebook del Job.")
    print(f"Plata local: {len(construir_silver(_cfg))} lecturas válidas")
    sys.exit(0)

# COMMAND ----------

dbutils.widgets.text("origen", "",
                     "Origen: Delta de Bronce, tabla, o carpeta s3:// de fotos")
dbutils.widgets.text("silver_uri", "", "Prefijo S3 de Plata")
dbutils.widgets.text("catalogo", "workspace", "Catálogo")
dbutils.widgets.text("esquema", "equipo7", "Esquema")
dbutils.widgets.dropdown("modo", "incremental", ["incremental", "reaplicar_reglas", "reprocesar_todo"], "Modo")
dbutils.widgets.text("modelo", "databricks-llama-4-maverick", "Endpoint del modelo de visión")
dbutils.widgets.text("lado_a", "1600", "Resolución lectura A (px)")
dbutils.widgets.text("lado_b", "2560", "Resolución lectura B (px)")
dbutils.widgets.text("precio_min", "15", "Precio mínimo válido (Q/gal)")
dbutils.widgets.text("precio_max", "60", "Precio máximo válido (Q/gal)")
dbutils.widgets.text("limite_fotos", "0", "Máximo de fotos nuevas (0 = todas)")
dbutils.widgets.dropdown("escribir", "si", ["si", "no"], "¿Escribir tablas?")

P = {k: dbutils.widgets.get(k) for k in
     ("origen", "silver_uri", "catalogo", "esquema", "modo", "modelo", "lado_a", "lado_b",
      "precio_min", "precio_max", "limite_fotos", "escribir")}
if not P["origen"].strip() or not P["silver_uri"].strip():
    raise ValueError("Faltan parámetros origen y silver_uri; configúrelos en el Job o en los widgets")
P["silver_uri"] = P["silver_uri"].rstrip("/")
for k in ("catalogo", "esquema"):
    if not P[k].replace("_", "").isalnum():
        raise ValueError(f"{k} inválido: {P[k]}")
NOMBRES = ("precios", "precios_rejected", "extracciones")
RUTA = {n: f"{P['silver_uri']}/{n}" for n in NOMBRES}
TABLA = {n: f"{P['catalogo']}.{P['esquema']}.silver_{n}" for n in NOMBRES}  # misma convención que databricks_layers
print(P)

# COMMAND ----------

import os

# Las reglas viven en pipelines/plata_reglas.py (probadas con pytest).
try:
    _nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    for _d in (os.getcwd(), "/Workspace" + os.path.dirname(_nb)):
        if _d not in sys.path:
            sys.path.insert(0, _d)
    from plata_reglas import (anio_de_ruta, conciliar, lecturas_por_combustible, motivo_rechazo, normalizar_modalidad,
                              normalizar_ubicacion, orden_incoherente, parsear_respuesta, precio_desde_display)
except ImportError as exc:
    raise ImportError("No se encontró plata_reglas.py junto a este notebook (Git folder del repo).") from exc

# COMMAND ----------

import base64, io, json
from datetime import date, datetime, timezone
from decimal import Decimal

from delta.tables import DeltaTable
from pyspark.sql import functions as F
from pyspark.sql import types as T

ESQUEMAS = {
    "precios": T.StructType([
        T.StructField("fecha", T.DateType(), metadata={"comment": "Fecha de captura de la foto (EXIF)"}),
        T.StructField("combustible", T.StringType(), metadata={"comment": "super, regular o diesel"}),
        T.StructField("precio_q_galon", T.DecimalType(6, 2), metadata={"comment": "Precio en quetzales por galón"}),
        T.StructField("modalidad", T.StringType(), metadata={"comment": "autoservicio, servicio completo o no_especificada"}),
        T.StructField("ubicacion", T.StringType(), metadata={"comment": "Estación y/o lugar leído en la foto; desconocida si no aparece"}),
        T.StructField("foto_origen", T.StringType(), metadata={"comment": "Ruta de la foto en Bronce"}),
        T.StructField("metodo_validacion", T.StringType(), metadata={"comment": "consenso (dos lecturas iguales) o display_bomba (coincide con monto/galones)"}),
        T.StructField("_processed_timestamp", T.TimestampType()),
    ]),
    "precios_rejected": T.StructType([
        T.StructField("foto_origen", T.StringType()),
        T.StructField("combustible", T.StringType()),
        T.StructField("precio_q_galon", T.DoubleType()),
        T.StructField("motivo", T.StringType(), metadata={"comment": "Regla de calidad que falló"}),
        T.StructField("_processed_timestamp", T.TimestampType()),
    ]),
    "extracciones": T.StructType([
        T.StructField("foto_origen", T.StringType()),
        T.StructField("fecha", T.DateType()),
        T.StructField("fuente_fecha", T.StringType()),
        T.StructField("respuesta_a", T.StringType(), metadata={"comment": "Respuesta cruda del modelo, lectura A"}),
        T.StructField("respuesta_b", T.StringType(), metadata={"comment": "Respuesta cruda del modelo, lectura B"}),
        T.StructField("precio_display", T.DoubleType(), metadata={"comment": "monto/galones del display de la bomba"}),
        T.StructField("_processed_timestamp", T.TimestampType()),
    ]),
}
LLAVES = {
    "precios": ["fecha", "ubicacion", "combustible", "modalidad"],
    "precios_rejected": ["foto_origen", "combustible", "motivo"],
    "extracciones": ["foto_origen"],
}
CONDICION = {
    "precios": "t.fecha = s.fecha AND t.ubicacion = s.ubicacion AND t.combustible = s.combustible AND t.modalidad = s.modalidad",
    "precios_rejected": "t.foto_origen = s.foto_origen AND t.combustible <=> s.combustible AND t.motivo = s.motivo",
    "extracciones": "t.foto_origen = s.foto_origen",
}

hoy = date.today()
pmin, pmax = float(P["precio_min"]), float(P["precio_max"])
ahora = datetime.now(timezone.utc).replace(tzinfo=None)


def evaluar(foto: str, fecha: date | None, texto_a: str | None, texto_b: str | None):
    """Aplica conciliación y reglas a las dos respuestas del modelo para una foto.

    Devuelve (aceptadas, rechazadas, precio_display). No llama al modelo: se usa tanto con respuestas nuevas como con
    las guardadas en `extracciones` (modo reaplicar_reglas).
    """
    resp_a, resp_b = parsear_respuesta(texto_a), parsear_respuesta(texto_b)
    base = resp_b or resp_a or {}
    disp = base.get("display_bomba") or {}
    p_display = precio_desde_display(disp.get("monto_q"), disp.get("galones"))
    ubicacion = normalizar_ubicacion(base.get("estacion"), base.get("ubicacion"))
    modalidad = normalizar_modalidad(base.get("modalidad"))

    lect_a, lect_b = lecturas_por_combustible(resp_a), lecturas_por_combustible(resp_b)
    if not lect_a and not lect_b:
        return [], [(foto, None, None, "foto_sin_precios", ahora)], p_display

    aceptadas, rechazadas, finales = [], [], {}
    for comb in sorted(set(lect_a) | set(lect_b)):
        precio, metodo = conciliar(lect_a.get(comb), lect_b.get(comb), p_display)
        motivo = (motivo_rechazo(fecha, comb, precio, hoy, pmin, pmax, anio_de_ruta(foto))
                  if precio is not None else metodo)
        if motivo:
            rechazadas.append((foto, comb, precio, motivo, ahora))
        else:
            finales[comb] = (precio, metodo)
    if orden_incoherente({c: v[0] for c, v in finales.items()}):
        for comb in ("super", "regular"):
            precio, _ = finales.pop(comb)
            rechazadas.append((foto, comb, precio, "super_menor_que_regular", ahora))
    for comb, (precio, metodo) in finales.items():
        aceptadas.append((fecha, comb, Decimal(str(precio)), modalidad, ubicacion, foto, metodo, ahora))
    return aceptadas, rechazadas, p_display

# COMMAND ----------

def leer_origen():
    o = P["origen"]
    if o.startswith(("s3://", "abfss://", "gs://", "/Volumes/")):
        df = (spark.read.format("delta").load(o) if DeltaTable.isDeltaTable(spark, o)
              else spark.read.format("binaryFile").option("recursiveFileLookup", "true").load(o))
    else:
        df = spark.table(o)
    return df.filter(F.lower(F.regexp_extract("path", r"\.([^.]+)$", 1)).isin("heic", "jpg", "jpeg", "png"))

pendientes = []
if P["modo"] != "reaplicar_reglas":
    fotos = leer_origen()
    total_origen = fotos.count()
    if P["modo"] == "incremental" and DeltaTable.isDeltaTable(spark, RUTA["extracciones"]):
        hechas = spark.read.format("delta").load(RUTA["extracciones"]).select(F.col("foto_origen").alias("path")).distinct()
        fotos = fotos.join(hechas, "path", "left_anti")
    fotos = fotos.orderBy("path")
    if int(P["limite_fotos"]) > 0:
        fotos = fotos.limit(int(P["limite_fotos"]))
    pendientes = fotos.select("path", "content").collect()
    print(f"Fotos en origen: {total_origen} · por enviar al modelo: {len(pendientes)}")

# COMMAND ----------

aceptadas, rechazadas, extracciones = [], [], []

if P["modo"] == "reaplicar_reglas":
    if not DeltaTable.isDeltaTable(spark, RUTA["extracciones"]):
        raise RuntimeError("No hay extracciones guardadas: ejecute primero en modo incremental")
    guardadas = spark.read.format("delta").load(RUTA["extracciones"]).collect()
    for e in guardadas:
        a, r, _ = evaluar(e.foto_origen, e.fecha, e.respuesta_a, e.respuesta_b)
        aceptadas += a
        rechazadas += r
    # Conservar los errores de extracción de fotos que nunca llegaron a `extracciones` (se reintentan en incremental).
    if DeltaTable.isDeltaTable(spark, RUTA["precios_rejected"]):
        con_extraccion = {e.foto_origen for e in guardadas}
        rechazadas += [tuple(x) for x in spark.read.format("delta").load(RUTA["precios_rejected"])
                       .filter(F.col("motivo").startswith("error_extraccion")).collect()
                       if x.foto_origen not in con_extraccion]
    print(f"Reglas reaplicadas a {len(guardadas)} fotos guardadas (sin llamar al modelo)")
else:
    import pillow_heif
    from PIL import Image
    from databricks.sdk import WorkspaceClient

    pillow_heif.register_heif_opener()
    cliente = WorkspaceClient().serving_endpoints.get_open_ai_client()

    PROMPT = """La imagen es una foto tomada en una gasolinera de Guatemala (bomba, rótulo o tabla de precios).
Lee cada visor de precio por galón con cuidado, dígito por dígito. Los visores LCD de 7 segmentos confunden
fácilmente 1 con 7 y 2 con 3: revisa cada segmento. Devuelve SOLO JSON con esta forma:
{"estacion": str|null, "ubicacion": str|null, "modalidad": "autoservicio"|"servicio completo"|null,
 "precios": [{"nombre_en_rotulo": str, "combustible": "super"|"regular"|"diesel"|"otro", "precio_q_galon": number|null}],
 "display_bomba": {"monto_q": number|null, "galones": number|null}}
display_bomba es el total de la venta en curso (quetzales y galones) si la foto lo muestra.
Si un dígito no se distingue, usa null. No inventes valores."""

    def fecha_foto(img) -> tuple[date | None, str]:
        """Fecha de captura (EXIF). modificationTime NO sirve: es cuando se subió el archivo a S3."""
        exif = img.getexif()
        crudo = exif.get_ifd(0x8769).get(36867) or exif.get(306)
        if crudo:
            try:
                return datetime.strptime(str(crudo), "%Y:%m:%d %H:%M:%S").date(), "exif"
            except ValueError:
                pass
        return None, "sin_exif"

    def a_jpeg_b64(img, lado: int) -> str:
        copia = img.copy()
        copia.thumbnail((lado, lado))
        buf = io.BytesIO()
        copia.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode()

    def preguntar(b64: str) -> str:
        r = cliente.chat.completions.create(
            model=P["modelo"], temperature=0, max_tokens=700,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}])
        return r.choices[0].message.content

    for i, fila in enumerate(pendientes, 1):
        try:
            img = Image.open(io.BytesIO(bytes(fila.content)))
            fecha, fuente_fecha = fecha_foto(img)
            img = img.convert("RGB")
            texto_a = preguntar(a_jpeg_b64(img, int(P["lado_a"])))
            texto_b = preguntar(a_jpeg_b64(img, int(P["lado_b"])))
        except Exception as exc:  # foto corrupta o endpoint caído: queda registrada y se reintenta en la próxima corrida
            rechazadas.append((fila.path, None, None, f"error_extraccion: {str(exc)[:200]}", ahora))
            continue
        a, r, p_display = evaluar(fila.path, fecha, texto_a, texto_b)
        aceptadas += a
        rechazadas += r
        extracciones.append((fila.path, fecha, fuente_fecha, texto_a, texto_b, p_display, ahora))
        print(f"[{i}/{len(pendientes)}] {fila.path.split('/')[-1]}: {len(a)} aceptadas")

# COMMAND ----------

def guardar(nombre: str, filas: list, reemplazar: bool) -> None:
    df = spark.createDataFrame(filas, ESQUEMAS[nombre]).dropDuplicates(LLAVES[nombre])
    if reemplazar or not DeltaTable.isDeltaTable(spark, RUTA[nombre]):
        df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(RUTA[nombre])
    else:
        DeltaTable.forPath(spark, RUTA[nombre]).alias("t").merge(df.alias("s"), CONDICION[nombre]) \
            .whenNotMatchedInsertAll().execute()

def copiar_a_catalogo(nombre: str) -> None:
    """Copia el Delta de S3 a la tabla administrada del equipo (no requiere CREATE EXTERNAL TABLE)."""
    vista = f"_equipo7_silver_{nombre}_source"
    spark.read.format("delta").load(RUTA[nombre]).createOrReplaceTempView(vista)
    try:
        spark.sql(f"CREATE OR REPLACE TABLE {TABLA[nombre]} USING DELTA AS SELECT * FROM {vista}")
    finally:
        spark.catalog.dropTempView(vista)

if P["escribir"] == "si":
    reemplazar = P["modo"] != "incremental"
    if reemplazar and not aceptadas:
        raise RuntimeError("La corrida no produjo precios válidos; no se reemplazaron las tablas de Plata")
    guardar("precios", aceptadas, reemplazar)
    guardar("precios_rejected", rechazadas, reemplazar)
    if P["modo"] != "reaplicar_reglas":
        # extracciones va al final: si algo falla antes, las fotos se vuelven a procesar en la siguiente corrida.
        guardar("extracciones", extracciones, P["modo"] == "reprocesar_todo")
    for nombre in NOMBRES:
        if DeltaTable.isDeltaTable(spark, RUTA[nombre]):
            copiar_a_catalogo(nombre)
    spark.sql(f"COMMENT ON TABLE {TABLA['precios']} IS 'Precios limpios por fecha, ubicación, combustible y modalidad, extraídos de las fotos de Bronce'")
    spark.sql(f"COMMENT ON TABLE {TABLA['precios_rejected']} IS 'Lecturas o fotos que no pasaron las reglas de calidad, con el motivo'")
    spark.sql(f"COMMENT ON TABLE {TABLA['extracciones']} IS 'Respuestas crudas del modelo de visión por foto (auditoría y reaplicación de reglas)'")
else:
    print("escribir = no → no se escribió ninguna tabla")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Resumen de la ejecución

# COMMAND ----------

from collections import Counter

print(f"Modo: {P['modo']} · lecturas aceptadas: {len(aceptadas)} · rechazadas: {len(rechazadas)}")
for motivo, n in Counter(r[3].split(':')[0] for r in rechazadas).most_common():
    print(f"  {motivo}: {n}")

if P["escribir"] == "si":
    leer = lambda n: spark.read.format("delta").load(RUTA[n])
    fotos_total = leer("extracciones").select("foto_origen").distinct()
    fotos_ok = leer("precios").select("foto_origen").distinct()
    n_total, n_ok = fotos_total.count(), fotos_ok.count()
    print(f"\nFotos procesadas: {n_total} · con al menos un precio válido: {n_ok} · rechazadas por completo: {n_total - n_ok}")
    print(f"Lecturas → válidas: {leer('precios').count()} · rechazadas: {leer('precios_rejected').count()}")

    # Fotos rechazadas por completo y el motivo principal de cada una
    display(fotos_total.join(fotos_ok, "foto_origen", "left_anti")
            .join(leer("precios_rejected").withColumn("motivo", F.split("motivo", ":")[0]), "foto_origen", "left")
            .groupBy("motivo").agg(F.countDistinct("foto_origen").alias("fotos")).orderBy(F.desc("fotos")))
    # Lecturas rechazadas por motivo
    display(leer("precios_rejected").withColumn("motivo", F.split("motivo", ":")[0])
            .groupBy("motivo").count().orderBy(F.desc("count")))
    display(leer("precios").groupBy("metodo_validacion").count())
    display(leer("precios").groupBy(F.year("fecha").alias("anio"), "combustible")
            .agg(F.count("*").alias("n"), F.min("precio_q_galon").alias("min"), F.max("precio_q_galon").alias("max"))
            .orderBy("anio", "combustible"))

# COMMAND ----------

# Resumen para quien llame este notebook como tarea del Job. Va en su propia celda porque
# dbutils.notebook.exit oculta la salida de la celda donde se ejecuta.
dbutils.notebook.exit(json.dumps({"modo": P["modo"], "aceptadas": len(aceptadas), "rechazadas": len(rechazadas),
                                  "fotos_enviadas_al_modelo": len(pendientes)}))
