# Job y experimento de Databricks · equipo 7

Referencia: [enunciado](enunciado_proyecto.pdf), fases 3 y 4. El Job se configura en la interfaz de Databricks; al terminar se exporta su definición real a `pipelines/job.json` para la entrega. Un archivo en Git **no crea** un Job en el workspace.

## Diseño listo en el repositorio

| Tarea | Notebook del Git folder `Workspace → Shared → MLOPS` | Resultado |
| --- | --- | --- |
| `01_bronce` | `pipelines/01_bronze.py` | Fotos y WTI opcional en Bronce; verifica fotos faltantes y duplicadas. |
| `02_plata` | `pipelines/02_silver.py` | Extracción con modelo de visión en modo `incremental`; Delta de precios, rechazos y respuestas crudas. |
| `03_oro` | `pipelines/03_gold.py` | Tablas Oro, predicciones, métricas y una ejecución del experimento MLflow. |

Las dependencias entre tareas son Bronce → Plata → Oro. Todas usan **serverless environment v6** con `pillow-heif`, `openai`, `scikit-learn`, `mlflow`, `pandas` y `requests`. Los notebooks Bronce y Oro reciben las cuatro URI y el catálogo como parámetros; Plata recibe `origen`, `silver_uri`, `catalogo`, `esquema` y sus parámetros de extracción. Los siete parámetros comunes se completan en **Job parameters** y se pasan automáticamente a las tareas de notebook. El Job no lee automáticamente un `.env` y no requiere claves AWS en el repositorio.

La programación propuesta es **martes a las 20:00, hora de Guatemala**, inicialmente pausada para probar `Run now`. Falta elegir en la UI el correo de aviso por fallo y activar la programación tras la primera ejecución correcta. En Free Edition se usa serverless porque no hay clusters clásicos disponibles; esto satisface la alternativa de cómputo que indique el catedrático, pero la diferencia con un cluster interactivo/clásico debe explicarse en el informe.

## Antes del primer `Run now`

1. Hacer commit y push de los cambios de código, y luego `Pull` en el Git folder **`/Workspace/Shared/MLOPS`** de Databricks. Verificar que esté en `proyecto1` y que aparezcan `01_bronze.py`, `02_silver.py` y `03_gold.py` actualizados. El pull local no actualiza automáticamente ese Git folder.
2. Verificar que la identidad **Run as** del Job pueda leer `xloc-raw`, escribir `equipo7/` en Bronce y Plata y el prefijo completo configurado en `gold_output_uri` para Oro, crear o reemplazar tablas en `workspace.equipo7`, consultar el endpoint `databricks-llama-4-maverick` y crear/escribir el experimento `/Shared/equipo7-gasolina`.
3. Crear el Job `equipo-07-pipeline` con las tres tareas de la tabla anterior; usar **Notebook** como tipo de tarea, origen **Workspace** y cómputo **Serverless** con el mismo entorno v6. Completar en **Job parameters** `bronze_input_uri`, `bronze_output_uri`, `silver_output_uri`, `gold_output_uri`, `databricks_catalog`, `origen` y `silver_uri` con las rutas autorizadas del equipo. `gold_output_uri` debe ser la ruta completa del prefijo Oro y coincidir con `GOLD_OUTPUT_URI` de la API. En Plata usar `modo=incremental`, `catalogo=workspace`, `esquema=equipo7`, `modelo=databricks-llama-4-maverick`, `precio_min=15` y `precio_max=60`. En Oro usar `mlflow_experiment=/Shared/equipo7-gasolina`, `umbral_q=0.10`, `semanas_test=4` y `usar_wti=true`. Agregar aviso por correo **On failure**. Mantener la programación pausada durante la prueba.

## Primera verificación

Ejecutar **Run now** y comprobar en el historial que las tres tareas terminen correctamente en orden. La tarea Oro debe imprimir `Oro: parámetros ...` y un `run MLflow: <id>` no nulo. Si hay pocos ejemplos, `modelo=linea_base` y `modo_pocos_datos=true` son resultados válidos; en ese caso el experimento tendrá parámetros y métricas, pero no un artefacto de clasificador entrenado.

Consultas de control:

```sql
SELECT COUNT(*) FROM workspace.equipo7.bronze_fotos_precios;
SELECT COUNT(*) FROM workspace.equipo7.silver_precios;
SELECT COUNT(*) FROM workspace.equipo7.silver_precios_rejected;
SELECT modelo_elegido, modo_pocos_datos, n_ejemplos, run_id_mlflow, usa_wti, _generado_en
FROM workspace.equipo7.gold_metricas_modelo ORDER BY _generado_en DESC LIMIT 1;
SELECT semana, combustible, tipo, prediccion, probabilidad, direccion_real
FROM workspace.equipo7.gold_predicciones ORDER BY semana DESC, combustible, tipo;
SELECT criterio, combustible, modelo, n_test, accuracy, f1_macro, semana_inicio, semana_fin
FROM workspace.equipo7.gold_metricas_combustible
ORDER BY combustible, criterio, modelo;
```

`gold_metricas_combustible` compara la línea base, la regresión logística y el árbol en los mismos triples de cada combustible. `criterio=independiente` usa solo lecturas verificadas sin referencia; `criterio=asistido` añade desempates de lecturas fotográficas apoyados por el promedio mensual, pero nunca precios sustituidos. Cada predicción se entrena solo con semanas anteriores; `n_test=0` indica que todavía no hay suficientes ejemplos previos para medir ese combustible. Es un diagnóstico adicional y no cambia el modelo publicado en `gold_predicciones`.

Verificar además el experimento `/Shared/equipo7-gasolina` en **Experiments** y los comentarios de las tablas Oro con `DESCRIBE TABLE EXTENDED workspace.equipo7.gold_predicciones`. El código de Oro ahora falla antes de escribir si MLflow no registra la ejecución; también falla si no puede aplicar los comentarios.

Después de la prueba, activar la programación o el disparador de archivos que permita el workspace. Para la evidencia del enunciado se necesitan **dos ejecuciones exitosas con fotos de semanas distintas**; repetir el Job sin nuevas fotos comprueba idempotencia, pero no sustituye esa evidencia.
Al terminar la configuración, exportar la definición real del Job a `pipelines/job.json`. Antes de guardarla en Git, revisar sus parámetros y retirar cualquier secreto o valor privado que aparezca en el archivo.

## Reproceso de Plata

El notebook `02_silver.py` tiene `modo=incremental`, `reaplicar_reglas` y `reprocesar_todo`. Para cambiar reglas, ejecutar **solo Plata** con `reaplicar_reglas` y luego Oro. Para extraer de nuevo todas las fotos, usar `reprocesar_todo` y luego Oro; esto vuelve a llamar al endpoint y tarda más. En el Job programado dejar `incremental`. `databricks_layers.silver()` está deshabilitada para evitar que el OCR anterior sobrescriba las tablas de visión.
