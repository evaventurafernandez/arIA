"""Tool queryAemetMaxTempHistory: historico diario de avisos AEMET de
temperaturas maximas.

Lee de `pub.aemet_max_temperature_daily_stat` (la misma fuente que la capa
`aemet_max_temp_history` del visor) y devuelve para cada dia el numero de
zonas en aviso, el desglose por nivel (Verde/Amarillo/Naranja/Rojo) y la
maxima temperatura nominal AEMET registrada (`max_temperature_c`).

Util para preguntas tipo "que dia del historico hubo el aviso de
temperatura mas alta" o "cuantos avisos hubo en julio". El dia pico se
calcula por `max_temperature_c` (no por numero de avisos).
"""

from __future__ import annotations

from typing import Any

from chat.tools import server_tool


SCHEMA = {
    "type": "object",
    "properties": {
        "date_from": {
            "type": "string",
            "description": "Fecha minima YYYY-MM-DD (inclusiva).",
        },
        "date_to": {
            "type": "string",
            "description": "Fecha maxima YYYY-MM-DD (inclusiva).",
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
    name="queryAemetMaxTempHistory",
    description=(
        "Consulta el historico diario de avisos AEMET CAP filtrados al "
        "fenomeno 'AT;Temperaturas maximas'. Devuelve la serie por dia con "
        "numero de zonas en aviso, desglose por nivel y la maxima "
        "temperatura registrada, mas el dia pico (mayor temperatura "
        "nominal del rango). Cobertura del historico: la misma que la "
        "capa aemet_max_temp_history del visor. Util para 'que dia hubo "
        "el aviso de temperatura mas alta' o 'cuantas zonas en aviso "
        "rojo hubo'."
    ),
    parameters=SCHEMA,
)
async def query_aemet_max_temp_history(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    from main import query_aemet_max_temperature_stats_rows

    rows = query_aemet_max_temperature_stats_rows(date_from, date_to)

    peak_day: dict[str, Any] | None = None
    peak_temp: float | None = None
    total_warning_count = 0
    total_red = 0
    total_orange = 0
    total_yellow = 0
    total_green = 0

    for row in rows:
        max_temp = row.get("max_temperature_c")
        if isinstance(max_temp, (int, float)):
            if peak_temp is None or max_temp > peak_temp:
                peak_temp = float(max_temp)
                peak_day = {
                    "nominal_date": row.get("nominal_date"),
                    "max_temperature_c": float(max_temp),
                    "warning_count": int(row.get("warning_count", 0)),
                    "red_count": int(row.get("red_count", 0)),
                    "orange_count": int(row.get("orange_count", 0)),
                    "yellow_count": int(row.get("yellow_count", 0)),
                    "green_count": int(row.get("green_count", 0)),
                }
        total_warning_count += int(row.get("warning_count", 0))
        total_red += int(row.get("red_count", 0))
        total_orange += int(row.get("orange_count", 0))
        total_yellow += int(row.get("yellow_count", 0))
        total_green += int(row.get("green_count", 0))

    items = [
        {
            "nominal_date": row.get("nominal_date"),
            "warning_count": int(row.get("warning_count", 0)),
            "max_temperature_c": (
                float(row["max_temperature_c"]) if row.get("max_temperature_c") is not None else None
            ),
            "red_count": int(row.get("red_count", 0)),
            "orange_count": int(row.get("orange_count", 0)),
            "yellow_count": int(row.get("yellow_count", 0)),
            "green_count": int(row.get("green_count", 0)),
            "coverage_complete": bool(row.get("coverage_complete", False)),
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
        },
        "total_warning_count": total_warning_count,
        "totals_by_level": {
            "Rojo": total_red,
            "Naranja": total_orange,
            "Amarillo": total_yellow,
            "Verde": total_green,
        },
        "peak_day": peak_day,
        "items": items,
    }
