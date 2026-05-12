"""Tests de manejo de errores durante el stream del LLM."""

from __future__ import annotations

import httpx
import pytest
import respx

from chat.orchestrator import OrchestratorConfig, run_chat_stream
from chat.schemas import ChatMessage
from chat.tests.conftest import LLM_API_URL


def _config() -> OrchestratorConfig:
    return OrchestratorConfig(
        api_url=LLM_API_URL, api_key=None, model="test-model",
        max_iterations=2, timeout=2.0,
    )


@pytest.mark.asyncio
async def test_stream_emits_error_when_llm_returns_5xx():
    with respx.mock(assert_all_called=False) as router:
        router.post(LLM_API_URL).respond(status_code=500, text="server boom")
        events = []
        async for ev in run_chat_stream(
            user_messages=[ChatMessage(role="user", content="x")],
            config=_config(),
        ):
            events.append(ev)

        assert any(e["type"] == "error" for e in events), events
        last = events[-1]
        assert last["type"] == "error"
        assert "500" in last["message"]


@pytest.mark.asyncio
async def test_stream_emits_error_on_network_failure():
    with respx.mock(assert_all_called=False) as router:
        router.post(LLM_API_URL).mock(side_effect=httpx.ConnectError("no route"))
        events = []
        async for ev in run_chat_stream(
            user_messages=[ChatMessage(role="user", content="x")],
            config=_config(),
        ):
            events.append(ev)

        assert events[-1]["type"] == "error"
        assert "Fallo de red" in events[-1]["message"]


@pytest.mark.asyncio
async def test_stream_endpoint_emits_sse_via_api(api_client):
    """Test integrado del endpoint /api/chat/stream con LLM mockeado."""
    final_text = (
        "**[Consulta Interpretada]** ok\n\n"
        "**[Resultados]** sin datos\n"
    )
    response_json = {"choices": [{"message": {"role": "assistant", "content": final_text}}]}

    with respx.mock(assert_all_called=False) as router:
        router.post(LLM_API_URL).respond(status_code=200, json=response_json)

        async with api_client.stream(
            "POST", "/api/chat/stream",
            json={"messages": [{"role": "user", "content": "x"}]},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            body = b""
            async for chunk in resp.aiter_bytes():
                body += chunk

        text = body.decode("utf-8")
        # El endpoint debe emitir eventos final_block y done.
        assert "event: final_block" in text
        assert '"interpretacion"' in text
        assert "event: done" in text
