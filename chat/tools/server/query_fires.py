"""Tool queryFires: focos NASA FIRMS activos (datos en vivo).

Reutiliza `fetch_spain_hotspots()` de `main.py` que consulta la API de FIRMS
en cada llamada (no hay cache persistente; ya viene filtrado a Espana y a
confianza nominal/alta). Sobre la lista devuelta se aplican filtros
in-memory por sensor, bbox y FRP minimo.
"""

from __future__ import annotations

from typing import Any

from chat.tools import server_tool


SCHEMA = {
    "type": "object",
    "properties": {
        "sensor": {
            "type": "string",
            "enum": ["VIIRS_NOAA20_SP", "VIIRS_NOAA21_SP", "VIIRS_SNPP_SP", "MODIS_SP"],
            "description": (
                "Identificador FIRMS del sensor. Omitir para todos los sensores "
                "activos del visor (VIIRS NOAA-20/21/SNPP por defecto)."
            ),
        },
        "bbox": {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 4,
            "maxItems": 4,
            "description": (
                "Filtro geografico [min_lon, min_lat, max_lon, max_lat] en grados "
                "WGS84. Si se omite no se filtra por bbox."
            ),
        },
        "min_frp": {
            "type": "number",
            "description": "FRP minimo (MW) para incluir el foco. Omitir = sin minimo.",
            "minimum": 0,
        },
        "confidence": {
            "type": "string",
            "enum": ["alta", "nominal", "baja"],
            "description": (
                "Nivel de confianza del foco segun FIRMS. Por defecto el visor ya "
                "filtra a nominal+alta; este parametro permite restringir mas."
            ),
        },
        "limit": {
            "type": "integer",
            "description": "Maximo numero de focos en 'items'. Por defecto 25.",
            "minimum": 1,
            "maximum": 200,
            "default": 25,
        },
    },
    "additionalProperties": False,
}


def _in_bbox(fire: dict[str, Any], bbox: list[float]) -> bool:
    try:
        lon = float(fire.get("longitude"))
        lat = float(fire.get("latitude"))
    except (TypeError, ValueError):
        return False
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


@server_tool(
    name="queryFires",
    description=(
        "Consulta focos de calor NASA FIRMS activos en Espana en este momento, "
        "agregados por sensores VIIRS NOAA-20, NOAA-21 y SNPP. Permite filtrar "
        "por sensor, bbox geografico, FRP minimo (proxy de intensidad) y nivel "
        "de confianza. La consulta es en vivo: cada invocacion contacta con "
        "FIRMS. Util para 'que focos hay ahora', 'foco mas intenso de hoy', etc."
    ),
    parameters=SCHEMA,
)
async def query_fires(
    *,
    sensor: str | None = None,
    bbox: list[float] | None = None,
    min_frp: float | None = None,
    confidence: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    from main import fetch_spain_hotspots

    fires = await fetch_spain_hotspots()

    def matches(f: dict[str, Any]) -> bool:
        if sensor and f.get("firms_source") != sensor:
            return False
        if bbox is not None and not _in_bbox(f, bbox):
            return False
        if min_frp is not None:
            try:
                if float(f.get("frp") or 0.0) < min_frp:
                    return False
            except (TypeError, ValueError):
                return False
        if confidence and f.get("confidence_label") != confidence:
            return False
        return True

    matched = [f for f in fires if matches(f)]
    matched.sort(key=lambda f: float(f.get("frp") or 0.0), reverse=True)

    by_sensor: dict[str, int] = {}
    for f in matched:
        s = f.get("firms_source") or "Desconocido"
        by_sensor[s] = by_sensor.get(s, 0) + 1

    items = [
        {
            "id": f.get("id"),
            "latitude": f.get("latitude"),
            "longitude": f.get("longitude"),
            "frp": f.get("frp"),
            "acq_date": f.get("acq_date"),
            "acq_time": f.get("acq_time"),
            "satellite": f.get("satellite"),
            "sensor": f.get("firms_source"),
            "confidence_label": f.get("confidence_label"),
            "intensity_label": f.get("intensity_label"),
        }
        for f in matched[:limit]
    ]

    max_frp = max((float(f.get("frp") or 0.0) for f in matched), default=0.0)
    return {
        "total_matched": len(matched),
        "returned": len(items),
        "truncated": len(matched) > len(items),
        "filters": {
            "sensor": sensor,
            "bbox": bbox,
            "min_frp": min_frp,
            "confidence": confidence,
        },
        "summary_by_sensor": by_sensor,
        "max_frp": max_frp,
        "items": items,
    }
