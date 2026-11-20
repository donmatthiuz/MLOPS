"""Las vistas enfocadas conservan toda la altura (visor y rótulo)."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipelines"))
from plata_vision import vistas_enfoque  # noqa: E402


def test_vistas_incluyen_foto_y_paneles_solapados() -> None:
    imagen = Image.new("RGB", (1000, 600), (180, 100, 40))
    vistas = vistas_enfoque(imagen)
    mejoradas = vistas_enfoque(imagen, contraste=True)

    assert len(vistas) == len(mejoradas) == 5
    assert vistas[0].size == imagen.size
    assert [v.size for v in vistas[1:]] == [(300, 600), (330, 600), (330, 600), (300, 600)]
    assert all(v.height == imagen.height for v in mejoradas)
