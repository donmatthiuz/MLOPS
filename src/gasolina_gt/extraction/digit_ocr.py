"""Lectura de dígitos de un visor LCD de 7 segmentos.

Se implementa un clasificador de 7 segmentos "clásico" (sin dependencias de
sistema) como motor por defecto: es determinista, no requiere el binario
`tesseract` ni modelos pesados, y está hecho a la medida de paneles LED/LCD
(a diferencia de Tesseract, que está afinado para tipografías impresas).
Si el binario de `tesseract` está disponible en el sistema (p. ej. dentro
del contenedor Docker, que sí lo instala) se usa como motor alterno/mejor
esfuerzo y se compara con el resultado del clasificador de 7 segmentos.

Ver Business Understanding: "Tesseract/EasyOCR" como herramientas candidatas,
y el riesgo R6 (falla de lectura) con su mitigación de preprocesamiento +
validación estadística.
"""
from __future__ import annotations

import functools
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# Mapa de patrones de 7 segmentos -> dígito.
# Orden de segmentos: (arriba, sup-izq, sup-der, medio, inf-izq, inf-der, abajo)
_PATRONES: dict[tuple[int, ...], str] = {
    (1, 1, 1, 0, 1, 1, 1): "0",
    (0, 0, 1, 0, 0, 1, 0): "1",
    (1, 0, 1, 1, 1, 0, 1): "2",
    (1, 0, 1, 1, 0, 1, 1): "3",
    (0, 1, 1, 1, 0, 1, 0): "4",
    (1, 1, 0, 1, 0, 1, 1): "5",
    (1, 1, 0, 1, 1, 1, 1): "6",
    (1, 0, 1, 0, 0, 1, 0): "7",
    (1, 1, 1, 1, 1, 1, 1): "8",
    (1, 1, 1, 1, 0, 1, 1): "9",
}


@dataclass
class LecturaOCR:
    texto: str
    valor: float | None
    confianza: float
    motor: str


def _enderezar(binaria: np.ndarray) -> np.ndarray:
    """Corrige la ligera inclinación con la que suele quedar el visor (el
    tótem rara vez se fotografía perfectamente de frente). Sin esto, la
    segmentación por proyección de columnas mezcla dígitos vecinos porque
    su tinta ya no cae en rangos de columna separados."""
    tinta = (binaria < 128).astype(np.uint8)
    ys, xs = np.where(tinta > 0)
    if len(xs) < 20:
        return binaria
    pts = np.column_stack([xs, ys]).astype(np.float32)
    (_, _), (rw, rh), angulo = cv2.minAreaRect(pts)
    if rw < rh:
        angulo = angulo - 90
    if abs(angulo) < 0.5 or abs(angulo) > 20:
        return binaria
    centro = (binaria.shape[1] / 2, binaria.shape[0] / 2)
    M = cv2.getRotationMatrix2D(centro, angulo, 1.0)
    return cv2.warpAffine(
        binaria, M, (binaria.shape[1], binaria.shape[0]),
        borderValue=255, flags=cv2.INTER_NEAREST,
    )


def _segmentar_caracteres(binaria: np.ndarray) -> list[np.ndarray]:
    """Separa la imagen binaria (fondo blanco=255, tinta negra=0) en
    sub-imágenes por carácter, usando la proyección vertical de tinta."""
    if binaria.size == 0:
        return []
    tinta = (binaria < 128).astype(np.uint8)
    columnas = tinta.sum(axis=0)
    umbral = max(1, int(0.06 * binaria.shape[0]))
    activo = columnas > umbral

    bloques: list[tuple[int, int]] = []
    inicio = None
    for i, v in enumerate(activo):
        if v and inicio is None:
            inicio = i
        if not v and inicio is not None:
            bloques.append((inicio, i))
            inicio = None
    if inicio is not None:
        bloques.append((inicio, len(activo)))

    # Fusiona bloques separados por huecos minúsculos (ruido de anti-aliasing)
    fusionados: list[tuple[int, int]] = []
    for b in bloques:
        if fusionados and b[0] - fusionados[-1][1] < max(2, int(0.02 * binaria.shape[1])):
            fusionados[-1] = (fusionados[-1][0], b[1])
        else:
            fusionados.append(b)

    return [binaria[:, s:e] for s, e in fusionados if e - s >= 2]


def _recortar_a_tinta(caracter: np.ndarray) -> np.ndarray:
    """Recorta el carácter a la caja delimitadora real de sus píxeles de
    tinta (filas y columnas), quitando el margen blanco sobrante que deja
    la segmentación por columnas (que solo acota en X, no en Y)."""
    tinta = caracter < 128
    filas = np.where(tinta.any(axis=1))[0]
    cols = np.where(tinta.any(axis=0))[0]
    if len(filas) == 0 or len(cols) == 0:
        return caracter
    return caracter[filas[0] : filas[-1] + 1, cols[0] : cols[-1] + 1]


def _es_punto_decimal(caracter: np.ndarray) -> bool:
    h, w = caracter.shape[:2]
    if h == 0 or w == 0:
        return False
    tinta = caracter < 128
    filas_con_tinta = np.where(tinta.any(axis=1))[0]
    if len(filas_con_tinta) == 0:
        return False
    centro_vertical = filas_con_tinta.mean() / h
    ocupacion = tinta.mean()
    return centro_vertical > 0.68 and w < h * 1.3 and ocupacion > 0.15


_CANVAS_W, _CANVAS_H = 40, 64
_GROSOR = 6

