"""Caso de borde: EFFIS fuera de alcance.

La capa EFFIS / Copernicus se elimino del proyecto. El sistema debe:
- NO registrar `compareFirmsEffis` como tool.
- NO incluir 'effis_*' en el enum de `toggleLayer`.
- Si el LLM intenta invocar `compareFirmsEffis`, el orquestador devuelve el
  catalogo (tool_error) en lugar de fallar.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from chat.orchestrator import OrchestratorConfig, run_chat
from chat.schemas import ChatMessage
from chat.tools import CLIENT_TOOLS, TOOLS
from chat.tools.client.definitions import LAYER_NAMES


URL = "https://llm.test.invalid/v1/chat/completions"


def test_compare_firms_effis_is_not_registered():
    assert "compareFirmsEffis" not in TOOLS
    assert "compareFirmsEffis" not in CLIENT_TOOLS


def test_toggle_layer_enum_excludes_effis_layers():
    forbidden = {"effis_fires", "effis_fwi", "effis_dc"}
    assert forbidden.isdisjoint(set(LAYER_NAMES))


@pytest.mark.asyncio
async def test_unknown_effis_tool_returns_catalog_to_llm():
    """Si el LLM emite compareFirmsEffis, el orquestador devuelve tool_error con catalogo."""
    fake_call = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "compareFirmsEffis",
                                "arguments": json.dumps({"date": "2025-08-15"}),
                            },
                        }
                    ],
                }
            }
        ]
    }
    final_text = (
        "**[Consulta Interpretada]**\nUsuario pide comparar FIRMS con EFFIS.\n\n"
        "**[Operaciones Geoespaciales]**\nNinguna: la capa EFFIS no esta disponible.\n\n"
        "**[Resultados]**\nNo se ofrecen resultados predictivos ni inventados.\n\n"
        "**[Interpretacion para Emergencias]**\nLa capa EFFIS no esta en el alcance del visor.\n"
    )
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(
            side_effect=[
                httpx.Response(200, json=fake_call),
                httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": final_text}}]}),
            ]
        )

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="compara FIRMS y EFFIS de ayer")],
            config=OrchestratorConfig(api_url=URL, api_key=None, model="m", max_iterations=4, timeout=5.0),
        )

        assert len(reply.trace) == 1
        assert reply.trace[0].tool == "compareFirmsEffis"
        assert reply.trace[0].ok is False
        # El mensaje de error debe incluir el catalogo (lista de tools disponibles).
        err = reply.trace[0].error or ""
        assert "queryFires" in err
        assert "compareFirmsEffis" not in err.split("Tools disponibles:")[-1]
