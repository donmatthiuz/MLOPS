"""API HTTP opcional para consultar la recomendación más reciente."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from ..data.pipeline import cargar_gold_si_existe
from .recommendation import recomendacion_como_dict

app = FastAPI(title="Gasolina GT", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/recomendacion")
def recomendacion(
    combustible: str = Query("regular"), horizonte: int = Query(1, ge=1), hora: int | None = Query(None, ge=0, le=23)
) -> dict:
    gold = cargar_gold_si_existe()
    if gold is None:
        raise HTTPException(503, "No existe dataset Gold; ejecute gasolina-gt build-data.")
    try:
        return recomendacion_como_dict(gold, combustible, horizonte, hora)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(503, str(exc)) from exc
