"""Tool activeFiresNearPopulation: focos FIRMS activos cerca de nucleos.

Calcula distancia real en metros entre los puntos FIRMS en vivo y la capa
local `core.nucleos_poblacion_polygon` usando PostGIS (`ST_DWithin` sobre
geography). Complementa a `firesNearPopulation`, que opera solo sobre el
historico persistido en BD.
"""

from __future__ import annotations

from typing import Any

from chat.tools import server_tool


SCHEMA = {
    "type": "object",
    "properties": {
        "distance_m": {
            "type": "integer",
            "description": "Distancia maxima en metros entre foco activo y nucleo. Por defecto 2000.",
            "minimum": 100,
            "maximum": 50000,
            "default": 2000,
        },
        "population_max": {
            "type": "integer",
            "description": (
                "Umbral superior exclusivo de habitantes del nucleo. Para 'menos de "
                "5000 habitantes', usar 5000. Por defecto 5000."
            ),
            "minimum": 1,
            "maximum": 500000,
            "default": 5000,
        },
        "sensor": {
            "type": "string",
            "enum": ["VIIRS_NOAA20_SP", "VIIRS_NOAA21_SP", "VIIRS_SNPP_SP", "MODIS_SP"],
            "description": "Filtro opcional por sensor FIRMS normalizado del visor.",
        },
        "bbox": {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 4,
            "maxItems": 4,
            "description": "Filtro geografico [min_lon, min_lat, max_lon, max_lat] WGS84.",
        },
        "min_frp": {
            "type": "number",
            "description": "FRP minimo (MW) para incluir el foco activo. Omitir = sin minimo.",
            "minimum": 0,
        },
        "confidence": {
            "type": "string",
            "enum": ["alta", "nominal", "baja"],
            "description": "Restringe por confianza del foco activo si se indica.",
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 200,
            "default": 50,
            "description": "Maximo de pares foco-nucleo devueltos.",
        },
    },
    "additionalProperties": False,
}


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _in_bbox(lon: float, lat: float, bbox: list[float]) -> bool:
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def _normalise_fire(raw: dict[str, Any]) -> dict[str, Any] | None:
    lat = _as_float(raw.get("latitude"))
    lon = _as_float(raw.get("longitude"))
    if lat is None or lon is None:
        return None

    frp = _as_float(raw.get("frp"))
    fire_id = raw.get("id")
    if not fire_id:
        fire_id = f"{raw.get('firms_source') or 'FIRMS'}:{lat:.5f}:{lon:.5f}:{raw.get('acq_date') or ''}:{raw.get('acq_time') or ''}"

    return {
        "fire_id": str(fire_id),
        "sensor": raw.get("firms_source"),
        "latitude": lat,
        "longitude": lon,
        "frp": frp,
        "confidence_label": raw.get("confidence_label"),
        "acq_date": raw.get("acq_date"),
        "acq_time": raw.get("acq_time"),
        "satellite": raw.get("satellite"),
        "intensity_label": raw.get("intensity_label"),
    }


def _filter_fires(
    fires: list[dict[str, Any]],
    *,
    sensor: str | None,
    bbox: list[float] | None,
    min_frp: float | None,
    confidence: str | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in fires:
        fire = _normalise_fire(raw)
        if fire is None:
            continue
        if sensor and fire["sensor"] != sensor:
            continue
        if bbox is not None and not _in_bbox(fire["longitude"], fire["latitude"], bbox):
            continue
        if min_frp is not None and (fire["frp"] is None or fire["frp"] < min_frp):
            continue
        if confidence and fire["confidence_label"] != confidence:
            continue
        out.append(fire)
    return out


def _build_map_payload(items: list[dict[str, Any]]) -> tuple[dict[str, Any], list[float] | None]:
    features: list[dict[str, Any]] = []
    coords_for_bbox: list[tuple[float, float]] = []

    for item in items:
        fire_lon = item["fire_longitude"]
        fire_lat = item["fire_latitude"]
        nucleo_lon = item["nucleo_lon"]
        nucleo_lat = item["nucleo_lat"]
        coords_for_bbox.extend([(fire_lon, fire_lat), (nucleo_lon, nucleo_lat)])

        label = f"{item['nucleo_nombre']} ({item['nucleo_habitantes']} hab.) a {item['distance_m']} m"
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[fire_lon, fire_lat], [nucleo_lon, nucleo_lat]]},
            "properties": {
                "kind": "distance",
                "label": label,
                "distance_m": item["distance_m"],
            },
        })
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [fire_lon, fire_lat]},
            "properties": {
                "kind": "fire",
                "label": f"Foco activo {item['fire_id']} · FRP {item['frp']} MW",
                "fire_id": item["fire_id"],
            },
        })
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [nucleo_lon, nucleo_lat]},
            "properties": {
                "kind": "population",
                "label": f"{item['nucleo_nombre']} · {item['nucleo_habitantes']} hab.",
                "nucleo_id": item["nucleo_id"],
            },
        })

    bbox = None
    if coords_for_bbox:
        lons = [p[0] for p in coords_for_bbox]
        lats = [p[1] for p in coords_for_bbox]
        pad = 0.03
        bbox = [min(lons) - pad, min(lats) - pad, max(lons) + pad, max(lats) + pad]

    return {"type": "FeatureCollection", "features": features}, bbox


