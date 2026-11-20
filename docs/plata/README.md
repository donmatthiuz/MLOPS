# Capa Plata — extracción y limpieza de precios

Responsable: Carlos Valladares · Equipo 7

La capa Plata convierte cada foto de Bronce en filas limpias de precio: **una fila por fecha, ubicación, combustible y modalidad**.

## Archivos

| Archivo | Qué hace |
|---|---|
| `pipelines/02_silver.py` | Notebook/tarea del Job. Extrae, valida y carga con `MERGE`. |
| `pipelines/plata_reglas.py` | Reglas de calidad y normalización (funciones puras). |
| `pipelines/plata_referencia.py` | Carga y consulta de promedios mensuales del MEM. |
| `docs/plata/precios_mem_capital_mensual.csv` | Transcripción del [PDF del MEM](../PRECIOS-PROMEDIO-MENSUAL-CONSUMIDOR-FINAL-EN-CIUDAD-CAPITAL-2026-09.pdf): enero de 2020 a septiembre de 2026. |
| `tests/unit/test_plata_reglas.py` | Pruebas de las reglas (`pytest`). |
| `pipelines/plata_revision_manual.py` | Galería de la muestra y cálculo de exactitud. |
| `docs/plata/revision_manual.csv` | Precios reales anotados a mano para la muestra. |

## Tablas

Delta en S3 (fuente de verdad) en `s3://cc3105-ag-869227452861-us-east-2-an/equipo7/<tabla>`, copiadas a tablas
administradas de `workspace.equipo7` (Oro usa el prefijo S3 completo que se configure y conserva el mismo esquema administrado; no requiere
`CREATE EXTERNAL TABLE`).

| Delta en S3 | Tabla en el catálogo | Contenido |
|---|---|---|
| `precios` | `workspace.equipo7.silver_precios` | `fecha`, `combustible`, `precio_q_galon`, `modalidad`, `ubicacion`, `foto_origen`, `metodo_validacion` |
| `precios_rejected` | `workspace.equipo7.silver_precios_rejected` | Lecturas o fotos que fallaron una regla, con `motivo` |
| `extracciones` | `workspace.equipo7.silver_extracciones` | Respuesta cruda del modelo por foto (auditoría y reaplicación de reglas) |
| `revision_manual` | — | Resultado de la revisión manual |

## Cómo se ejecuta

- **Tarea Plata del Job:** el notebook `pipelines/02_silver.py` (tarea de tipo notebook desde el Git folder), con modo `incremental`.
- **Modos del notebook** (widget `modo`):
  - `incremental`: solo fotos nuevas de Bronce.
  - `reaplicar_reglas`: no llama al modelo; vuelve a aplicar las reglas a `extracciones` y reemplaza `precios` y
    `precios_rejected` (~1 min). Usar cuando cambia una regla.
  - `reprocesar_todo`: vuelve a enviar todas las fotos al modelo (~20 min para 110 fotos).
- Después de cambiar Plata hay que volver a ejecutar Oro.
- Para aplicar esta regla a las extracciones existentes, actualice el Git folder en Databricks y ejecute con
  `modo=reaplicar_reglas`, `usar_referencia=si`, `referencia_csv` vacío y los parámetros habituales `origen` y
  `silver_uri`. Luego ejecute `pipelines/03_gold.py`. No necesita repetir Bronce ni llamar de nuevo al modelo.

## Cómo se extrae el precio

**Por qué un modelo de visión y no Tesseract:** el cómputo del workspace es solo serverless (no permite instalar el binario de Tesseract), y el OCR de 7 segmentos que ya existía usa recortes calibrados a mano para un solo dispensador Shell, así que no sirve para las fotos del catedrático (Puma, Shell, otras bombas). El enunciado permite "OCR o un modelo de visión".

Se probaron los modelos con entrada de imagen disponibles en el workspace:

| Modelo | Resultado en la prueba |
|---|---|
| `databricks-llama-4-maverick` | Lee bien rótulos grandes; en visores LCD pequeños confunde dígitos (leyó 21.29 en un visor que dice 27.29) |
| `databricks-gemma-3-12b` | Respuestas sin sentido (devuelve galones o montos como precios) |
| `databricks-qwen35-122b-a10b` | No acepta imágenes |

Se eligió **Llama 4 Maverick** y, como puede confundir dígitos, cada foto se lee **dos veces** (a 1600 px y a 2560 px) y se concilia:

