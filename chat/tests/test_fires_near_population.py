"""Tests de firesNearPopulation con pool PostGIS mockeado."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from chat.tools.server.fires_near_population import fires_near_population


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.last_sql = None
        self.last_params = None

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def execute(self, sql, params):
        self.last_sql = sql
        self.last_params = params

    def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, rows):
        self.cursor_obj = FakeCursor(rows)
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def cursor(self): return self.cursor_obj


class FakePool:
    def __init__(self, rows):
        self.rows = rows
    @contextmanager
    def connection(self):
        yield FakeConn(self.rows)


@pytest.fixture
def patch_pool(monkeypatch):
    def _patch(rows):
        pool = FakePool(rows)
        monkeypatch.setattr("main.get_db_pool", lambda: pool)
        return pool
    return _patch


@pytest.mark.asyncio
async def test_returns_items_sorted_by_distance(patch_pool):
    rows = [
        # (id, sensor, acq_date, frp, confidence, lat, lon, nucleo, hab, dist_m)
        ("1", "VIIRS_NOAA20_SP", "2025-08-15", 30.0, "n", 42.5, -7.5, "Lalin", 13000, 850.5),
        ("2", "VIIRS_SNPP_SP", "2025-08-16", 12.0, "n", 42.6, -7.4, "Silleda", 9000, 1500.0),
    ]
    patch_pool(rows)
    res = await fires_near_population(date_from="2025-08-01", date_to="2025-08-31")
    assert res["returned"] == 2
    assert res["items"][0]["nucleo_nombre"] == "Lalin"
    assert res["items"][0]["distance_m"] == 850.5


@pytest.mark.asyncio
async def test_truncates_when_more_than_limit(patch_pool):
    rows = [
        ("i" + str(i), "VIIRS_NOAA20_SP", "2025-08-15", 10.0, "n",
         40 + i*0.01, -3 - i*0.01, f"P{i}", 1000, 500.0 + i)
        for i in range(6)
    ]
    patch_pool(rows)
    res = await fires_near_population(date_from="2025-08-01", date_to="2025-08-31", limit=5)
    assert res["truncated"] is True
    assert res["returned"] == 5


@pytest.mark.asyncio
async def test_db_unavailable_returns_error_without_raising(monkeypatch):
    def fail_pool():
        raise RuntimeError("pool not initialised")
    monkeypatch.setattr("main.get_db_pool", fail_pool)
    res = await fires_near_population(date_from="2025-08-01", date_to="2025-08-31")
    assert "error" in res
    assert res["total_matched"] == 0
