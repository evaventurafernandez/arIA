"""Tests del registro central de tools (chat.tools)."""

from __future__ import annotations

import pytest

from chat.tools import (
    TOOLS,
    ServerTool,
    get_openai_tool_specs,
    list_tool_names,
    server_tool,
)


def test_initial_registry_contains_phase1_tools():
    # Las 3 tools de Fase 1 se autorregistran al importar chat.tools.
    for name in ("queryAlerts", "queryFires", "queryBurntArea"):
        assert name in TOOLS, f"Tool '{name}' no esta en el registro"
        tool = TOOLS[name]
        assert isinstance(tool, ServerTool)
        assert tool.parameters["type"] == "object"


def test_get_openai_tool_specs_shape():
    specs = get_openai_tool_specs()
    assert isinstance(specs, list)
    assert all(s["type"] == "function" for s in specs)
    names = [s["function"]["name"] for s in specs]
    for required in ("queryAlerts", "queryFires", "queryBurntArea"):
        assert required in names


def test_list_tool_names_matches_registry():
    assert set(list_tool_names()) == set(TOOLS.keys())


def test_decorator_rejects_duplicates():
    async def _noop():
        return None

    # Registrar primera vez con un nombre nuevo.
    server_tool(name="__test_dup__", description="d", parameters={"type": "object"})(_noop)
    try:
        with pytest.raises(ValueError, match="ya registrada"):
            server_tool(name="__test_dup__", description="d", parameters={"type": "object"})(_noop)
    finally:
        TOOLS.pop("__test_dup__", None)
