"""Router FastAPI del chat.

En Fase 1 el endpoint `POST /api/chat` delega en el orquestador, que ya
gestiona las tools server-side y devuelve la respuesta estructurada en
los cuatro bloques.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from chat.llm_client import LLMClientError
from chat.log import log_interaction, monotonic_ms
from chat.orchestrator import OrchestratorConfig, run_chat, run_chat_stream
from chat.schemas import ChatRequest, ChatResponse


router = APIRouter(prefix="/api/chat", tags=["chat"])


def _settings():
    # Import diferido: evita ciclo de importacion con main.py en arranque.
    from main import settings
    return settings


def _build_config(settings) -> OrchestratorConfig:
    return OrchestratorConfig(
        api_url=settings.llm_api_url,
        api_key=settings.llm_api_key or None,
        model=settings.llm_model,
        max_iterations=int(settings.llm_max_tool_iterations),
        timeout=float(settings.llm_request_timeout),
    )


def _last_user_message(messages) -> str:
    """Devuelve el ultimo content de mensaje de rol=user para los logs."""
    for m in reversed(messages):
        if getattr(m, "role", None) == "user":
            return getattr(m, "content", "") or ""
    return ""


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    settings = _settings()

    if not settings.llm_api_url or not settings.llm_model:
        raise HTTPException(
            status_code=503,
            detail="El chat LLM no esta configurado (falta LLM_API_URL o LLM_MODEL).",
        )

    if not request.messages:
        raise HTTPException(status_code=400, detail="messages no puede estar vacio")

    started_ms = monotonic_ms()
    try:
        reply = await run_chat(
            user_messages=request.messages,
            config=_build_config(settings),
        )
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    log_interaction(
        session_id=request.session_id,
        user_query=_last_user_message(request.messages),
        trace=[t.model_dump() for t in reply.trace],
        client_actions=[ca.model_dump() for ca in reply.client_actions],
        final_reply=reply.blocks.model_dump(),
        latency_ms=monotonic_ms() - started_ms,
        model=settings.llm_model,
        iterations=reply.iterations,
        truncated=reply.truncated,
        stream=False,
    )

    return ChatResponse(session_id=request.session_id, reply=reply)


def _sse_format(event_type: str, payload: dict) -> str:
    """Serializa un evento como mensaje SSE.

    Cada evento ocupa dos lineas: `event: <tipo>` y `data: <json>`, separadas
    por una linea en blanco.
    """
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {data}\n\n"


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Variante streaming de /api/chat. Devuelve eventos SSE en tiempo real."""
    settings = _settings()

    if not settings.llm_api_url or not settings.llm_model:
        raise HTTPException(
            status_code=503,
            detail="El chat LLM no esta configurado (falta LLM_API_URL o LLM_MODEL).",
        )

    if not request.messages:
        raise HTTPException(status_code=400, detail="messages no puede estar vacio")

    config = _build_config(settings)

    async def event_generator():
        # Acumulamos estado para emitir un log unico al final.
        trace_acc: list[dict] = []
        client_actions_acc: list[dict] = []
        blocks_acc: dict[str, str] = {}
        iterations = 0
        truncated = False
        started_ms = monotonic_ms()

        try:
            async for event in run_chat_stream(
                user_messages=request.messages,
                config=config,
            ):
                event_type = event.get("type")
                payload = {k: v for k, v in event.items() if k != "type"}
                # Acumular para log antes de emitir (no mutamos el evento).
                if event_type == "tool_call_done":
                    trace_acc.append({
                        "tool": payload.get("tool"),
                        "ok": payload.get("ok", False),
                        "result_summary": payload.get("result_summary", ""),
                        "error": payload.get("error"),
                    })
                elif event_type == "client_action":
                    client_actions_acc.append({
                        "id": payload.get("id"),
                        "action": payload.get("action"),
                        "arguments": payload.get("arguments", {}),
                    })
                elif event_type == "final_block":
                    blocks_acc[payload.get("key", "")] = payload.get("content", "")
                elif event_type == "done":
                    iterations = int(payload.get("iterations") or 0)
                    truncated = bool(payload.get("truncated", False))
                yield _sse_format(event_type or "message", payload)
        except LLMClientError as exc:
            yield _sse_format("error", {"message": str(exc)})
        except Exception as exc:  # noqa: BLE001 — error fatal final, lo encapsulamos
            yield _sse_format("error", {"message": f"Error inesperado: {exc}"})
        finally:
            log_interaction(
                session_id=request.session_id,
                user_query=_last_user_message(request.messages),
                trace=trace_acc,
                client_actions=client_actions_acc,
                final_reply=blocks_acc,
                latency_ms=monotonic_ms() - started_ms,
                model=settings.llm_model,
                iterations=iterations,
                truncated=truncated,
                stream=True,
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # desactiva buffering en proxies (nginx).
        },
    )
