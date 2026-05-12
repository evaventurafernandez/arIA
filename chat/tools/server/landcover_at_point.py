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


@server_tool(
    name="landcoverAtPoint",
    description=(
        "Devuelve la clase de ocupacion del suelo CORINE 2018 en una coordenada "
        "(WGS84). Util para 'que uso del suelo hay en el punto X' o como "
        "contexto al inspeccionar un foco. La fuente es el WMS oficial del IGN."
    ),
    parameters=SCHEMA,
)
async def landcover_at_point(*, lon: float, lat: float) -> dict[str, Any]:
    from main import fetch_landcover_features_by_point

    # Construimos un bbox sintetico minimo alrededor del punto y consultamos el
    # pixel central. El WMS necesita bbox/width/height/i/j; aqui sintetizamos
    # un viewport de 2x2 pixeles centrado en (lon, lat) con un margen de 0.001
    # grados (~100 m). Eso basta para que GetFeatureInfo localice la celda.
    delta = 0.001
    bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"
    raw = fetch_landcover_features_by_point(
        lon=lon, lat=lat,
        bbox=bbox, width=2, height=2, i=1, j=1, crs="EPSG:4326",
    )

    features = raw.get("features") or []
    if not features:
        return {
            "found": False,
            "lon": lon, "lat": lat,
            "message": "El IGN no devolvio clase CORINE en esta coordenada.",
            "source": raw.get("metadata", {}).get("source"),
        }

    props = (features[0] or {}).get("properties") or {}
    return {
        "found": True,
        "lon": lon, "lat": lat,
        "class_code": props.get("class_code"),
        "class_label": props.get("class_label"),
        "class_color": props.get("class_color"),
        "theme": props.get("theme"),
        "source": raw.get("metadata", {}).get("source"),
    }
