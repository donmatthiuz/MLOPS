#!/usr/bin/env python3
"""Reproduce la composición original de PolyRL sin modificar el PDF de referencia."""
from __future__ import annotations

import argparse
from datetime import date, datetime
from functools import partial
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from PIL import Image as PILImage
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject, DictionaryObject, FloatObject, NameObject, NumberObject, TextStringObject,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

SKILL = Path(__file__).resolve().parents[1]
NAVY = colors.HexColor('#17304B')
TEAL = colors.HexColor('#11746F')
INK = colors.HexColor('#273647')
MUTED = colors.HexColor('#5A6977')
LINE = colors.HexColor('#D6E1E8')
PALE = colors.HexColor('#F2F6F9')
WHITE = colors.white
W, H = A4
LEFT, RIGHT = 44, 44
WIDTH = W - LEFT - RIGHT
STYLES = {
    'kicker': ParagraphStyle('kicker', fontName='NotoBold', fontSize=8.3, leading=12, textColor=TEAL, spaceAfter=7),
    'title': ParagraphStyle('title', fontName='NotoBold', fontSize=23, leading=28, textColor=NAVY, spaceAfter=10),
    'subtitle': ParagraphStyle('subtitle', fontName='Noto', fontSize=10.5, leading=15.5, textColor=MUTED, spaceAfter=13),
    'h2': ParagraphStyle('h2', fontName='NotoBold', fontSize=11.2, leading=15.5, textColor=NAVY, spaceBefore=11, spaceAfter=5, keepWithNext=True),
    'body': ParagraphStyle('body', fontName='Noto', fontSize=9.4, leading=14.1, textColor=INK, spaceAfter=7),
    'small': ParagraphStyle('small', fontName='Noto', fontSize=8.2, leading=12, textColor=MUTED, spaceAfter=6),
    'cell': ParagraphStyle('cell', fontName='Noto', fontSize=8.6, leading=12.4, textColor=INK),
    'cellsmall': ParagraphStyle('cellsmall', fontName='Noto', fontSize=8.1, leading=11.7, textColor=INK),
    'th': ParagraphStyle('th', fontName='NotoBold', fontSize=8.2, leading=11.7, textColor=WHITE),
    'code': ParagraphStyle('code', fontName='Mono', fontSize=8, leading=13.2, textColor=NAVY, spaceAfter=6),
    'bullet': ParagraphStyle('bullet', fontName='Noto', fontSize=9.1, leading=13.6, textColor=INK, leftIndent=10, firstLineIndent=-10, spaceAfter=5),
}


def register_fonts(directory: Path | None) -> None:
    """Usar las fuentes originales; una sustitución cambiaría los saltos de línea."""
    for name, filename, system_dir in [
        ('Noto', 'NotoSans-Regular.ttf', '/usr/share/fonts/noto'),
        ('NotoBold', 'NotoSans-Bold.ttf', '/usr/share/fonts/noto'),
        ('NotoItalic', 'NotoSans-Italic.ttf', '/usr/share/fonts/noto'),
        ('Mono', 'DejaVuSansMono.ttf', '/usr/share/fonts/TTF'),
    ]:
        path = (directory or Path(system_dir)) / filename
        if not path.is_file():
            raise ValueError(f'Falta la fuente original: {path}. Usa --font-dir con las cuatro TTF.')
        pdfmetrics.registerFont(TTFont(name, str(path)))
    pdfmetrics.registerFontFamily('Noto', normal='Noto', bold='NotoBold', italic='NotoItalic', boldItalic='NotoBold')


def paragraph(text: str, kind: str = 'body') -> Paragraph:
    return Paragraph(text, STYLES[kind])


def table(block: dict) -> Table:
    widths = block['widths'][:]
    if widths[-1] == 'remaining':
        widths[-1] = WIDTH - sum(widths[:-1])
    if any(w <= 18 for w in widths) or abs(sum(widths) - WIDTH) > 0.01:
        raise ValueError('Los anchos de tabla deben cubrir exactamente el ancho útil de la página.')
    if len(block['headers']) != len(widths) or any(len(row) != len(widths) for row in block['rows']):
        raise ValueError('Las filas, encabezados y anchos deben tener el mismo número de columnas.')
    kind = 'cellsmall' if block.get('small', False) else 'cell'
    contents = [[paragraph(h, 'th') for h in block['headers']]]
    contents += [[paragraph(v, kind) for v in row] for row in block['rows']]
    result = Table(contents, colWidths=widths, hAlign='LEFT', repeatRows=1)
    result.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, PALE]),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, NAVY),
        ('LINEBELOW', (0, 1), (-1, -1), 0.35, LINE),
    ]))
    return result


