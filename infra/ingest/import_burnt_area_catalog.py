#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import psycopg


DATASET_ID = "burnt_area_global_300m_daily_catalog"
SOURCE_SYSTEM = "copernicus_clms"
PRODUCT_FAMILY = "ba_global_300m_daily"
CATALOG_TARGETS = (
    ("v3", "cog", "bio-geophysical/burnt_area/ba_global_300m_daily_v3/cog.csv"),
    ("v3", "nc", "bio-geophysical/burnt_area/ba_global_300m_daily_v3/nc.csv"),
    ("v4", "cog", "bio-geophysical/burnt_area/ba_global_300m_daily_v4/cog.csv"),
    ("v4", "nc", "bio-geophysical/burnt_area/ba_global_300m_daily_v4/nc.csv"),
)
CATALOG_DIR_ENTRY_PATHS = {
    ("v3", "cog"): ("ba_global_300m_daily_v3/cog.csv",),
    ("v3", "nc"): ("ba_global_300m_daily_v3/nc.csv",),
    ("v4", "cog"): ("ba_global_300m_daily_v4/cog.csv",),
    ("v4", "nc"): ("ba_global_300m_daily_v4/nc.csv",),
}


@dataclass(frozen=True)
class CatalogSource:
    kind: str
    path: Path

    @property
    def origin_format(self) -> str:
        return "catalog_csv_in_zip" if self.kind == "zip" else "catalog_csv_directory"


@dataclass(frozen=True)
class CatalogRow:
    dataset_version: str
    delivery_format: str
    catalog_entry_path: str
    source_item_id: str
    product_name: str
    product_version: str
    content_length_bytes: int
    nominal_date: str
    content_start_at: str | None
    content_end_at: str | None
    catalog_ingested_at: str | None
    catalog_modified_at: str | None
    checksum_algorithm: str | None
    checksum_value: str | None
    remote_uri: str
    bbox_wkt: str | None
    metadata_json: str


def env(name: str, default: str) -> str:
    value = os.environ.get(name, default)
    return value if value else default


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def candidate_catalog_paths(root_dir: Path) -> list[Path]:
    return [
        Path(env("BURNT_AREA_CATALOG_ZIP", str(root_dir / "data-store/files/raw/copernicus/clms/all.zip"))),
        root_dir / "data-store/files/all.zip",
        Path.home() / "Downloads/all.zip",
    ]


def candidate_catalog_roots(root_dir: Path) -> list[Path]:
    return [
        Path(env("BURNT_AREA_CATALOG_ROOT", str(root_dir / "data/copernicus/data_burnt_areas"))),
        root_dir / "data-store/files/raw/copernicus/clms",
    ]


def resolve_catalog_dir_entry_path(catalog_root: Path, target: tuple[str, str, str]) -> Path | None:
    dataset_version, delivery_format, logical_entry_path = target
    for rel_path in (logical_entry_path, *CATALOG_DIR_ENTRY_PATHS[(dataset_version, delivery_format)]):
        file_path = catalog_root / rel_path
        if file_path.is_file():
            return file_path
    return None


def resolve_catalog_source(root_dir: Path) -> CatalogSource:
    for path in candidate_catalog_roots(root_dir):
        if path.is_dir() and any(resolve_catalog_dir_entry_path(path, target) is not None for target in CATALOG_TARGETS):
            return CatalogSource(kind="directory", path=path)
    for path in candidate_catalog_paths(root_dir):
        if path.is_file():
            return CatalogSource(kind="zip", path=path)
    raise FileNotFoundError(
        "No se encontro un catalogo burnt area valido. Configura BURNT_AREA_CATALOG_ROOT "
        "con la carpeta extraida o BURNT_AREA_CATALOG_ZIP con all.zip."
    )


def pg_conninfo() -> str:
    return " ".join(
        [
            f"host={env('POSTGRES_HOST', '127.0.0.1')}",
            f"port={env('POSTGRES_PORT', '5432')}",
            f"dbname={env('POSTGRES_DB', 'meteovisor')}",
            f"user={env('POSTGRES_USER', 'meteovisor')}",
            f"password={env('POSTGRES_PASSWORD', 'meteovisor')}",
        ]
    )


def normalize_datetime(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.replace('""', '"').replace('"T"', "T").strip('"')
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized).astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def parse_product_version(product_name: str) -> str:
    parts = product_name.split("_")
    for part in parts:
        if part.startswith("V"):
            return part
    return ""


def parse_nominal_date(value: str) -> str:
    return value[:10]


