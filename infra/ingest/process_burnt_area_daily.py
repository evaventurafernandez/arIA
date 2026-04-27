#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
from osgeo import gdal


EARTH_AUTHALIC_RADIUS_METERS = 6371007.181
CATALOG_ENTRY_PATHS = {
    ("v3", "cog"): ("bio-geophysical/burnt_area/ba_global_300m_daily_v3/cog.csv", "ba_global_300m_daily_v3/cog.csv"),
    ("v3", "nc"): ("bio-geophysical/burnt_area/ba_global_300m_daily_v3/nc.csv", "ba_global_300m_daily_v3/nc.csv"),
    ("v4", "cog"): ("bio-geophysical/burnt_area/ba_global_300m_daily_v4/cog.csv", "ba_global_300m_daily_v4/cog.csv"),
    ("v4", "nc"): ("bio-geophysical/burnt_area/ba_global_300m_daily_v4/nc.csv", "ba_global_300m_daily_v4/nc.csv"),
}

gdal.UseExceptions()


@dataclass(frozen=True)
class CatalogItem:
    nominal_date: str
    product_name: str
    remote_uri: str
    content_length_bytes: int
    checksum_value: str | None


@dataclass
class TemporaryS3Credentials:
    access_id: str
    secret: str
    bearer_token: str | None = None


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root_dir = repo_root()
    parser = argparse.ArgumentParser(
        description="Procesa burnt area diaria Copernicus CLMS a recortes España, tiles PNG y manifiestos."
    )
    parser.add_argument("--catalog-root", default=str(root_dir / "data/copernicus/data_burnt_areas"))
    parser.add_argument("--dataset-version", default="v4", choices=["v3", "v4"])
    parser.add_argument("--delivery-format", default="cog", choices=["cog", "nc"])
    parser.add_argument("--date-from", default="2025-05-01")
    parser.add_argument("--date-to", default="2025-08-31")
    parser.add_argument("--mode", default="daily", choices=["daily", "cumulative"])
    parser.add_argument("--spain-boundary", default=str(root_dir / "data/boundaries/spain_nuts_2024_01m.geojson"))
    parser.add_argument("--local-source-root", default=str(root_dir / "data/copernicus/burnt_area/raw"))
    parser.add_argument("--spain-cog-root", default=str(root_dir / "data/copernicus/burnt_area/spain_cog"))
    parser.add_argument("--tiles-root", default=str(root_dir / "data/copernicus/burnt_area/tiles"))
    parser.add_argument("--visual-root", default=str(root_dir / "tmp/burnt_area_visual"))
    parser.add_argument("--manifest-root", default=str(root_dir / "data/copernicus/burnt_area/manifests"))
    parser.add_argument("--temp-root", default=str(root_dir / "tmp/burnt_area_pipeline"))
    parser.add_argument("--min-zoom", type=int, default=4)
    parser.add_argument("--max-zoom", type=int, default=10)
    parser.add_argument("--tile-processes", type=int, default=max(1, os.cpu_count() or 1))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-remote", action="store_true")
    return parser.parse_args()


def normalized_rel_path(path: Path, root_dir: Path) -> str:
    return path.resolve().relative_to(root_dir.resolve()).as_posix()


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def find_catalog_csv(catalog_root: Path, dataset_version: str, delivery_format: str) -> Path:
    for rel_path in CATALOG_ENTRY_PATHS[(dataset_version, delivery_format)]:
        candidate = catalog_root / rel_path
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"No se encontro el catalogo {dataset_version}/{delivery_format} en {catalog_root}"
    )


def load_catalog_items(
    catalog_root: Path,
    dataset_version: str,
    delivery_format: str,
    date_from: str,
    date_to: str,
) -> list[CatalogItem]:
    csv_path = find_catalog_csv(catalog_root, dataset_version, delivery_format)
    selected: list[CatalogItem] = []
    with csv_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            nominal_date = (row.get("nominaldate") or "")[:10]
            if not nominal_date or nominal_date < date_from or nominal_date > date_to:
                continue
            selected.append(
                CatalogItem(
                    nominal_date=nominal_date,
                    product_name=row.get("name", ""),
                    remote_uri=row.get("s3path", ""),
                    content_length_bytes=int(row.get("contentlength", "0") or "0"),
                    checksum_value=row.get("checksumvalue") or None,
                )
            )
    selected.sort(key=lambda item: item.nominal_date)
    return selected


