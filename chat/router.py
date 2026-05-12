"""Router FastAPI del chat. En Fase 0 solo expone POST /api/chat sin tools."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from chat.llm_client import LLMClientError, chat_completion, extract_assistant_text
from chat.schemas import ChatRequest, ChatResponse


router = APIRouter(prefix="/api/chat", tags=["chat"])


def _settings():
    # Import diferido: evita ciclo de importación con main.py en arranque.
    from main import settings
    return settings


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    settings = _settings()

    if not settings.llm_api_url or not settings.llm_model:
        raise HTTPException(
            status_code=503,
            detail="El chat LLM no está configurado (falta LLM_API_URL o LLM_MODEL).",
        )

    messages = [m.model_dump() for m in request.messages]
    if not messages:
        raise HTTPException(status_code=400, detail="messages no puede estar vacío")

    try:
        payload = await chat_completion(
            messages=messages,
            api_url=settings.llm_api_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.llm_request_timeout,
        )
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ChatResponse(session_id=request.session_id, reply=extract_assistant_text(payload))