1. Si una lectura coincide con el precio que se deduce del **display de la bomba** (monto ÷ galones; p. ej. Q100.00 ÷ 3.664 gal = Q27.29), se acepta (`metodo_validacion = display_bomba`).
2. Si las dos lecturas coinciden (±Q0.01), se acepta (`consenso`).
3. Si discrepan, se escoge la lectura más cercana al promedio mensual del MEM del mismo mes, combustible y modalidad,
   siempre que esté a Q3 o menos de ese promedio. Si hay empate, ambas están más lejos o no se pudo leer un número,
   se usa el promedio mensual (`referencia_mensual`). Si el orden súper ≥ regular falla, la referencia corrige la
   lectura atípica o respalda ambas. Cada caso queda marcado en `metodo_validacion`.

**Supuestos del respaldo:** todas las fotos se tratan como tomadas en Ciudad Capital. Si la foto no indica modalidad,
se usa el promedio de **autoservicio** y el método termina en `_autoservicio_supuesto`. El CSV cubre 2020-01 a
2026-09; para fechas posteriores no se extrapola un mes anterior y se mantiene el rechazo habitual si las lecturas
siguen sin conciliar. Si ninguna respuesta identifica el combustible, se conserva `foto_sin_precios`: el promedio no
permite saber qué visor había en la foto. Oro usa los métodos que empiezan en `referencia_` para completar
semanas de entrenamiento, pero mide el desempeño únicamente en semanas formadas por lecturas observadas.
En el resumen semanal se usa el respaldo solo cuando no hay una lectura observada del mismo combustible y semana.
Agregar respaldos no garantiza que MLflow deje de usar la línea base: siguen haciendo falta suficientes ejemplos
antes de las últimas semanas observadas y al menos dos clases en entrenamiento.

## Reglas de calidad

| Regla | Motivo de rechazo |
|---|---|
| La foto tiene fecha EXIF | `fecha_desconocida` |
| La fecha no es futura | `fecha_futura` |
| Si la foto está en una carpeta de año (`img/2024/…`), su fecha cae en ese año (±90 días: las carpetas incluyen fotos de fin del año anterior) | `fecha_no_coincide_con_carpeta` |
| Combustible del catálogo: `super`, `regular`, `diesel` (V-Power y otras premium quedan fuera) | `combustible_fuera_catalogo` |
| Precio legible o promedio mensual disponible | `sin_lectura` / `precio_ilegible` si no hay respaldo |
| Precio entre **Q15 y Q60** por galón | `precio_fuera_rango` |
| Las dos lecturas coinciden, una coincide con el display o hay referencia mensual | `lecturas_inconsistentes` / `sin_lectura` si no hay respaldo |
| La súper no puede costar menos que la regular en la misma foto | `super_menor_que_regular` |

**Rango Q15–Q60:** en las fotos de 2023–2026 se observaron precios entre Q24.79 y Q43.99 por galón; los de 2026 (Q40–Q44) están confirmados con el display de la bomba en varias fotos. El margen evita descartar alzas reales y aun así filtra lecturas absurdas, como galones (3.66) o montos (Q100) leídos como precio. El rango es un parámetro del Job (`precio_min`, `precio_max`). La primera ejecución usó Q45 como máximo.

**Fecha:** se usa solo el EXIF de la foto. `modificationTime` no sirve porque es la fecha en que se subió el archivo a S3 (todas las fotos del catedrático tienen 2026-11-11).

## Carga idempotente

- Las fotos que ya están en `silver.extracciones` no se vuelven a enviar al modelo.
- `MERGE` con llave `fecha + ubicacion + combustible + modalidad` en `precios`, y `foto_origen + combustible + motivo` en `precios_rejected`.
- Una segunda ejecución sin fotos nuevas no cambia ninguna tabla.

## Parámetros (widgets)

`origen` (Delta de Bronce, tabla o carpeta `s3://`), `silver_uri`, `catalogo`, `esquema`, `modo`, `modelo`, `lado_a`, `lado_b`, `precio_min`, `precio_max`, `limite_fotos`, `escribir`, `usar_referencia`, `referencia_csv`.

En el Job, `origen = s3://cc3105-cusn-869227452861-us-east-2-an/equipo7/fotos_precios` (Delta de Bronce). Para desarrollo se puede apuntar directo a `s3://cc3105-raw-869227452861-us-east-2-an/img/`.

