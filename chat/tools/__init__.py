"""Registro central de tools del chat (server-side y client-side).

Tools server-side: el orquestador ejecuta su `handler` y reinyecta el
resultado al LLM. Ejemplo: `queryAlerts` consulta el cache de avisos.

Tools client-side: el backend NO ejecuta nada. Solo declara el schema
para que el LLM las pueda invocar, y cada invocacion se acumula en la
respuesta como `client_actions[]` para que el frontend (Leaflet) las
materialice (mover el mapa, activar capas, aplicar filtros). Al LLM se
le devuelve `{"status":"queued","id":"ca-N"}` como observacion para que
pueda terminar el razonamiento.

Ambos catalogos se exponen al LLM en el mismo array `tools=[...]`.
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


@dataclass(frozen=True)
class ClientTool:
    name: str
    description: str
    parameters: dict[str, Any]


TOOLS: dict[str, ServerTool] = {}
CLIENT_TOOLS: dict[str, ClientTool] = {}


def server_tool(*, name: str, description: str, parameters: dict[str, Any]):
    """Decorador que registra la corrutina como tool server-side."""

    def decorator(fn: ToolHandler) -> ToolHandler:
        if name in TOOLS or name in CLIENT_TOOLS:
            raise ValueError(f"Tool ya registrada: {name}")
        TOOLS[name] = ServerTool(
            name=name,
            description=description,
            parameters=parameters,
            handler=fn,
        )
        return fn

    return decorator


def client_tool(*, name: str, description: str, parameters: dict[str, Any]) -> ClientTool:
    """Registra una tool cliente. Devuelve la metadata para uso opcional."""
    if name in CLIENT_TOOLS or name in TOOLS:
        raise ValueError(f"Tool ya registrada: {name}")
    tool = ClientTool(name=name, description=description, parameters=parameters)
    CLIENT_TOOLS[name] = tool
    return tool


def get_openai_tool_specs() -> list[dict[str, Any]]:
    """Catalogo (server + client) en formato OpenAI tools=[...]."""
    specs: list[dict[str, Any]] = []
    for t in TOOLS.values():
        specs.append({
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
        })
    for t in CLIENT_TOOLS.values():
        specs.append({
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
        })
    return specs


def list_tool_names() -> list[str]:
    return list(TOOLS.keys()) + list(CLIENT_TOOLS.keys())


def is_client_tool(name: str) -> bool:
    return name in CLIENT_TOOLS


def get_tool_parameters(name: str) -> dict[str, Any] | None:
    """JSON Schema de una tool por nombre (server o cliente). None si no existe."""
    if name in TOOLS:
        return TOOLS[name].parameters
    if name in CLIENT_TOOLS:
        return CLIENT_TOOLS[name].parameters
    return None


# Disparo del registro: importar los submodulos encadena las tools concretas.
# Se hace al final para evitar ciclos al cargar este __init__.
from chat.tools import server as _server  # noqa: E402,F401
from chat.tools import client as _client  # noqa: E402,F401
