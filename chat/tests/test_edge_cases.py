"""Casos de borde del documento (Seccion 6) - tests con LLM mockeado.

Cubren los seis escenarios donde el comportamiento esperado del asistente
es rechazar o declarar limitacion en lugar de inventar datos.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from chat.orchestrator import OrchestratorConfig, run_chat
from chat.schemas import ChatMessage


URL = "https://llm.test.invalid/v1/chat/completions"


def _config():
    return OrchestratorConfig(api_url=URL, api_key=None, model="m", max_iterations=4, timeout=5.0)


def _text(text: str):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def _4block_rejection(area_no_disponible: str) -> str:
    return (
        f"**[Consulta Interpretada]**\nUsuario pregunta por {area_no_disponible}.\n\n"
        f"**[Operaciones Geoespaciales]**\nNinguna tool invocada: {area_no_disponible} no esta disponible en el visor.\n\n"
        f"**[Resultados]**\nNo procede.\n\n"
        f"**[Interpretacion para Emergencias]**\nSe declara la limitacion al usuario.\n"
    )


@pytest.mark.asyncio
async def test_layer_not_available_carreteras():
    """Seccion 6.1: 'que tramos de autovia cruzan zonas quemadas'."""
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).respond(status_code=200, json=_text(_4block_rejection("carreteras IGN")))
        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="que tramos de autovia cruzan zonas quemadas")],
            config=_config(),
        )
        assert reply.iterations == 1
        assert reply.trace == []
        assert "carreteras" in reply.blocks.operaciones.lower() or "carreteras" in reply.blocks.interpretacion.lower()


@pytest.mark.asyncio
async def test_variable_no_observada_temperatura():
    """Seccion 6.2: el usuario pide '> 35 grados' pero solo hay avisos CAP, no series.
    Se modela como un turno: el LLM redirige a queryAlerts(phenomenon='temperatura').
    """
    tool_call = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {"name": "queryAlerts", "arguments": json.dumps(
                                {"phenomenon": "temperatura", "status": "vigente"}
                            )},
                        }
                    ],
                }
            }
        ]
    }
    final = _text(_4block_rejection("mediciones de temperatura > 35"))

    import os
    os.environ.setdefault("PYTEST_CURRENT_TEST", "edge")

    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(side_effect=[httpx.Response(200, json=tool_call), httpx.Response(200, json=final)])
        # Sin alerts_cache, queryAlerts devolvera lista vacia.
        # Usamos monkeypatch del modulo main directamente.
        import main
        main.alerts_cache = []
        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="donde hubo mas de 35 grados ayer")],
            config=_config(),
        )
        # El LLM redirigio a queryAlerts en lugar de inventar mediciones.
        assert any(t.tool == "queryAlerts" for t in reply.trace)


@pytest.mark.asyncio
async def test_date_out_of_coverage():
    """Seccion 6.3: 'focos FIRMS en marzo 2024' - fuera de la cobertura del historico."""
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).respond(status_code=200, json=_text(_4block_rejection("marzo 2024 fuera de cobertura del historico FIRMS")))
        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="focos FIRMS en marzo de 2024")],
            config=_config(),
        )
        assert reply.trace == []
        text = (reply.blocks.operaciones + reply.blocks.interpretacion).lower()
        assert "2024" in text or "cobertura" in text


@pytest.mark.asyncio
async def test_predictive_query_rejected():
    """Seccion 6.5: 'que provincias tendran mas incendios en septiembre' - el LLM no predice."""
    rejection = (
        "**[Consulta Interpretada]**\nConsulta predictiva sobre incendios futuros.\n\n"
        "**[Operaciones Geoespaciales]**\nNinguna: el visor no realiza predicciones futuras.\n\n"
        "**[Resultados]**\nNo aplica.\n\n"
        "**[Interpretacion para Emergencias]**\nConsultar fuentes oficiales (AEMET, EFFIS).\n"
    )
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).respond(status_code=200, json=_text(rejection))
        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="que provincias tendran mas incendios en septiembre")],
            config=_config(),
        )
        assert reply.trace == []
        text = (reply.blocks.operaciones + reply.blocks.interpretacion_emergencia).lower()
        assert "predic" in text or "futur" in text or "no realiza" in text


@pytest.mark.asyncio
async def test_burnt_area_intersect_population_not_implemented():
    """Caso de borde extra: la tool burntAreaIntersectPopulation NO se implementa por
    falta de geometrias vectoriales. Si el LLM intenta invocarla, el orquestador
    devuelve catalogo en lugar de fallar (es una 'unknown tool')."""
    fake = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "burntAreaIntersectPopulation",
                                "arguments": json.dumps({"date_from": "2025-08-01", "date_to": "2025-08-31"}),
                            },
                        }
                    ],
                }
            }
        ]
    }
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(
            side_effect=[httpx.Response(200, json=fake), httpx.Response(200, json=_text("ok"))]
        )
        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="cruza areas quemadas con pueblos")],
            config=_config(),
        )
        assert len(reply.trace) == 1
        assert reply.trace[0].tool == "burntAreaIntersectPopulation"
        assert reply.trace[0].ok is False
        assert "no existe" in (reply.trace[0].error or "").lower()