## Resultados (2026-11-15)

Origen: las 110 fotos de `s3://cc3105-raw-869227452861-us-east-2-an/img/` (38 sueltas de 2026 + carpetas `2023`, `2024`, `2025`). Extracción con el modelo: ~18 min en serverless. Después se corrigió la regla de carpeta y se ejecutó `reaplicar_reglas` (sin llamar al modelo).

| Métrica | Primera ejecución | Tras `reaplicar_reglas` |
|---|---|---|
| Fotos procesadas | 110 | 110 |
| Fotos con al menos un precio válido | — | 76 |
| Fotos rechazadas por completo | — | 34 |
| Lecturas válidas (`silver_precios`) | 139 | **148** |
| Lecturas rechazadas (`silver_precios_rejected`) | 159 | **150** |

Motivos de rechazo en la primera ejecución: `lecturas_inconsistentes` 100 · `sin_lectura` 36 · `fecha_no_coincide_con_carpeta` 10 (regla demasiado estricta, corregida) · `foto_sin_precios` 7 · `super_menor_que_regular` 4 · `precio_fuera_rango` 2. De los 139 válidos, 90 se validaron por consenso de dos lecturas y 49 con el display de la bomba.

Precios válidos por año (mín–máx, Q/galón, primera ejecución): 2023 Q30.59–Q37.29 · 2024 Q27.49–Q34.44 · 2025 Q24.79–Q31.53 · 2026 Q25.99–Q43.99.

**Idempotencia:** la escritura se ejecutó dos veces con los mismos datos y los conteos no cambiaron (139 / 159 / 110).

**Exactitud medida a mano (2026-11-15).** Muestra de 24 fotos repartidas entre 2023, 2024, 2025 y 2026
(`docs/plata/revision_manual.csv`). Se leyeron a ciegas (sin ver la salida del modelo) con
`plata_revision_ciega2`, recortando cada visor a resolución completa; cuando la foto muestra el display de la bomba,
el precio se confirmó con monto ÷ galones. Solo cuentan las 33 lecturas que se pudieron leer con seguridad
(15 fotos); otras 19 quedaron como `dudosa` (visor deslavado, cortado o a medio refrescar) y no entran en el cálculo.

| Métrica | Valor |
|---|---|
| Lecturas visibles con certeza | 33 |
| Extraídas por Plata con el valor correcto | 13 |
| Extraídas con valor incorrecto | 4 |
| No extraídas (rechazadas o no leídas) | 16 |
| **Cobertura** (correctas / visibles) | **39.4 %** |
| **Precisión** (correctas / guardadas verificables) | **76.5 %** (13/17) |

Errores encontrados:
- `IMG_8271` (2026): el modelo corrió las etiquetas un lugar: guardó el diésel (35.59) como regular y la regular
  (37.09) como súper. Pasó porque **las dos lecturas coincidieron en el mismo error**, así que el consenso no lo detecta.
- `2025/IMG_6400` (diésel 25.69 → 25.64) e `IMG_7736` (diésel 26.19 → 26.17): error en el último dígito.
- Probables, sin verdad confiable para contar: `2023/IMG_3388` súper 33.19 (el display da 33.79) y `2024/IMG_5181`
  diésel 32.84 (el display de la súper da 32.89; posible etiqueta corrida).

Conclusión: la doble lectura filtra mucho ruido, pero no los errores sistemáticos de etiqueta. Mejora propuesta: exigir
que cada precio coincida con el display cuando la foto lo muestra, y validar el orden diésel < regular < súper.

### Observaciones para la revisión manual

- El modelo confunde dígitos de 7 segmentos (1↔7). La doble lectura descarta muchas lecturas dudosas (100 inconsistentes): preferimos perder datos a guardarlos mal.
- Revisar con cuidado `IMG_8382.HEIC` (2026-08-19): diésel Q43.99 y súper Q39.99 en la misma foto; puede ser una lectura equivocada que pasó por consenso.

## Coordinación con el equipo

- **No ejecutar `databricks_layers.silver()`**: ahora se detiene con un mensaje que dirige a este notebook. Así el OCR
  antiguo no puede sobrescribir las tablas del modelo de visión.
- Oro lee `s3://…ag/equipo7/precios`; `precio_q_galon` es `DECIMAL(6,2)`. **Hay que volver a ejecutar Oro** después del
  `reaplicar_reglas` (las tablas Oro se calcularon con 139 precios).