def box(text: str, kind: str = 'body') -> Table:
    result = Table([[paragraph(text, kind)]], colWidths=[WIDTH], hAlign='LEFT')
    result.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PALE),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
        ('LINEBEFORE', (0, 0), (0, -1), 3, TEAL),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return result


def flowable(block: dict, root: Path):
    match block['type']:
        case 'paragraph':
            return paragraph(block['text'], block.get('style', 'body'))
        case 'bullet':
            return paragraph('•  ' + block['text'], 'bullet')
        case 'table':
            return table(block)
        case 'box':
            return box(block['text'], block.get('style', 'body'))
        case 'spacer':
            return Spacer(1, block['height'])
        case 'image':
            path = root / block['path']
            with PILImage.open(path) as im:
                iw, ih = im.size
            return Image(str(path), width=WIDTH, height=WIDTH * ih / iw, hAlign='LEFT')
        case _:
            raise ValueError(f"Tipo de bloque desconocido: {block['type']}")


class Doc(BaseDocTemplate):
    def afterFlowable(self, item):
        self.body_bottom[self.page] = self.frame._y
        if isinstance(item, Paragraph) and item.style.name == 'title':
            key = f'page_{self.page}'
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(item.getPlainText(), key, level=0)


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, footer_text: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.footer_text = footer_text
        self._saved_pages = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self.setStrokeColor(LINE)
            self.setLineWidth(.5)
            self.line(LEFT, 39, W - RIGHT, 39)
            self.setFont('Noto', 7.4)
            self.setFillColor(MUTED)
            self.drawString(LEFT, 25, self.footer_text)
            self.drawRightString(W - RIGHT, 25, f'{self._pageNumber} / {total}')
            super().showPage()
        super().save()


def header(c, doc):
    c.saveState()
    c.setFillColor(MUTED)
    c.setFont('NotoBold', 7.3)
    c.drawString(LEFT, H - 29, 'APRENDIZAJE POR REFUERZO · PROYECTO FINAL')
    c.setFont('Noto', 7.3)
    c.drawRightString(W - RIGHT, H - 29, doc.header_right)
    c.setStrokeColor(LINE)
    c.setLineWidth(.5)
    c.line(LEFT, H - 39, W - RIGHT, H - 39)
    c.restoreState()


def resolve_tokens(value, tokens: dict):
    if isinstance(value, str):
        for key, replacement in tokens.items():
            value = value.replace('{{' + key + '}}', replacement)
        if '{{' in value or '}}' in value:
            raise ValueError(f'Token sin resolver: {value}')
    elif isinstance(value, list):
        value = [resolve_tokens(item, tokens) for item in value]
    elif isinstance(value, dict):
        value = {key: resolve_tokens(item, tokens) for key, item in value.items()}
    return value


def read_content(path: Path) -> tuple[dict, str]:
    content = json.loads(path.read_text(encoding='utf-8'))
    when = date.fromisoformat(content['date'])
    months = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
    long_date = f'{when.day} de {months[when.month - 1]} de {when.year}'
    content = resolve_tokens(content, {
        'fecha_larga': long_date, 'fecha_mayusculas': long_date.upper(),
        'fecha_corta': when.strftime('%d/%m/%Y'), 'grupo': str(content['group']),
    })
    if len(content['pages']) != 6 or any(not page for page in content['pages']):
        raise ValueError('El formato del entregable requiere seis páginas explícitas, no vacías.')
    for number, page in enumerate(content['pages'], 1):
        titles = [b for b in page if b['type'] == 'paragraph' and b.get('style') == 'title']
        if len(titles) != 1:
            raise ValueError(f'La página {number} debe contener exactamente un título principal.')
    return content, long_date


