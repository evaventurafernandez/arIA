"""Tests del orquestador para tools CLIENTE: se acumulan en client_actions, no se ejecutan."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from chat.orchestrator import OrchestratorConfig, run_chat
from chat.schemas import ChatMessage
from chat.tools import TOOLS, ServerTool


URL = "https://llm.test.invalid/v1/chat/completions"


def _msg_assistant_text(text: str) -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def _msg_assistant_tool_call(name: str, arguments: dict[str, Any], call_id: str = "c1") -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(arguments)},
                        }
                    ],
                }
            }
        ]
    }


def _msg_assistant_two_tool_calls(
    name_a: str, args_a: dict, name_b: str, args_b: dict
) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {"name": name_a, "arguments": json.dumps(args_a)},
                        },
                        {
                            "id": "c2",
                            "type": "function",
                            "function": {"name": name_b, "arguments": json.dumps(args_b)},
                        },
                    ],
                }
            }
        ]
    }


def _config(max_iterations: int = 4) -> OrchestratorConfig:
    return OrchestratorConfig(
        api_url=URL,
        api_key=None,
        model="test-model",
        max_iterations=max_iterations,
        timeout=5.0,
    )


@pytest.mark.asyncio
async def test_client_tool_call_is_queued_not_executed():
    """LLM invoca flyTo -> orquestador la mete en client_actions y devuelve 'queued'."""
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json=_msg_assistant_tool_call("flyTo", {"bbox": [-10.0, 35.0, 5.0, 44.0]}),
                ),
                httpx.Response(200, json=_msg_assistant_text("ok")),
            ]
        )

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="centra en Espana")],
            config=_config(),
        )

        assert len(reply.client_actions) == 1
        ca = reply.client_actions[0]
        assert ca.action == "flyTo"
        assert ca.id == "ca-1"
        assert ca.arguments == {"bbox": [-10.0, 35.0, 5.0, 44.0]}

        # El trace tambien registra la accion encolada.
        assert len(reply.trace) == 1
        assert reply.trace[0].tool == "flyTo"
        assert reply.trace[0].ok is True
        assert "queued" in reply.trace[0].result_summary


@pytest.mark.asyncio
async def test_multiple_client_actions_keep_order():
    """flyTo + toggleLayer en un mismo turno: orden y ids correlativos."""
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json=_msg_assistant_two_tool_calls(
                        "flyTo",
                        {"coords": {"lat": 42.5, "lon": -7.5, "zoom": 8}},
                        "toggleLayer",
                        {"name": "fires", "on": True},
                    ),
                ),
                httpx.Response(200, json=_msg_assistant_text("listo")),
            ]
        )

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="vete a Galicia y activa los focos")],
            config=_config(),
        )

        assert [ca.action for ca in reply.client_actions] == ["flyTo", "toggleLayer"]
        assert [ca.id for ca in reply.client_actions] == ["ca-1", "ca-2"]


@pytest.mark.asyncio
async def test_mixed_server_and_client_tools_preserve_order(monkeypatch):
    """queryAlerts (server) + flyTo (client) en el mismo turno: ambos llegan al trace."""
    monkeypatch.setattr("main.alerts_cache", [])

    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json=_msg_assistant_two_tool_calls(
                        "queryAlerts",
                        {"phenomenon": "viento"},
                        "flyTo",
                        {"bbox": [-10.0, 35.0, 5.0, 44.0]},
                    ),
                ),
                httpx.Response(200, json=_msg_assistant_text("ok")),
            ]
        )

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="x")],
            config=_config(),
        )

        # Server tool produjo un resumen JSON; client tool produjo 'queued'.
        traces_by_tool = {t.tool: t for t in reply.trace}
        assert "queryAlerts" in traces_by_tool
        assert traces_by_tool["queryAlerts"].ok is True
        assert "total_matched" in traces_by_tool["queryAlerts"].result_summary
        assert "flyTo" in traces_by_tool
        assert "queued" in traces_by_tool["flyTo"].result_summary

        # client_actions contiene la client tool emitida por el LLM (flyTo)
        # y el setVisibleLayers automatico derivado de queryAlerts (flyTo no
        # modifica capas, asi que el auto-emit sigue aplicandose).
        action_pairs = [(ca.action, ca.arguments) for ca in reply.client_actions]
        assert ("flyTo", {"bbox": [-10.0, 35.0, 5.0, 44.0]}) in action_pairs
        assert ("setVisibleLayers", {"names": ["alerts"]}) in action_pairs


@pytest.mark.asyncio
async def test_server_geojson_result_is_auto_queued_and_compacted_for_llm():
    """El GeoJSON pesado viaja al frontend, no en la observacion reinyectada al LLM."""
    async def fake_active_tool(**_kwargs):
        return {
            "total_matched": 1,
            "returned": 1,
            "items": [{"nucleo_nombre": "Aldea", "distance_m": 850.5}],
            "map_layers": ["fires", "nucleos"],
            "map_geojson": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [-7.5, 42.5]},
                        "properties": {"kind": "fire", "label": "Foco"},
                    }
                ],
            },
        }

    old_tool = TOOLS["activeFiresNearPopulation"]
    TOOLS["activeFiresNearPopulation"] = ServerTool(
        name=old_tool.name,
        description=old_tool.description,
        parameters=old_tool.parameters,
        handler=fake_active_tool,
    )
    try:
        with respx.mock(assert_all_called=False) as router:
            request_bodies = []

            def llm_side_effect(request):
                request_bodies.append(json.loads(request.content))
                if len(request_bodies) == 1:
                    return httpx.Response(
                        200,
                        json=_msg_assistant_tool_call(
                            "activeFiresNearPopulation",
                            {"distance_m": 2000, "population_max": 5000},
                        ),
                    )
                return httpx.Response(200, json=_msg_assistant_text("ok"))

            router.post(URL).mock(side_effect=llm_side_effect)

            reply = await run_chat(
                user_messages=[ChatMessage(role="user", content="hay focos activos cerca de nucleos")],
                config=_config(),
            )
    finally:
        TOOLS["activeFiresNearPopulation"] = old_tool

    actions = {ca.action: ca for ca in reply.client_actions}
    assert "showGeoJsonResults" in actions
    assert actions["showGeoJsonResults"].arguments["geojson"]["features"][0]["properties"]["kind"] == "fire"
    # auto setVisibleLayers para que el visor refleje solo las capas usadas.
    assert "setVisibleLayers" in actions
    assert set(actions["setVisibleLayers"].arguments["names"]) == {"fires", "nucleos"}
    assert "map_geojson_summary" in reply.trace[0].result_summary

    assert len(request_bodies) == 2
    second_body = request_bodies[1]
    tool_messages = [m for m in second_body["messages"] if m.get("role") == "tool"]
    observation = json.loads(tool_messages[-1]["content"])
    assert "map_geojson" not in observation
    assert observation["map_geojson_summary"]["feature_count"] == 1
    assert observation["client_actions_queued"] == [
        {"id": "ca-1", "action": "showGeoJsonResults"}
    ]


@pytest.mark.asyncio
async def test_auto_set_visible_layers_for_burnt_area(monkeypatch):
    """queryBurntArea -> backend encola setVisibleLayers(['burnt_area']) y setLayerDate al peak_day."""
    async def fake_burnt_area(**_kwargs):
        return {
            "total_days": 123,
            "returned": 1,
            "truncated": False,
            "filters": {"date_from": "2025-05-01", "date_to": "2025-08-31", "dataset_version": "v4"},
            "total_burned_area_ha": 248383.15,
            "peak_day": {"nominal_date": "2025-08-16", "burned_area_ha": 32305.51},
            "items": [],
        }

    old_tool = TOOLS["queryBurntArea"]
    TOOLS["queryBurntArea"] = ServerTool(
        name=old_tool.name,
        description=old_tool.description,
        parameters=old_tool.parameters,
        handler=fake_burnt_area,
    )
    try:
        with respx.mock(assert_all_called=False) as router:
            router.post(URL).mock(
                side_effect=[
                    httpx.Response(
                        200,
                        json=_msg_assistant_tool_call(
                            "queryBurntArea",
                            {"date_from": "2025-05-01", "date_to": "2025-08-31"},
                        ),
                    ),
                    httpx.Response(200, json=_msg_assistant_text("ok")),
                ]
            )

            reply = await run_chat(
                user_messages=[ChatMessage(role="user", content="que dia se quemo mas?")],
                config=_config(),
            )
    finally:
        TOOLS["queryBurntArea"] = old_tool

    actions = [(ca.action, ca.arguments) for ca in reply.client_actions]
    assert ("setVisibleLayers", {"names": ["burnt_area"]}) in actions
    assert (
        "setLayerDate",
        {"layer": "burnt_area", "date": "2025-08-16"},
    ) in actions


@pytest.mark.asyncio
async def test_auto_set_visible_layers_skipped_if_llm_emits_toggle(monkeypatch):
    """Si el LLM emite toggleLayer/setVisibleLayers, NO se sobrescribe con auto."""
    monkeypatch.setattr("main.alerts_cache", [])

    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(
            side_effect=[
                # Turno 1: queryAlerts + el LLM activa explicitamente 'flood'.
                httpx.Response(
                    200,
                    json=_msg_assistant_two_tool_calls(
                        "queryAlerts",
                        {"phenomenon": "viento"},
                        "toggleLayer",
                        {"name": "flood", "on": True},
                    ),
                ),
                httpx.Response(200, json=_msg_assistant_text("ok")),
            ]
        )

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="vientos + activa inundacion")],
            config=_config(),
        )

    actions = [ca.action for ca in reply.client_actions]
    # El LLM ya gestiono visibilidad: no se inyecta el setVisibleLayers automatico.
    assert "setVisibleLayers" not in actions
    assert "toggleLayer" in actions


@pytest.mark.asyncio
async def test_auto_set_visible_layers_unions_layers_from_multiple_tools(monkeypatch):
    """queryAlerts + queryFires -> setVisibleLayers(['alerts','fires'])."""
    monkeypatch.setattr("main.alerts_cache", [])

    async def fake_query_fires(**_kwargs):
        return {"total_matched": 0, "returned": 0, "items": [], "summary_by_sensor": {}, "max_frp": 0}

    old_tool = TOOLS["queryFires"]
    TOOLS["queryFires"] = ServerTool(
        name=old_tool.name,
        description=old_tool.description,
        parameters=old_tool.parameters,
        handler=fake_query_fires,
    )
    try:
        with respx.mock(assert_all_called=False) as router:
            router.post(URL).mock(
                side_effect=[
                    httpx.Response(
                        200,
                        json=_msg_assistant_two_tool_calls(
                            "queryAlerts", {"phenomenon": "viento"},
                            "queryFires", {},
                        ),
                    ),
                    httpx.Response(200, json=_msg_assistant_text("ok")),
                ]
            )

            reply = await run_chat(
                user_messages=[ChatMessage(role="user", content="x")],
                config=_config(),
            )
    finally:
        TOOLS["queryFires"] = old_tool

    set_visible = [ca for ca in reply.client_actions if ca.action == "setVisibleLayers"]
    assert len(set_visible) == 1
    assert set(set_visible[0].arguments["names"]) == {"alerts", "fires"}


@pytest.mark.asyncio
async def test_no_auto_layers_when_only_searchplace(monkeypatch):
    """searchPlace por si solo no implica ninguna capa; no se inyecta setVisibleLayers."""
    async def fake_search_place(**_kwargs):
        return {"matches": [{"name": "Galicia", "bbox": [-9.3, 41.8, -6.7, 43.8]}]}

    old_tool = TOOLS["searchPlace"]
    TOOLS["searchPlace"] = ServerTool(
        name=old_tool.name,
        description=old_tool.description,
        parameters=old_tool.parameters,
        handler=fake_search_place,
    )
    try:
        with respx.mock(assert_all_called=False) as router:
            router.post(URL).mock(
                side_effect=[
                    httpx.Response(
                        200,
                        json=_msg_assistant_tool_call("searchPlace", {"query": "Galicia"}),
                    ),
                    httpx.Response(200, json=_msg_assistant_text("ok")),
                ]
            )

            reply = await run_chat(
                user_messages=[ChatMessage(role="user", content="bbox de Galicia")],
                config=_config(),
            )
    finally:
        TOOLS["searchPlace"] = old_tool

    actions = [ca.action for ca in reply.client_actions]
    assert "setVisibleLayers" not in actions


@pytest.mark.asyncio
async def test_auto_layer_date_for_single_day_burnt_area(monkeypatch):
    """queryBurntArea con date_from == date_to -> setLayerDate a ese dia exacto, aunque burned_area_ha sea 0."""
    async def fake_burnt_area(**_kwargs):
        return {
            "total_days": 1,
            "returned": 1,
            "filters": {
                "date_from": "2025-06-15",
                "date_to": "2025-06-15",
                "dataset_version": "v4",
            },
            "total_burned_area_ha": 0.0,
            "peak_day": {"nominal_date": "2025-06-15", "burned_area_ha": 0.0},
            "items": [],
        }

    old_tool = TOOLS["queryBurntArea"]
    TOOLS["queryBurntArea"] = ServerTool(
        name=old_tool.name,
        description=old_tool.description,
        parameters=old_tool.parameters,
        handler=fake_burnt_area,
    )
    try:
        with respx.mock(assert_all_called=False) as router:
            router.post(URL).mock(
                side_effect=[
                    httpx.Response(
                        200,
                        json=_msg_assistant_tool_call(
                            "queryBurntArea",
                            {"date_from": "2025-06-15", "date_to": "2025-06-15"},
                        ),
                    ),
                    httpx.Response(200, json=_msg_assistant_text("ok")),
                ]
            )

            reply = await run_chat(
                user_messages=[ChatMessage(role="user", content="area quemada el 15 de junio")],
                config=_config(),
            )
    finally:
        TOOLS["queryBurntArea"] = old_tool

    actions = [(ca.action, ca.arguments) for ca in reply.client_actions]
    assert (
        "setLayerDate",
        {"layer": "burnt_area", "date": "2025-06-15"},
    ) in actions


@pytest.mark.asyncio
async def test_auto_layer_date_for_aemet_max_temp_peak(monkeypatch):
    """queryAemetMaxTempHistory -> setVisibleLayers(['aemet_max_temp_history']) y setLayerDate al peak_day."""
    async def fake_aemet(**_kwargs):
        return {
            "total_days": 92,
            "returned": 1,
            "filters": {"date_from": "2025-06-01", "date_to": "2025-08-31"},
            "total_warning_count": 1234,
            "totals_by_level": {"Rojo": 50, "Naranja": 200, "Amarillo": 800, "Verde": 184},
            "peak_day": {
                "nominal_date": "2025-07-18",
                "max_temperature_c": 44.0,
                "warning_count": 44,
                "red_count": 12,
                "orange_count": 18,
                "yellow_count": 14,
                "green_count": 0,
            },
            "items": [],
        }

    old_tool = TOOLS["queryAemetMaxTempHistory"]
    TOOLS["queryAemetMaxTempHistory"] = ServerTool(
        name=old_tool.name,
        description=old_tool.description,
        parameters=old_tool.parameters,
        handler=fake_aemet,
    )
    try:
        with respx.mock(assert_all_called=False) as router:
            router.post(URL).mock(
                side_effect=[
                    httpx.Response(
                        200,
                        json=_msg_assistant_tool_call(
                            "queryAemetMaxTempHistory",
                            {"date_from": "2025-06-01", "date_to": "2025-08-31"},
                        ),
                    ),
                    httpx.Response(200, json=_msg_assistant_text("ok")),
                ]
            )

            reply = await run_chat(
                user_messages=[ChatMessage(role="user", content="el dia mas caliente del historico")],
                config=_config(),
            )
    finally:
        TOOLS["queryAemetMaxTempHistory"] = old_tool

    actions = [(ca.action, ca.arguments) for ca in reply.client_actions]
    assert ("setVisibleLayers", {"names": ["aemet_max_temp_history"]}) in actions
    assert (
        "setLayerDate",
        {"layer": "aemet_max_temp_history", "date": "2025-07-18"},
    ) in actions


@pytest.mark.asyncio
async def test_auto_layer_date_for_aemet_warnings_near_population(monkeypatch):
    """aemetWarningsNearPopulation(date=X) -> setVisibleLayers(['aemet_max_temp_history','nucleos']) y setLayerDate."""
    async def fake_aemet_near(**_kwargs):
        return {
            "total_matched": 1,
            "returned": 1,
            "truncated": False,
            "filters": {
                "date_from": "2025-07-18",
                "date_to": "2025-07-18",
                "warnings_only": True,
                "min_temperature_c": None,
                "level": None,
                "distance_m": 50000,
            },
            "operation": "ST_DWithin",
            "peak_temperature_c": 44.0,
            "items": [
                {
                    "feature_id": "f1",
                    "area_name": "Vega del Guadalquivir",
                    "level_label": "Rojo",
                    "temperature_max_c": 44.0,
                    "nucleo_nombre": "Ecija",
                    "distance_m": 0.0,
                }
            ],
        }

    old_tool = TOOLS["aemetWarningsNearPopulation"]
    TOOLS["aemetWarningsNearPopulation"] = ServerTool(
        name=old_tool.name,
        description=old_tool.description,
        parameters=old_tool.parameters,
        handler=fake_aemet_near,
    )
    try:
        with respx.mock(assert_all_called=False) as router:
            router.post(URL).mock(
                side_effect=[
                    httpx.Response(
                        200,
                        json=_msg_assistant_tool_call(
                            "aemetWarningsNearPopulation",
                            {"date": "2025-07-18"},
                        ),
                    ),
                    httpx.Response(200, json=_msg_assistant_text("ok")),
                ]
            )

            reply = await run_chat(
                user_messages=[ChatMessage(role="user", content="que nucleo esta mas cerca")],
                config=_config(),
            )
    finally:
        TOOLS["aemetWarningsNearPopulation"] = old_tool

    actions = [(ca.action, ca.arguments) for ca in reply.client_actions]
    set_visible = [args for action, args in actions if action == "setVisibleLayers"]
    assert len(set_visible) == 1
    assert set(set_visible[0]["names"]) == {"aemet_max_temp_history", "nucleos"}
    assert (
        "setLayerDate",
        {"layer": "aemet_max_temp_history", "date": "2025-07-18"},
    ) in actions


@pytest.mark.asyncio
async def test_auto_layer_date_for_single_day_firms_hotspot_analysis(monkeypatch):
    """firmsHotspotAnalysis con un solo dia -> setLayerDate(firms_history, ese_dia)."""
    async def fake_hotspot(**_kwargs):
        return {
            "total_clusters": 0,
            "returned": 0,
            "filters": {
                "date_from": "2025-08-16",
                "date_to": "2025-08-16",
                "bbox": None,
                "sensor": None,
                "eps_meters": 1500,
                "min_points": 4,
            },
            "items": [],
        }

    old_tool = TOOLS["firmsHotspotAnalysis"]
    TOOLS["firmsHotspotAnalysis"] = ServerTool(
        name=old_tool.name,
        description=old_tool.description,
        parameters=old_tool.parameters,
        handler=fake_hotspot,
    )
    try:
        with respx.mock(assert_all_called=False) as router:
            router.post(URL).mock(
                side_effect=[
                    httpx.Response(
                        200,
                        json=_msg_assistant_tool_call(
                            "firmsHotspotAnalysis",
                            {"date_from": "2025-08-16", "date_to": "2025-08-16"},
                        ),
                    ),
                    httpx.Response(200, json=_msg_assistant_text("ok")),
                ]
            )

            reply = await run_chat(
                user_messages=[ChatMessage(role="user", content="focos del 16 ago")],
                config=_config(),
            )
    finally:
        TOOLS["firmsHotspotAnalysis"] = old_tool

    actions = [(ca.action, ca.arguments) for ca in reply.client_actions]
    assert (
        "setLayerDate",
        {"layer": "firms_history", "date": "2025-08-16"},
    ) in actions
    assert ("setVisibleLayers", {"names": ["firms_history"]}) in actions


@pytest.mark.asyncio
async def test_auto_layer_date_skipped_if_peak_is_zero(monkeypatch):
    """Si peak_day.burned_area_ha es 0, no se encola setLayerDate."""
    async def fake_burnt_area(**_kwargs):
        return {
            "total_days": 5,
            "returned": 0,
            "filters": {},
            "total_burned_area_ha": 0.0,
            "peak_day": {"nominal_date": "2025-05-01", "burned_area_ha": 0.0},
            "items": [],
        }

    old_tool = TOOLS["queryBurntArea"]
    TOOLS["queryBurntArea"] = ServerTool(
        name=old_tool.name,
        description=old_tool.description,
        parameters=old_tool.parameters,
        handler=fake_burnt_area,
    )
    try:
        with respx.mock(assert_all_called=False) as router:
            router.post(URL).mock(
                side_effect=[
                    httpx.Response(
                        200,
                        json=_msg_assistant_tool_call("queryBurntArea", {}),
                    ),
                    httpx.Response(200, json=_msg_assistant_text("ok")),
                ]
            )

            reply = await run_chat(
                user_messages=[ChatMessage(role="user", content="x")],
                config=_config(),
            )
    finally:
        TOOLS["queryBurntArea"] = old_tool

    actions = [ca.action for ca in reply.client_actions]
    assert "setLayerDate" not in actions
    # setVisibleLayers si se emite (la capa de burnt_area se consulto).
    assert "setVisibleLayers" in actions


@pytest.mark.asyncio
async def test_invalid_client_args_dont_queue():
    """Si los args de una client tool no validan, no se encola y se reinyecta tool_error."""
    with respx.mock(assert_all_called=False) as router:
        router.post(URL).mock(
            side_effect=[
                # bbox de longitud invalida (solo 2 elementos)
                httpx.Response(200, json=_msg_assistant_tool_call("flyTo", {"bbox": [1.0, 2.0]})),
                httpx.Response(200, json=_msg_assistant_text("ok")),
            ]
        )

        reply = await run_chat(
            user_messages=[ChatMessage(role="user", content="x")],
            config=_config(),
        )

        assert reply.client_actions == []
        assert reply.trace[0].ok is False
        assert "tool_error" in (reply.trace[0].error or "")
