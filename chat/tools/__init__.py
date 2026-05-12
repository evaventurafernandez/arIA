"""Registro central de tools del chat.

Una tool del servidor expone:
- `name`: nombre publico invocable por el LLM (ej. "queryAlerts").
- `description`: explicacion corta para el modelo.
- `parameters`: JSON Schema de los argumentos.
- `handler`: corrutina async que ejecuta la tool y devuelve un objeto
  serializable a JSON.

Las tools se auto-registran al importar `chat.tools.server` (modulo que
encadena los submodulos concretos). El orquestador consulta `TOOLS` y
`get_openai_tool_specs()` sin conocer cada tool en particular.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


ToolHandler = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class ServerTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler


TOOLS: dict[str, ServerTool] = {}


def server_tool(*, name: str, description: str, parameters: dict[str, Any]):
    """Decorador que registra la corrutina como tool server-side."""

    def decorator(fn: ToolHandler) -> ToolHandler:
        if name in TOOLS:
            raise ValueError(f"Tool ya registrada: {name}")
        TOOLS[name] = ServerTool(
            name=name,
            description=description,
            parameters=parameters,
            handler=fn,
        )
        return fn

    return decorator


def get_openai_tool_specs() -> list[dict[str, Any]]:
    """Devuelve el catalogo en formato OpenAI/tools=[...] para incluir en /v1/chat/completions."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in TOOLS.values()
    ]


def list_tool_names() -> list[str]:
    return list(TOOLS.keys())


# Disparo del registro: importar el submodulo encadena las tools concretas.
# Se hace al final para evitar ciclos al cargar este __init__.
from chat.tools import server as _server  # noqa: E402,F401
