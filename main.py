import csv
import gzip
import io
import json
import os
import tarfile
import xml.etree.ElementTree as ET
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
 
import httpx
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic_settings import BaseSettings
from shapely.geometry import Point, shape
from shapely.ops import unary_union


# Claves 
class Settings(BaseSettings):
    aemet_api_key: str
    firms_map_key: str = ""
    firms_include_modis: bool = False
    class Config:
        env_file = ".env"

settings = Settings()


# Cache en memoria 
alerts_cache:     list[dict] = []
fires_cache:      list[dict] = []

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
    global alerts_cache, fires_cache
    print("Cargando geometria de Espana...")
    await load_spain_geometry()
 
    # Verificar que el GeoJSON de landcover existe
    if not os.path.exists('data/landcover.geojson'):
        print("  AVISO: data/landcover.geojson no encontrado.")
        print("  Ejecuta primero: python generar_landcover.py")
    else:
        size_mb = os.path.getsize('data/landcover.geojson') / 1024 / 1024
        print(f"  CORINE landcover.geojson listo ({size_mb:.1f} MB)")
 
    print("Cargando datos de AEMET...")
    alerts_cache = await fetch_aemet_alerts()
    print(f"  → {len(alerts_cache)} avisos cargados")
    fires_cache = []
    print("NASA FIRMS se consultara en vivo al cargar el visor")
    yield
 

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
    """Cobertura forestal filtrada de CORINE Land Cover 2018 (IGN/CNIG)."""
    path = 'data/landcover.geojson'
    if not os.path.exists(path):
        return {"type": "FeatureCollection", "features": [], "error": "Ejecuta generar_landcover.py"}
    return FileResponse(path, media_type='application/geo+json')

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
