"""Tests del orquestador para tools CLIENTE: se acumulan en client_actions, no se ejecutan."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from chat.orchestrator import OrchestratorConfig, run_chat
from chat.schemas import ChatMessage


URL = "https://llm.test.invalid/v1/chat/completions"


def _msg_assistant_text(text: str) -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def _msg_assistant_tool_call(name: str, arguments: dict[str, Any], call_id: str = "c1") -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(arguments)},
                        }
                    ],
                }
            }
        ]
    }


def _msg_assistant_two_tool_calls(
    name_a: str, args_a: dict, name_b: str, args_b: dict
) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {"name": name_a, "arguments": json.dumps(args_a)},
                        },
                        {
                            "id": "c2",
                            "type": "function",
                            "function": {"name": name_b, "arguments": json.dumps(args_b)},
                        },
                    ],
                }
            }
        ]
    }


def _config(max_iterations: int = 4) -> OrchestratorConfig:
    return OrchestratorConfig(
        api_url=URL,
        api_key=None,
        model="test-model",
        max_iterations=max_iterations,
        timeout=5.0,
    )


@pytest.mark.asyncio
async def test_client_tool_call_is_queued_not_executed():
    """LLM invoca flyTo -> orquestador la mete en client_actions y devuelve 'queued'."""
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json=_msg_assistant_tool_call("flyTo", {"bbox": [-10.0, 35.0, 5.0, 44.0]}),
                ),
                httpx.Response(200, json=_msg_assistant_text("ok")),
            ]
        )

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="centra en Espana")],
            config=_config(),
        )

        assert len(reply.client_actions) == 1
        ca = reply.client_actions[0]
        assert ca.action == "flyTo"
        assert ca.id == "ca-1"
        assert ca.arguments == {"bbox": [-10.0, 35.0, 5.0, 44.0]}

        # El trace tambien registra la accion encolada.
        assert len(reply.trace) == 1
        assert reply.trace[0].tool == "flyTo"
        assert reply.trace[0].ok is True
        assert "queued" in reply.trace[0].result_summary


@pytest.mark.asyncio
async def test_multiple_client_actions_keep_order():
    """flyTo + toggleLayer en un mismo turno: orden y ids correlativos."""
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json=_msg_assistant_two_tool_calls(
                        "flyTo",
                        {"coords": {"lat": 42.5, "lon": -7.5, "zoom": 8}},
                        "toggleLayer",
                        {"name": "fires", "on": True},
                    ),
                ),
                httpx.Response(200, json=_msg_assistant_text("listo")),
            ]
        )

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="vete a Galicia y activa los focos")],
            config=_config(),
        )

        assert [ca.action for ca in reply.client_actions] == ["flyTo", "toggleLayer"]
        assert [ca.id for ca in reply.client_actions] == ["ca-1", "ca-2"]


@pytest.mark.asyncio
async def test_mixed_server_and_client_tools_preserve_order(monkeypatch):
    """queryAlerts (server) + flyTo (client) en el mismo turno: ambos llegan al trace."""
    monkeypatch.setattr("main.alerts_cache", [])

    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json=_msg_assistant_two_tool_calls(
                        "queryAlerts",
                        {"phenomenon": "viento"},
                        "flyTo",
                        {"bbox": [-10.0, 35.0, 5.0, 44.0]},
                    ),
                ),
                httpx.Response(200, json=_msg_assistant_text("ok")),
            ]
        )

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="x")],
            config=_config(),
        )

        # Server tool produjo un resumen JSON; client tool produjo 'queued'.
        traces_by_tool = {t.tool: t for t in reply.trace}
        assert "queryAlerts" in traces_by_tool
        assert traces_by_tool["queryAlerts"].ok is True
        assert "total_matched" in traces_by_tool["queryAlerts"].result_summary
        assert "flyTo" in traces_by_tool
        assert "queued" in traces_by_tool["flyTo"].result_summary

        # client_actions solo contiene la client tool.
        assert len(reply.client_actions) == 1
        assert reply.client_actions[0].action == "flyTo"


@pytest.mark.asyncio
async def test_invalid_client_args_dont_queue():
    """Si los args de una client tool no validan, no se encola y se reinyecta tool_error."""
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(
            side_effect=[
                # bbox de longitud invalida (solo 2 elementos)
                httpx.Response(200, json=_msg_assistant_tool_call("flyTo", {"bbox": [1.0, 2.0]})),
                httpx.Response(200, json=_msg_assistant_text("ok")),
            ]
        )

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="x")],
            config=_config(),
        )

        assert reply.client_actions == []
        assert reply.trace[0].ok is False
        assert "tool_error" in (reply.trace[0].error or "")