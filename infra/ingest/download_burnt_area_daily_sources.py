#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import boto3
from dotenv import dotenv_values


CATALOG_ENTRY_PATHS = {
    ("v3", "cog"): ("bio-geophysical/burnt_area/ba_global_300m_daily_v3/cog.csv", "ba_global_300m_daily_v3/cog.csv"),
    ("v3", "nc"): ("bio-geophysical/burnt_area/ba_global_300m_daily_v3/nc.csv", "ba_global_300m_daily_v3/nc.csv"),
    ("v4", "cog"): ("bio-geophysical/burnt_area/ba_global_300m_daily_v4/cog.csv", "ba_global_300m_daily_v4/cog.csv"),
    ("v4", "nc"): ("bio-geophysical/burnt_area/ba_global_300m_daily_v4/nc.csv", "ba_global_300m_daily_v4/nc.csv"),
}


@dataclass(frozen=True)
class CatalogItem:
    nominal_date: str
    product_name: str
    remote_uri: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root_dir = repo_root()
    parser = argparse.ArgumentParser(
        description="Descarga a disco local los assets burnt area diarios publicados en CDSE S3."
    )
    parser.add_argument("--catalog-root", default=str(root_dir / "data/copernicus/data_burnt_areas"))
    parser.add_argument("--dataset-version", default="v4", choices=["v3", "v4"])
    parser.add_argument("--delivery-format", default="cog", choices=["cog", "nc"])
    parser.add_argument("--date-from", default="2025-05-01")
    parser.add_argument("--date-to", default="2025-08-31")
    parser.add_argument("--output-root", default=str(root_dir / "data/copernicus/burnt_area/raw"))
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_env() -> dict[str, str]:
    env = {k: v for k, v in dotenv_values(".env").items() if v is not None}
    env.update({k: v for k, v in os.environ.items() if v})
    return env


def build_s3_client(env: dict[str, str]):
    access_key = env.get("CDSE_S3_ACCESS_KEY") or env.get("AWS_ACCESS_KEY_ID")
    secret_key = env.get("CDSE_S3_SECRET_KEY") or env.get("AWS_SECRET_ACCESS_KEY")
    endpoint = env.get("CDSE_S3_ENDPOINT", "eodata.dataspace.copernicus.eu")
    if not access_key or not secret_key:
        raise RuntimeError("Faltan CDSE_S3_ACCESS_KEY y CDSE_S3_SECRET_KEY en .env o en el entorno.")
    return boto3.client(
        "s3",
        endpoint_url=f"https://{endpoint}",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="default",
    )


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
    items: list[CatalogItem] = []
    with csv_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            nominal_date = (row.get("nominaldate") or "")[:10]
            if not nominal_date or nominal_date < date_from or nominal_date > date_to:
                continue
            items.append(
                CatalogItem(
                    nominal_date=nominal_date,
                    product_name=row.get("name", ""),
                    remote_uri=row.get("s3path", ""),
                )
            )
    items.sort(key=lambda item: item.nominal_date)
    return items


def remote_uri_to_s3_prefix(remote_uri: str) -> str:
    if not remote_uri.startswith("s3://eodata/"):
        raise ValueError(f"URI remota no soportada: {remote_uri}")
    return remote_uri.removeprefix("s3://eodata/").rstrip("/")


def list_prefix_objects(s3_client, prefix: str) -> list[dict]:
    paginator = s3_client.get_paginator("list_objects_v2")
    contents: list[dict] = []
    for page in paginator.paginate(Bucket="eodata", Prefix=prefix):
        contents.extend(page.get("Contents", []))
    return contents


def build_output_base_dir(item: CatalogItem, output_root: Path, dataset_version: str) -> Path:
    year, month, day = item.nominal_date.split("-")
    return output_root / dataset_version / year / month / day


def download_item(s3_client, item: CatalogItem, output_root: Path, dataset_version: str, overwrite: bool) -> tuple[int, int]:
    prefix = remote_uri_to_s3_prefix(item.remote_uri)
    objects = list_prefix_objects(s3_client, prefix)
    if not objects:
        raise FileNotFoundError(f"No se encontraron objetos S3 bajo el prefijo {prefix}")

    base_dir = build_output_base_dir(item, output_root, dataset_version)
    downloaded = 0
    skipped = 0
    multi_file_product = len(objects) > 1 or any(obj["Key"].rstrip("/") != prefix for obj in objects)
    target_dir = base_dir / item.product_name if multi_file_product else base_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    for obj in objects:
        key = obj["Key"]
        filename = Path(key).name
        if not filename:
            continue
        destination = target_dir / filename
        remote_size = int(obj.get("Size") or 0)
        if destination.exists() and not overwrite and destination.stat().st_size == remote_size:
            skipped += 1
            continue
        s3_client.download_file("eodata", key, str(destination))
        downloaded += 1

    return downloaded, skipped


def main() -> int:
    args = parse_args()
    env = load_env()
    s3_client = build_s3_client(env)
    items = load_catalog_items(
        catalog_root=Path(args.catalog_root),
        dataset_version=args.dataset_version,
        delivery_format=args.delivery_format,
        date_from=args.date_from,
        date_to=args.date_to,
    )
    if not items:
        print("No hay dias seleccionados en el catalogo para ese rango.", file=sys.stderr)
        return 1

    total_downloaded = 0
    total_skipped = 0
    failures = 0
    print(
        f"Descargando {len(items)} dias de burnt area {args.dataset_version}/{args.delivery_format} "
        f"({args.date_from} a {args.date_to})"
    )
    for item in items:
        try:
            downloaded, skipped = download_item(
                s3_client=s3_client,
                item=item,
                output_root=Path(args.output_root),
                dataset_version=args.dataset_version,
                overwrite=args.overwrite,
            )
            total_downloaded += downloaded
            total_skipped += skipped
            print(f"- {item.nominal_date}: descargados={downloaded}, omitidos={skipped}")
        except Exception as exc:
            failures += 1
            print(f"- {item.nominal_date}: ERROR {exc}", file=sys.stderr)

    print(f"Resumen descarga: descargados={total_downloaded}, omitidos={total_skipped}, fallos={failures}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