def post_form_json(url: str, payload: dict[str, str], headers: dict[str, str] | None = None) -> dict:
    request = Request(
        url,
        data=urlencode(payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded", **(headers or {})},
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict[str, str], headers: dict[str, str] | None = None) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def delete_request(url: str, headers: dict[str, str]) -> None:
    request = Request(url, headers=headers, method="DELETE")
    with urlopen(request, timeout=60):
        return


def resolve_s3_credentials(skip_remote: bool) -> TemporaryS3Credentials | None:
    access_id = os.environ.get("CDSE_S3_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID")
    secret = os.environ.get("CDSE_S3_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")
    if access_id and secret:
        return TemporaryS3Credentials(access_id=access_id, secret=secret)

    if skip_remote:
        return None

    bearer_token = os.environ.get("CDSE_ACCESS_TOKEN")
    if not bearer_token:
        username = os.environ.get("CDSE_USERNAME")
        password = os.environ.get("CDSE_PASSWORD")
        if not username or not password:
            return None
        token_payload = post_form_json(
            "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
            {
                "client_id": "cdse-public",
                "grant_type": "password",
                "username": username,
                "password": password,
            },
        )
        bearer_token = token_payload["access_token"]

    credentials_payload = post_json(
        "https://s3-keys-manager.cloudferro.com/api/user/credentials",
        {},
        headers={"Authorization": f"Bearer {bearer_token}", "Accept": "application/json"},
    )
    return TemporaryS3Credentials(
        access_id=credentials_payload["access_id"],
        secret=credentials_payload["secret"],
        bearer_token=bearer_token,
    )


def cleanup_s3_credentials(credentials: TemporaryS3Credentials | None) -> None:
    if credentials is None or credentials.bearer_token is None:
        return
    try:
        delete_request(
            f"https://s3-keys-manager.cloudferro.com/api/user/credentials/access_id/{credentials.access_id}",
            headers={"Authorization": f"Bearer {credentials.bearer_token}"},
        )
    except Exception as exc:  # pragma: no cover - limpieza defensiva
        print(f"AVISO: no se pudieron borrar las credenciales temporales S3: {exc}", file=sys.stderr)


def configure_gdal_for_cdse(credentials: TemporaryS3Credentials | None) -> None:
    if credentials is None:
        return
    config = {
        "AWS_ACCESS_KEY_ID": credentials.access_id,
        "AWS_SECRET_ACCESS_KEY": credentials.secret,
        "AWS_DEFAULT_REGION": "default",
        "AWS_REGION": "default",
        "AWS_S3_ENDPOINT": os.environ.get("CDSE_S3_ENDPOINT", "eodata.dataspace.copernicus.eu"),
        "AWS_HTTPS": "YES",
        "AWS_VIRTUAL_HOSTING": "FALSE",
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    }
    for key, value in config.items():
        os.environ[key] = value
        gdal.SetConfigOption(key, value)


def remote_uri_to_vsis3_path(remote_uri: str) -> str:
    if not remote_uri.startswith("s3://"):
        raise ValueError(f"URI remota no soportada: {remote_uri}")
    bucket_and_key = remote_uri[len("s3://") :]
    return f"/vsis3/{bucket_and_key}"


def resolve_local_source_path(item: CatalogItem, local_source_root: Path, dataset_version: str) -> Path | None:
    canonical_path = build_local_source_path(item, local_source_root, dataset_version)
    if canonical_path.is_file():
        return canonical_path
    vrt_path = build_local_source_vrt_path(item, local_source_root, dataset_version)
    if vrt_path.is_file():
        return vrt_path
    parts = item.nominal_date.split("-")
    base_dir = local_source_root / dataset_version / parts[0] / parts[1] / parts[2]
    candidates = [
        base_dir / item.product_name,
        base_dir / f"{item.product_name}.cog.tif",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def build_local_source_path(item: CatalogItem, local_source_root: Path, dataset_version: str) -> Path:
    parts = item.nominal_date.split("-")
    return local_source_root / dataset_version / parts[0] / parts[1] / parts[2] / f"{item.product_name}.tif"


def build_local_source_base_dir(item: CatalogItem, local_source_root: Path, dataset_version: str) -> Path:
    parts = item.nominal_date.split("-")
    return local_source_root / dataset_version / parts[0] / parts[1] / parts[2]


def build_local_source_vrt_path(item: CatalogItem, local_source_root: Path, dataset_version: str) -> Path:
    base_dir = build_local_source_base_dir(item, local_source_root, dataset_version)
    return base_dir / f"{item.product_name}.vrt"


def collect_local_band_files(item: CatalogItem, local_source_root: Path, dataset_version: str) -> list[Path]:
    base_dir = build_local_source_base_dir(item, local_source_root, dataset_version)
    product_dir = base_dir / item.product_name
    if not product_dir.is_dir():
        return []
    return sorted(path for path in product_dir.iterdir() if path.is_file() and path.suffix.lower() in {".tif", ".tiff"})


def build_v4_band_stack_vrt(
    item: CatalogItem,
    local_source_root: Path,
    dataset_version: str,
    overwrite: bool,
) -> Path | None:
    band_files = collect_local_band_files(item, local_source_root, dataset_version)
    if not band_files:
        return None

    product_dir = build_local_source_base_dir(item, local_source_root, dataset_version) / item.product_name
    ordered_files: list[Path] = []
    for band_name in ("BF", "CP", "DOB", "LFP"):
        expected = [path for path in band_files if f"-{band_name}-" in path.name]
        if len(expected) != 1:
            raise RuntimeError(
                f"No se pudo resolver exactamente un TIFF para la banda {band_name} en {product_dir}"
            )
        ordered_files.append(expected[0])

    vrt_path = build_local_source_vrt_path(item, local_source_root, dataset_version)
    if vrt_path.exists() and not overwrite:
        return vrt_path

    vrt_path.parent.mkdir(parents=True, exist_ok=True)
    vrt = gdal.BuildVRT(str(vrt_path), [str(path) for path in ordered_files], separate=True)
    if vrt is None:
        raise RuntimeError(f"No se pudo construir el VRT {vrt_path}")
    vrt.FlushCache()
    vrt = None
    return vrt_path


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def ensure_local_source_cog(
    item: CatalogItem,
    remote_source_path: str,
    output_path: Path,
    temp_root: Path,
    overwrite: bool,
) -> None:
    if output_path.exists() and not overwrite:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    temp_output_path = temp_root / f"{item.nominal_date}_{item.product_name}_raw_tmp.tif"
    if temp_output_path.exists():
        temp_output_path.unlink()

    translate_options = gdal.TranslateOptions(
        format="COG",
        creationOptions=[
            "COMPRESS=DEFLATE",
            "PREDICTOR=2",
            "BIGTIFF=IF_SAFER",
        ],
    )
    gdal.Translate(str(temp_output_path), remote_source_path, options=translate_options)
    temp_output_path.replace(output_path)


def ensure_spain_cog(
    item: CatalogItem,
    source_path: str,
    spain_boundary: Path,
    output_path: Path,
    temp_root: Path,
    overwrite: bool,
) -> None:
    if output_path.exists() and not overwrite:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    temp_warp_path = temp_root / f"{item.nominal_date}_{item.product_name}_spain_tmp.tif"
    if temp_warp_path.exists():
        temp_warp_path.unlink()

    warp_options = gdal.WarpOptions(
        format="GTiff",
        cutlineDSName=str(spain_boundary),
        cropToCutline=True,
        dstAlpha=True,
        multithread=True,
        creationOptions=[
            "TILED=YES",
            "COMPRESS=DEFLATE",
            "PREDICTOR=2",
            "BIGTIFF=IF_SAFER",
        ],
    )
    gdal.Warp(str(temp_warp_path), source_path, options=warp_options)

    translate_options = gdal.TranslateOptions(
        format="COG",
        creationOptions=[
            "COMPRESS=DEFLATE",
            "PREDICTOR=2",
            "BIGTIFF=IF_SAFER",
        ],
    )
    gdal.Translate(str(output_path), str(temp_warp_path), options=translate_options)
    temp_warp_path.unlink(missing_ok=True)


def daily_mask_from_arrays(
    bf_values: np.ndarray,
    dob_values: np.ndarray,
    alpha_values: np.ndarray | None,
    day_of_year: int,
    mode: str,
) -> np.ndarray:
    base_mask = bf_values > 0
    if alpha_values is not None:
        base_mask &= alpha_values > 0
    if mode == "daily":
        return base_mask & (dob_values == day_of_year)
    return base_mask & (dob_values > 0) & (dob_values <= day_of_year)


def dilate_mask(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    if radius <= 0 or not np.any(mask):
        return mask.copy()

    expanded = mask.copy()
    rows, cols = mask.shape
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue

            src_y_start = max(0, -dy)
            src_y_end = rows - max(0, dy)
            src_x_start = max(0, -dx)
            src_x_end = cols - max(0, dx)
            dst_y_start = max(0, dy)
            dst_y_end = rows - max(0, -dy)
            dst_x_start = max(0, dx)
            dst_x_end = cols - max(0, -dx)
            expanded[dst_y_start:dst_y_end, dst_x_start:dst_x_end] |= mask[
                src_y_start:src_y_end,
                src_x_start:src_x_end,
            ]
    return expanded


def write_visual_raster(
    source_cog_path: Path,
    output_path: Path,
    nominal_date: str,
    mode: str,
    overwrite: bool,
) -> None:
    if output_path.exists() and not overwrite:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset = gdal.Open(str(source_cog_path))
    if dataset is None:
        raise RuntimeError(f"No se pudo abrir {source_cog_path}")

    xsize = dataset.RasterXSize
    ysize = dataset.RasterYSize
    geotransform = dataset.GetGeoTransform()
    projection = dataset.GetProjection()
    alpha_band = dataset.GetRasterBand(5) if dataset.RasterCount >= 5 else None
    bf_band = dataset.GetRasterBand(1)
    dob_band = dataset.GetRasterBand(3)
    day_of_year = date.fromisoformat(nominal_date).timetuple().tm_yday

    driver = gdal.GetDriverByName("GTiff")
    visual_ds = driver.Create(
        str(output_path),
        xsize,
        ysize,
        4,
        gdal.GDT_Byte,
        options=[
            "TILED=YES",
            "COMPRESS=DEFLATE",
            "BIGTIFF=IF_SAFER",
        ],
    )
    if visual_ds is None:
        raise RuntimeError(f"No se pudo crear {output_path}")
    visual_ds.SetGeoTransform(geotransform)
    visual_ds.SetProjection(projection)

    block_rows = 512
    for yoff in range(0, ysize, block_rows):
        rows = min(block_rows, ysize - yoff)
        bf_values = bf_band.ReadAsArray(0, yoff, xsize, rows).astype(np.float32) / 1000.0
        dob_values = dob_band.ReadAsArray(0, yoff, xsize, rows)
        alpha_values = alpha_band.ReadAsArray(0, yoff, xsize, rows) if alpha_band is not None else None
        mask = daily_mask_from_arrays(bf_values, dob_values, alpha_values, day_of_year, mode)
        halo_mask = dilate_mask(mask, radius=1)
        outer_halo_mask = halo_mask & ~mask
        intensity = np.clip((bf_values * 255.0).round(), 0, 255).astype(np.uint8)

        red = np.zeros((rows, xsize), dtype=np.uint8)
        green = np.zeros((rows, xsize), dtype=np.uint8)
        blue = np.zeros((rows, xsize), dtype=np.uint8)
        alpha = np.zeros((rows, xsize), dtype=np.uint8)

        red[outer_halo_mask] = 255
        green[outer_halo_mask] = 212
        blue[outer_halo_mask] = 82
        alpha[outer_halo_mask] = 150

        red[mask] = 255
        green[mask] = np.clip(240 - (intensity[mask] * 105) // 255, 88, 240)
        blue[mask] = np.clip(164 - (intensity[mask] * 112) // 255, 26, 164)
        alpha[mask] = np.clip(182 + (intensity[mask] * 58) // 255, 182, 240)

        visual_ds.GetRasterBand(1).WriteArray(red, xoff=0, yoff=yoff)
        visual_ds.GetRasterBand(2).WriteArray(green, xoff=0, yoff=yoff)
        visual_ds.GetRasterBand(3).WriteArray(blue, xoff=0, yoff=yoff)
        visual_ds.GetRasterBand(4).WriteArray(alpha, xoff=0, yoff=yoff)

    visual_ds.FlushCache()
    visual_ds = None
    dataset = None


def cell_area_hectares_per_row(dataset: gdal.Dataset, yoff: int, rows: int) -> np.ndarray:
    gt = dataset.GetGeoTransform()
    lon_step_rad = math.radians(abs(gt[1]))
    row_indices = np.arange(yoff, yoff + rows, dtype=np.float64)
    lat_top = gt[3] + row_indices * gt[5]
    lat_bottom = gt[3] + (row_indices + 1.0) * gt[5]
    lat_top_rad = np.radians(lat_top)
    lat_bottom_rad = np.radians(lat_bottom)
    cell_area_m2 = (
        EARTH_AUTHALIC_RADIUS_METERS
        * EARTH_AUTHALIC_RADIUS_METERS
        * lon_step_rad
        * np.abs(np.sin(lat_top_rad) - np.sin(lat_bottom_rad))
    )
    return cell_area_m2 / 10000.0


def compute_burnt_stats(source_cog_path: Path, nominal_date: str, mode: str) -> dict[str, float | int]:
    dataset = gdal.Open(str(source_cog_path))
    if dataset is None:
        raise RuntimeError(f"No se pudo abrir {source_cog_path}")

    xsize = dataset.RasterXSize
    ysize = dataset.RasterYSize
    alpha_band = dataset.GetRasterBand(5) if dataset.RasterCount >= 5 else None
    bf_band = dataset.GetRasterBand(1)
    dob_band = dataset.GetRasterBand(3)
    day_of_year = date.fromisoformat(nominal_date).timetuple().tm_yday

    burned_fraction_sum = 0.0
    burned_area_ha = 0.0
    burned_pixel_count = 0
    block_rows = 512

    for yoff in range(0, ysize, block_rows):
        rows = min(block_rows, ysize - yoff)
        bf_values = bf_band.ReadAsArray(0, yoff, xsize, rows).astype(np.float64) / 1000.0
        dob_values = dob_band.ReadAsArray(0, yoff, xsize, rows)
        alpha_values = alpha_band.ReadAsArray(0, yoff, xsize, rows) if alpha_band is not None else None
        mask = daily_mask_from_arrays(bf_values, dob_values, alpha_values, day_of_year, mode)
        if not np.any(mask):
            continue
        row_areas = cell_area_hectares_per_row(dataset, yoff, rows)[:, np.newaxis]
        burned_fraction_sum += float((bf_values * mask).sum())
        burned_area_ha += float((bf_values * row_areas * mask).sum())
        burned_pixel_count += int(mask.sum())

    dataset = None
    return {
        "burned_area_ha": burned_area_ha,
        "burned_fraction_sum": burned_fraction_sum,
        "burned_pixel_count": burned_pixel_count,
    }


def generate_tiles(
    visual_raster_path: Path,
    tiles_dir: Path,
    min_zoom: int,
    max_zoom: int,
    tile_processes: int,
    overwrite: bool,
) -> int:
    if tiles_dir.exists() and overwrite:
        shutil.rmtree(tiles_dir)
    if tiles_dir.exists() and not overwrite:
        return sum(1 for _ in tiles_dir.rglob("*.png"))

    temp_tiles_dir = tiles_dir.parent / f".{tiles_dir.name}_tmp"
    ensure_clean_dir(temp_tiles_dir)
    command = [
        sys.executable,
        "-m",
        "osgeo_utils.gdal2tiles",
        "--xyz",
        "--webviewer",
        "none",
        "--tiledriver",
        "PNG",
        "--zoom",
        f"{min_zoom}-{max_zoom}",
        "--processes",
        str(max(1, tile_processes)),
        str(visual_raster_path),
        str(temp_tiles_dir),
    ]
    subprocess.run(command, check=True)
    temp_tiles_dir.replace(tiles_dir)
    return sum(1 for _ in tiles_dir.rglob("*.png"))


def write_manifest(manifest_path: Path, payload: dict) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def process_item(
    args: argparse.Namespace,
    item: CatalogItem,
    credentials: TemporaryS3Credentials | None,
) -> dict:
    root_dir = repo_root()
    parts = item.nominal_date.split("-")
    spain_cog_path = Path(args.spain_cog_root) / args.dataset_version / f"{item.nominal_date}.tif"
    visual_raster_path = Path(args.visual_root) / args.dataset_version / args.mode / f"{item.nominal_date}.tif"
    tiles_dir = Path(args.tiles_root) / args.dataset_version / item.nominal_date
    manifest_path = Path(args.manifest_root) / args.dataset_version / args.mode / f"{item.nominal_date}.json"
    temp_root = Path(args.temp_root)
    spain_boundary = Path(args.spain_boundary)
    local_source_root = Path(args.local_source_root)

    local_source_path = resolve_local_source_path(item, local_source_root, args.dataset_version)
    if local_source_path is None and args.dataset_version == "v4":
        local_source_path = build_v4_band_stack_vrt(
            item=item,
            local_source_root=local_source_root,
            dataset_version=args.dataset_version,
            overwrite=args.overwrite,
        )
    source_descriptor: str | None = None
    source_path_used: str | None = None

    try:
        if local_source_path is not None:
            source_path_used = str(local_source_path)
            source_descriptor = normalized_rel_path(local_source_path, root_dir)
        else:
            if args.skip_remote:
                raise RuntimeError(
                    "No existe un raster bruto local y se ha pedido --skip-remote, asi que no se puede procesar el dia."
                )
            if credentials is None:
                raise RuntimeError(
                    "No hay credenciales CDSE configuradas. Define CDSE_USERNAME/CDSE_PASSWORD "
                    "o CDSE_S3_ACCESS_KEY/CDSE_S3_SECRET_KEY para descargar el COG remoto."
                )
            remote_source_path = remote_uri_to_vsis3_path(item.remote_uri)
            local_source_path = build_local_source_path(item, local_source_root, args.dataset_version)
            ensure_local_source_cog(
                item=item,
                remote_source_path=remote_source_path,
                output_path=local_source_path,
                temp_root=temp_root,
                overwrite=args.overwrite,
            )
            source_path_used = str(local_source_path)
            source_descriptor = normalized_rel_path(local_source_path, root_dir)

        ensure_spain_cog(
            item=item,
            source_path=source_path_used,
            spain_boundary=spain_boundary,
            output_path=spain_cog_path,
            temp_root=temp_root,
            overwrite=args.overwrite,
        )
        stats = compute_burnt_stats(spain_cog_path, item.nominal_date, args.mode)
        tile_count = 0
        if stats["burned_pixel_count"] and stats["burned_pixel_count"] > 0:
            write_visual_raster(
                source_cog_path=spain_cog_path,
                output_path=visual_raster_path,
                nominal_date=item.nominal_date,
                mode=args.mode,
                overwrite=args.overwrite,
            )
            tile_count = generate_tiles(
                visual_raster_path=visual_raster_path,
                tiles_dir=tiles_dir,
                min_zoom=args.min_zoom,
                max_zoom=args.max_zoom,
                tile_processes=args.tile_processes,
                overwrite=args.overwrite,
            )
        elif args.overwrite and tiles_dir.exists():
            shutil.rmtree(tiles_dir)

        manifest = {
            "dataset_version": args.dataset_version,
            "delivery_format": args.delivery_format,
            "nominal_date": item.nominal_date,
            "mode": args.mode,
            "day_of_year": date.fromisoformat(item.nominal_date).timetuple().tm_yday,
            "source_product_name": item.product_name,
            "source_remote_uri": item.remote_uri,
            "source_descriptor": source_descriptor,
            "content_length_bytes": item.content_length_bytes,
            "checksum_value": item.checksum_value,
            "local_file_path": normalized_rel_path(local_source_path, root_dir) if local_source_path and local_source_path.exists() else None,
            "local_spain_cog_path": normalized_rel_path(spain_cog_path, root_dir),
            "local_tiles_path": normalized_rel_path(tiles_dir, root_dir) if tile_count > 0 and tiles_dir.exists() else None,
            "tiles_generated": tile_count > 0,
            "tile_count": tile_count,
            "burned_area_ha": round(float(stats["burned_area_ha"]), 6),
            "burned_fraction_sum": round(float(stats["burned_fraction_sum"]), 6),
            "burned_pixel_count": int(stats["burned_pixel_count"]),
            "publication_status": "published",
            "publication_notes": None,
            "generated_at": utc_now_iso(),
            "metadata_json": {
                "mask_mode": args.mode,
                "tile_zoom_range": [args.min_zoom, args.max_zoom],
                "spain_boundary": normalized_rel_path(spain_boundary, root_dir),
            },
        }
    except Exception as exc:
        manifest = {
            "dataset_version": args.dataset_version,
            "delivery_format": args.delivery_format,
            "nominal_date": item.nominal_date,
            "mode": args.mode,
            "day_of_year": date.fromisoformat(item.nominal_date).timetuple().tm_yday,
            "source_product_name": item.product_name,
            "source_remote_uri": item.remote_uri,
            "source_descriptor": source_descriptor,
            "content_length_bytes": item.content_length_bytes,
            "checksum_value": item.checksum_value,
            "local_file_path": normalized_rel_path(local_source_path, root_dir) if local_source_path and local_source_path.exists() else None,
            "local_spain_cog_path": normalized_rel_path(spain_cog_path, root_dir) if spain_cog_path.exists() else None,
            "local_tiles_path": normalized_rel_path(tiles_dir, root_dir) if tiles_dir.exists() else None,
            "tiles_generated": bool(tiles_dir.exists()),
            "tile_count": sum(1 for _ in tiles_dir.rglob("*.png")) if tiles_dir.exists() else 0,
            "burned_area_ha": None,
            "burned_fraction_sum": None,
            "burned_pixel_count": None,
            "publication_status": "failed",
            "publication_notes": str(exc),
            "generated_at": utc_now_iso(),
            "metadata_json": {
                "mask_mode": args.mode,
                "error": str(exc),
                "tile_zoom_range": [args.min_zoom, args.max_zoom],
                "spain_boundary": normalized_rel_path(spain_boundary, root_dir),
            },
        }

    write_manifest(manifest_path, manifest)
    return manifest


def main() -> int:
    args = parse_args()
    catalog_root = Path(args.catalog_root)
    items = load_catalog_items(
        catalog_root=catalog_root,
        dataset_version=args.dataset_version,
        delivery_format=args.delivery_format,
        date_from=args.date_from,
        date_to=args.date_to,
    )
    if not items:
        print("No hay dias seleccionados en el catalogo para ese rango.", file=sys.stderr)
        return 1

    credentials = None
    try:
        credentials = resolve_s3_credentials(skip_remote=args.skip_remote)
        configure_gdal_for_cdse(credentials)

        print(
            f"Procesando {len(items)} dias de burnt area {args.dataset_version}/{args.delivery_format} "
            f"({args.date_from} a {args.date_to}, modo {args.mode})"
        )
        published = 0
        failed = 0
        for item in items:
            print(f"- {item.nominal_date}: {item.product_name}")
            manifest = process_item(args, item, credentials)
            if manifest["publication_status"] == "published":
                published += 1
                print(
                    f"  publicado: {manifest['burned_area_ha']:.2f} ha, "
                    f"{manifest['burned_pixel_count']} pixeles, {manifest['tile_count']} tiles"
                )
            else:
                failed += 1
                print(f"  fallo: {manifest['publication_notes']}", file=sys.stderr)

        print(f"Resumen: publicados={published}, fallidos={failed}")
        return 0 if failed == 0 else 2
    finally:
        cleanup_s3_credentials(credentials)


if __name__ == "__main__":
    raise SystemExit(main())
