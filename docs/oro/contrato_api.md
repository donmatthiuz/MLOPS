# Contrato Oro → API

La API de `api/app/main.py` lee **solo** estas tablas, en Delta, desde `s3://bucket-oro/equipo7/<nombre>` con credenciales de solo lectura mediante `deltalake`. Las mismas tablas existen en Databricks como `workspace.equipo7.gold_<nombre>`.

Reglas generales:

- `semana` es el **martes** con que empieza la semana de martes a lunes (tipo `DATE`).
- Precios en quetzales por galón. `combustible` ∈ `super`, `regular`, `diesel`.
- Los valores nulos son normales: significan «no hay dato», no un error. Devuélvalos como `null`.
- Todas las tablas tienen `_generado_en` (`TIMESTAMP`, UTC).

## `precio_semanal` (`gold_precio_semanal`)

| Columna | Tipo | Significado |
| --- | --- | --- |
| `semana` | DATE | martes de inicio de la semana |
| `combustible` | STRING | |
| `precio_promedio` | DOUBLE | promedio de las lecturas de la semana |
| `precio_minimo` | DOUBLE | |
| `precio_maximo` | DOUBLE | |
| `n_lecturas` | INT | lecturas de Plata que entran en la semana |
| `_generado_en` | TIMESTAMP | |

## `variacion_semanal` (`gold_variacion_semanal`)

Las columnas de `precio_semanal` más:

| Columna | Tipo | Significado |
| --- | --- | --- |
| `precio_anterior` | DOUBLE | promedio de la semana 7 días antes; **nulo si esa semana no existe** |
| `diferencia_q` | DOUBLE | `precio_promedio − precio_anterior`; nula si falta la anterior |
| `diferencia_pct` | DOUBLE | porcentaje sobre el precio anterior; nulo si falta la anterior |
| `direccion` | STRING | `sube`, `baja` o `se_mantiene`; nula si falta la anterior |
| `semana_anterior_disponible` | BOOLEAN | `true` si se pudo calcular la variación |
| `umbral_q` | DOUBLE | umbral (Q) usado para etiquetar |

## `features_modelo` (`gold_features_modelo`)

Una fila por semana y combustible. Es para el modelo; la API normalmente no la consulta.
Columnas: `semana`, `combustible`, `precio_promedio`, `variacion_lag_1` a `variacion_lag_4`, `promedio_movil_4`, `dif_super_diesel`, `wti_semanal`, `wti_variacion`, `direccion_actual`, `direccion_siguiente` (objetivo; nulo en la semana que se predice), `_generado_en`. Los tipos son `DOUBLE` salvo las direcciones (`STRING`).

## `predicciones` (`gold_predicciones`)

| Columna | Tipo | Significado |
| --- | --- | --- |
| `semana` | DATE | **semana que se predice** (la semana siguiente a los datos usados) |
| `combustible` | STRING | |
| `tipo` | STRING | `pronostico`: predicción hacia adelante. `backtest`: predicción sobre una semana de prueba que ya ocurrió |
| `prediccion` | STRING | `sube`, `baja` o `se_mantiene` |
| `probabilidad` | DOUBLE | de la dirección predicha, entre 0 y 1; **nula si `modelo` es `linea_base` o `linea_base_respaldo`** (no calculan probabilidades) |
| `modelo` | STRING | `regresion_logistica`, `arbol_decision`, `linea_base` o `linea_base_respaldo` (ver abajo) |
| `direccion_real` | STRING | dirección observada; nula hasta que llegan las fotos de esa semana |
| `_generado_en` | TIMESTAMP | |

**Garantía del pronóstico.** Siempre existe una fila `tipo = 'pronostico'` por cada combustible que tenga datos en Plata, para la semana siguiente a **su propia** última semana con datos (cada combustible puede tener una `semana` distinta). Cómo se calcula cuando no hay modelo:

| `modelo` | Cuándo | `prediccion` |
| --- | --- | --- |
| `linea_base` | la última semana del combustible tiene dirección actual | esa misma dirección |
| `linea_base_respaldo` | la última semana no tiene semana anterior (llegó tras un hueco) | la última dirección conocida de ese combustible |
| `linea_base_respaldo` | el combustible nunca tuvo una dirección conocida | `se_mantiene` |

`linea_base_respaldo` es un supuesto, no una medición: la API puede mostrarlo (por ejemplo con una advertencia) pero no necesita tratarlo distinto.

**Clave única: `(semana, combustible, tipo)`.** Un mismo par semana–combustible puede tener una fila `backtest` y otra `pronostico`. El `MERGE` de Oro es idempotente: repetir una ejecución no duplica filas, y un `pronostico` ya resuelto no se reescribe.

