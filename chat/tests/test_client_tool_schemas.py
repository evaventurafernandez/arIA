"""Tests de los schemas de las tools cliente (flyTo, toggleLayer, setFilter, getFeatureDetail)."""

from __future__ import annotations

import pytest

from chat.orchestrator import _validate_args
from chat.tools.client.definitions import DATED_LAYER_NAMES, LAYER_NAMES, LEVEL_VALUES


# --------- flyTo ---------


def test_flyto_accepts_bbox():
    ok, _ = _validate_args("flyTo", {"bbox": [-10.0, 35.0, 5.0, 44.0]})
    assert ok is True


def test_flyto_accepts_coords_without_zoom():
    ok, _ = _validate_args("flyTo", {"coords": {"lat": 40.0, "lon": -3.0}})
    assert ok is True


def test_flyto_accepts_coords_with_zoom():
    ok, _ = _validate_args("flyTo", {"coords": {"lat": 40.0, "lon": -3.0, "zoom": 10}})
    assert ok is True


def test_flyto_rejects_bbox_with_wrong_length():
    ok, err = _validate_args("flyTo", {"bbox": [1.0, 2.0]})
    assert ok is False


def test_flyto_rejects_zoom_out_of_range():
    ok, err = _validate_args("flyTo", {"coords": {"lat": 40.0, "lon": -3.0, "zoom": 25}})
    assert ok is False


def test_flyto_rejects_unknown_field():
    ok, err = _validate_args("flyTo", {"target": "Galicia"})
    assert ok is False


# --------- toggleLayer ---------


@pytest.mark.parametrize("name", LAYER_NAMES)
def test_toggle_layer_accepts_each_valid_name(name: str):
    ok, _ = _validate_args("toggleLayer", {"name": name, "on": True})
    assert ok is True


def test_toggle_layer_rejects_unknown_name():
    ok, err = _validate_args("toggleLayer", {"name": "effis_fires", "on": True})
    assert ok is False, "EFFIS no debe poder activarse desde el chat"


def test_toggle_layer_requires_on_flag():
    ok, err = _validate_args("toggleLayer", {"name": "fires"})
    assert ok is False


def test_toggle_layer_rejects_extra_props():
    ok, err = _validate_args("toggleLayer", {"name": "fires", "on": True, "opacity": 0.5})
    assert ok is False


# --------- setVisibleLayers ---------


def test_set_visible_layers_accepts_known_layers():
    ok, _ = _validate_args("setVisibleLayers", {"names": ["fires", "nucleos"]})
    assert ok is True


def test_set_visible_layers_rejects_unknown_layer():
    ok, err = _validate_args("setVisibleLayers", {"names": ["fires", "roads"]})
    assert ok is False


# --------- setFilter ---------


def test_set_filter_level_accepts_array_of_known_values():
    ok, _ = _validate_args("setFilter", {"field": "level", "value": ["Naranja", "Rojo"]})
    assert ok is True


def test_set_filter_event_type_accepts_string():
    ok, _ = _validate_args("setFilter", {"field": "event_type", "value": "Aviso de vientos"})
    assert ok is True


def test_set_filter_rejects_unknown_field():
    ok, err = _validate_args("setFilter", {"field": "intensity", "value": "alta"})
    assert ok is False


# --------- showGeoJsonResults ---------


def test_show_geojson_results_accepts_feature_collection():
    ok, _ = _validate_args(
        "showGeoJsonResults",
        {
            "title": "Resultados",
            "geojson": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [-7.5, 42.5]},
                        "properties": {"kind": "fire", "label": "Foco"},
                    }
                ],
            },
        },
    )
    assert ok is True


def test_show_geojson_results_rejects_non_feature_collection():
    ok, err = _validate_args(
        "showGeoJsonResults",
        {"geojson": {"type": "Feature", "features": []}},
    )
    assert ok is False


# --------- getFeatureDetail ---------


def test_get_feature_detail_accepts_alerts():
    ok, _ = _validate_args("getFeatureDetail", {"layer": "alerts", "id": "abc123"})
    assert ok is True


def test_get_feature_detail_rejects_unsupported_layer():
    """En Fase 2 solo se admite 'alerts'. Otras capas se manejan via flyTo+coords."""
    ok, err = _validate_args("getFeatureDetail", {"layer": "fires", "id": "abc"})
    assert ok is False


# --------- setLayerDate ---------


@pytest.mark.parametrize("layer", DATED_LAYER_NAMES)
def test_set_layer_date_accepts_dated_layers(layer: str):
    ok, _ = _validate_args("setLayerDate", {"layer": layer, "date": "2025-08-16"})
    assert ok is True


def test_set_layer_date_rejects_non_dated_layer():
    ok, _ = _validate_args("setLayerDate", {"layer": "fires", "date": "2025-08-16"})
    assert ok is False


def test_set_layer_date_rejects_bad_date_format():
    ok, _ = _validate_args("setLayerDate", {"layer": "burnt_area", "date": "16/08/2025"})
    assert ok is False


def test_set_layer_date_requires_both_fields():
    ok, _ = _validate_args("setLayerDate", {"layer": "burnt_area"})
    assert ok is False
