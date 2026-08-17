"""Calibración de las regiones de panel de precio (datos/calibracion_paneles.json).

Contexto: con solo 5 fotos piloto del mismo dispensor Shell, entrenar un
detector de objetos (Vision Transformer / YOLO, como plantea el Business
Understanding) no es viable ni justificable. En su lugar se usa una
calibración manual validada visualmente sobre las 5 fotos (dos perfiles de
encuadre distintos), y se deja documentado el camino de escalamiento: cuando
existan más fotos (S8), esta calibración fija se reemplaza por un detector
entrenado. Ver decisiones abiertas D1/D3 y riesgo R1 del business understanding.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..config import PROJECT_ROOT

CALIBRACION_PATH = PROJECT_ROOT / "datos" / "calibracion_paneles.json"

BoundingBoxFraccional = tuple[float, float, float, float]


class CalibracionPaneles:
    def __init__(self, path: Path | str = CALIBRACION_PATH):
        with open(path, "r", encoding="utf-8") as fh:
            self._data = json.load(fh)
        self.perfiles: dict[str, dict[str, Optional[BoundingBoxFraccional]]] = self._data["perfiles"]
        self.asignacion: dict[str, str] = self._data["asignacion_por_archivo"]
        self.perfil_por_defecto: str = self._data["perfil_por_defecto_para_imagenes_nuevas"]

    def perfil_para(self, nombre_archivo: str) -> str:
        return self.asignacion.get(nombre_archivo, self.perfil_por_defecto)

    def cajas_para(self, nombre_archivo: str) -> dict[str, Optional[BoundingBoxFraccional]]:
        perfil = self.perfil_para(nombre_archivo)
        return self.perfiles[perfil]

    def caja_absoluta(
        self, nombre_archivo: str, combustible: str, ancho: int, alto: int
    ) -> Optional[tuple[int, int, int, int]]:
        caja = self.cajas_para(nombre_archivo).get(combustible)
        if caja is None:
            return None
        x0, y0, x1, y1 = caja
        return int(x0 * ancho), int(y0 * alto), int(x1 * ancho), int(y1 * alto)
