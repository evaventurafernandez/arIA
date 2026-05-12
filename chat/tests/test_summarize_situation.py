"""Tests de summarizeSituation: composicion concurrente sobre tools existentes."""

from __future__ import annotations

import pytest

from chat.tools.server.summarize_situation import summarize_situation


@pytest.mark.asyncio
async def test_combines_alerts_and_fires(monkeypatch):
    monkeypatch.setattr("main.alerts_cache", [
        {
            "id": "a1", "event": "Viento", "level": "Naranja",
            "level_color": "#FFA500", "area_name": "Madrid",
            "description": "", "instruction": "",
            "onset": "2026-05-12T00:00:00",
            "expires": "2030-01-01T00:00:00",
            "polygon": None, "source": "aemet",
        },
    ])

    async def fake_fetch():
        return [{
            "id": "f1", "latitude": 40, "longitude": -3, "frp": 25.0,
            "acq_date": "2026-05-12", "acq_time": "1200", "satellite": "NOAA-20",
            "firms_source": "VIIRS_NOAA20_SP", "confidence_label": "nominal",
            "intensity_label": "Medio", "source": "firms",
        }]
    monkeypatch.setattr("main.fetch_spain_hotspots", fake_fetch)

    res = await summarize_situation(scope="nacional")
    assert res["scope"] == "nacional"
    assert res["alerts_total"] == 1
    assert res["fires_total"] == 1
    assert res["fires_max_frp"] == 25.0
    assert "alerts" in res["components"]
    assert "fires" in res["components"]
    assert "burnt_area" not in res["components"]


@pytest.mark.asyncio
async def test_handles_component_failures_without_raising(monkeypatch):
    monkeypatch.setattr("main.alerts_cache", [])

    async def fail_fetch():
        raise RuntimeError("FIRMS down")
    monkeypatch.setattr("main.fetch_spain_hotspots", fail_fetch)

    res = await summarize_situation(scope="nacional")
    assert res["alerts_total"] == 0
    assert "error" in res["components"]["fires"]
    assert "FIRMS down" in res["components"]["fires"]["error"]


@pytest.mark.asyncio
async def test_include_burnt_area_optional(monkeypatch):
    monkeypatch.setattr("main.alerts_cache", [])

    async def fake_fetch():
        return []
    monkeypatch.setattr("main.fetch_spain_hotspots", fake_fetch)

    def fake_burnt(*a, **kw):
        return [
            {"nominal_date": "2025-08-01", "burned_area_ha": 100.0, "burned_pixel_count": 10,
             "area_code": "ES", "area_label": "Espana", "burned_fraction_sum": 0.1,
             "tiles_generated": True, "stats_generated_at": None},
        ]
    monkeypatch.setattr("main.query_burnt_area_stats_rows", fake_burnt)

    res = await summarize_situation(scope="nacional", include_burnt_area=True)
    assert "burnt_area" in res["components"]
    assert res["burnt_area_total_ha_last30d"] == 100.0
