import csv
import base64
import gzip
import io
import json
import math
import os
import tarfile
import time
import zipfile
import xml.etree.ElementTree as ET
import asyncio
from contextlib import asynccontextmanager, redirect_stdout
from datetime import date, datetime, timezone
from email.utils import format_datetime
from functools import lru_cache
from pathlib import Path
 
import generar_effis_wfs
import httpx
from PIL import Image
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic_settings import BaseSettings
from pyproj import Transformer
from psycopg_pool import ConnectionPool
from shapely.geometry import Point, shape
from shapely.ops import transform, unary_union


# Claves 
class Settings(BaseSettings):
    aemet_api_key: str = ""
    firms_map_key: str = ""
    firms_include_modis: bool = False
    firms_historical_default_date_from: str = "2025-05-01"
    firms_historical_default_date_to: str = "2025-08-31"
    aemet_warnings_default_date_from: str = "2025-05-01"
    aemet_warnings_default_date_to: str = "2025-08-31"
    effis_auto_refresh: bool = True
    effis_refresh_timeout: float = 30.0
    effis_refresh_retries: int = 3
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "meteovisor"
    postgres_user: str = "meteovisor"
    postgres_password: str = "meteovisor"
    burnt_area_catalog_zip: str = ""
    burnt_area_catalog_root: str = "data/copernicus/data_burnt_areas"
    burnt_area_tiles_root: str = "data/copernicus/burnt_area/tiles"
    burnt_area_default_date_from: str = "2025-05-01"
    burnt_area_default_date_to: str = "2025-08-31"
    cdse_username: str = ""
    cdse_password: str = ""
    cdse_access_token: str = ""
    cdse_s3_access_key: str = ""
    cdse_s3_secret_key: str = ""
    cdse_s3_endpoint: str = "eodata.dataspace.copernicus.eu"
    class Config:
        env_file = ".env"

settings = Settings()


# Cache en memoria 
alerts_cache:     list[dict] = []
fires_cache:      list[dict] = []
db_pool: ConnectionPool | None = None
landcover_class_tile_source_available = False

LANDCOVER_TILE_OVERVIEW_MAX_ZOOM = 8
LANDCOVER_LAYER_METADATA_CACHE_TTL_SECONDS = 300.0

landcover_publication_cache_info = {
    "feature_count": 0,
    "refreshed_at": None,
}
landcover_layer_metadata_cache = {
    "value": None,
    "expires_at": 0.0,
}

EFFIS_WMTS_BASE = "https://maps.effis.emergency.copernicus.eu/gwist/wmts"
EFFIS_WMS_BASE = "https://maps.effis.emergency.copernicus.eu/effis"
EFFIS_WMTS_LAYERS = {"viirs.hs.today"}
EFFIS_LOCAL_FIRES_PATH = "data/copernicus/fires/effis_viirs_hs_today_wfs.geojson"
SPAIN_BOUNDARY_PATH = "data/boundaries/spain_nuts_2024_01m.geojson"
LANDCOVER_WMS_URL = "https://servicios.idee.es/wms-inspire/ocupacion-suelo"
LANDCOVER_WMS_LAYER = "LC.LandCoverSurfaces"
LANDCOVER_WMS_INFO_FORMAT = "application/json"
LANDCOVER_AREA_CRS = "EPSG:3035"
BURNT_AREA_LAYER_ID = "burnt_area_daily"
BURNT_AREA_LAYER_NAME = "Areas quemadas diarias Copernicus CLMS"
BURNT_AREA_SUPPORTED_VERSIONS = ("v4", "v3")
BURNT_AREA_SUPPORTED_FORMATS = ("cog", "nc")
BURNT_AREA_PREFERRED_VERSION = "v4"
BURNT_AREA_PREFERRED_FORMAT = "cog"
BURNT_AREA_DEFAULT_DATE_FROM = settings.burnt_area_default_date_from
BURNT_AREA_DEFAULT_DATE_TO = settings.burnt_area_default_date_to
FIRMS_HISTORICAL_LAYER_ID = "firms_hotspot_historical"
FIRMS_HISTORICAL_LAYER_NAME = "Focos históricos NASA FIRMS"
FIRMS_HISTORICAL_DATASET_TYPE = "SP"
FIRMS_HISTORICAL_SOURCES = ("VIIRS_NOAA20_SP", "VIIRS_SNPP_SP")
FIRMS_HISTORICAL_BBOX_REGIONS = ("peninsula_baleares", "canarias", "ceuta_melilla")
FIRMS_HISTORICAL_DEFAULT_DATE_FROM = settings.firms_historical_default_date_from
FIRMS_HISTORICAL_DEFAULT_DATE_TO = settings.firms_historical_default_date_to
FIRMS_HISTORICAL_FEATURE_LIMIT_DEFAULT = 5000
FIRMS_HISTORICAL_FEATURE_LIMIT_MAX = 20000
AEMET_MAX_TEMPERATURE_LAYER_ID = "aemet_max_temperature_warnings"
AEMET_MAX_TEMPERATURE_DATASET_ID = "aemet_max_temperature_warning_historical"
AEMET_MAX_TEMPERATURE_LAYER_NAME = "Avisos AEMET históricos de temperaturas máximas"
AEMET_MAX_TEMPERATURE_DEFAULT_DATE_FROM = settings.aemet_warnings_default_date_from
AEMET_MAX_TEMPERATURE_DEFAULT_DATE_TO = settings.aemet_warnings_default_date_to
AEMET_MAX_TEMPERATURE_FEATURE_LIMIT_DEFAULT = 2000
AEMET_MAX_TEMPERATURE_FEATURE_LIMIT_MAX = 10000
AEMET_MAX_TEMPERATURE_MVT_LAYER_NAME = "aemet_max_temp"
BURNT_AREA_TILE_MIN_ZOOM = 4
BURNT_AREA_TILE_MAX_ZOOM = 10
BURNT_AREA_CATALOG_ENTRY_PATHS = {
    ("v3", "cog"): "bio-geophysical/burnt_area/ba_global_300m_daily_v3/cog.csv",
    ("v3", "nc"): "bio-geophysical/burnt_area/ba_global_300m_daily_v3/nc.csv",
    ("v4", "cog"): "bio-geophysical/burnt_area/ba_global_300m_daily_v4/cog.csv",
    ("v4", "nc"): "bio-geophysical/burnt_area/ba_global_300m_daily_v4/nc.csv",
}
BURNT_AREA_CATALOG_DIR_ENTRY_PATHS = {
    ("v3", "cog"): ("ba_global_300m_daily_v3/cog.csv",),
    ("v3", "nc"): ("ba_global_300m_daily_v3/nc.csv",),
    ("v4", "cog"): ("ba_global_300m_daily_v4/cog.csv",),
    ("v4", "nc"): ("ba_global_300m_daily_v4/nc.csv",),
}
BURNT_AREA_TRANSPARENT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg=="
)


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def candidate_burnt_area_catalog_zip_paths() -> list[Path]:
    paths: list[Path] = []
    if settings.burnt_area_catalog_zip:
        paths.append(Path(settings.burnt_area_catalog_zip))
    root_dir = repo_root()
    paths.extend(
        [
            root_dir / "data-store/files/raw/copernicus/clms/all.zip",
            root_dir / "data-store/files/all.zip",
            Path.home() / "Downloads" / "all.zip",
        ]
    )
    return paths


def candidate_burnt_area_catalog_root_paths() -> list[Path]:
    paths: list[Path] = []
    if settings.burnt_area_catalog_root:
        paths.append(Path(settings.burnt_area_catalog_root))
    root_dir = repo_root()
    paths.extend(
        [
            root_dir / "data/copernicus/data_burnt_areas",
            root_dir / "data-store/files/raw/copernicus/clms",
        ]
    )
    return paths


def resolve_burnt_area_catalog_zip_path() -> Path | None:
    for path in candidate_burnt_area_catalog_zip_paths():
        if path.is_file():
            return path
    return None


def resolve_burnt_area_catalog_dir_entry_path(catalog_root: Path, dataset_version: str, delivery_format: str) -> Path | None:
    logical_entry_path = BURNT_AREA_CATALOG_ENTRY_PATHS[(dataset_version, delivery_format)]
    candidate_rel_paths = (logical_entry_path, *BURNT_AREA_CATALOG_DIR_ENTRY_PATHS[(dataset_version, delivery_format)])
    for rel_path in candidate_rel_paths:
        file_path = catalog_root / rel_path
        if file_path.is_file():
            return file_path
    return None


def resolve_burnt_area_catalog_root_path() -> Path | None:
    for path in candidate_burnt_area_catalog_root_paths():
        if not path.is_dir():
            continue
        if any(
            resolve_burnt_area_catalog_dir_entry_path(path, dataset_version, delivery_format) is not None
            for dataset_version in BURNT_AREA_SUPPORTED_VERSIONS
            for delivery_format in BURNT_AREA_SUPPORTED_FORMATS
        ):
            return path
    return None


def normalize_burnt_area_catalog_datetime(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.replace('""', '"').replace('"T"', "T").strip('"')
    if not cleaned:
        return None
    try:
        return datetime.fromisoformat(cleaned).astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def normalize_burnt_area_date(value: str) -> str:
    return value[:10]


def extract_burnt_area_product_version(product_name: str) -> str:
    for part in product_name.split("_"):
        if part.startswith("V"):
            return part
    return ""


def build_burnt_area_catalog_item(
    row: dict[str, str],
    dataset_version: str,
    delivery_format: str,
    entry_path: str,
) -> dict | None:
    nominal_date = normalize_burnt_area_date(row.get("nominaldate", ""))
    if not nominal_date:
        return None
    product_name = row.get("name", "")
    return {
        "dataset_version": dataset_version,
        "delivery_format": delivery_format,
        "catalog_entry_path": entry_path,
        "source_item_id": row.get("id", ""),
        "product_name": product_name,
        "product_version": extract_burnt_area_product_version(product_name),
        "content_length_bytes": int(row.get("contentlength", "0") or "0"),
        "nominal_date": nominal_date,
        "content_start_at": normalize_burnt_area_catalog_datetime(row.get("contentstartdate")),
        "content_end_at": normalize_burnt_area_catalog_datetime(row.get("contentdateend")),
        "catalog_ingested_at": normalize_burnt_area_catalog_datetime(row.get("ingestiondate")),
        "catalog_modified_at": normalize_burnt_area_catalog_datetime(row.get("modificationdate")),
        "checksum_algorithm": row.get("checksumalgorithm") or None,
        "checksum_value": row.get("checksumvalue") or None,
        "remote_uri": row.get("s3path", ""),
    }


@lru_cache(maxsize=4)
def load_burnt_area_catalog_snapshot(catalog_zip_path: str, mtime_ns: int, size_bytes: int) -> dict:
    del mtime_ns, size_bytes
    snapshot = {
        "catalog_source": "zip_catalog",
        "catalog_zip_path": catalog_zip_path,
        "catalog_root_path": None,
        "items": [],
        "items_by_version_format": {
            version: {delivery_format: [] for delivery_format in BURNT_AREA_SUPPORTED_FORMATS}
            for version in BURNT_AREA_SUPPORTED_VERSIONS
        },
    }
    with zipfile.ZipFile(catalog_zip_path) as archive:
        for (dataset_version, delivery_format), entry_path in BURNT_AREA_CATALOG_ENTRY_PATHS.items():
            with archive.open(entry_path) as raw_stream:
                reader = csv.DictReader(io.TextIOWrapper(raw_stream, encoding="utf-8"))
                rows = []
                for row in reader:
                    item = build_burnt_area_catalog_item(row, dataset_version, delivery_format, entry_path)
                    if item is None:
                        continue
                    rows.append(item)
                    snapshot["items"].append(item)
                rows.sort(key=lambda item: item["nominal_date"])
                snapshot["items_by_version_format"][dataset_version][delivery_format] = rows
    snapshot["items"].sort(
        key=lambda item: (item["dataset_version"], item["delivery_format"], item["nominal_date"])
    )
    return snapshot


@lru_cache(maxsize=4)
def load_burnt_area_catalog_snapshot_from_dir(
    catalog_root_path: str,
    signature: tuple[tuple[str, int, int], ...],
) -> dict:
    del signature
    snapshot = {
        "catalog_source": "directory_catalog",
        "catalog_zip_path": None,
        "catalog_root_path": catalog_root_path,
        "items": [],
        "items_by_version_format": {
            version: {delivery_format: [] for delivery_format in BURNT_AREA_SUPPORTED_FORMATS}
            for version in BURNT_AREA_SUPPORTED_VERSIONS
        },
    }
    catalog_root = Path(catalog_root_path)
    for dataset_version in BURNT_AREA_SUPPORTED_VERSIONS:
        for delivery_format in BURNT_AREA_SUPPORTED_FORMATS:
            entry_path = BURNT_AREA_CATALOG_ENTRY_PATHS[(dataset_version, delivery_format)]
            csv_path = resolve_burnt_area_catalog_dir_entry_path(catalog_root, dataset_version, delivery_format)
            if csv_path is None:
                continue
            with csv_path.open(encoding="utf-8", newline="") as csv_stream:
                reader = csv.DictReader(csv_stream)
                rows = []
                for row in reader:
                    item = build_burnt_area_catalog_item(row, dataset_version, delivery_format, entry_path)
                    if item is None:
                        continue
                    rows.append(item)
                    snapshot["items"].append(item)
                rows.sort(key=lambda item: item["nominal_date"])
                snapshot["items_by_version_format"][dataset_version][delivery_format] = rows
    snapshot["items"].sort(
        key=lambda item: (item["dataset_version"], item["delivery_format"], item["nominal_date"])
    )
    return snapshot


def get_burnt_area_catalog_snapshot() -> dict | None:
    catalog_root = resolve_burnt_area_catalog_root_path()
    if catalog_root is not None:
        signature = []
        for dataset_version in BURNT_AREA_SUPPORTED_VERSIONS:
            for delivery_format in BURNT_AREA_SUPPORTED_FORMATS:
                csv_path = resolve_burnt_area_catalog_dir_entry_path(catalog_root, dataset_version, delivery_format)
                if csv_path is None:
                    continue
                stat = csv_path.stat()
                signature.append((str(csv_path.relative_to(catalog_root)), stat.st_mtime_ns, stat.st_size))
        return load_burnt_area_catalog_snapshot_from_dir(str(catalog_root), tuple(signature))

    catalog_zip = resolve_burnt_area_catalog_zip_path()
    if catalog_zip is None:
        return None
    stat = catalog_zip.stat()
    return load_burnt_area_catalog_snapshot(str(catalog_zip), stat.st_mtime_ns, stat.st_size)


def postgres_relation_exists(relation_name: str) -> bool:
    if db_pool is None:
        return False
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (relation_name,))
            row = cur.fetchone()
    return bool(row and row[0] is not None)


