"""Tests del endpoint /api/chat/stream y del orquestador en modo streaming.

El orquestador hace la llamada al LLM en modo NO-streaming (vLLM/Gemma tiene
un bug que corrompe `tool_call.arguments` con numeros negativos cuando se
emite token-a-token). El frontend percibe streaming porque los eventos
salen a medida que el orquestador procesa las iteraciones (tool_call_start
-> done -> siguiente iteracion -> final_block).
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from chat.llm_client import accumulate_streamed_tool_calls
from chat.orchestrator import OrchestratorConfig, run_chat_stream
from chat.schemas import ChatMessage
from chat.tests.conftest import LLM_API_URL


def _msg_text(text: str) -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def _msg_tool_call(name: str, arguments: dict[str, Any], call_id: str = "c1") -> dict[str, Any]:
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
        api_url=LLM_API_URL, api_key=None, model="test-model",
        max_iterations=max_iterations, timeout=5.0,
    )


# ---- accumulate_streamed_tool_calls (utilidad del cliente, sigue util por si
# en el futuro se reactiva el streaming a nivel de token) ----


def test_accumulate_streamed_tool_calls_joins_partial_arguments():
    deltas = [
        {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "queryAlerts", "arguments": '{"phen'}}]},
        {"tool_calls": [{"index": 0, "function": {"arguments": 'omenon": "viento"}'}}]},
    ]
    out = accumulate_streamed_tool_calls(deltas)
    assert out == [{"id": "c1", "name": "queryAlerts", "arguments_raw": '{"phenomenon": "viento"}'}]


def test_accumulate_preserves_order_by_index():
    deltas = [
        {"tool_calls": [{"index": 1, "id": "b", "function": {"name": "toggleLayer", "arguments": '{"name":"fires","on":true}'}}]},
        {"tool_calls": [{"index": 0, "id": "a", "function": {"name": "flyTo", "arguments": '{"bbox":[0,0,1,1]}'}}]},
    ]
    out = accumulate_streamed_tool_calls(deltas)
    assert [c["name"] for c in out] == ["flyTo", "toggleLayer"]


# ---- run_chat_stream end-to-end (no streaming interno) ----


@pytest.mark.asyncio
async def test_stream_emits_final_blocks_for_text_response():
    final_text = (
        "**[Consulta Interpretada]** abc\n\n"
        "**[Operaciones Geoespaciales]** def\n\n"
        "**[Resultados]** ghi\n\n"
        "**[Interpretacion para Emergencias]** jkl\n"
    )
    with respx.mock(assert_all_called=False) as router:
        router.post(LLM_API_URL).respond(status_code=200, json=_msg_text(final_text))
        events = []
        async for ev in run_chat_stream(
            user_messages=[ChatMessage(role="user", content="x")],
            config=_config(),
        ):
            events.append(ev)

        final_blocks = [e for e in events if e["type"] == "final_block"]
        keys = [e["key"] for e in final_blocks]
        assert keys == ["interpretacion", "operaciones", "resultados", "interpretacion_emergencia"]
        assert events[-1]["type"] == "done"
        assert events[-1]["truncated"] is False


@pytest.mark.asyncio
async def test_stream_emits_tool_call_start_and_done(monkeypatch):
    monkeypatch.setattr("main.alerts_cache", [])
    with respx.mock(assert_all_called=False) as router:
        router.post(LLM_API_URL).mock(
            side_effect=[
                httpx.Response(200, json=_msg_tool_call("queryAlerts", {"phenomenon": "viento"})),
                httpx.Response(200, json=_msg_text("texto final")),
            ]
        )
        events = []
        async for ev in run_chat_stream(
            user_messages=[ChatMessage(role="user", content="x")],
            config=_config(),
        ):
            events.append(ev)

        starts = [e for e in events if e["type"] == "tool_call_start"]
        dones = [e for e in events if e["type"] == "tool_call_done"]
        assert len(starts) == 1
        assert starts[0]["tool"] == "queryAlerts"
        assert starts[0]["arguments"] == {"phenomenon": "viento"}
        assert len(dones) == 1
        assert dones[0]["ok"] is True


@pytest.mark.asyncio
async def test_stream_emits_client_action_for_client_tool():
    with respx.mock(assert_all_called=False) as router:
        router.post(LLM_API_URL).mock(
            side_effect=[
                httpx.Response(200, json=_msg_tool_call("flyTo", {"bbox": [-10.0, 35.0, 5.0, 44.0]})),
                httpx.Response(200, json=_msg_text("ok")),
            ]
        )
        events = []
        async for ev in run_chat_stream(
            user_messages=[ChatMessage(role="user", content="x")],
            config=_config(),
        ):
            events.append(ev)

        client_actions = [e for e in events if e["type"] == "client_action"]
        assert len(client_actions) == 1
        assert client_actions[0]["action"] == "flyTo"
        assert client_actions[0]["arguments"] == {"bbox": [-10.0, 35.0, 5.0, 44.0]}
        assert client_actions[0]["id"] == "ca-1"


@pytest.mark.asyncio
async def test_stream_event_order_tool_then_final_block():
    """Los eventos de tool deben preceder a los final_block y al done."""
    with respx.mock(assert_all_called=False) as router:
        router.post(LLM_API_URL).mock(
            side_effect=[
                httpx.Response(200, json=_msg_tool_call("explainTerm", {"term": "FRP"})),
                httpx.Response(200, json=_msg_text("**[Consulta Interpretada]** ok\n")),
            ]
        )
        types: list[str] = []
        async for ev in run_chat_stream(
            user_messages=[ChatMessage(role="user", content="que es FRP")],
            config=_config(),
        ):
            types.append(ev["type"])

        assert types.index("tool_call_start") < types.index("tool_call_done")
        assert types.index("tool_call_done") < types.index("final_block")
        assert types[-1] == "done"


@pytest.mark.asyncio
async def test_stream_truncated_on_max_iterations():
    """Si el LLM no termina nunca, emite done con truncated=true al alcanzar el tope."""
    looping = _msg_tool_call("queryAlerts", {"phenomenon": "viento"})
    with respx.mock(assert_all_called=False) as router:
        router.post(LLM_API_URL).respond(status_code=200, json=looping)
        events = []
        async for ev in run_chat_stream(
            user_messages=[ChatMessage(role="user", content="x")],
            config=_config(max_iterations=2),
        ):
            events.append(ev)

        assert events[-1]["type"] == "done"
        assert events[-1]["truncated"] is True
