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
    temperature: float | None = None,
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
    if temperature is not None:
        payload["temperature"] = float(temperature)
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


async def chat_completion_stream(
    *,
    messages: list[dict[str, Any]],
    api_url: str,
    api_key: str | None,
    model: str,
    tools: list[dict[str, Any]] | None = None,
    timeout: float = 120.0,
):
    """Iterador asincrono sobre los chunks JSON del stream del LLM.

    El servidor (vLLM, Ollama, OpenAI) responde con SSE: una linea
    `data: {...}` por chunk y un terminador `data: [DONE]`. Esta funcion
    parsea los chunks y los devuelve uno a uno. Las pegamientos de
    tool_calls parciales son responsabilidad del consumidor (orquestador).
    """
    import json as _json

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", api_url, json=payload, headers=headers
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread())[:500].decode("utf-8", errors="replace")
                    raise LLMClientError(
                        f"El LLM respondió {response.status_code}: {body}"
                    )
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].lstrip()
                    if data == "[DONE]":
                        break
                    try:
                        yield _json.loads(data)
                    except ValueError:
                        # Chunk no JSON (keep-alive de algunos servidores) -> ignorar.
                        continue
    except httpx.HTTPError as exc:
        raise LLMClientError(f"Fallo de red durante el stream del LLM: {exc}") from exc


def accumulate_streamed_tool_calls(
    chunks_deltas: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reconstruye los tool_calls completos desde los deltas parciales del stream.

    Cada delta puede contener `tool_calls=[{index, id?, function:{name?, arguments?}}]`.
    El campo `arguments` llega trozado caracter a caracter; hay que concatenar
    por `index` en el orden de llegada.
    """
    acc: dict[int, dict[str, Any]] = {}
    for delta in chunks_deltas:
        for call in delta.get("tool_calls") or []:
            idx = call.get("index", 0)
            slot = acc.setdefault(idx, {"id": "", "name": "", "arguments_raw": ""})
            if call.get("id"):
                slot["id"] = call["id"]
            fn = call.get("function") or {}
            if fn.get("name"):
                slot["name"] = fn["name"]
            if fn.get("arguments"):
                slot["arguments_raw"] += fn["arguments"]
    return [acc[k] for k in sorted(acc.keys())]
