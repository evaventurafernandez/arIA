"""Tool summarizeSituation: panorama agregado de la situacion actual.

Compone los resultados de queryAlerts, queryFires y queryBurntArea en una
sola respuesta. Las consultas se lanzan concurrentemente con asyncio.gather
para minimizar latencia. Devuelve un resumen para briefing rapido + los tres
payloads completos por si el LLM quiere ampliar despues.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

from chat.tools import server_tool
from chat.tools.server.query_alerts import query_alerts
from chat.tools.server.query_burnt_area import query_burnt_area
from chat.tools.server.query_fires import query_fires


SCHEMA = {
    "type": "object",
    "properties": {
        "scope": {
            "type": "string",
            "enum": ["nacional"],
            "description": (
                "Ambito del resumen. En Fase 3 solo se admite 'nacional' "
                "(Espana entera). Otros valores se rechazan."
            ),
            "default": "nacional",
        },
        "include_burnt_area": {
            "type": "boolean",
            "default": False,
            "description": (
                "Si true, incluye un resumen retrospectivo de area quemada del "
                "ultimo mes cubierto por Burnt Area v4 (verano 2025). Por "
                "defecto false para evitar 'mezclar' tiempos en un panorama 'hoy'."
            ),
        },
    },
    "additionalProperties": False,
}


@server_tool(
    name="summarizeSituation",
    description=(
        "Resumen ejecutivo de la situacion actual en Espana: avisos AEMET "
        "vigentes (queryAlerts) + focos NASA FIRMS activos (queryFires), "
        "opcionalmente con un agregado retrospectivo de areas quemadas "
        "Burnt Area v4. Util para preguntas 'resumeme la situacion de "
        "incendios hoy' o 'que esta pasando ahora mismo'."
    ),
    parameters=SCHEMA,
)
async def summarize_situation(
    *, scope: str = "nacional", include_burnt_area: bool = False
) -> dict[str, Any]:
    coros: list[Any] = [
        query_alerts(status="vigente", limit=200),
        query_fires(limit=200),
    ]
    if include_burnt_area:
        today = date.today()
        date_from = (today - timedelta(days=30)).isoformat()
        date_to = today.isoformat()
        coros.append(query_burnt_area(date_from=date_from, date_to=date_to, limit=50))

    results = await asyncio.gather(*coros, return_exceptions=True)

    alerts_res = results[0]
    fires_res = results[1]
    burnt_res = results[2] if include_burnt_area else None

    payload: dict[str, Any] = {"scope": scope, "components": {}}

    if isinstance(alerts_res, Exception):
        payload["components"]["alerts"] = {"error": str(alerts_res)}
    else:
        payload["components"]["alerts"] = alerts_res
        payload["alerts_total"] = alerts_res.get("total_matched", 0)
        payload["alerts_by_level"] = alerts_res.get("summary_by_level", {})

    if isinstance(fires_res, Exception):
        payload["components"]["fires"] = {"error": str(fires_res)}
    else:
        payload["components"]["fires"] = fires_res
        payload["fires_total"] = fires_res.get("total_matched", 0)
        payload["fires_max_frp"] = fires_res.get("max_frp", 0)
        payload["fires_by_sensor"] = fires_res.get("summary_by_sensor", {})

    if burnt_res is not None:
        if isinstance(burnt_res, Exception):
            payload["components"]["burnt_area"] = {"error": str(burnt_res)}
        else:
            payload["components"]["burnt_area"] = burnt_res
            payload["burnt_area_total_ha_last30d"] = burnt_res.get("total_burned_area_ha")

    return payload
