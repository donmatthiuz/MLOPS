"""COMMENT de Unity Catalog para cada tabla y columna Oro."""
from __future__ import annotations

COMENTARIOS_TABLA: dict[str, str] = {
    "precio_semanal": "Precio promedio, mínimo y máximo por semana (martes a lunes) y combustible, calculado desde Plata.",
    "variacion_semanal": "Cambio del precio promedio de cada semana contra la semana calendario inmediatamente anterior, con su etiqueta de dirección (sube, baja o se_mantiene).",
    "features_modelo": "Variables para predecir la dirección de la semana siguiente, una fila por semana y combustible. La última semana no tiene objetivo porque es la que se predice.",
    "predicciones": "Predicción de la dirección del precio por semana y combustible. tipo=pronostico es la predicción hacia adelante; tipo=backtest es la predicción sobre semanas de prueba que ya ocurrieron.",
    "metricas_modelo": "Una fila por ejecución de Oro con las métricas del modelo y de la línea base «se repite la dirección de la semana anterior», medidas en semanas que el modelo no usó para entrenar.",
    "metricas_combustible": "Backtest temporal por combustible con modelos fijos; cada predicción usa solo etiquetas de semanas anteriores y cada modelo se evalúa en los mismos casos observados.",
}

_BASE = {
    "semana": "Martes con que empieza la semana de martes a lunes.",
    "combustible": "Tipo de combustible: super, regular o diesel.",
    "precio_promedio": "Promedio del precio en quetzales por galón de las lecturas de la semana.",
    "_generado_en": "Fecha y hora UTC en que se calculó la fila.",
}

