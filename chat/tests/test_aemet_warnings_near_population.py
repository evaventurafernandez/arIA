"""Tests de aemetWarningsNearPopulation con pool PostGIS mockeado."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from chat.tools.server.aemet_warnings_near_population import aemet_warnings_near_population


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
        self.last_cursor = None

    @contextmanager
    def connection(self):
        conn = FakeConn(self.rows)
        self.last_cursor = conn.cursor_obj
        yield conn


@pytest.fixture
def patch_pool(monkeypatch):
    def _patch(rows):
        pool = FakePool(rows)
        monkeypatch.setattr("main.get_db_pool", lambda: pool)
        return pool
    return _patch


def _row(
    feature_id: str,
    area_name: str,
    level: str,
    level_rank: int,
    temp_c: float,
    nucleo: str,
    habitantes: int,
    distance_m: float,
):
    return (
        feature_id,
        area_name,
        f"AC{level_rank:02d}",  # area_code
        level,
        level_rank,
        temp_c,
        "100",  # probability
        None,   # onset_at
        None,   # expires_at
        "nuc-" + feature_id,
        nucleo,
        habitantes,
        -4.0,   # nucleo_lon
        37.0,   # nucleo_lat
        distance_m,
    )


@pytest.mark.asyncio
async def test_returns_items_sorted_by_hottest_first(patch_pool):
    """Mantiene el orden que viene del SQL (temperature_max_c DESC)."""
    rows = [
        _row("f1", "Vega del Guadalquivir", "Rojo", 4, 44.0, "Ecija", 40000, 0.0),
        _row("f2", "Vega del Genil", "Naranja", 3, 41.0, "Loja", 21000, 850.0),
        _row("f3", "Hoya de Antequera", "Amarillo", 2, 38.0, "Antequera", 41000, 12000.0),
    ]
    patch_pool(rows)
    res = await aemet_warnings_near_population(date="2025-07-18")

    assert res["returned"] == 3
    assert res["items"][0]["area_name"] == "Vega del Guadalquivir"
    assert res["items"][0]["temperature_max_c"] == 44.0
    assert res["items"][0]["nucleo_nombre"] == "Ecija"
    assert res["items"][0]["distance_m"] == 0.0
    assert res["peak_temperature_c"] == 44.0


@pytest.mark.asyncio
async def test_filters_applied_in_sql(patch_pool):
    """level y min_temperature_c se transmiten al SQL como condiciones WHERE."""
    pool = patch_pool([])
    await aemet_warnings_near_population(
        date="2025-07-18",
        level="Rojo",
        min_temperature_c=40.0,
        distance_m=10000,
    )
    cursor = pool.last_cursor
    assert cursor is not None
    sql = cursor.last_sql or ""
    assert "f.level_label = %s" in sql
    assert "f.temperature_max_c >= %s" in sql
    assert "f.is_warning" in sql  # warnings_only por defecto
    # El primer param es distance_m del LATERAL, luego level, luego min temp,
    # luego date, luego limit+1.
    assert cursor.last_params == (10000, "Rojo", 40.0, "2025-07-18", 51)


@pytest.mark.asyncio
async def test_warnings_only_false_drops_is_warning(patch_pool):
    pool = patch_pool([])
    await aemet_warnings_near_population(date="2025-07-18", warnings_only=False)
    sql = pool.last_cursor.last_sql or ""
    assert "f.is_warning" not in sql


@pytest.mark.asyncio
async def test_truncates_when_more_than_limit(patch_pool):
    rows = [
        _row(f"f{i}", f"Zona{i}", "Naranja", 3, 40.0 - i * 0.1, f"P{i}", 5000, 1000.0 + i)
        for i in range(6)
    ]
    patch_pool(rows)
    res = await aemet_warnings_near_population(date="2025-07-18", limit=5)
    assert res["truncated"] is True
    assert res["returned"] == 5


@pytest.mark.asyncio
async def test_filters_echo_date_as_single_day(patch_pool):
    """El bloque 'filters' devuelve date_from == date_to == date para que el
    auto-setLayerDate del orquestador situe el slider en ese dia."""
    patch_pool([])
    res = await aemet_warnings_near_population(date="2025-07-18")
    assert res["filters"]["date_from"] == "2025-07-18"
    assert res["filters"]["date_to"] == "2025-07-18"


@pytest.mark.asyncio
async def test_nucleo_strategy_closest_uses_knn_order(patch_pool):
    """closest (default) -> LATERAL ordena por '<->' (KNN geometrico)."""
    pool = patch_pool([])
    await aemet_warnings_near_population(date="2025-07-18")
    sql = pool.last_cursor.last_sql or ""
    assert "ORDER BY f.geom <-> geom" in sql
    assert "ORDER BY habitantes" not in sql


@pytest.mark.asyncio
async def test_nucleo_strategy_most_populated_orders_by_habitantes(patch_pool):
    """most_populated -> LATERAL ordena por habitantes DESC, rompe empates por ST_Distance."""
    pool = patch_pool([])
    await aemet_warnings_near_population(date="2025-08-12", nucleo_strategy="most_populated")
    sql = pool.last_cursor.last_sql or ""
    assert "ORDER BY habitantes DESC NULLS LAST" in sql
    assert "ST_Distance(f.geom::geography, geom::geography) ASC" in sql
    # El KNN <-> ya NO debe estar en este caso.
    assert "f.geom <-> geom" not in sql


@pytest.mark.asyncio
async def test_nucleo_strategy_echoed_in_filters(patch_pool):
    """La respuesta declara la estrategia usada para que el LLM pueda razonar sobre ella."""
    patch_pool([])
    res_default = await aemet_warnings_near_population(date="2025-07-18")
    assert res_default["filters"]["nucleo_strategy"] == "closest"

    patch_pool([])
    res_pop = await aemet_warnings_near_population(date="2025-07-18", nucleo_strategy="most_populated")
    assert res_pop["filters"]["nucleo_strategy"] == "most_populated"
    assert "habitantes DESC" in res_pop["operation"]


@pytest.mark.asyncio
async def test_db_unavailable_returns_error_without_raising(monkeypatch):
    def fail_pool():
        raise RuntimeError("pool not initialised")
    monkeypatch.setattr("main.get_db_pool", fail_pool)
    res = await aemet_warnings_near_population(date="2025-07-18")
    assert "error" in res
    assert res["total_matched"] == 0
    assert res["items"] == []
