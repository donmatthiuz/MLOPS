# Guion de la presentación · Gasolina GT · Equipo 7

**Formato del jurado:** 20 minutos = 10 de exposición + 5 de demo en vivo + 5 de preguntas.
**Archivo:** `presentacion/presentacion.html` (abrir en Chrome o Edge, tecla **F** para pantalla completa, flechas para avanzar).
**Regla del enunciado:** el jurado puede preguntarle a cualquiera, así que todos deben conocer el flujo completo.

| # | Diapositiva | Presenta | Tiempo |
|---|---|---|---|
| 1 | Portada | José Gramajo | 0:20 |
| 2 | El problema | José Gramajo | 1:00 |
| 3 | La solución | Mathew Cordero | 0:50 |
| 4 | Arquitectura | Mathew Cordero | 1:10 |
| 5 | Capa Bronce | Gustavo Cruz | 1:00 |
| 6 | Capa Plata | Carlos Valladares | 1:30 |
| 7 | Capa Oro | José Gramajo | 1:00 |
| 8 | El modelo | José Gramajo | 1:20 |
| 9 | Orquestación (Job) | Mathew Cordero | 0:50 |
| 10 | API pública | Josué Say | 0:50 |
| 11 | Demo en vivo | Mathew Cordero y Josué Say | 5:00 |
| 12 | Lecciones | Todo el equipo | 0:40 |
| 13 | Gracias / preguntas | Todo el equipo | 5:00 |

---

## 1 · Portada — José (20 s)
> Buenas tardes. Somos el equipo 7 y presentamos **Gasolina GT**: un sistema que, a partir de una foto de los precios en la gasolinera, predice si el precio de cada combustible sube, baja o se mantiene la semana siguiente, y lo publica en una API.

## 2 · El problema — José (1 min)
- El MEM publica cada martes los precios de referencia de súper, regular y diésel, vigentes de martes a lunes.
- Esos precios siguen al petróleo internacional y, a veces, a subsidios temporales.
- A hogares, transportistas y negocios les sirve saber **hacia dónde va el precio** para decidir cuándo llenar el tanque o cómo presupuestar.
> Nuestra pregunta es concreta: para cada combustible, ¿la próxima semana sube, baja o se mantiene?

## 3 · La solución — Mathew (50 s)
- Una línea: foto → Bronce → Plata → Oro → API.
- Tres plataformas: S3 guarda cada capa, Databricks procesa y entrena, y DigitalOcean publica la API.
> Todo corre de forma automática y se puede reproducir desde el repositorio.

## 4 · Arquitectura — Mathew (1 min 10 s)
- Recorrer el diagrama de izquierda a derecha: las fotos del catedrático en `cc3105-raw/img/` y el WTI de FRED entran al Job.
- Cada tarea escribe en su bucket (`equipo7/`) y la siguiente lee de ahí: es la arquitectura medallón.
- Oro registra cada ejecución en MLflow.
- La API del Droplet **solo lee Oro**. El equipo entra por SSH y el usuario final usa HTTP.

## 5 · Capa Bronce — Gustavo (1 min)
- Spark lee las fotos con `binaryFile` a través de la external location, sin llaves en el código.
- Se guardan tal cual, con columnas de auditoría, para poder reprocesarlas si cambia la extracción.
- La carga es incremental: MERGE por ruta. En cada corrida se verifica que **filas = fotos (110)** y que no haya duplicados.
- Fuente complementaria: 10 660 días del precio del petróleo WTI (FRED).

## 6 · Capa Plata — Carlos (1 min 30 s)
- El OCR de 7 segmentos no servía para todas las bombas, y serverless no permite instalar Tesseract. Por eso usamos el modelo de visión **Llama 4 Maverick** dentro de Databricks.
- Cada foto se lee **dos veces**. Se acepta una lectura si coincide con monto ÷ galones del display, o si las dos lecturas coinciden.
- 8 reglas de calidad; lo que falla va a `silver_precios_rejected` con su motivo.
- Si las dos lecturas no se concilian, se desempata o completa con el **promedio mensual del MEM** (Ciudad Capital, 2020–2026) y queda marcado en `metodo_validacion`.
- Resultado actual: 289 lecturas válidas (134 completadas con el promedio mensual) y 12 rechazadas; 105 de 110 fotos aportan al menos un precio.
- Ser transparentes: casi la mitad de los precios de Plata vienen del promedio mensual, por eso no se usan para medir el modelo.
- **Revisión manual de 24 fotos:** precisión 76.5 % (lo que guardamos está bien) y cobertura 39.4 %.
> El respaldo mensual nos sirve para entrenar, pero nunca lo usamos como verdad para medir el modelo.

## 7 · Capa Oro — José (1 min)
- Seis tablas Delta con comentarios en cada columna: precio semanal, variación, variables, predicciones, métricas del modelo y métricas por combustible.
- La semana va de martes a lunes, como el MEM. Un cambio de hasta Q0.10 cuenta como «se mantiene».
- **Huecos:** solo comparamos con la semana inmediatamente anterior. Si no hay fotos esa semana, la variación queda vacía en vez de compararse con un precio de hace meses.

