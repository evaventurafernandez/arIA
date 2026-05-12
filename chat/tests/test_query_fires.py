"""Tests de la tool server-side queryFires con fetch_spain_hotspots mockeado."""

from __future__ import annotations

import pytest

from chat.tools.server.query_fires import query_fires


def _fire(
    *,
    fid: str,
    lat: float,
    lon: float,
    frp: float,
    sensor: str = "VIIRS_NOAA20_SP",
    confidence_label: str = "nominal",
) -> dict:
    return {
        "id": fid,
        "latitude": lat,
        "longitude": lon,
        "frp": frp,
        "acq_date": "2026-05-04",
        "acq_time": "1200",
        "satellite": "NOAA-20",
        "firms_source": sensor,
        "confidence_label": confidence_label,
        "intensity_label": "Medio",
        "source": "firms",
    }


@pytest.fixture
def patch_hotspots(monkeypatch):
    """Sustituye fetch_spain_hotspots por una corrutina con datos fijos."""

    def _patch(fires):
        async def fake_fetch():
            return list(fires)
        monkeypatch.setattr("main.fetch_spain_hotspots", fake_fetch)

    return _patch


@pytest.mark.asyncio
async def test_returns_all_sorted_by_frp_desc(patch_hotspots):
    patch_hotspots([
        _fire(fid="f1", lat=40.0, lon=-3.0, frp=5.0),
        _fire(fid="f2", lat=41.0, lon=-4.0, frp=50.0),
        _fire(fid="f3", lat=42.0, lon=-5.0, frp=15.0),
    ])
    result = await query_fires()
    frps = [item["frp"] for item in result["items"]]
    assert frps == sorted(frps, reverse=True)
    assert result["max_frp"] == 50.0


@pytest.mark.asyncio
async def test_filter_by_sensor(patch_hotspots):
    patch_hotspots([
        _fire(fid="f1", lat=40.0, lon=-3.0, frp=5.0, sensor="VIIRS_NOAA20_SP"),
        _fire(fid="f2", lat=41.0, lon=-4.0, frp=10.0, sensor="VIIRS_SNPP_SP"),
    ])
    result = await query_fires(sensor="VIIRS_SNPP_SP")
    assert result["total_matched"] == 1
    assert result["items"][0]["id"] == "f2"


@pytest.mark.asyncio
async def test_filter_by_bbox(patch_hotspots):
    patch_hotspots([
        _fire(fid="dentro", lat=40.0, lon=-3.0, frp=5.0),
        _fire(fid="fuera", lat=10.0, lon=-3.0, frp=5.0),
    ])
    result = await query_fires(bbox=[-10.0, 35.0, 5.0, 44.0])
    assert result["total_matched"] == 1
    assert result["items"][0]["id"] == "dentro"


@pytest.mark.asyncio
async def test_filter_by_min_frp(patch_hotspots):
    patch_hotspots([
        _fire(fid="bajo", lat=40.0, lon=-3.0, frp=5.0),
        _fire(fid="alto", lat=41.0, lon=-4.0, frp=100.0),
    ])
    result = await query_fires(min_frp=50.0)
    assert result["total_matched"] == 1
    assert result["items"][0]["id"] == "alto"


@pytest.mark.asyncio
async def test_filter_by_confidence(patch_hotspots):
    patch_hotspots([
        _fire(fid="nom", lat=40.0, lon=-3.0, frp=5.0, confidence_label="nominal"),
        _fire(fid="alt", lat=41.0, lon=-4.0, frp=10.0, confidence_label="alta"),
    ])
    result = await query_fires(confidence="alta")
    assert result["total_matched"] == 1
    assert result["items"][0]["id"] == "alt"


@pytest.mark.asyncio
async def test_empty_fetch_returns_zero(patch_hotspots):
    patch_hotspots([])
    result = await query_fires()
    assert result["total_matched"] == 0
    assert result["max_frp"] == 0.0
