"""Tests de firmsHotspotAnalysis con pool PostGIS mockeado."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from chat.tools.server.firms_hotspot_analysis import firms_hotspot_analysis


class FakeCursor:
    def __init__(self, rows=None, exc=None):
        self._rows = rows or []
        self._exc = exc
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params):
        if self._exc:
            raise self._exc
    def fetchall(self): return self._rows


class FakeConn:
    def __init__(self, *a, **kw): self.cur = FakeCursor(*a, **kw)
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def cursor(self): return self.cur


class FakePool:
    def __init__(self, rows=None, exc=None):
        self.rows = rows or []
        self.exc = exc
    @contextmanager
    def connection(self):
        yield FakeConn(self.rows, self.exc)


@pytest.mark.asyncio
async def test_returns_clusters_sorted_by_count(monkeypatch):
    rows = [
        # (cluster_id, count, avg_frp, max_frp, first_date, last_date, lon, lat)
        (0, 15, 35.5, 120.0, "2025-08-10", "2025-08-13", -7.5, 42.5),
        (1, 8, 18.2, 45.0, "2025-08-12", "2025-08-15", -8.1, 42.9),
    ]
    monkeypatch.setattr("main.get_db_pool", lambda: FakePool(rows=rows))
    res = await firms_hotspot_analysis(date_from="2025-08-01", date_to="2025-08-31")
    assert res["total_clusters"] == 2
    assert res["items"][0]["hotspot_count"] == 15
    assert res["items"][0]["center_lon"] == -7.5


@pytest.mark.asyncio
async def test_degrades_gracefully_on_missing_function(monkeypatch):
    """Si PostGIS < 3.1 no tiene ST_ClusterDBSCAN, la tool reporta limitacion."""
    err = Exception('function st_clusterdbscan(geometry, integer, integer) does not exist')
    monkeypatch.setattr("main.get_db_pool", lambda: FakePool(exc=err))
    res = await firms_hotspot_analysis(date_from="2025-08-01", date_to="2025-08-31")
    assert "error" in res
    assert "ST_ClusterDBSCAN" in res["error"]
    assert res["items"] == []


@pytest.mark.asyncio
async def test_db_unavailable_returns_error(monkeypatch):
    def fail():
        raise RuntimeError("pool not initialised")
    monkeypatch.setattr("main.get_db_pool", fail)
    res = await firms_hotspot_analysis(date_from="2025-08-01", date_to="2025-08-31")
    assert "error" in res


def test_sql_uses_hotspot_id_not_id():
    """Regresion: core.firms_hotspot tiene PK 'hotspot_id', no 'id'."""
    from chat.tools.server import firms_hotspot_analysis as mod
    import inspect
    source = inspect.getsource(mod)
    assert "fh.hotspot_id" in source
    # No debe quedar 'fh.id' suelto en el SQL.
    assert "fh.id," not in source
    assert "fh.id\n" not in source
