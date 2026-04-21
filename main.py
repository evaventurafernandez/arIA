import csv
import gzip
import io
import json
import os
import tarfile
import xml.etree.ElementTree as ET
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from email.utils import format_datetime
 
import httpx
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic_settings import BaseSettings
from psycopg_pool import ConnectionPool
from shapely.geometry import Point, shape
from shapely.ops import unary_union


# Claves 
class Settings(BaseSettings):
    aemet_api_key: str = ""
    firms_map_key: str = ""
    firms_include_modis: bool = False
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "meteovisor"
    postgres_user: str = "meteovisor"
    postgres_password: str = "meteovisor"
    class Config:
        env_file = ".env"

settings = Settings()


# Cache en memoria 
alerts_cache:     list[dict] = []
fires_cache:      list[dict] = []
db_pool: ConnectionPool | None = None

EFFIS_WMTS_BASE = "https://maps.effis.emergency.copernicus.eu/gwist/wmts"
EFFIS_WMTS_LAYERS = {"viirs.hs.today"}
EFFIS_LOCAL_FIRES_PATH = "data/copernicus/fires/effis_viirs_hs_today_wfs.geojson"
SPAIN_BOUNDARY_PATH = "data/boundaries/spain_nuts_2024_01m.geojson"

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
FIRMS_QUERY_AREAS = (
    ("peninsula_balears_ceuta_melilla", "-10.0,35.0,4.6,44.2"),
    ("canarias", "-18.5,27.5,-13.0,29.6"),
)
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

def fetch_landcover_layer_metadata() -> dict:
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
    return row[0] if row and row[0] is not None else {
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

def fetch_landcover_publication_cache_info() -> dict:
    sql = """
    SELECT
        COUNT(*) AS feature_count,
        max(canonicalized_at) AS refreshed_at
    FROM core.landcover_polygon
    """
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
    return {
        "feature_count": row[0] if row else 0,
        "refreshed_at": row[1] if row else None,
    }

def build_landcover_cache_headers() -> dict[str, str]:
    cache_info = fetch_landcover_publication_cache_info()
    headers = {"Cache-Control": "public, max-age=300"}
    refreshed_at = cache_info["refreshed_at"]
    if refreshed_at is not None:
        refreshed_at_utc = refreshed_at.astimezone(timezone.utc)
        headers["Last-Modified"] = format_datetime(refreshed_at_utc, usegmt=True)
        headers["ETag"] = f'W/"landcover-{cache_info["feature_count"]}-{int(refreshed_at_utc.timestamp())}"'
    return headers

def build_landcover_tile_cache_headers() -> dict[str, str]:
    headers = build_landcover_cache_headers()
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

def fetch_landcover_vector_tile(z: int, x: int, y: int) -> bytes:
    tolerance = get_landcover_tile_simplification_tolerance(z)
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
    with get_db_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL max_parallel_workers_per_gather = 0")
            cur.execute(sql, (z, x, y, tolerance, tolerance))
            row = cur.fetchone()
    if not row or row[0] is None:
        return b""
    return bytes(row[0])

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
    if frp >= 50: return "Rojo",    "#CC0000"
    if frp >= 10: return "Naranja", "#FFA500"
    return              "Amarillo", "#FFD700"

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

def _format_acq_datetime_utc(acq_date: str, acq_time: str) -> str:
    if not acq_date:
        return ""
    time = (acq_time or "").zfill(4)
    if len(time) != 4 or not time.isdigit():
        return f"{acq_date}T00:00:00Z"
    return f"{acq_date}T{time[:2]}:{time[2:]}:00Z"

async def fetch_firms_csv(
    client: httpx.AsyncClient,
    source: str,
    area_coordinates: str,
) -> str:
    url = f"{FIRMS_API_BASE}/{settings.firms_map_key}/{source}/{area_coordinates}/{FIRMS_DAY_RANGE}"
    r = await client.get(url)
    r.raise_for_status()
    return r.text

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
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, trust_env=False) as client:
        results = await asyncio.gather(
            *[
                fetch_firms_csv(client, source, area_coordinates)
                for source, _, area_coordinates in requests
            ],
            return_exceptions=True,
        )

    fires = []
    excluded = 0
    errors = []
    for (source, area_name, _), result in zip(requests, results):
        if isinstance(result, Exception):
            errors.append(f"{source}/{area_name}: {result}")
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
        unique.values(),
        key=lambda f: (f.get("acq_datetime_utc") or "", float(f.get("frp") or 0)),
        reverse=True,
    )
    print(f"  FIRMS: {len(fires)} focos en Espana, {excluded} excluidos")
    return fires

fetch_firms_fires = fetch_spain_hotspots


# Lifespan 
@asynccontextmanager
async def lifespan(app: FastAPI):
    global alerts_cache, fires_cache, db_pool
    print("Cargando geometria de Espana...")
    await load_spain_geometry()

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
        print(
            "  CORINE listo "
            f"(pub.landcover_filtered={landcover_count} clases publicadas, "
            f"pub.landcover_mvt_source={landcover_tile_count} features para MVT)"
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
    print("NASA FIRMS se consultara en vivo al cargar el visor")
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
 
@app.get("/api/stats")
def get_stats():
    """Estadísticas básicas de los datos cargados."""
    level_count      = {}
    fire_level_count = {}
    for a in alerts_cache:
        level_count[a["level"]] = level_count.get(a["level"], 0) + 1
    for f in fires_cache:
        fire_level_count[f["level"]] = fire_level_count.get(f["level"], 0) + 1
    return {
        "alerts": {
            "total":     len(alerts_cache),
            "por_nivel": level_count,
        },
        "fires": {
            "total":     len(fires_cache),
            "por_nivel": fire_level_count,
            "frp_max":   max((f["frp"] for f in fires_cache), default=0),
        },
    }
 
@app.get("/api/landcover")
def get_landcover():
    """Cobertura forestal filtrada publicada desde PostGIS."""
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
    return FileResponse(EFFIS_LOCAL_FIRES_PATH, media_type='application/geo+json')

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
