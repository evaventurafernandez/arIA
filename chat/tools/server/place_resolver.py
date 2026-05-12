"""Interfaz `PlaceResolver` y `LocalPlaceResolver` para la tool searchPlace.

`PlaceResolver` define el contrato (`resolve(name) -> dict | None`). La
implementacion por defecto, `LocalPlaceResolver`, busca primero en un fichero
estatico con bbox por comunidad autonoma y provincia, y como fallback contra
la tabla `core.nucleos_poblacion_polygon` de PostGIS.

Una futura `NominatimPlaceResolver` se enchufara aqui sin cambiar el
orquestador ni la tool, controlada por la variable de entorno PLACE_RESOLVER.
"""

from __future__ import annotations

import json
import unicodedata
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Any


PLACES_PATH = Path(__file__).resolve().parents[2] / "data" / "places.json"


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize_name(name: str) -> str:
    return _strip_accents((name or "").strip().lower())


@lru_cache(maxsize=1)
def _load_places() -> dict[str, dict[str, list[float]]]:
    with PLACES_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


class PlaceResolver(ABC):
    @abstractmethod
    async def resolve(self, name: str) -> dict[str, Any] | None: ...


class LocalPlaceResolver(PlaceResolver):
    """Resolver basado en fichero estatico + tabla de nucleos como fallback.

    Devuelve un dict con `name` (nombre canonico), `kind` (ccaa / provincia /
    municipio), `bbox` ([min_lon, min_lat, max_lon, max_lat]), `source`.
    """

    def __init__(self, *, use_db_fallback: bool = True) -> None:
        self.use_db_fallback = use_db_fallback

    async def resolve(self, name: str) -> dict[str, Any] | None:
        needle = normalize_name(name)
        if not needle:
            return None

        places = _load_places()

        # 1) CCAA: match exacto normalizado o substring sobre alias conocidos.
        for canonical, bbox in places.get("ccaa", {}).items():
            if normalize_name(canonical) == needle or needle in normalize_name(canonical):
                return {"name": canonical, "kind": "ccaa", "bbox": bbox, "source": "static_places"}

        # 2) Provincias: igual.
        for canonical, bbox in places.get("provincias", {}).items():
            if normalize_name(canonical) == needle or needle in normalize_name(canonical):
                return {"name": canonical, "kind": "provincia", "bbox": bbox, "source": "static_places"}

        # 3) Fallback PostGIS: busqueda en nucleos_poblacion por nombre.
        if self.use_db_fallback:
            row = await self._resolve_in_db(name)
            if row is not None:
                return row

        return None

    async def _resolve_in_db(self, name: str) -> dict[str, Any] | None:
        # Import diferido: la tool solo se ejecuta cuando main.py ya esta arriba.
        try:
            from main import get_db_pool
        except Exception:
            return None

        try:
            pool = get_db_pool()
        except RuntimeError:
            return None

        sql = (
            "SELECT nombre, ST_XMin(env), ST_YMin(env), ST_XMax(env), ST_YMax(env), habitantes "
            "FROM (SELECT nombre, habitantes, ST_Envelope(geom) AS env "
            "      FROM core.nucleos_poblacion_polygon "
            "      WHERE nombre ILIKE %s "
            "      ORDER BY habitantes DESC NULLS LAST LIMIT 1) t"
        )
        params = (f"%{name}%",)
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    row = cur.fetchone()
        except Exception:
            return None

        if not row:
            return None
        return {
            "name": row[0],
            "kind": "municipio",
            "bbox": [float(row[1]), float(row[2]), float(row[3]), float(row[4])],
            "source": "core.nucleos_poblacion_polygon",
            "habitantes": row[5],
        }


_RESOLVER: PlaceResolver | None = None


def get_place_resolver() -> PlaceResolver:
    """Devuelve el resolver activo. Cacheado por proceso."""
    global _RESOLVER
    if _RESOLVER is None:
        _RESOLVER = LocalPlaceResolver()
    return _RESOLVER


def set_place_resolver(resolver: PlaceResolver | None) -> None:
    """Setter para tests: permite inyectar un mock o None para reset."""
    global _RESOLVER
    _RESOLVER = resolver
