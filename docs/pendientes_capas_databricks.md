# Pendientes de las capas en Databricks

Estado revisado el 17 de noviembre de 2026. Referencia: [enunciado del proyecto](enunciado_proyecto.pdf). Las cifras provienen de las evidencias guardadas; el contenido actual de las tablas debe comprobarse en Databricks.

## Estado actual

| Capa | Ya funciona en Databricks | Pendiente |
| --- | --- | --- |
| Bronce | Lee `img/`, guarda fotos y metadatos en Delta y registra la tabla en `workspace.equipo7`. Se comprobaron 110 fotos únicas. | No hay un cambio esencial pendiente en la lógica de la capa. |
| Plata | El notebook de visión aplica reglas de calidad y deduplicación, guarda precios y rechazos en Delta y registra las tablas. Se documentaron 148 lecturas válidas y 150 rechazos después de reaplicar reglas. | Verificar el estado actual de las tablas en Databricks y comprobar la ejecución de Plata dentro del Job. |
| Oro | Genera cinco tablas, predicciones y métricas; hay evidencia de una ejecución con 15 ejemplos y registro en MLflow, usando la línea base. | Volver a correr con Plata actualizada y WTI, verificar los comentarios y completar la evidencia del Job. |

## Pendientes por capa

### Bronce

- [x] Comprobar que una segunda ejecución no duplica las fotos.
- [ ] Integrar su ejecución en el Job completo; esto es un pendiente de orquestación, no de la lógica de Bronce.
- [x] Verificación automática filas = fotos y sin duplicados; fuente complementaria WTI. Ver [docs/bronce](bronce/README.md).

### Plata

- [x] Revisar manualmente **al menos 20 fotos** y reportar los resultados: 24 fotos anotadas, 33 lecturas visibles con certeza, cobertura 39,4 % y precisión 76,5 % entre las guardadas verificables. Ver [docs/plata](plata/README.md).
- [x] Mostrar en el notebook fotos procesadas, fotos rechazadas por completo y desglose por motivo.
- [x] Extraer `modalidad` y `ubicacion` cuando aparezcan en la imagen; usar valores de ausencia cuando no se vean.
- [x] Documentar y probar `reaplicar_reglas` en Databricks; `reprocesar_todo` está implementado para volver a llamar al modelo de visión.
- [ ] Ejecutar el notebook de Plata como tarea del Job y verificar de nuevo sus tablas administradas y Delta de S3.

### Oro

Implementado y probado localmente (`pytest`, datos sintéticos solo en `tests/`) y ejecutado una vez en Databricks con la línea base. Ver [docs/oro](oro/README.md) y el [contrato para la API](oro/contrato_api.md).

- [x] Calcular `variacion_semanal` solo contra la **semana calendario anterior** (semana − 7 días); sin esa semana, la variación queda nula y `semana_anterior_disponible = false`. Los rezagos de `features_modelo` siguen la misma regla.
- [x] Umbral de dirección parametrizable (por defecto ±Q0.10), junto con semanas de test, experimento de MLflow y uso del WTI (widgets → CLI → entorno).
- [x] Definir el objetivo **dirección de la semana siguiente** y entrenar un clasificador (regresión logística o árbol, modelo global con el combustible como variable) con validación temporal y comparación contra la línea base «se repite la dirección anterior». Modo «pocos datos» sin fallar.
- [x] Registrar parámetros, métricas y modelo elegido en MLflow (con reporte local en `reports/` si MLflow no está disponible).
- [x] Crear `gold_predicciones` (`pronostico` y `backtest`, `MERGE` idempotente que rellena `direccion_real`) y `gold_metricas_modelo`.
- [x] Añadir comentarios a cada tabla y columna Oro en Unity Catalog (se reaplican después de cada `CREATE OR REPLACE`).
- [x] Variable WTI desde `bronze_petroleo_wti` (opcional).
- [x] Ejecutar Oro en Databricks (serverless): 15 ejemplos; MLflow registró parámetros y métricas. No hubo artefacto de modelo porque el clasificador no se entrenó por escasez de datos.
- [ ] Repetir Oro después de confirmar Plata actualizada y WTI, y comprobar comentarios en las cinco tablas.
- [ ] Guardar las dos ejecuciones del Job con fotos de semanas distintas y el resto de capturas listadas en [docs/oro](oro/README.md#evidencia-pendiente).

## Código local que aún no se integra al flujo Databricks

- [`src/gasolina_gt/data/features.py`](../src/gasolina_gt/data/features.py): calcula variables y objetivos de precio/tendencia a 1, 2 y 4 semanas para el flujo local. Oro en Databricks ya tiene su propia ingeniería de variables y el objetivo `direccion_siguiente`, con semanas calendario consecutivas.
- [`src/gasolina_gt/modeling/training.py`](../src/gasolina_gt/modeling/training.py): entrena un **regresor de precio** XGBoost, busca hiperparámetros, separa un test temporal y guarda archivos `joblib`. Puede orientar la validación temporal, pero **no sustituye** al clasificador de dirección solicitado para Oro.
- [`src/gasolina_gt/evaluation/metrics.py`](../src/gasolina_gt/evaluation/metrics.py): compara el regresor de precio con un baseline de persistencia y genera un reporte local. Oro en Databricks ya implementa una evaluación temporal separada para el clasificador cuando haya ejemplos suficientes.
- [`src/gasolina_gt/serving/recommendation.py`](../src/gasolina_gt/serving/recommendation.py): genera recomendaciones con el modelo local. La API de producción es independiente y consulta directamente los Delta de Oro en S3.
- [`src/gasolina_gt/data/pipeline.py`](../src/gasolina_gt/data/pipeline.py): construye un dataset local con historia sintética. Es útil para desarrollo; los datos sintéticos no deben presentarse como evidencia de validación temporal sobre precios reales del pipeline Databricks.

El OCR local de siete segmentos ya no es la ruta de producción de Plata: el notebook de Databricks usa un modelo de visión. `databricks_layers.silver()` está deshabilitada para proteger esas tablas.

## Pendientes generales para la entrega

- [x] Configurar en Databricks el Job `equipo-07-pipeline`, correo de fallo y programación semanal; el primer `Run now` terminó correctamente. Ver [guía](databricks_job.md).
- [ ] Exportar la definición real del Job a `pipelines/job.json` y revisar sus valores antes de subirla.
- [ ] Verificar dos ejecuciones exitosas con fotos de semanas distintas y conservar evidencia de duración e historial.
- [x] Implementar la API FastAPI y Docker para leer precios, pronósticos y métricas desde Oro en S3.
- [ ] Desplegar la API en el Droplet, añadir `api/.env` solo allí y comprobar los endpoints desde una computadora externa. Contenedor desplegado y puerto 8007 accesible desde fuera; falta el permiso de lectura de Oro en S3, solicitado al catedrático. Ver [guía de despliegue](api_despliegue.md).
