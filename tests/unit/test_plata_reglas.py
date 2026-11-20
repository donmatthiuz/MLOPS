from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipelines"))

from plata_reglas import (  # noqa: E402
    ajustar_orden_con_referencia,
    anio_de_ruta,
    conciliar,
    conciliar_con_enfoque,
    lecturas_por_combustible,
    motivo_rechazo,
    normalizar_combustible,
    normalizar_modalidad,
    normalizar_ubicacion,
    orden_incoherente,
    parsear_respuesta,
    precio_desde_display,
)

HOY = date(2026, 11, 15)


def test_premium_no_entra_al_catalogo() -> None:
    assert normalizar_combustible("super", "V-Power") == "otro"
    assert normalizar_combustible("super", "FuelSave Super") == "super"
    assert normalizar_combustible(None, "ION Diesel") == "diesel"
    assert normalizar_combustible("otro", "Regular CLEANTEC") == "regular"


def test_display_de_bomba_da_precio_por_galon() -> None:
    # Caso real IMG_7575: Q100.00 por 3.664 galones
    assert precio_desde_display(100.0, 3.664) == 27.29
    assert precio_desde_display(None, 3.664) is None
    assert precio_desde_display(100, 0) is None


def test_conciliar_prefiere_display_y_luego_consenso() -> None:
    # El modelo leyó 21.29 y 27.29; el display confirma 27.29
    assert conciliar(21.29, 27.29, 27.29) == (27.29, "display_bomba")
    assert conciliar(25.99, 25.99, None) == (25.99, "consenso")
    assert conciliar(21.29, 27.29, None) == (None, "lecturas_inconsistentes")
    assert conciliar(None, None, None) == (None, "sin_lectura")


def test_referencia_desempata_lecturas_y_respalda_precio_ilegible() -> None:
    assert conciliar(21, 27, None, 22) == (21, "referencia_desempate")
    assert conciliar(None, None, None, 22) == (22, "referencia_mensual")
    assert conciliar(21, 27, 27, 22) == (27, "display_bomba")
    assert conciliar(21, 21, None, 27) == (21, "consenso")
    assert conciliar(16, 29, None, 22) == (22, "referencia_mensual")
    assert conciliar(21, 23, None, 22) == (22, "referencia_mensual")  # empate: no inventar desempate


def test_recortes_resuelven_conflicto_sin_usar_referencia() -> None:
    assert conciliar_con_enfoque(21, 27, 21, 21, None, 22) == (21, "consenso_enfoque")
    assert conciliar_con_enfoque(None, None, 31.5, 31.5, None, 30) == (31.5, "consenso_enfoque")
    assert conciliar_con_enfoque(21, 27, 21, 27, None, 22) == (21, "referencia_desempate")
    assert conciliar_con_enfoque(None, None, None, None, None, 30) == (30, "referencia_mensual")


def test_referencia_resuelve_orden_invertido_con_procedencia() -> None:
    finales = {"super": (25, "consenso"), "regular": (30, "consenso")}
    refs = {"super": 32, "regular": 30}
    assert ajustar_orden_con_referencia(finales, refs) == {
        "super": (32, "referencia_mensual_orden"), "regular": (30, "consenso")}
    assert ajustar_orden_con_referencia(finales, {}) is None


def test_reglas_de_calidad() -> None:
    assert motivo_rechazo(HOY, "super", 27.29, HOY) is None
    assert motivo_rechazo(None, "super", 27.29, HOY) == "fecha_desconocida"
    assert motivo_rechazo(date(2026, 12, 1), "super", 27.29, HOY) == "fecha_futura"
    assert motivo_rechazo(HOY, "otro", 27.29, HOY) == "combustible_fuera_catalogo"
    assert motivo_rechazo(HOY, "diesel", 2.48, HOY) == "precio_fuera_rango"
    assert motivo_rechazo(HOY, "diesel", None, HOY) == "precio_ilegible"


def test_super_no_puede_ser_menor_que_regular() -> None:
    assert orden_incoherente({"super": 21.29, "regular": 26.29})
    assert not orden_incoherente({"super": 27.29, "regular": 26.29})
    assert not orden_incoherente({"regular": 26.29})


def test_parseo_tolera_bloques_de_codigo() -> None:
    texto = '```json\n{"precios": [{"nombre_en_rotulo": "Super", "combustible": "super", "precio_q_galon": "Q27,29"}]}\n```'
    assert lecturas_por_combustible(parsear_respuesta(texto)) == {"super": 27.29}
    assert parsear_respuesta("no hay json") is None


def test_normalizacion_de_modalidad_y_ubicacion() -> None:
    assert normalizar_modalidad("Autoservicio") == "autoservicio"
    assert normalizar_modalidad("servicio_completo") == "servicio completo"
    assert normalizar_modalidad(None) == "no_especificada"
    assert normalizar_ubicacion("Shell", None) == "Shell"
    assert normalizar_ubicacion(None, "  ") == "desconocida"


def test_fecha_debe_coincidir_con_carpeta_del_anio() -> None:
    assert anio_de_ruta("s3://b/img/2024/IMG_1.HEIC") == 2024
    assert anio_de_ruta("s3://b/img/IMG_1.HEIC") is None
    assert motivo_rechazo(date(2024, 5, 1), "super", 30.1, HOY, anio_carpeta=2024) is None
    assert motivo_rechazo(date(2026, 1, 7), "super", 27.29, HOY, anio_carpeta=2024) == "fecha_no_coincide_con_carpeta"
    # Casos reales: img/2023/IMG_2976 es del 2022-12-14 e img/2024/IMG_4310 del 2023-11-13
    assert motivo_rechazo(date(2022, 12, 14), "super", 32.49, HOY, anio_carpeta=2023) is None
    assert motivo_rechazo(date(2023, 11, 13), "super", 32.49, HOY, anio_carpeta=2024) is None
    assert motivo_rechazo(date(2022, 6, 1), "super", 32.49, HOY, anio_carpeta=2023) == "fecha_no_coincide_con_carpeta"
