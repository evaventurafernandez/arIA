import csv
import gzip
import io
import json
import os
import tarfile
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from datetime import datetime
 
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic_settings import BaseSettings
from shapely.geometry import Point, shape
from shapely.ops import unary_union


# ── Configuración ──────────────────────────────────────────────────────────
class Settings(BaseSettings):
    aemet_api_key: str
    firms_map_key: str = ""
    class Config:
        env_file = ".env"

settings = Settings()


# ── Cache en memoria ───────────────────────────────────────────────────────
alerts_cache:     list[dict] = []
fires_cache:      list[dict] = []

# ── AEMET: parseo CAP ─────────────────────────────────────────────────────
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


# ── NASA FIRMS ────────────────────────────────────────────────────────────
SPAIN_BBOX = "-9.5,35.9,4.5,43.8"
_SPAIN_GEOM = None

async def load_spain_geometry():
    global _SPAIN_GEOM
    url = "https://raw.githubusercontent.com/georgique/world-geojson/develop/countries/spain.json"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            r.raise_for_status()
            geojson = r.json()
        features = geojson.get("features", [geojson]) if "features" in geojson else [geojson]
        geometries = [shape(f["geometry"]) for f in features if f.get("geometry")]
        _SPAIN_GEOM = unary_union(geometries)
        print("  Geometria de Espana cargada correctamente")
    except Exception as e:
        print(f"  Error cargando geometria: {e} — usando bbox de respaldo")
        from shapely.geometry import box
        _SPAIN_GEOM = unary_union([
            box(-9.3, 36.0, 3.3, 43.8),
            box(1.1, 38.6, 4.4, 40.1),
            box(-18.2, 27.6, -13.3, 29.5),
            box(-5.4, 35.85, -5.2, 35.95),
            box(-2.97, 35.26, -2.93, 35.30),
        ])

def is_in_spain(lat: float, lon: float) -> bool:
    if _SPAIN_GEOM is None:
        return True
    return _SPAIN_GEOM.contains(Point(lon, lat))

def classify_frp(frp: float) -> tuple[str, str]:
    if frp >= 50: return "Rojo",    "#CC0000"
    if frp >= 10: return "Naranja", "#FFA500"
    return              "Amarillo", "#FFD700"

async def fetch_firms_fires() -> list[dict]:
    if not settings.firms_map_key:
        return []
    url = (f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
           f"{settings.firms_map_key}/VIIRS_SNPP_NRT/{SPAIN_BBOX}/1")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        r.raise_for_status()
        text = r.text

    fires = []
    excluded = 0
    for row in csv.DictReader(io.StringIO(text)):
        try:
            if row.get("confidence", "l").strip().lower() == "l":
                continue
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            if not is_in_spain(lat, lon):
                excluded += 1
                continue
            frp = float(row.get("frp", 0))
            level, color = classify_frp(frp)
            date = row.get("acq_date", "")
            time = row.get("acq_time", "").zfill(4)
            fires.append({
                "id":          f"{lat}_{lon}_{date}_{time}",
                "latitude":    lat,
                "longitude":   lon,
                "frp":         frp,
                "confidence":  row.get("confidence", "").strip(),
                "level":       level,
                "level_color": color,
                "acq_date":    date,
                "acq_time":    time,
                "satellite":   row.get("satellite", ""),
                "daynight":    row.get("daynight", ""),
                "source":      "firms",
            })
        except Exception:
            pass
    print(f"  FIRMS: {len(fires)} focos en Espana, {excluded} excluidos")
    return fires


# ── Lifespan ──────────────────────────────────────────────────────────────
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
    print("Cargando datos de NASA FIRMS...")
    fires_cache = await fetch_firms_fires()
    print(f"  → {len(fires_cache)} focos cargados")
    yield
 

# ── App ───────────────────────────────────────────────────────────────────
app = FastAPI(title="MeteoVisor Demo", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Endpoints ─────────────────────────────────────────────────────────────
@app.get("/api/alerts")
def get_alerts():
    """Avisos meteorológicos activos de AEMET."""
    return alerts_cache
 
@app.get("/api/fires")
def get_fires():
    """Focos de incendio activos de NASA FIRMS."""
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
    """
    Cobertura forestal filtrada de CORINE Land Cover 2018 (IGN/CNIG).
    Clases: bosques, matorrales y cultivos con mayor riesgo de incendio.
    Sirve el fichero pre-procesado data/landcover.geojson directamente.
    Genera el fichero ejecutando: python generar_landcover.py
    """
    path = 'data/landcover.geojson'
    if not os.path.exists(path):
        return {"type": "FeatureCollection", "features": [], "error": "Ejecuta generar_landcover.py"}
    return FileResponse(path, media_type='application/geo+json')
 
 
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
 