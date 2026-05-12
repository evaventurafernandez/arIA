"""Tool landcoverAtPoint: clase CORINE en una coordenada via WMS IGN GetFeatureInfo.

Reutiliza `fetch_landcover_features_by_point` de `main.py`, que ya consume
el WMS oficial del IGN. Esta es la misma fuente que el visor usa para los
clicks puntuales en CORINE: garantiza coherencia visual con la capa.
"""

from __future__ import annotations

from typing import Any

from chat.tools import server_tool


SCHEMA = {
    "type": "object",
    "properties": {
        "lon": {"type": "number", "minimum": -180, "maximum": 180, "description": "Longitud WGS84."},
        "lat": {"type": "number", "minimum": -90, "maximum": 90, "description": "Latitud WGS84."},
    },
    "required": ["lon", "lat"],
    "additionalProperties": False,
}


def _build_synthetic_query(lon: float, lat: float) -> dict[str, Any]:
    """Sintetiza un viewport WMS 1.3.0 + EPSG:4326 centrado en (lon, lat).

    En WMS 1.3.0 con CRS geografico (EPSG:4326) el orden del bbox es
    lat/lon (south, west, north, east), NO lon/lat. El visor lo construye
    asi (frontend `buildWmsBbox`); mantenemos el mismo formato para que el
    IGN devuelva la misma clase que el usuario veria al hacer click.

    Se usa un viewport de 21x21 pixeles con margen de 0.001 grados
    (aprox. 100 m) alrededor del punto. El pixel central (10, 10) cae
    exactamente sobre la coordenada solicitada.
    """
    delta = 0.001
    bbox_latlon = f"{lat - delta},{lon - delta},{lat + delta},{lon + delta}"
    return {
        "bbox": bbox_latlon,
        "width": 21,
        "height": 21,
        "i": 10,
        "j": 10,
        "crs": "EPSG:4326",
    }


@server_tool(
    name="landcoverAtPoint",
    description=(
        "Devuelve la clase de ocupacion del suelo CORINE 2018 en una coordenada "
        "(WGS84). Util para 'que uso del suelo hay en el punto X' o como "
        "contexto al inspeccionar un foco. La fuente es el WMS oficial del IGN, "
        "la misma que la ficha del foco en el visor."
    ),
    parameters=SCHEMA,
)
async def landcover_at_point(*, lon: float, lat: float) -> dict[str, Any]:
    from main import fetch_landcover_features_by_point

    query = _build_synthetic_query(lon, lat)
    try:
        raw = fetch_landcover_features_by_point(lon=lon, lat=lat, **query)
    except Exception as exc:
        return {
            "found": False,
            "lon": lon, "lat": lat,
            "error": f"Fallo al consultar el WMS del IGN: {exc}",
        }

    features = raw.get("features") or []
    if not features:
        return {
            "found": False,
            "lon": lon, "lat": lat,
            "message": "El IGN no devolvio clase CORINE en esta coordenada.",
            "source": raw.get("metadata", {}).get("source"),
        }

    # `normalize_landcover_wms_feature` (main.py) entrega `label`, `code`,
    # `code_field`, `source_dataset` y otras. NO existen 'class_label' ni
    # 'class_code'; usar los nombres correctos para no devolver None.
    props = (features[0] or {}).get("properties") or {}
    return {
        "found": True,
        "lon": lon, "lat": lat,
        "label": props.get("label"),
        "code": props.get("code"),
        "code_field": props.get("code_field"),
        "secondary_label": props.get("secondary_label"),
        "source_dataset": props.get("source_dataset"),
        "source_date": props.get("source_date"),
        "surface_ha": props.get("surface_ha"),
        "source": raw.get("metadata", {}).get("source"),
    }
