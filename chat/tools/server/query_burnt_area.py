"""Tool queryBurntArea: estadisticas diarias de area quemada Burnt Area v4.

Reutiliza `query_burnt_area_stats_rows()` de `main.py`, que consulta la tabla
`pub.burnt_area_daily_stat` (escala pais, no admite filtro espacial bbox).
La cobertura nominal es 2025-05-01 a 2025-08-31; fuera de ese rango se
devuelve lista vacia, lo cual es un caso de borde valido que el LLM debe
declarar al usuario.
"""

from __future__ import annotations

from typing import Any

from chat.tools import server_tool


SCHEMA = {
    "type": "object",
    "properties": {
        "date_from": {
            "type": "string",
            "description": "Fecha minima YYYY-MM-DD (inclusiva). Por defecto 2025-05-01.",
            "default": "2025-05-01",
        },
        "date_to": {
            "type": "string",
            "description": "Fecha maxima YYYY-MM-DD (inclusiva). Por defecto 2025-08-31.",
            "default": "2025-08-31",
        },
        "dataset_version": {
            "type": "string",
            "description": "Version del dataset Burnt Area. Por defecto 'v4'.",
            "default": "v4",
        },
        "limit": {
            "type": "integer",
            "description": "Maximo numero de dias devueltos en 'items'. Por defecto 50.",
            "minimum": 1,
            "maximum": 500,
            "default": 50,
        },
    },
    "additionalProperties": False,
}


@server_tool(
    name="queryBurntArea",
    description=(
        "Consulta estadisticas diarias de area quemada (Copernicus CLMS Burnt "
        "Area v4) en Espana entre dos fechas. Devuelve area total acumulada en "
        "hectareas, dia pico, y una serie diaria. Cobertura nominal "
        "2025-05-01 a 2025-08-31; fuera de ese rango la consulta puede "
        "devolver lista vacia y el LLM debe declarar la limitacion."
    ),
    parameters=SCHEMA,
)
async def query_burnt_area(
    *,
    date_from: str = "2025-05-01",
    date_to: str = "2025-08-31",
    dataset_version: str = "v4",
    limit: int = 50,
) -> dict[str, Any]:
    from main import query_burnt_area_stats_rows

    rows = query_burnt_area_stats_rows(
        dataset_version=dataset_version,
        delivery_format="cog",
        date_from=date_from,
        date_to=date_to,
    )

    total_ha = 0.0
    peak_day: dict[str, Any] | None = None
    peak_ha = -1.0
    for row in rows:
        ha = row.get("burned_area_ha") or 0.0
        total_ha += ha
        if ha > peak_ha:
            peak_ha = ha
            peak_day = {"nominal_date": row.get("nominal_date"), "burned_area_ha": ha}

    items = [
        {
            "nominal_date": row.get("nominal_date"),
            "burned_area_ha": row.get("burned_area_ha"),
            "burned_pixel_count": row.get("burned_pixel_count"),
        }
        for row in rows[:limit]
    ]

    return {
        "total_days": len(rows),
        "returned": len(items),
        "truncated": len(rows) > len(items),
        "filters": {
            "date_from": date_from,
            "date_to": date_to,
            "dataset_version": dataset_version,
        },
        "total_burned_area_ha": round(total_ha, 2),
        "peak_day": peak_day,
        "items": items,
    }
