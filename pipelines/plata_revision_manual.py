# Databricks notebook source
# MAGIC %md
# MAGIC # Plata · Revisión manual de la extracción
# MAGIC
# MAGIC El enunciado pide revisar **a mano al menos 20 fotos** y reportar el porcentaje de precios extraídos correctamente.
# MAGIC
# MAGIC 1. **Galería**: muestra cada foto de la muestra junto a los precios que guardó Plata (aceptados y rechazados).
# MAGIC 2. **Llenar** `docs/plata/revision_manual.csv` (en el repo): por cada foto y combustible, el precio que se ve en la foto
# MAGIC    (`precio_real`). Dejar vacío si ese combustible no aparece en la foto.
# MAGIC 3. **Exactitud**: la última celda compara el CSV contra `silver.precios` y guarda el resultado en `<silver_uri>/revision_manual`.
# MAGIC
# MAGIC Un precio cuenta como correcto si Plata lo aceptó con el mismo valor (±Q0.01). Si la foto lo muestra pero Plata lo
# MAGIC rechazó o no lo leyó, cuenta como **no extraído**.

# COMMAND ----------

# MAGIC %pip install -q pillow-heif
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("silver_uri", "s3://cc3105-ag-869227452861-us-east-2-an/equipo7", "Prefijo S3 de Plata")
dbutils.widgets.text("catalogo", "workspace")
dbutils.widgets.text("esquema", "silver")
dbutils.widgets.text("n_fotos", "24", "Fotos en la muestra")
dbutils.widgets.text("csv_revision", "../docs/plata/revision_manual.csv", "CSV con precio_real (ruta relativa al notebook)")
CAT, ESQ = dbutils.widgets.get("catalogo"), dbutils.widgets.get("esquema")
N = int(dbutils.widgets.get("n_fotos"))
T = lambda n: f"{CAT}.{ESQ}.{n}"
URI = dbutils.widgets.get("silver_uri").rstrip("/")
leer = lambda n: spark.read.format("delta").load(f"{URI}/{n}")  # por ruta: no depende de que las tablas estén registradas

# COMMAND ----------

from pyspark.sql import functions as F

# Muestra determinista y repartida entre carpetas (2023, 2024, 2025 y fotos recientes): una de cada k fotos.
fotos = (leer("extracciones").select("foto_origen", "fecha").distinct()
         .withColumn("n", F.row_number().over(__import__("pyspark.sql.window", fromlist=["Window"]).Window.orderBy("foto_origen"))))
total = fotos.count()
paso = max(total // N, 1)
muestra = fotos.filter((F.col("n") - 1) % paso == 0).limit(N).orderBy("foto_origen")
display(muestra)

# COMMAND ----------

import base64, io
import pillow_heif
from PIL import Image

pillow_heif.register_heif_opener()
aceptados = leer("precios").select("foto_origen", "combustible", "precio_q_galon", "metodo_validacion")
rechazados = leer("precios_rejected").select("foto_origen", "combustible", "precio_q_galon", "motivo")
rutas = [r.foto_origen for r in muestra.collect()]
contenido = {r.path: bytes(r.content) for r in spark.read.format("binaryFile").load(rutas).collect()}

html = []
for ruta in rutas:
    img = Image.open(io.BytesIO(contenido[ruta])).convert("RGB")
    img.thumbnail((1400, 1400))
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
    ok = [f"{r.combustible}: Q{r.precio_q_galon} ({r.metodo_validacion})" for r in aceptados.filter(F.col("foto_origen") == ruta).collect()]
    ko = [f"{r.combustible or '—'}: {r.precio_q_galon or '—'} ({r.motivo})" for r in rechazados.filter(F.col("foto_origen") == ruta).collect()]
    html.append(f"<div style='margin:16px 0;border-top:1px solid #888;padding-top:8px'><b>{ruta.split('/img/')[-1]}</b>"
                f"<br>Aceptados: {', '.join(ok) or 'ninguno'}<br>Rechazados: {', '.join(ko) or 'ninguno'}<br>"
                f"<img src='data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}' width='900'></div>")
displayHTML("".join(html))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Exactitud (ejecutar después de llenar el CSV)

# COMMAND ----------

import os
import pandas as pd

ruta_csv = os.path.normpath(os.path.join(os.getcwd(), dbutils.widgets.get("csv_revision")))
rev = pd.read_csv(ruta_csv, dtype={"foto": str, "combustible": str})
rev = rev[rev["precio_real"].notna()]
if rev.empty:
    dbutils.notebook.exit("El CSV todavía no tiene precio_real llenado.")

extraidos = aceptados.toPandas()
extraidos["foto"] = extraidos["foto_origen"].str.split("/img/").str[-1]
extraidos["precio_q_galon"] = extraidos["precio_q_galon"].astype(float)
cmp = rev.merge(extraidos[["foto", "combustible", "precio_q_galon"]], on=["foto", "combustible"], how="left")
cmp["correcto"] = (cmp["precio_q_galon"] - cmp["precio_real"].astype(float)).abs() < 0.011
cmp["resultado"] = cmp.apply(lambda r: "correcto" if r.correcto else ("no_extraido" if pd.isna(r.precio_q_galon) else "valor_incorrecto"), axis=1)

exactitud = cmp["correcto"].mean() * 100
print(f"Fotos revisadas: {cmp['foto'].nunique()} · precios visibles: {len(cmp)}")
print(f"Exactitud de extracción: {exactitud:.1f}%")
print(cmp["resultado"].value_counts().to_string())

resultado = spark.createDataFrame(cmp.astype({"precio_q_galon": "float64", "precio_real": "float64"}))
resultado.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{URI}/revision_manual")
display(leer("revision_manual"))
