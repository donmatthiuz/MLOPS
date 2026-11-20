# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Plata — extracción de precios y reglas de calidad
# MAGIC
# MAGIC Convierte cada foto de Bronce en filas limpias de precio (una por fecha, ubicación, combustible y modalidad).
# MAGIC
# MAGIC 1. **Extracción**: un modelo de visión servido en Databricks lee cada foto dos veces; si hace falta,
# MAGIC    añade dos lecturas enfocadas con recortes de los visores.
# MAGIC 2. **Conciliación**: un precio se acepta si dos lecturas coinciden, o si una coincide con el precio que se deduce
# MAGIC    del display de la bomba (monto ÷ galones).
# MAGIC    Si no se puede conciliar, se usa el promedio mensual del MEM para Ciudad Capital como desempate o respaldo,
# MAGIC    dejando el método registrado en `metodo_validacion`. Se supone que todas las fotos son de Ciudad Capital.
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
# MAGIC - `refinar_referencias`: relee con recortes solo fotos que usan referencia y reconstruye Plata desde las extracciones.
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
dbutils.widgets.dropdown("modo", "incremental", ["incremental", "reaplicar_reglas", "reprocesar_todo", "refinar_referencias"], "Modo")
dbutils.widgets.text("modelo", "databricks-llama-4-maverick", "Endpoint del modelo de visión")
dbutils.widgets.text("lado_a", "1600", "Resolución lectura A (px)")
dbutils.widgets.text("lado_b", "2560", "Resolución lectura B (px)")
dbutils.widgets.text("precio_min", "15", "Precio mínimo válido (Q/gal)")
dbutils.widgets.text("precio_max", "60", "Precio máximo válido (Q/gal)")
dbutils.widgets.text("limite_fotos", "0", "Máximo de fotos nuevas (0 = todas)")
dbutils.widgets.dropdown("escribir", "si", ["si", "no"], "¿Escribir tablas?")
dbutils.widgets.dropdown("usar_referencia", "si", ["si", "no"], "¿Usar referencia mensual MEM?")
dbutils.widgets.text("referencia_csv", "", "CSV mensual MEM (vacío = archivo del Git folder)")

P = {k: dbutils.widgets.get(k) for k in
     ("origen", "silver_uri", "catalogo", "esquema", "modo", "modelo", "lado_a", "lado_b",
     "precio_min", "precio_max", "limite_fotos", "escribir", "usar_referencia", "referencia_csv")}
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
from pathlib import Path

# Las reglas viven en pipelines/plata_reglas.py (probadas con pytest).
try:
    _nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    ruta_notebook = Path(_nb if _nb.startswith("/Workspace/") else "/Workspace" + _nb)
    for _d in (os.getcwd(), str(ruta_notebook.parent)):
        if _d not in sys.path:
            sys.path.insert(0, _d)
    from plata_reglas import (ajustar_orden_con_referencia, anio_de_ruta, conciliar_con_enfoque, lecturas_por_combustible,
                              motivo_rechazo, normalizar_modalidad, normalizar_ubicacion, orden_incoherente,
                              parsear_respuesta, precio_desde_display)
    from plata_referencia import buscar_referencia, cargar_referencias
    from plata_vision import vistas_enfoque
except ImportError as exc:
    raise ImportError("No se encontraron plata_reglas.py y plata_referencia.py junto a este notebook (Git folder).") from exc

if P["usar_referencia"] == "si":
    repo = ruta_notebook.parent.parent
    ruta_referencia = (Path(P["referencia_csv"]) if P["referencia_csv"].strip()
                       else repo / "docs/plata/precios_mem_capital_mensual.csv")
    referencias = cargar_referencias(ruta_referencia)
    print(f"Referencia MEM Ciudad Capital: {len(referencias)} precios de {ruta_referencia}")
else:
    referencias = {}

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
        T.StructField("metodo_validacion", T.StringType(), metadata={"comment": "consenso, display_bomba o referencia_... (precio asistido o sustituido por promedio mensual MEM)"}),
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
        T.StructField("respuesta_enfoque_a", T.StringType(), metadata={"comment": "Lectura enfocada de visores, recortes originales"}),
        T.StructField("respuesta_enfoque_b", T.StringType(), metadata={"comment": "Lectura enfocada de visores, recortes con contraste"}),
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