# Extremos (x, y) de cada uno de los 7 segmentos sobre el lienzo _CANVAS_W x _CANVAS_H.
_SEGMENTO_COORDS: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "arriba": ((9, 5), (31, 5)),
    "sup_izq": ((6, 7), (6, 30)),
    "sup_der": ((34, 7), (34, 30)),
    "medio": ((9, 32), (31, 32)),
    "inf_izq": ((6, 34), (6, 57)),
    "inf_der": ((34, 34), (34, 57)),
    "abajo": ((9, 59), (31, 59)),
}
_ORDEN_SEGMENTOS = ["arriba", "sup_izq", "sup_der", "medio", "inf_izq", "inf_der", "abajo"]


def _dibujar_plantilla(patron: tuple[int, ...]) -> np.ndarray:
    lienzo = np.zeros((_CANVAS_H, _CANVAS_W), dtype=np.uint8)
    for activo, nombre in zip(patron, _ORDEN_SEGMENTOS):
        if activo:
            p1, p2 = _SEGMENTO_COORDS[nombre]
            cv2.line(lienzo, p1, p2, 255, _GROSOR)
    return lienzo


@functools.lru_cache(maxsize=1)
def _plantillas() -> dict[str, np.ndarray]:
    return {digito: _dibujar_plantilla(patron) for patron, digito in _PATRONES.items()}


def _clasificar_digito(caracter: np.ndarray) -> tuple[str | None, float]:
    """Clasifica un carácter comparando su forma (por solapamiento tipo IoU)
    contra plantillas de 7 segmentos dibujadas para cada dígito 0-9. Es más
    robusto que umbrales de densidad por zona fija, porque compara la forma
    completa en vez de decidir "encendido/apagado" segmento por segmento con
    un único punto de corte."""
    caracter = _recortar_a_tinta(caracter)
    h, w = caracter.shape[:2]
    if h < 4 or w < 2:
        return None, 0.0

    grid = cv2.resize(caracter, (_CANVAS_W, _CANVAS_H), interpolation=cv2.INTER_LINEAR)
    tinta = (grid < 128).astype(np.uint8)
    tinta = cv2.dilate(tinta, np.ones((3, 3), np.uint8))  # tolera trazos finos

    mejor_digito, mejor_score = None, 0.0
    for digito, plantilla in _plantillas().items():
        plantilla_bin = (plantilla > 0).astype(np.uint8)
        interseccion = np.logical_and(tinta, plantilla_bin).sum()
        union = np.logical_or(tinta, plantilla_bin).sum()
        score = interseccion / union if union else 0.0
        if score > mejor_score:
            mejor_digito, mejor_score = digito, score

    if mejor_digito is not None and mejor_score > 0.30:
        return mejor_digito, min(1.0, mejor_score * 1.4)

    return None, 0.0


class LectorSieteSegmentos:
    """Motor de OCR de 7 segmentos, sin dependencias externas."""

    nombre = "siete_segmentos"

    def leer(self, binaria: np.ndarray) -> LecturaOCR:
        binaria = _enderezar(binaria)
        caracteres = _segmentar_caracteres(binaria)
        if not caracteres:
            return LecturaOCR("", None, 0.0, self.nombre)

        texto = ""
        confianzas: list[float] = []
        for c in caracteres:
            if _es_punto_decimal(c):
                texto += "."
                confianzas.append(0.8)
                continue
            digito, conf = _clasificar_digito(c)
            if digito is None:
                texto += "?"
                confianzas.append(0.0)
            else:
                texto += digito
                confianzas.append(conf)

        valor = _texto_a_valor(texto)
        confianza = float(np.mean(confianzas)) if confianzas else 0.0
        if valor is None:
            confianza = 0.0
        return LecturaOCR(texto, valor, confianza, self.nombre)


class LectorTesseract:
    """Motor alterno usando el binario `tesseract` (si está instalado, p.ej.
    dentro del contenedor Docker). Ver Dockerfile: apt-get install tesseract-ocr.
    """

    nombre = "tesseract"

    def __init__(self) -> None:
        self.disponible = shutil.which("tesseract") is not None

    def leer(self, binaria: np.ndarray) -> LecturaOCR:
        if not self.disponible:
            return LecturaOCR("", None, 0.0, self.nombre)
        with tempfile.TemporaryDirectory() as tmp:
            img_path = Path(tmp) / "crop.png"
            cv2.imwrite(str(img_path), binaria)
            try:
                salida = subprocess.run(
                    [
                        "tesseract", str(img_path), "stdout",
                        "--psm", "7",
                        "-c", "tessedit_char_whitelist=0123456789.",
                    ],
                    capture_output=True, text=True, timeout=10,
                )
                texto = salida.stdout.strip()
            except Exception:
                return LecturaOCR("", None, 0.0, self.nombre)
        valor = _texto_a_valor(texto)
        return LecturaOCR(texto, valor, 0.6 if valor is not None else 0.0, self.nombre)


def _texto_a_valor(texto: str) -> float | None:
    limpio = texto.replace(" ", "")
    if "?" in limpio or limpio.count(".") > 1:
        return None
    try:
        valor = float(limpio)
    except ValueError:
        return None
    return valor


def leer_precio(binaria: np.ndarray, usar_tesseract_si_disponible: bool = True) -> LecturaOCR:
    """Punto de entrada único: intenta 7-segmentos y, si está disponible,
    compara con tesseract, quedándose con la lectura de mayor confianza."""
    lector_7seg = LectorSieteSegmentos()
    mejor = lector_7seg.leer(binaria)

    if usar_tesseract_si_disponible:
        lector_tess = LectorTesseract()
        if lector_tess.disponible:
            alt = lector_tess.leer(binaria)
            if alt.valor is not None and alt.confianza > mejor.confianza:
                mejor = alt
    return mejor