@server_tool(
    name="activeFiresNearPopulation",
    description=(
        "Calcula que focos NASA FIRMS activos estan a menos de N metros de un "
        "nucleo de poblacion del IGN por debajo de un umbral de habitantes. "
        "Usa ST_DWithin/ST_Distance sobre geography en PostGIS, con los focos "
        "en vivo del visor como puntos temporales. Util para preguntas como "
        "'hay algun nucleo de menos de 5000 habitantes a menos de 2 km de un "
        "foco activo'. Devuelve items y un map_geojson para pintarlo con "
        "showGeoJsonResults."
    ),
    parameters=SCHEMA,
)
async def active_fires_near_population(
    *,
    distance_m: int = 2000,
    population_max: int = 5000,
    sensor: str | None = None,
    bbox: list[float] | None = None,
    min_frp: float | None = None,
    confidence: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    from main import fetch_spain_hotspots, get_db_pool

    fires = _filter_fires(
        await fetch_spain_hotspots(),
        sensor=sensor,
        bbox=bbox,
        min_frp=min_frp,
        confidence=confidence,
    )

    if not fires:
        return {
            "total_matched": 0,
            "active_fire_candidates": 0,
            "returned": 0,
            "truncated": False,
            "filters": {
                "distance_m": distance_m,
                "population_max": population_max,
                "sensor": sensor,
                "bbox": bbox,
                "min_frp": min_frp,
                "confidence": confidence,
            },
            "items": [],
            "map_layers": ["fires", "nucleos"],
            "map_geojson": {"type": "FeatureCollection", "features": []},
            "map_bbox": None,
        }

    try:
        pool = get_db_pool()
    except RuntimeError as exc:
        return {"error": str(exc), "total_matched": 0, "items": []}

    row_sql = (
        "(%s::text, %s::text, %s::double precision, %s::double precision, "
        "%s::double precision, %s::text, %s::text, %s::text, %s::text, %s::text)"
    )
    values_sql = ", ".join(row_sql for _ in fires)
    params: list[Any] = []
    for fire in fires:
        params.extend([
            fire["fire_id"],
            fire["sensor"],
            fire["latitude"],
            fire["longitude"],
            fire["frp"],
            fire["confidence_label"],
            fire["acq_date"],
            fire["acq_time"],
            fire["satellite"],
            fire["intensity_label"],
        ])

    deg_margin = (float(distance_m) / 111_000.0) * 1.2
    params.extend([population_max, deg_margin, distance_m, limit + 1])

    sql = f"""
        WITH live_fire(
            fire_id, sensor, latitude, longitude, frp, confidence_label,
            acq_date, acq_time, satellite, intensity_label
        ) AS (
            VALUES {values_sql}
        ),
        fire_geom AS (
            SELECT
                fire_id, sensor, latitude, longitude, frp, confidence_label,
                acq_date, acq_time, satellite, intensity_label,
                ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) AS geom
            FROM live_fire
        )
        SELECT
            f.fire_id,
            f.sensor,
            f.acq_date,
            f.acq_time,
            f.satellite,
            f.frp,
            f.confidence_label,
            f.intensity_label,
            f.latitude,
            f.longitude,
            n.core_feature_id::text,
            n.nombre,
            n.habitantes,
            ST_X(ST_Centroid(n.geom)) AS nucleo_lon,
            ST_Y(ST_Centroid(n.geom)) AS nucleo_lat,
            ST_Distance(f.geom::geography, n.geom::geography) AS distance_m
        FROM fire_geom f
        JOIN LATERAL (
            SELECT core_feature_id, nombre, habitantes, geom
            FROM core.nucleos_poblacion_polygon
            WHERE habitantes IS NOT NULL
              AND habitantes > 0
              AND habitantes < %s
              AND geom && ST_Expand(f.geom, %s)
              AND ST_DWithin(f.geom::geography, geom::geography, %s)
            ORDER BY f.geom <-> geom
            LIMIT 1
        ) n ON true
        ORDER BY distance_m ASC, f.frp DESC NULLS LAST
        LIMIT %s
    """

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
            "acq_time": r[3],
            "satellite": r[4],
            "frp": float(r[5]) if r[5] is not None else None,
            "confidence_label": r[6],
            "intensity_label": r[7],
            "fire_latitude": float(r[8]),
            "fire_longitude": float(r[9]),
            "nucleo_id": r[10],
            "nucleo_nombre": r[11],
            "nucleo_habitantes": r[12],
            "nucleo_lon": float(r[13]),
            "nucleo_lat": float(r[14]),
            "distance_m": round(float(r[15]), 1),
        }
        for r in rows
    ]
    map_geojson, map_bbox = _build_map_payload(items)

    return {
        "total_matched": len(items) + (1 if truncated else 0),
        "active_fire_candidates": len(fires),
        "returned": len(items),
        "truncated": truncated,
        "filters": {
            "distance_m": distance_m,
            "population_max": population_max,
            "sensor": sensor,
            "bbox": bbox,
            "min_frp": min_frp,
            "confidence": confidence,
        },
        "operation": "ST_DWithin(foco_activo::geography, nucleo.geom::geography)",
        "map_layers": ["fires", "nucleos"],
        "map_geojson": map_geojson,
        "map_bbox": map_bbox,
        "items": items,
    }