def resolve_local_burnt_area_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value)
    if path.is_absolute():
        return path
    return repo_root() / path


def local_burnt_area_path_exists(path_value: str | None) -> bool:
    path = resolve_local_burnt_area_path(path_value)
    return bool(path and path.exists())


def local_burnt_area_tiles_exist(path_value: str | None) -> bool:
    path = resolve_local_burnt_area_path(path_value)
    if path is None or not path.is_dir():
        return False
    return next(path.glob("*/*/*.png"), None) is not None


def query_burnt_area_core_rows() -> list[dict]:
    if not postgres_relation_exists("core.burnt_area_daily_file"):
        return []
    sql = """
    SELECT
        dataset_version,
        delivery_format,
        nominal_date::text,
        publication_status,
        local_file_path IS NOT NULL AS has_local_file,
        local_spain_cog_path IS NOT NULL AS has_local_spain_cog,
        local_tiles_path IS NOT NULL AS has_local_tiles,
        local_file_path,
        local_spain_cog_path,
        local_tiles_path
    FROM core.burnt_area_daily_file
    """
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return [
        {
            "dataset_version": row[0],
            "delivery_format": row[1],
            "nominal_date": row[2],
            "publication_status": row[3],
            "has_local_file": local_burnt_area_path_exists(row[7]),
            "has_local_spain_cog": local_burnt_area_path_exists(row[8]),
            "has_local_tiles": local_burnt_area_tiles_exist(row[9]),
            "local_file_path": row[7],
            "local_spain_cog_path": row[8],
            "local_tiles_path": row[9],
        }
        for row in rows
    ]


def build_burnt_area_publication_index() -> dict[tuple[str, str, str], dict]:
    index = {}
    for row in query_burnt_area_core_rows():
        key = (row["dataset_version"], row["delivery_format"], row["nominal_date"])
        index[key] = row
    return index


def merge_burnt_area_catalog_with_publication_state(
    items: list[dict],
    publication_index: dict[tuple[str, str, str], dict] | None = None,
) -> list[dict]:
    if publication_index is None:
        publication_index = build_burnt_area_publication_index()
    merged = []
    for item in items:
        publication = publication_index.get(
            (item["dataset_version"], item["delivery_format"], item["nominal_date"]),
            {},
        )
        merged.append(
            {
                **item,
                "publication_status": publication.get("publication_status", "cataloged"),
                "has_local_file": bool(publication.get("has_local_file", False)),
                "has_local_spain_cog": bool(publication.get("has_local_spain_cog", False)),
                "has_local_tiles": bool(publication.get("has_local_tiles", False)),
                "local_file_path": publication.get("local_file_path"),
                "local_spain_cog_path": publication.get("local_spain_cog_path"),
                "local_tiles_path": publication.get("local_tiles_path"),
            }
        )
    return merged


def query_burnt_area_stats_rows(
    dataset_version: str,
    delivery_format: str,
    date_from: str | None,
    date_to: str | None,
) -> list[dict]:
    if not postgres_relation_exists("pub.burnt_area_daily_stat"):
        return []
    where_clauses = ["dataset_version = %s", "delivery_format = %s", "stat_scope = 'country'"]
    params: list[object] = [dataset_version, delivery_format]
    if date_from:
        where_clauses.append("nominal_date >= %s")
        params.append(date_from)
    if date_to:
        where_clauses.append("nominal_date <= %s")
        params.append(date_to)
    sql = f"""
    SELECT
        nominal_date::text,
        area_code,
        area_label,
        burned_area_ha,
        burned_pixel_count,
        burned_fraction_sum,
        tiles_generated,
        stats_generated_at
    FROM pub.burnt_area_daily_stat
    WHERE {' AND '.join(where_clauses)}
    ORDER BY nominal_date
    """
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
    return [
        {
            "nominal_date": row[0],
            "area_code": row[1],
            "area_label": row[2],
            "burned_area_ha": float(row[3]) if row[3] is not None else None,
            "burned_pixel_count": int(row[4]) if row[4] is not None else None,
            "burned_fraction_sum": float(row[5]) if row[5] is not None else None,
            "tiles_generated": bool(row[6]),
            "stats_generated_at": row[7].isoformat() if row[7] is not None else None,
        }
        for row in rows
    ]


def filter_burnt_area_items(
    dataset_version: str,
    delivery_format: str,
    date_from: str | None = None,
    date_to: str | None = None,
    publication_index: dict[tuple[str, str, str], dict] | None = None,
) -> list[dict]:
    snapshot = get_burnt_area_catalog_snapshot()
    if snapshot is not None:
        rows = snapshot["items_by_version_format"].get(dataset_version, {}).get(delivery_format, [])
        rows = merge_burnt_area_catalog_with_publication_state(rows, publication_index)
    else:
        rows = [
            row
            for row in query_burnt_area_core_rows()
            if row["dataset_version"] == dataset_version and row["delivery_format"] == delivery_format
        ]
    return [
        row
        for row in rows
        if (date_from is None or row["nominal_date"] >= date_from)
        and (date_to is None or row["nominal_date"] <= date_to)
    ]


def build_burnt_area_layer_metadata() -> dict:
    publication_index = build_burnt_area_publication_index()
    summary = []
    published_dates = 0
    for dataset_version in BURNT_AREA_SUPPORTED_VERSIONS:
        for delivery_format in BURNT_AREA_SUPPORTED_FORMATS:
            items = filter_burnt_area_items(
                dataset_version,
                delivery_format,
                publication_index=publication_index,
            )
            available_dates = [item["nominal_date"] for item in items]
            published_date_count = sum(1 for item in items if item.get("has_local_tiles"))
            published_dates += published_date_count
            summary.append(
                {
                    "dataset_version": dataset_version,
                    "delivery_format": delivery_format,
                    "date_count": len(items),
                    "min_date": available_dates[0] if available_dates else None,
                    "max_date": available_dates[-1] if available_dates else None,
                    "published_date_count": published_date_count,
                }
            )

    preferred_items = filter_burnt_area_items(
        BURNT_AREA_PREFERRED_VERSION,
        BURNT_AREA_PREFERRED_FORMAT,
        publication_index=publication_index,
    )
    preferred_dates = [item["nominal_date"] for item in preferred_items]
    snapshot = get_burnt_area_catalog_snapshot()
    return {
        "layer_id": BURNT_AREA_LAYER_ID,
        "name": BURNT_AREA_LAYER_NAME,
        "description": (
            "Catalogo temporal diario de burnt area Copernicus CLMS preparado para publicacion "
            "raster local con barra temporal independiente."
        ),
        "catalog_source": snapshot.get("catalog_source") if snapshot is not None else "database_only",
        "catalog_zip_path": snapshot.get("catalog_zip_path") if snapshot is not None else None,
        "catalog_root_path": snapshot.get("catalog_root_path") if snapshot is not None else None,
        "preferred_version": BURNT_AREA_PREFERRED_VERSION,
        "preferred_format": BURNT_AREA_PREFERRED_FORMAT,
        "supported_versions": list(BURNT_AREA_SUPPORTED_VERSIONS),
        "supported_formats": list(BURNT_AREA_SUPPORTED_FORMATS),
        "available": bool(preferred_dates),
        "default_date_from": BURNT_AREA_DEFAULT_DATE_FROM,
        "default_date_to": BURNT_AREA_DEFAULT_DATE_TO,
        "min_date": preferred_dates[0] if preferred_dates else None,
        "max_date": preferred_dates[-1] if preferred_dates else None,
        "date_count": len(preferred_dates),
        "published_date_count": published_dates,
        "timeline_url": "/api/burnt-area/timeline",
        "stats_url": "/api/burnt-area/stats/daily",
        "tile_url_template": "/api/burnt-area/tiles/{version}/{date}/{z}/{x}/{y}.png",
        "publication_mode": "local_png_tiles",
        "tile_min_zoom": BURNT_AREA_TILE_MIN_ZOOM,
        "tile_max_zoom": BURNT_AREA_TILE_MAX_ZOOM,
        "tiles_root": settings.burnt_area_tiles_root,
        "variants": summary,
    }


def build_burnt_area_timeline_payload(
    dataset_version: str,
    delivery_format: str,
    date_from: str | None,
    date_to: str | None,
) -> dict:
    items = filter_burnt_area_items(dataset_version, delivery_format, date_from, date_to)
    stats_index = {
        row["nominal_date"]: row
        for row in query_burnt_area_stats_rows(dataset_version, delivery_format, date_from, date_to)
    }
    return {
        "layer_id": BURNT_AREA_LAYER_ID,
        "dataset_version": dataset_version,
        "delivery_format": delivery_format,
        "date_from": date_from,
        "date_to": date_to,
        "date_count": len(items),
        "dates": [
            {
                "date": item["nominal_date"],
                "publication_status": item.get("publication_status", "cataloged"),
                "has_local_file": bool(item.get("has_local_file", False)),
                "has_local_spain_cog": bool(item.get("has_local_spain_cog", False)),
                "has_local_tiles": bool(item.get("has_local_tiles", False)),
                "burned_area_ha": stats_index.get(item["nominal_date"], {}).get("burned_area_ha"),
                "burned_pixel_count": stats_index.get(item["nominal_date"], {}).get("burned_pixel_count"),
                "stats_generated_at": stats_index.get(item["nominal_date"], {}).get("stats_generated_at"),
            }
            for item in items
        ],
    }


def build_burnt_area_daily_stats_payload(
    dataset_version: str,
    delivery_format: str,
    date_from: str | None,
    date_to: str | None,
) -> dict:
    stats_rows = query_burnt_area_stats_rows(dataset_version, delivery_format, date_from, date_to)
    if stats_rows:
        return {
            "layer_id": BURNT_AREA_LAYER_ID,
            "dataset_version": dataset_version,
            "delivery_format": delivery_format,
            "date_from": date_from,
            "date_to": date_to,
            "stats_scope": "country",
            "items": stats_rows,
        }

    timeline = build_burnt_area_timeline_payload(dataset_version, delivery_format, date_from, date_to)
    return {
        "layer_id": BURNT_AREA_LAYER_ID,
        "dataset_version": dataset_version,
        "delivery_format": delivery_format,
        "date_from": date_from,
        "date_to": date_to,
        "stats_scope": "country",
        "items": [
            {
                "nominal_date": item["date"],
                "area_code": "ES",
                "area_label": "Espana",
                "burned_area_ha": None,
                "burned_pixel_count": None,
                "burned_fraction_sum": None,
                "tiles_generated": item["has_local_tiles"],
                "stats_generated_at": None,
            }
            for item in timeline["dates"]
        ],
    }


def query_firms_historical_stats_rows(
    date_from: str | None,
    date_to: str | None,
) -> list[dict]:
    if not postgres_relation_exists("pub.firms_hotspot_daily_stat"):
        return []
    base_where_clauses = [
        "dataset_type = %s",
        "stat_scope = 'country'",
        "area_code = 'ES'",
    ]
    base_params: list[object] = [FIRMS_HISTORICAL_DATASET_TYPE]
    if date_from:
        base_where_clauses.append("nominal_date >= %s")
        base_params.append(date_from)
    if date_to:
        base_where_clauses.append("nominal_date <= %s")
        base_params.append(date_to)

    sql = f"""
    SELECT
        nominal_date::text,
        coverage_expected_unit_count,
        coverage_unit_count,
        coverage_complete,
        hotspot_count,
        high_confidence_count,
        nominal_confidence_count,
        low_confidence_count,
        day_count,
        night_count,
        frp_sum_mw,
        frp_max_mw,
        source_count,
        source_list,
        bbox_region_list,
        stats_generated_at
    FROM pub.firms_hotspot_daily_stat
    WHERE {' AND '.join(base_where_clauses)}
    ORDER BY nominal_date
    """
    params = tuple(base_params)
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [
        {
            "nominal_date": row[0],
            "coverage_expected_unit_count": int(row[1]),
            "coverage_unit_count": int(row[2]),
            "coverage_complete": bool(row[3]),
            "hotspot_count": int(row[4]),
            "high_confidence_count": int(row[5]),
            "nominal_confidence_count": int(row[6]),
            "low_confidence_count": int(row[7]),
            "day_count": int(row[8]),
            "night_count": int(row[9]),
            "frp_sum_mw": float(row[10]) if row[10] is not None else 0.0,
            "frp_max_mw": float(row[11]) if row[11] is not None else None,
            "source_count": int(row[12]),
            "source_list": list(row[13] or []),
            "bbox_region_list": list(row[14] or []),
            "stats_generated_at": row[15].isoformat() if row[15] is not None else None,
        }
        for row in rows
    ]


def build_firms_historical_layer_metadata() -> dict:
    stats_rows = query_firms_historical_stats_rows(None, None)
    available_dates = [row["nominal_date"] for row in stats_rows]
    coverage_complete_date_count = sum(1 for row in stats_rows if row["coverage_complete"])
    return {
        "layer_id": FIRMS_HISTORICAL_LAYER_ID,
        "name": FIRMS_HISTORICAL_LAYER_NAME,
        "description": (
            "Histórico vectorial diario de focos NASA FIRMS persistido en PostGIS, "
            "con serie temporal país y consulta GeoJSON por fecha."
        ),
        "dataset_type": FIRMS_HISTORICAL_DATASET_TYPE,
        "supported_sources": list(FIRMS_HISTORICAL_SOURCES),
        "bbox_regions": list(FIRMS_HISTORICAL_BBOX_REGIONS),
        "available": bool(stats_rows),
        "default_date_from": FIRMS_HISTORICAL_DEFAULT_DATE_FROM,
        "default_date_to": FIRMS_HISTORICAL_DEFAULT_DATE_TO,
        "min_date": available_dates[0] if available_dates else None,
        "max_date": available_dates[-1] if available_dates else None,
        "date_count": len(available_dates),
        "coverage_complete_date_count": coverage_complete_date_count,
        "timeline_url": "/api/firms/history/timeline",
        "stats_url": "/api/firms/history/stats/daily",
        "features_url_template": "/api/firms/history/features?date={date}",
        "publication_mode": "postgres_geojson",
    }


