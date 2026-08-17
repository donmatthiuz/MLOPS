"""Carga de imágenes HEIC (formato nativo de iPhone) a arrays RGB + metadatos EXIF.

Los tótems/dispensores se fotografían con celular en formato HEIC. Este módulo
aísla la dependencia de `pillow-heif` y expone también la fecha/hora real de
captura (EXIF DateTimeOriginal), que es la señal de "día y hora" que el
negocio pide usar para la recomendación final.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pillow_heif
from PIL import Image
from PIL.ExifTags import TAGS


@dataclass
class ImagenCargada:
    ruta: Path
    arreglo: np.ndarray          # HxWx3 uint8 RGB
    capturada_en: datetime | None
    ancho: int
    alto: int


def _extraer_datetime_original(heif_file) -> datetime | None:
    exif_bytes = heif_file.info.get("exif")
    if not exif_bytes:
        return None
    try:
        img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw")
        img.info["exif"] = exif_bytes
        exifdata = img.getexif()
        exif_ifd = exifdata.get_ifd(0x8769)  # Exif IFD pointer
        raw = exif_ifd.get(36867) or exif_ifd.get(36868)  # DateTimeOriginal / Digitized
        if raw is None:
            for tag_id, value in exifdata.items():
                if TAGS.get(tag_id) == "DateTime":
                    raw = value
                    break
        if raw is None:
            return None
        return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None


def cargar_heic(ruta: Path | str) -> ImagenCargada:
    """Carga un archivo .HEIC devolviendo el array RGB y la fecha/hora EXIF real."""
    ruta = Path(ruta)
    heif_file = pillow_heif.open_heif(ruta, convert_hdr_to_8bit=True)
    img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw").convert("RGB")
    arr = np.array(img)
    capturada_en = _extraer_datetime_original(heif_file)
    return ImagenCargada(
        ruta=ruta,
        arreglo=arr,
        capturada_en=capturada_en,
        ancho=arr.shape[1],
        alto=arr.shape[0],
    )


def listar_imagenes(directorio: Path | str) -> list[Path]:
    directorio = Path(directorio)
    exts = {".heic", ".HEIC", ".jpg", ".jpeg", ".JPG", ".JPEG", ".png", ".PNG"}
    return sorted(p for p in directorio.iterdir() if p.suffix in exts)


def cargar_imagen_generica(ruta: Path | str) -> ImagenCargada:
    """Carga HEIC o cualquier formato soportado por Pillow, de forma transparente."""
    ruta = Path(ruta)
    if ruta.suffix.lower() == ".heic":
        return cargar_heic(ruta)
    img = Image.open(ruta).convert("RGB")
    arr = np.array(img)
    capturada_en = None
    try:
        exifdata = img.getexif()
        exif_ifd = exifdata.get_ifd(0x8769)
        raw = exif_ifd.get(36867)
        if raw:
            capturada_en = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return ImagenCargada(ruta=ruta, arreglo=arr, capturada_en=capturada_en, ancho=arr.shape[1], alto=arr.shape[0])
