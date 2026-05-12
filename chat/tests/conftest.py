"""Fixtures compartidos por la suite de tests del chat.

- `llm_config` aplica una configuración válida (URL, key, modelo) al singleton
  `settings` de `main.py` sin tocar `.env`. Cada test puede sobrescribirla.
- `respx_llm` registra el mock contra el endpoint OpenAI-compatible y deja
  que cada test prepare la respuesta concreta del LLM.
- `api_client` expone un `httpx.AsyncClient` apuntando a la app FastAPI
  montada en memoria, sin abrir red ni arrancar uvicorn.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Iterator

import httpx
import pytest
import respx


LLM_API_URL = "https://llm.test.invalid/v1/chat/completions"
LLM_API_KEY = "test-token"
LLM_MODEL = "qwen3.6:35b-a3b"


@pytest.fixture(autouse=True)
def llm_config(monkeypatch) -> Any:
    """Aplica una configuración válida del LLM al objeto `settings` de main.py.

    Es autouse para que ningún test arranque el router sin configuración y
    devuelva 503 por accidente. Los tests que quieran probar el caso
    "sin configurar" pueden hacer `monkeypatch.setattr(settings, 'llm_api_key', '')`.
    """
    from main import settings

    monkeypatch.setattr(settings, "llm_api_url", LLM_API_URL, raising=False)
    monkeypatch.setattr(settings, "llm_api_key", LLM_API_KEY, raising=False)
    monkeypatch.setattr(settings, "llm_model", LLM_MODEL, raising=False)
    monkeypatch.setattr(settings, "llm_request_timeout", 5.0, raising=False)
    return settings


@pytest.fixture
def respx_llm() -> Iterator[respx.Router]:
    """Activa respx y registra el endpoint del LLM. Cada test programa la respuesta."""
    with respx.mock(assert_all_called=False) as router:
        router.post(LLM_API_URL).respond(
            status_code=200,
            json={"choices": [{"message": {"role": "assistant", "content": ""}}]},
        )
        yield router


@pytest.fixture
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    """Cliente HTTP contra la app FastAPI montada en memoria (ASGI transport).

    Importamos `main.app` perezosamente para que `llm_config` ya haya parcheado
    `settings` antes del primer uso.
    """
    from main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
