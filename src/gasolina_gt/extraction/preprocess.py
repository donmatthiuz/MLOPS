"""Preprocesamiento OpenCV: localizar el visor LCD dentro de un panel y
dejarlo listo (binarizado, contraste realzado) para el OCR de dígitos.

Corresponde a la etapa "Preprocesamiento de imagen con OpenCV (contraste,
filtros morfológicos)" descrita en el Business Understanding, sección
Enfoque de modelado / Herramientas y técnicas.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class RecorteLCD:
    imagen_gris_binaria: np.ndarray
    imagen_recorte_original: np.ndarray
    encontrado_automaticamente: bool


def localizar_visor_lcd(panel_rgb: np.ndarray) -> RecorteLCD:
    """Dentro del recorte (generoso) de un panel de precio, ubica el
    rectángulo retroiluminado del visor LCD (blanco/azulado, alto brillo,
    bajo-moderada saturación) mediante un umbral HSV + contornos.

    Si no se encuentra un candidato plausible, cae a una caja relativa fija
    (banda superior-centrada del panel) para nunca fallar duro — coherente
    con el riesgo R6 del negocio (falla de lectura por reflejos/parpadeo).
    """
    h, w = panel_rgb.shape[:2]
    hsv = cv2.cvtColor(panel_rgb, cv2.COLOR_RGB2HSV)
    banda_superior = hsv[: int(h * 0.72), :]

    mask = cv2.inRange(banda_superior, (0, 0, 140), (180, 120, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 9), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    mejor = None
    for c in cnts:
        x, y, cw, ch = cv2.boundingRect(c)
        if ch == 0:
            continue
        aspecto = cw / ch
        area = cw * ch
        if 1.5 < aspecto < 5.0 and area > 0.012 * w * h:
            if mejor is None or area > mejor[4]:
                mejor = (x, y, cw, ch, area)

    encontrado = mejor is not None
    if mejor is None:
        x, y = int(w * 0.10), int(h * 0.08)
        cw, ch = int(w * 0.80), int(h * 0.32)
    else:
        x, y, cw, ch, _ = mejor
        pad = int(0.15 * ch)
        x, y = max(0, x - pad), max(0, y - pad)
        cw, ch = min(w - x, cw + 2 * pad), min(h - y, ch + 2 * pad)

    recorte = panel_rgb[y : y + ch, x : x + cw]
    recorte = _recortar_al_interior_del_visor(recorte)
    binaria = _binarizar_para_ocr(recorte)
    return RecorteLCD(binaria, recorte, encontrado)


def _recortar_al_interior_del_visor(recorte_rgb: np.ndarray) -> np.ndarray:
    """Segunda pasada: dentro del recorte (que puede incluir el bisel negro
    del visor por el margen añadido), ubica de nuevo la región retroiluminada
    y recorta exactamente a su caja, sin margen — así el bisel oscuro no
    contamina la segmentación de caracteres."""
    h, w = recorte_rgb.shape[:2]
    if h < 4 or w < 4:
        return recorte_rgb
    hsv = cv2.cvtColor(recorte_rgb, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, (0, 0, 140), (180, 120, 255))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return recorte_rgb
    x, y, cw, ch = cv2.boundingRect(max(cnts, key=cv2.contourArea))
    if cw * ch < 0.25 * w * h:
        return recorte_rgb
    margen = max(1, int(0.04 * ch))
    x0, y0 = max(0, x + margen), max(0, y + margen)
    x1, y1 = min(w, x + cw - margen), min(h, y + ch - margen)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return recorte_rgb
    return recorte_rgb[y0:y1, x0:x1]


def _binarizar_para_ocr(recorte_rgb: np.ndarray) -> np.ndarray:
    if recorte_rgb.size == 0:
        return np.zeros((10, 10), dtype=np.uint8)
    gris = cv2.cvtColor(recorte_rgb, cv2.COLOR_RGB2GRAY)
    # Sobre-muestreo: los dígitos de 7 segmentos ganan mucho con más resolución.
    factor = max(1, int(300 / max(1, gris.shape[0])))
    if factor > 1:
        gris = cv2.resize(gris, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
    gris = cv2.bilateralFilter(gris, 7, 40, 40)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gris = clahe.apply(gris)
    _, binaria = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Los dígitos LCD suelen ser oscuros sobre fondo claro; si quedó invertido
    # (mayoría de píxeles oscuros), se voltea para estandarizar dígito=negro.
    if (binaria == 0).mean() > 0.6:
        binaria = 255 - binaria
    return _quitar_manchas_que_tocan_el_borde(binaria)


def _quitar_manchas_que_tocan_el_borde(binaria: np.ndarray) -> np.ndarray:
    """El recorte del visor rara vez queda perfectamente rectangular (el
    tótem se fotografía con cierta inclinación), así que quedan triángulos
    de bisel/fondo oscuro en las esquinas. En vez de perseguir ese borde
    irregular, se ubica el componente BLANCO más grande (el fondo
    retroiluminado del visor), se calcula su envolvente convexa, y todo lo
    que quede fuera de esa envolvente se fuerza a blanco. Los dígitos (negros)
    quedan intactos porque son "huecos" dentro del componente blanco, no
    tocan el borde de la envolvente."""
    fondo = (binaria > 128).astype(np.uint8)
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(fondo, connectivity=4)
    if n <= 1:
        return binaria
    idx_mayor = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    componente = (etiquetas == idx_mayor).astype(np.uint8)
    cnts, _ = cv2.findContours(componente, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return binaria
    hull = cv2.convexHull(max(cnts, key=cv2.contourArea))
    mascara_hull = np.zeros_like(binaria)
    cv2.fillConvexPoly(mascara_hull, hull, 255)  # type: ignore[arg-type]
    limpio = binaria.copy()
    limpio[mascara_hull == 0] = 255
    return limpio
