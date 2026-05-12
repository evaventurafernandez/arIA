"""Tests del endpoint GET /api/chat/health."""

from __future__ import annotations

import httpx
import pytest
import respx

from chat.tests.conftest import LLM_API_URL


@pytest.mark.asyncio
async def test_health_ok_when_llm_responds(api_client, respx_llm):
    respx_llm.post(LLM_API_URL).respond(
        status_code=200,
        json={"choices": [{"message": {"role": "assistant", "content": "pong"}}]},
    )
    r = await api_client.get("/api/chat/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["configured"] is True
    assert body["model"]
    assert body["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_health_reports_error_when_llm_fails(api_client, respx_llm):
    respx_llm.post(LLM_API_URL).respond(status_code=503, text="server down")
    r = await api_client.get("/api/chat/health")
    assert r.status_code == 200  # el endpoint no levanta 5xx; reporta el error en el body
    body = r.json()
    assert body["ok"] is False
    assert body["configured"] is True
    assert "503" in body["error"]


@pytest.mark.asyncio
async def test_health_reports_not_configured_when_url_missing(api_client, monkeypatch):
    from main import settings
    monkeypatch.setattr(settings, "llm_api_url", "", raising=False)

    r = await api_client.get("/api/chat/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["configured"] is False
    assert "LLM_API_URL" in body["error"] or "LLM_MODEL" in body["error"]


@pytest.mark.asyncio
async def test_health_handles_network_error(api_client, respx_llm):
    respx_llm.post(LLM_API_URL).mock(side_effect=httpx.ConnectError("no route"))
    r = await api_client.get("/api/chat/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "Fallo de red" in body["error"]
