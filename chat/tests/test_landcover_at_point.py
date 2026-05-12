"""Tests de la tool landcoverAtPoint (WMS IGN GetFeatureInfo mockeado)."""

from __future__ import annotations

import pytest

from chat.tools.server.landcover_at_point import landcover_at_point


@pytest.fixture
def patch_wms(monkeypatch):
    def _patch(payload):
        def fake_fetch(**kwargs):
            return payload
        monkeypatch.setattr("main.fetch_landcover_features_by_point", fake_fetch)
    return _patch


@pytest.mark.asyncio
async def test_returns_class_when_wms_finds_feature(patch_wms):
    patch_wms({
        "features": [{
            "properties": {
                "class_code": "311", "class_label": "Bosques de frondosas",
                "class_color": "#80FF00", "theme": "Forest",
            }
        }],
        "metadata": {"source": "IGN WMS GetFeatureInfo"},
    })

    res = await landcover_at_point(lon=-3.7, lat=40.4)
    assert res["found"] is True
    assert res["class_code"] == "311"
    assert res["class_label"] == "Bosques de frondosas"
    assert res["source"] == "IGN WMS GetFeatureInfo"


@pytest.mark.asyncio
async def test_returns_not_found_when_no_features(patch_wms):
    patch_wms({"features": [], "metadata": {"source": "IGN WMS GetFeatureInfo"}})

    res = await landcover_at_point(lon=0.0, lat=0.0)
    assert res["found"] is False
    assert "lon" in res and "lat" in res
