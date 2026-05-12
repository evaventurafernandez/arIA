"""E2E con LLM mockeado: consulta tipo 'centra en Galicia' devuelve client_actions."""

from __future__ import annotations

import json

import httpx
import pytest

from chat.tests.conftest import LLM_API_URL


@pytest.mark.asyncio
async def test_post_chat_returns_client_actions(api_client, respx_llm):
    """El backend debe devolver client_actions y NO ejecutar nada localmente."""

    tool_call_resp = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "ca-test",
                            "type": "function",
                            "function": {
                                "name": "flyTo",
                                "arguments": json.dumps({"bbox": [-9.4, 41.8, -6.7, 43.8]}),
                            },
                        }
                    ],
                }
            }
        ]
    }
    final_text = (
        "**[Consulta Interpretada]**\nUsuario quiere centrar en Galicia.\n\n"
        "**[Operaciones Geoespaciales]**\nflyTo con bbox de Galicia.\n\n"
        "**[Resultados]**\nMapa encuadrado.\n\n"
        "**[Interpretacion para Emergencias]**\nVista preparada.\n"
    )

    respx_llm.post(LLM_API_URL).mock(
        side_effect=[
            httpx.Response(200, json=tool_call_resp),
            httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": final_text}}]}),
        ]
    )

    response = await api_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "centra el mapa en Galicia"}]},
    )

    assert response.status_code == 200
    body = response.json()
    reply = body["reply"]

    assert len(reply["client_actions"]) == 1
    ca = reply["client_actions"][0]
    assert ca["action"] == "flyTo"
    assert ca["id"] == "ca-1"
    assert ca["arguments"] == {"bbox": [-9.4, 41.8, -6.7, 43.8]}

    # El trace incluye la accion encolada y los bloques estan poblados.
    assert any(t["tool"] == "flyTo" for t in reply["trace"])
    assert "Galicia" in reply["blocks"]["interpretacion"]
