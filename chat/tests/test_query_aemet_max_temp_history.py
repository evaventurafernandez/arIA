"""Tests de queryAemetMaxTempHistory con query_aemet_max_temperature_stats_rows mockeado."""

from __future__ import annotations

import pytest

from chat.tools.server.query_aemet_max_temp_history import query_aemet_max_temp_history


@pytest.fixture
def patch_stats(monkeypatch):
    def _patch(rows):
        def fake_query(*args, **kwargs):
            return list(rows)
        monkeypatch.setattr("main.query_aemet_max_temperature_stats_rows", fake_query)
    return _patch


def _row(date: str, max_temp_c, warning_count=0, red=0, orange=0, yellow=0, green=0):
    return {
        "nominal_date": date,
        "coverage_expected_unit_count": 100,
        "coverage_unit_count": 100,
        "coverage_complete": True,
        "feature_count": warning_count + green,
        "warning_count": warning_count,
        "green_count": green,
        "yellow_count": yellow,
        "orange_count": orange,
        "red_count": red,
        "max_temperature_c": max_temp_c,
        "warned_area_count": warning_count,
        "source_feature_count": warning_count + green,
        "stats_generated_at": None,
    }


@pytest.mark.asyncio
async def test_peak_day_is_the_hottest(patch_stats):
    patch_stats([
        _row("2025-07-17", 35.0, warning_count=10, orange=3, yellow=7),
        _row("2025-07-18", 41.0, warning_count=44, red=12, orange=20, yellow=12),
        _row("2025-07-19", 39.0, warning_count=22, orange=10, yellow=12),
    ])

    result = await query_aemet_max_temp_history(date_from="2025-07-01", date_to="2025-07-31")

    assert result["total_days"] == 3
    assert result["peak_day"]["nominal_date"] == "2025-07-18"
    assert result["peak_day"]["max_temperature_c"] == 41.0
    assert result["peak_day"]["warning_count"] == 44
    assert result["peak_day"]["red_count"] == 12
    assert result["totals_by_level"]["Rojo"] == 12
    assert result["total_warning_count"] == 10 + 44 + 22


@pytest.mark.asyncio
async def test_handles_none_max_temperature(patch_stats):
    """Algunos dias pueden no tener max_temperature_c registrada."""
    patch_stats([
        _row("2025-05-01", None, warning_count=0),
        _row("2025-05-02", 30.0, warning_count=5, yellow=5),
    ])

    result = await query_aemet_max_temp_history(date_from="2025-05-01", date_to="2025-05-02")

    assert result["peak_day"]["nominal_date"] == "2025-05-02"
    assert result["peak_day"]["max_temperature_c"] == 30.0


@pytest.mark.asyncio
async def test_empty_rows_returns_no_peak(patch_stats):
    patch_stats([])
    result = await query_aemet_max_temp_history(date_from="2020-01-01", date_to="2020-01-31")
    assert result["total_days"] == 0
    assert result["peak_day"] is None
    assert result["items"] == []
    assert result["total_warning_count"] == 0


@pytest.mark.asyncio
async def test_limit_truncates_items(patch_stats):
    rows = [_row(f"2025-07-{day:02d}", 30.0 + day * 0.1, warning_count=1) for day in range(1, 11)]
    patch_stats(rows)
    result = await query_aemet_max_temp_history(date_from="2025-07-01", date_to="2025-07-10", limit=3)
    assert result["total_days"] == 10
    assert result["returned"] == 3
    assert result["truncated"] is True


@pytest.mark.asyncio
async def test_filters_are_echoed(patch_stats):
    patch_stats([])
    result = await query_aemet_max_temp_history(date_from="2025-07-01", date_to="2025-07-31")
    assert result["filters"] == {"date_from": "2025-07-01", "date_to": "2025-07-31"}
