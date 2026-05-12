"""Logging de interacciones del chat — version ligera de la Fase 5.

Emite una linea JSON por interaccion a stdout, con timestamp ISO 8601 y
los campos minimos para RF-64 / RF-73 sin persistencia en base de datos.

La persistencia completa (tabla `core.chat_interactions`, endpoint
`/api/chat/history`, boton de exportacion) queda diferida; cuando se
active, esta misma estructura se inserta tal cual.

Defensa: las cadenas pasan por `_redact` antes de imprimirse para tapar
tokens y claves si el modelo los devolviera por error. Sin pretensiones
de DLP completo: solo cubre patrones obvios (sk-..., Bearer ...).
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any


_SECRET_PATTERNS = [
    # OpenAI-style: sk-... con sufijo largo. Captura tambien sk-proj-, sk-ant-, etc.
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),
    # Bearer token en cabecera. Acepta separador comun (espacio o dos puntos).
    re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.=]{16,}\b", re.IGNORECASE),
]


def _redact(value: Any) -> Any:
    """Recursivamente sustituye patrones de secretos por '[REDACTED]'.

    Solo modifica strings; dicts y listas se procesan campo a campo.
    Los tipos primitivos no-string (int, float, bool, None) pasan tal cual.
    """
    if isinstance(value, str):
        out = value
        for pat in _SECRET_PATTERNS:
            out = pat.sub("[REDACTED]", out)
        return out
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def now_iso() -> str:
    """Timestamp ISO 8601 UTC, segundos de precision, con sufijo Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_interaction(
    *,
    session_id: str | None,
    user_query: str,
    trace: list[dict[str, Any]] | None = None,
    client_actions: list[dict[str, Any]] | None = None,
    final_reply: dict[str, Any] | None = None,
    latency_ms: int,
    model: str,
    iterations: int = 0,
    truncated: bool = False,
    stream: bool = False,
) -> None:
    """Imprime un evento JSON con la trazabilidad de una interaccion.

    Estructura:
      {
        "ts": "2026-05-12T17:42:33Z",
        "kind": "chat_interaction",
        "stream": true,
        "session_id": "uuid-o-null",
        "user_query": "...",
        "intent": "...",                     # bloque interpretacion del reply final
        "trace": [{tool, arguments, ok, result_summary, error?}, ...],
        "client_actions": [{id, action, arguments}, ...],
        "final_reply": {interpretacion, operaciones, resultados, interpretacion_emergencia},
        "latency_ms": 1234,
        "iterations": 2,
        "truncated": false,
        "model": "google/gemma-4-26B-A4B-it"
      }
    """
    blocks = final_reply or {}
    entry = {
        "ts": now_iso(),
        "kind": "chat_interaction",
        "stream": stream,
        "session_id": session_id,
        "user_query": _redact(user_query),
        "intent": _redact(blocks.get("interpretacion", "")) if isinstance(blocks, dict) else "",
        "trace": _redact(trace or []),
        "client_actions": _redact(client_actions or []),
        "final_reply": _redact(blocks),
        "latency_ms": int(latency_ms),
        "iterations": int(iterations),
        "truncated": bool(truncated),
        "model": model,
    }
    # `print` con flush=True para que la linea llegue al log al instante;
    # en Windows con codepage cp1252 hace falta PYTHONIOENCODING=utf-8 al
    # arrancar uvicorn (recordatorio del bug pre-existente del lifespan).
    print(json.dumps(entry, ensure_ascii=False, default=str), flush=True)


def monotonic_ms() -> int:
    """Marca temporal monotona en milisegundos. Util para medir latencia."""
    return int(time.monotonic() * 1000)
