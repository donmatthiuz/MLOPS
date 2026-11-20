from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "pipelines"))

from plata_referencia import buscar_referencia, cargar_referencias  # noqa: E402


def test_csv_mem_cubre_81_meses_y_separa_modalidad() -> None:
    refs = cargar_referencias(RAIZ / "docs/plata/precios_mem_capital_mensual.csv")
    assert len(refs) == 81 * 8
    meses = [(anio, mes) for anio in range(2020, 2027)
             for mes in range(1, 13) if (anio, mes) <= (2026, 9)]
    assert {(anio, mes) for anio, mes, _, _ in refs} == set(meses)
    assert all(sum((anio, mes) == (a, m) for a, m, _, _ in refs) == 8 for anio, mes in meses)
    assert buscar_referencia(refs, date(2026, 9, 20), "autoservicio", "regular") == (42.34, False)
    assert buscar_referencia(refs, date(2026, 9, 20), "servicio completo", "regular") == (43.36, False)
    assert buscar_referencia(refs, date(2026, 9, 20), "no_especificada", "regular") == (42.34, True)
    assert buscar_referencia(refs, date(2026, 10, 20), "autoservicio", "regular") == (None, False)


def test_csv_rechaza_clave_duplicada(tmp_path: Path) -> None:
    csv = tmp_path / "duplicado.csv"
    csv.write_text("mes,modalidad,combustible,precio_q_galon,ambito\n"
                   "2026-01,autoservicio,regular,30.00,ciudad_capital\n"
                   "2026-01,autoservicio,regular,31.00,ciudad_capital\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicada"):
        cargar_referencias(csv)
