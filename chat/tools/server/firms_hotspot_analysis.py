"""Tool firmsHotspotAnalysis: clusters de focos FIRMS HISTORICOS por densidad.

Usa `ST_ClusterDBSCAN` de PostGIS sobre `core.firms_hotspot`, filtrando por
rango temporal, bbox opcional y sensor. Devuelve el centroide, conteo de
focos y FRP medio/maximo de cada cluster detectado.

Si la version de PostGIS no soporta ST_ClusterDBSCAN, la tool devuelve un
error controlado en lugar de fallar; el LLM lo reinyecta y explica al usuario.
"""

from __future__ import annotations

from typing import Any

from chat.tools import server_tool


SCHEMA = {
    "type": "object",
    "properties": {
        "date_from": {"type": "string", "description": "Fecha minima YYYY-MM-DD."},
        "date_to": {"type": "string", "description": "Fecha maxima YYYY-MM-DD."},
        "bbox": {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 4,
            "maxItems": 4,
            "description": "[min_lon, min_lat, max_lon, max_lat] WGS84 opcional.",
        },
        "sensor": {
            "type": "string",
            "enum": ["VIIRS_NOAA20_SP", "VIIRS_NOAA21_SP", "VIIRS_SNPP_SP", "MODIS_SP"],
        },
        "eps_meters": {
            "type": "integer",
            "minimum": 100,
            "maximum": 50000,
            "default": 1500,
            "description": "Radio del vecindario DBSCAN en metros. Por defecto 1.5 km.",
        },
        "min_points": {
            "type": "integer",
            "minimum": 2,
            "maximum": 50,
            "default": 4,
            "description": "Numero minimo de focos para considerar un cluster denso.",
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 200,
            "default": 50,
            "description": "Maximo clusters en items.",
        },
    },
    "required": ["date_from", "date_to"],
    "additionalProperties": False,
}


@server_tool(
    name="firmsHotspotAnalysis",
    description=(
        "Analisis de densidad espacial de focos NASA FIRMS HISTORICOS (DBSCAN). "
        "Devuelve los clusters detectados en un rango de fechas (y bbox opcional) "
        "con centroide, conteo, FRP medio y maximo. Cobertura historico: "
        "mayo-agosto 2025. Util para 'donde se concentraron los focos en Galicia' "
        "o estudios retrospectivos."
    ),
    parameters=SCHEMA,
)
async def firms_hotspot_analysis(
    *,
    date_from: str,
    date_to: str,
    bbox: list[float] | None = None,
    sensor: str | None = None,
    eps_meters: int = 1500,
    min_points: int = 4,
    limit: int = 50,
) -> dict[str, Any]:
    from main import get_db_pool

    try:
        pool = get_db_pool()
    except RuntimeError as exc:
        return {"error": str(exc), "total_clusters": 0, "items": []}

    # eps en metros sobre geometry(4326) lo proyectamos a 3857 (mercator) para
    # que ST_ClusterDBSCAN reciba distancias coherentes con metros aproximados.
    # En latitudes medias de Espana el factor de distorsion es aceptable; no
    # buscamos precision topografica, solo agrupamiento orientativo.
    bbox_filter = ""
    bbox_params: list[Any] = []
    if bbox is not None:
        bbox_filter = (
            "AND fh.geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326) "
        )
        bbox_params = list(bbox)

    sensor_filter = ""
    sensor_params: list[Any] = []
    if sensor:
        sensor_filter = "AND fh.firms_source = %s "
        sensor_params = [sensor]

    sql = f"""
        WITH base AS (
            SELECT
                fh.hotspot_id,
                fh.frp,
                fh.firms_source,
                fh.acq_date,
                fh.geom,
                ST_Transform(fh.geom, 3857) AS geom3857
            FROM core.firms_hotspot fh
            WHERE fh.acq_date >= %s AND fh.acq_date <= %s
              {bbox_filter}
              {sensor_filter}
        ),
        clustered AS (
            SELECT
                hotspot_id, frp, firms_source, acq_date, geom,
                ST_ClusterDBSCAN(geom3857, eps := %s, minpoints := %s) OVER () AS cluster_id
            FROM base
        )
        SELECT
            cluster_id,
            COUNT(*) AS hotspot_count,
            ROUND(AVG(frp)::numeric, 2) AS avg_frp,
            ROUND(MAX(frp)::numeric, 2) AS max_frp,
            MIN(acq_date)::text AS first_date,
            MAX(acq_date)::text AS last_date,
            ST_X(ST_Centroid(ST_Collect(geom))) AS center_lon,
            ST_Y(ST_Centroid(ST_Collect(geom))) AS center_lat
        FROM clustered
        WHERE cluster_id IS NOT NULL
        GROUP BY cluster_id
        ORDER BY hotspot_count DESC
        LIMIT %s
    """
    params = [date_from, date_to] + bbox_params + sensor_params + [eps_meters, min_points, limit + 1]

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
    except Exception as exc:
        msg = str(exc).lower()
        if "st_clusterdbscan" in msg or "function" in msg:
            return {
                "error": (
                    "Esta instalacion de PostGIS no expone ST_ClusterDBSCAN; "
                    "se necesita PostGIS 3.1+."
                ),
                "total_clusters": 0,
                "items": [],
            }
        return {"error": f"Fallo de consulta SQL: {exc}", "total_clusters": 0, "items": []}

    truncated = len(rows) > limit
    rows = rows[:limit]

    items = [
        {
            "cluster_id": int(r[0]),
            "hotspot_count": int(r[1]),
            "avg_frp": float(r[2]) if r[2] is not None else None,
            "max_frp": float(r[3]) if r[3] is not None else None,
            "first_date": r[4],
            "last_date": r[5],
            "center_lon": float(r[6]),
            "center_lat": float(r[7]),
        }
        for r in rows
    ]

    return {
        "total_clusters": len(items) + (1 if truncated else 0),
        "returned": len(items),
        "truncated": truncated,
        "filters": {
            "date_from": date_from, "date_to": date_to,
            "bbox": bbox, "sensor": sensor,
            "eps_meters": eps_meters, "min_points": min_points,
        },
        "items": items,
    }