def build_firms_historical_timeline_payload(
    date_from: str | None,
    date_to: str | None,
) -> dict:
    stats_rows = query_firms_historical_stats_rows(date_from, date_to)
    return {
        "layer_id": FIRMS_HISTORICAL_LAYER_ID,
        "dataset_type": FIRMS_HISTORICAL_DATASET_TYPE,
        "date_from": date_from,
        "date_to": date_to,
        "date_count": len(stats_rows),
        "dates": [
            {
                "date": row["nominal_date"],
                "coverage_expected_unit_count": row["coverage_expected_unit_count"],
                "coverage_unit_count": row["coverage_unit_count"],
                "coverage_complete": row["coverage_complete"],
                "hotspot_count": row["hotspot_count"],
                "high_confidence_count": row["high_confidence_count"],
                "nominal_confidence_count": row["nominal_confidence_count"],
                "low_confidence_count": row["low_confidence_count"],
                "frp_max_mw": row["frp_max_mw"],
                "stats_generated_at": row["stats_generated_at"],
            }
            for row in stats_rows
        ],
    }


def build_firms_historical_daily_stats_payload(
    date_from: str | None,
    date_to: str | None,
) -> dict:
    return {
        "layer_id": FIRMS_HISTORICAL_LAYER_ID,
        "dataset_type": FIRMS_HISTORICAL_DATASET_TYPE,
        "date_from": date_from,
        "date_to": date_to,
        "stats_scope": "country",
        "items": query_firms_historical_stats_rows(date_from, date_to),
    }


def query_firms_historical_feature_rows(
    nominal_date: str,
    firms_source: str | None,
    bbox_values: tuple[float, float, float, float] | None,
    limit: int,
) -> list[dict]:
    if not postgres_relation_exists("core.firms_hotspot"):
        return []
    where_clauses = [
        "fh.dataset_type = %s",
        "fh.acq_date = %s::date",
        "fh.confidence = ANY(%s)",
    ]
    params: list[object] = [
        FIRMS_HISTORICAL_DATASET_TYPE,
        nominal_date,
        sorted(FIRMS_ALLOWED_CONFIDENCE),
    ]
    if firms_source:
        where_clauses.append("fh.firms_source = %s")
        params.append(firms_source)
    if bbox_values is not None:
        minx, miny, maxx, maxy = bbox_values
        where_clauses.append("fh.geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)")
        where_clauses.append("ST_Intersects(fh.geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326))")
        params.extend([minx, miny, maxx, maxy, minx, miny, maxx, maxy])
    params.append(limit)
    sql = f"""
    SELECT
        fh.firms_source,
        fh.latitude,
        fh.longitude,
        fh.acq_date::text,
        fh.acq_time,
        fh.satellite,
        fh.confidence,
        fh.frp,
        fh.daynight,
        fh.observed_at,
        fh.bbox_regions
    FROM core.firms_hotspot fh
    WHERE {' AND '.join(where_clauses)}
    ORDER BY fh.observed_at DESC, fh.frp DESC NULLS LAST, fh.firms_source
    LIMIT %s
    """
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
    result = [
        {
            "firms_source": row[0],
            "latitude": float(row[1]),
            "longitude": float(row[2]),
            "acq_date": row[3],
            "acq_time": row[4],
            "satellite": row[5],
            "confidence": row[6],
            "frp": float(row[7]) if row[7] is not None else None,
            "daynight": row[8],
            "observed_at": row[9].isoformat() if row[9] is not None else None,
            "bbox_regions": list(row[10] or []),
        }
        for row in rows
    ]
    return result


def build_firms_historical_feature_collection(
    nominal_date: str,
    firms_source: str | None,
    bbox_values: tuple[float, float, float, float] | None,
    limit: int,
) -> dict:
    rows = query_firms_historical_feature_rows(nominal_date, firms_source, bbox_values, limit)
    features = []
    confidence_counts = {"h": 0, "n": 0, "l": 0}
    for row in rows:
        confidence_code = normalize_firms_confidence(row.get("confidence"))
        if confidence_code in confidence_counts:
            confidence_counts[confidence_code] += 1
        frp = float(row.get("frp") or 0.0)
        level, color = classify_frp(frp)
        lat = row["latitude"]
        lon = row["longitude"]
        acq_date = row["acq_date"]
        acq_time = row["acq_time"]
        satellite = row["satellite"]
        feature_id = f"{row['firms_source']}_{lat:.6f}_{lon:.6f}_{acq_date}_{acq_time}_{satellite}"
        features.append(
            {
                "type": "Feature",
                "id": feature_id,
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],
                },
                "properties": {
                    "id": feature_id,
                    "latitude": lat,
                    "longitude": lon,
                    "acq_date": acq_date,
                    "acq_time": acq_time,
                    "satellite": satellite,
                    "confidence": row["confidence"],
                    "confidence_code": confidence_code,
                    "confidence_label": firms_confidence_label(confidence_code),
                    "frp": row["frp"],
                    "daynight": row["daynight"],
                    "level": level,
                    "level_color": color,
                    "intensity_label": level,
                    "intensity_color": color,
                    "acq_datetime_utc": row["observed_at"] or _format_acq_datetime_utc(acq_date, acq_time),
                    "source": "firms_historical",
                    "dataset_type": FIRMS_HISTORICAL_DATASET_TYPE,
                    "firms_source": row["firms_source"],
                    "bbox_regions": row["bbox_regions"],
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "metadata": {
            "layer_id": FIRMS_HISTORICAL_LAYER_ID,
            "dataset_type": FIRMS_HISTORICAL_DATASET_TYPE,
            "nominal_date": nominal_date,
            "firms_source": firms_source,
            "bbox_filter": list(bbox_values) if bbox_values is not None else None,
            "limit": limit,
            "feature_count": len(features),
            "confidence_counts": confidence_counts,
        },
        "features": features,
    }


def query_aemet_max_temperature_stats_rows(
    date_from: str | None,
    date_to: str | None,
) -> list[dict]:
    if not postgres_relation_exists("pub.aemet_max_temperature_daily_stat"):
        return []
    where_clauses = [
        "dataset_id = %s",
        "stat_scope = 'country'",
        "area_code = 'ES'",
    ]
    params: list[object] = [AEMET_MAX_TEMPERATURE_DATASET_ID]
    if date_from:
        where_clauses.append("nominal_date >= %s")
        params.append(date_from)
    if date_to:
        where_clauses.append("nominal_date <= %s")
        params.append(date_to)

    sql = f"""
    SELECT
        nominal_date::text,
        coverage_expected_unit_count,
        coverage_unit_count,
        coverage_complete,
        feature_count,
        warning_count,
        green_count,
        yellow_count,
        orange_count,
        red_count,
        max_temperature_c,
        warned_area_count,
        source_feature_count,
        stats_generated_at
    FROM pub.aemet_max_temperature_daily_stat
    WHERE {' AND '.join(where_clauses)}
    ORDER BY nominal_date
    """
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
    return [
        {
            "nominal_date": row[0],
            "coverage_expected_unit_count": int(row[1]),
            "coverage_unit_count": int(row[2]),
            "coverage_complete": bool(row[3]),
            "feature_count": int(row[4]),
            "warning_count": int(row[5]),
            "green_count": int(row[6]),
            "yellow_count": int(row[7]),
            "orange_count": int(row[8]),
            "red_count": int(row[9]),
            "max_temperature_c": float(row[10]) if row[10] is not None else None,
            "warned_area_count": int(row[11]),
            "source_feature_count": int(row[12]),
            "stats_generated_at": row[13].isoformat() if row[13] is not None else None,
        }
        for row in rows
    ]


def build_aemet_max_temperature_layer_metadata() -> dict:
    stats_rows = query_aemet_max_temperature_stats_rows(None, None)
    available_dates = [row["nominal_date"] for row in stats_rows]
    warning_date_count = sum(1 for row in stats_rows if row["warning_count"] > 0)
    coverage_complete_date_count = sum(1 for row in stats_rows if row["coverage_complete"])
    feature_count = sum(int(row["warning_count"]) for row in stats_rows)
    return {
        "layer_id": AEMET_MAX_TEMPERATURE_LAYER_ID,
        "name": AEMET_MAX_TEMPERATURE_LAYER_NAME,
        "description": (
            "Histórico diario de avisos AEMET CAP filtrado al fenómeno "
            "AT;Temperaturas máximas, publicado como estadísticas, GeoJSON y MVT."
        ),
        "event_code": "AT;Temperaturas máximas",
        "parameter_code": "TA",
        "available": bool(stats_rows),
        "default_date_from": AEMET_MAX_TEMPERATURE_DEFAULT_DATE_FROM,
        "default_date_to": AEMET_MAX_TEMPERATURE_DEFAULT_DATE_TO,
        "min_date": available_dates[0] if available_dates else None,
        "max_date": available_dates[-1] if available_dates else None,
        "date_count": len(available_dates),
        "warning_date_count": warning_date_count,
        "coverage_complete_date_count": coverage_complete_date_count,
        "warning_area_day_count": feature_count,
        "timeline_url": "/api/aemet/max-temperature/timeline",
        "stats_url": "/api/aemet/max-temperature/stats/daily",
        "features_url_template": "/api/aemet/max-temperature/features?date={date}",
        "tile_url_template": "/api/aemet/max-temperature/tiles/{date}/{z}/{x}/{y}.mvt",
        "tile_layer_name": AEMET_MAX_TEMPERATURE_MVT_LAYER_NAME,
        "publication_mode": "postgres_mvt",
    }


def build_aemet_max_temperature_timeline_payload(
    date_from: str | None,
    date_to: str | None,
) -> dict:
    stats_rows = query_aemet_max_temperature_stats_rows(date_from, date_to)
    return {
        "layer_id": AEMET_MAX_TEMPERATURE_LAYER_ID,
        "event_code": "AT;Temperaturas máximas",
        "date_from": date_from,
        "date_to": date_to,
        "date_count": len(stats_rows),
        "dates": [
            {
                "date": row["nominal_date"],
                "coverage_expected_unit_count": row["coverage_expected_unit_count"],
                "coverage_unit_count": row["coverage_unit_count"],
                "coverage_complete": row["coverage_complete"],
                "feature_count": row["feature_count"],
                "warning_count": row["warning_count"],
                "green_count": row["green_count"],
                "yellow_count": row["yellow_count"],
                "orange_count": row["orange_count"],
                "red_count": row["red_count"],
                "max_temperature_c": row["max_temperature_c"],
                "warned_area_count": row["warned_area_count"],
                "stats_generated_at": row["stats_generated_at"],
            }
            for row in stats_rows
        ],
    }


def build_aemet_max_temperature_daily_stats_payload(
    date_from: str | None,
    date_to: str | None,
) -> dict:
    return {
        "layer_id": AEMET_MAX_TEMPERATURE_LAYER_ID,
        "event_code": "AT;Temperaturas máximas",
        "date_from": date_from,
        "date_to": date_to,
        "stats_scope": "country",
        "items": query_aemet_max_temperature_stats_rows(date_from, date_to),
    }


def query_aemet_max_temperature_feature_rows(
    nominal_date: str,
    warnings_only: bool,
    bbox_values: tuple[float, float, float, float] | None,
    limit: int,
) -> list[dict]:
    if not postgres_relation_exists("pub.aemet_max_temperature_daily_feature"):
        return []
    where_clauses = ["valid_date = %s::date"]
    params: list[object] = [nominal_date]
    if warnings_only:
        where_clauses.append("is_warning")
    if bbox_values is not None:
        minx, miny, maxx, maxy = bbox_values
        where_clauses.append("geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)")
        where_clauses.append("ST_Intersects(geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326))")
        params.extend([minx, miny, maxx, maxy, minx, miny, maxx, maxy])
    params.append(limit)
    sql = f"""
    SELECT
        feature_id,
        valid_date::text,
        cap_identifier,
        sent_at,
        onset_at,
        expires_at,
        level_label,
        level_color,
        level_rank,
        is_warning,
        event_code,
        phenomenon_label,
        parameter_value,
        temperature_max_c,
        probability,
        area_name,
        area_code,
        headline,
        description,
        source_version_count,
        ST_AsGeoJSON(geom)::json
    FROM pub.aemet_max_temperature_daily_feature
    WHERE {' AND '.join(where_clauses)}
    ORDER BY level_rank DESC, temperature_max_c DESC NULLS LAST, area_name
    LIMIT %s
    """
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
    return [
        {
            "feature_id": row[0],
            "valid_date": row[1],
            "cap_identifier": row[2],
            "sent_at": row[3].isoformat() if row[3] is not None else None,
            "onset_at": row[4].isoformat() if row[4] is not None else None,
            "expires_at": row[5].isoformat() if row[5] is not None else None,
            "level_label": row[6],
            "level_color": row[7],
            "level_rank": int(row[8]),
            "is_warning": bool(row[9]),
            "event_code": row[10],
            "phenomenon_label": row[11],
            "parameter_value": row[12],
            "temperature_max_c": float(row[13]) if row[13] is not None else None,
            "probability": row[14],
            "area_name": row[15],
            "area_code": row[16],
            "headline": row[17],
            "description": row[18],
            "source_version_count": int(row[19]),
            "geometry": row[20],
        }
        for row in rows
    ]


def build_aemet_max_temperature_feature_collection(
    nominal_date: str,
    warnings_only: bool,
    bbox_values: tuple[float, float, float, float] | None,
    limit: int,
) -> dict:
    rows = query_aemet_max_temperature_feature_rows(nominal_date, warnings_only, bbox_values, limit)
    features = [
        {
            "type": "Feature",
            "id": row["feature_id"],
            "geometry": row["geometry"],
            "properties": {
                key: value
                for key, value in row.items()
                if key not in {"geometry"}
            },
        }
        for row in rows
    ]
    return {
        "type": "FeatureCollection",
        "metadata": {
            "layer_id": AEMET_MAX_TEMPERATURE_LAYER_ID,
            "event_code": "AT;Temperaturas máximas",
            "nominal_date": nominal_date,
            "warnings_only": warnings_only,
            "bbox_filter": list(bbox_values) if bbox_values is not None else None,
            "limit": limit,
            "feature_count": len(features),
        },
        "features": features,
    }


