# Formato original del entregable de PolyRL

## Procedencia

Referencia: `Entregable 16 y 23.pdf`, seis páginas A4. Metadatos originales: título «PolyRL — Propuesta actualizada y evidencia de entrega», autor «Equipo del proyecto PolyRL · Grupo 2», creador «Proyecto RL · Generación de documento con ReportLab». Creación: 23/10/2026 18:47:28; última modificación: 18:59:20, Guatemala (UTC−06:00).

Se recuperaron los archivos de trabajo originales de `/tmp/polyrl-pdf-20261023/`:

1. `generar_propuesta.py`: construyó las seis páginas mediante ReportLab Platypus, fuentes incrustadas, marcadores y numeración en dos pasadas.
2. `agregar_repositorio.py`: añadió mediante pypdf una caja con enlace en las páginas 1 y 6.
3. `mover_repositorio_al_inicio.py`: reconstruyó desde el PDF previo al enlace, colocó el enlace de la primera página arriba de las evidencias y mantuvo la caja de la sexta. **Ese es el resultado final que se debe reproducir.**

Los recursos de esta skill ya incorporan el resultado final y no dependen de que esos archivos temporales sigan existiendo. `generar_pdf.py` conserva los parámetros originales y separa el contenido en JSON. Versiones comprobadas en el entorno original: ReportLab 5.1.0, pypdf 6.21.2, Pillow 13.0.0.

SHA-256 del PDF de referencia al crear la skill:

```text
cad770de250cb50bbfb9b9020a0e23eb178e3cc2a24c8b55bb5db90868f29afb
```

## Página y elementos fijos

Todas las medidas están en puntos PDF (72 pt = 1 pulgada). Las coordenadas absolutas se miden desde la esquina inferior izquierda.

| Elemento | Valor original |
|---|---|
| Página | A4 vertical, 595.2755905511812 × 841.8897637795277 pt |
| Márgenes izquierdo / derecho | 44 / 44 pt |
| Márgenes superior / inferior | 57 / 53 pt |
| Ancho útil | 507.2755905511812 pt |
| Frame | x=44, y=53, ancho=507.2755905511812, alto=731.8897637795277; paddings=0 |
| Encabezado izquierdo | `APRENDIZAJE POR REFUERZO · PROYECTO FINAL`, Noto Bold 7.3; x=44, y=alto−29 |
| Encabezado derecho | `Grupo 2 · 23/10/2026`, Noto Regular 7.3; alineado a x=ancho−44 |
| Línea superior | y=alto−39; grosor 0.5; color LINE |
| Pie izquierdo | `PolyRL · Actualización del 23 de octubre de 2026`, Noto Regular 7.4; x=44, y=25 |
| Pie derecho | `n / 6`, Noto Regular 7.4; alineado a x=ancho−44, y=25 |
| Línea inferior | y=39; grosor 0.5; color LINE |
| Separación de secciones principales | PageBreak explícito después de cada página, salvo la última |
| Marcadores | Uno por título principal, seis en total |

## Colores

| Nombre | Hex | Uso |
|---|---|---|
| NAVY | `#17304B` | Títulos, cabeceras de tablas |
| TEAL | `#11746F` | Kicker, enlaces, borde lateral de cajas |
| INK | `#273647` | Texto principal |
| MUTED | `#5A6977` | Subtítulos, notas, encabezado y pie |
| LINE | `#D6E1E8` | Líneas y bordes |
| PALE | `#F2F6F9` | Filas alternas y fondos de cajas |
| WHITE | `#FFFFFF` | Fondo y texto de encabezados de tabla |

## Fuentes y párrafos

Usar los archivos originales, sin sustituir por Helvetica, Arial u otra sans. Por defecto: `/usr/share/fonts/noto/NotoSans-{Regular,Bold,Italic}.ttf` y `/usr/share/fonts/TTF/DejaVuSansMono.ttf`. Si las rutas difieren, poner las cuatro TTF en una carpeta y usar `--font-dir`. Las fuentes se incrustan. La familia Noto vincula negrita e itálica; el original vincula boldItalic a NotoBold.

