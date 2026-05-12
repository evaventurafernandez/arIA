"""Orquestador del chat: bucle think -> tool_call -> observe -> respond.

Recibe los mensajes del usuario, anade el system prompt, llama al LLM
con el catalogo de tools y razona en bucle hasta producir una respuesta
final con la estructura de cuatro bloques. Tope de iteraciones
configurable via `LLM_MAX_TOOL_ITERATIONS`.

Robustez:
- Si el LLM devuelve un `tool_call` con JSON de argumentos malformado o
  con args invalidos para el schema, se reinyecta como `tool_error` y se
  da una iteracion adicional para que el modelo se corrija.
- Si el LLM invoca una tool inexistente, se reinyecta la lista de tools
  disponibles.
- Si el LLM emite un tool_call empotrado en texto plano (formato Hermes
  `<tool_call>...</tool_call>`), se detecta y se procesa como
  estructurado.
"""

from __future__ import annotations

import json
import re
from typing import Any

import jsonschema

from chat.llm_client import (
    LLMClientError,
    accumulate_streamed_tool_calls,
    chat_completion,
    chat_completion_stream,
)
from chat.prompt import build_system_prompt
from chat.sanitize import sanitize_user_content
from chat.schemas import (
    AssistantBlocks,
    ChatMessage,
    ChatReply,
    ClientAction,
    TraceEntry,
)
from chat.tools import (
    CLIENT_TOOLS,
    TOOLS,
    get_openai_tool_specs,
    get_tool_parameters,
    is_client_tool,
    list_tool_names,
)


HERMES_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL
)