## `metricas_modelo` (`gold_metricas_modelo`)

Una fila por ejecución de Oro (historial). **La API usa la fila con el `_generado_en` más reciente.**

| Columna | Tipo | Significado |
| --- | --- | --- |
| `run_id_mlflow` | STRING | ejecución en MLflow; nulo si MLflow no estuvo disponible |
| `modelo_elegido` | STRING | el que genera las predicciones (`linea_base` si el modelo no la superó) |
| `usa_linea_base` | BOOLEAN | |
| `modo_pocos_datos` | BOOLEAN | `true`: no hubo ejemplos para entrenar y se predijo con la línea base |
| `motivo` | STRING | explicación en texto de la elección |
| `candidato` | STRING | mejor modelo en la validación dentro de train; nulo con pocos datos |
| `validado_en_train` | BOOLEAN | |
| `cv_f1_regresion_logistica`, `cv_f1_arbol_decision` | DOUBLE | F1 macro de la validación temporal dentro de train |
| `n_ejemplos`, `n_train`, `n_test` | INT | |
| `semana_train_inicio`, `semana_train_fin`, `semana_test_inicio`, `semana_test_fin` | DATE | |
| `accuracy_modelo`, `f1_macro_modelo` | DOUBLE | del modelo candidato en las semanas de prueba; nulas con pocos datos |
| `accuracy_linea_base`, `f1_macro_linea_base` | DOUBLE | de la línea base sobre las mismas semanas |
| `umbral_q`, `semanas_test` | DOUBLE, INT | parámetros usados |
| `usa_wti` | BOOLEAN | |

Con pocos datos, `n_train = 0` y la línea base se mide sobre todos los ejemplos (`n_test = n_ejemplos`).

## Consulta de cada endpoint

`GET /health` comprueba que se puede abrir `precio_semanal` en S3. Devuelve 503 si falla. `GET /precios/actual` devuelve una lista, una fila por combustible. `GET /precios` acepta `limit` (1 a 500, predeterminado 100) y `offset` (desde 0); devuelve primero las semanas más recientes. Todos los campos nulos se serializan como `null`.

SQL de referencia (DuckDB/Polars con `delta_scan`; en Databricks se usa el nombre `workspace.equipo7.gold_<tabla>`).

**`GET /precios/actual`**: último precio por combustible.

```sql
SELECT combustible, semana, precio_promedio, precio_minimo, precio_maximo
FROM precio_semanal
QUALIFY semana = max(semana) OVER (PARTITION BY combustible);
```

**`GET /precios?combustible=diesel&desde=2026-10-01&hasta=2026-11-30&limit=100`**: histórico semanal. Los filtros son opcionales.

```sql
SELECT v.semana, v.combustible, v.precio_promedio, v.precio_minimo, v.precio_maximo,
       v.diferencia_q, v.diferencia_pct, v.direccion
FROM variacion_semanal v
WHERE (:combustible IS NULL OR v.combustible = :combustible)
  AND (:desde IS NULL OR v.semana >= :desde) AND (:hasta IS NULL OR v.semana <= :hasta)
ORDER BY v.semana DESC, v.combustible DESC
LIMIT :limit OFFSET :offset;
```

**`GET /prediccion?combustible=super`**: pronóstico más reciente.

```sql
SELECT semana, prediccion, probabilidad, modelo
FROM predicciones
WHERE tipo = 'pronostico' AND combustible = :combustible
ORDER BY semana DESC
LIMIT 1;
```

Ejemplo de respuesta: `{"semana": "2026-11-17", "prediccion": "sube", "probabilidad": 0.68, "modelo": "regresion_logistica"}`. Con `modelo = linea_base` o `linea_base_respaldo` la `probabilidad` es `null`. Solo hay 404 si el combustible nunca tuvo datos. Si la `semana` del pronóstico quedó atrás de la semana actual, ese combustible no ha recibido fotos nuevas.

**`GET /modelo/metricas`**: exactitud del modelo y de la línea base.

```sql
SELECT modelo_elegido, usa_linea_base, modo_pocos_datos, motivo,
       accuracy_modelo, f1_macro_modelo, accuracy_linea_base, f1_macro_linea_base,
       n_train, n_test, semana_test_inicio, semana_test_fin, run_id_mlflow, _generado_en
FROM metricas_modelo
ORDER BY _generado_en DESC
LIMIT 1;
```

Con `modo_pocos_datos = true`, `accuracy_modelo` y `f1_macro_modelo` son `null`: muéstrelo tal cual junto con `motivo`.
