"""Precios mensuales de referencia del MEM para Ciudad Capital."""
from __future__ import annotations

import csv
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

MODALIDADES = {"autoservicio", "servicio completo"}
COMBUSTIBLES = {"super_aditivada", "super", "regular", "diesel"}


def cargar_referencias(ruta: str | Path) -> dict[tuple[int, int, str, str], float]:
    """Lee el CSV auditado; falla ante claves repetidas o precios inválidos."""
    referencias: dict[tuple[int, int, str, str], float] = {}
    with Path(ruta).open(newline="", encoding="utf-8") as archivo:
        lector = csv.DictReader(archivo)
        esperadas = {"mes", "modalidad", "combustible", "precio_q_galon", "ambito"}
        if set(lector.fieldnames or []) != esperadas:
            raise ValueError(f"Columnas inválidas en referencia mensual: {lector.fieldnames}")
        for fila in lector:
            mes = fila["mes"]
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
                raise ValueError(f"Mes inválido en referencia mensual: {mes}")
            modalidad, combustible = fila["modalidad"], fila["combustible"]
            if modalidad not in MODALIDADES or combustible not in COMBUSTIBLES:
                raise ValueError(f"Serie inválida en referencia mensual: {fila}")
            if fila["ambito"] != "ciudad_capital":
                raise ValueError(f"Ámbito inválido en referencia mensual: {fila['ambito']}")
            try:
                precio = Decimal(fila["precio_q_galon"])
            except InvalidOperation as exc:
                raise ValueError(f"Precio inválido en referencia mensual: {fila}") from exc
            if not precio.is_finite() or not 0 < precio < 100 or precio != precio.quantize(Decimal("0.01")):
                raise ValueError(f"Precio inválido en referencia mensual: {fila}")
            clave = (int(mes[:4]), int(mes[5:]), modalidad, combustible)
            if clave in referencias:
                raise ValueError(f"Referencia mensual duplicada: {clave}")
            referencias[clave] = float(precio)
    if not referencias:
        raise ValueError("El CSV de referencia mensual está vacío")
    return referencias


def buscar_referencia(referencias: dict, fecha: date | None, modalidad: str,
                      combustible: str) -> tuple[float | None, bool]:
    """Devuelve precio y si se supuso autoservicio por modalidad desconocida."""
    if fecha is None:
        return None, False
    supuesto = modalidad not in MODALIDADES
    modo = "autoservicio" if supuesto else modalidad
    return referencias.get((fecha.year, fecha.month, modo, combustible)), supuesto
