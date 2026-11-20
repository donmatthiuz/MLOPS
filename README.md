# Gasolina GT  Proyecto

Proyecto de extracción de precios desde fotografías y preparación de datos Bronce → Plata → Oro. El origen se selecciona en `.env`: carpeta local para desarrollar ahora; rutas de external locations de Unity Catalog cuando se despliegue en Databricks.

## Estructura

- `pipelines/01_bronze.py`, `02_silver.py`, `03_gold.py`: entradas por capa.
- `src/gasolina_gt/`: OCR, preparación de datos, modelo local y utilidades compartidas.
- `api/app/main.py`, `api/Dockerfile` y `frontend/`: API HTTP, interfaz React y entorno aislado.
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
```

`DATA_SOURCE=local` lee las fotos de `LOCAL_DATA_DIR`. Los archivos generados se guardan en `LOCAL_BRONZE_DIR`, `LOCAL_SILVER_DIR`, `LOCAL_GOLD_DIR`, `LOCAL_MODELS_DIR` y `LOCAL_REPORTS_DIR`. Todas estas rutas se pueden cambiar en `.env`; las relativas se resuelven desde la raíz del repositorio. La calibración OCR viaja con el paquete y no depende de la carpeta de fotos. El Gold local actual incluye una serie **sintética** para poder probar el modelo con pocas fotos; sus resultados no son validación con datos reales.

El `compose.yaml` de la raíz despliega la API del Droplet y requiere `api/.env`; el flujo local de OCR y entrenamiento se ejecuta con los comandos anteriores.

## Databricks

Para pruebas manuales, use `DATA_SOURCE=databricks` y las rutas del equipo en un `.env` **local al Git folder**:

```dotenv
BRONZE_INPUT_URI=s3://bucket-bronce/img/
BRONZE_OUTPUT_URI=s3://bucket-bronce/
SILVER_OUTPUT_URI=s3://bucket-plata/
GOLD_OUTPUT_URI=s3://bucket-oro/prefijo-completo/
DATABRICKS_CATALOG=workspace
```

Las imágenes se leen de `img/`. `BRONZE_INPUT_URI` puede apuntar al bucket o directamente a `img/`. Bronce y Plata escriben bajo `equipo7/`. Para Oro, `GOLD_OUTPUT_URI` debe contener la ruta completa del prefijo de salida: el pipeline no le agrega una carpeta de equipo. Por ejemplo, con `GOLD_OUTPUT_URI=s3://bucket-oro/prefijo-completo/`, la tabla semanal queda en `s3://bucket-oro/prefijo-completo/precio_semanal`. Después de escribir cada capa, el pipeline crea o actualiza tablas administradas en `workspace.equipo7`, como `bronze_fotos_precios`, `silver_precios` y `gold_precio_semanal`. Estas tablas son copias adicionales de los Delta de S3; se pueden consultar en Catalog Explorer y ocupan almacenamiento administrado por Unity Catalog.

Según el enunciado del curso, S3 guarda físicamente cada capa: Bronce recibe las fotos y conserva su contenido binario, Plata guarda precios limpios y rechazos, y Oro guarda indicadores y resultados para la API del Droplet. El workspace aloja el Git folder, el cómputo interactivo, el Job, los experimentos de MLflow y las tablas administradas del esquema del equipo. Este esquema usa `CREATE TABLE` y no requiere `CREATE EXTERNAL TABLE` sobre las external locations; los datos de S3 permanecen como fuente para cada capa y para la futura API.

Las rutas son **prefijos autorizados mediante external locations**, no nombres de credenciales. El Job usa **parámetros del Job** que Databricks pasa a los notebooks; no presupone que exista ese `.env`. Se configura en **Jobs & Pipelines** con tres tareas de notebook Bronce → Plata → Oro, entorno serverless y experimento `/Shared/equipo7-gasolina`. Tras comprobar `Run now`, se activa la programación y se exporta la definición real a `pipelines/job.json` para la entrega. Los pasos y valores que hay que configurar están en [`docs/databricks_job.md`](docs/databricks_job.md).

Plata usa el notebook de visión `02_silver.py`; **no use `databricks_layers.silver()`**, que ahora se detiene explícitamente para proteger las tablas. Oro calcula indicadores, predicciones y métricas y registra una ejecución en MLflow. Si hay pocos ejemplos de semanas consecutivas, usa y registra la línea base sin crear un artefacto de modelo entrenado.

### Reprocesar Plata y Oro

