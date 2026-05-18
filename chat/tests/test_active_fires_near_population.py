"""Tests de activeFiresNearPopulation con FIRMS vivo y PostGIS mockeados."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from chat.tools.server.active_fires_near_population import active_fires_near_population


class FakeCursor:
    def __init__(self, rows=None, exc=None):
        self._rows = rows or []
        self._exc = exc
        self.last_sql = None
        self.last_params = None

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def execute(self, sql, params):
        self.last_sql = sql
        self.last_params = params
        if self._exc:
            raise self._exc

    def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, rows=None, exc=None):
        self.cursor_obj = FakeCursor(rows, exc)
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def cursor(self): return self.cursor_obj


class FakePool:
    def __init__(self, rows=None, exc=None):
        self.rows = rows or []
        self.exc = exc
        self.conn = FakeConn(self.rows, self.exc)
    @contextmanager
    def connection(self):
        yield self.conn


@pytest.fixture
def patch_live_fires(monkeypatch):
    async def _fetch():
        return [
            {
                "id": "f1",
                "firms_source": "VIIRS_NOAA20_SP",
                "latitude": 42.5,
                "longitude": -7.5,
                "frp": 31.2,
                "confidence_label": "nominal",
                "intensity_label": "media",
                "acq_date": "2026-05-13",
                "acq_time": "1030",
                "satellite": "NOAA-20",
            }
        ]
    monkeypatch.setattr("main.fetch_spain_hotspots", _fetch)


@pytest.mark.asyncio
async def test_returns_live_fire_population_pairs(monkeypatch, patch_live_fires):
    rows = [
        # fire fields, nucleo fields, distance
        (
            "f1", "VIIRS_NOAA20_SP", "2026-05-13", "1030", "NOAA-20",
            31.2, "nominal", "media", 42.5, -7.5, "101", "Aldea", 1200,
            -7.49, 42.51, 850.45,
        )
    ]
    pool = FakePool(rows=rows)
    monkeypatch.setattr("main.get_db_pool", lambda: pool)

    res = await active_fires_near_population(distance_m=2000, population_max=5000)

    assert res["returned"] == 1
    assert res["items"][0]["nucleo_nombre"] == "Aldea"
    assert res["items"][0]["distance_m"] == 850.5
    assert res["map_layers"] == ["fires", "nucleos"]
    assert res["map_geojson"]["type"] == "FeatureCollection"
    assert len(res["map_geojson"]["features"]) == 3
    assert "ST_DWithin" in pool.conn.cursor_obj.last_sql


@pytest.mark.asyncio
async def test_filters_live_fires_before_db(monkeypatch, patch_live_fires):
    pool = FakePool(rows=[])
    monkeypatch.setattr("main.get_db_pool", lambda: pool)

    res = await active_fires_near_population(min_frp=1000)

    assert res["active_fire_candidates"] == 0
    assert res["returned"] == 0
    assert pool.conn.cursor_obj.last_sql is None


@pytest.mark.asyncio
async def test_db_unavailable_returns_error(monkeypatch, patch_live_fires):
    def fail_pool():
        raise RuntimeError("pool not initialised")
    monkeypatch.setattr("main.get_db_pool", fail_pool)

    res = await active_fires_near_population()

    assert "error" in res
    assert res["total_matched"] == 0
