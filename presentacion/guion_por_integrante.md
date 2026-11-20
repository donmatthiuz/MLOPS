# Guion por integrante · Gasolina GT · Equipo 7

**Orden:** José (1–2) → Mathew (3–4) → Gustavo (5) → Carlos (6) → José (7–8) → Mathew (9) → Josué (10) → Mathew y Josué (11, demo) → todos (12–13)

---

## José Gramajo · Diapositivas 1–2 (≈1 min 20 s)
**1. Portada**
> "Buenas tardes, somos el equipo 7 y les presentamos Gasolina GT: un sistema que, a partir de fotos de los precios en la gasolinera, predice si el precio de cada combustible sube, baja o se mantiene la semana siguiente, y lo publica en una API."

**2. El problema**
> "Cada martes el Ministerio de Energía y Minas publica los precios de referencia de súper, regular y diésel, vigentes de martes a lunes. Esos precios siguen al petróleo internacional y a veces a subsidios. A hogares, transportistas y negocios les sirve saber hacia dónde va el precio para decidir cuándo llenar el tanque. Nuestra pregunta es: para cada combustible, ¿la próxima semana sube, baja o se mantiene? Le paso la palabra a Mathew."

## Mathew Cordero · Diapositivas 3–4 (≈2 min)
**3. La solución**
> "La solución es un pipeline de punta a punta: la foto entra a Bronce, se limpia en Plata, se convierte en indicadores y predicción en Oro, y se publica en una API. Usamos tres plataformas: S3 para guardar cada capa, Databricks para procesar y entrenar, y DigitalOcean para la API."

**4. Arquitectura**
> "De izquierda a derecha: las fotos del catedrático y el precio del petróleo WTI entran al Job de Databricks. Cada tarea escribe en su propio bucket de S3 y la siguiente lee de ahí; esa es la arquitectura medallón. Oro registra cada ejecución en MLflow, y la API del Droplet solo lee la capa Oro. El equipo entra al servidor por SSH y el usuario final consulta por HTTP. Le paso a Gustavo."

## Gustavo Cruz · Diapositiva 5 (≈1 min)
**5. Bronce**
> "En Bronce guardamos las fotos tal como llegan. Spark las lee con binaryFile a través de la external location, sin llaves en el código, y las guarda en Delta con columnas de auditoría. La carga es incremental: un MERGE por ruta evita duplicados, y en cada corrida verificamos que haya tantas filas como fotos: 110 y cero duplicados. Además cargamos como fuente complementaria más de diez mil días del precio del petróleo WTI. Le paso a Carlos."

## Carlos Valladares · Diapositiva 6 (≈1 min 30 s)
**6. Plata**
> "En Plata convertimos la foto en un precio. El OCR tradicional no servía para todas las bombas, así que usamos el modelo de visión Llama 4 Maverick dentro de Databricks. Cada foto se lee dos veces y aceptamos la lectura si coincide con monto entre galones del display o si las dos lecturas coinciden. Aplicamos 8 reglas de calidad y lo que falla va a una tabla de rechazos con su motivo. Cuando las lecturas no cuadran, usamos como respaldo el promedio mensual del MEM. Hoy hay 289 lecturas válidas y 12 rechazadas. En la revisión manual de 24 fotos, el 76.5 % de lo que guardamos está bien. El respaldo mensual nos sirve para entrenar, pero nunca para medir el modelo. Le paso a José."

## José Gramajo · Diapositivas 7–8 (≈2 min 20 s)
**7. Oro**
> "En Oro calculamos los indicadores por semana, de martes a lunes como el MEM: precio promedio, variación contra la semana anterior y la dirección, con un umbral de diez centavos para no llamar alza a un redondeo. Generamos seis tablas Delta, todas con comentarios en Unity Catalog. Y si falta la semana anterior, la variación queda vacía: no comparamos contra un precio de hace meses."

**8. El modelo**
> "Para predecir la dirección de la semana siguiente usamos variables que solo miran al pasado: variaciones recientes, promedio móvil, la diferencia súper–diésel y el WTI. Comparamos regresión logística y árbol de decisión con validación temporal, nunca aleatoria, contra una línea base: repetir la dirección de la semana anterior. El resultado honesto es que tenemos 49 ejemplos, pero solo 4 semanas reales para probar: la logística empata en accuracy y pierde en F1, así que el sistema publica la línea base y lo registra en MLflow. No es un error del código, es falta de semanas seguidas con fotos. Le paso a Mathew."

## Mathew Cordero · Diapositiva 9 (≈50 s)
**9. Orquestación**
> "Todo corre en un Job de Databricks con tres tareas encadenadas: Bronce, Plata y Oro. Como Free Edition solo tiene cómputo serverless, no hay que encender clusters ni configurar autoterminación, y se paga solo el uso. El Job está programado los martes a las 9:40, avisa por correo si falla y recibe las rutas y el umbral como parámetros. El historial tiene 18 ejecuciones, 16 exitosas. Le paso a Josué."

## Josué Say · Diapositiva 10 (≈50 s)
**10. API**
> "La API es FastAPI dentro de Docker en un Droplet de DigitalOcean, en el puerto 8007, y se reinicia sola si se cae. Lee la capa Oro directamente de S3 con credenciales de solo lectura que no están en Git. Tiene cinco endpoints: salud, precio actual, histórico, predicción y métricas del modelo, más una página web. Los invitamos a escanear el código QR: abre la predicción de la súper en su teléfono, y pueden cambiar súper por regular o diésel."

## Mathew Cordero y Josué Say · Diapositiva 11 · Demo (≈5 min)
- **Mathew:** "Ahora vamos a ejecutar el Job." → Run now, mostrar las tres tareas; abrir la salida de Oro y el experimento en MLflow.
- **Josué:** "Y aquí consultamos el resultado en la API." → abrir `http://159.65.111.14:8007/`, mostrar precios, histórico y la sección Modelo; luego `/prediccion?combustible=super`.
- **Plan B:** si algo falla, mostrar las capturas de `docs/job/evidencia`.

## Todo el equipo · Diapositiva 12 (≈40 s, una frase cada uno)
- **José:** "El dato manda: con 4 semanas de prueba ningún modelo puede demostrar que gana, y preferimos decirlo a inflar un número."
- **Carlos:** "Validar en cada capa y guardar los rechazos con su motivo hace visibles los errores."
- **Gustavo:** "Con MERGE en todas las capas, repetir el Job no duplica nada."
- **Mathew / Josué:** "Con más tiempo cargaríamos el histórico semanal del MEM para tener cientos de ejemplos reales."

## Diapositiva 13 · Cierre (José)
> "Muchas gracias. Quedamos atentos a sus preguntas."

---
### Si preguntan…
| Pregunta | Responde | Respuesta corta |
|---|---|---|
| ¿Por qué el modelo no le gana a la línea base? | José | Solo hay 4 semanas reales de prueba; con eso el resultado es casi azar. Hay señal: el WTI anticipó el 74 % de las bajas, pero no se puede demostrar con tan pocos casos. |
| ¿Por qué validación temporal? | José | Mezclar semanas filtraría información del futuro. |
| ¿Qué tan confiable es la extracción? | Carlos | 76.5 % de precisión en lo guardado; descartamos lo dudoso. |
| ¿Fotos repetidas? | Gustavo | MERGE por ruta: no se duplican. |
| ¿Por qué serverless? | Mathew | Free Edition no ofrece clusters clásicos; serverless cobra solo el uso. |
| ¿Credenciales? | Josué | External locations en Databricks y `.env` fuera de Git en el Droplet. |