def add_repository_links(base: Path, config: dict) -> PdfWriter:
    """Reaplica las posiciones finales del ajuste original del 23/10/2026."""
    writer = PdfWriter(clone_from=PdfReader(base))
    for number in (0, 5):
        data = BytesIO()
        c = canvas.Canvas(data, pagesize=A4)
        if number == 0:
            label = 'Repositorio del proyecto:'
            c.setFont('NotoBold', 8.8)
            c.setFillColor(NAVY)
            c.drawString(44, 790.5, label)
            x = 44 + pdfmetrics.stringWidth(label, 'NotoBold', 8.8) + 6
            y, size = 790.5, 9.0
        else:
            c.setFillColor(PALE)
            c.setStrokeColor(LINE)
            c.setLineWidth(.5)
            c.rect(44, 147, W - 88, 51, stroke=1, fill=1)
            c.setStrokeColor(TEAL)
            c.setLineWidth(3)
            c.line(44, 147, 44, 198)
            c.setFillColor(NAVY)
            c.setFont('NotoBold', 9.2)
            c.drawString(56, 181, f"Repositorio del proyecto · rama {config['branch']}")
            x, y, size = 56, 163, 9.4
        link_width = pdfmetrics.stringWidth(config['repository'], 'Noto', size)
        if x + link_width > W - RIGHT:
            raise ValueError('La URL excede el espacio original del enlace; usa una URL más corta.')
        c.setFillColor(TEAL)
        c.setStrokeColor(TEAL)
        c.setFont('Noto', size)
        c.drawString(x, y, config['repository'])
        c.setLineWidth(.5)
        c.line(x, y - 2, x + link_width, y - 2)
        c.save()
        data.seek(0)
        writer.pages[number].merge_page(PdfReader(data).pages[0])
        writer.add_annotation(page_number=number, annotation=DictionaryObject({
            NameObject('/Type'): NameObject('/Annot'),
            NameObject('/Subtype'): NameObject('/Link'),
            NameObject('/Rect'): ArrayObject([FloatObject(x - 1), FloatObject(y - 4), FloatObject(x + link_width + 1), FloatObject(y + 10)]),
            NameObject('/Border'): ArrayObject([NumberObject(0), NumberObject(0), NumberObject(0)]),
            NameObject('/A'): DictionaryObject({NameObject('/S'): NameObject('/URI'), NameObject('/URI'): TextStringObject(config['repository'])}),
        }))
    writer.add_metadata({'/ModDate': datetime.now(ZoneInfo('America/Guatemala')).strftime("D:%Y%m%d%H%M%S-06'00'")})
    return writer


def generate(content: Path, root: Path, output: Path, font_dir: Path | None) -> None:
    if output.exists():
        raise ValueError(f'La salida ya existe; elige otro nombre para conservarla: {output}')
    config, long_date = read_content(content)
    register_fonts(font_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.polyrl-pdf-', dir=output.parent) as temporary:
        base = Path(temporary) / 'base.pdf'
        doc = Doc(str(base), pagesize=A4, leftMargin=LEFT, rightMargin=RIGHT,
                  topMargin=57, bottomMargin=53,
                  title=config['title'], author=config['author'], subject=config['subject'],
                  creator='Proyecto RL · Generación de documento con ReportLab')
        doc.body_bottom = {}
        doc.header_right = f"Grupo {config['group']} · {date.fromisoformat(config['date']).strftime('%d/%m/%Y')}"
        frame = Frame(LEFT, 53, WIDTH, H - 110, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        doc.addPageTemplates(PageTemplate(id='default', frames=frame, onPage=header))
        story = []
        for number, blocks in enumerate(config['pages']):
            if number:
                story.append(PageBreak())
            story.extend(flowable(block, root) for block in blocks)
        doc.build(story, canvasmaker=partial(NumberedCanvas, footer_text=f'PolyRL · Actualización del {long_date}'))
        reader = PdfReader(base)
        if len(reader.pages) != 6 or len(reader.outline) != 6:
            raise ValueError('El contenido desborda el formato de seis páginas. Resume el texto sin cambiar estilos ni márgenes.')
        if doc.body_bottom[6] < 200:
            raise ValueError('El texto de la página 6 invade la caja del repositorio. Resume esa página.')
        writer = add_repository_links(base, config)
        final = BytesIO()
        writer.write(final)
        check = PdfReader(BytesIO(final.getvalue()))
        for number in (0, 5):
            urls = [a.get_object().get('/A', {}).get('/URI') for a in check.pages[number].get('/Annots', [])]
            if config['repository'] not in urls:
                raise ValueError(f'Falta el enlace clicable en la página {number + 1}.')
        with output.open('xb') as stream:
            stream.write(final.getvalue())
    print(f'PDF generado: {output} · 6 páginas · {output.stat().st_size:,} bytes')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--content', type=Path, default=SKILL / 'assets/contenido-2026-10-23.json', help='JSON de contenido; por defecto, la versión histórica del 23/10/2026.')
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='Raíz del proyecto para resolver las imágenes.')
    parser.add_argument('--output', type=Path, required=True, help='PDF nuevo; se rechaza sobrescribir archivos existentes.')
    parser.add_argument('--font-dir', type=Path, help='Carpeta con las cuatro fuentes originales cuando no están en las rutas del sistema.')
    args = parser.parse_args()
    try:
        generate(args.content.resolve(), args.root.resolve(), args.output.resolve(), args.font_dir)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
