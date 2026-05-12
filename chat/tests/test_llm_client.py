"""Tests unitarios de `chat.llm_client.chat_completion`."""

from __future__ import annotations

import httpx
import pytest
import respx

from chat.llm_client import LLMClientError, chat_completion, extract_assistant_text


URL = "https://llm.test.invalid/v1/chat/completions"
KEY = "test-token"
MODEL = "qwen3.6:35b-a3b"


@pytest.mark.asyncio
async def test_sends_bearer_and_model_and_returns_payload():
    expected_body = {
        "choices": [
            {"message": {"role": "assistant", "content": "hola"}}
        ]
    }

    with respx.mock() as router:
        route = router.post(URL).respond(status_code=200, json=expected_body)

        result = await chat_completion(
            messages=[{"role": "user", "content": "hola"}],
            api_url=URL,
            api_key=KEY,
            model=MODEL,
        )

        assert result == expected_body
        assert route.called
        sent = route.calls.last.request
        assert sent.headers["Authorization"] == f"Bearer {KEY}"
        assert sent.headers["Content-Type"] == "application/json"
        body = sent.read().decode()
        assert f'"model":"{MODEL}"' in body.replace(" ", "")
        assert "hola" in body


@pytest.mark.asyncio
async def test_no_auth_header_when_api_key_empty():
    """Servidores abiertos (vLLM local, Ollama sin token) no requieren Authorization."""
    with respx.mock() as router:
        route = router.post(URL).respond(
            status_code=200,
            json={"choices": [{"message": {"role": "assistant", "content": ""}}]},
        )

        await chat_completion(
            messages=[{"role": "user", "content": "x"}],
            api_url=URL,
            api_key="",
            model=MODEL,
        )

        sent = route.calls.last.request
        assert "Authorization" not in sent.headers


@pytest.mark.asyncio
async def test_no_auth_header_when_api_key_none():
    with respx.mock() as router:
        route = router.post(URL).respond(
            status_code=200,
            json={"choices": [{"message": {"role": "assistant", "content": ""}}]},
        )

        await chat_completion(
            messages=[{"role": "user", "content": "x"}],
            api_url=URL,
            api_key=None,
            model=MODEL,
        )

        assert "Authorization" not in route.calls.last.request.headers


@pytest.mark.asyncio
async def test_tools_param_is_forwarded_when_provided():
    """El contrato debe soportar tools desde Fase 0 (aunque no se use)."""
    with respx.mock() as router:
        route = router.post(URL).respond(
            status_code=200,
            json={"choices": [{"message": {"role": "assistant", "content": ""}}]},
        )

        await chat_completion(
            messages=[{"role": "user", "content": "x"}],
            api_url=URL,
            api_key=KEY,
            model=MODEL,
            tools=[{"type": "function", "function": {"name": "noop", "parameters": {}}}],
        )

        body = route.calls.last.request.read().decode()
        assert "tools" in body
        assert "noop" in body


@pytest.mark.asyncio
async def test_http_error_raises_llm_client_error():
    with respx.mock() as router:
        router.post(URL).respond(status_code=500, text="boom")

        with pytest.raises(LLMClientError, match="500"):
            await chat_completion(
                messages=[{"role": "user", "content": "x"}],
                api_url=URL,
                api_key=KEY,
                model=MODEL,
            )


@pytest.mark.asyncio
async def test_network_error_raises_llm_client_error():
    with respx.mock() as router:
        router.post(URL).mock(side_effect=httpx.ConnectError("no route"))

        with pytest.raises(LLMClientError, match="Fallo de red"):
            await chat_completion(
                messages=[{"role": "user", "content": "x"}],
                api_url=URL,
                api_key=KEY,
                model=MODEL,
            )


def test_extract_assistant_text_handles_empty_choices():
    assert extract_assistant_text({}) == ""
    assert extract_assistant_text({"choices": []}) == ""
    assert extract_assistant_text({"choices": [{"message": {}}]}) == ""


def test_extract_assistant_text_trims_content():
    payload = {"choices": [{"message": {"content": "  hola  "}}]}
    assert extract_assistant_text(payload) == "hola"