## 8 · El modelo — José (1 min 20 s)
- Variables que solo usan el pasado: variación de 1 a 4 semanas, promedio móvil, diferencia súper–diésel y WTI.
- Candidatos: regresión logística y árbol de decisión, un modelo global con el combustible como variable.
- Validación **temporal**: las últimas 4 semanas son prueba. La línea base es «se repite la dirección de la semana anterior».
- **Resultado honesto:** con el respaldo mensual ya hay **49 ejemplos** y el modelo se entrena (45). Pero la prueba, solo con semanas de fotos reales, tiene **4 casos**: la logística empata en accuracy (0.50) y pierde en F1 macro (0.27 contra 0.33). Por regla, **se publica la línea base** y queda registrado en MLflow.
- Todo queda registrado en MLflow.

## 9 · Orquestación — Mathew (50 s)
- Job `equipo-07-pipeline` con tres tareas de notebook encadenadas.
- Free Edition solo tiene serverless: no hay que encender clusters ni configurar autoterminación, y se paga solo el uso.
- Programado los martes a las 09:40 (hora de Guatemala), con aviso por correo si falla. El historial tiene 18 ejecuciones (16 exitosas); la programada del 17-nov corrió las tres tareas en 3 min 56 s. Las rutas y el umbral son parámetros del Job.

## 10 · API — Josué (50 s)
- FastAPI en Docker en el Droplet, puerto 8007, `restart: unless-stopped`.
- Lee Oro desde S3 con `deltalake` y credenciales de solo lectura en un `.env` que no está en Git. `/health` responde `ok`.
- La misma imagen sirve una **interfaz web** en `/` con precios, histórico y pronóstico.
- Cinco endpoints. Swagger en `/docs`. Invitar al jurado a escanear el QR: abre `/prediccion?combustible=super` en su teléfono (pueden cambiar `super` por `regular` o `diesel`).

## 11 · Demo en vivo — Mathew y Josué (5 min)
1. **Databricks → Jobs & Pipelines → `equipo-07-pipeline` → Run now.** Mostrar las tareas Bronce → Plata → Oro. Si tarda, abrir una ejecución anterior ya terminada.
2. Abrir la tarea **03_oro → Output**: parámetros, ejemplos válidos y `run MLflow`.
3. **Experiments → `/Shared/equipo7-gasolina`**: la nueva corrida con parámetros y métricas.
4. En el navegador: `http://159.65.111.14:8007/docs` → probar `/prediccion?combustible=super` y `/modelo/metricas`.
   - Abrir también la **interfaz web** `http://159.65.111.14:8007/`: precios por combustible, histórico y sección «Modelo».
5. **Plan B** (si falla la red o la API): mostrar las capturas de `docs/job/evidencia/` y `docs/oro/evidencia/`.

## 12 · Lecciones — todo el equipo (40 s, una idea cada uno)
- **José:** el dato manda; con 4 casos de prueba ningún modelo puede demostrar que le gana a la línea base, y preferimos decirlo a inflar un número.
- **Carlos:** validar en cada frontera; la cuarentena con motivo hace visibles los errores.
- **Gustavo:** idempotencia; repetir el Job no duplica nada.
- **Josué / Mathew:** las restricciones de la plataforma (serverless, permisos de S3) se resuelven temprano. Con más tiempo cargaríamos el histórico del MEM.

## 13 · Preguntas probables del jurado
| Pregunta | Respuesta corta | Responde |
|---|---|---|
| ¿Por qué no aleatorio el test? | En series de tiempo, mezclar semanas filtra información del futuro; validamos con semanas posteriores al entrenamiento. | José |
| ¿Su modelo funciona? | Entrena y se compara en cada ejecución; en la prueba (4 casos reales) no supera a la línea base, así que se publica la base. Con el histórico semanal del MEM tendríamos cientos de ejemplos para una prueba seria. | José |
| ¿Por qué no evaluar con los precios mensuales? | Un promedio mensual repite el mismo precio todas las semanas del mes: inventaría «se mantiene». Solo medimos contra fotos reales. | José |
| ¿Qué tan confiable es la extracción? | 76.5 % de precisión en lo que guardamos y 39.4 % de cobertura. Descartamos lo dudoso a propósito. | Carlos |
| ¿Qué pasa si suben fotos repetidas? | MERGE por ruta en Bronce: no se duplican; se verifica en cada corrida. | Gustavo |
| ¿Por qué serverless y no un job cluster? | Free Edition no ofrece clusters clásicos; serverless cobra solo el uso y arranca sin configurar nodos. | Mathew |
| ¿Cómo protegen las credenciales? | External locations en Databricks; en el Droplet, `.env` con permisos 600 fuera de Git. | Josué |
| ¿Por qué ±Q0.10? | Los precios se mueven por centavos; no queremos llamar «alza» a un redondeo. Es un parámetro. | José |
