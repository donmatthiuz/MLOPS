# Pendientes de las capas en Databricks

Estado observado el 15 de noviembre de 2026. Referencia: [enunciado del proyecto](enunciado_proyecto.pdf). Las cifras provienen de las ejecuciones compartidas del notebook y sirven como punto de partida para verificar cambios posteriores.

## Estado actual

| Capa | Ya funciona en Databricks | Pendiente |
| --- | --- | --- |
| Bronce | Lee `img/`, guarda fotos y metadatos en Delta y registra la tabla en `workspace.equipo7`. Se comprobaron 110 fotos únicas. | No hay un cambio esencial pendiente en la lógica de la capa. |
| Plata | Usa el OCR del proyecto local, aplica reglas de calidad y deduplicación, guarda precios y rechazos en Delta y registra las tablas. Se observaron 139 lecturas válidas y 159 rechazos; las 110 fotos quedaron contabilizadas. | Medición manual de calidad, desglose de rechazos en el notebook, extracción de modalidad/ubicación y prueba del reproceso completo. |
| Oro | Genera y registra `precio_semanal`, `variacion_semanal` y `features_modelo`. Se observaron 125 filas en cada tabla. | Corregir comparaciones entre semanas, entrenar y evaluar el clasificador, registrar MLflow, crear `predicciones` y documentar tablas/columnas. |

## Pendientes por capa

### Bronce

- [x] Comprobar que una segunda ejecución no duplica las fotos.
- [ ] Integrar su ejecución en el Job completo; esto es un pendiente de orquestación, no de la lógica de Bronce.

### Plata

- [ ] Revisar manualmente **al menos 20 fotos** y reportar el porcentaje de precios extraídos correctamente.
- [ ] Mostrar en el notebook cuántas **fotos** se procesaron, cuántas se rechazaron y el desglose por motivo. Los totales actuales son de **lecturas**, no necesariamente de fotos.
- [ ] Extraer `modalidad` y `ubicacion` cuando aparezcan en la imagen. Actualmente se guardan `no_especificada` y `desconocida`.
- [ ] Probar en Databricks `silver(settings(), reprocess=True)` y verificar que las tablas Plata se regeneran sin duplicados; después volver a ejecutar Oro.

### Oro

- [ ] Calcular `variacion_semanal` solo contra la **semana calendario anterior**. Actualmente `lag` toma la observación anterior aunque hayan pasado meses. En los datos observados hay 9 pares consecutivos para diésel, 6 para regular y 18 para súper; esto limita los ejemplos válidos para el modelo.
- [ ] Definir el objetivo **dirección de la semana siguiente** y entrenar un clasificador por combustible o una estrategia equivalente. Separar entrenamiento y prueba por tiempo y compararlo con la línea base «se repite la dirección anterior».
- [ ] Registrar parámetros, métricas y modelo elegido en MLflow de Databricks.
- [ ] Crear `gold.predicciones` con combustible, semana, dirección predicha, probabilidad y dirección real cuando esté disponible.
- [ ] Añadir comentarios a cada tabla y columna Oro en Unity Catalog.

## Código local que aún no se integra al flujo Databricks

- [`src/gasolina_gt/data/features.py`](../src/gasolina_gt/data/features.py): calcula variables de calendario, rezagos, medias móviles y objetivos de precio/tendencia a 1, 2 y 4 semanas. La tabla Databricks `features_modelo` tiene otras variables y **no contiene todavía el objetivo de clasificación**. Sus desplazamientos por fila tampoco deben interpretarse automáticamente como semanas consecutivas ante los huecos observados.
- [`src/gasolina_gt/modeling/training.py`](../src/gasolina_gt/modeling/training.py): entrena un **regresor de precio** XGBoost, busca hiperparámetros, separa un test temporal y guarda archivos `joblib`. Puede orientar la validación temporal, pero **no sustituye** al clasificador de dirección solicitado para Oro.
- [`src/gasolina_gt/evaluation/metrics.py`](../src/gasolina_gt/evaluation/metrics.py): compara el regresor de precio con un baseline de persistencia y genera un reporte local. En Databricks falta una evaluación temporal del **clasificador** frente al baseline de dirección indicado en el enunciado.
- [`src/gasolina_gt/serving/recommendation.py`](../src/gasolina_gt/serving/recommendation.py): genera recomendaciones con el modelo local. Falta conectar el servicio/API al resultado de Oro en Databricks una vez que existan predicciones.
- [`src/gasolina_gt/data/pipeline.py`](../src/gasolina_gt/data/pipeline.py): construye un dataset local con historia sintética. Es útil para desarrollo; los datos sintéticos no deben presentarse como evidencia de validación temporal sobre precios reales del pipeline Databricks.

El OCR local **ya está reutilizado en Plata**, por lo que no figura como integración pendiente.

## Pendientes generales para la entrega

- [ ] Crear el Job de Databricks con tareas Bronce → Plata → Oro, parámetros y dependencias; configurar ejecución programada o por llegada de fotos y aviso de fallo.
- [ ] Verificar dos ejecuciones exitosas con fotos de semanas distintas y conservar evidencia de duración e historial.
- [ ] Completar la API que publica precios y predicciones desde Oro y la documentación/evidencia pedida por el enunciado.
