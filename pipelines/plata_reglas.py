"""Reglas de la capa Plata: normalización y calidad de lecturas de precio.

Funciones puras (sin Spark ni red) para que se puedan probar con pytest y
reutilizar desde ``02_silver.py`` en Databricks.

Flujo por foto:
1. El modelo de visión lee la foto dos veces (a dos resoluciones distintas).
2. ``conciliar`` prioriza el display y el consenso; ante lecturas discordantes,
   usa la referencia mensual como desempate o respaldo identificado.
3. ``motivo_rechazo`` aplica las reglas de calidad del enunciado.
"""
from __future__ import annotations

import json
import re
from datetime import date

CATALOGO = ("super", "regular", "diesel")
TOLERANCIA_Q = 0.011  # dos lecturas "coinciden" si difieren menos de un centavo
MAX_DESVIO_REFERENCIA_Q = 3.0  # evita elegir una lectura muy alejada del promedio mensual

# Rango de precio aceptado (Q/galón). En las fotos 2023-2026 se observaron precios
# entre ~Q25 y ~Q44 (2026 trae alzas confirmadas con el display de la bomba).
# El margen filtra lecturas absurdas (galones o montos leídos como precio) sin
# descartar alzas reales. Se puede cambiar por widget.
PRECIO_MIN_Q = 15.0
PRECIO_MAX_Q = 60.0

_ALIAS = {
    "super": "super", "súper": "super", "premium": "super", "especial": "super",
    "regular": "regular", "normal": "regular", "corriente": "regular",
    "diesel": "diesel", "diésel": "diesel", "gasoil": "diesel",
}
_PREMIUM = re.compile(r"v[\s-]?power|supreme|ultra|racing|98", re.IGNORECASE)


def normalizar_combustible(combustible: str | None, nombre_en_rotulo: str | None = None) -> str:
    """Devuelve 'super', 'regular', 'diesel' u 'otro'.

    Las gasolinas premium (V-Power, Supreme+...) no forman parte del catálogo
    del MEM y se marcan como 'otro' aunque el modelo diga 'super'.
    """
    nombre = (nombre_en_rotulo or "").strip()
    if nombre and _PREMIUM.search(nombre):
        return "otro"
    for texto in ((combustible or ""), nombre):
        t = texto.strip().lower()
        if t in _ALIAS:
            return _ALIAS[t]
        for alias, valor in _ALIAS.items():
            if re.search(rf"\b{alias}\b", t):
                return valor
    return "otro"


def normalizar_modalidad(valor: str | None) -> str:
    t = (valor or "").strip().lower().replace("_", " ")
    if "auto" in t:
        return "autoservicio"
    if "servicio" in t or "completo" in t or "full" in t:
        return "servicio completo"
    return "no_especificada"


def normalizar_ubicacion(estacion: str | None, ubicacion: str | None) -> str:
    partes = [p.strip() for p in (estacion, ubicacion) if p and p.strip()]
    return " - ".join(partes) if partes else "desconocida"


def parsear_respuesta(texto: str | None) -> dict | None:
    """Extrae el primer objeto JSON de la respuesta del modelo (tolera ```json)."""
    if not texto:
        return None
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fin <= inicio:
        return None
    try:
        datos = json.loads(texto[inicio:fin + 1])
    except json.JSONDecodeError:
        return None
    return datos if isinstance(datos, dict) else None


def a_precio(valor) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    try:
        return round(float(str(valor).replace("Q", "").replace(",", ".").strip()), 2)
    except ValueError:
        return None


def precio_desde_display(monto_q, galones) -> float | None:
    """Precio por galón deducido del display de la bomba (p. ej. Q100.00 / 3.664 gal = Q27.29)."""
    monto, gal = a_precio(monto_q), None
    try:
        gal = float(galones) if galones is not None else None
    except (TypeError, ValueError):
        gal = None
    if not monto or not gal or gal <= 0:
        return None
    return round(monto / gal, 2)


def lecturas_por_combustible(respuesta: dict | None) -> dict[str, float | None]:
    """{combustible_normalizado: precio} de una respuesta. Ignora 'otro'."""
    salida: dict[str, float | None] = {}
    for item in (respuesta or {}).get("precios") or []:
        if not isinstance(item, dict):
            continue
        comb = normalizar_combustible(item.get("combustible"), item.get("nombre_en_rotulo"))
        if comb == "otro" or comb in salida:
            continue
        salida[comb] = a_precio(item.get("precio_q_galon"))
    return salida


