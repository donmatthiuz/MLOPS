"""Orquestador de extracción: imagen de tótem -> pares (tipo_combustible, precio).

Implementa la interfaz de extracción pedida por el negocio: "el sistema debe
poder recibir una imagen, procesarla y devolver un formato estructurado
(tipo de combustible -> precio)". Aplica también las reglas de validación
que exige el documento de negocio (R6/R7): nivel de confianza mínimo y rango
de precio plausible; ante la duda, descarta (null) en vez de inventar.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from ..config import load_config, resolve_path
from .calibration import CalibracionPaneles
from .digit_ocr import leer_precio
from .heic_loader import ImagenCargada, cargar_imagen_generica, listar_imagenes
from .preprocess import localizar_visor_lcd
from .privacy import aplicar_filtro_privacidad

logger = logging.getLogger(__name__)


@dataclass
class LecturaCombustible:
    tipo_combustible: str
    precio_gtq_por_galon: float | None
    confianza: float
    motor_ocr: str
    texto_crudo: str
    valido: bool
    motivo_invalido: str | None


@dataclass
class RegistroExtraccion:
    archivo: str
    capturada_en: str | None
    caras_difuminadas: int
    lecturas: list[LecturaCombustible]


class ExtractorPrecios:
    def __init__(self, config: dict | None = None):
        self.cfg = config or load_config()
        self.calibracion = CalibracionPaneles()
        ext_cfg = self.cfg["extraccion"]
        self.orden_combustibles: list[str] = ext_cfg["orden_combustibles"]
        self.rango_valido = tuple(ext_cfg["rango_precio_valido_gtq"])
        self.confianza_minima = float(ext_cfg["confianza_minima"])

    def extraer_de_imagen(self, imagen: ImagenCargada) -> RegistroExtraccion:
        privacidad = aplicar_filtro_privacidad(imagen.arreglo)
        arr = privacidad.imagen
        nombre = imagen.ruta.name

        lecturas: list[LecturaCombustible] = []
        for combustible in self.orden_combustibles:
            caja = self.calibracion.caja_absoluta(nombre, combustible, imagen.ancho, imagen.alto)
            if caja is None:
                lecturas.append(
                    LecturaCombustible(combustible, None, 0.0, "n/a", "", False, "panel_fuera_de_encuadre")
                )
                continue

            x0, y0, x1, y1 = caja
            panel = arr[y0:y1, x0:x1]
            recorte = localizar_visor_lcd(panel)
            lectura = leer_precio(recorte.imagen_gris_binaria)

            valido, motivo = self._validar(lectura.valor, lectura.confianza)
            lecturas.append(
                LecturaCombustible(
                    tipo_combustible=combustible,
                    precio_gtq_por_galon=lectura.valor if valido else None,
                    confianza=round(lectura.confianza, 3),
                    motor_ocr=lectura.motor,
                    texto_crudo=lectura.texto,
                    valido=valido,
                    motivo_invalido=motivo,
                )
            )

        return RegistroExtraccion(
            archivo=nombre,
            capturada_en=imagen.capturada_en.isoformat() if imagen.capturada_en else None,
            caras_difuminadas=privacidad.caras_difuminadas,
            lecturas=lecturas,
        )

    def _validar(self, valor: float | None, confianza: float) -> tuple[bool, str | None]:
        if valor is None:
            return False, "ocr_no_pudo_leer"
        if confianza < self.confianza_minima:
            return False, f"confianza_baja({confianza:.2f})"
        lo, hi = self.rango_valido
        if not (lo <= valor <= hi):
            return False, f"fuera_de_rango_plausible({valor})"
        return True, None

    def procesar_directorio(self, directorio: Path | str | None = None) -> list[RegistroExtraccion]:
        directorio = Path(directorio) if directorio else resolve_path(self.cfg["paths"]["datos_raw"])
        registros = []
        for ruta in listar_imagenes(directorio):
            try:
                imagen = cargar_imagen_generica(ruta)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo cargar %s: %s", ruta, exc)
                continue
            registros.append(self.extraer_de_imagen(imagen))
        return registros

    def guardar_bronze(self, registros: list[RegistroExtraccion]) -> Path:
        bronze_dir = resolve_path(self.cfg["paths"]["bronze"])
        bronze_dir.mkdir(parents=True, exist_ok=True)
        salida = bronze_dir / f"extraccion_{datetime.now():%Y%m%dT%H%M%S}.json"
        payload = [asdict(r) for r in registros]
        with open(salida, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        logger.info("Bronze guardado en %s (%d imágenes)", salida, len(registros))
        return salida