COLUMNAS: dict[str, dict[str, str]] = {
    "precio_semanal": {
        **{k: _BASE[k] for k in ("semana", "combustible", "precio_promedio")},
        "precio_minimo": "Precio mínimo de la semana en Q por galón.",
        "precio_maximo": "Precio máximo de la semana en Q por galón.",
        "n_lecturas": "Número de lecturas de Plata que entran en la semana.",
        "_generado_en": _BASE["_generado_en"],
    },
    "variacion_semanal": {
        **{k: _BASE[k] for k in ("semana", "combustible", "precio_promedio")},
        "precio_minimo": "Precio mínimo de la semana en Q por galón.",
        "precio_maximo": "Precio máximo de la semana en Q por galón.",
        "n_lecturas": "Número de lecturas de Plata que entran en la semana.",
        "precio_anterior": "Precio promedio de la semana exactamente 7 días antes; nulo si esa semana no existe.",
        "diferencia_q": "precio_promedio menos precio_anterior, en Q por galón; nulo si falta la semana anterior.",
        "diferencia_pct": "diferencia_q como porcentaje del precio anterior; nulo si falta la semana anterior.",
        "direccion": "sube si diferencia_q > umbral_q, baja si < -umbral_q, se_mantiene en otro caso; nulo si falta la semana anterior.",
        "semana_anterior_disponible": "Verdadero si existe la semana calendario anterior y por eso se pudo calcular la variación.",
        "umbral_q": "Umbral en Q usado para etiquetar la dirección en esta ejecución.",
        "_generado_en": _BASE["_generado_en"],
    },
    "features_modelo": {
        **{k: _BASE[k] for k in ("semana", "combustible", "precio_promedio")},
        "variacion_lag_1": "Variación en Q de la última semana conocida (semana t contra t-7 días); nula si falta alguna.",
        "variacion_lag_2": "Variación en Q de la semana t-7 días; nula si esa semana o su anterior no existen.",
        "variacion_lag_3": "Variación en Q de la semana t-14 días; nula si no existe.",
        "variacion_lag_4": "Variación en Q de la semana t-21 días; nula si no existe.",
        "promedio_movil_4": "Promedio del precio de las semanas existentes entre t-21 días y t; nulo con menos de 2 semanas.",
        "dif_super_diesel": "Precio promedio de súper menos el de diésel en la misma semana; nulo si falta alguno.",
        "wti_semanal": "Precio promedio semanal (martes a lunes) del petróleo WTI en USD por barril; nulo si no hay dato o no se usa.",
        "wti_variacion": "wti_semanal menos el de la semana anterior; nulo si falta alguno.",
        "direccion_actual": "Dirección de la semana t contra la anterior; es lo que predice la línea base.",
        "direccion_siguiente": "Objetivo: dirección de la semana t+7 días; nulo si esa semana aún no existe.",
        "_generado_en": _BASE["_generado_en"],
    },
    "predicciones": {
        "semana": "Martes de la semana que se predice (la semana siguiente a los datos usados).",
        "combustible": _BASE["combustible"],
        "tipo": "pronostico: predicción hacia adelante, no se reescribe una vez conocido el resultado; backtest: predicción sobre una semana de prueba que ya ocurrió.",
        "prediccion": "Dirección predicha: sube, baja o se_mantiene.",
        "probabilidad": "Probabilidad del modelo para la dirección predicha, entre 0 y 1; nula cuando se usa la línea base o su respaldo, que no calculan probabilidades.",
        "modelo": "Quién hizo la predicción: regresion_logistica, arbol_decision, linea_base (repite la dirección de la semana) o linea_base_respaldo (esa semana no tenía dirección actual: se usó la última dirección conocida del combustible o, si no existe, se_mantiene).",
        "direccion_real": "Dirección observada de esa semana; nula hasta que llegan sus fotos.",
        "_generado_en": _BASE["_generado_en"],
    },
    "metricas_modelo": {
        "run_id_mlflow": "Identificador de la ejecución en MLflow; nulo si MLflow no estuvo disponible.",
        "modelo_elegido": "Modelo que genera las predicciones: regresion_logistica, arbol_decision o linea_base.",
        "usa_linea_base": "Verdadero si se usa la línea base porque el modelo no la superó o hubo pocos datos.",
        "modo_pocos_datos": "Verdadero si no hubo ejemplos suficientes para entrenar y se predijo con la línea base.",
        "motivo": "Explicación en texto de por qué se eligió ese modelo.",
        "candidato": "Mejor modelo según la validación temporal dentro de train; nulo en modo pocos datos.",
        "validado_en_train": "Verdadero si hubo semanas suficientes para comparar los modelos dentro de train.",
        "cv_f1_regresion_logistica": "F1 macro promedio de la regresión logística en la validación temporal dentro de train.",
        "cv_f1_arbol_decision": "F1 macro promedio del árbol de decisión en la validación temporal dentro de train.",
        "n_ejemplos": "Ejemplos etiquetados disponibles para entrenar: incluye semanas con respaldo mensual cuando se usa en Plata.",
        "n_train": "Ejemplos usados para entrenar (semanas más antiguas).",
        "n_test": "Ejemplos de prueba; en Databricks usan solo lecturas observadas. En modo pocos datos son todos los ejemplos evaluados con la línea base.",
        "semana_train_inicio": "Primera semana del entrenamiento.",
        "semana_train_fin": "Última semana del entrenamiento.",
        "semana_test_inicio": "Primera semana de prueba.",
        "semana_test_fin": "Última semana de prueba.",
        "accuracy_modelo": "Exactitud (accuracy) del modelo candidato: fracción de semanas de prueba cuya dirección acertó; entre 0 y 1.",
        "f1_macro_modelo": "F1 macro del modelo candidato en las semanas de prueba: promedio del F1 de sube, baja y se_mantiene, sin favorecer a la clase más frecuente; entre 0 y 1.",
        "accuracy_linea_base": "Exactitud (accuracy) de la línea base «se repite la dirección de la semana anterior» sobre las mismas semanas de prueba.",
        "f1_macro_linea_base": "F1 macro de la línea base sobre las mismas semanas de prueba; el modelo debe superarlo para usarse.",
        "umbral_q": "Umbral en Q para etiquetar sube, baja o se_mantiene.",
        "semanas_test": "Número de semanas reservadas para la prueba.",
        "usa_wti": "Verdadero si el petróleo WTI se incluyó como variable.",
        "_generado_en": _BASE["_generado_en"],
    },
    "metricas_combustible": {
        "combustible": _BASE["combustible"],
        "modelo": "Modelo evaluado: linea_base, regresion_logistica o arbol_decision con parámetros fijos.",
        "n_test": "Cantidad de triples observados evaluados con entrenamiento anterior suficiente; cero significa que no se pudo medir.",
        "accuracy": "Fracción de direcciones acertadas; nula cuando n_test es cero.",
        "f1_macro": "F1 macro en los mismos casos que los otros modelos de este combustible; nulo cuando n_test es cero.",
        "semana_inicio": "Primera semana de las variables evaluadas.",
        "semana_fin": "Última semana de las variables evaluadas.",
        "_generado_en": _BASE["_generado_en"],
    },
}


def _literal(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("'", "''")


def sentencias_comentarios(tabla_completa: str, nombre: str) -> list[str]:
    """COMMENT ON TABLE + un ALTER COLUMN … COMMENT por columna."""
    sentencias = [f"COMMENT ON TABLE {tabla_completa} IS '{_literal(COMENTARIOS_TABLA[nombre])}'"]
    for columna, texto in COLUMNAS[nombre].items():
        sentencias.append(f"ALTER TABLE {tabla_completa} ALTER COLUMN {columna} COMMENT '{_literal(texto)}'")
    return sentencias
