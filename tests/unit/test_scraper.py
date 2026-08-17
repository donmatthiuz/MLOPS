from __future__ import annotations

from unittest.mock import Mock

from gasolina_gt.config import load_config
from gasolina_gt.scraping.price_scraper import obtener_precio_referencia


def test_scraper_usa_fixture_si_falla_red(monkeypatch) -> None:
    import gasolina_gt.scraping.price_scraper as modulo

    monkeypatch.setattr(modulo.requests, "get", Mock(side_effect=OSError("sin red")))
    resultado = obtener_precio_referencia("gasolina", load_config())
    assert resultado.es_offline_fixture is True
    assert resultado.precio_gtq_por_galon > 0