En `pipelines/02_silver.py`, use el widget `modo=incremental` para fotos nuevas, `modo=reaplicar_reglas` para recalcular Plata desde las extracciones ya guardadas, `modo=refinar_referencias` para releer con recortes solo fotos con referencia o lectura fallida, o `modo=reprocesar_todo` para volver a enviar todas las fotos al modelo de visión. Después ejecute `pipelines/03_gold.py`. No hace falta repetir Bronce si las imágenes no cambiaron. El Job normal usa `incremental` y recalcula Oro en cada ejecución.

Plata puede usar el promedio mensual del MEM de Ciudad Capital como desempate o respaldo (`usar_referencia=si`); los precios están en `docs/plata/precios_mem_capital_mensual.csv`. Se asume que todas las fotos son de Ciudad Capital y que las de modalidad desconocida son de autoservicio. Consulte [la guía de Plata](docs/plata/README.md) para aplicar la regla a las extracciones existentes y ver sus límites.

## API en DigitalOcean

La API FastAPI lee directamente los Delta del prefijo Oro en S3 con `deltalake`. Docker aísla sus dependencias y `restart: unless-stopped` la mantiene en marcha al cerrar SSH. El contenedor solo consulta S3; no escribe tablas ni necesita acceso a Bronce o Plata. El `.env` del servidor, excluido de Git, contiene `GOLD_OUTPUT_URI`, `API_PORT` y las credenciales AWS de solo lectura (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`); `api/.env.example` es la plantilla. La guía paso a paso está en [`docs/api_despliegue.md`](docs/api_despliegue.md). El puerto externo predeterminado es `8007`; ajuste `API_PORT` si el curso asignó otro `80XX`.

El frontend React se compila dentro de `api/Dockerfile` y FastAPI lo sirve en `/` por el mismo puerto. Consulta precios, histórico, pronósticos y métricas usando los endpoints existentes; `/docs` sigue disponible para Swagger. La interfaz informa cuando Oro no está disponible y no sustituye datos reales por ejemplos.

En el Droplet, dentro de `/home/equipo-07/`:

```bash
git clone -b proyecto1 https://github.com/donmatthiuz/MLOPS.git
cd MLOPS
cp api/.env.example api/.env
chmod 600 api/.env
# Editar api/.env: GOLD_OUTPUT_URI, API_PORT y llaves AWS de solo lectura.
docker compose --env-file api/.env up -d --build
docker compose --env-file api/.env ps
```

Si el repositorio ya está clonado, use `git pull` desde la rama `proyecto1` y repita `docker compose --env-file api/.env up -d --build`. El `.env` se conserva en el servidor y no se copia a la imagen. `--env-file` permite que Compose lea `API_PORT`; `env_file` pasa `GOLD_OUTPUT_URI` al contenedor. La región S3 `us-east-2` se configura en Compose. El contenedor recibe el acceso de solo lectura a S3 por las llaves AWS de `api/.env`; el acceso configurado para el usuario Linux del Droplet (`~/.aws`) no se hereda. Sin esas llaves, `/health` responde 503. Para ver un fallo: `docker compose --env-file api/.env logs --tail=100 api`.

Endpoints: `GET /health`, `/precios/actual`, `/precios?combustible=super&desde=2026-10-01&hasta=2026-11-30&limit=100&offset=0`, `/prediccion?combustible=super`, `/modelo/metricas` y Swagger en `/docs`. `/health` responde 503 si no puede abrir Oro. Los demás endpoints devuelven 503 si S3 no está disponible; los pronósticos o métricas ausentes devuelven 404. La API muestra `probabilidad: null` cuando Oro usa la línea base. Las predicciones conservan la fecha de la última semana disponible para cada combustible; no se presentan como actuales si faltan fotos nuevas.

Desde otra computadora, pruebe `API_URL=http://<ip>:<puerto> sh tests/consultas_api.sh`. La imagen y los endpoints se probaron localmente contra un S3 de prueba; el despliegue real y el acceso HTTP externo aún deben comprobarse en el Droplet.

Para desarrollar solo la interfaz: ejecute `npm ci` y `npm run dev` dentro de `frontend/`, con la API escuchando en `localhost:8007`. Vite abre `localhost:5173` y pasa las consultas a la API. Para apuntar a otro puerto, defina `VITE_API_PROXY_TARGET` antes de iniciar Vite.

## Documentación

- [Enunciado del proyecto](docs/enunciado_proyecto.pdf)
- [Entendimiento de negocio](docs/business-understanding-consolidado.pdf)
- [Diagrama de arquitectura](docs/arquitectura.png) y [fuente editable](docs/arquitectura.drawio)
- [Estado del informe técnico](docs/informe.md)
- [Material de presentación](presentacion/README.md)

## Pruebas

```bash
.venv/bin/python -m pytest -q
```
