"""Tests del registro central de tools (chat.tools)."""

from __future__ import annotations

import pytest

from chat.tools import (
    CLIENT_TOOLS,
    TOOLS,
    ClientTool,
    ServerTool,
    client_tool,
    get_openai_tool_specs,
    get_tool_parameters,
    is_client_tool,
    list_tool_names,
    server_tool,
)


def test_initial_registry_contains_phase1_server_tools():
    for name in ("queryAlerts", "queryFires", "queryBurntArea", "activeFiresNearPopulation"):
        assert name in TOOLS, f"Tool '{name}' no esta en el registro server"
        tool = TOOLS[name]
        assert isinstance(tool, ServerTool)
        assert tool.parameters["type"] == "object"


def test_initial_registry_contains_phase2_client_tools():
    for name in ("flyTo", "toggleLayer", "setVisibleLayers", "setFilter", "showGeoJsonResults", "getFeatureDetail"):
        assert name in CLIENT_TOOLS, f"Tool cliente '{name}' no esta en el registro"
        tool = CLIENT_TOOLS[name]
        assert isinstance(tool, ClientTool)
        assert is_client_tool(name) is True


def test_get_openai_tool_specs_includes_server_and_client():
    specs = get_openai_tool_specs()
    names = [s["function"]["name"] for s in specs]
    for required in (
        "queryAlerts",
        "queryFires",
        "queryBurntArea",
        "activeFiresNearPopulation",
        "flyTo",
        "toggleLayer",
        "setVisibleLayers",
        "setFilter",
        "showGeoJsonResults",
        "getFeatureDetail",
    ):
        assert required in names
    assert all(s["type"] == "function" for s in specs)


def test_list_tool_names_includes_both_registries():
    names = set(list_tool_names())
    assert names.issuperset(set(TOOLS.keys()))
    assert names.issuperset(set(CLIENT_TOOLS.keys()))


def test_get_tool_parameters_for_server_and_client():
    assert get_tool_parameters("queryAlerts") is TOOLS["queryAlerts"].parameters
    assert get_tool_parameters("flyTo") is CLIENT_TOOLS["flyTo"].parameters
    assert get_tool_parameters("noSuchTool") is None


def test_decorator_rejects_duplicates():
    async def _noop():
        return None

    server_tool(name="__test_dup__", description="d", parameters={"type": "object"})(_noop)
    try:
        with pytest.raises(ValueError, match="ya registrada"):
            server_tool(name="__test_dup__", description="d", parameters={"type": "object"})(_noop)
        # Tampoco se puede pisar con una cliente del mismo nombre.
        with pytest.raises(ValueError, match="ya registrada"):
            client_tool(name="__test_dup__", description="d", parameters={"type": "object"})
    finally:
        TOOLS.pop("__test_dup__", None)
        CLIENT_TOOLS.pop("__test_dup__", None)
