"""Tests de integracion del log al pasar por los endpoints /api/chat y /api/chat/stream."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from chat.tests.conftest import LLM_API_URL


def _last_log_line(captured_out: str) -> dict:
    """Devuelve la ultima linea JSON parseada del stdout capturado."""
    lines = [ln for ln in captured_out.splitlines() if ln.strip()]
    # Buscar la ultima linea que sea JSON valido con kind=chat_interaction.
    for ln in reversed(lines):
        try:
            entry = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict) and entry.get("kind") == "chat_interaction":
            return entry
    raise AssertionError(f"No se encontro log de chat_interaction en stdout: {lines!r}")


@pytest.mark.asyncio
async def test_post_chat_logs_one_interaction(api_client, respx_llm, capsys):
    final_text = (
        "**[Consulta Interpretada]** El usuario pregunta por algo.\n\n"
        "**[Resultados]** Sin avisos.\n"
    )
    respx_llm.post(LLM_API_URL).respond(
        status_code=200,
        json={"choices": [{"message": {"role": "assistant", "content": final_text}}]},
    )

    response = await api_client.post(
        "/api/chat",
        json={"session_id": "sess-1", "messages": [{"role": "user", "content": "que pasa"}]},
    )
    assert response.status_code == 200

    entry = _last_log_line(capsys.readouterr().out)
    assert entry["session_id"] == "sess-1"
    assert entry["stream"] is False
    assert entry["user_query"] == "que pasa"
    assert entry["model"]  # debe haber un modelo configurado por el fixture
    assert entry["latency_ms"] >= 0
    assert entry["final_reply"]["interpretacion"].startswith("El usuario pregunta")
    assert entry["intent"] == entry["final_reply"]["interpretacion"]


@pytest.mark.asyncio
async def test_post_chat_stream_logs_one_interaction(api_client, capsys):
    final_text = (
        "**[Consulta Interpretada]** abc\n\n"
        "**[Resultados]** def\n"
    )
    with respx.mock(assert_all_called=False) as router:
        router.post(LLM_API_URL).respond(
            status_code=200,
            json={"choices": [{"message": {"role": "assistant", "content": final_text}}]},
        )

        async with api_client.stream(
            "POST", "/api/chat/stream",
            json={"session_id": "sess-2", "messages": [{"role": "user", "content": "hola"}]},
        ) as resp:
            body = b""
            async for chunk in resp.aiter_bytes():
                body += chunk

    entry = _last_log_line(capsys.readouterr().out)
    assert entry["session_id"] == "sess-2"
    assert entry["stream"] is True
    assert entry["user_query"] == "hola"
    assert entry["final_reply"]["interpretacion"] == "abc"
    assert entry["iterations"] >= 1


@pytest.mark.asyncio
async def test_post_chat_logs_trace_with_tool_call(api_client, respx_llm, capsys, monkeypatch):
    """El log debe contener la entrada del trace cuando hubo tool calls."""
    monkeypatch.setattr("main.alerts_cache", [])

    tool_call_resp = {
        "choices": [{
            "message": {
                "role": "assistant", "content": None,
                "tool_calls": [{
                    "id": "c1", "type": "function",
                    "function": {"name": "queryAlerts", "arguments": json.dumps({"phenomenon": "viento"})},
                }],
            }
        }]
    }
    final_resp = {"choices": [{"message": {"role": "assistant", "content": "**[Consulta Interpretada]** ok\n"}}]}

    respx_llm.post(LLM_API_URL).mock(
        side_effect=[httpx.Response(200, json=tool_call_resp), httpx.Response(200, json=final_resp)]
    )

    response = await api_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "que avisos hay"}]},
    )
    assert response.status_code == 200

    entry = _last_log_line(capsys.readouterr().out)
    assert len(entry["trace"]) >= 1
    assert entry["trace"][0]["tool"] == "queryAlerts"
    assert entry["iterations"] == 2


@pytest.mark.asyncio
async def test_post_chat_redacts_secrets_in_user_query(api_client, respx_llm, capsys):
    """Si el usuario pega una clave por error, no debe quedar en el log."""
    respx_llm.post(LLM_API_URL).respond(
        status_code=200,
        json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
    )
    leaky = "mi token es sk-supersecretkey1234567890abcd"
    response = await api_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": leaky}]},
    )
    assert response.status_code == 200

    entry = _last_log_line(capsys.readouterr().out)
    assert "sk-supersecretkey1234567890abcd" not in entry["user_query"]
    assert "[REDACTED]" in entry["user_query"]
