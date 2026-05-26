"""Carga de tools server-side. Importar este modulo registra todas las tools en el registro central."""

from chat.tools.server import query_alerts  # noqa: F401
from chat.tools.server import query_fires  # noqa: F401
from chat.tools.server import query_burnt_area  # noqa: F401
from chat.tools.server import landcover_at_point  # noqa: F401
from chat.tools.server import fires_near_population  # noqa: F401
from chat.tools.server import active_fires_near_population  # noqa: F401
from chat.tools.server import firms_hotspot_analysis  # noqa: F401
from chat.tools.server import search_place  # noqa: F401
from chat.tools.server import summarize_situation  # noqa: F401
from chat.tools.server import explain_term  # noqa: F401
from chat.tools.server import query_aemet_max_temp_history  # noqa: F401
from chat.tools.server import aemet_warnings_near_population  # noqa: F401
from chat.tools.server import query_roads_near_point  # noqa: F401
