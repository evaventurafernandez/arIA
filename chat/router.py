"""Router FastAPI del chat.

En Fase 1 el endpoint `POST /api/chat` delega en el orquestador, que ya
gestiona las tools server-side y devuelve la respuesta estructurada en
los cuatro bloques.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from chat.llm_client import LLMClientError
from chat.orchestrator import OrchestratorConfig, run_chat
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

    try:
        reply = await run_chat(
            user_messages=request.messages,
            config=_build_config(settings),
        )
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ChatResponse(session_id=request.session_id, reply=reply)