| Estilo JSON | Fuente | Tamaño / interlínea | Antes / después | Color |
|---|---|---|---|---|
| kicker | Noto Bold | 8.3 / 12 | 0 / 7 | TEAL |
| title | Noto Bold | 23 / 28 | 0 / 10 | NAVY |
| subtitle | Noto Regular | 10.5 / 15.5 | 0 / 13 | MUTED |
| h2 | Noto Bold | 11.2 / 15.5 | 11 / 5 | NAVY |
| body | Noto Regular | 9.4 / 14.1 | 0 / 7 | INK |
| small | Noto Regular | 8.2 / 12 | 0 / 6 | MUTED |
| cell | Noto Regular | 8.6 / 12.4 | 0 / 0 | INK |
| cellsmall | Noto Regular | 8.1 / 11.7 | 0 / 0 | INK |
| th | Noto Bold | 8.2 / 11.7 | 0 / 0 | WHITE |
| code | DejaVu Sans Mono | 8 / 13.2 | 0 / 6 | NAVY |
| bullet | Noto Regular | 9.1 / 13.6 | 0 / 5 | INK |

Texto alineado a la izquierda. `h2` usa keepWithNext. Las viñetas tienen leftIndent=10 y firstLineIndent=−10, y el texto comienza con `•  `. Los títulos de las páginas 1 y 2 usan los saltos `<br/>` explícitos del JSON. No cambiar esos saltos al reproducir el original.

Para identificar las versiones exactas de las fuentes, estos son sus SHA-256 en el entorno original:

```text
NotoSans-Regular.ttf  478c558ea716033cd60c03438f628dfa75694dcf6b5f6d505a2f05fd2b4f3823
NotoSans-Bold.ttf     1df075a380fc7cb898acf64c1f7b3b4dd780de3caa860178bf929de35817a913
NotoSans-Italic.ttf   467e3f89eeca4108bb8710a2b9e0cf2281ac56d5b0609211a83776d0505eecb5
DejaVuSansMono.ttf    b5babc084554ebdd142fe099d8b7c573ff161738bca913723d3e84f5c3df1c78
```

## Tablas, cajas e imágenes

Tablas alineadas a la izquierda y a todo el ancho útil. Primera fila NAVY con texto WHITE; filas alternas WHITE y PALE; alineación vertical TOP. Padding horizontal=9, vertical=7. Línea bajo cabecera: 0.5 NAVY; bajo cada fila de datos: 0.35 LINE. Repetir cabecera si fuera necesario, pero conservar una página por apartado.

| Tabla | Columnas originales en pt | Texto de celdas |
|---|---|---|
| Técnicas (p. 2) | 120, WIDTH−120 | cell |
| Módulos (p. 3) | 113, WIDTH−113 | cell |
| Equipo (p. 4) | 151, WIDTH−216, 65 | cellsmall |
| Fases (p. 4) | 132, WIDTH−132 | cellsmall |
| Entregables (p. 5) | 132, WIDTH−132 | cellsmall |
| Cambios / commits (p. 6) | 133, WIDTH−133 | cellsmall |

Cajas de notas: tabla de una celda; ancho WIDTH; fondo PALE; borde 0.5 LINE; borde izquierdo 3 TEAL; padding izquierdo/derecho=12, superior=10, inferior=5. La primera caja usa body; las otras usan small, según el JSON.

Evidencias de la primera página, en este orden:

1. `image copy.png`: aprobación, imagen original de 839 × 149 px.
2. `image.png`: envío de propuesta, imagen original de 826 × 229 px.

Mostrar cada imagen completa, alineada a la izquierda, ancho WIDTH y alto proporcional `WIDTH × alto_px / ancho_px`. Mantener el Spacer de 6 pt antes de cada pie de imagen. La caja final de esa página tiene un Spacer previo de 8 pt.

## Enlaces finales del repositorio

URL original: `https://github.com/donmatthiuz/RL/tree/proyecto`. La doble `t` en `donmatthiuz` forma parte de la URL original. Mantener el subrayado y una anotación PDF `/Link` con acción `/URI` en cada ubicación.