def evaluar(foto: str, fecha: date | None, texto_a: str | None, texto_b: str | None,
            texto_foco_a: str | None = None, texto_foco_b: str | None = None):
    """Aplica conciliación y reglas a las dos respuestas del modelo para una foto.

    Devuelve (aceptadas, rechazadas, precio_display). No llama al modelo: se usa tanto con respuestas nuevas como con
    las guardadas en `extracciones` (modo reaplicar_reglas).
    """
    resp_a, resp_b = parsear_respuesta(texto_a), parsear_respuesta(texto_b)
    base = resp_b or resp_a or {}
    disp_a = (resp_a or {}).get("display_bomba") or {}
    disp_b = (resp_b or {}).get("display_bomba") or {}
    p_display_a = precio_desde_display(disp_a.get("monto_q"), disp_a.get("galones"))
    p_display_b = precio_desde_display(disp_b.get("monto_q"), disp_b.get("galones"))
    p_display = (None if p_display_a is not None and p_display_b is not None
                 and abs(p_display_a - p_display_b) > 0.01
                 else p_display_b if p_display_b is not None else p_display_a)
    ubicacion = normalizar_ubicacion(base.get("estacion"), base.get("ubicacion"))
    modalidad = normalizar_modalidad(base.get("modalidad"))
    if modalidad == "no_especificada":
        modalidad = normalizar_modalidad((resp_a or {}).get("modalidad"))

    lect_a, lect_b = lecturas_por_combustible(resp_a), lecturas_por_combustible(resp_b)
    lect_fa = lecturas_por_combustible(parsear_respuesta(texto_foco_a))
    lect_fb = lecturas_por_combustible(parsear_respuesta(texto_foco_b))
    if not (lect_a or lect_b or lect_fa or lect_fb):
        return [], [(foto, None, None, "foto_sin_precios", ahora)], p_display

    aceptadas, rechazadas, finales = [], [], {}
    ref_valores = {}
    for comb in sorted(set(lect_a) | set(lect_b) | set(lect_fa) | set(lect_fb)):
        ref, supuesto_auto = buscar_referencia(referencias, fecha, modalidad, comb)
        ref_valores[comb] = ref
        precio, metodo = conciliar_con_enfoque(lect_a.get(comb), lect_b.get(comb),
                                              lect_fa.get(comb), lect_fb.get(comb), p_display, ref)
        if supuesto_auto and metodo.startswith("referencia_"):
            metodo += "_autoservicio_supuesto"
        motivo = (motivo_rechazo(fecha, comb, precio, hoy, pmin, pmax, anio_de_ruta(foto))
                  if precio is not None else metodo)
        if motivo:
            rechazadas.append((foto, comb, precio, motivo, ahora))
        else:
            finales[comb] = (precio, metodo)
    if orden_incoherente({c: v[0] for c, v in finales.items()}):
        ajustadas = ajustar_orden_con_referencia(finales, ref_valores)
        if ajustadas is None:
            for comb in ("super", "regular"):
                precio, _ = finales.pop(comb)
                rechazadas.append((foto, comb, precio, "super_menor_que_regular", ahora))
        else:
            finales = ajustadas
            if modalidad == "no_especificada":
                finales = {comb: (precio, metodo + "_autoservicio_supuesto"
                                  if metodo == "referencia_mensual_orden" else metodo)
                           for comb, (precio, metodo) in finales.items()}
    for comb, (precio, _) in list(finales.items()):
        motivo = motivo_rechazo(fecha, comb, precio, hoy, pmin, pmax, anio_de_ruta(foto))
        if motivo:
            finales.pop(comb)
            rechazadas.append((foto, comb, precio, motivo, ahora))
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
anteriores = {}
n_referencia_anterior = None
if P["modo"] == "refinar_referencias":
    if not all(DeltaTable.isDeltaTable(spark, RUTA[n]) for n in ("precios", "extracciones")):
        raise RuntimeError("Primero ejecute Plata y guarde precios y extracciones")
    anteriores = {e.foto_origen: e for e in spark.read.format("delta").load(RUTA["extracciones"]).collect()}
    precios_previos = spark.read.format("delta").load(RUTA["precios"])
    n_referencia_anterior = precios_previos.filter(F.col("metodo_validacion").startswith("referencia_")).count()
    rutas_ref = (precios_previos
                 .filter(F.col("metodo_validacion").startswith("referencia_"))
                 .select(F.col("foto_origen").alias("path")))
    if DeltaTable.isDeltaTable(spark, RUTA["precios_rejected"]):
        pendientes_lectura = (spark.read.format("delta").load(RUTA["precios_rejected"])
                              .filter(F.col("motivo").isin("lecturas_inconsistentes", "sin_lectura",
                                                            "foto_sin_precios", "super_menor_que_regular"))
                              .select(F.col("foto_origen").alias("path")))
        rutas_ref = rutas_ref.union(pendientes_lectura)
    rutas_ref = rutas_ref.distinct()
    fotos = leer_origen().join(rutas_ref, "path", "inner").orderBy("path")
    if int(P["limite_fotos"]) > 0:
        fotos = fotos.limit(int(P["limite_fotos"]))
    pendientes = fotos.select("path", "content").collect()
    print(f"Fotos con referencia o lectura fallida por refinar: {rutas_ref.count()} · disponibles: {len(pendientes)}")