def conciliar(a: float | None, b: float | None, display: float | None,
             referencia: float | None = None) -> tuple[float | None, str]:
    """Combina dos lecturas independientes del mismo visor.

    El display y el consenso tienen prioridad. Si hay desacuerdo, elige la
    lectura más cercana al promedio mensual, siempre que no difiera más de Q3.
    Si ninguna lectura es confiable, usa el promedio mensual identificado.
    """
    if display is not None:
        for valor in (a, b):
            if valor is not None and abs(valor - display) < TOLERANCIA_Q:
                return display, "display_bomba"
    if a is not None and b is not None and abs(a - b) < TOLERANCIA_Q:
        return a, "consenso"
    if referencia is not None:
        candidatos = [v for v in (a, b) if v is not None and abs(v - referencia) <= MAX_DESVIO_REFERENCIA_Q]
        if candidatos:
            distancias = [(abs(v - referencia), v) for v in candidatos]
            distancias.sort()
            if len(distancias) == 1 or distancias[0][0] < distancias[1][0]:
                return distancias[0][1], "referencia_desempate"
        return referencia, "referencia_mensual"
    if a is None and b is None:
        return None, "sin_lectura"
    return None, "lecturas_inconsistentes"


def ajustar_orden_con_referencia(finales: dict[str, tuple[float, str]],
                                referencias: dict[str, float | None]) -> dict[str, tuple[float, str]] | None:
    """Sustituye por referencia el precio que rompe súper >= regular.

    Conserva una lectura cercana a la referencia si la otra es un claro valor
    atípico. Si ambas siguen invertidas, usa ambas referencias. Sin referencias
    suficientes, deja el rechazo habitual de las dos lecturas.
    """
    if not orden_incoherente({c: v[0] for c, v in finales.items()}):
        return finales
    if any(referencias.get(c) is None for c in ("super", "regular")):
        return None
    ajustadas = dict(finales)
    for comb in ("super", "regular"):
        precio, _ = finales[comb]
        ref = referencias[comb]
        if abs(precio - ref) > MAX_DESVIO_REFERENCIA_Q:
            ajustadas[comb] = (ref, "referencia_mensual_orden")
    if orden_incoherente({c: v[0] for c, v in ajustadas.items()}):
        for comb in ("super", "regular"):
            ajustadas[comb] = (referencias[comb], "referencia_mensual_orden")
    return ajustadas


def anio_de_ruta(ruta: str) -> int | None:
    """Año de la carpeta de la foto (p. ej. .../img/2024/IMG_1.HEIC -> 2024)."""
    m = re.search(r"/((?:19|20)\d{2})/[^/]+$", ruta or "")
    return int(m.group(1)) if m else None


TOLERANCIA_CARPETA_DIAS = 90  # las carpetas por año del catedrático incluyen fotos de fin del año anterior


def _cerca_del_anio(fecha: date, anio: int) -> bool:
    """True si la fecha cae en el año de la carpeta, con tolerancia en los bordes.

    Ej.: img/2023/ contiene una foto del 2022-12-14 e img/2024/ una del 2023-11-13.
    """
    inicio, fin = date(anio, 1, 1), date(anio, 12, 31)
    return (inicio - fecha).days <= TOLERANCIA_CARPETA_DIAS and (fecha - fin).days <= TOLERANCIA_CARPETA_DIAS


def motivo_rechazo(fecha: date | None, combustible: str, precio: float | None, hoy: date,
                   precio_min: float = PRECIO_MIN_Q, precio_max: float = PRECIO_MAX_Q,
                   anio_carpeta: int | None = None) -> str | None:
    """Reglas de calidad del enunciado. None si la lectura es válida.

    La fecha viene del EXIF de la foto. No se usa modificationTime porque es la
    fecha en que se subió el archivo a S3, no la del precio.
    """
    if fecha is None:
        return "fecha_desconocida"
    if fecha > hoy:
        return "fecha_futura"
    if anio_carpeta is not None and not _cerca_del_anio(fecha, anio_carpeta):
        return "fecha_no_coincide_con_carpeta"
    if combustible not in CATALOGO:
        return "combustible_fuera_catalogo"
    if precio is None:
        return "precio_ilegible"
    if not precio_min <= precio <= precio_max:
        return "precio_fuera_rango"
    return None


def orden_incoherente(precios: dict[str, float | None]) -> bool:
    """En Guatemala la súper siempre cuesta más que la regular."""
    s, r = precios.get("super"), precios.get("regular")
    return s is not None and r is not None and s < r
