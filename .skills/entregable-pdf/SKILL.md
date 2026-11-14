---
name: entregable-pdf
description: "Genera entregables académicos de PolyRL en PDF con el formato exacto de Entregable 16 y 23.pdf: seis páginas A4, evidencias, propuesta, diseño técnico, organización, evaluación y avances. Usar al reproducir ese documento o preparar una nueva entrega del proyecto con el mismo diseño."
---

# Entregable PDF de PolyRL

Reproducir el formato de `Entregable 16 y 23.pdf` usando el generador recuperado de su creación original. El diseño está fijado en [scripts/generar_pdf.py](scripts/generar_pdf.py); el contenido histórico está separado en [assets/contenido-2026-10-23.json](assets/contenido-2026-10-23.json).

## Preparar la entrega

1. Leer [references/formato.md](references/formato.md) antes de generar: contiene las medidas exactas, el esquema de contenido y el orden de las páginas.
2. Localizar la raíz del proyecto, el PDF de referencia, la propuesta original y las dos evidencias (`image copy.png` e `image.png`). Inspeccionar el PDF y las capturas. Conservar las imágenes completas, sin recortar ni retocar.
3. Distinguir el pedido:
   - **Reproducción histórica:** usar el JSON incluido sin modificar sus hechos, fechas, nombres ni resultados.
   - **Nueva entrega:** copiar el JSON a la carpeta de esa entrega y actualizarlo a partir de `README.md`, `docs/01_idea_general.md` a `docs/07_riesgos_y_decisiones.md`, `docs/polymarket.md`, `pyproject.toml`, código, tests y Git. Consultar solo las fuentes necesarias para los apartados que cambien. Conservar la plantilla histórica para futuras reproducciones.
4. En una actualización, verificar fecha y zona `America/Guatemala`, asignaciones, commits y estado real de implementación. Ejecutar los tests pertinentes si se van a informar resultados actuales. Los **22 tests**, las asignaciones y los avances del JSON son una fotografía del **23/10/2026**, no valores permanentes. Expresar lo planificado como previsto y lo comprobado con su evidencia; no convertir documentación de arquitectura en funcionalidades implementadas.

Mantener el contexto del proyecto: RL universitario con datos históricos de Polymarket y saldo ficticio; acciones `WAIT`, `BUY_YES`, `BUY_NO`, `SELL`; comparación de PPO, DQN y variante offline. Usar un simulador histórico no convierte PPO/DQN en Offline RL. Las nuevas conclusiones experimentales deben proceder de artefactos y mediciones existentes.

## Generar

Ejecutar desde la raíz del repositorio con Python 3.11 o posterior. Usar un entorno que tenga las versiones de [scripts/requirements.txt](scripts/requirements.txt), junto con las cuatro fuentes TTF originales indicadas en la referencia. Si hace falta un entorno, crearlo separado del entorno de entrenamiento:

```bash
python3 -m venv /tmp/polyrl-entregable-venv
/tmp/polyrl-entregable-venv/bin/python -m pip install -r .skills/entregable-pdf/scripts/requirements.txt
```

Reproducir el entregable histórico en un archivo nuevo:

```bash
/tmp/polyrl-entregable-venv/bin/python .skills/entregable-pdf/scripts/generar_pdf.py --root . --output /tmp/entregable-reproducido.pdf
```

Para una nueva entrega, pasar `--content <JSON-actualizado>` y `--output <PDF-nuevo>`. Cambiar `date` actualiza encabezados, pies y los tokens de fecha de actualización; revisar también las fechas y descripciones escritas como texto. El generador no obtiene avances ni ejecuta tests por su cuenta. Conservar sus estilos, fuentes, márgenes y saltos de página; resumir el contenido cuando no quepa.

El script incorpora tanto la composición original en ReportLab como la posición **final** de los enlaces: arriba de las evidencias en la primera página y en la caja inferior de la sexta. No aplicar después los parches temporales originales. El generador rechaza sobrescribir un archivo existente y no publica ni envía el PDF.

## Verificar y entregar

- **Reproducción:** ejecutar [scripts/verificar_pdf.py](scripts/verificar_pdf.py) contra el original:

  ```bash
  /tmp/polyrl-entregable-venv/bin/python .skills/entregable-pdf/scripts/verificar_pdf.py --reference 'Entregable 16 y 23.pdf' --candidate /tmp/entregable-reproducido.pdf
  ```

  Debe coincidir el texto, las evidencias, los marcadores, los enlaces y cada píxel de las seis páginas rasterizadas con `pdftoppm` a 150 dpi. No exigir igualdad binaria: las fechas internas del PDF pueden variar.
- **Contenido actualizado:** el generador comprueba seis páginas, seis marcadores, enlaces y espacio para la caja final. Rasterizar las seis páginas con `pdftoppm -r 150 -png <PDF> /tmp/polyrl-revision` e inspeccionarlas con el visor de imágenes disponible. Revisar cortes, tablas, títulos, evidencias, paginación y ausencia de solapamientos. No exigir igualdad de píxeles a textos distintos.
- Entregar el enlace al PDF generado y, si se actualizó el contenido, al JSON usado. Indicar qué se verificó y cualquier impedimento concreto. Conservar el PDF de referencia y las demás skills.
