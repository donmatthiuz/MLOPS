"""Vistas de la foto para una segunda lectura enfocada de los visores."""
from __future__ import annotations

from PIL import Image, ImageOps


def vistas_enfoque(imagen: Image.Image, *, contraste: bool = False) -> list[Image.Image]:
    """Foto completa y cuatro franjas solapadas que conservan visor y rótulo."""
    img = imagen.convert("RGB")
    ancho, alto = img.size
    limites = ((0.00, 0.30), (0.22, 0.55), (0.45, 0.78), (0.70, 1.00))
    vistas = [img]
    for inicio, fin in limites:
        izquierda = int(ancho * inicio)
        derecha = max(izquierda + 1, int(ancho * fin))
        corte = img.crop((izquierda, 0, derecha, alto))
        vistas.append(ImageOps.autocontrast(corte, cutoff=1) if contraste else corte)
    return vistas
