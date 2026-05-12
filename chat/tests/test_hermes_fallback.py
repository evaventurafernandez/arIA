"""Tests del parser Hermes (<tool_call>...</tool_call>) y del parser de bloques."""

from __future__ import annotations

from chat.orchestrator import parse_blocks, parse_hermes_tool_calls


def test_hermes_extracts_single_tool_call():
    text = (
        "Voy a invocar la tool:\n"
        "<tool_call>{\"name\": \"queryAlerts\", \"arguments\": {\"phenomenon\": \"viento\"}}</tool_call>"
    )
    calls = parse_hermes_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "queryAlerts"
    assert calls[0]["arguments"] == {"phenomenon": "viento"}


def test_hermes_extracts_multiple_tool_calls():
    text = (
        "<tool_call>{\"name\": \"queryAlerts\", \"arguments\": {}}</tool_call> y "
        "<tool_call>{\"name\": \"queryFires\", \"arguments\": {}}</tool_call>"
    )
    calls = parse_hermes_tool_calls(text)
    assert [c["name"] for c in calls] == ["queryAlerts", "queryFires"]


def test_hermes_accepts_string_arguments():
    """Algunos modelos serializan 'arguments' como string JSON anidado."""
    text = '<tool_call>{"name": "queryAlerts", "arguments": "{\\"level\\": \\"Rojo\\"}"}</tool_call>'
    calls = parse_hermes_tool_calls(text)
    assert calls[0]["arguments"] == {"level": "Rojo"}


def test_hermes_ignores_malformed_json():
    text = "<tool_call>{not json}</tool_call>"
    assert parse_hermes_tool_calls(text) == []


def test_hermes_returns_empty_for_no_match():
    assert parse_hermes_tool_calls("solo texto sin tools") == []
    assert parse_hermes_tool_calls("") == []


def test_parse_blocks_recognizes_canonical_format():
    text = (
        "**[Consulta Interpretada]**\n"
        "El usuario pregunta por avisos de viento.\n\n"
        "**[Operaciones Geoespaciales]**\n"
        "Se invoco queryAlerts(phenomenon='viento').\n\n"
        "**[Resultados]**\n"
        "3 avisos activos.\n\n"
        "**[Interpretacion para Emergencias]**\n"
        "Conviene priorizar zonas afectadas.\n"
    )
    blocks = parse_blocks(text)
    assert "avisos de viento" in blocks.interpretacion
    assert "queryAlerts" in blocks.operaciones
    assert "3 avisos" in blocks.resultados
    assert "priorizar" in blocks.interpretacion_emergencia


def test_parse_blocks_handles_accented_header():
    """El modelo puede escribir 'Interpretación' con tilde."""
    text = (
        "[Consulta Interpretada]\n"
        "abc\n\n"
        "[Interpretación para Emergencias]\n"
        "def\n"
    )
    blocks = parse_blocks(text)
    assert blocks.interpretacion == "abc"
    assert blocks.interpretacion_emergencia == "def"


def test_parse_blocks_falls_back_to_interpretacion_when_no_headers():
    text = "Texto plano sin marcadores."
    blocks = parse_blocks(text)
    assert blocks.interpretacion == text
    assert blocks.operaciones == ""
    assert blocks.resultados == ""
    assert blocks.interpretacion_emergencia == ""


def test_parse_blocks_strips_gemma_channel_markers():
    """Gemma a veces prefija `<|channel>thought<channel|>` antes del primer bloque."""
    text = (
        "<|channel>thought\n<channel|>**[Consulta Interpretada]**\n"
        "abc\n\n"
        "**[Operaciones Geoespaciales]**\ndef\n\n"
        "**[Resultados]**\nghi\n\n"
        "**[Interpretacion para Emergencias]**\njkl\n"
    )
    blocks = parse_blocks(text)
    assert blocks.interpretacion == "abc"
    assert blocks.operaciones == "def"
    assert blocks.resultados == "ghi"
    assert blocks.interpretacion_emergencia == "jkl"


def test_parse_blocks_strips_thinking_blocks():
    text = (
        "<thinking>razonamiento interno</thinking>\n"
        "**[Consulta Interpretada]** abc\n\n"
        "**[Operaciones Geoespaciales]** def\n"
    )
    blocks = parse_blocks(text)
    assert "razonamiento" not in blocks.interpretacion
    assert blocks.interpretacion == "abc"
    assert blocks.operaciones == "def"


def test_parse_blocks_header_inline_after_decorator():
    """El modelo puede pegar la cabecera y el contenido en la misma linea."""
    text = (
        "**[Consulta Interpretada]** abc\n"
        "**[Operaciones Geoespaciales]** def\n"
        "**[Resultados]** ghi\n"
        "**[Interpretación para Emergencias]** jkl\n"
    )
    blocks = parse_blocks(text)
    assert blocks.interpretacion == "abc"
    assert blocks.operaciones == "def"
    assert blocks.resultados == "ghi"
    assert blocks.interpretacion_emergencia == "jkl"
