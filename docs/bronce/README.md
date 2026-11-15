# Capa Bronce (Gustavo Cruz)

Código: [`pipelines/01_bronze.py`](../../pipelines/01_bronze.py) → `bronze()` en [`pipelines/databricks_layers.py`](../../pipelines/databricks_layers.py).

## Qué hace

1. Lee las fotos de `BRONZE_INPUT_URI` (`img/`, recursivo) con Spark `binaryFile` por la external location del bucket Bronce. Filtra `heic/jpg/jpeg/png`.
2. Escribe el Delta `s3://<bucket-bronce>/equipo7/fotos_precios` con `path`, `modificationTime`, `length`, `content`, `_ingestion_timestamp` y `_source_file`, y lo copia a `workspace.equipo7.bronze_fotos_precios`.
3. **Incremental:** `MERGE` por `path` y solo inserta las fotos nuevas. Al volver a ejecutar no se duplica nada.
4. **Criterio de aceptación verificado en cada ejecución:** si falta alguna foto de la carpeta o hay un `path` duplicado, la tarea falla. Imprime `N fotos en la carpeta, N filas en la tabla, K nuevas`.
5. **Fuente complementaria (opcional del enunciado):** el precio diario del petróleo WTI desde FRED (`DCOILWTICO`).
   - Se guarda el CSV original en `equipo7/fuentes/wti/AAAA-MM-DD.csv`.
   - La tabla `bronze_petroleo_wti` tiene las columnas `observation_date` y `DCOILWTICO` como texto, más las columnas de auditoría. Se reemplaza en cada carga, lo que la hace idempotente.
   - Si FRED no responde, se omite sin detener la carga de fotos. Si cambia el formato del CSV, la tarea falla.

## Decisiones

- `MERGE` por `path` en lugar de Auto Loader: es más simple, cumple el criterio y no requiere un checkpoint. Una foto reemplazada con la misma ruta **no** se vuelve a cargar.
- WTI y no el histórico del MEM: FRED ofrece un CSV estable sin llave de API. El MEM publica PDFs sin una URL fija.

## Para Oro (pendiente de otro integrante)

`bronze_petroleo_wti` es texto crudo. En Oro hay que convertirlo con `CAST(DCOILWTICO AS DOUBLE)` (los días sin dato vienen vacíos) y promediarlo por semana de martes a lunes para usarlo como variable.

## Evidencia pendiente

- [ ] Captura de dos ejecuciones de Bronce: la segunda con `0 nuevas`.
- [ ] Captura de `SELECT count(*) FROM workspace.equipo7.bronze_fotos_precios` comparado con el número de fotos en `img/`.
- [ ] Captura de `bronze_petroleo_wti`. Requiere que el cluster tenga salida a internet.
