"""Esquemas Pydantic del chat — Fase 1.

Se modela el contrato cliente↔backend (peticiones y respuestas) y los
artefactos intermedios del orquestador (trace de tools, bloques del LLM).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ChatRequest(BaseModel):
    session_id: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)


class AssistantBlocks(BaseModel):
    """Los cuatro bloques de respuesta (Seccion 1.6 del documento)."""

    interpretacion: str = ""
    operaciones: str = ""
    resultados: str = ""
    interpretacion_emergencia: str = ""


class TraceEntry(BaseModel):
    """Una entrada del trace de razonamiento: una invocacion a tool con resumen."""

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_summary: str = ""
    ok: bool = True
    error: str | None = None


class ChatReply(BaseModel):
    blocks: AssistantBlocks
    text: str = ""  # respuesta tal cual la emitio el LLM (util si los bloques no se detectaron)
    trace: list[TraceEntry] = Field(default_factory=list)
    iterations: int = 0
    truncated: bool = False  # True si se alcanzo LLM_MAX_TOOL_ITERATIONS


class ChatResponse(BaseModel):
    session_id: str | None = None
    reply: ChatReply
