"""Tests del orquestador con LLM mockeado: tool calls, fallbacks, limites."""

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


def _config(max_iterations: int = 4) -> OrchestratorConfig:
    return OrchestratorConfig(
        api_url=URL,
        api_key=None,
        model="test-model",
        max_iterations=max_iterations,
        timeout=5.0,
    )


def _final_blocks_text() -> str:
    return (
        "**[Consulta Interpretada]**\nabc\n\n"
        "**[Operaciones Geoespaciales]**\ndef\n\n"
        "**[Resultados]**\nghi\n\n"
        "**[Interpretacion para Emergencias]**\njkl\n"
    )


@pytest.mark.asyncio
async def test_full_loop_tool_then_text(monkeypatch):
    """Caso happy path: LLM pide queryAlerts, observa resultado, responde con bloques."""
    monkeypatch.setattr("main.alerts_cache", [])  # cache vacio -> tool devuelve 0

    with respx.mock(assert_all_called=False) as router:
        route = router.post(URL).mock(
            side_effect=[
                httpx.Response(200, json=_msg_assistant_tool_call("queryAlerts", {"phenomenon": "viento"})),
                httpx.Response(200, json=_msg_assistant_text(_final_blocks_text())),
            ]
        )

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="que avisos de viento hay")],
            config=_config(),
        )

        assert route.call_count == 2
        assert reply.iterations == 2
        assert reply.truncated is False
        assert reply.blocks.interpretacion == "abc"
        assert reply.blocks.resultados == "ghi"
        assert len(reply.trace) == 1
        entry = reply.trace[0]
        assert entry.tool == "queryAlerts"
        assert entry.ok is True
        assert entry.arguments == {"phenomenon": "viento"}


@pytest.mark.asyncio
async def test_invalid_args_are_reinjected_as_tool_error(monkeypatch):
    """Si los args no pasan el schema, no se ejecuta la tool; se reinyecta el error."""
    monkeypatch.setattr("main.alerts_cache", [])

    bad_call = _msg_assistant_tool_call("queryAlerts", {"limit": 9999})  # > maximum 200
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(
            side_effect=[
                httpx.Response(200, json=bad_call),
                httpx.Response(200, json=_msg_assistant_text("texto final")),
            ]
        )

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="x")],
            config=_config(),
        )

        assert len(reply.trace) == 1
        assert reply.trace[0].ok is False
        assert "tool_error" in (reply.trace[0].error or "")
        # El texto final llega al bloque interpretacion porque no hay cabeceras.
        assert reply.blocks.interpretacion == "texto final"


@pytest.mark.asyncio
async def test_unknown_tool_returns_available_list():
    fake_call = _msg_assistant_tool_call("doesNotExist", {})
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(
            side_effect=[
                httpx.Response(200, json=fake_call),
                httpx.Response(200, json=_msg_assistant_text("ok")),
            ]
        )

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="x")],
            config=_config(),
        )

        assert reply.trace[0].ok is False
        assert "queryAlerts" in (reply.trace[0].error or "")  # lista tools disponibles


@pytest.mark.asyncio
async def test_max_iterations_truncates():
    """Si el LLM no termina nunca, el orquestador para en max_iterations."""
    looping = _msg_assistant_tool_call("queryAlerts", {"limit": 1})
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).respond(status_code=200, json=looping)

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="x")],
            config=_config(max_iterations=3),
        )

        assert reply.truncated is True
        assert reply.iterations == 3


@pytest.mark.asyncio
async def test_hermes_text_tool_call_is_treated_as_structured(monkeypatch):
    """Si el LLM emite <tool_call>...</tool_call> en texto, se procesa igual."""
    monkeypatch.setattr("main.alerts_cache", [])

    hermes_text = (
        '<tool_call>{"name": "queryAlerts", "arguments": {"phenomenon": "viento"}}</tool_call>'
    )
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(
            side_effect=[
                httpx.Response(200, json=_msg_assistant_text(hermes_text)),
                httpx.Response(200, json=_msg_assistant_text("done")),
            ]
        )

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="x")],
            config=_config(),
        )

        assert len(reply.trace) == 1
        assert reply.trace[0].tool == "queryAlerts"
        assert reply.trace[0].ok is True
