"""Tool firesNearPopulation: focos FIRMS HISTORICOS a menos de N metros de nucleos.

Cruza `core.firms_hotspot` con `core.nucleos_poblacion_polygon` usando
ST_DWithin sobre geography (metros). FIRMS activos NO se cubren aqui: para
'cerca' en tiempo real haria falta otra ruta (su geometria no esta en BD).
"""

from __future__ import annotations

from typing import Any

from chat.tools import server_tool


SCHEMA = {
    "type": "object",
    "properties": {
        "date_from": {
            "type": "string",
            "description": "Fecha minima YYYY-MM-DD inclusiva (acq_date del foco).",
        },
        "date_to": {
            "type": "string",
            "description": "Fecha maxima YYYY-MM-DD inclusiva.",
        },
        "distance_m": {
            "type": "integer",
            "description": "Distancia maxima en metros entre foco y nucleo. Por defecto 5000 (5 km).",
            "minimum": 100,
            "maximum": 50000,
            "default": 5000,
        },
        "sensor": {
            "type": "string",
            "enum": ["VIIRS_NOAA20_SP", "VIIRS_NOAA21_SP", "VIIRS_SNPP_SP", "MODIS_SP"],
            "description": "Filtro opcional por sensor (firms_source).",
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 500,
            "default": 100,
            "description": "Maximo de pares foco-nucleo devueltos en items.",
        },
    },
    "required": ["date_from", "date_to"],
    "additionalProperties": False,
}


@server_tool(
    name="firesNearPopulation",
    description=(
        "Lista focos NASA FIRMS HISTORICOS a menos de N metros de un nucleo de "
        "poblacion del IGN, en un rango de fechas. Cobertura del historico: "
        "mayo-agosto 2025. La consulta usa ST_DWithin sobre geography "
        "(metros reales, no grados). Util para evaluar exposicion poblacional "
        "retrospectiva. NO opera sobre focos activos en vivo (esos no estan "
        "en la BD); si el usuario quiere 'hoy', proponle queryFires + bbox."
    ),
    parameters=SCHEMA,
)
async def fires_near_population(
    *,
    date_from: str,
    date_to: str,
    distance_m: int = 5000,
    sensor: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    from main import get_db_pool

    try:
        pool = get_db_pool()
    except RuntimeError as exc:
        return {"error": str(exc), "total_matched": 0, "items": []}

    where_extra = ""
    params: list[Any] = [distance_m, date_from, date_to]
    if sensor:
        where_extra = "AND fh.firms_source = %s "
        params.append(sensor)

    sql = f"""
        SELECT
            fh.id::text,
            fh.firms_source,
            fh.acq_date::text,
            fh.frp,
            fh.confidence,
            fh.latitude,
            fh.longitude,
            np.nombre,
            np.habitantes,
            ST_Distance(fh.geom::geography, np.geom::geography) AS distance_m
        FROM core.firms_hotspot fh
        JOIN LATERAL (
            SELECT n.nombre, n.habitantes, n.geom
            FROM core.nucleos_poblacion_polygon n
            WHERE ST_DWithin(fh.geom::geography, n.geom::geography, %s)
            ORDER BY fh.geom::geography <-> n.geom::geography
            LIMIT 1
        ) np ON TRUE
        WHERE fh.acq_date >= %s AND fh.acq_date <= %s {where_extra}
        ORDER BY distance_m ASC
        LIMIT %s
    """
    params.append(limit + 1)  # +1 para detectar truncado

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
    except Exception as exc:
        return {"error": f"Fallo de consulta SQL: {exc}", "total_matched": 0, "items": []}

    truncated = len(rows) > limit
    rows = rows[:limit]

    items = [
        {
            "fire_id": r[0],
            "sensor": r[1],
            "acq_date": r[2],
            "frp": float(r[3]) if r[3] is not None else None,
            "confidence": r[4],
            "latitude": float(r[5]),
            "longitude": float(r[6]),
            "nucleo_nombre": r[7],
            "nucleo_habitantes": r[8],
            "distance_m": round(float(r[9]), 1),
        }
        for r in rows
    ]

    return {
        "total_matched": len(items) + (1 if truncated else 0),
        "returned": len(items),
        "truncated": truncated,
        "filters": {
            "date_from": date_from, "date_to": date_to,
            "distance_m": distance_m, "sensor": sensor,
        },
        "items": items,
    }