def execute_aemet_max_temperature_mvt_query(sql: str, params: tuple[object, ...]) -> bytes:
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL max_parallel_workers_per_gather = 0")
            cur.execute(sql, params)
            row = cur.fetchone()
    if not row or row[0] is None:
        return b""
    return bytes(row[0])


def fetch_aemet_max_temperature_vector_tile(
    nominal_date: str,
    z: int,
    x: int,
    y: int,
    warnings_only: bool,
) -> bytes:
    if not postgres_relation_exists("pub.aemet_max_temperature_daily_feature"):
        return b""
    where_clauses = ["src.valid_date = %s::date"]
    params: list[object] = [z, x, y, nominal_date]
    if warnings_only:
        where_clauses.append("src.is_warning")
    sql = f"""
    WITH tile_envelope AS (
        SELECT ST_TileEnvelope(%s, %s, %s) AS geom
    ),
    candidate_geom AS (
        SELECT
            src.feature_id,
            src.valid_date::text AS valid_date,
            src.area_code,
            src.area_name,
            src.level_label,
            src.level_color,
            src.level_rank,
            src.is_warning,
            src.parameter_value,
            src.temperature_max_c,
            src.probability,
            src.onset_at,
            src.expires_at,
            src.sent_at,
            src.source_version_count,
            src.geom_webmercator
        FROM pub.aemet_max_temperature_daily_feature AS src
        CROSS JOIN tile_envelope AS env
        WHERE {' AND '.join(where_clauses)}
          AND src.geom_webmercator && env.geom
          AND ST_Intersects(src.geom_webmercator, env.geom)
    ),
    mvtgeom AS (
        SELECT
            src.feature_id,
            src.valid_date,
            src.area_code,
            src.area_name,
            src.level_label,
            src.level_color,
            src.level_rank,
            src.is_warning,
            src.parameter_value,
            src.temperature_max_c,
            src.probability,
            src.onset_at::text AS onset_at,
            src.expires_at::text AS expires_at,
            src.sent_at::text AS sent_at,
            src.source_version_count,
            ST_AsMVTGeom(src.geom_webmercator, env.geom, 4096, 64, true) AS geom
        FROM candidate_geom AS src
        CROSS JOIN tile_envelope AS env
    )
    SELECT ST_AsMVT(tile_rows, %s, 4096, 'geom')
    FROM (
        SELECT *
        FROM mvtgeom
        WHERE geom IS NOT NULL
    ) AS tile_rows
    """
    return execute_aemet_max_temperature_mvt_query(
        sql,
        tuple(params + [AEMET_MAX_TEMPERATURE_MVT_LAYER_NAME]),
    )


def build_aemet_max_temperature_tile_cache_headers() -> dict[str, str]:
    return {"Cache-Control": "public, max-age=86400"}


def validate_burnt_area_variant(dataset_version: str, delivery_format: str) -> None:
    if dataset_version not in BURNT_AREA_SUPPORTED_VERSIONS:
        raise HTTPException(status_code=400, detail="dataset_version no soportada")
    if delivery_format not in BURNT_AREA_SUPPORTED_FORMATS:
        raise HTTPException(status_code=400, detail="delivery_format no soportado")


def validate_burnt_area_date_string(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="La fecha debe tener formato YYYY-MM-DD") from exc


def validate_burnt_area_zoom_level(value: int) -> int:
    if value < BURNT_AREA_TILE_MIN_ZOOM or value > BURNT_AREA_TILE_MAX_ZOOM:
        raise HTTPException(
            status_code=400,
            detail=(
                f"El zoom debe estar entre {BURNT_AREA_TILE_MIN_ZOOM} "
                f"y {BURNT_AREA_TILE_MAX_ZOOM}"
            ),
        )
    return value


def resolve_burnt_area_tile_path(dataset_version: str, nominal_date: str, z: int, x: int, y: int) -> Path:
    return Path(settings.burnt_area_tiles_root) / dataset_version / nominal_date / str(z) / str(x) / f"{y}.png"


def resolve_burnt_area_tiles_zoom_dir(dataset_version: str, nominal_date: str, source_zoom: int) -> Path:
    return Path(settings.burnt_area_tiles_root) / dataset_version / nominal_date / str(source_zoom)


def slippy_tile_x_to_lon(tile_x: float, zoom: int) -> float:
    return tile_x / (2 ** zoom) * 360.0 - 180.0


def slippy_tile_y_to_lat(tile_y: float, zoom: int) -> float:
    mercator = math.pi * (1.0 - 2.0 * tile_y / (2 ** zoom))
    return math.degrees(math.atan(math.sinh(mercator)))


def build_burnt_area_locator_ring(
    tile_x: int,
    tile_y: int,
    zoom: int,
    pixel_y: int,
    pixel_x_start: int,
    pixel_x_end: int,
    tile_size: int,
) -> list[list[float]]:
    left = tile_x + (pixel_x_start / tile_size)
    right = tile_x + ((pixel_x_end + 1) / tile_size)
    top = tile_y + (pixel_y / tile_size)
    bottom = tile_y + ((pixel_y + 1) / tile_size)
    west = slippy_tile_x_to_lon(left, zoom)
    east = slippy_tile_x_to_lon(right, zoom)
    north = slippy_tile_y_to_lat(top, zoom)
    south = slippy_tile_y_to_lat(bottom, zoom)
    return [
        [west, south],
        [west, north],
        [east, north],
        [east, south],
        [west, south],
    ]


@lru_cache(maxsize=256)
def build_burnt_area_locator_geojson_cached(
    tiles_root: str,
    dataset_version: str,
    nominal_date: str,
    source_zoom: int,
) -> dict:
    zoom_dir = Path(tiles_root) / dataset_version / nominal_date / str(source_zoom)
    features = []
    total_pixels = 0
    total_runs = 0

    if zoom_dir.is_dir():
        for x_dir in sorted(path for path in zoom_dir.iterdir() if path.is_dir() and path.name.isdigit()):
            tile_x = int(x_dir.name)
            for tile_path in sorted(
                path
                for path in x_dir.iterdir()
                if path.is_file() and path.suffix.lower() == ".png" and path.stem.isdigit()
            ):
                tile_y = int(tile_path.stem)
                with Image.open(tile_path) as image:
                    rgba = image.convert("RGBA")
                    alpha = rgba.getchannel("A")
                    alpha_pixels = alpha.load()
                    tile_size = alpha.width
                    tile_polygons = []
                    tile_pixels = 0
                    tile_runs = 0

                    for pixel_y in range(alpha.height):
                        pixel_x = 0
                        while pixel_x < tile_size:
                            if alpha_pixels[pixel_x, pixel_y] <= 0:
                                pixel_x += 1
                                continue
                            pixel_x_start = pixel_x
                            while pixel_x + 1 < tile_size and alpha_pixels[pixel_x + 1, pixel_y] > 0:
                                pixel_x += 1
                            tile_polygons.append(
                                [
                                    build_burnt_area_locator_ring(
                                        tile_x,
                                        tile_y,
                                        source_zoom,
                                        pixel_y,
                                        pixel_x_start,
                                        pixel_x,
                                        tile_size,
                                    )
                                ]
                            )
                            run_pixels = pixel_x - pixel_x_start + 1
                            tile_pixels += run_pixels
                            tile_runs += 1
                            pixel_x += 1

                if not tile_polygons:
                    continue

                total_pixels += tile_pixels
                total_runs += tile_runs
                features.append(
                    {
                        "type": "Feature",
                        "properties": {
                            "dataset_version": dataset_version,
                            "nominal_date": nominal_date,
                            "source_zoom": source_zoom,
                            "tile_x": tile_x,
                            "tile_y": tile_y,
                            "run_count": tile_runs,
                            "pixel_count": tile_pixels,
                        },
                        "geometry": {
                            "type": "MultiPolygon",
                            "coordinates": tile_polygons,
                        },
                    }
                )

    return {
        "type": "FeatureCollection",
        "metadata": {
            "dataset_version": dataset_version,
            "nominal_date": nominal_date,
            "source_zoom": source_zoom,
            "tile_feature_count": len(features),
            "pixel_count": total_pixels,
            "run_count": total_runs,
        },
        "features": features,
    }

TRACEABLE_LAYERS = {
    "effis_fires": {
        "name": "Focos incendio Copernicus (EFFIS)",
        "service": "GeoJSON local",
        "layer": "effis_viirs_hs_today_wfs",
        "status_label": "cargada",
    },
    "effis_fwi": {
        "name": "Peligro de incendio FWI (EFFIS)",
        "service": "WMS",
        "url": EFFIS_WMS_BASE,
        "layer": "mf010.fwi",
        "time_policy": "today",
    },
    "effis_dc": {
        "name": "Índice sequía DC (EFFIS)",
        "service": "WMS",
        "url": EFFIS_WMS_BASE,
        "layer": "mf010.dc",
        "time_policy": "today",
    },
    "flood": {
        "name": "Zonas inundables fluviales T=10",
        "service": "WMS",
        "url": "https://servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones",
        "layer": "NZ.Flood.FluvialT10",
        "status_label": "cargada",
    },
    "corine_wms": {
        "name": "Usos del suelo completo WMS (IGN)",
        "service": "WMS",
        "url": "https://servicios.idee.es/wms-inspire/ocupacion-suelo",
        "layer": "LC.LandCoverSurfaces",
        "status_label": "cargada",
    },
    "corine": {
        "name": "Usos del suelo CORINE filtrado",
        "service": "GeoJSON local",
        "layer": "data/landcover.geojson",
        "status_label": "cargada",
    },
}


# AEMET: parseo CAP 
NS = "urn:oasis:names:tc:emergency:cap:1.2"
LEVEL_COLORS   = {"Amarillo": "#FFD700", "Naranja": "#FFA500", "Rojo": "#CC0000", "Verde": "#4CAF50"}
LEVEL_KEYWORDS = {"rojo": "Rojo", "naranja": "Naranja", "amarillo": "Amarillo", "verde": "Verde"}

def extract_level(event_text: str) -> str:
    lower = (event_text or "").lower()
    for kw, level in LEVEL_KEYWORDS.items():
        if kw in lower:
            return level
    return "Verde"

def normalize_event(event_text: str) -> str:
    if not event_text:
        return "Desconocido"
    lower = event_text.lower()
    for kw in LEVEL_KEYWORDS:
        idx = lower.find(f"nivel {kw}")
        if idx != -1:
            return event_text[:idx].strip(" ,;-de")
    return event_text.strip()

def _t(node, tag):
    el = node.find(f"{{{NS}}}{tag}") if node is not None else None
    return el.text.strip() if el is not None and el.text else None

def _dt(value):
    if not value:
        return None
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").isoformat()
    except Exception:
        return None

