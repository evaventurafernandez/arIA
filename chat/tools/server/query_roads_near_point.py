"""Tool queryRoadsNearPoint: tramos viarios IGR-RT cercanos a una coordenada.

Consulta `core.road_segment` (fallback local IGR-RT del visor) con un radio
en metros. Devuelve los tramos mas proximos al punto ordenados por distancia,
con todos los campos del contrato comun publicado por el visor (clase, tipo,
nombre, codigo, titular, sentido, acceso, estado fisico, firme, carriles,
orden, territorio).

La fuente es local IGR-RT, no el WFS de IDEE. Razon: el LLM necesita una
respuesta rapida y completa (con atributos) para razonar sobre la red viaria
proxima a un foco, un aviso o un nucleo. El WFS solo aporta geometria fresca
y exigiria un join adicional por tramo; el atributo "frescura" no aplica al
caso de uso conversacional.
"""

from __future__ import annotations

from typing import Any

from chat.tools import server_tool


ROADS_VALID_CLASES = [
    "Autopista de peaje",
    "Autopista libre / autovía",
    "Carretera multicarril",
    "Carretera convencional",
    "Urbano",
    "Urbano diseminado",
    "Camino",
    "Carril bici",
    "Senda",
]


SCHEMA = {
    "type": "object",
    "properties": {
        "lon": {
            "type": "number",
            "minimum": -180,
            "maximum": 180,
            "description": "Longitud WGS84 del punto de consulta.",
        },
        "lat": {
            "type": "number",
            "minimum": -90,
            "maximum": 90,
            "description": "Latitud WGS84 del punto de consulta.",
        },
        "radius_m": {
            "type": "integer",
            "minimum": 50,
            "maximum": 20000,
            "default": 1000,
            "description": "Radio de busqueda en metros alrededor del punto.",
        },
        "max_results": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "default": 20,
            "description": "Limite de tramos devueltos.",
        },
        "classes": {
            "type": "array",
            "items": {"type": "string", "enum": ROADS_VALID_CLASES},
            "description": (
                "Filtro opcional por clases del catalogo IGR-RT. Si se omite, "
                "devuelve todas las clases. Util para preguntas como 'autopistas "
                "cerca de X' o 'caminos en torno a Y'."
            ),
        },
    },
    "required": ["lon", "lat"],
    "additionalProperties": False,
}


@server_tool(
    name="queryRoadsNearPoint",
    description=(
        "Devuelve los tramos viarios IGR-RT mas cercanos a una coordenada (WGS84) "
        "dentro de un radio en metros. Util para razonar sobre la red viaria "
        "proxima a un foco, un aviso o un nucleo, o para responder preguntas como "
        "'que autopistas pasan cerca del punto X' o 'que carretera es la mas "
        "proxima al foco activo Y'. La fuente es la copia local IGR-RT (IGN/CNIG), "
        "que cubre toda Espana (50 provincias + Ceuta + Melilla)."
    ),
    parameters=SCHEMA,
)
async def query_roads_near_point(
    *,
    lon: float,
    lat: float,
    radius_m: int = 1000,
    max_results: int = 20,
    classes: list[str] | None = None,
) -> dict[str, Any]:
    from main import get_db_pool

    clase_filter_sql = " AND clase = ANY(%s::text[])" if classes else ""
    sql = f"""
    WITH q AS (
        SELECT ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography AS geog
    )
    SELECT
        rs.id_tramo,
        rs.inspire_id,
        rs.clase,
        rs.tipo,
        rs.nombre,
        rs.nombre_alt,
        rs.codigo,
        rs.titular,
        rs.sentido,
        rs.acceso,
        rs.estado_fisico,
        rs.firme,
        rs.n_carriles,
        rs.orden,
        rs.tipovehic,
        rs.territory_code,
        ST_Distance(rs.geom::geography, q.geog)::int AS distance_m
    FROM core.road_segment rs, q
    WHERE ST_DWithin(rs.geom::geography, q.geog, %s){clase_filter_sql}
    ORDER BY distance_m ASC
    LIMIT %s
    """
    params: list[object] = [lon, lat, radius_m]
    if classes:
        params.append(classes)
    params.append(max_results)

    try:
        with get_db_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                cols = [d.name for d in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as exc:
        return {
            "found": False,
            "lon": lon, "lat": lat, "radius_m": radius_m,
            "error": f"Fallo al consultar core.road_segment: {exc}",
        }

    return {
        "found": len(rows) > 0,
        "lon": lon,
        "lat": lat,
        "radius_m": radius_m,
        "max_results": max_results,
        "classes_filter": classes,
        "returned_count": len(rows),
        "results": rows,
        "source": "IGR-RT local (IGN/CNIG, via core.road_segment)",
    }
