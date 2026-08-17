"""Scraper del precio real de referencia de gasolina/diésel en Guatemala.

Fuente: globalpetrolprices.com, que a su vez cita como fuente oficial al
Ministerio de Energía y Minas (MEM) de Guatemala y se actualiza semanalmente
(mismo criterio de frecuencia que D2 en el Business Understanding). Se usa
en la etapa de *testing* para contrastar contra las predicciones/recomendación
del modelo con un precio real, no fabricado.

Si no hay red disponible (p. ej. corriendo pruebas offline/CI), se cae a un
fixture local (`tests/fixtures/precio_referencia_offline.json`) para que la
suite de tests siga siendo determinista.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from ..config import load_config, resolve_path

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; gasolina-gt-bot/1.0)"}


@dataclass
class PrecioReferencia:
    combustible: str
    precio_gtq_por_galon: float
    precio_gtq_por_litro: float
    variacion_mensual_pct: float | None
    fuente: str
    obtenido_en: str
    es_offline_fixture: bool


def _parsear_tabla_gpp(html: str) -> tuple[float, float]:
    """Extrae (GTQ/litro, GTQ/galón) de la tabla superior de la página."""
    m_litro = re.search(r"GTQ.*?align=\"center\">([\d.]+)</td>\s*<td[^>]*align=\"center\">([\d.]+)</td>", html, re.S)
    if not m_litro:
        raise ValueError("No se pudo parsear la tabla de precios de globalpetrolprices")
    litro, galon = float(m_litro.group(1)), float(m_litro.group(2))
    return litro, galon


def _parsear_variacion_mensual(html: str) -> float | None:
    m = re.search(r"Hace un mes.*?align=\"center\">([\d.]+)</td>", html, re.S)
    if not m:
        return None
    return float(m.group(1))


def _obtener_online(combustible: str, cfg: dict) -> PrecioReferencia:
    scraping_cfg = cfg["scraping"]
    url = scraping_cfg["urls"][combustible]
    resp = requests.get(url, headers=_HEADERS, timeout=scraping_cfg["timeout_segundos"])
    resp.raise_for_status()
    litro, galon = _parsear_tabla_gpp(resp.text)
    hace_un_mes = _parsear_variacion_mensual(resp.text)
    variacion = None
    if hace_un_mes and hace_un_mes > 0:
        variacion = round((litro - hace_un_mes) / hace_un_mes * 100, 2)
    return PrecioReferencia(
        combustible=combustible,
        precio_gtq_por_galon=galon,
        precio_gtq_por_litro=litro,
        variacion_mensual_pct=variacion,
        fuente=url,
        obtenido_en=datetime.now(timezone.utc).isoformat(),
        es_offline_fixture=False,
    )


def _obtener_offline(combustible: str, cfg: dict) -> PrecioReferencia:
    fixture_path = resolve_path(cfg["scraping"]["fixture_offline"])
    with open(fixture_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    entrada = data[combustible]
    return PrecioReferencia(
        combustible=combustible,
        precio_gtq_por_galon=entrada["precio_gtq_por_galon"],
        precio_gtq_por_litro=entrada["precio_gtq_por_litro"],
        variacion_mensual_pct=entrada.get("variacion_mensual_pct"),
        fuente="fixture_offline",
        obtenido_en=datetime.now(timezone.utc).isoformat(),
        es_offline_fixture=True,
    )


def obtener_precio_referencia(combustible: str = "gasolina", config: dict | None = None) -> PrecioReferencia:
    """Punto de entrada único. `combustible` es "gasolina" (proxy de Regular)
    o "diesel". Intenta scrapear en vivo; si falla por cualquier motivo de
    red, cae de forma transparente al fixture offline."""
    cfg = config or load_config()
    try:
        return _obtener_online(combustible, cfg)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Scraping en vivo falló (%s); usando fixture offline.", exc)
        return _obtener_offline(combustible, cfg)