def parse_cap_xml(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    results = []
    nodes = root.findall(f"{{{NS}}}alert") or [root]
    for node in nodes:
        identifier = _t(node, "identifier")
        if not identifier:
            continue
        info = node.find(f"{{{NS}}}info")
        if info is None:
            continue
        raw_event = _t(info, "event") or "Desconocido"
        onset   = _dt(_t(info, "onset"))
        expires = _dt(_t(info, "expires"))
        if not onset or not expires:
            continue
        level = extract_level(raw_event)
        area  = info.find(f"{{{NS}}}area")
        results.append({
            "id":          identifier,
            "event":       normalize_event(raw_event),
            "level":       level,
            "level_color": LEVEL_COLORS.get(level, "#888"),
            "area_name":   _t(area, "areaDesc") if area is not None else "España",
            "description": _t(info, "description"),
            "instruction": _t(info, "instruction"),
            "onset":       onset,
            "expires":     expires,
            "polygon":     _t(area, "polygon") if area is not None else None,
            "source":      "aemet",
        })
    return results

async def fetch_aemet_alerts() -> list[dict]:
    if not settings.aemet_api_key:
        return []
    base    = "https://opendata.aemet.es/opendata/api"
    headers = {"api_key": settings.aemet_api_key}
    all_alerts = []

    async with httpx.AsyncClient(timeout=30) as client:
        for area in ["esp", "can"]:
            r1 = await client.get(f"{base}/avisos_cap/ultimoelaborado/area/{area}", headers=headers)
            r1.raise_for_status()
            meta = r1.json()
            if meta.get("estado") != 200:
                continue
            data_url = meta.get("datos")
            if not data_url:
                continue
            r2 = await client.get(data_url)
            r2.raise_for_status()
            content = r2.content
            if content[:2] == b'\x1f\x8b':
                content = gzip.decompress(content)
            with tarfile.open(fileobj=io.BytesIO(content)) as tar:
                for member in tar.getmembers():
                    if member.name.endswith(".xml"):
                        f = tar.extractfile(member)
                        if f:
                            try:
                                all_alerts.extend(parse_cap_xml(f.read()))
                            except Exception:
                                pass
    return all_alerts


# NASA FIRMS
FIRMS_API_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
FIRMS_DAY_RANGE = 1
FIRMS_VIIRS_SOURCES = ("VIIRS_NOAA21_NRT", "VIIRS_NOAA20_NRT", "VIIRS_SNPP_NRT")
FIRMS_OPTIONAL_SOURCES = ("MODIS_NRT",)
FIRMS_HTTP_TRUST_ENV_SEQUENCE = (False, True, False)
FIRMS_QUERY_AREAS = (
    ("peninsula_balears_ceuta_melilla", "-10.0,35.0,4.6,44.2"),
    ("canarias", "-18.5,27.5,-13.0,29.6"),
)
FIRMS_ALLOWED_CONFIDENCE = {"n", "h"}
FIRMS_CONFIDENCE_LABELS = {
    "l": "baja",
    "n": "nominal",
    "h": "alta",
}
FIRMS_VIIRS_FIELDS = (
    "latitude",
    "longitude",
    "bright_ti4",
    "scan",
    "track",
    "acq_date",
    "acq_time",
    "satellite",
    "confidence",
    "version",
    "bright_ti5",
    "frp",
    "daynight",
)
_SPAIN_GEOM = None

def postgres_conninfo() -> str:
    return (
        f"host={settings.postgres_host} "
        f"port={settings.postgres_port} "
        f"dbname={settings.postgres_db} "
        f"user={settings.postgres_user} "
        f"password={settings.postgres_password}"
    )

def get_db_pool() -> ConnectionPool:
    if db_pool is None:
        raise RuntimeError("El pool PostgreSQL no está inicializado")
    return db_pool

def set_landcover_publication_cache(feature_count: int, refreshed_at: datetime | None) -> None:
    global landcover_publication_cache_info
    landcover_publication_cache_info = {
        "feature_count": int(feature_count),
        "refreshed_at": refreshed_at,
    }

def reset_landcover_layer_metadata_cache() -> None:
    global landcover_layer_metadata_cache
    landcover_layer_metadata_cache = {
        "value": None,
        "expires_at": 0.0,
    }

def fetch_latest_landcover_refresh_timestamp() -> datetime | None:
    sql = """
    SELECT canonicalized_at
    FROM core.landcover_polygon
    ORDER BY canonicalized_at DESC
    LIMIT 1
    """
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
    return row[0] if row else None

def fetch_landcover_feature_collection() -> dict:
    sql = """
    SELECT jsonb_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(jsonb_agg(
            jsonb_build_object(
                'type', 'Feature',
                'id', feature_id,
                'geometry', ST_AsGeoJSON(geom)::jsonb,
                'properties', jsonb_build_object(
                    'class_code', class_code,
                    'label', class_label,
                    'color', class_color,
                    'theme', theme
                )
            )
            ORDER BY class_code
        ), '[]'::jsonb)
    )
    FROM pub.landcover_filtered
    """
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
    return row[0] if row and row[0] is not None else {"type": "FeatureCollection", "features": []}

def query_landcover_layer_metadata() -> dict:
    sql = """
    SELECT jsonb_build_object(
        'layer_id', 'landcover',
        'name', 'CORINE Land Cover filtrado',
        'geometry_type', 'MultiPolygon',
        'srid', 4326,
        'feature_count', COUNT(*),
        'class_count', COUNT(DISTINCT class_code),
        'bbox', jsonb_build_array(
            ST_XMin(ST_Extent(geom)),
            ST_YMin(ST_Extent(geom)),
            ST_XMax(ST_Extent(geom)),
            ST_YMax(ST_Extent(geom))
        ),
        'refreshed_at', (
            SELECT max(canonicalized_at)
            FROM core.landcover_polygon
        ),
        'source_view', 'pub.landcover_filtered',
        'tile_source_view', 'pub.landcover_mvt_source',
        'tile_feature_count', (
            SELECT count(*)
            FROM pub.landcover_mvt_source
        ),
        'render_mode', 'mvt',
        'tile_format', 'application/vnd.mapbox-vector-tile',
        'tile_url_template', '/api/landcover/tiles/{z}/{x}/{y}.mvt',
        'tile_layer_name', 'landcover'
    )
    FROM pub.landcover_filtered
    """
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
    data = row[0] if row and row[0] is not None else {
        "layer_id": "landcover",
        "name": "CORINE Land Cover filtrado",
        "geometry_type": "MultiPolygon",
        "srid": 4326,
        "feature_count": 0,
        "class_count": 0,
        "bbox": None,
        "refreshed_at": None,
        "source_view": "pub.landcover_filtered",
        "tile_source_view": "pub.landcover_mvt_source",
        "tile_feature_count": 0,
        "render_mode": "mvt",
        "tile_format": "application/vnd.mapbox-vector-tile",
        "tile_url_template": "/api/landcover/tiles/{z}/{x}/{y}.mvt",
        "tile_layer_name": "landcover",
    }
    if landcover_class_tile_source_available:
        data["tile_overview_source_view"] = "pub.landcover_mvt_class_source"
        data["tile_overview_max_zoom"] = LANDCOVER_TILE_OVERVIEW_MAX_ZOOM
    return data

def fetch_landcover_layer_metadata() -> dict:
    now = time.monotonic()
    cached_value = landcover_layer_metadata_cache["value"]
    if cached_value is not None and now < landcover_layer_metadata_cache["expires_at"]:
        return cached_value

    data = query_landcover_layer_metadata()
    landcover_layer_metadata_cache["value"] = data
    landcover_layer_metadata_cache["expires_at"] = now + LANDCOVER_LAYER_METADATA_CACHE_TTL_SECONDS
    return data

def fetch_landcover_publication_cache_info() -> dict:
    return landcover_publication_cache_info

def build_landcover_cache_headers() -> dict[str, str]:
    cache_info = fetch_landcover_publication_cache_info()
    feature_count = int(cache_info["feature_count"] or 0)
    refreshed_at = cache_info["refreshed_at"]
    if feature_count <= 0 or refreshed_at is None:
        return {"Cache-Control": "no-store"}

    headers = {"Cache-Control": "public, max-age=300"}
    refreshed_at_utc = refreshed_at.astimezone(timezone.utc)
    headers["Last-Modified"] = format_datetime(refreshed_at_utc, usegmt=True)
    headers["ETag"] = f'W/"landcover-{feature_count}-{int(refreshed_at_utc.timestamp())}"'
    return headers

def build_landcover_tile_cache_headers() -> dict[str, str]:
    headers = build_landcover_cache_headers()
    if headers.get("Cache-Control") == "no-store":
        return headers
    headers["Cache-Control"] = "public, max-age=3600"
    return headers

def get_landcover_tile_simplification_tolerance(z: int) -> float:
    if z >= 13:
        return 0.0
    meters_per_pixel = 156543.03392804097 / (2 ** z)
    if z <= 6:
        factor = 0.75
    elif z <= 8:
        factor = 0.25
    elif z <= 10:
        factor = 0.15
    else:
        factor = 0.05
    return meters_per_pixel * factor

def execute_landcover_vector_tile_query(sql: str, params: tuple[object, ...]) -> bytes:
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL max_parallel_workers_per_gather = 0")
            cur.execute(sql, params)
            row = cur.fetchone()
    if not row or row[0] is None:
        return b""
    return bytes(row[0])

def fetch_landcover_overview_vector_tile(z: int, x: int, y: int, tolerance: float) -> bytes:
    sql = """
    WITH tile_envelope AS (
        SELECT ST_TileEnvelope(%s, %s, %s) AS geom
    ),
    candidate_geom AS (
        SELECT
            src.feature_id AS core_feature_id,
            src.feature_id,
            src.class_code,
            src.class_label,
            src.class_color,
            src.theme,
            src.geom
        FROM pub.landcover_mvt_class_source AS src
        CROSS JOIN tile_envelope AS env
        WHERE src.geom && env.geom
          AND ST_Intersects(src.geom, env.geom)
    ),
    mvtgeom AS (
        SELECT
            src.core_feature_id,
            src.feature_id,
            src.class_code,
            src.class_label,
            src.class_color,
            src.theme,
            class_label AS label,
            class_color AS color,
            ST_AsMVTGeom(
                CASE
                    WHEN %s > 0 THEN ST_SimplifyPreserveTopology(src.geom, %s)
                    ELSE src.geom
                END,
                env.geom,
                4096,
                64,
                true
            ) AS geom
        FROM candidate_geom AS src
        CROSS JOIN tile_envelope AS env
    )
    SELECT ST_AsMVT(tile_rows, 'landcover', 4096, 'geom')
    FROM (
        SELECT
            core_feature_id,
            feature_id,
            class_code,
            class_label,
            class_color,
            theme,
            label,
            color,
            geom
        FROM mvtgeom
        WHERE geom IS NOT NULL
    ) AS tile_rows
    """
    return execute_landcover_vector_tile_query(sql, (z, x, y, tolerance, tolerance))

def fetch_landcover_detail_vector_tile(z: int, x: int, y: int, tolerance: float) -> bytes:
    sql = """
    WITH tile_envelope AS (
        SELECT ST_TileEnvelope(%s, %s, %s) AS geom
    ),
    candidate_geom AS (
        SELECT
            src.core_feature_id,
            src.class_code,
            src.class_label,
            src.class_color,
            src.theme,
            src.geom
        FROM pub.landcover_mvt_source AS src
        CROSS JOIN tile_envelope AS env
        WHERE src.geom && env.geom
          AND ST_Intersects(src.geom, env.geom)
    ),
    mvtgeom AS (
        SELECT
            src.core_feature_id,
            src.class_code,
            src.class_label,
            src.class_color,
            src.theme,
            class_label AS label,
            class_color AS color,
            ST_AsMVTGeom(
                CASE
                    WHEN %s > 0 THEN ST_SimplifyPreserveTopology(src.geom, %s)
                    ELSE src.geom
                END,
                env.geom,
                4096,
                64,
                true
            ) AS geom
        FROM candidate_geom AS src
        CROSS JOIN tile_envelope AS env
    )
    SELECT ST_AsMVT(tile_rows, 'landcover', 4096, 'geom')
    FROM (
        SELECT
            core_feature_id,
            class_code,
            class_label,
            class_color,
            theme,
            label,
            color,
            geom
        FROM mvtgeom
        WHERE geom IS NOT NULL
    ) AS tile_rows
    """
    return execute_landcover_vector_tile_query(sql, (z, x, y, tolerance, tolerance))

def fetch_landcover_vector_tile(z: int, x: int, y: int) -> bytes:
    tolerance = get_landcover_tile_simplification_tolerance(z)
    if z <= LANDCOVER_TILE_OVERVIEW_MAX_ZOOM and landcover_class_tile_source_available:
        return fetch_landcover_overview_vector_tile(z, x, y, tolerance)
    return fetch_landcover_detail_vector_tile(z, x, y, tolerance)

def get_landcover_zoom_config(
    zoom: int,
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    width: int,
    height: int,
) -> dict:
    span_x = maxx - minx
    span_y = maxy - miny
    safe_width = max(width, 1)
    safe_height = max(height, 1)
    units_per_pixel = max(span_x / safe_width, span_y / safe_height)

    if zoom <= 5:
        limit = 800
        pixel_factor = 2.0
    elif zoom <= 6:
        limit = 1200
        pixel_factor = 1.5
    elif zoom <= 8:
        limit = 1800
        pixel_factor = 1.0
    elif zoom <= 10:
        limit = 2500
        pixel_factor = 0.75
    elif zoom <= 12:
        limit = 3500
        pixel_factor = 0.5
    else:
        limit = 5000
        pixel_factor = 0.25

    tolerance = units_per_pixel * pixel_factor

    if units_per_pixel <= 0.00008:
        tolerance = 0.0
    elif units_per_pixel <= 0.0002:
        tolerance = min(tolerance, units_per_pixel * 0.35)
    elif units_per_pixel <= 0.0005:
        tolerance = min(tolerance, units_per_pixel * 0.5)

    return {
        "source": "core",
        "simplification_tolerance": tolerance,
        "limit": limit,
        "units_per_pixel": units_per_pixel,
    }

def clean_landcover_wms_text(value: object) -> str:
    if value in (None, ""):
        return ""
    return " ".join(str(value).split())

def detect_landcover_wms_dataset(feature_id: str) -> str:
    if feature_id.startswith("corine2018."):
        return "CORINE 2018"
    if feature_id.startswith("siose2014."):
        return "SIOSE 2014"
    if feature_id.startswith("sioseAR2017."):
        return "SIOSE AR 2017"
    return "IGN WMS"

def normalize_landcover_wms_crs_name(payload: dict) -> str:
    crs = payload.get("crs") or {}
    properties = crs.get("properties") or {}
    name = str(properties.get("name") or "").upper()
    if name.endswith("EPSG::3857") or name.endswith("EPSG:3857"):
        return "EPSG:3857"
    if name.endswith("EPSG::4326") or name.endswith("EPSG:4326"):
        return "EPSG:4326"
    if name.endswith("CRS::84") or name.endswith("CRS:84"):
        return "CRS:84"
    return ""

def extract_landcover_wms_coordinate_pair(coordinates: object) -> tuple[float, float] | None:
    if isinstance(coordinates, (list, tuple)):
        if len(coordinates) >= 2 and all(isinstance(value, (int, float)) for value in coordinates[:2]):
            return float(coordinates[0]), float(coordinates[1])
        for item in coordinates:
            pair = extract_landcover_wms_coordinate_pair(item)
            if pair is not None:
                return pair
    return None

def normalize_landcover_wms_source_crs(source_crs: str, geometry: dict | None) -> str:
    if source_crs in {"EPSG:3857", "EPSG:4326", "CRS:84"}:
        return source_crs
    if not geometry:
        return source_crs
    if geometry.get("type") == "GeometryCollection":
        for item in geometry.get("geometries", []):
            normalized = normalize_landcover_wms_source_crs(source_crs, item)
            if normalized in {"EPSG:3857", "EPSG:4326", "CRS:84"}:
                return normalized
        return source_crs
    pair = extract_landcover_wms_coordinate_pair(geometry.get("coordinates"))
    if pair is None:
        return source_crs
    x, y = pair
    if abs(x) <= 180 and abs(y) <= 90:
        return "EPSG:4326"
    return "EPSG:3857"

def mercator_to_wgs84(x: float, y: float) -> tuple[float, float]:
    lon = (x / 20037508.34) * 180.0
    lat = (y / 20037508.34) * 180.0
    lat = (180.0 / math.pi) * (2.0 * math.atan(math.exp(lat * math.pi / 180.0)) - math.pi / 2.0)
    return lon, lat

def reproject_landcover_wms_coordinates(coords: list, source_crs: str) -> list:
    if not coords:
        return coords
    if isinstance(coords[0], (int, float)):
        if source_crs == "EPSG:3857":
            lon, lat = mercator_to_wgs84(float(coords[0]), float(coords[1]))
            if len(coords) > 2:
                return [lon, lat, *coords[2:]]
            return [lon, lat]
        return coords
    return [reproject_landcover_wms_coordinates(item, source_crs) for item in coords]

def reproject_landcover_wms_geometry(geometry: dict | None, source_crs: str) -> dict | None:
    if not geometry or source_crs not in {"EPSG:3857"}:
        return geometry
    geometry_type = geometry.get("type")
    if geometry_type == "GeometryCollection":
        return {
            **geometry,
            "geometries": [
                reproject_landcover_wms_geometry(item, source_crs)
                for item in geometry.get("geometries", [])
            ],
        }
    return {
        **geometry,
        "coordinates": reproject_landcover_wms_coordinates(geometry.get("coordinates", []), source_crs),
    }

def normalize_landcover_wms_surface_ha(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        surface_ha = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(surface_ha) or surface_ha < 0:
        return None
    return round(surface_ha, 2)

@lru_cache(maxsize=8)
def get_landcover_area_transformer(source_crs: str) -> Transformer | None:
    if not source_crs:
        return None
    normalized_source = "EPSG:4326" if source_crs == "CRS:84" else source_crs
    if normalized_source == LANDCOVER_AREA_CRS:
        return None
    return Transformer.from_crs(normalized_source, LANDCOVER_AREA_CRS, always_xy=True)

def calculate_landcover_wms_surface_ha(geometry: dict | None, source_crs: str) -> float | None:
    effective_source_crs = normalize_landcover_wms_source_crs(source_crs, geometry)
    if not geometry or not effective_source_crs:
        return None
    try:
        geom = shape(geometry)
        if geom.is_empty:
            return None
        transformer = get_landcover_area_transformer(effective_source_crs)
        geom_for_area = geom if transformer is None else transform(transformer.transform, geom)
        surface_ha = geom_for_area.area / 10000.0
    except Exception:
        return None
    if not math.isfinite(surface_ha) or surface_ha < 0:
        return None
    return round(surface_ha, 2)

def normalize_landcover_wms_feature(feature: dict, source_crs: str) -> dict:
    raw_properties = feature.get("properties") or {}
    feature_id = str(feature.get("id") or "")
    raw_geometry = feature.get("geometry")
    effective_source_crs = normalize_landcover_wms_source_crs(source_crs, raw_geometry)
    label = (
        clean_landcover_wms_text(raw_properties.get("valor"))
        or clean_landcover_wms_text(raw_properties.get("codiige_valor"))
        or clean_landcover_wms_text(raw_properties.get("hilucs_valor"))
        or "Uso del suelo"
    )

    code = None
    code_field = None
    for candidate_field in ("codigo_n3", "codiige", "hilucs"):
        value = raw_properties.get(candidate_field)
        if value not in (None, ""):
            code = str(value)
            code_field = candidate_field
            break

    secondary_label = ""
    if code_field != "hilucs":
        secondary_label = clean_landcover_wms_text(raw_properties.get("hilucs_valor"))

    surface_ha = normalize_landcover_wms_surface_ha(raw_properties.get("superficie_ha"))
    surface_ha_source = "attribute" if surface_ha is not None else None
    if surface_ha is None:
        surface_ha = calculate_landcover_wms_surface_ha(raw_geometry, effective_source_crs)
        if surface_ha is not None:
            surface_ha_source = "computed"

    return {
        "type": "Feature",
        "id": feature.get("id"),
        "geometry": reproject_landcover_wms_geometry(raw_geometry, effective_source_crs),
        "properties": {
            "label": label,
            "code": code,
            "code_field": code_field,
            "source_dataset": detect_landcover_wms_dataset(feature_id),
            "source_date": raw_properties.get("fecha_observacion"),
            "secondary_label": secondary_label,
            "surface_ha": surface_ha,
            "surface_ha_source": surface_ha_source,
            "geometry_crs": "EPSG:4326",
            "source_properties": raw_properties,
        },
    }

def parse_landcover_query_bbox(bbox: str) -> list[float]:
    try:
        values = [float(value) for value in bbox.split(",")]
    except ValueError as exc:
        raise ValueError("bbox debe contener cuatro numeros") from exc
    if len(values) != 4:
        raise ValueError("bbox debe tener formato minx,miny,maxx,maxy")
    minx, miny, maxx, maxy = values
    if minx >= maxx or miny >= maxy:
        raise ValueError("bbox invalido: min debe ser menor que max")
    return values

def fetch_landcover_features_by_point(
    lon: float,
    lat: float,
    bbox: str,
    width: int,
    height: int,
    i: int,
    j: int,
    crs: str,
) -> dict:
    bbox_values = parse_landcover_query_bbox(bbox)
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetFeatureInfo",
        "LAYERS": LANDCOVER_WMS_LAYER,
        "QUERY_LAYERS": LANDCOVER_WMS_LAYER,
        "CRS": crs,
        "BBOX": ",".join(str(value) for value in bbox_values),
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "I": str(i),
        "J": str(j),
        "STYLES": "",
        "FORMAT": "image/png",
        "INFO_FORMAT": LANDCOVER_WMS_INFO_FORMAT,
        "FEATURE_COUNT": "1",
    }

    with httpx.Client(timeout=30, follow_redirects=True, trust_env=False) as client:
        response = client.get(LANDCOVER_WMS_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    response_crs = normalize_landcover_wms_crs_name(payload)
    normalized_features = [
        normalize_landcover_wms_feature(feature, response_crs)
        for feature in payload.get("features", [])
    ]

    return {
        "type": "FeatureCollection",
        "features": normalized_features,
        "metadata": {
            "source": "IGN WMS GetFeatureInfo",
            "wms_url": LANDCOVER_WMS_URL,
            "layer": LANDCOVER_WMS_LAYER,
            "response_crs": response_crs,
            "geometry_crs": "EPSG:4326",
            "query": {
                "lon": lon,
                "lat": lat,
                "crs": crs,
                "bbox": bbox_values,
                "width": width,
                "height": height,
                "i": i,
                "j": j,
            },
            "returned_count": len(normalized_features),
        },
    }

def fetch_landcover_features_by_bbox(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    zoom: int,
    width: int,
    height: int,
    limit: int,
) -> dict:
    config = get_landcover_zoom_config(zoom, minx, miny, maxx, maxy, width, height)
    tolerance = config["simplification_tolerance"]
    units_per_pixel = config["units_per_pixel"]
    sql = """
    WITH envelope AS (
        SELECT ST_MakeEnvelope(%s, %s, %s, %s, 4326) AS geom
    ),
    matching AS (
        SELECT
            class_code,
            class_label,
            class_color,
            theme,
            ST_Multi(
                ST_CollectionExtract(
                    CASE
                        WHEN %s > 0 THEN ST_SimplifyPreserveTopology(
                            ST_Intersection(lp.geom, e.geom),
                            %s
                        )
                        ELSE ST_Intersection(lp.geom, e.geom)
                    END,
                    3
                )
            )::geometry(MultiPolygon, 4326) AS geom
        FROM core.landcover_polygon lp
        JOIN envelope e ON lp.geom && e.geom AND ST_Intersects(lp.geom, e.geom)
    ),
    non_empty AS (
        SELECT *
        FROM matching
        WHERE NOT ST_IsEmpty(geom)
    ),
    aggregated AS (
        SELECT
            format('landcover_%%s', class_code) AS feature_id,
            class_code,
            class_label,
            class_color,
            theme,
            ST_Multi(
                ST_CollectionExtract(
                    ST_UnaryUnion(ST_Collect(geom)),
                    3
                )
            )::geometry(MultiPolygon, 4326) AS geom
        FROM non_empty
        GROUP BY class_code, class_label, class_color, theme
    )
    SELECT jsonb_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(jsonb_agg(
            jsonb_build_object(
                'type', 'Feature',
                'id', feature_id,
                'geometry', ST_AsGeoJSON(geom)::jsonb,
                'properties', jsonb_build_object(
                    'class_code', class_code,
                    'label', class_label,
                    'color', class_color,
                    'theme', theme
                )
            )
            ORDER BY class_code
        ), '[]'::jsonb),
        'metadata', jsonb_build_object(
            'zoom', %s,
            'source', 'core.landcover_polygon',
            'aggregation', 'class',
            'simplification_tolerance', %s,
            'units_per_pixel', %s,
            'returned_count', COUNT(*),
            'matched_feature_count', (SELECT COUNT(*) FROM non_empty),
            'truncated', false
        )
    )
    FROM aggregated
    """
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL max_parallel_workers_per_gather = 0")
            cur.execute(
                sql,
                (
                    minx,
                    miny,
                    maxx,
                    maxy,
                    tolerance,
                    tolerance,
                    zoom,
                    tolerance,
                    units_per_pixel,
                ),
            )
            row = cur.fetchone()
    return row[0] if row and row[0] is not None else {
        "type": "FeatureCollection",
        "features": [],
        "metadata": {
            "zoom": zoom,
            "source": "core.landcover_polygon",
            "aggregation": "class",
            "simplification_tolerance": tolerance,
            "units_per_pixel": units_per_pixel,
            "returned_count": 0,
            "matched_feature_count": 0,
            "truncated": False,
        },
    }

def fetch_landcover_feature_detail(core_feature_id: int) -> dict | None:
    sql = """
    SELECT jsonb_build_object(
        'type', 'Feature',
        'id', core_feature_id,
        'geometry', ST_AsGeoJSON(geom)::jsonb,
        'properties', jsonb_build_object(
            'class_code', class_code,
            'label', class_label,
            'color', class_color,
            'theme', theme,
            'dataset_id', dataset_id,
            'source_layer', source_layer,
            'source_objectid', source_objectid,
            'ingest_id', ingest_id,
            'imported_at', imported_at,
            'canonicalized_at', canonicalized_at
        )
    )
    FROM core.landcover_polygon
    WHERE core_feature_id = %s
    """
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (core_feature_id,))
            row = cur.fetchone()
    return row[0] if row and row[0] is not None else None

async def load_spain_geometry():
    global _SPAIN_GEOM
    if not os.path.exists(SPAIN_BOUNDARY_PATH):
        raise FileNotFoundError(
            f"No se encontró {SPAIN_BOUNDARY_PATH}; es necesario para filtrar FIRMS por España"
        )

    try:
        with open(SPAIN_BOUNDARY_PATH, encoding="utf-8") as f:
            geojson = json.load(f)
        features = geojson.get("features", [geojson]) if "features" in geojson else [geojson]
        geometries = [shape(f["geometry"]) for f in features if f.get("geometry")]
        if not geometries:
            raise ValueError("El GeoJSON de España no contiene geometrías")
        _SPAIN_GEOM = unary_union(geometries)
        print("  Geometria de Espana cargada desde GeoJSON local")
    except Exception as e:
        raise RuntimeError(f"Error cargando geometria local de Espana: {e}") from e

def is_in_spain(lat: float, lon: float) -> bool:
    if _SPAIN_GEOM is None:
        raise RuntimeError("La geometria de Espana no esta cargada")
    return _SPAIN_GEOM.covers(Point(lon, lat))

def classify_frp(frp: float) -> tuple[str, str]:
    if frp > 200: return "Muy alto", "#8E1B1B"
    if frp >= 50: return "Alto",     "#E94F37"
    if frp >= 10: return "Medio",    "#F8961E"
    return              "Bajo",      "#FFD166"

def normalize_firms_confidence(value: str | None) -> str:
    raw = (value or "").strip().lower()
    aliases = {
        "low": "l",
        "l": "l",
        "nominal": "n",
        "n": "n",
        "high": "h",
        "h": "h",
    }
    return aliases.get(raw, raw)

def firms_confidence_label(code: str) -> str:
    return FIRMS_CONFIDENCE_LABELS.get(code, code or "no indicada")

def firms_sources() -> tuple[str, ...]:
    sources = list(FIRMS_VIIRS_SOURCES)
    if settings.firms_include_modis:
        sources.extend(FIRMS_OPTIONAL_SOURCES)
    return tuple(sources)

def _float_or_none(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def current_local_date_iso() -> str:
    return datetime.now().astimezone().date().isoformat()

def file_size_mb(path: str) -> float:
    return os.path.getsize(path) / 1024 / 1024

def format_utc_timestamp(value: str | None) -> str:
    if not value:
        return "fecha no indicada"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return value

def read_effis_local_metadata() -> tuple[dict, int] | None:
    if not os.path.exists(EFFIS_LOCAL_FIRES_PATH):
        return None
    with open(EFFIS_LOCAL_FIRES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("metadata", {}), len(data.get("features", []))

def effis_generated_local_date(metadata: dict) -> str | None:
    value = metadata.get("generated_at_utc")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone().date().isoformat()

async def refresh_effis_local_layer_if_needed() -> None:
    if not settings.effis_auto_refresh:
        print("  EFFIS/Copernicus autoactualización desactivada")
        return

    effis_metadata = read_effis_local_metadata()
    metadata = effis_metadata[0] if effis_metadata else {}
    generated_date = effis_generated_local_date(metadata)
    today = current_local_date_iso()
    if generated_date == today:
        print("  EFFIS/Copernicus local actualizado hoy; no se regenera")
        return

    if generated_date:
        generated_at = format_utc_timestamp(metadata.get("generated_at_utc"))
        print(f"  EFFIS/Copernicus local desactualizado ({generated_at}); actualizando...")
    else:
        print("  EFFIS/Copernicus local no encontrado; generando capa de hoy...")

    args = generar_effis_wfs.parse_args([
        "--source", "effis",
        "--timeout", str(settings.effis_refresh_timeout),
        "--retries", str(settings.effis_refresh_retries),
    ])

    try:
        with redirect_stdout(io.StringIO()):
            result = await generar_effis_wfs.async_main(args)
    except Exception as exc:
        print(f"  AVISO: no se pudo actualizar EFFIS/Copernicus: {exc}")
        return

    if result != 0:
        print(f"  AVISO: no se pudo actualizar EFFIS/Copernicus (código {result})")
        return
    print("  EFFIS/Copernicus actualizado")

def trace_layer_message(key: str, requested_time: str | None = None) -> str:
    layer = TRACEABLE_LAYERS.get(key)
    if not layer:
        return f"  Capa desconocida: {key}"

    name = layer["name"]
    if layer.get("time_policy") == "today":
        time_value = requested_time or current_local_date_iso()
        return f"  {name}: TIME={time_value}"
    if layer.get("status_label"):
        return f"  {name}: {layer['status_label']}"
    return f"  {name}: cargada"

def log_static_layers() -> None:
    print("Cargando capas locales...")
    effis_metadata = read_effis_local_metadata()
    if effis_metadata is None:
        print("  AVISO: capa local EFFIS/Copernicus no encontrada.")
        print("  Ejecuta primero: python generar_effis_wfs.py")
    else:
        metadata, feature_count = effis_metadata
        generated_at = format_utc_timestamp(metadata.get("generated_at_utc"))
        source_layer = metadata.get("layer", "viirs.hs.today")
        tiles_ok = metadata.get("tiles_ok", "n/d")
        tiles_total = metadata.get("tiles_total", "n/d")
        print(
            f"  EFFIS/Copernicus local listo "
            f"({file_size_mb(EFFIS_LOCAL_FIRES_PATH):.1f} MB)"
        )
        print(f"    Capa origen: {source_layer}; generado: {generated_at}")
        print(f"    Features: {feature_count}; teselas correctas: {tiles_ok}/{tiles_total}")

def log_wms_catalog() -> None:
    print("Cargando catálogo de capas WMS...")
    for key in ("effis_fwi", "effis_dc", "flood", "corine_wms"):
        print(trace_layer_message(key))

def log_main_layers(alert_count: int) -> None:
    print("Cargando capas principales...")
    print(f"  Avisos AEMET: {alert_count} avisos cargados")
    print("  Focos NASA FIRMS: en vivo al cargar el visor")

def _format_acq_datetime_utc(acq_date: str, acq_time: str) -> str:
    if not acq_date:
        return ""
    time = (acq_time or "").zfill(4)
    if len(time) != 4 or not time.isdigit():
        return f"{acq_date}T00:00:00Z"
    return f"{acq_date}T{time[:2]}:{time[2:]}:00Z"

async def fetch_firms_csv(
    source: str,
    area_coordinates: str,
) -> str:
    url = f"{FIRMS_API_BASE}/{settings.firms_map_key}/{source}/{area_coordinates}/{FIRMS_DAY_RANGE}"
    last_transport_error = None
    total_attempts = len(FIRMS_HTTP_TRUST_ENV_SEQUENCE)

    for attempt_number, trust_env in enumerate(FIRMS_HTTP_TRUST_ENV_SEQUENCE, start=1):
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True, trust_env=trust_env) as client:
                r = await client.get(url)
                r.raise_for_status()
                return r.text
        except httpx.HTTPStatusError:
            raise
        except httpx.TransportError as exc:
            last_transport_error = exc
            if attempt_number >= total_attempts:
                break
            await asyncio.sleep(0.4 * attempt_number)

    if last_transport_error is not None:
        raise last_transport_error
    raise RuntimeError(f"No se pudo consultar FIRMS para {source}")

def parse_firms_csv(text: str, source: str, area_name: str) -> tuple[list[dict], int]:
    fires = []
    excluded = 0
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or not {"latitude", "longitude"}.issubset(reader.fieldnames):
        raise ValueError(f"Respuesta FIRMS inesperada para {source}/{area_name}")
    for row in reader:
        try:
            lat = _float_or_none(row.get("latitude"))
            lon = _float_or_none(row.get("longitude"))
            if lat is None or lon is None:
                excluded += 1
                continue
            if not is_in_spain(lat, lon):
                excluded += 1
                continue

            confidence_code = normalize_firms_confidence(row.get("confidence"))
            if confidence_code not in FIRMS_ALLOWED_CONFIDENCE:
                excluded += 1
                continue

            frp = _float_or_none(row.get("frp")) or 0.0
            level, color = classify_frp(frp)
            acq_date = row.get("acq_date", "")
            acq_time = row.get("acq_time", "").zfill(4)
            fire = {field: row.get(field, "") for field in FIRMS_VIIRS_FIELDS}
            fire.update({
                "id": (
                    f"{source}_{lat:.6f}_{lon:.6f}_{acq_date}_{acq_time}_"
                    f"{row.get('satellite', '')}"
                ),
                "latitude": lat,
                "longitude": lon,
                "frp": frp,
                "level": level,
                "level_color": color,
                "intensity_label": level,
                "intensity_color": color,
                "confidence_code": confidence_code,
                "confidence_label": firms_confidence_label(confidence_code),
                "acq_date": acq_date,
                "acq_time": acq_time,
                "acq_datetime_utc": _format_acq_datetime_utc(acq_date, acq_time),
                "source": "firms",
                "firms_source": source,
                "query_area": area_name,
            })
            fires.append(fire)
        except Exception:
            excluded += 1
    return fires, excluded

async def fetch_spain_hotspots() -> list[dict]:
    if not settings.firms_map_key:
        return []
    if _SPAIN_GEOM is None:
        await load_spain_geometry()

    requests = [
        (source, area_name, area_coordinates)
        for source in firms_sources()
        for area_name, area_coordinates in FIRMS_QUERY_AREAS
    ]
    fires = []
    excluded = 0
    errors = []
    for source, area_name, area_coordinates in requests:
        try:
            result = await fetch_firms_csv(source, area_coordinates)
        except Exception as exc:
            errors.append(f"{source}/{area_name}: {exc}")
            continue
        try:
            parsed, parsed_excluded = parse_firms_csv(result, source, area_name)
        except Exception as exc:
            errors.append(f"{source}/{area_name}: {exc}")
            continue
        fires.extend(parsed)
        excluded += parsed_excluded

    if errors and not fires:
        raise RuntimeError("; ".join(errors))
    if errors:
        print("  FIRMS: avisos parciales:", "; ".join(errors))

    unique = {}
    for fire in fires:
        key = (
            fire.get("firms_source"),
            fire.get("latitude"),
            fire.get("longitude"),
            fire.get("acq_date"),
            fire.get("acq_time"),
            fire.get("satellite"),
        )
        unique.setdefault(key, fire)

    fires = sorted(
        list(unique.values()),
        key=lambda f: (f.get("acq_datetime_utc") or "", float(f.get("frp") or 0)),
        reverse=True,
    )
    print(f"  FIRMS: {len(fires)} focos en Espana, {excluded} excluidos")
    return fires

fetch_firms_fires = fetch_spain_hotspots


# Lifespan 
@asynccontextmanager
async def lifespan(app: FastAPI):
    global alerts_cache, fires_cache, db_pool, landcover_class_tile_source_available
    print("Cargando geometria de Espana...")
    await load_spain_geometry()

    await refresh_effis_local_layer_if_needed()
    log_static_layers()
    log_wms_catalog()

    print("Inicializando PostgreSQL/PostGIS...")
    db_pool = ConnectionPool(conninfo=postgres_conninfo(), min_size=1, max_size=4, open=False)
    try:
        db_pool.open()
        with db_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM pub.landcover_filtered")
                landcover_count = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM pub.landcover_mvt_source")
                landcover_tile_count = cur.fetchone()[0]
                cur.execute("SELECT to_regclass('pub.landcover_mvt_class_source')")
                landcover_class_tile_source_available = cur.fetchone()[0] is not None
                landcover_overview_tile_count = 0
                if landcover_class_tile_source_available:
                    cur.execute("SELECT count(*) FROM pub.landcover_mvt_class_source")
                    landcover_overview_tile_count = cur.fetchone()[0]
        landcover_refreshed_at = fetch_latest_landcover_refresh_timestamp() if landcover_tile_count > 0 else None
        set_landcover_publication_cache(landcover_tile_count, landcover_refreshed_at)
        reset_landcover_layer_metadata_cache()
        print(
            "  CORINE listo "
            f"(pub.landcover_filtered={landcover_count} clases publicadas, "
            f"pub.landcover_mvt_source={landcover_tile_count} features para MVT"
            + (
                f", pub.landcover_mvt_class_source={landcover_overview_tile_count} clases para bajo zoom"
                if landcover_class_tile_source_available
                else ", sin fuente agregada de bajo zoom"
            )
            + ")"
        )
    except Exception:
        if db_pool is not None:
            db_pool.close()
            db_pool = None
        raise
 
    print("Cargando datos de AEMET...")
    alerts_cache = await fetch_aemet_alerts()
    if settings.aemet_api_key:
        print(f"  → {len(alerts_cache)} avisos cargados")
    else:
        print("  AEMET_API_KEY no configurada; /api/alerts devolvera lista vacia")
    fires_cache = []
    log_main_layers(len(alerts_cache))
    yield
    if db_pool is not None:
        db_pool.close()
        db_pool = None
 

# App 
app = FastAPI(title="MeteoVisor Demo", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# Endpoints
@app.get("/api/alerts")
def get_alerts():
    """Avisos meteorológicos activos de AEMET."""
    return alerts_cache
 
@app.get("/api/fires")
async def get_fires(response: Response):
    """Focos de incendio activos de NASA FIRMS, solicitados en vivo al cargar el visor."""
    global fires_cache
    response.headers["Cache-Control"] = "no-store"
    try:
        fires_cache = await fetch_spain_hotspots()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error consultando NASA FIRMS: {exc}") from exc
    return fires_cache
 
def compute_alert_status_counts(reference_time: datetime | None = None) -> dict[str, int]:
    current_time = reference_time or datetime.now()
    active = 0
    upcoming = 0
    expired = 0

    for alert in alerts_cache:
        try:
            onset = datetime.fromisoformat(alert["onset"])
            expires = datetime.fromisoformat(alert["expires"])
        except Exception:
            continue
        if expires < current_time:
            expired += 1
        elif onset <= current_time:
            active += 1
        else:
            upcoming += 1

    return {
        "active": active,
        "upcoming": upcoming,
        "expired": expired,
        "total": active + upcoming,
    }

@app.get("/api/stats")
def get_stats():
    """Estadísticas básicas de los datos cargados."""
    current_time = datetime.now()
    alert_counts = compute_alert_status_counts(current_time)
    level_count      = {}
    fire_intensity_count = {}
    for a in alerts_cache:
        try:
            if datetime.fromisoformat(a["expires"]) < current_time:
                continue
        except Exception:
            continue
        level_count[a["level"]] = level_count.get(a["level"], 0) + 1
    for f in fires_cache:
        intensity = f.get("intensity_label") or f.get("level") or "Sin clasificar"
        fire_intensity_count[intensity] = fire_intensity_count.get(intensity, 0) + 1
    return {
        "alerts": {
            "total":     alert_counts["total"],
            "active":    alert_counts["active"],
            "upcoming":  alert_counts["upcoming"],
            "expired":   alert_counts["expired"],
            "por_nivel": level_count,
        },
        "fires": {
            "total":     len(fires_cache),
            "por_nivel": fire_intensity_count,
            "por_intensidad": fire_intensity_count,
            "frp_max":   max((f["frp"] for f in fires_cache), default=0),
        },
    }

@app.get("/api/layers/burnt-area")
def get_burnt_area_layer_metadata():
    """Metadatos de la capa temporal diaria de burnt area."""
    data = build_burnt_area_layer_metadata()
    return JSONResponse(content=data, headers={"Cache-Control": "no-store"})

@app.get("/api/burnt-area/timeline")
def get_burnt_area_timeline(
    dataset_version: str = Query(BURNT_AREA_PREFERRED_VERSION, alias="version"),
    delivery_format: str = Query(BURNT_AREA_PREFERRED_FORMAT, alias="format"),
    date_from: str | None = Query(BURNT_AREA_DEFAULT_DATE_FROM),
    date_to: str | None = Query(BURNT_AREA_DEFAULT_DATE_TO),
):
    """Timeline diaria disponible para la capa temporal de burnt area."""
    validate_burnt_area_variant(dataset_version, delivery_format)
    normalized_date_from = validate_burnt_area_date_string(date_from) if date_from else None
    normalized_date_to = validate_burnt_area_date_string(date_to) if date_to else None
    data = build_burnt_area_timeline_payload(
        dataset_version,
        delivery_format,
        normalized_date_from,
        normalized_date_to,
    )
    return JSONResponse(content=data, headers={"Cache-Control": "no-store"})

@app.get("/api/burnt-area/stats/daily")
def get_burnt_area_daily_stats(
    dataset_version: str = Query(BURNT_AREA_PREFERRED_VERSION, alias="version"),
    delivery_format: str = Query(BURNT_AREA_PREFERRED_FORMAT, alias="format"),
    date_from: str | None = Query(BURNT_AREA_DEFAULT_DATE_FROM),
    date_to: str | None = Query(BURNT_AREA_DEFAULT_DATE_TO),
):
    """Serie diaria de estadisticas publicadas de burnt area."""
    validate_burnt_area_variant(dataset_version, delivery_format)
    normalized_date_from = validate_burnt_area_date_string(date_from) if date_from else None
    normalized_date_to = validate_burnt_area_date_string(date_to) if date_to else None
    data = build_burnt_area_daily_stats_payload(
        dataset_version,
        delivery_format,
        normalized_date_from,
        normalized_date_to,
    )
    return JSONResponse(content=data, headers={"Cache-Control": "no-store"})

@app.get("/api/burnt-area/tiles/{dataset_version}/{nominal_date}/{z:int}/{x:int}/{y:int}.png")
def get_burnt_area_tile(dataset_version: str, nominal_date: str, z: int, x: int, y: int):
    """Tesela PNG local de burnt area para una fecha concreta.

    Mientras no existan teselas locales generadas, responde PNG transparente
    para que el cliente pueda inicializar la capa temporal sin romper el visor.
    """
    validate_burnt_area_variant(dataset_version, BURNT_AREA_PREFERRED_FORMAT)
    normalized_date = validate_burnt_area_date_string(nominal_date)
    if z < 0 or x < 0 or y < 0:
        raise HTTPException(status_code=400, detail="Coordenadas de tesela no validas")

    tile_path = resolve_burnt_area_tile_path(dataset_version, normalized_date, z, x, y)
    if tile_path.is_file():
        return FileResponse(tile_path, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})

    return Response(
        content=BURNT_AREA_TRANSPARENT_PNG,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store",
            "X-Burnt-Area-Status": "missing-local-tile",
        },
    )


@app.get("/api/burnt-area/locator/{dataset_version}/{nominal_date}")
def get_burnt_area_locator(
    dataset_version: str,
    nominal_date: str,
    source_zoom: int = Query(10),
):
    """Vector localizador aproximado derivado de las PNG no vacias para destacar el raster."""
    validate_burnt_area_variant(dataset_version, BURNT_AREA_PREFERRED_FORMAT)
    normalized_date = validate_burnt_area_date_string(nominal_date)
    normalized_zoom = validate_burnt_area_zoom_level(source_zoom)
    data = build_burnt_area_locator_geojson_cached(
        settings.burnt_area_tiles_root,
        dataset_version,
        normalized_date,
        normalized_zoom,
    )
    return JSONResponse(content=data, headers={"Cache-Control": "public, max-age=86400"})

@app.get("/api/layers/aemet-max-temperature")
def get_aemet_max_temperature_layer_metadata():
    """Metadatos de la capa histórica de avisos AEMET por temperaturas máximas."""
    data = build_aemet_max_temperature_layer_metadata()
    return JSONResponse(content=data, headers={"Cache-Control": "public, max-age=86400"})

@app.get("/api/aemet/max-temperature/timeline")
def get_aemet_max_temperature_timeline(
    date_from: str | None = Query(AEMET_MAX_TEMPERATURE_DEFAULT_DATE_FROM),
    date_to: str | None = Query(AEMET_MAX_TEMPERATURE_DEFAULT_DATE_TO),
):
    """Timeline diaria publicada para avisos AEMET de temperaturas máximas."""
    normalized_date_from = validate_burnt_area_date_string(date_from) if date_from else None
    normalized_date_to = validate_burnt_area_date_string(date_to) if date_to else None
    data = build_aemet_max_temperature_timeline_payload(normalized_date_from, normalized_date_to)
    return JSONResponse(content=data, headers={"Cache-Control": "public, max-age=86400"})

@app.get("/api/aemet/max-temperature/stats/daily")
def get_aemet_max_temperature_daily_stats(
    date_from: str | None = Query(AEMET_MAX_TEMPERATURE_DEFAULT_DATE_FROM),
    date_to: str | None = Query(AEMET_MAX_TEMPERATURE_DEFAULT_DATE_TO),
):
    """Serie diaria país de avisos AEMET de temperaturas máximas."""
    normalized_date_from = validate_burnt_area_date_string(date_from) if date_from else None
    normalized_date_to = validate_burnt_area_date_string(date_to) if date_to else None
    data = build_aemet_max_temperature_daily_stats_payload(normalized_date_from, normalized_date_to)
    return JSONResponse(content=data, headers={"Cache-Control": "public, max-age=86400"})

@app.get("/api/aemet/max-temperature/features")
def get_aemet_max_temperature_features(
    nominal_date: str = Query(..., alias="date"),
    warnings_only: bool = Query(True),
    bbox: str | None = Query(None, description="BBox EPSG:4326 con formato minx,miny,maxx,maxy"),
    limit: int = Query(
        AEMET_MAX_TEMPERATURE_FEATURE_LIMIT_DEFAULT,
        ge=1,
        le=AEMET_MAX_TEMPERATURE_FEATURE_LIMIT_MAX,
    ),
):
    """GeoJSON histórico de avisos AEMET por temperaturas máximas para una fecha."""
    normalized_date = validate_burnt_area_date_string(nominal_date)
    bbox_values: tuple[float, float, float, float] | None = None
    if bbox:
        try:
            coords = [float(value) for value in bbox.split(",")]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="bbox debe contener cuatro numeros") from exc
        if len(coords) != 4:
            raise HTTPException(status_code=400, detail="bbox debe tener formato minx,miny,maxx,maxy")
        minx, miny, maxx, maxy = coords
        if minx >= maxx or miny >= maxy:
            raise HTTPException(status_code=400, detail="bbox invalido: min debe ser menor que max")
        bbox_values = (minx, miny, maxx, maxy)
    data = build_aemet_max_temperature_feature_collection(
        normalized_date,
        warnings_only,
        bbox_values,
        limit,
    )
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "public, max-age=86400"},
        media_type="application/geo+json",
    )

