"""Carga de tools server-side. Importar este modulo registra todas las tools en el registro central."""

from chat.tools.server import query_alerts  # noqa: F401
from chat.tools.server import query_fires  # noqa: F401
from chat.tools.server import query_burnt_area  # noqa: F401
