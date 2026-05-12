"""Defensa de tools sensibles: ninguna descripcion ni schema debe mencionar
claves, paths del servidor o secretos. Es una assert sobre el catalogo
completo (server + cliente) que protege contra fugas accidentales al
exponer las tools al LLM."""

from __future__ import annotations

import json
import re

from chat.tools import CLIENT_TOOLS, TOOLS


# Patrones que NO deben aparecer en descripcion ni en JSON Schema de ninguna tool.
_FORBIDDEN_PATTERNS = [
    re.compile(r"\bAEMET_API_KEY\b"),
    re.compile(r"\bFIRMS_MAP_KEY\b"),
    re.compile(r"\bCDSE_(?:USERNAME|PASSWORD|ACCESS_TOKEN|S3_(?:ACCESS|SECRET)_KEY)\b"),
    re.compile(r"\bLLM_API_KEY\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.]{16,}\b", re.IGNORECASE),
    # Paths de Windows del proyecto que no deberian filtrarse a las tools:
    re.compile(r"C:\\Users\\\w+\\", re.IGNORECASE),
    # Strings tipo /etc/passwd o /root/, comunes en leaks LFI:
    re.compile(r"/etc/passwd|/root/"),
]


def _collect_strings(value, out):
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            _collect_strings(v, out)
    elif isinstance(value, list):
        for v in value:
            _collect_strings(v, out)


def test_no_forbidden_patterns_in_any_tool_description_or_schema():
    offenders: list[str] = []
    for name, tool in {**TOOLS, **CLIENT_TOOLS}.items():
        haystack: list[str] = [tool.description]
        _collect_strings(tool.parameters, haystack)
        joined = "\n".join(haystack)
        for pat in _FORBIDDEN_PATTERNS:
            m = pat.search(joined)
            if m:
                offenders.append(f"{name}: pattern={pat.pattern} match={m.group(0)!r}")
    assert not offenders, f"Tools que exponen patrones sensibles: {offenders}"


def test_no_tool_schema_includes_extra_top_level_metadata():
    """JSON Schema seguro: solo type / properties / required / additionalProperties / etc.
    Si una tool incluyera 'examples' con datos reales, podria filtrar cosas."""
    SAFE_TOP_LEVEL_KEYS = {
        "type", "properties", "required", "additionalProperties",
        "description", "title", "default", "enum",
    }
    for name, tool in {**TOOLS, **CLIENT_TOOLS}.items():
        extra = set(tool.parameters.keys()) - SAFE_TOP_LEVEL_KEYS
        assert not extra, f"Tool {name} expone claves inesperadas a nivel raiz: {extra}"


def test_every_tool_has_non_empty_description():
    for name, tool in {**TOOLS, **CLIENT_TOOLS}.items():
        assert tool.description and len(tool.description) > 20, (
            f"Tool {name} sin description suficiente (lo necesita el LLM)"
        )


def test_no_tool_handler_arguments_accept_arbitrary_keys():
    """Todas las tools deben tener additionalProperties: False para evitar que
    el LLM pase argumentos no declarados que la firma del handler ignore (eso
    podria enmascarar bugs o intentos de explotacion)."""
    missing: list[str] = []
    for name, tool in {**TOOLS, **CLIENT_TOOLS}.items():
        params = tool.parameters
        if params.get("type") != "object":
            continue
        if params.get("additionalProperties") is not False:
            missing.append(name)
    assert not missing, (
        f"Tools sin additionalProperties: False -> aceptarian args extra del LLM: {missing}"
    )