@app.get("/api/aemet/max-temperature/tiles/{nominal_date}/{z:int}/{x:int}/{y:int}.mvt")
def get_aemet_max_temperature_vector_tile(
    nominal_date: str,
    z: int,
    x: int,
    y: int,
    warnings_only: bool = Query(True),
):
    """Teselas MVT históricas de avisos AEMET por temperaturas máximas."""
    normalized_date = validate_burnt_area_date_string(nominal_date)
    if z < 0 or x < 0 or y < 0:
        raise HTTPException(status_code=400, detail="Coordenadas de tesela no válidas")
    try:
        tile = fetch_aemet_max_temperature_vector_tile(normalized_date, z, x, y, warnings_only)
        headers = build_aemet_max_temperature_tile_cache_headers()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Error consultando tesela MVT AEMET: {exc}") from exc
    return Response(content=tile, media_type="application/vnd.mapbox-vector-tile", headers=headers)

@app.get("/api/layers/firms-history")
def get_firms_historical_layer_metadata():
    """Metadatos de la capa temporal histórica de focos NASA FIRMS."""
    data = build_firms_historical_layer_metadata()
    return JSONResponse(content=data, headers={"Cache-Control": "public, max-age=86400"})

@app.get("/api/firms/history/timeline")
def get_firms_historical_timeline(
    date_from: str | None = Query(FIRMS_HISTORICAL_DEFAULT_DATE_FROM),
    date_to: str | None = Query(FIRMS_HISTORICAL_DEFAULT_DATE_TO),
):
    """Timeline diaria publicada para el histórico FIRMS."""
    normalized_date_from = validate_burnt_area_date_string(date_from) if date_from else None
    normalized_date_to = validate_burnt_area_date_string(date_to) if date_to else None
    data = build_firms_historical_timeline_payload(normalized_date_from, normalized_date_to)
    return JSONResponse(content=data, headers={"Cache-Control": "public, max-age=86400"})