class OrchestratorConfig:
    """Wrapper minimo para inyectar settings sin acoplar a `main.py` en tests."""

    def __init__(
        self,
        *,
        api_url: str,
        api_key: str | None,
        model: str,
        max_iterations: int,
        timeout: float,
        max_user_message_length: int = 4000,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.max_iterations = max_iterations
        self.timeout = timeout
        self.max_user_message_length = max_user_message_length


def _build_history(
    user_messages: list[ChatMessage],
    *,
    max_user_message_length: int,
) -> list[dict[str, Any]]:
    """System prompt + mensajes sanitizados (solo los de rol user)."""
    history: list[dict[str, Any]] = [{"role": "system", "content": build_system_prompt()}]
    for m in user_messages:
        if m.role == "user":
            content = sanitize_user_content(m.content, max_length=max_user_message_length)
        else:
            content = m.content
        history.append({"role": m.role, "content": content})
    return history


# ---------------------------- Parser de bloques ----------------------------

_BLOCK_HEADERS = [
    ("interpretacion", "Consulta Interpretada"),
    ("operaciones", "Operaciones Geoespaciales"),
    ("resultados", "Resultados"),
    ("interpretacion_emergencia", "Interpretacion para Emergencias"),
    # Variante con tilde frecuente.
    ("interpretacion_emergencia", "Interpretación para Emergencias"),
]


def _strip_channel_markers(text: str) -> str:
    """Limpia marcadores tipo Gemma `<|channel|>thought`, `<thinking>...</thinking>`."""
    if not text:
        return text
    # Bloques de pensamiento estilo OpenAI/Anthropic o variantes.
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Marcadores Gemma estilo `<|channel|>thought<|channel|>` o `<channel>...</channel>`.
    text = re.sub(r"<\|[^>]*\|>", "", text)
    text = re.sub(r"</?channel[^>]*>", "", text, flags=re.IGNORECASE)
    return text


def parse_blocks(text: str) -> AssistantBlocks:
    """Extrae los cuatro bloques. Si no se detectan, vuelca todo en `interpretacion`.

    Estrategia: limpia marcadores de razonamiento, luego busca cada cabecera
    canonica como substring (independientemente de su posicion en linea o
    decoradores `**`/`[]`). Para cada cabecera encontrada, el contenido del
    bloque va desde el final de la cabecera hasta el inicio de la siguiente.
    """
    blocks = AssistantBlocks()
    if not text:
        return blocks

    cleaned = _strip_channel_markers(text)
    found: list[tuple[int, int, str]] = []  # (start_of_header, end_of_header, key)

    for key, header in _BLOCK_HEADERS:
        # Acentos: el modelo puede usar tilde o no. Probamos ambas.
        for variant in {header, header.replace("Interpretacion", "Interpretación")}:
            pattern = re.escape(variant)
            for m in re.finditer(pattern, cleaned, re.IGNORECASE):
                found.append((m.start(), m.end(), key))

    if not found:
        blocks.interpretacion = cleaned.strip()
        return blocks

    found.sort()
    # Si la misma key aparece varias veces nos quedamos con la primera ocurrencia.
    seen_keys: set[str] = set()
    deduped: list[tuple[int, int, str]] = []
    for entry in found:
        if entry[2] in seen_keys:
            continue
        seen_keys.add(entry[2])
        deduped.append(entry)
    deduped.sort()

    for i, (_hstart, hend, key) in enumerate(deduped):
        end = deduped[i + 1][0] if i + 1 < len(deduped) else len(cleaned)
        content = cleaned[hend:end]
        # Limpia decoradores residuales `]`, `**`, `[`, espacios y saltos al
        # principio (sobra el `]**` que cierra la cabecera actual) y al final
        # (sobra el `**[` o `[` que abre la siguiente cabecera).
        content = re.sub(r"^[\]\*\s]+", "", content)
        content = re.sub(r"[\*\s\[\]]+$", "", content)
        setattr(blocks, key, content.strip())

    return blocks


# ------------------------- Parser Hermes fallback --------------------------


def parse_hermes_tool_calls(text: str) -> list[dict[str, Any]]:
    """Busca patrones `<tool_call>{...}</tool_call>` y los devuelve normalizados."""
    if not text:
        return []
    out: list[dict[str, Any]] = []
    for m in HERMES_TOOL_CALL_RE.finditer(text):
        raw = m.group(1)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        name = parsed.get("name") or parsed.get("tool")
        args = parsed.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        if not isinstance(args, dict):
            args = {}
        if not name:
            continue
        out.append({"name": name, "arguments": args})
    return out


# --------------------- Validacion y ejecucion de tool ----------------------


def _validate_args(tool_name: str, args: Any) -> tuple[bool, str]:
    """Valida args contra el schema JSON de la tool (server o cliente)."""
    schema = get_tool_parameters(tool_name)
    if schema is None:
        return False, (
            f"tool_error: tool '{tool_name}' no existe. Tools disponibles: "
            + ", ".join(list_tool_names())
        )
    if not isinstance(args, dict):
        return False, f"tool_error: los argumentos de '{tool_name}' deben ser un objeto JSON."
    try:
        jsonschema.validate(instance=args, schema=schema)
    except jsonschema.ValidationError as exc:
        return False, f"tool_error: argumentos invalidos para '{tool_name}': {exc.message}"
    return True, ""


def _summarize_result(result: Any, *, max_len: int = 400) -> str:
    text = json.dumps(result, ensure_ascii=False, default=str)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


async def _execute_tool(tool_name: str, args: dict[str, Any]) -> tuple[bool, Any, str]:
    """Ejecuta el handler de la tool. Devuelve (ok, result_or_None, error_msg)."""
    tool = TOOLS[tool_name]
    try:
        result = await tool.handler(**args)
        return True, result, ""
    except Exception as exc:  # noqa: BLE001 — lo encapsulamos para reinyectarlo
        return False, None, f"tool_error al ejecutar '{tool_name}': {exc}"


def _safe_args_for_history(raw: str | None) -> str:
    """Garantiza que `arguments` en assistant.tool_calls sea JSON valido.

    Si el modelo emite args troceados durante el stream y la concatenacion
    resulta en JSON malformado, inyectar esa cadena tal cual en el historial
    hace que el siguiente request al LLM devuelva 400 (vLLM parsea
    arguments con json.loads). Reemplazamos por '{}' en ese caso; el
    tool_error correspondiente ya se enviara como rol=tool al modelo.
    """
    if not raw:
        return "{}"
    try:
        json.loads(raw)
        return raw
    except json.JSONDecodeError:
        return "{}"


# ----------------------------- Bucle principal -----------------------------


def _make_tool_call_id(idx: int) -> str:
    return f"call_{idx}"


def _coerce_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Normaliza tool_calls vengan estructurados o como `<tool_call>` en texto."""
    structured = message.get("tool_calls") or []
    if structured:
        return [
            {
                "id": call.get("id") or _make_tool_call_id(i),
                "name": (call.get("function") or {}).get("name", ""),
                "arguments_raw": (call.get("function") or {}).get("arguments", "{}"),
            }
            for i, call in enumerate(structured)
        ]
    content = message.get("content") or ""
    fallback = parse_hermes_tool_calls(content)
    return [
        {
            "id": _make_tool_call_id(i),
            "name": call["name"],
            "arguments_raw": json.dumps(call["arguments"]),
            "from_hermes": True,
        }
        for i, call in enumerate(fallback)
    ]


async def run_chat(
    *,
    user_messages: list[ChatMessage],
    config: OrchestratorConfig,
) -> ChatReply:
    """Ejecuta el bucle del chat y devuelve la respuesta estructurada."""
    history = _build_history(user_messages, max_user_message_length=config.max_user_message_length)

    tools_spec = get_openai_tool_specs()
    trace: list[TraceEntry] = []
    client_actions: list[ClientAction] = []
    iterations = 0
    truncated = False
    final_text = ""

    while iterations < config.max_iterations:
        iterations += 1

        try:
            payload = await chat_completion(
                messages=history,
                api_url=config.api_url,
                api_key=config.api_key,
                model=config.model,
                tools=tools_spec,
                timeout=config.timeout,
            )
        except LLMClientError:
            raise

        choices = payload.get("choices") or []
        if not choices:
            break
        message = choices[0].get("message") or {}

        tool_calls = _coerce_tool_calls(message)

        if not tool_calls:
            final_text = (message.get("content") or "").strip()
            break

        # Agregar el mensaje del asistente al historial.
        # Si vienen estructurados, los pasamos tal cual. Si vienen de Hermes,
        # los serializamos como tool_calls estructurados para que el LLM siga el contrato.
        # Convencion OpenAI: content=null cuando hay tool_calls (evita que
        # marcadores internos del modelo en `content` rompan la siguiente request).
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": None}
        if message.get("tool_calls"):
            # Sanitizar function.arguments por si el modelo entrego JSON malformado.
            assistant_msg["tool_calls"] = [
                {
                    **tc,
                    "function": {
                        **(tc.get("function") or {}),
                        "arguments": _safe_args_for_history((tc.get("function") or {}).get("arguments")),
                    },
                }
                for tc in message["tool_calls"]
            ]
        else:
            assistant_msg["tool_calls"] = [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {"name": call["name"], "arguments": _safe_args_for_history(call["arguments_raw"])},
                }
                for call in tool_calls
            ]
        history.append(assistant_msg)

        for call in tool_calls:
            tool_name = call["name"]
            try:
                args = json.loads(call["arguments_raw"]) if call["arguments_raw"] else {}
            except json.JSONDecodeError as exc:
                err = f"tool_error: JSON de argumentos invalido para '{tool_name}': {exc}"
                trace.append(TraceEntry(tool=tool_name, ok=False, error=err))
                history.append({"role": "tool", "tool_call_id": call["id"], "content": err})
                continue

            ok, err = _validate_args(tool_name, args)
            if not ok:
                trace.append(TraceEntry(tool=tool_name, arguments=args if isinstance(args, dict) else {}, ok=False, error=err))
                history.append({"role": "tool", "tool_call_id": call["id"], "content": err})
                continue

            if is_client_tool(tool_name):
                action_id = f"ca-{len(client_actions) + 1}"
                client_actions.append(
                    ClientAction(id=action_id, action=tool_name, arguments=args)
                )
                trace.append(
                    TraceEntry(
                        tool=tool_name,
                        arguments=args,
                        result_summary=f"client_action queued (id={action_id})",
                        ok=True,
                    )
                )
                observation = json.dumps({"status": "queued", "id": action_id}, ensure_ascii=False)
                history.append({"role": "tool", "tool_call_id": call["id"], "content": observation})
                continue

            exec_ok, result, exec_err = await _execute_tool(tool_name, args)
            if not exec_ok:
                trace.append(TraceEntry(tool=tool_name, arguments=args, ok=False, error=exec_err))
                history.append({"role": "tool", "tool_call_id": call["id"], "content": exec_err})
                continue

            trace.append(
                TraceEntry(
                    tool=tool_name,
                    arguments=args,
                    result_summary=_summarize_result(result),
                    ok=True,
                )
            )
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )
    else:
        truncated = True

    blocks = parse_blocks(final_text)
    return ChatReply(
        blocks=blocks,
        text=final_text,
        trace=trace,
        client_actions=client_actions,
        iterations=iterations,
        truncated=truncated,
    )


# ----------------------------- Bucle con streaming -----------------------------


def _make_event(event_type: str, **payload: Any) -> dict[str, Any]:
    return {"type": event_type, **payload}


async def run_chat_stream(
    *,
    user_messages: list[ChatMessage],
    config: OrchestratorConfig,
):
    """Variante por stream del bucle: emite eventos a medida que progresa.

    Diseno: la llamada al LLM se hace en modo NO-streaming dentro del
    orquestador, pero el endpoint /api/chat/stream emite eventos SSE a
    medida que el orquestador procesa cada iteracion. Esto se debe a un
    bug confirmado de vLLM/Gemma donde los `tool_call.arguments` con
    numeros negativos llegan corruptos en chunks token-a-token (ej.
    `["--9.03,...` con doble `-`). Priorizar fiabilidad sobre tokens
    incrementales: el usuario ve los tool_call_start/done y los bloques
    aparecer progresivamente; el texto final llega bloque a bloque, no
    caracter a caracter.

    Eventos emitidos (clave `type` del dict):
      - `tool_call_start` {id, tool, arguments}: tool detectada para invocar.
      - `tool_call_done` {id, tool, result_summary, ok, error?}: tool ejecutada
        (server-side) o queued (client-side).
      - `client_action` {id, action, arguments}: accion para el frontend.
      - `final_block` {key, content}: bloque del formato de respuesta final.
      - `done` {iterations, truncated}: cierre del stream.
      - `error` {message}: error fatal (la stream termina).
    """
    history = _build_history(user_messages, max_user_message_length=config.max_user_message_length)

    tools_spec = get_openai_tool_specs()
    client_actions_count = 0
    iterations = 0
    truncated = False

    while iterations < config.max_iterations:
        iterations += 1

        try:
            payload = await chat_completion(
                messages=history,
                api_url=config.api_url,
                api_key=config.api_key,
                model=config.model,
                tools=tools_spec,
                timeout=config.timeout,
            )
        except LLMClientError as exc:
            yield _make_event("error", message=str(exc))
            return

        choices = payload.get("choices") or []
        if not choices:
            yield _make_event("done", iterations=iterations, truncated=False)
            return
        message = choices[0].get("message") or {}
        tool_calls = _coerce_tool_calls(message)

        if not tool_calls:
            final_text = (message.get("content") or "").strip()
            blocks = parse_blocks(final_text)
            for key in ("interpretacion", "operaciones", "resultados", "interpretacion_emergencia"):
                value = getattr(blocks, key)
                if value:
                    yield _make_event("final_block", key=key, content=value)
            yield _make_event("done", iterations=iterations, truncated=False)
            return

        # Anadir el mensaje assistant con tool_calls al historial.
        # Convencion OpenAI estricta: cuando hay tool_calls, content=null.
        # Si dejamos accumulated_content (que puede llevar marcadores tipo
        # `<|channel>thought<channel|>` de Gemma), algunos servidores (vLLM)
        # devuelven 400 al reparsear la conversacion en la siguiente
        # iteracion. Sanitizamos tambien arguments por si llegaron troceados.
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": None}
        assistant_msg["tool_calls"] = [
            {
                "id": call["id"],
                "type": "function",
                "function": {"name": call["name"], "arguments": _safe_args_for_history(call["arguments_raw"])},
            }
            for call in tool_calls
        ]
        history.append(assistant_msg)

        for call in tool_calls:
            tool_name = call["name"]
            try:
                args = json.loads(call["arguments_raw"]) if call["arguments_raw"] else {}
            except json.JSONDecodeError as exc:
                err = f"tool_error: JSON de argumentos invalido para '{tool_name}': {exc}"
                yield _make_event("tool_call_done", id=call["id"], tool=tool_name, ok=False, error=err)
                history.append({"role": "tool", "tool_call_id": call["id"], "content": err})
                continue

            yield _make_event("tool_call_start", id=call["id"], tool=tool_name, arguments=args if isinstance(args, dict) else {})

            ok, err = _validate_args(tool_name, args)
            if not ok:
                yield _make_event("tool_call_done", id=call["id"], tool=tool_name, ok=False, error=err)
                history.append({"role": "tool", "tool_call_id": call["id"], "content": err})
                continue

            if is_client_tool(tool_name):
                client_actions_count += 1
                action_id = f"ca-{client_actions_count}"
                yield _make_event("client_action", id=action_id, action=tool_name, arguments=args)
                yield _make_event(
                    "tool_call_done",
                    id=call["id"], tool=tool_name, ok=True,
                    result_summary=f"client_action queued (id={action_id})",
                )
                observation = json.dumps({"status": "queued", "id": action_id}, ensure_ascii=False)
                history.append({"role": "tool", "tool_call_id": call["id"], "content": observation})
                continue

            exec_ok, result, exec_err = await _execute_tool(tool_name, args)
            if not exec_ok:
                yield _make_event("tool_call_done", id=call["id"], tool=tool_name, ok=False, error=exec_err)
                history.append({"role": "tool", "tool_call_id": call["id"], "content": exec_err})
                continue

            yield _make_event(
                "tool_call_done",
                id=call["id"], tool=tool_name, ok=True,
                result_summary=_summarize_result(result),
            )
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )

    truncated = True
    yield _make_event("done", iterations=iterations, truncated=truncated)
