"""Aumento de datos de imagen para la etapa de extracción por visión.

Con solo 5 fotografías piloto no hay margen para medir cuán robusto es el
extractor ante variaciones de iluminación, ángulo o ruido de cámara — algo
que el propio Business Understanding anticipa como riesgo (R6: "Falla de
lectura por resplandor del sol, paneles LED parpadeantes o mala calidad de
imagen"). Este módulo genera variantes sintéticas de cada imagen real
(rotación leve, brillo/contraste, ruido gaussiano y jitter de perspectiva)
para ampliar la muestra usada en las pruebas de robustez del extractor
(ver tests/integration/test_extraccion_robustez.py).
"""
from __future__ import annotations

import numpy as np
import cv2


def _rotar(img: np.ndarray, grados: float) -> np.ndarray:
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), grados, 1.0)
    return cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)


def _brillo_contraste(img: np.ndarray, brillo: float, contraste: float) -> np.ndarray:
    out = img.astype(np.float32) * contraste + (brillo - 1.0) * 128
    return np.clip(out, 0, 255).astype(np.uint8)


def _ruido_gaussiano(img: np.ndarray, sigma: float, rng: np.random.Generator) -> np.ndarray:
    ruido = rng.normal(0, sigma, img.shape)
    return np.clip(img.astype(np.float32) + ruido, 0, 255).astype(np.uint8)


def _jitter_perspectiva(img: np.ndarray, max_px: int, rng: np.random.Generator) -> np.ndarray:
    h, w = img.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = src + rng.uniform(-max_px, max_px, src.shape).astype(np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)


def generar_variantes(imagen_rgb: np.ndarray, n: int, config: dict, semilla: int = 0) -> list[np.ndarray]:
    """Genera `n` variantes aumentadas de una imagen (recorte de panel o
    imagen completa), combinando rotación, brillo/contraste, ruido y
    perspectiva según los rangos definidos en config/config.yaml."""
    aug_cfg = config["augmentation"]
    rng = np.random.default_rng(semilla)
    variantes = []
    for _ in range(n):
        out = imagen_rgb.copy()
        grados = rng.uniform(-aug_cfg["rotacion_max_grados"], aug_cfg["rotacion_max_grados"])
        out = _rotar(out, grados)
        brillo = rng.uniform(*aug_cfg["brillo_rango"])
        contraste = rng.uniform(*aug_cfg["contraste_rango"])
        out = _brillo_contraste(out, brillo, contraste)
        out = _ruido_gaussiano(out, aug_cfg["ruido_gaussiano_sigma"], rng)
        out = _jitter_perspectiva(out, aug_cfg["perspectiva_jitter_px"], rng)
        variantes.append(out)
    return variantes