- **Página 1:** etiqueta `Repositorio del proyecto:` en x=44, y=790.5, Noto Bold 8.8 NAVY. Enlace a continuación, x=44+ancho_de_etiqueta+6, mismo y, Noto Regular 9 TEAL. No colocar una caja inferior en esta página.
- **Página 6:** caja x=44, y=147, ancho=WIDTH, alto=51, relleno PALE y borde LINE 0.5; línea TEAL 3 en x=44, y=147..198. Etiqueta `Repositorio del proyecto · rama proyecto` en x=56, y=181, Noto Bold 9.2 NAVY. URL en x=56, y=163, Noto Regular 9.4 TEAL.
- Subrayado: y_del_enlace−2, grosor 0.5. Rectángulo clicable: `[x−1, y−4, x+ancho_del_enlace+1, y+10]`.

El texto de la sexta página debe terminar antes de la caja. El generador rechaza invasiones del espacio reservado y URLs que excedan el ancho original.

## Orden editorial de las seis páginas

| Página | Kicker / título principal | Contenido |
|---|---|---|
| 1 | EVIDENCIA DOCUMENTAL / Constancia de entrega y aprobación | Enlace inicial; evidencia de aprobación; evidencia de envío; pies documentales; caja con fecha de actualización |
| 2 | PROPUESTA ACTUALIZADA · FECHA / PolyRL: aprendizaje por refuerzo en Polymarket | Idea y objetivo; cuatro pasos; tabla de técnicas; precisión sobre Offline RL; resultado esperado |
| 3 | DISEÑO TÉCNICO PREVISTO / Datos, entorno y recompensa | Tabla de módulos; datos y no-lookahead; estado, acciones, transición y final; recompensa y variantes |
| 4 | ORGANIZACIÓN Y PLAN DE TRABAJO / Equipo, fases y entregables | Tabla de cinco roles y respaldos; tabla F0–F4; prioridades; colaboración y criterio de finalización |
| 5 | METODOLOGÍA Y CRITERIOS DE ÉXITO / Evaluación y calidad | Baselines; métricas y semillas; hipótesis; tabla de entregables; pruebas; riesgos y límites |
| 6 | CAMBIOS REGISTRADOS · FECHA / Avances y estado actual | Tabla de commits; implementado y comprobado; caja de verificación; pendientes frente al plan; fuentes; caja de repositorio |

## Contrato del JSON de contenido

El archivo incluido es una instantánea histórica; copiarlo para actualizar una entrega. Las rutas de imágenes se resuelven desde `--root`. No necesita Markdown, LaTeX, navegador ni conversión HTML.

Campos superiores: `date` (ISO `AAAA-MM-DD`), `group` (texto), `repository` (URL), `branch`, `title`, `author`, `subject`, `pages`. `pages` contiene exactamente seis listas de bloques, cada una con un único párrafo `style: title`. Los saltos entre listas los añade el generador.

| Tipo de bloque | Campos |
|---|---|
| paragraph | `type`, `text`, `style` de la tabla de estilos; por defecto body |
| bullet | `type`, `text`; el generador añade la viñeta original |
| table | `type`, `headers` (lista de textos), `rows` (listas de textos), `widths` (anchos), `small` (booleano opcional) |
| box | `type`, `text`, `style` opcional |
| image | `type`, `path` |
| spacer | `type`, `height` en pt |

La última columna de `widths` puede ser `"remaining"`: ocupa el ancho útil menos las anteriores. Cada fila debe tener tantas celdas como encabezados y anchos. `small: true` usa cellsmall. Los textos admiten el marcado de Paragraph de ReportLab usado por el original: `<b>`, `<i>`, `<br/>` y `<font face="Mono" size="8">`. Escapar los caracteres de texto literal `&`, `<`, `>` como `&amp;`, `&lt;`, `&gt;`.

Tokens admitidos dentro de los textos: `{{fecha_larga}}`, `{{fecha_mayusculas}}`, `{{fecha_corta}}`, `{{grupo}}`. Se obtienen de `date` y `group`. Las fechas históricas de correos, horas de commits y resultados de pruebas escritos directamente en el contenido no cambian automáticamente.

Al actualizar, mantener la jerarquía, las tablas y la función de cada página. Ajustar la redacción para que quepa; no reducir fuentes ni márgenes, ni añadir una séptima página para acomodar texto. Si el usuario solicita otra extensión o diseño, esa petición redefine el formato y requiere una adaptación explícita de la plantilla.
