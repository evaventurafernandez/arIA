"""Tool aemetWarningsNearPopulation: zonas AEMET de temperaturas maximas y
el nucleo de poblacion mas cercano para una fecha concreta.

Cruza `pub.aemet_max_temperature_daily_feature` (poligonos de zonas AEMET
en aviso por fenomeno AT;Temperaturas maximas, por dia) con
`core.nucleos_poblacion_polygon` (capa local IGN de nucleos de poblacion).
Para cada zona, calcula el nucleo mas cercano via `ST_Distance` sobre
geography. Util para preguntas tipo "que nucleo esta mas cerca del aviso
de temperatura mas alta del 18 de julio" o "que poblaciones quedan dentro
de zonas de aviso rojo el dia X".
"""

from __future__ import annotations

from typing import Any

from chat.tools import server_tool


SCHEMA = {
    "type": "object",
    "properties": {
        "date": {
            "type": "string",
            "pattern": r"^\d{4}-\d{2}-\d{2}$",
            "description": "Fecha YYYY-MM-DD del aviso (valid_date).",
        },
        "warnings_only": {
            "type": "boolean",
            "description": "Si true (por defecto), solo zonas con is_warning=true (Amarillo/Naranja/Rojo).",
            "default": True,
        },
        "min_temperature_c": {
            "type": "number",
            "description": "Filtro opcional: incluir solo zonas con temperature_max_c >= este valor.",
        },
        "level": {
            "type": "string",
            "enum": ["Verde", "Amarillo", "Naranja", "Rojo"],
            "description": "Filtro opcional por nivel AEMET de la zona.",
        },
        "distance_m": {
            "type": "integer",
            "description": (
                "Distancia maxima en metros entre zona AEMET y nucleo. Por defecto 50000 "
                "(50 km). Las zonas AEMET son administrativas y suelen incluir nucleos "
                "dentro, lo que produce distancia 0."
            ),
            "minimum": 100,
            "maximum": 200000,
            "default": 50000,
        },
        "nucleo_strategy": {
            "type": "string",
            "enum": ["closest", "most_populated"],
            "default": "closest",
            "description": (
                "Criterio para elegir UN nucleo por zona AEMET. 'closest' (por defecto) "
                "devuelve el geometricamente mas cercano. 'most_populated' devuelve el "
                "de mayor poblacion entre los que estan dentro o cerca de la zona, "
                "rompiendo empates por distancia. Usar 'most_populated' cuando el usuario "
                "pida 'el nucleo con mas habitantes' o 'la ciudad mas grande' dentro del "
                "aviso."
            ),
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 200,
            "default": 50,
            "description": "Maximo numero de pares zona-nucleo devueltos.",
        },
    },
    "required": ["date"],
    "additionalProperties": False,
}


