"""Cliente HTTP del LLM remoto (endpoint OpenAI-compatible).

El servidor objetivo es un Ollama remoto que expone `/v1/chat/completions`
con autenticación Bearer Token. La interfaz devuelta es el dict bruto de la
respuesta JSON del proveedor — el orquestador se encarga de interpretarlo.

En Fase 0 esta función solo se usa sin `tools`. El soporte de `tools` se
ejercita ya por el contrato para evitar tener que cambiar firma en Fase 1.
"""

from __future__ import annotations

from typing import Any

import httpx


class LLMClientError(RuntimeError):
    """Error al comunicar con el LLM remoto."""


async def chat_completion(
    *,
    messages: list[dict[str, Any]],
    api_url: str,
    api_key: str | None,
    model: str,
    tools: list[dict[str, Any]] | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Llama al endpoint OpenAI-compatible y devuelve el JSON crudo.

    `api_key` puede ser None o cadena vacía para servidores abiertos (vLLM
    interno, Ollama sin token, etc.); en ese caso no se envía cabecera
    Authorization. Lanza `LLMClientError` si la respuesta no es 2xx o el
    cuerpo no es JSON.
    """
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        # Algunos backends (vLLM con Gemma) no asumen 'auto' por defecto y se
        # quedan en respuesta textual. Hay que declararlo explicitamente para
        # que el modelo emita tool_calls cuando proceda.
        payload["tool_choice"] = "auto"

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(api_url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise LLMClientError(f"Fallo de red llamando al LLM: {exc}") from exc

    if response.status_code >= 400:
        raise LLMClientError(
            f"El LLM respondió {response.status_code}: {response.text[:500]}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise LLMClientError("La respuesta del LLM no es JSON válido") from exc


def extract_assistant_text(payload: dict[str, Any]) -> str:
    """Devuelve el texto del primer choice. Útil mientras no hay tools."""
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return (message.get("content") or "").strip()