elif P["modo"] != "reaplicar_reglas":
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
        a, r, _ = evaluar(e.foto_origen, e.fecha, e.respuesta_a, e.respuesta_b,
                          e.asDict().get("respuesta_enfoque_a"), e.asDict().get("respuesta_enfoque_b"))
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
    from PIL import Image, ImageOps
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
    PROMPT_ENFOQUE = """La primera imagen muestra la bomba completa. Las cuatro siguientes son recortes verticales
solapados de izquierda a derecha; algunos repiten el mismo visor. Lee SOLO precios por galón visibles en los visores
y asocia cada número con el nombre de combustible impreso directamente debajo. No uses conocimiento de precios
de mercado ni infieras un dígito borroso. Responde SOLO JSON con la misma estructura de la lectura original:
{"estacion": str|null, "ubicacion": str|null, "modalidad": "autoservicio"|"servicio completo"|null,
 "precios": [{"nombre_en_rotulo": str, "combustible": "super"|"regular"|"diesel"|"otro", "precio_q_galon": number|null}],
 "display_bomba": {"monto_q": null, "galones": null}}"""

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

    def preguntar_enfoque(img, contraste: bool) -> str:
        contenido = [{"type": "text", "text": PROMPT_ENFOQUE}]
        for vista in vistas_enfoque(img, contraste=contraste):
            contenido.append({"type": "image_url", "image_url": {
                "url": f"data:image/jpeg;base64,{a_jpeg_b64(vista, 1600)}"}})
        r = cliente.chat.completions.create(
            model=P["modelo"], temperature=0, max_tokens=700,
            messages=[{"role": "user", "content": contenido}])
        return r.choices[0].message.content

    def intentar_enfoque(img, contraste: bool, foto: str) -> str | None:
        try:
            return preguntar_enfoque(img, contraste)
        except Exception as exc:
            print(f"Lectura enfocada falló para {foto} (contraste={contraste}): {str(exc)[:160]}")
            return None

    for i, fila in enumerate(pendientes, 1):
        try:
            img = Image.open(io.BytesIO(bytes(fila.content)))
            if P["modo"] == "refinar_referencias":
                e = anteriores[fila.path]
                fecha, fuente_fecha = e.fecha, e.fuente_fecha
                texto_a, texto_b = e.respuesta_a, e.respuesta_b
            else:
                fecha, fuente_fecha = fecha_foto(img)
            img = ImageOps.exif_transpose(img).convert("RGB")
            if P["modo"] != "refinar_referencias":
                texto_a = preguntar(a_jpeg_b64(img, int(P["lado_a"])))
                texto_b = preguntar(a_jpeg_b64(img, int(P["lado_b"])))
            a0, r0, _ = evaluar(fila.path, fecha, texto_a, texto_b)
            necesita_enfoque = (P["modo"] == "refinar_referencias" or
                                any(row[6].startswith("referencia_") for row in a0) or
                                any(row[3] in ("lecturas_inconsistentes", "sin_lectura",
                                               "foto_sin_precios", "super_menor_que_regular") for row in r0))
            texto_fa = intentar_enfoque(img, False, fila.path) if necesita_enfoque else None
            texto_fb = intentar_enfoque(img, True, fila.path) if necesita_enfoque else None
        except Exception as exc:  # foto corrupta o endpoint caído: queda registrada y se reintenta en la próxima corrida
            rechazadas.append((fila.path, None, None, f"error_extraccion: {str(exc)[:200]}", ahora))
            continue
        a, r, p_display = evaluar(fila.path, fecha, texto_a, texto_b, texto_fa, texto_fb)
        if P["modo"] != "refinar_referencias":
            aceptadas += a
            rechazadas += r
        extracciones.append((fila.path, fecha, fuente_fecha, texto_a, texto_b,
                             texto_fa, texto_fb, p_display, ahora))
        print(f"[{i}/{len(pendientes)}] {fila.path.split('/')[-1]}: {len(a)} aceptadas")

