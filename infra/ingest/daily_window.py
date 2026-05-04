from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


DEFAULT_LOCAL_TIMEZONE = "Europe/Madrid"


def previous_local_date(timezone_name: str = DEFAULT_LOCAL_TIMEZONE) -> date:
    return datetime.now(ZoneInfo(timezone_name)).date() - timedelta(days=1)


def resolve_date_range(
    date_from_value: str | None,
    date_to_value: str | None,
    *,
    timezone_name: str = DEFAULT_LOCAL_TIMEZONE,
) -> tuple[date, date, bool]:
    if date_from_value is None and date_to_value is None:
        default_date = previous_local_date(timezone_name)
        return default_date, default_date, True

    if date_from_value is None or date_to_value is None:
        raise ValueError("Indica --date-from y --date-to juntos, o ninguno para procesar ayer.")

    date_from = date.fromisoformat(date_from_value)
    date_to = date.fromisoformat(date_to_value)
    if date_to < date_from:
        raise ValueError("date_to debe ser mayor o igual que date_from")
    return date_from, date_to, False
