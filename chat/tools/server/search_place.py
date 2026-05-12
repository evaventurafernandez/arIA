"""Tool searchPlace: resolver de toponimos de Espana (CCAA, provincias, municipios).

Delega en una implementacion de `PlaceResolver` (Strategy). Por defecto usa
`LocalPlaceResolver`, que busca primero en un fichero estatico de CCAA y
provincias y, si no hay match, intenta la tabla `core.nucleos_poblacion_polygon`
de PostGIS. Una futura implementacion Nominatim se enchufa sin tocar esta tool.
"""

from __future__ import annotations

from typing import Any

from chat.tools import server_tool
from chat.tools.server.place_resolver import get_place_resolver


SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "Toponimo a resolver (provincia, comunidad autonoma, municipio).",
        },
    },
    "required": ["name"],
    "additionalProperties": False,
}


@server_tool(
    name="searchPlace",
    description=(
        "Resolver de toponimos limitado a Espana. Devuelve el bbox del lugar en "
        "WGS84 ([min_lon, min_lat, max_lon, max_lat]) y su tipo (ccaa, "
        "provincia, municipio). Util como paso previo a flyTo cuando el usuario "
        "menciona una zona por nombre ('Galicia', 'Sevilla', 'Cuenca')."
    ),
    parameters=SCHEMA,
)
async def search_place(*, name: str) -> dict[str, Any]:
    result = await get_place_resolver().resolve(name)
    if result is None:
        return {
            "found": False,
            "query": name,
            "message": f"No se encontro un lugar con el nombre '{name}' en el resolver local.",
        }
    return {"found": True, "query": name, **result}
