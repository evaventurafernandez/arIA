"""Tests de la tool landcoverAtPoint (WMS IGN GetFeatureInfo mockeado)."""

from __future__ import annotations

import pytest

from chat.tools.server.landcover_at_point import (
    _build_synthetic_query,
    landcover_at_point,
)


@pytest.fixture
def patch_wms(monkeypatch):
    captured = {}

    def _patch(payload):
        def fake_fetch(**kwargs):
            captured.update(kwargs)
            return payload
        monkeypatch.setattr("main.fetch_landcover_features_by_point", fake_fetch)
        return captured

    return _patch


def test_synthetic_bbox_uses_latlon_order_for_wms13_geographic():
    """WMS 1.3.0 + EPSG:4326 exige bbox en orden lat/lon (south, west, north, east)."""
    q = _build_synthetic_query(lon=-3.7, lat=40.4)
    assert q["crs"] == "EPSG:4326"
    south, west, north, east = (float(v) for v in q["bbox"].split(","))
    # south=lat - delta, west=lon - delta, etc. -> el primer y tercer valor son lat.
    assert south < north and west < east
    assert abs(((south + north) / 2) - 40.4) < 1e-6, "centro lat"
    assert abs(((west + east) / 2) - (-3.7)) < 1e-6, "centro lon"
    # i, j cae en el pixel central.
    assert q["i"] == q["width"] // 2
    assert q["j"] == q["height"] // 2


@pytest.mark.asyncio
async def test_returns_class_when_wms_finds_feature(patch_wms):
    """Las claves normalizadas son `label`, `code`, `code_field`,
    `source_dataset` (NO class_label / class_code, que no existen)."""
    captured = patch_wms({
        "features": [{
            "properties": {
                "label": "Bosques de frondosas",
                "code": "311",
                "code_field": "codigo_n3",
                "source_dataset": "CORINE 2018",
                "source_date": "2018",
                "secondary_label": "Forestal y semi-natural",
                "surface_ha": 12.3,
            }
        }],
        "metadata": {"source": "IGN WMS GetFeatureInfo"},
    })

    res = await landcover_at_point(lon=-3.7, lat=40.4)
    assert res["found"] is True
    assert res["label"] == "Bosques de frondosas"
    assert res["code"] == "311"
    assert res["source_dataset"] == "CORINE 2018"
    assert res["source"] == "IGN WMS GetFeatureInfo"

    # Verifica que se llamo al WMS con bbox en orden lat/lon.
    assert captured["crs"] == "EPSG:4326"
    south, west, north, east = (float(v) for v in captured["bbox"].split(","))
    assert (south + north) / 2 == pytest.approx(40.4, abs=1e-6)
    assert (west + east) / 2 == pytest.approx(-3.7, abs=1e-6)


@pytest.mark.asyncio
async def test_returns_not_found_when_no_features(patch_wms):
    patch_wms({"features": [], "metadata": {"source": "IGN WMS GetFeatureInfo"}})

    res = await landcover_at_point(lon=0.0, lat=0.0)
    assert res["found"] is False
    assert "lon" in res and "lat" in res


@pytest.mark.asyncio
async def test_wms_exception_returns_error_without_raising(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("503 Service Unavailable")
    monkeypatch.setattr("main.fetch_landcover_features_by_point", boom)

    res = await landcover_at_point(lon=-3.7, lat=40.4)
    assert res["found"] is False
    assert "error" in res
    assert "503" in res["error"]