if P["modo"] == "refinar_referencias":
    actualizadas = {e[0]: e for e in extracciones}
    extracciones = []
    aceptadas, rechazadas = [], []
    for foto, e in anteriores.items():
        fila = actualizadas.get(foto)
        if fila is None:
            d = e.asDict()
            fila = (foto, e.fecha, e.fuente_fecha, e.respuesta_a, e.respuesta_b,
                    d.get("respuesta_enfoque_a"), d.get("respuesta_enfoque_b"), e.precio_display,
                    d["_processed_timestamp"])
        extracciones.append(fila)
        a, r, _ = evaluar(foto, fila[1], fila[3], fila[4], fila[5], fila[6])
        aceptadas += a
        rechazadas += r
    if DeltaTable.isDeltaTable(spark, RUTA["precios_rejected"]):
        rechazadas += [tuple(x) for x in spark.read.format("delta").load(RUTA["precios_rejected"])
                       .filter(F.col("motivo").startswith("error_extraccion")).collect()
                       if x.foto_origen not in anteriores]
    n_referencia_calculada = sum(row[6].startswith("referencia_") for row in aceptadas)
    print(f"Lecturas con referencia: antes={n_referencia_anterior} · recalculadas={n_referencia_calculada}")

# COMMAND ----------

def guardar(nombre: str, filas: list, reemplazar: bool) -> None:
    df = spark.createDataFrame(filas, ESQUEMAS[nombre]).dropDuplicates(LLAVES[nombre])
    if reemplazar or not DeltaTable.isDeltaTable(spark, RUTA[nombre]):
        df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(RUTA[nombre])
    else:
        if nombre == "extracciones":
            columnas = set(spark.read.format("delta").load(RUTA[nombre]).columns)
            faltantes = [c for c in ("respuesta_enfoque_a", "respuesta_enfoque_b") if c not in columnas]
            if faltantes:
                definiciones = ", ".join(f"{c} STRING" for c in faltantes)
                spark.sql(f"ALTER TABLE delta.`{RUTA[nombre]}` ADD COLUMNS ({definiciones})")
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
    if P["modo"] == "refinar_referencias":
        # Guardar primero la evidencia enfocada: si falla una escritura posterior,
        # reaplicar_reglas puede reconstruir los precios sin nuevas llamadas.
        guardar("extracciones", extracciones, True)
    guardar("precios", aceptadas, reemplazar)
    guardar("precios_rejected", rechazadas, reemplazar)
    if P["modo"] not in ("reaplicar_reglas", "refinar_referencias"):
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
    if n_referencia_anterior is not None:
        n_referencia_nueva = leer("precios").filter(F.col("metodo_validacion").startswith("referencia_")).count()
        print(f"Lecturas con referencia: antes={n_referencia_anterior} · ahora={n_referencia_nueva}")
    display(leer("precios").groupBy(F.year("fecha").alias("anio"), "combustible")
            .agg(F.count("*").alias("n"), F.min("precio_q_galon").alias("min"), F.max("precio_q_galon").alias("max"))
            .orderBy("anio", "combustible"))

# COMMAND ----------

# Resumen para quien llame este notebook como tarea del Job. Va en su propia celda porque
# dbutils.notebook.exit oculta la salida de la celda donde se ejecuta.
dbutils.notebook.exit(json.dumps({"modo": P["modo"], "aceptadas": len(aceptadas), "rechazadas": len(rechazadas),
                                  "fotos_enviadas_al_modelo": len(pendientes)}))
