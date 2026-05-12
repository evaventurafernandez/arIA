"""Tests de la tool server-side queryBurntArea con query_burnt_area_stats_rows mockeado."""

from __future__ import annotations

import pytest

from chat.tools.server.query_burnt_area import query_burnt_area


@pytest.fixture
def patch_stats(monkeypatch):
    def _patch(rows):
        def fake_query(*args, **kwargs):
            return list(rows)
        monkeypatch.setattr("main.query_burnt_area_stats_rows", fake_query)

    return _patch


@pytest.mark.asyncio
async def test_aggregates_total_and_peak(patch_stats):
    patch_stats([
        {"nominal_date": "2025-05-01", "burned_area_ha": 100.0, "burned_pixel_count": 10, "area_code": "ES", "area_label": "Espana", "burned_fraction_sum": 0.1, "tiles_generated": True, "stats_generated_at": "2025-05-02T00:00:00"},
        {"nominal_date": "2025-05-02", "burned_area_ha": 250.0, "burned_pixel_count": 25, "area_code": "ES", "area_label": "Espana", "burned_fraction_sum": 0.25, "tiles_generated": True, "stats_generated_at": "2025-05-03T00:00:00"},
        {"nominal_date": "2025-05-03", "burned_area_ha": 50.0, "burned_pixel_count": 5, "area_code": "ES", "area_label": "Espana", "burned_fraction_sum": 0.05, "tiles_generated": True, "stats_generated_at": "2025-05-04T00:00:00"},
    ])

    result = await query_burnt_area(date_from="2025-05-01", date_to="2025-05-03")

    assert result["total_days"] == 3
    assert result["total_burned_area_ha"] == 400.0
    assert result["peak_day"]["nominal_date"] == "2025-05-02"
    assert result["peak_day"]["burned_area_ha"] == 250.0


@pytest.mark.asyncio
async def test_empty_rows_returns_zero(patch_stats):
    patch_stats([])
    result = await query_burnt_area(date_from="2024-01-01", date_to="2024-01-31")
    assert result["total_days"] == 0
    assert result["total_burned_area_ha"] == 0
    assert result["peak_day"] is None
    assert result["items"] == []


@pytest.mark.asyncio
async def test_limit_truncates_items(patch_stats):
    rows = [
        {
            "nominal_date": f"2025-05-{day:02d}",
            "burned_area_ha": 10.0,
            "burned_pixel_count": 1,
            "area_code": "ES",
            "area_label": "Espana",
            "burned_fraction_sum": 0.01,
            "tiles_generated": True,
            "stats_generated_at": None,
        }
        for day in range(1, 11)
    ]
    patch_stats(rows)
    result = await query_burnt_area(date_from="2025-05-01", date_to="2025-05-10", limit=3)
    assert result["total_days"] == 10
    assert result["returned"] == 3
    assert result["truncated"] is True


@pytest.mark.asyncio
async def test_handles_none_area_values(patch_stats):
    """Algunos dias pueden tener burned_area_ha None (datos no procesados)."""
    patch_stats([
        {"nominal_date": "2025-05-01", "burned_area_ha": None, "burned_pixel_count": None, "area_code": "ES", "area_label": "Espana", "burned_fraction_sum": None, "tiles_generated": False, "stats_generated_at": None},
        {"nominal_date": "2025-05-02", "burned_area_ha": 30.0, "burned_pixel_count": 3, "area_code": "ES", "area_label": "Espana", "burned_fraction_sum": 0.03, "tiles_generated": True, "stats_generated_at": None},
    ])
    result = await query_burnt_area(date_from="2025-05-01", date_to="2025-05-02")
    assert result["total_burned_area_ha"] == 30.0
    assert result["peak_day"]["nominal_date"] == "2025-05-02"
