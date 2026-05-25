"""Router FastAPI del chat.

Endpoints expuestos bajo /api/chat:
- POST /         — chat sincrono (no streaming).
- POST /stream   — variante SSE (eventos progresivos).
- GET  /health   — ping al LLM remoto, devuelve estado y latencia.

Endurecimiento (Fase 6): rate limit por IP via slowapi (configurable
`CHAT_RATE_LIMIT`, por defecto 30/minuto) + sanitizacion del contenido
del usuario aplicada por el orquestador antes de pasar al LLM.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from chat.llm_client import LLMClientError, chat_completion
from chat.log import log_interaction, monotonic_ms
from chat.orchestrator import OrchestratorConfig, run_chat, run_chat_stream
from chat.schemas import ChatRequest, ChatResponse


router = APIRouter(prefix="/api/chat", tags=["chat"])


def _settings():
    # Import diferido: evita ciclo de importacion con main.py en arranque.
    from main import settings
    return settings


def _current_rate_limit() -> str:
    """Lee el limite cada vez para permitir overrides en tests via monkeypatch."""
    settings = _settings()
    return getattr(settings, "chat_rate_limit", "30/minute") or "30/minute"


# Limiter por IP. La key_func consulta la IP cliente (X-Forwarded-For si
# hay proxy reverso, IP directa si no). En tests respx, todas las peticiones
# llegan con la misma IP (testclient/127.0.0.1).
limiter = Limiter(key_func=get_remote_address, default_limits=[])


def _build_config(settings) -> OrchestratorConfig:
    return OrchestratorConfig(
        api_url=settings.llm_api_url,
        api_key=settings.llm_api_key or None,
        model=settings.llm_model,
        max_iterations=int(settings.llm_max_tool_iterations),
        timeout=float(settings.llm_request_timeout),
        max_user_message_length=int(getattr(settings, "chat_max_user_message_length", 4000)),
        temperature=getattr(settings, "llm_temperature", None),
    )


def _last_user_message(messages) -> str:
    """Devuelve el ultimo content de mensaje de rol=user para los logs."""
    for m in reversed(messages):
        if getattr(m, "role", None) == "user":
            return getattr(m, "content", "") or ""
    return ""


def _validate_config(settings) -> None:
    """503 si falta LLM_API_URL o LLM_MODEL."""
    if not settings.llm_api_url or not settings.llm_model:
        raise HTTPException(
            status_code=503,
            detail="El chat LLM no esta configurado (falta LLM_API_URL o LLM_MODEL).",
        )


@router.post("", response_model=ChatResponse)
@limiter.limit(_current_rate_limit)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    settings = _settings()
    _validate_config(settings)

    if not body.messages:
        raise HTTPException(status_code=400, detail="messages no puede estar vacio")

    started_ms = monotonic_ms()
    try:
        reply = await run_chat(
            user_messages=body.messages,
            config=_build_config(settings),
        )
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    log_interaction(
        session_id=body.session_id,
        user_query=_last_user_message(body.messages),
        trace=[t.model_dump() for t in reply.trace],
        client_actions=[ca.model_dump() for ca in reply.client_actions],
        final_reply=reply.blocks.model_dump(),
        latency_ms=monotonic_ms() - started_ms,
        model=settings.llm_model,
        iterations=reply.iterations,
        truncated=reply.truncated,
        stream=False,
    )

    return ChatResponse(session_id=body.session_id, reply=reply)


def _sse_format(event_type: str, payload: dict) -> str:
    """Serializa un evento como mensaje SSE.

    Cada evento ocupa dos lineas: `event: <tipo>` y `data: <json>`, separadas
    por una linea en blanco.
    """
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {data}\n\n"


@router.post("/stream")
@limiter.limit(_current_rate_limit)
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    """Variante streaming de /api/chat. Devuelve eventos SSE en tiempo real."""
    settings = _settings()
    _validate_config(settings)

    if not body.messages:
        raise HTTPException(status_code=400, detail="messages no puede estar vacio")

    config = _build_config(settings)

    async def event_generator():
        trace_acc: list[dict] = []
        client_actions_acc: list[dict] = []
        blocks_acc: dict[str, str] = {}
        iterations = 0
        truncated = False
        started_ms = monotonic_ms()

        try:
            async for event in run_chat_stream(
                user_messages=body.messages,
                config=config,
            ):
                event_type = event.get("type")
                payload = {k: v for k, v in event.items() if k != "type"}
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
        except Exception as exc:  # noqa: BLE001
            yield _sse_format("error", {"message": f"Error inesperado: {exc}"})
        finally:
            log_interaction(
                session_id=body.session_id,
                user_query=_last_user_message(body.messages),
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
            "X-Accel-Buffering": "no",
        },
    )


def attach_chat_to(app: FastAPI) -> None:
    """Conecta el router, el limiter y el handler de RateLimitExceeded a la app.

    Llamar UNA sola vez desde main.py tras crear `app = FastAPI(...)`.
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(router)


@router.get("/health")
async def chat_health() -> dict:
    """Comprueba conectividad con el LLM remoto y reporta latencia.

    No es un endpoint de Kubernetes-style health (no se usa para liveness),
    sino una sonda manual para diagnosticar caidas del backend LLM. Si el
    chat no esta configurado devuelve ok=false con la razon, sin error 5xx.
    """
    settings = _settings()
    if not settings.llm_api_url or not settings.llm_model:
        return {
            "ok": False,
            "model": settings.llm_model or None,
            "configured": False,
            "error": "LLM_API_URL o LLM_MODEL no configurados",
        }
    started = monotonic_ms()
    try:
        await chat_completion(
            messages=[{"role": "user", "content": "ping"}],
            api_url=settings.llm_api_url,
            api_key=settings.llm_api_key or None,
            model=settings.llm_model,
            timeout=10.0,
        )
    except LLMClientError as exc:
        return {
            "ok": False,
            "model": settings.llm_model,
            "configured": True,
            "latency_ms": monotonic_ms() - started,
            "error": str(exc),
        }
    return {
        "ok": True,
        "model": settings.llm_model,
        "configured": True,
        "latency_ms": monotonic_ms() - started,
    }
