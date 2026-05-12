"""Tool queryAlerts: filtra `alerts_cache` (avisos AEMET vigentes) en memoria.

Se reutilizan los datos cargados por `fetch_aemet_alerts()` en el lifespan de
`main.py`. El filtrado se hace aqui (en memoria) porque el endpoint
`/api/alerts` original no acepta parametros y simplemente devuelve la lista.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from chat.tools import server_tool


SCHEMA = {
    "type": "object",
    "properties": {
        "phenomenon": {
            "type": "string",
            "description": (
                "Texto descriptivo del fenomeno a filtrar (busqueda por substring "
                "case-insensitive sobre el campo 'event' del aviso). Ejemplos: "
                "'temperatura', 'viento', 'precipitaciones', 'tormentas', 'nieve'. "
                "Omitir para no filtrar por fenomeno."
            ),
        },
        "level": {
            "type": "string",
            "enum": ["Verde", "Amarillo", "Naranja", "Rojo"],
            "description": "Nivel AEMET. Omitir para todos los niveles.",
        },
        "status": {
            "type": "string",
            "enum": ["vigente", "proximo", "expirado", "cualquiera"],
            "description": (
                "Estado de vigencia respecto al instante actual. 'vigente' = onset "
                "<= ahora <= expires; 'proximo' = aviso futuro; 'expirado' = ya "
                "termino. Por defecto 'vigente'."
            ),
            "default": "vigente",
        },
        "date_from": {
            "type": "string",
            "description": "Fecha ISO 8601 minima (inclusiva) que debe solapar con la vigencia del aviso. Opcional.",
        },
        "date_to": {
            "type": "string",
            "description": "Fecha ISO 8601 maxima (inclusiva) que debe solapar con la vigencia del aviso. Opcional.",
        },
        "limit": {
            "type": "integer",
            "description": "Maximo numero de avisos devueltos en 'items'. Por defecto 25.",
            "minimum": 1,
            "maximum": 200,
            "default": 25,
        },
    },
    "additionalProperties": False,
}


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00").split("+")[0])
    except ValueError:
        return None


def _matches(
    alert: dict[str, Any],
    *,
    phenomenon: str | None,
    level: str | None,
    status: str,
    date_from: datetime | None,
    date_to: datetime | None,
    now: datetime,
) -> bool:
    if phenomenon:
        if phenomenon.lower() not in (alert.get("event") or "").lower():
            return False
    if level and alert.get("level") != level:
        return False

    onset = _parse_iso(alert.get("onset"))
    expires = _parse_iso(alert.get("expires"))
    if onset is None or expires is None:
        # Si no podemos interpretar las fechas, solo dejamos pasar si el usuario
        # pidio 'cualquiera' (es decir, esta dispuesto a ver avisos sin fecha bien formada).
        return status == "cualquiera"

    if status == "vigente":
        if not (onset <= now <= expires):
            return False
    elif status == "proximo":
        if not (onset > now):
            return False
    elif status == "expirado":
        if not (expires < now):
            return False
    # 'cualquiera' no filtra por estado.

    # Solape con ventana [date_from, date_to] si se pidio.
    if date_from is not None and expires < date_from:
        return False
    if date_to is not None and onset > date_to:
        return False
    return True


@server_tool(
    name="queryAlerts",
    description=(
        "Consulta avisos AEMET (CAP) cargados en el visor. Permite filtrar por "
        "fenomeno (texto), nivel (Verde/Amarillo/Naranja/Rojo), estado de "
        "vigencia (vigente/proximo/expirado) y ventana temporal. Devuelve un "
        "resumen agregado y la lista de avisos coincidentes (truncada por 'limit'). "
        "Util para preguntas tipo 'que avisos de temperatura hay vigentes' o "
        "'avisos de viento nivel naranja la semana pasada'."
    ),
    parameters=SCHEMA,
)
async def query_alerts(
    *,
    phenomenon: str | None = None,
    level: str | None = None,
    status: str = "vigente",
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    # Import diferido para no acoplar al arranque de main.py.
    from main import alerts_cache

    now = datetime.now()
    date_from_dt = _parse_iso(date_from)
    date_to_dt = _parse_iso(date_to)

    matched = [
        a
        for a in alerts_cache
        if _matches(
            a,
            phenomenon=phenomenon,
            level=level,
            status=status,
            date_from=date_from_dt,
            date_to=date_to_dt,
            now=now,
        )
    ]

    by_level: dict[str, int] = {}
    by_phenomenon: dict[str, int] = {}
    for a in matched:
        by_level[a.get("level", "Desconocido")] = by_level.get(a.get("level", "Desconocido"), 0) + 1
        ev = a.get("event") or "Desconocido"
        by_phenomenon[ev] = by_phenomenon.get(ev, 0) + 1

    items = [
        {
            "id": a.get("id"),
            "event": a.get("event"),
            "level": a.get("level"),
            "area_name": a.get("area_name"),
            "onset": a.get("onset"),
            "expires": a.get("expires"),
        }
        for a in matched[:limit]
    ]

    return {
        "total_matched": len(matched),
        "returned": len(items),
        "truncated": len(matched) > len(items),
        "filters": {
            "phenomenon": phenomenon,
            "level": level,
            "status": status,
            "date_from": date_from,
            "date_to": date_to,
        },
        "summary_by_level": by_level,
        "summary_by_phenomenon": by_phenomenon,
        "items": items,
    }
