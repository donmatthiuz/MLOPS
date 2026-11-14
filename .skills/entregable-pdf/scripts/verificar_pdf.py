#!/usr/bin/env python3
"""Comprueba la reproducción histórica: texto, evidencias, enlaces y píxeles."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image, ImageChops
from pypdf import PdfReader


def links(page) -> list:
    result = []
    for ref in page.get('/Annots', []):
        annotation = ref.get_object()
        if annotation.get('/Subtype') == '/Link':
            result.append((
                annotation.get('/A', {}).get('/URI'),
                tuple(float(v) for v in annotation['/Rect']),
                tuple(annotation.get('/Border', [])),
            ))
    return result


def outline_titles(outline) -> list[str]:
    titles = []
    for item in outline:
        if isinstance(item, list):
            titles.extend(outline_titles(item))
        else:
            titles.append(str(item['/Title']))
    return titles


def verify(reference: Path, candidate: Path) -> None:
    if shutil.which('pdftoppm') is None:
        raise ValueError('Falta pdftoppm (Poppler), necesario para comparar los píxeles.')
    original, rebuilt = PdfReader(reference), PdfReader(candidate)
    if len(original.pages) != 6 or len(rebuilt.pages) != 6:
        raise ValueError('Ambos documentos deben contener seis páginas.')
    if outline_titles(original.outline) != outline_titles(rebuilt.outline):
        raise ValueError('Los marcadores difieren.')
    for field in ('/Title', '/Author', '/Subject', '/Creator'):
        if original.metadata.get(field) != rebuilt.metadata.get(field):
            raise ValueError(f'Los metadatos difieren: {field}.')
    with TemporaryDirectory(prefix='polyrl-pdf-comparison-') as temp:
        prefixes = [Path(temp) / 'original', Path(temp) / 'reproduccion']
        for path, prefix in zip((reference, candidate), prefixes):
            subprocess.run(['pdftoppm', '-r', '150', '-png', str(path), str(prefix)], check=True, capture_output=True)
        for number, (before, after) in enumerate(zip(original.pages, rebuilt.pages), 1):
            if tuple(before.mediabox) != tuple(after.mediabox):
                raise ValueError(f'Página {number}: dimensiones distintas.')
            if before.extract_text() != after.extract_text():
                raise ValueError(f'Página {number}: texto distinto.')
            if links(before) != links(after):
                raise ValueError(f'Página {number}: enlace o posición clicable distintos.')
            if len(before.images) != len(after.images):
                raise ValueError(f'Página {number}: número de evidencias distinto.')
            for a, b in zip(before.images, after.images):
                if a.image.size != b.image.size or a.image.tobytes() != b.image.tobytes():
                    raise ValueError(f'Página {number}: imagen de evidencia alterada.')
            with Image.open(f'{prefixes[0]}-{number}.png') as a, Image.open(f'{prefixes[1]}-{number}.png') as b:
                if a.size != b.size or ImageChops.difference(a.convert('RGB'), b.convert('RGB')).getbbox() is not None:
                    raise ValueError(f'Página {number}: diferencia visual a 150 dpi.')
            print(f'Página {number}: texto, evidencias, enlaces y píxeles idénticos.')
    print('Verificación correcta: seis páginas y marcadores conservados. Las fechas internas pueden diferir.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    try:
        verify(args.reference.resolve(), args.candidate.resolve())
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
