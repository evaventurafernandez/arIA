"""Esquemas Pydantic del chat.

Se mantienen aquí los modelos compartidos entre router, orquestador y tests.
En Fase 0 solo se necesitan los modelos básicos de petición/respuesta sin tools.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ChatRequest(BaseModel):
    session_id: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    session_id: str | None = None
    reply: str
