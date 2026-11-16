# Capa Oro: notas para el informe y la defensa

**Qué predice.** Si el precio de cada combustible (súper, regular, diésel) sube, baja o se mantiene la semana siguiente. La semana va de martes a lunes.

**Decisiones**

- **Umbral:** un cambio de Q0.10 o menos cuenta como «se mantiene». Es un parámetro; se eligió porque los precios cambian por centavos y no queremos llamar «alza» a un redondeo.
- **Huecos:** solo comparo una semana con la semana inmediatamente anterior. Si faltan fotos de esa semana, no hay variación (queda vacía), en vez de comparar con un precio de hace meses. Lo mismo vale para los rezagos.
- **Variables:** cómo cambió el precio en las últimas 4 semanas, el promedio de las últimas 4 semanas, la diferencia súper–diésel y el petróleo WTI semanal. Todas usan solo datos de esa semana o anteriores, así que el modelo no ve el futuro.
- **Modelo:** regresión logística y árbol de decisión, un solo modelo para los tres combustibles (el combustible es una variable más). Por combustible hay muy pocas semanas seguidas.
- **Validación:** las últimas 4 semanas con datos se guardan para probar y el modelo nunca las ve al entrenar. Entre los dos modelos se elige con semanas anteriores a esas, y la prueba final solo compara el elegido contra la línea base.
- **Línea base:** «la dirección de la semana siguiente será igual a la de esta semana».
- **Regla final:** se usa el modelo solo si supera a la línea base en F1 macro y no tiene menos accuracy. Si no la supera, usamos la línea base y lo decimos.

**Limitaciones por pocos datos**

- Cada ejemplo necesita tres semanas seguidas con fotos. Con huecos entre semanas quedan muy pocos ejemplos, y con menos de 20 (o 12 para entrenar) **no se entrena**: se predice con la línea base y las métricas dicen «pocos datos». No es un fallo, es una decisión.
- Con unas pocas semanas de prueba, una sola semana cambia mucho el porcentaje de acierto. Por eso los resultados deben leerse como orientativos y no como prueba de que el modelo es bueno.
- Si no hay semanas suficientes para comparar los modelos antes de la prueba, se usa la regresión logística por defecto. Es una limitación y se reporta.
- Las probabilidades solo existen cuando se usa un modelo; la línea base no las calcula.
- Cada combustible siempre tiene su pronóstico, aunque su última semana no tenga semana anterior. En ese caso se usa la última dirección conocida (o «se mantiene» si nunca hubo una) y se marca como `linea_base_respaldo`: es un supuesto, no una medición.

**Cómo correrlo.** Con Bronce y Plata ya ejecutados, correr `03_gold.py` (tarea del Job) o `gold(settings())` en un notebook. Los parámetros (umbral, semanas de prueba, experimento de MLflow, usar WTI) se pasan como widgets o argumentos. Resultados: tablas `workspace.equipo7.gold_*`, experimento `/Shared/equipo7-gasolina` en MLflow y la fila más reciente de `gold_metricas_modelo`.
