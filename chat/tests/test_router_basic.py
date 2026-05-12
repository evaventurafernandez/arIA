"""Tests del endpoint POST /api/chat (contrato y errores). Fases 0-1."""

from __future__ import annotations

import json

import pytest

from chat.tests.conftest import LLM_API_URL


def _final_text_response(text: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


@pytest.mark.asyncio
async def test_post_chat_returns_structured_reply(api_client, respx_llm):
    respx_llm.post(LLM_API_URL).respond(status_code=200, json=_final_text_response("hola humano"))

    response = await api_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hola"}]},
    )

    assert response.status_code == 200
    body = response.json()
    reply = body["reply"]
    # En ausencia de bloques explicitos, el contenido cae en 'interpretacion'.
    assert reply["text"] == "hola humano"
    assert reply["blocks"]["interpretacion"] == "hola humano"
    assert reply["iterations"] >= 1
    assert reply["truncated"] is False


@pytest.mark.asyncio
async def test_post_chat_rejects_empty_messages(api_client):
    response = await api_client.post("/api/chat", json={"messages": []})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_post_chat_returns_503_when_url_missing(api_client, monkeypatch):
    from main import settings

    monkeypatch.setattr(settings, "llm_api_url", "", raising=False)

    response = await api_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hola"}]},
    )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_post_chat_returns_503_when_model_missing(api_client, monkeypatch):
    from main import settings

    monkeypatch.setattr(settings, "llm_model", "", raising=False)

    response = await api_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hola"}]},
    )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_post_chat_works_without_api_key(api_client, respx_llm, monkeypatch):
    """Servidores abiertos (vLLM interno, Ollama sin token) deben funcionar sin LLM_API_KEY."""
    from main import settings

    monkeypatch.setattr(settings, "llm_api_key", "", raising=False)
    route = respx_llm.post(LLM_API_URL).respond(status_code=200, json=_final_text_response("ok"))

    response = await api_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hola"}]},
    )

    assert response.status_code == 200
    sent = route.calls.last.request
    assert "Authorization" not in sent.headers


@pytest.mark.asyncio
async def test_post_chat_returns_502_when_llm_fails(api_client, respx_llm):
    respx_llm.post(LLM_API_URL).respond(status_code=500, text="boom")

    response = await api_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hola"}]},
    )

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_post_chat_preserves_session_id(api_client, respx_llm):
    respx_llm.post(LLM_API_URL).respond(status_code=200, json=_final_text_response("ok"))

    response = await api_client.post(
        "/api/chat",
        json={
            "session_id": "abc-123",
            "messages": [{"role": "user", "content": "hola"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == "abc-123"
