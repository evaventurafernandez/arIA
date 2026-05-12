"""Tests unitarios del modulo `chat.log`: estructura, ISO 8601, redaccion."""

from __future__ import annotations

import json
import re

from chat.log import _redact, log_interaction, now_iso


# --- helpers ---


def _captured_line(capsys) -> dict:
    """Lee la unica linea impresa por log_interaction durante el test."""
    captured = capsys.readouterr().out
    lines = [ln for ln in captured.splitlines() if ln.strip()]
    assert len(lines) == 1, f"Esperaba 1 linea de log, obtuve {len(lines)}: {lines!r}"
    return json.loads(lines[0])


# --- timestamp ---


def test_now_iso_format_is_iso8601_utc():
    ts = now_iso()
    # Patron YYYY-MM-DDTHH:MM:SSZ.
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts), ts


# --- estructura basica ---


def test_log_interaction_writes_a_single_json_line(capsys):
    log_interaction(
        session_id="abc",
        user_query="hola",
        trace=[],
        client_actions=[],
        final_reply={"interpretacion": "ok"},
        latency_ms=123,
        model="model-x",
        iterations=1,
        truncated=False,
    )
    entry = _captured_line(capsys)
    assert entry["kind"] == "chat_interaction"
    assert entry["session_id"] == "abc"
    assert entry["user_query"] == "hola"
    assert entry["latency_ms"] == 123
    assert entry["model"] == "model-x"
    assert entry["iterations"] == 1
    assert entry["truncated"] is False
    assert entry["intent"] == "ok"  # se toma del bloque interpretacion
    assert "ts" in entry and entry["ts"].endswith("Z")


def test_log_interaction_includes_trace_and_client_actions(capsys):
    log_interaction(
        session_id=None,
        user_query="centra el mapa",
        trace=[
            {"tool": "searchPlace", "ok": True, "result_summary": "Galicia bbox"},
            {"tool": "flyTo", "ok": True, "result_summary": "client_action queued (id=ca-1)"},
        ],
        client_actions=[{"id": "ca-1", "action": "flyTo", "arguments": {"bbox": [-9.3, 41.8, -6.7, 43.8]}}],
        final_reply={"interpretacion": "Centra en Galicia"},
        latency_ms=2500,
        model="model-x",
        iterations=2,
        stream=True,
    )
    entry = _captured_line(capsys)
    assert entry["stream"] is True
    assert len(entry["trace"]) == 2
    assert entry["trace"][0]["tool"] == "searchPlace"
    assert entry["client_actions"][0]["action"] == "flyTo"


# --- redaccion ---


def test_redact_replaces_openai_style_keys():
    out = _redact("Mi key es sk-abc123def456ghi789jkl0 por favor")
    assert "sk-abc123" not in out
    assert "[REDACTED]" in out


def test_redact_replaces_bearer_tokens():
    out = _redact("Authorization: Bearer abc123def456ghi789xyz")
    assert "abc123def456ghi789xyz" not in out
    assert "[REDACTED]" in out


def test_redact_preserves_short_strings_that_look_safe():
    """No queremos falsos positivos: 'sk-1' es demasiado corto para considerarlo secreto."""
    out = _redact("sk-1 corto")
    assert out == "sk-1 corto"


def test_redact_walks_dicts_and_lists():
    nested = {
        "msg": "Bearer aaaaaaaaaaaaaaaa1234",
        "tools": [{"args": {"token": "sk-zzzzzzzzzzzzzzzzzzzz"}}],
    }
    out = _redact(nested)
    assert "[REDACTED]" in out["msg"]
    assert "[REDACTED]" in out["tools"][0]["args"]["token"]


def test_log_interaction_redacts_final_reply(capsys):
    log_interaction(
        session_id=None,
        user_query="cualquier consulta",
        final_reply={
            "interpretacion": "el token recibido es sk-secretkey1234567890zzz",
            "operaciones": "",
            "resultados": "",
            "interpretacion_emergencia": "",
        },
        latency_ms=10,
        model="m",
    )
    entry = _captured_line(capsys)
    assert "sk-secretkey1234567890zzz" not in entry["final_reply"]["interpretacion"]
    assert "sk-secretkey1234567890zzz" not in entry["intent"]
    assert "[REDACTED]" in entry["final_reply"]["interpretacion"]


# --- defaults ---


def test_log_interaction_defaults_for_optional_args(capsys):
    log_interaction(
        session_id=None,
        user_query="hola",
        latency_ms=5,
        model="m",
    )
    entry = _captured_line(capsys)
    assert entry["trace"] == []
    assert entry["client_actions"] == []
    assert entry["final_reply"] == {}
    assert entry["intent"] == ""
    assert entry["stream"] is False