@app.get("/api/firms/history/stats/daily")
def get_firms_historical_daily_stats(
    date_from: str | None = Query(FIRMS_HISTORICAL_DEFAULT_DATE_FROM),
    date_to: str | None = Query(FIRMS_HISTORICAL_DEFAULT_DATE_TO),
):
    """Serie diaria de estadísticas país del histórico FIRMS."""
    normalized_date_from = validate_burnt_area_date_string(date_from) if date_from else None
    normalized_date_to = validate_burnt_area_date_string(date_to) if date_to else None
    data = build_firms_historical_daily_stats_payload(normalized_date_from, normalized_date_to)
    return JSONResponse(content=data, headers={"Cache-Control": "public, max-age=86400"})

@app.get("/api/firms/history/features")
def get_firms_historical_features(
    nominal_date: str = Query(..., alias="date"),
    firms_source: str | None = Query(None, alias="source"),
    bbox: str | None = Query(None, description="BBox EPSG:4326 con formato minx,miny,maxx,maxy"),
    limit: int = Query(
        FIRMS_HISTORICAL_FEATURE_LIMIT_DEFAULT,
        ge=1,
        le=FIRMS_HISTORICAL_FEATURE_LIMIT_MAX,
    ),
):
    """GeoJSON histórico de focos FIRMS para una fecha concreta."""
    normalized_date = validate_burnt_area_date_string(nominal_date)
    if firms_source is not None and firms_source not in FIRMS_HISTORICAL_SOURCES:
        raise HTTPException(status_code=400, detail="source no soportado")
    bbox_values: tuple[float, float, float, float] | None = None
    if bbox:
        try:
            coords = [float(value) for value in bbox.split(",")]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="bbox debe contener cuatro numeros") from exc
        if len(coords) != 4:
            raise HTTPException(status_code=400, detail="bbox debe tener formato minx,miny,maxx,maxy")
        minx, miny, maxx, maxy = coords
        if minx >= maxx or miny >= maxy:
            raise HTTPException(status_code=400, detail="bbox invalido: min debe ser menor que max")
        bbox_values = (minx, miny, maxx, maxy)
    data = build_firms_historical_feature_collection(
        normalized_date,
        firms_source,
        bbox_values,
        limit,
    )
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "public, max-age=86400"},
        media_type="application/geo+json",
    )
 
