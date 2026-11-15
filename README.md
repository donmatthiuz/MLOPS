# Gasolina GT  Proyecto

Proyecto de extracción de precios desde fotografías y preparación de datos Bronce → Plata → Oro. El origen se selecciona en `.env`: carpeta local para desarrollar ahora; rutas de external locations de Unity Catalog cuando se despliegue en Databricks.

## Estructura

- `pipelines/01_bronze.py`, `02_silver.py`, `03_gold.py`: entradas por capa.
- `src/gasolina_gt/`: OCR, preparación de datos, modelo local y utilidades compartidas.
- `api/app/main.py` y `api/Dockerfile`: aplicación HTTP y entorno aislado.
- `docs/`: enunciado, entendimiento de negocio, diagrama e informe técnico en elaboración.
- `presentacion/`: material del jurado cuando esté listo.
- `tests/`: pruebas de código.

## Desarrollo local

```bash
cp .env.example .env
# LOCAL_DATA_DIR=/home/donmathiuz/mlops/datos ya está configurado para este workspace.
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python pipelines/01_bronze.py
.venv/bin/python pipelines/02_silver.py
.venv/bin/python pipelines/03_gold.py
.venv/bin/gasolina-gt train --combustible regular
.venv/bin/uvicorn api.app.main:app --reload
```

`DATA_SOURCE=local` lee las fotos de `LOCAL_DATA_DIR`. Los archivos generados se guardan en `LOCAL_BRONZE_DIR`, `LOCAL_SILVER_DIR`, `LOCAL_GOLD_DIR`, `LOCAL_MODELS_DIR` y `LOCAL_REPORTS_DIR`. Todas estas rutas se pueden cambiar en `.env`; las relativas se resuelven desde la raíz del repositorio. La calibración OCR viaja con el paquete y no depende de la carpeta de fotos. El Gold local actual incluye una serie **sintética** para poder probar el modelo con pocas fotos; sus resultados no son validación con datos reales.

```bash
docker compose up --build
# API local: http://localhost:8000/health
```

Compose monta `LOCAL_DATA_DIR` en solo lectura dentro del contenedor. El Dockerfile está en `api/` para seguir la estructura de entrega.

## Databricks

Al disponer de Unity Catalog, cambie `DATA_SOURCE=databricks` y complete en el entorno del Job:

```dotenv
BRONZE_INPUT_URI=s3://bucket-bronce/img/
BRONZE_OUTPUT_URI=s3://bucket-bronce/
SILVER_OUTPUT_URI=s3://bucket-plata/
GOLD_OUTPUT_URI=s3://bucket-oro/
DATABRICKS_CATALOG=workspace
```

Las imágenes se leen de `img/`. `BRONZE_INPUT_URI` puede apuntar al bucket o directamente a `img/`. Antes de escribir, cada tarea crea si falta `equipo7/` dentro del prefijo de salida de su capa. Si la URI ya termina en `equipo7/`, se utiliza tal cual. Las capas Delta quedan en `equipo7/fotos_precios`, `equipo7/precios` y `equipo7/precio_semanal`, entre otras. Después de escribir cada capa, el pipeline crea o actualiza tablas administradas en `workspace.equipo7`, como `bronze_fotos_precios`, `silver_precios` y `gold_precio_semanal`. Estas tablas son copias adicionales de los Delta de S3; se pueden consultar en Catalog Explorer y ocupan almacenamiento administrado por Unity Catalog.

Según el enunciado del curso, S3 guarda físicamente cada capa: Bronce recibe las fotos y conserva su contenido binario, Plata guarda precios limpios y rechazos, y Oro guarda indicadores y resultados para la API del Droplet. El workspace aloja el Git folder, el cómputo interactivo, el Job, los experimentos de MLflow y las tablas administradas del esquema del equipo. Este esquema usa `CREATE TABLE` y no requiere `CREATE EXTERNAL TABLE` sobre las external locations; los datos de S3 permanecen como fuente para cada capa y para la futura API.

Las rutas son **prefijos autorizados mediante external locations**, no nombres de credenciales. El administrador debe configurar storage credentials, external locations y permisos de Unity Catalog. Instale este paquete en el cluster y ejecute las tres entradas `pipelines/01_bronze.py` → `02_silver.py` → `03_gold.py` como tareas Python del Job. Bronce lee con `binaryFile` e ingesta por ruta única; Plata extrae OCR, aplica reglas de calidad y separa rechazos; Oro genera indicadores semanales y variables en Delta. El entrenamiento y publicación de predicciones en Databricks, el Job exportado y el despliegue en el Droplet se completarán cuando existan infraestructura, fotos históricas y credenciales. No hay recursos Databricks desplegados desde este repositorio todavía.

El API actual ofrece `/health` y `/recomendacion` para el flujo local. La lectura de tablas Oro desde S3 por el Droplet, los endpoints adicionales del enunciado y la validación real del modelo siguen pendientes de la fase de despliegue. Las credenciales del Droplet deben estar solo en `api/.env`, con permisos `600` y acceso de solo lectura; nunca en Git.

## Documentación

- [Enunciado del proyecto](docs/enunciado_proyecto.pdf)
- [Entendimiento de negocio](docs/business-understanding-consolidado.pdf)
- [Diagrama de arquitectura](docs/arquitectura.png) y [fuente editable](docs/arquitectura.drawio)
- [Estado del informe técnico](docs/informe.md)
- [Material de presentación](presentacion/README.md)

## Pruebas

```bash
.venv/bin/python -m pytest -q
# o
 docker compose run --rm tests
```
