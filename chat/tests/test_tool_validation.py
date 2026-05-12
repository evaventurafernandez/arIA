"""Tests de la validacion defensiva de argumentos de tools."""

from __future__ import annotations

import pytest

from chat.orchestrator import _validate_args


def test_unknown_tool_returns_error_with_catalog():
    ok, err = _validate_args("noSuchTool", {})
    assert ok is False
    assert "no existe" in err
    assert "queryAlerts" in err  # incluye el catalogo


def test_non_dict_args_are_rejected():
    ok, err = _validate_args("queryAlerts", "not a dict")
    assert ok is False
    assert "objeto JSON" in err


def test_query_alerts_accepts_valid_args():
    ok, err = _validate_args(
        "queryAlerts",
        {"phenomenon": "viento", "level": "Naranja", "status": "vigente"},
    )
    assert ok is True
    assert err == ""


def test_query_alerts_rejects_invalid_level():
    ok, err = _validate_args("queryAlerts", {"level": "Morado"})
    assert ok is False
    assert "Morado" in err or "enum" in err


def test_query_alerts_rejects_unknown_field():
    """additionalProperties: False protege contra 'arrastre' de campos imaginados."""
    ok, err = _validate_args("queryAlerts", {"unknownField": "x"})
    assert ok is False


def test_query_fires_validates_bbox_shape():
    # bbox correcto
    ok, _ = _validate_args("queryFires", {"bbox": [-10.0, 35.0, 5.0, 44.0]})
    assert ok is True

    # bbox con menos de 4 valores
    ok, err = _validate_args("queryFires", {"bbox": [1.0, 2.0]})
    assert ok is False


def test_query_burnt_area_rejects_excessive_limit():
    ok, err = _validate_args("queryBurntArea", {"limit": 5000})
    assert ok is False