def load_catalog_rows(catalog_zip: Path, target: tuple[str, str, str]) -> list[CatalogRow]:
    dataset_version, delivery_format, entry_path = target
    with zipfile.ZipFile(catalog_zip) as archive:
        with archive.open(entry_path) as raw_stream:
            decoded_stream = (line.decode("utf-8") for line in raw_stream)
            return build_catalog_rows(decoded_stream, dataset_version, delivery_format, entry_path, str(catalog_zip), "zip")


def load_catalog_rows_from_dir(catalog_root: Path, target: tuple[str, str, str]) -> list[CatalogRow]:
    dataset_version, delivery_format, entry_path = target
    csv_path = resolve_catalog_dir_entry_path(catalog_root, target)
    if csv_path is None:
        raise FileNotFoundError(f"No se encontro el CSV {entry_path} en {catalog_root}")
    with csv_path.open("r", encoding="utf-8", newline="") as stream:
        return build_catalog_rows(stream, dataset_version, delivery_format, entry_path, str(csv_path), "directory")


def build_catalog_rows(
    stream: Iterable[str],
    dataset_version: str,
    delivery_format: str,
    entry_path: str,
    source_path: str,
    source_kind: str,
) -> list[CatalogRow]:
    reader = csv.DictReader(stream)
    rows: list[CatalogRow] = []
    for row in reader:
        product_name = row.get("name", "")
        rows.append(
            CatalogRow(
                dataset_version=dataset_version,
                delivery_format=delivery_format,
                catalog_entry_path=entry_path,
                source_item_id=row.get("id", ""),
                product_name=product_name,
                product_version=parse_product_version(product_name),
                content_length_bytes=int(row.get("contentlength", "0") or "0"),
                nominal_date=parse_nominal_date(row.get("nominaldate", "")),
                content_start_at=normalize_datetime(row.get("contentstartdate")),
                content_end_at=normalize_datetime(row.get("contentdateend")),
                catalog_ingested_at=normalize_datetime(row.get("ingestiondate")),
                catalog_modified_at=normalize_datetime(row.get("modificationdate")),
                checksum_algorithm=row.get("checksumalgorithm") or None,
                checksum_value=row.get("checksumvalue") or None,
                remote_uri=row.get("s3path", ""),
                bbox_wkt=row.get("bbox") or None,
                metadata_json=json.dumps(
                    {
                        "catalog_entry_path": entry_path,
                        "catalog_source_kind": source_kind,
                        "catalog_source_path": source_path,
                        "source_name": product_name,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        )
    return rows


def create_ingest_record(
    conn: psycopg.Connection,
    catalog_source: CatalogSource,
    file_path: str,
    entry_path: str,
    dataset_version: str,
    delivery_format: str,
) -> int:
    metadata = {
        "product_family": PRODUCT_FAMILY,
        "dataset_version": dataset_version,
        "delivery_format": delivery_format,
        "catalog_entry_path": entry_path,
    }
    sql = """
        INSERT INTO ingest.ingest_file (
            dataset_id,
            source_system,
            source_layer,
            origin_format,
            file_path,
            captured_at,
            status,
            metadata_json
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            now(),
            'running',
            %s::jsonb
        )
        RETURNING ingest_id
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                DATASET_ID,
                SOURCE_SYSTEM,
                entry_path,
                catalog_source.origin_format,
                file_path,
                json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            ),
        )
        ingest_id = cur.fetchone()[0]
    return int(ingest_id)


def update_ingest_record(
    conn: psycopg.Connection,
    ingest_id: int,
    status: str,
    metadata: dict[str, object] | None = None,
    error: dict[str, object] | None = None,
) -> None:
    sql = """
        UPDATE ingest.ingest_file
        SET status = %s,
            ingested_at = now(),
            metadata_json = %s::jsonb,
            error_json = %s::jsonb
        WHERE ingest_id = %s
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                status,
                json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                json.dumps(error or {}, ensure_ascii=False, sort_keys=True),
                ingest_id,
            ),
        )


def truncate_source(conn: psycopg.Connection) -> None:
    if env("TRUNCATE_SOURCE", "0").lower() in {"0", "false", "no"}:
        return
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE source.burnt_area_catalog_item RESTART IDENTITY CASCADE")


def upsert_rows(conn: psycopg.Connection, catalog_source: CatalogSource, rows: Iterable[CatalogRow]) -> int:
    row_list = list(rows)
    if not row_list:
        return 0

    ingest_id = create_ingest_record(
        conn,
        catalog_source,
        json.loads(row_list[0].metadata_json)["catalog_source_path"],
        row_list[0].catalog_entry_path,
        row_list[0].dataset_version,
        row_list[0].delivery_format,
    )
    conn.commit()
    sql = """
        INSERT INTO source.burnt_area_catalog_item (
            product_family,
            dataset_version,
            delivery_format,
            product_version,
            catalog_entry_path,
            catalog_zip_path,
            source_item_id,
            product_name,
            content_length_bytes,
            nominal_date,
            content_start_at,
            content_end_at,
            catalog_ingested_at,
            catalog_modified_at,
            checksum_algorithm,
            checksum_value,
            remote_uri,
            bbox,
            ingest_id,
            metadata_json
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            CASE
                WHEN COALESCE(%s::text, '') = '' THEN NULL
                ELSE ST_GeomFromText(%s, 4326)::geometry(Polygon, 4326)
            END,
            %s,
            %s::jsonb
        )
        ON CONFLICT (dataset_version, delivery_format, nominal_date, product_name) DO UPDATE
        SET product_version = EXCLUDED.product_version,
            catalog_entry_path = EXCLUDED.catalog_entry_path,
            catalog_zip_path = EXCLUDED.catalog_zip_path,
            source_item_id = EXCLUDED.source_item_id,
            content_length_bytes = EXCLUDED.content_length_bytes,
            content_start_at = EXCLUDED.content_start_at,
            content_end_at = EXCLUDED.content_end_at,
            catalog_ingested_at = EXCLUDED.catalog_ingested_at,
            catalog_modified_at = EXCLUDED.catalog_modified_at,
            checksum_algorithm = EXCLUDED.checksum_algorithm,
            checksum_value = EXCLUDED.checksum_value,
            remote_uri = EXCLUDED.remote_uri,
            bbox = EXCLUDED.bbox,
            ingest_id = EXCLUDED.ingest_id,
            metadata_json = EXCLUDED.metadata_json,
            imported_at = now()
    """
    try:
        with conn.cursor() as cur:
            for row in row_list:
                cur.execute(
                    sql,
                    (
                        PRODUCT_FAMILY,
                        row.dataset_version,
                        row.delivery_format,
                        row.product_version,
                        row.catalog_entry_path,
                        json.loads(row.metadata_json)["catalog_source_path"],
                        row.source_item_id,
                        row.product_name,
                        row.content_length_bytes,
                        row.nominal_date,
                        row.content_start_at,
                        row.content_end_at,
                        row.catalog_ingested_at,
                        row.catalog_modified_at,
                        row.checksum_algorithm,
                        row.checksum_value,
                        row.remote_uri,
                        row.bbox_wkt,
                        row.bbox_wkt,
                        ingest_id,
                        row.metadata_json,
                    ),
                )
        update_ingest_record(
            conn,
            ingest_id,
            "ok",
            metadata={
                "row_count": len(row_list),
                "dataset_version": row_list[0].dataset_version,
                "delivery_format": row_list[0].delivery_format,
                "catalog_entry_path": row_list[0].catalog_entry_path,
                "catalog_source_kind": catalog_source.kind,
                "catalog_source_path": json.loads(row_list[0].metadata_json)["catalog_source_path"],
            },
        )
    except Exception as exc:
        conn.rollback()
        update_ingest_record(
            conn,
            ingest_id,
            "failed",
            metadata={
                "dataset_version": row_list[0].dataset_version,
                "delivery_format": row_list[0].delivery_format,
                "catalog_entry_path": row_list[0].catalog_entry_path,
                "catalog_source_kind": catalog_source.kind,
                "catalog_source_path": json.loads(row_list[0].metadata_json)["catalog_source_path"],
            },
            error={"message": str(exc)},
        )
        conn.commit()
        raise
    return len(row_list)


def main() -> int:
    root_dir = repo_root()
    catalog_source = resolve_catalog_source(root_dir)
    conninfo = pg_conninfo()

    print(f"Catalogo Copernicus ({catalog_source.kind}): {catalog_source.path}")
    print(f"PostgreSQL: {conninfo}")

    with psycopg.connect(conninfo) as conn:
        truncate_source(conn)
        conn.commit()

        total_rows = 0
        for target in CATALOG_TARGETS:
            dataset_version, delivery_format, entry_path = target
            print(f"Importando {entry_path} ...")
            if catalog_source.kind == "directory":
                csv_path = resolve_catalog_dir_entry_path(catalog_source.path, target)
                if csv_path is None:
                    print("  omitido: CSV no disponible en la carpeta fuente")
                    continue
                rows = load_catalog_rows_from_dir(catalog_source.path, target)
            else:
                rows = load_catalog_rows(catalog_source.path, target)
            imported = upsert_rows(conn, catalog_source, rows)
            total_rows += imported
            conn.commit()
            print(f"  {dataset_version}/{delivery_format}: {imported} filas")
        print(f"Importacion de catalogo burnt area completada: {total_rows} filas")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