@server_tool(
    name="aemetWarningsNearPopulation",
    description=(
        "Para una fecha del historico, lista las zonas AEMET en aviso por "
        "temperaturas maximas (fenomeno AT;Temperaturas maximas) y, por "
        "cada zona, UN nucleo de poblacion del IGN (ST_Distance sobre "
        "geography). El criterio se elige con 'nucleo_strategy': 'closest' "
        "(por defecto, el mas cercano) o 'most_populated' (el de mayor "
        "poblacion entre los proximos). Permite filtros opcionales por nivel, "
        "temperatura minima y distancia. Ordena por temperatura nominal "
        "descendente: el primer item suele ser la zona mas calida del dia. "
        "Util para 'que nucleo esta mas cerca del aviso mas caliente del 18 "
        "de julio' (closest) o 'que ciudad/nucleo con mas habitantes hay "
        "dentro del aviso' (most_populated)."
    ),
    parameters=SCHEMA,
)
async def aemet_warnings_near_population(
    *,
    date: str,
    warnings_only: bool = True,
    min_temperature_c: float | None = None,
    level: str | None = None,
    distance_m: int = 50000,
    nucleo_strategy: str = "closest",
    limit: int = 50,
) -> dict[str, Any]:
    from main import get_db_pool

    try:
        pool = get_db_pool()
    except RuntimeError as exc:
        return {
            "error": str(exc),
            "total_matched": 0,
            "items": [],
            "filters": {
                "date": date,
                "warnings_only": warnings_only,
                "min_temperature_c": min_temperature_c,
                "level": level,
                "distance_m": distance_m,
            },
        }

    if nucleo_strategy not in ("closest", "most_populated"):
        nucleo_strategy = "closest"

    where_extra: list[str] = []
    extra_params: list[Any] = []
    if warnings_only:
        where_extra.append("f.is_warning")
    if level is not None:
        where_extra.append("f.level_label = %s")
        extra_params.append(level)
    if min_temperature_c is not None:
        where_extra.append("f.temperature_max_c >= %s")
        extra_params.append(float(min_temperature_c))

    where_sql = ""
    if where_extra:
        where_sql = "AND " + " AND ".join(where_extra) + " "

    # El LATERAL elige UN nucleo por zona AEMET. El orden de seleccion depende
    # de nucleo_strategy:
    # - 'closest': por distancia geometrica ascendente (operador KNN <->).
    # - 'most_populated': por habitantes descendente, rompiendo empates por
    #   distancia geografica real, para que ante varios nucleos dentro del
    #   poligono (distance=0) gane el de mayor poblacion.
    if nucleo_strategy == "most_populated":
        lateral_order = (
            "ORDER BY habitantes DESC NULLS LAST, "
            "ST_Distance(f.geom::geography, geom::geography) ASC"
        )
    else:
        lateral_order = "ORDER BY f.geom <-> geom"

    sql = f"""
        SELECT
            f.feature_id,
            f.area_name,
            f.area_code,
            f.level_label,
            f.level_rank,
            f.temperature_max_c,
            f.probability,
            f.onset_at,
            f.expires_at,
            n.core_feature_id::text,
            n.nombre,
            n.habitantes,
            ST_X(ST_Centroid(n.geom)) AS nucleo_lon,
            ST_Y(ST_Centroid(n.geom)) AS nucleo_lat,
            ST_Distance(f.geom::geography, n.geom::geography) AS distance_m
        FROM pub.aemet_max_temperature_daily_feature f
        JOIN LATERAL (
            SELECT core_feature_id, nombre, habitantes, geom
            FROM core.nucleos_poblacion_polygon
            WHERE habitantes IS NOT NULL
              AND habitantes > 0
              AND ST_DWithin(f.geom::geography, geom::geography, %s)
            {lateral_order}
            LIMIT 1
        ) n ON true
        WHERE f.valid_date = %s::date
          {where_sql}
        ORDER BY f.temperature_max_c DESC NULLS LAST, f.level_rank DESC, f.area_name
        LIMIT %s
    """
    params: list[Any] = [distance_m] + extra_params + [date, limit + 1]

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
    except Exception as exc:
        return {
            "error": f"Fallo de consulta SQL: {exc}",
            "total_matched": 0,
            "items": [],
            "filters": {
                "date": date,
                "warnings_only": warnings_only,
                "min_temperature_c": min_temperature_c,
                "level": level,
                "distance_m": distance_m,
            },
        }

    truncated = len(rows) > limit
    rows = rows[:limit]

    items = [
        {
            "feature_id": r[0],
            "area_name": r[1],
            "area_code": r[2],
            "level_label": r[3],
            "level_rank": int(r[4]) if r[4] is not None else None,
            "temperature_max_c": float(r[5]) if r[5] is not None else None,
            "probability": r[6],
            "onset_at": r[7].isoformat() if r[7] is not None else None,
            "expires_at": r[8].isoformat() if r[8] is not None else None,
            "nucleo_id": r[9],
            "nucleo_nombre": r[10],
            "nucleo_habitantes": int(r[11]) if r[11] is not None else None,
            "nucleo_lon": float(r[12]),
            "nucleo_lat": float(r[13]),
            "distance_m": round(float(r[14]), 1),
        }
        for r in rows
    ]

    peak_temperature_c: float | None = None
    for it in items:
        t = it.get("temperature_max_c")
        if isinstance(t, (int, float)):
            if peak_temperature_c is None or t > peak_temperature_c:
                peak_temperature_c = float(t)

    return {
        "total_matched": len(items) + (1 if truncated else 0),
        "returned": len(items),
        "truncated": truncated,
        "filters": {
            "date_from": date,
            "date_to": date,
            "warnings_only": warnings_only,
            "min_temperature_c": min_temperature_c,
            "level": level,
            "distance_m": distance_m,
            "nucleo_strategy": nucleo_strategy,
        },
        "operation": (
            "ST_DWithin(aemet_zone::geography, nucleo::geography) + "
            "ST_Distance(); LATERAL ordenado por "
            + ("habitantes DESC" if nucleo_strategy == "most_populated" else "<-> KNN")
        ),
        "peak_temperature_c": peak_temperature_c,
        "items": items,
    }
