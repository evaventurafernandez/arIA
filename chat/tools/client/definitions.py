"""Schemas de las tools cliente: el backend NO las ejecuta, el frontend si.

El LLM las invoca como cualquier otra tool. El orquestador detecta que
son cliente, las acumula en `client_actions[]` de la respuesta, y al
LLM le devuelve `{"status":"queued","id":"ca-N"}` para que pueda seguir
razonando. El frontend Leaflet recibe la lista y la ejecuta sobre el
visor (mapa, capas, filtros).
"""

from __future__ import annotations

from chat.tools import client_tool


# Nombres de capa que el visor sabe activar/desactivar. Coinciden con los
# IDs de checkbox del sidebar (sin el prefijo `chk-`). Se omite cualquier
# capa EFFIS (efis_fires/effis_fwi/effis_dc) porque queda fuera de alcance.
LAYER_NAMES = [
    "alerts",
    "fires",
    "firms_history",
    "aemet_max_temp_history",
    "burnt_area",
    "nucleos",
    "flood",
    "corine_wms",
]

LEVEL_VALUES = ["Verde", "Amarillo", "Naranja", "Rojo"]


client_tool(
    name="flyTo",
    description=(
        "Centra/encuadra el mapa Leaflet en una zona. Se acepta bbox (formato "
        "[min_lon, min_lat, max_lon, max_lat] en grados WGS84), o coords "
        "(latitud, longitud y zoom opcional). Usar para preguntas tipo "
        "'centra el mapa en Galicia' o 'lleva el mapa al foco mas intenso'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "bbox": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 4,
                "maxItems": 4,
                "description": "[min_lon, min_lat, max_lon, max_lat] WGS84.",
            },
            "coords": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                    "zoom": {"type": "integer", "minimum": 4, "maximum": 18},
                },
                "required": ["lat", "lon"],
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    },
)


client_tool(
    name="toggleLayer",
    description=(
        "Activa o desactiva una capa del visor MeteoVisor. El nombre debe ser "
        "uno del catalogo cerrado. Equivale a hacer click en la casilla "
        "correspondiente del panel lateral. No incluye capas EFFIS (no "
        "disponibles)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "enum": LAYER_NAMES,
                "description": (
                    "Capa a alternar. Significado: 'alerts' = avisos AEMET activos; "
                    "'fires' = focos NASA FIRMS en vivo; 'firms_history' = historico "
                    "FIRMS; 'aemet_max_temp_history' = historico AEMET de temperaturas "
                    "maximas; 'burnt_area' = areas quemadas Burnt Area v4; 'nucleos' "
                    "= nucleos de poblacion IGN; 'flood' = peligro fluvial T=10; "
                    "'corine_wms' = uso del suelo CORINE."
                ),
            },
            "on": {
                "type": "boolean",
                "description": "true = activar, false = desactivar.",
            },
        },
        "required": ["name", "on"],
        "additionalProperties": False,
    },
)


client_tool(
    name="setFilter",
    description=(
        "Aplica un filtro existente del visor. 'level' acepta una lista con "
        "uno o varios niveles AEMET (Verde/Amarillo/Naranja/Rojo). 'event_type' "
        "acepta el texto exacto del fenomeno tal como aparece en el desplegable "
        "del visor, o 'all' para no filtrar."
    ),
    parameters={
        "type": "object",
        "properties": {
            "field": {
                "type": "string",
                "enum": ["level", "event_type"],
            },
            "value": {
                "description": (
                    "Para 'level': array con uno o varios de "
                    "['Verde','Amarillo','Naranja','Rojo']. Para 'event_type': "
                    "string."
                ),
            },
        },
        "required": ["field", "value"],
        "additionalProperties": False,
    },
)


client_tool(
    name="getFeatureDetail",
    description=(
        "Abre la ficha lateral y centra el mapa en una feature concreta del "
        "visor. En Fase 2 solo soporta avisos AEMET (layer='alerts') porque "
        "el visor ya tiene la funcion `zoomToAlert(id)` para resolver el "
        "centrado y el highlight. Para fires usar `flyTo` con coords."
    ),
    parameters={
        "type": "object",
        "properties": {
            "layer": {"type": "string", "enum": ["alerts"]},
            "id": {"type": "string", "description": "Identificador del aviso (campo id devuelto por queryAlerts)."},
        },
        "required": ["layer", "id"],
        "additionalProperties": False,
    },
)