@app.get("/api/landcover")
def get_landcover():
    """Capa landcover filtrada publicada desde PostGIS."""
    try:
        data = fetch_landcover_feature_collection()
        headers = build_landcover_cache_headers()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Error consultando landcover en PostGIS: {exc}") from exc
    return JSONResponse(
        content=data,
        headers=headers,
        media_type="application/geo+json",
    )

@app.get("/api/layers/landcover")
def get_landcover_layer_metadata():
    """Metadatos básicos de la capa landcover publicada."""
    try:
        data = fetch_landcover_layer_metadata()
        headers = build_landcover_cache_headers()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Error consultando metadata de landcover: {exc}") from exc
    return JSONResponse(content=data, headers=headers)

@app.get("/api/landcover/features")
def get_landcover_features(
    bbox: str = Query(..., description="BBox en EPSG:4326 con formato minx,miny,maxx,maxy"),
    zoom: int = Query(6, ge=0, le=22, description="Zoom del mapa Leaflet para ajustar el nivel de detalle"),
    width: int = Query(1024, ge=1, le=10000, description="Ancho del viewport en pixeles"),
    height: int = Query(768, ge=1, le=10000, description="Alto del viewport en pixeles"),
    limit: int = Query(1000, ge=1, le=5000, description="Maximo de features devueltas por peticion"),
):
    """Features de detalle en core.landcover_polygon filtradas por bbox."""
    try:
        coords = [float(value) for value in bbox.split(",")]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="bbox debe contener cuatro numeros") from exc
    if len(coords) != 4:
        raise HTTPException(status_code=400, detail="bbox debe tener formato minx,miny,maxx,maxy")
    minx, miny, maxx, maxy = coords
    if minx >= maxx or miny >= maxy:
        raise HTTPException(status_code=400, detail="bbox invalido: min debe ser menor que max")
    try:
        data = fetch_landcover_features_by_bbox(minx, miny, maxx, maxy, zoom, width, height, limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Error consultando features landcover: {exc}") from exc
    return JSONResponse(content=data, media_type="application/geo+json")

@app.get("/api/landcover/point")
def get_landcover_point(
    lon: float = Query(..., ge=-180, le=180, description="Longitud del punto en EPSG:4326"),
    lat: float = Query(..., ge=-90, le=90, description="Latitud del punto en EPSG:4326"),
    bbox: str = Query(..., description="BBox del mapa en el CRS de consulta con formato minx,miny,maxx,maxy"),
    width: int = Query(..., ge=1, le=10000, description="Ancho del viewport en pixeles"),
    height: int = Query(..., ge=1, le=10000, description="Alto del viewport en pixeles"),
    i: int = Query(..., ge=0, description="Coordenada horizontal del pixel consultado"),
    j: int = Query(..., ge=0, description="Coordenada vertical del pixel consultado"),
    crs: str = Query("EPSG:3857", description="CRS del mapa usado para GetFeatureInfo"),
):
    """Consulta de atributos landcover por punto via GetFeatureInfo sobre el WMS de IGN."""
    try:
        data = fetch_landcover_features_by_point(lon, lat, bbox, width, height, i, j, crs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Error consultando landcover por punto: {exc}") from exc
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "no-store"},
        media_type="application/geo+json",
    )

@app.get("/api/landcover/features/{feature_id}")
def get_landcover_feature(feature_id: int):
    """Detalle de una feature individual desde core.landcover_polygon."""
    try:
        data = fetch_landcover_feature_detail(feature_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Error consultando feature landcover: {exc}") from exc
    if data is None:
        raise HTTPException(status_code=404, detail="Feature landcover no encontrada")
    return JSONResponse(content=data, media_type="application/geo+json")

@app.get("/api/landcover/tiles/{z:int}/{x:int}/{y:int}.mvt")
def get_landcover_vector_tile(z: int, x: int, y: int):
    """Vector tiles MVT de landcover servidas desde PostGIS."""
    if z < 0 or x < 0 or y < 0:
        raise HTTPException(status_code=400, detail="Coordenadas de tesela no válidas")
    try:
        tile = fetch_landcover_vector_tile(z, x, y)
        headers = build_landcover_tile_cache_headers()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Error consultando tesela MVT de landcover: {exc}") from exc
    return Response(content=tile, media_type="application/vnd.mapbox-vector-tile", headers=headers)

@app.get("/api/boundaries/spain")
def get_spain_boundary():
    """Límite territorial de España usado para recortar y filtrar capas."""
    if not os.path.exists(SPAIN_BOUNDARY_PATH):
        raise HTTPException(status_code=404, detail="No se encontró el límite de España")
    return FileResponse(SPAIN_BOUNDARY_PATH, media_type='application/geo+json')

@app.get("/api/effis/wmts")
@app.get("/api/effis/wmts/")
def get_effis_wmts_layer():
    """Capa local GeoJSON de focos EFFIS/Copernicus generada desde WMTS."""
    if not os.path.exists(EFFIS_LOCAL_FIRES_PATH):
        return {
            "type": "FeatureCollection",
            "features": [],
            "error": "Ejecuta generar_effis_wfs.py para crear la capa EFFIS local",
        }
    return FileResponse(
        EFFIS_LOCAL_FIRES_PATH,
        media_type='application/geo+json',
        headers={"Cache-Control": "no-store"},
    )

@app.get("/api/effis/wmts/{layer}/{z:int}/{y:int}/{x:int}.png")
async def get_effis_wmts_tile(layer: str, z: int, y: int, x: int):
    """Proxy local para teselas WMTS de EFFIS que fallan en algunos navegadores con HTTP/2."""
    if layer not in EFFIS_WMTS_LAYERS:
        raise HTTPException(status_code=404, detail="Capa EFFIS no permitida")
    if z < 0 or y < 0 or x < 0:
        raise HTTPException(status_code=400, detail="Coordenadas de tesela no válidas")

    params = {
        "Service": "WMTS",
        "Request": "GetTile",
        "Version": "1.0.0",
        "Layer": layer,
        "Style": "default",
        "Format": "image/png; mode=8bit",
        "TileMatrixSet": "EPSG3857",
        "TileMatrix": z,
        "TileRow": y,
        "TileCol": x,
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, trust_env=False) as client:
            r = await client.get(
                EFFIS_WMTS_BASE,
                params=params,
                headers={"Accept": "image/png,*/*", "User-Agent": "Mozilla/5.0"},
            )
            r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Error consultando EFFIS") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="No se pudo consultar EFFIS") from exc

    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "image/png"),
        headers={"Cache-Control": "public, max-age=300"},
    )
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
