"""Filtro de privacidad sobre las fotos de tótem/dispensor.

El Business Understanding es explícito: "el sistema no debe almacenar placas
de vehículos ni rostros de personas que aparezcan de fondo en la fotografía
de la gasolinera". Este módulo aplica un desenfoque best-effort sobre caras
detectadas antes de que cualquier imagen se persista en `datos_procesados/`.

Nota: `opencv-python-headless` no siempre trae empaquetados los clasificadores
Haar; si no están disponibles en el entorno, se degrada de forma segura
(no se cae el pipeline) y se deja constancia en el resultado.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class ResultadoPrivacidad:
    imagen: np.ndarray
    caras_difuminadas: int
    filtro_disponible: bool


def _cargar_detector_caras():
    if not hasattr(cv2, "CascadeClassifier"):
        # Build de OpenCV sin módulo objdetect (p.ej. algunas ruedas
        # headless mínimas). Se degrada sin romper el pipeline.
        return None
    try:
        ruta = f"{cv2.data.haarcascades}haarcascade_frontalface_default.xml"
        clasificador = cv2.CascadeClassifier(ruta)
    except Exception:
        return None
    if clasificador.empty():
        return None
    return clasificador


_DETECTOR = _cargar_detector_caras()


def aplicar_filtro_privacidad(imagen_rgb: np.ndarray) -> ResultadoPrivacidad:
    if _DETECTOR is None:
        return ResultadoPrivacidad(imagen_rgb, 0, filtro_disponible=False)

    gris = cv2.cvtColor(imagen_rgb, cv2.COLOR_RGB2GRAY)
    caras = _DETECTOR.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

    salida = imagen_rgb.copy()
    for (x, y, w, h) in caras:
        region = salida[y : y + h, x : x + w]
        salida[y : y + h, x : x + w] = cv2.GaussianBlur(region, (51, 51), 0)

    return ResultadoPrivacidad(salida, len(caras), filtro_disponible=True)
