"""Tests del rate limit configurable. Se aplica por IP (todas las peticiones
del test cliente llegan desde 127.0.0.1, asi que es facil disparar el 429)."""

from __future__ import annotations

import pytest

from chat.tests.conftest import LLM_API_URL


@pytest.fixture
def tight_rate_limit(monkeypatch):
    """Pone un limite muy bajo (2/minute) para que el test sea rapido y deterministico."""
    from main import settings
    monkeypatch.setattr(settings, "chat_rate_limit", "2/minute", raising=False)
    # slowapi cachea el storage entre tests; resetearlo para no contaminar.
    from chat.router import limiter
    limiter.reset()
    yield
    limiter.reset()


@pytest.mark.asyncio
async def test_rate_limit_triggers_429_after_threshold(api_client, respx_llm, tight_rate_limit):
    """Tres peticiones en la misma ventana: las dos primeras 200, la tercera 429."""
    respx_llm.post(LLM_API_URL).respond(
        status_code=200,
        json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
    )

    statuses = []
    for _ in range(3):
        r = await api_client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "hola"}]},
        )
        statuses.append(r.status_code)

    assert statuses[0] == 200
    assert statuses[1] == 200
    assert statuses[2] == 429, f"esperaba 429 en la tercera; statuses={statuses}"


@pytest.mark.asyncio
async def test_rate_limit_resets_between_tests(api_client, respx_llm, tight_rate_limit):
    """Verifica que la fixture resetea el contador entre tests (sin esto, los
    tests son inter-dependientes)."""
    respx_llm.post(LLM_API_URL).respond(
        status_code=200,
        json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
    )
    r = await api_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "x"}]},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_also_applies_to_stream(api_client, respx_llm, tight_rate_limit):
    respx_llm.post(LLM_API_URL).respond(
        status_code=200,
        json={"choices": [{"message": {"role": "assistant", "content": "**[X]** ok"}}]},
    )

    statuses = []
    for _ in range(3):
        async with api_client.stream(
            "POST", "/api/chat/stream",
            json={"messages": [{"role": "user", "content": "hola"}]},
        ) as resp:
            statuses.append(resp.status_code)
            # drenar el body para liberar la conexion.
            async for _chunk in resp.aiter_bytes():
                pass

    assert statuses[2] == 429
