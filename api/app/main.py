"""API pública de consulta de las tablas Delta de Oro."""
from __future__ import annotations

from datetime import date

from fastapi import FastAPI, HTTPException, Query

from .gold_store import GoldUnavailable, check_gold, read_gold

app = FastAPI(title="Gasolina GT · equipo 07", version="1.0.0")

COMBUSTIBLES = {"diesel", "regular", "super"}


def _rows(table: str, columns: list[str]) -> list[dict]:
    try:
        return read_gold(table, columns)
    except GoldUnavailable as exc:
        raise HTTPException(status_code=503, detail="La capa Oro no está disponible.") from exc


def _week(row: dict) -> date:
    return date.fromisoformat(str(row["semana"])[:10])


def _fuel(value: str) -> str:
    value = value.lower()
    if value not in COMBUSTIBLES:
        raise HTTPException(status_code=422, detail="combustible debe ser diesel, regular o super")
    return value


@app.get("/health", summary="Comprueba el servicio y la conexión con Oro")
def health() -> dict[str, str]:
    try:
        check_gold()
    except GoldUnavailable as exc:
        raise HTTPException(status_code=503, detail="La capa Oro no está disponible.") from exc
    return {"status": "ok"}


@app.get("/precios/actual", summary="Último precio semanal de cada combustible")
def precios_actual() -> list[dict]:
    rows = _rows("precio_semanal", [
        "semana", "combustible", "precio_promedio", "precio_minimo", "precio_maximo", "n_lecturas"
    ])
    latest: dict[str, dict] = {}
    for row in rows:
        fuel = row["combustible"]
        if fuel not in latest or _week(row) > _week(latest[fuel]):
            latest[fuel] = row
    return [latest[fuel] for fuel in sorted(latest)]


@app.get("/precios", summary="Histórico semanal, del más reciente al más antiguo")
def precios(
    combustible: str | None = Query(None, description="diesel, regular o super"),
    desde: date | None = None,
    hasta: date | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    fuel = _fuel(combustible) if combustible is not None else None
    if desde and hasta and desde > hasta:
        raise HTTPException(status_code=422, detail="desde no puede ser posterior a hasta")
    rows = _rows("variacion_semanal", [
        "semana", "combustible", "precio_promedio", "precio_minimo", "precio_maximo",
        "diferencia_q", "diferencia_pct", "direccion"
    ])
    filtered = [
        row for row in rows
        if (fuel is None or row["combustible"] == fuel)
        and (desde is None or _week(row) >= desde)
        and (hasta is None or _week(row) <= hasta)
    ]
    filtered.sort(key=lambda row: (_week(row), row["combustible"]), reverse=True)
    return filtered[offset:offset + limit]


@app.get("/prediccion", summary="Pronóstico vigente según los últimos datos disponibles")
def prediccion(combustible: str = Query(..., description="diesel, regular o super")) -> dict:
    fuel = _fuel(combustible)
    rows = _rows("predicciones", [
        "semana", "combustible", "tipo", "prediccion", "probabilidad", "modelo", "_generado_en"
    ])
    forecasts = [row for row in rows if row["tipo"] == "pronostico" and row["combustible"] == fuel]
    if not forecasts:
        raise HTTPException(status_code=404, detail=f"No hay pronóstico para {fuel}.")
    latest = max(forecasts, key=lambda row: (_week(row), str(row["_generado_en"])))
    return {key: latest[key] for key in ("semana", "combustible", "prediccion", "probabilidad", "modelo")}


@app.get("/modelo/metricas", summary="Métricas de la última ejecución de Oro")
def modelo_metricas() -> dict:
    columns = [
        "run_id_mlflow", "modelo_elegido", "usa_linea_base", "modo_pocos_datos", "motivo",
        "n_ejemplos", "n_train", "n_test", "accuracy_modelo", "f1_macro_modelo",
        "accuracy_linea_base", "f1_macro_linea_base", "semana_test_inicio", "semana_test_fin", "_generado_en"
    ]
    rows = _rows("metricas_modelo", columns)
    if not rows:
        raise HTTPException(status_code=404, detail="No hay métricas de Oro.")
    return max(rows, key=lambda row: str(row["_generado_en"]))
