"""Tool firesNearPopulation: focos FIRMS HISTORICOS a menos de N metros de nucleos.

Cruza `core.firms_hotspot` con `core.nucleos_poblacion_polygon` usando
ST_DWithin sobre geography (metros). FIRMS activos NO se cubren aqui: para
'cerca' en tiempo real usar `activeFiresNearPopulation`.
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
        "retrospectiva. NO opera sobre focos activos en vivo; si el usuario "
        "quiere 'hoy' o 'activo', usa activeFiresNearPopulation."
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

    # Estrategia de rendimiento:
    # 1) Filtro grueso con ST_DWithin sobre geometry (grados): aprovecha el
    #    indice GIST de fh.geom y np.geom. El margen `deg_margin` es una
    #    aproximacion de 1 grado ~= 111 km en latitudes medias; añadimos
    #    20 % de holgura para no descartar candidatos cerca del umbral.
    # 2) Calculo fino de la distancia con ST_Distance sobre geography (metros).
    # 3) Filtro final por distancia <= distance_m.
    # LATERAL con LIMIT 1 deja un solo nucleo (el mas cercano) por foco.
    deg_margin = (float(distance_m) / 111_000.0) * 1.2

    where_extra = ""
    sensor_params: list[Any] = []
    if sensor:
        where_extra = "AND fh.firms_source = %s "
        sensor_params = [sensor]

    sql = f"""
        SELECT
            fh.hotspot_id::text,
            fh.firms_source,
            fh.acq_date::text,
            fh.frp,
            fh.confidence,
            fh.latitude,
            fh.longitude,
            np.nombre,
            np.habitantes,
            np.distance_m
        FROM core.firms_hotspot fh
        CROSS JOIN LATERAL (
            SELECT
                n.nombre, n.habitantes,
                ST_Distance(fh.geom::geography, n.geom::geography) AS distance_m
            FROM core.nucleos_poblacion_polygon n
            WHERE ST_DWithin(fh.geom, n.geom, %s)
            ORDER BY fh.geom <-> n.geom
            LIMIT 1
        ) np
        WHERE fh.acq_date >= %s AND fh.acq_date <= %s
          AND np.distance_m <= %s
          {where_extra}
        ORDER BY np.distance_m ASC
        LIMIT %s
    """
    params: list[Any] = [deg_margin, date_from, date_to, distance_m] + sensor_params + [limit + 1]

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
