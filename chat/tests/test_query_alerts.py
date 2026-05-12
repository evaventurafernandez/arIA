"""Tests de la tool server-side queryAlerts filtrando alerts_cache."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from chat.tools.server.query_alerts import query_alerts


def _alert(
    *,
    aid: str,
    event: str,
    level: str = "Amarillo",
    area: str = "Madrid",
    onset_offset_h: int = -1,
    expires_offset_h: int = 6,
) -> dict:
    now = datetime.now()
    return {
        "id": aid,
        "event": event,
        "level": level,
        "level_color": "#FFD700",
        "area_name": area,
        "description": "",
        "instruction": "",
        "onset": (now + timedelta(hours=onset_offset_h)).isoformat(timespec="seconds"),
        "expires": (now + timedelta(hours=expires_offset_h)).isoformat(timespec="seconds"),
        "polygon": None,
        "source": "aemet",
    }


@pytest.fixture
def sample_alerts(monkeypatch):
    alerts = [
        _alert(aid="a1", event="Temperaturas maximas", level="Naranja", area="Madrid"),
        _alert(aid="a2", event="Temperaturas maximas", level="Rojo", area="Sevilla"),
        _alert(aid="a3", event="Viento", level="Amarillo", area="Asturias"),
        _alert(aid="a4", event="Lluvias", level="Verde", area="Galicia", expires_offset_h=-2),  # expirado
        _alert(aid="a5", event="Viento", level="Naranja", area="Cantabria", onset_offset_h=24),  # proximo
    ]
    monkeypatch.setattr("main.alerts_cache", alerts)
    return alerts


@pytest.mark.asyncio
async def test_returns_all_vigent_by_default(sample_alerts):
    result = await query_alerts()
    # a4 expirado y a5 proximo no son vigentes -> quedan a1, a2, a3.
    assert result["total_matched"] == 3
    ids = {item["id"] for item in result["items"]}
    assert ids == {"a1", "a2", "a3"}


@pytest.mark.asyncio
async def test_filter_by_phenomenon_substring(sample_alerts):
    result = await query_alerts(phenomenon="temperatura")
    assert result["total_matched"] == 2
    assert result["summary_by_phenomenon"] == {"Temperaturas maximas": 2}


@pytest.mark.asyncio
async def test_filter_by_level(sample_alerts):
    result = await query_alerts(level="Rojo")
    assert result["total_matched"] == 1
    assert result["items"][0]["area_name"] == "Sevilla"


@pytest.mark.asyncio
async def test_status_proximo_finds_future_alert(sample_alerts):
    result = await query_alerts(status="proximo")
    assert result["total_matched"] == 1
    assert result["items"][0]["id"] == "a5"


@pytest.mark.asyncio
async def test_status_expirado_finds_past_alert(sample_alerts):
    result = await query_alerts(status="expirado")
    assert result["total_matched"] == 1
    assert result["items"][0]["id"] == "a4"


@pytest.mark.asyncio
async def test_limit_truncates_items(sample_alerts):
    result = await query_alerts(limit=1)
    assert result["total_matched"] == 3
    assert result["returned"] == 1
    assert result["truncated"] is True


@pytest.mark.asyncio
async def test_empty_cache_returns_zero(monkeypatch):
    monkeypatch.setattr("main.alerts_cache", [])
    result = await query_alerts(phenomenon="viento")
    assert result["total_matched"] == 0
    assert result["items"] == []
    assert result["truncated"] is False
