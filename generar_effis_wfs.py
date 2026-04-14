"""
Genera una capa vectorial local de focos EFFIS/Copernicus a partir de teselas WMTS.

Uso básico, con el backend local arrancado:
    python generar_effis_wfs.py

Uso directo contra el WMTS remoto de EFFIS:
    python generar_effis_wfs.py --source effis

La salida por defecto se escribe en:
    data/copernicus/fires/effis_viirs_hs_today_wfs.geojson

Nota: WFS es un servicio, no un formato de archivo. Este script genera un
GeoJSON local compatible con una capa vectorial tipo WFS. Como el origen WMTS
son imágenes PNG, las features se derivan de los píxeles no transparentes y no
incluyen los atributos originales de un servicio WFS nativo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urlencode

import httpx

try:
    from PIL import Image, UnidentifiedImageError
except ImportError as exc:
    raise SystemExit(
        "Falta la dependencia Pillow. Instálala con: pip install pillow"
    ) from exc


DEFAULT_LAYER = "viirs.hs.today"
DEFAULT_ENDPOINT_URL = "http://127.0.0.1:8000/api/effis/wmts"
EFFIS_WMTS_BASE = "https://maps.effis.emergency.copernicus.eu/gwist/wmts"
EFFIS_WMS_BASE = "https://maps.effis.emergency.copernicus.eu/gwis"
WEB_MERCATOR_EXTENT = 20037508.342789244
DEFAULT_OUTPUT_DIR = Path("data/copernicus/fires")
DEFAULT_BBOX = (-18.5, 27.5, 4.5, 43.9)
MERCATOR_LAT_LIMIT = 85.05112878
DEFAULT_TILE_SIZE = 0


@dataclass(frozen=True)
class Tile:
    x: int
    y: int


@dataclass(frozen=True)
class Component:
    tile_x: int
    tile_y: int
    tile_width: int
    tile_height: int
    min_px: int
    min_py: int
    max_px: int
    max_py: int
    centroid_px: float
    centroid_py: float
    pixel_count: int
    avg_color: str


@dataclass
class TileResult:
    tile: Tile
    ok: bool
    empty: bool
    features: list[dict]
    error: str | None = None
    used_fallback: bool = False


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    try:
        parts = [float(part.strip()) for part in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "El bbox debe tener el formato min_lon,min_lat,max_lon,max_lat"
        ) from exc

    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "El bbox debe tener 4 valores: min_lon,min_lat,max_lon,max_lat"
        )

    min_lon, min_lat, max_lon, max_lat = parts
    if min_lon >= max_lon or min_lat >= max_lat:
        raise argparse.ArgumentTypeError(
            "El bbox no es válido: min_lon < max_lon y min_lat < max_lat"
        )
    if min_lat < -MERCATOR_LAT_LIMIT or max_lat > MERCATOR_LAT_LIMIT:
        raise argparse.ArgumentTypeError(
            f"El bbox debe estar dentro de Web Mercator (+/-{MERCATOR_LAT_LIMIT})"
        )
    return min_lon, min_lat, max_lon, max_lat


def sanitize_layer_name(layer: str) -> str:
    return layer.replace("/", "_").replace("\\", "_").replace(".", "_")


def lon_to_tile_x(lon: float, zoom: int) -> int:
    n = 2**zoom
    x = int(math.floor((lon + 180.0) / 360.0 * n))
    return min(max(x, 0), n - 1)


def lat_to_tile_y(lat: float, zoom: int) -> int:
    lat = min(max(lat, -MERCATOR_LAT_LIMIT), MERCATOR_LAT_LIMIT)
    lat_rad = math.radians(lat)
    n = 2**zoom
    y = int(
        math.floor(
            (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi)
            / 2.0
            * n
        )
    )
    return min(max(y, 0), n - 1)


def pixel_to_lonlat(
    zoom: int,
    tile_x: int,
    tile_y: int,
    px: float,
    py: float,
    tile_width: int,
    tile_height: int,
) -> tuple[float, float]:
    n = 2**zoom
    global_x = tile_x + px / tile_width
    global_y = tile_y + py / tile_height
    lon = global_x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * global_y / n)))
    lat = math.degrees(lat_rad)
    return lon, lat


def tile_to_web_mercator_bbox(zoom: int, tile: Tile) -> tuple[float, float, float, float]:
    n = 2**zoom
    tile_span = 2 * WEB_MERCATOR_EXTENT / n
    min_x = -WEB_MERCATOR_EXTENT + tile.x * tile_span
    max_x = -WEB_MERCATOR_EXTENT + (tile.x + 1) * tile_span
    max_y = WEB_MERCATOR_EXTENT - tile.y * tile_span
    min_y = WEB_MERCATOR_EXTENT - (tile.y + 1) * tile_span
    return min_x, min_y, max_x, max_y


def iter_tiles(
    bbox: tuple[float, float, float, float],
    zoom: int,
    limit_tiles: int,
) -> list[Tile]:
    min_lon, min_lat, max_lon, max_lat = bbox
    x_min = lon_to_tile_x(min_lon, zoom)
    x_max = lon_to_tile_x(max_lon, zoom)
    y_min = lat_to_tile_y(max_lat, zoom)
    y_max = lat_to_tile_y(min_lat, zoom)

    tiles = [Tile(x, y) for y in range(y_min, y_max + 1) for x in range(x_min, x_max + 1)]
    if limit_tiles > 0:
        return tiles[:limit_tiles]
    return tiles


def tile_url(endpoint_url: str, layer: str, zoom: int, tile: Tile) -> str:
    layer_path = quote(layer, safe="")
    return f"{endpoint_url.rstrip('/')}/{layer_path}/{zoom}/{tile.y}/{tile.x}.png"


async def fetch_wms_fallback(
    client: httpx.AsyncClient,
    args: argparse.Namespace,
    tile: Tile,
) -> bytes:
    min_x, min_y, max_x, max_y = tile_to_web_mercator_bbox(args.zoom, tile)
    size = args.tile_size or args.wms_size
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": args.layer,
        "STYLES": args.style,
        "FORMAT": "image/png",
        "TRANSPARENT": "true",
        "SRS": "EPSG:3857",
        "BBOX": f"{min_x},{min_y},{max_x},{max_y}",
        "WIDTH": size,
        "HEIGHT": size,
    }
    query = urlencode(params, quote_via=quote)
    response = await client.get(
        f"{args.wms_fallback_url}?{query}",
        headers={"Accept": "image/png,*/*", "User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    if response.content.lstrip().startswith(b"<"):
        raise RuntimeError("El fallback WMS devolvió XML/HTML, no PNG")
    return response.content


async def fetch_tile(
    client: httpx.AsyncClient,
    args: argparse.Namespace,
    tile: Tile,
) -> tuple[bytes, bool]:
    if args.source == "endpoint":
        url = tile_url(args.endpoint_url, args.layer, args.zoom, tile)
        request_kwargs = {"url": url}
    else:
        if args.effis_request_mode == "rest":
            layer = quote(args.layer, safe="")
            style = quote(args.style, safe="")
            tile_matrix_set = quote(args.tile_matrix_set, safe="")
            url = (
                f"{args.effis_wmts_url.rstrip('/')}/1.0.0/"
                f"{layer}/{style}/{tile_matrix_set}/{args.zoom}/{tile.y}/{tile.x}.png"
            )
            request_kwargs = {"url": url}
        else:
            params = {
                "Service": "WMTS",
                "Request": "GetTile",
                "Version": "1.0.0",
                "Layer": args.layer,
                "Style": args.style,
                "Format": args.format,
                "TileMatrixSet": args.tile_matrix_set,
                "TileMatrix": args.zoom,
                "TileRow": tile.y,
                "TileCol": tile.x,
            }
            query = urlencode(params, quote_via=quote)
            request_kwargs = {"url": f"{args.effis_wmts_url}?{query}"}

    last_error: Exception | None = None
    for attempt in range(args.retries + 1):
        try:
            response = await client.get(
                headers={"Accept": "image/png,*/*", "User-Agent": "Mozilla/5.0"},
                **request_kwargs,
            )
            response.raise_for_status()
            if response.content.lstrip().startswith(b"<"):
                raise RuntimeError("La respuesta parece XML/HTML, no PNG")
            return response.content, False
        except (httpx.HTTPError, RuntimeError) as exc:
            last_error = exc
            if attempt < args.retries:
                await asyncio.sleep(0.5 * (attempt + 1))

    if args.wms_fallback:
        try:
            return await fetch_wms_fallback(client, args, tile), True
        except (httpx.HTTPError, RuntimeError) as exc:
            last_error = exc

    assert last_error is not None
    raise last_error


def rgba_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def extract_components(
    png_bytes: bytes,
    tile: Tile,
    args: argparse.Namespace,
) -> list[Component]:
    try:
        image = Image.open(BytesIO(png_bytes)).convert("RGBA")
    except UnidentifiedImageError:
        raise RuntimeError("La tesela descargada no es una imagen PNG válida")

    width, height = image.size
    if args.tile_size and (width != args.tile_size or height != args.tile_size):
        raise RuntimeError(f"Tamaño de tesela inesperado: {width}x{height}")

    alpha_mask = image.getchannel("A").point(
        lambda alpha: 255 if alpha >= args.min_alpha else 0
    )
    active_bbox = alpha_mask.getbbox()
    if active_bbox is None:
        return []

    pixels = image.load()
    alpha_pixels = alpha_mask.load()
    mask = bytearray(width * height)
    left, top, right, bottom = active_bbox
    for py in range(top, bottom):
        row = py * width
        for px in range(left, right):
            if not alpha_pixels[px, py]:
                continue
            r, g, b, _ = pixels[px, py]
            if args.skip_near_white and r >= 245 and g >= 245 and b >= 245:
                continue
            mask[row + px] = 1

    visited = bytearray(width * height)
    components: list[Component] = []

    for start_idx, is_target in enumerate(mask):
        if not is_target or visited[start_idx]:
            continue

        stack = [start_idx]
        visited[start_idx] = 1
        min_px = max_px = start_idx % width
        min_py = max_py = start_idx // width
        sum_px = 0
        sum_py = 0
        sum_r = 0
        sum_g = 0
        sum_b = 0
        count = 0

        while stack:
            idx = stack.pop()
            px = idx % width
            py = idx // width
            r, g, b, _ = pixels[px, py]

            min_px = min(min_px, px)
            max_px = max(max_px, px)
            min_py = min(min_py, py)
            max_py = max(max_py, py)
            sum_px += px
            sum_py += py
            sum_r += r
            sum_g += g
            sum_b += b
            count += 1

            for ny in range(max(0, py - 1), min(height, py + 2)):
                row = ny * width
                for nx in range(max(0, px - 1), min(width, px + 2)):
                    next_idx = row + nx
                    if mask[next_idx] and not visited[next_idx]:
                        visited[next_idx] = 1
                        stack.append(next_idx)

        if count < args.min_pixels:
            continue

        components.append(
            Component(
                tile_x=tile.x,
                tile_y=tile.y,
                tile_width=width,
                tile_height=height,
                min_px=min_px,
                min_py=min_py,
                max_px=max_px,
                max_py=max_py,
                centroid_px=sum_px / count + 0.5,
                centroid_py=sum_py / count + 0.5,
                pixel_count=count,
                avg_color=rgba_to_hex(sum_r // count, sum_g // count, sum_b // count),
            )
        )

    return components


def component_to_feature(
    component: Component,
    args: argparse.Namespace,
) -> dict:
    lon, lat = pixel_to_lonlat(
        args.zoom,
        component.tile_x,
        component.tile_y,
        component.centroid_px,
        component.centroid_py,
        component.tile_width,
        component.tile_height,
    )
    west, north = pixel_to_lonlat(
        args.zoom,
        component.tile_x,
        component.tile_y,
        component.min_px,
        component.min_py,
        component.tile_width,
        component.tile_height,
    )
    east, south = pixel_to_lonlat(
        args.zoom,
        component.tile_x,
        component.tile_y,
        component.max_px + 1,
        component.max_py + 1,
        component.tile_width,
        component.tile_height,
    )

    properties = {
        "id": (
            f"{args.layer}:{args.zoom}:{component.tile_x}:{component.tile_y}:"
            f"{component.min_px}:{component.min_py}:{component.pixel_count}"
        ),
        "source": "effis_wmts",
        "source_mode": args.source,
        "layer": args.layer,
        "zoom": args.zoom,
        "tile_x": component.tile_x,
        "tile_y": component.tile_y,
        "pixel_count": component.pixel_count,
        "pixel_bbox": [
            component.min_px,
            component.min_py,
            component.max_px,
            component.max_py,
        ],
        "bbox_wgs84": [west, south, east, north],
        "avg_color": component.avg_color,
    }

    if args.geometry == "bbox":
        geometry = {
            "type": "Polygon",
            "coordinates": [
                [
                    [west, south],
                    [east, south],
                    [east, north],
                    [west, north],
                    [west, south],
                ]
            ],
        }
    else:
        geometry = {"type": "Point", "coordinates": [lon, lat]}

    return {
        "type": "Feature",
        "id": properties["id"],
        "geometry": geometry,
        "properties": properties,
    }


async def process_tile(
    client: httpx.AsyncClient,
    args: argparse.Namespace,
    tile: Tile,
) -> TileResult:
    try:
        content, used_fallback = await fetch_tile(client, args, tile)
        components = extract_components(content, tile, args)
        features = [component_to_feature(component, args) for component in components]
        return TileResult(tile=tile, ok=True, empty=not features, features=features, used_fallback=used_fallback)
    except Exception as exc:
        if args.fail_fast:
            raise
        return TileResult(tile=tile, ok=False, empty=True, features=[], error=str(exc))


async def build_features(
    args: argparse.Namespace,
    tiles: list[Tile],
) -> tuple[list[dict], dict]:
    total = len(tiles)
    features: list[dict] = []
    failed_tiles: list[dict] = []
    empty_tiles = 0
    ok_tiles = 0
    fallback_tiles = 0
    processed = 0

    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    async with httpx.AsyncClient(
        timeout=args.timeout,
        follow_redirects=True,
        trust_env=False,
        limits=limits,
    ) as client:
        semaphore = asyncio.Semaphore(args.concurrency)

        async def guarded_process(tile: Tile) -> TileResult:
            async with semaphore:
                return await process_tile(client, args, tile)

        tasks = [asyncio.create_task(guarded_process(tile)) for tile in tiles]
        for task in asyncio.as_completed(tasks):
            result = await task
            processed += 1
            if result.ok:
                ok_tiles += 1
                if result.empty:
                    empty_tiles += 1
                if result.used_fallback:
                    fallback_tiles += 1
                features.extend(result.features)
            else:
                failed_tiles.append(
                    {
                        "x": result.tile.x,
                        "y": result.tile.y,
                        "error": result.error,
                    }
                )

            if args.max_features > 0 and len(features) >= args.max_features:
                for pending in tasks:
                    if not pending.done():
                        pending.cancel()
                features = features[: args.max_features]
                break

            if processed == total or processed % args.progress_every == 0 or result.features:
                print(
                    f"  Teselas procesadas: {processed}/{total} | "
                    f"features: {len(features)} | fallback: {fallback_tiles} | fallos: {len(failed_tiles)}",
                    end="\r",
                    flush=True,
                )

    print()
    features.sort(
        key=lambda feature: (
            feature["properties"]["tile_y"],
            feature["properties"]["tile_x"],
            feature["properties"]["pixel_bbox"][1],
            feature["properties"]["pixel_bbox"][0],
        )
    )
    stats = {
        "tiles_total": total,
        "tiles_ok": ok_tiles,
        "tiles_empty": empty_tiles,
        "tiles_fallback_wms": fallback_tiles,
        "tiles_failed": len(failed_tiles),
        "failed_tiles": failed_tiles,
    }
    return features, stats


def make_feature_collection(
    args: argparse.Namespace,
    features: list[dict],
    stats: dict,
) -> dict:
    return {
        "type": "FeatureCollection",
        "name": f"effis_{sanitize_layer_name(args.layer)}_wfs_local",
        "metadata": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "EFFIS Copernicus WMTS",
            "source_mode": args.source,
            "endpoint_url": args.endpoint_url if args.source == "endpoint" else None,
            "effis_wmts_url": args.effis_wmts_url if args.source == "effis" else None,
            "effis_request_mode": args.effis_request_mode if args.source == "effis" else None,
            "wms_fallback": args.wms_fallback,
            "wms_fallback_url": args.wms_fallback_url if args.wms_fallback else None,
            "tiles_fallback_wms": stats["tiles_fallback_wms"],
            "layer": args.layer,
            "zoom": args.zoom,
            "bbox": list(args.bbox),
            "geometry": args.geometry,
            "min_alpha": args.min_alpha,
            "min_pixels": args.min_pixels,
            "tile_size": args.tile_size or "auto",
            "tiles_total": stats["tiles_total"],
            "tiles_ok": stats["tiles_ok"],
            "tiles_empty": stats["tiles_empty"],
            "tiles_failed": stats["tiles_failed"],
            "failed_tiles": stats["failed_tiles"],
            "warning": (
                "Capa vectorial derivada de teselas WMTS PNG; no contiene "
                "atributos originales de un WFS nativo."
            ),
        },
        "features": features,
    }


def output_path(args: argparse.Namespace) -> Path:
    if args.output:
        return args.output
    filename = f"effis_{sanitize_layer_name(args.layer)}_wfs.geojson"
    return args.output_dir / filename


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Debe ser un entero positivo")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("Debe ser 0 o un entero positivo")
    return parsed


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Genera un GeoJSON vectorial local de focos EFFIS/Copernicus "
            "a partir del endpoint WMTS del proyecto o del WMTS remoto."
        )
    )
    parser.add_argument("--layer", default=DEFAULT_LAYER, help=f"Capa WMTS. Por defecto: {DEFAULT_LAYER}")
    parser.add_argument("--zoom", type=non_negative_int, default=8, help="Zoom WMTS que se descargará. Por defecto: 8")
    parser.add_argument(
        "--bbox",
        type=parse_bbox,
        default=DEFAULT_BBOX,
        help="Bbox WGS84 como min_lon,min_lat,max_lon,max_lat. Por defecto: España e islas.",
    )
    parser.add_argument(
        "--source",
        choices=("endpoint", "effis"),
        default="endpoint",
        help="Origen de teselas: endpoint local o WMTS remoto EFFIS. Por defecto: endpoint.",
    )
    parser.add_argument(
        "--endpoint-url",
        default=DEFAULT_ENDPOINT_URL,
        help=f"Base del endpoint local. Por defecto: {DEFAULT_ENDPOINT_URL}",
    )
    parser.add_argument(
        "--effis-wmts-url",
        default=EFFIS_WMTS_BASE,
        help=f"URL WMTS remoto EFFIS. Por defecto: {EFFIS_WMTS_BASE}",
    )
    parser.add_argument(
        "--effis-request-mode",
        choices=("rest", "kvp"),
        default="rest",
        help="Modo de petición al WMTS remoto para --source effis. Por defecto: rest",
    )
    parser.add_argument(
        "--wms-fallback-url",
        default=EFFIS_WMS_BASE,
        help=f"URL WMS de respaldo para teselas WMTS fallidas. Por defecto: {EFFIS_WMS_BASE}",
    )
    parser.add_argument(
        "--wms-size",
        type=positive_int,
        default=1024,
        help="Tamaño en píxeles usado por el fallback WMS cuando --tile-size es 0. Por defecto: 1024",
    )
    parser.add_argument(
        "--no-wms-fallback",
        dest="wms_fallback",
        action="store_false",
        help="Desactiva el fallback WMS para teselas WMTS fallidas.",
    )
    parser.set_defaults(wms_fallback=True)
    parser.add_argument("--style", default="default", help="Estilo WMTS para --source effis. Por defecto: default")
    parser.add_argument(
        "--format",
        default="image/png; mode=8bit",
        help='Formato WMTS para --source effis. Por defecto: "image/png; mode=8bit"',
    )
    parser.add_argument(
        "--tile-matrix-set",
        default="EPSG3857",
        help="TileMatrixSet WMTS para --source effis. Por defecto: EPSG3857",
    )
    parser.add_argument(
        "--geometry",
        choices=("point", "bbox"),
        default="point",
        help="Geometría de salida por componente detectado. Por defecto: point",
    )
    parser.add_argument(
        "--min-alpha",
        type=non_negative_int,
        default=10,
        help="Alpha mínimo para considerar un píxel como foco. Por defecto: 10",
    )
    parser.add_argument(
        "--min-pixels",
        type=positive_int,
        default=3,
        help="Tamaño mínimo de un componente en píxeles. Por defecto: 3",
    )
    parser.add_argument(
        "--skip-near-white",
        action="store_true",
        help="Ignora píxeles casi blancos aunque tengan alpha suficiente.",
    )
    parser.add_argument(
        "--tile-size",
        type=non_negative_int,
        default=DEFAULT_TILE_SIZE,
        help="Tamaño esperado de tesela en píxeles. 0 autodetecta el tamaño real. Por defecto: 0",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directorio de salida. Por defecto: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument("--output", type=Path, help="Ruta exacta de salida GeoJSON. Si se indica, ignora --output-dir.")
    parser.add_argument("--timeout", type=float, default=20.0, help="Timeout HTTP por petición. Por defecto: 20")
    parser.add_argument("--retries", type=non_negative_int, default=2, help="Reintentos por tesela. Por defecto: 2")
    parser.add_argument("--concurrency", type=positive_int, default=8, help="Descargas simultáneas. Por defecto: 8")
    parser.add_argument(
        "--progress-every",
        type=positive_int,
        default=25,
        help="Frecuencia de progreso en número de teselas. Por defecto: 25",
    )
    parser.add_argument(
        "--limit-tiles",
        type=non_negative_int,
        default=0,
        help="Limita el número de teselas procesadas. 0 significa sin límite.",
    )
    parser.add_argument(
        "--max-features",
        type=non_negative_int,
        default=0,
        help="Limita el número de features generadas. 0 significa sin límite.",
    )
    parser.add_argument("--fail-fast", action="store_true", help="Detiene el proceso ante el primer error HTTP/PNG.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra las teselas que se procesarían, sin descargar.")
    return parser.parse_args(list(argv))


async def async_main(args: argparse.Namespace) -> int:
    tiles = iter_tiles(args.bbox, args.zoom, args.limit_tiles)
    output = output_path(args)

    print("Generando capa vectorial EFFIS/Copernicus")
    print(f"  Capa: {args.layer}")
    print(f"  Origen: {args.source}")
    if args.source == "endpoint":
        print(f"  Endpoint: {args.endpoint_url}")
    else:
        print(f"  WMTS remoto: {args.effis_wmts_url}")
        print(f"  Fallback WMS: {'sí' if args.wms_fallback else 'no'}")
    print(f"  Zoom: {args.zoom}")
    print(f"  Bbox: {','.join(str(v) for v in args.bbox)}")
    print(f"  Teselas: {len(tiles)}")
    print(f"  Salida: {output}")

    if args.dry_run:
        for tile in tiles:
            print(f"    z={args.zoom} y={tile.y} x={tile.x}")
        return 0

    features, stats = await build_features(args, tiles)
    if stats["tiles_ok"] == 0 and stats["tiles_failed"] > 0:
        print("No se pudo descargar ninguna tesela correctamente.", file=sys.stderr)
        return 2

    feature_collection = make_feature_collection(args, features, stats)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(feature_collection, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    size_mb = output.stat().st_size / 1024 / 1024
    print(f"Guardado: {output}")
    print(f"  Features: {len(features)}")
    print(f"  Teselas correctas: {stats['tiles_ok']}/{stats['tiles_total']}")
    print(f"  Teselas vacías: {stats['tiles_empty']}")
    print(f"  Teselas con fallback WMS: {stats['tiles_fallback_wms']}")
    print(f"  Teselas con fallo: {stats['tiles_failed']}")
    print(f"  Tamaño: {size_mb:.2f} MB")
    if stats["tiles_failed"]:
        print("  Revisa metadata.failed_tiles en el GeoJSON si necesitas depurar fallos.")

    return 0


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("\nProceso interrumpido.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())