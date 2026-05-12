"""Test end-to-end del Ejemplo 4.3 del documento usando LLM mockeado.

Simula la conversacion completa:
- Usuario: '?Donde coincidieron altas temperaturas y nucleos urbanos la semana pasada?'
- LLM (turno 1): invoca queryAlerts con phenomenon='temperatura' y status='cualquiera'.
- Backend ejecuta la tool sobre un alerts_cache controlado.
- LLM (turno 2): devuelve respuesta final con los 4 bloques.

Verifica el contrato externo del endpoint /api/chat: codigo 200, blocks,
trace con la tool invocada y resumen del resultado.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from chat.tests.conftest import LLM_API_URL


def _alert(aid: str, event: str, level: str, area: str) -> dict:
    now = datetime.now()
    return {
        "id": aid,
        "event": event,
        "level": level,
        "level_color": "#FFD700",
        "area_name": area,
        "description": "",
        "instruction": "",
        "onset": (now - timedelta(days=3)).isoformat(timespec="seconds"),
        "expires": (now + timedelta(days=1)).isoformat(timespec="seconds"),
        "polygon": None,
        "source": "aemet",
    }


@pytest.mark.asyncio
async def test_e2e_query_alerts_via_chat(api_client, respx_llm, monkeypatch):
    monkeypatch.setattr(
        "main.alerts_cache",
        [
            _alert("e1", "Temperaturas maximas", "Naranja", "Madrid"),
            _alert("e2", "Temperaturas maximas", "Rojo", "Sevilla"),
            _alert("e3", "Viento", "Amarillo", "Asturias"),
        ],
    )

    tool_call_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_e2e",
                            "type": "function",
                            "function": {
                                "name": "queryAlerts",
                                "arguments": json.dumps({"phenomenon": "temperatura", "status": "vigente"}),
                            },
                        }
                    ],
                }
            }
        ]
    }
    final_response_text = (
        "**[Consulta Interpretada]**\n"
        "El usuario quiere ver donde hay avisos de temperatura.\n\n"
        "**[Operaciones Geoespaciales]**\n"
        "Se invoco queryAlerts(phenomenon='temperatura', status='vigente').\n\n"
        "**[Resultados]**\n"
        "2 avisos vigentes: Madrid (Naranja) y Sevilla (Rojo).\n\n"
        "**[Interpretacion para Emergencias]**\n"
        "Conviene priorizar Sevilla por el nivel rojo.\n"
    )

    import httpx

    respx_llm.post(LLM_API_URL).mock(
        side_effect=[
            httpx.Response(200, json=tool_call_response),
            httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": final_response_text}}]}),
        ]
    )

    response = await api_client.post(
        "/api/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "que avisos de temperatura hay vigentes en Espana",
                }
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    reply = body["reply"]

    # Trace: una sola entrada con queryAlerts OK.
    assert len(reply["trace"]) == 1
    entry = reply["trace"][0]
    assert entry["tool"] == "queryAlerts"
    assert entry["ok"] is True
    assert entry["arguments"] == {"phenomenon": "temperatura", "status": "vigente"}
    assert "Sevilla" in entry["result_summary"] or "total_matched" in entry["result_summary"]

    # Bloques de la respuesta final.
    assert "temperatura" in reply["blocks"]["interpretacion"].lower()
    assert "queryAlerts" in reply["blocks"]["operaciones"]
    assert "Sevilla" in reply["blocks"]["resultados"]
    assert "rojo" in reply["blocks"]["interpretacion_emergencia"].lower()
