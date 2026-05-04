#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import psycopg
from dotenv import dotenv_values
from shapely.geometry import Point, shape
from shapely.ops import unary_union


FIRMS_HISTORICAL_SOURCES = ("VIIRS_NOAA20_SP", "VIIRS_SNPP_SP")
FIRMS_HISTORICAL_BBOXES = {
    "peninsula_baleares": "-10.0,35.0,5.0,44.5",
    "canarias": "-18.5,27.5,-13.0,29.5",
    "ceuta_melilla": "-6.0,35.0,-1.5,36.5",
}
DATASET_ID = "firms_hotspot_historical_csv"
SOURCE_SYSTEM = "nasa_firms"
SPAIN_BOUNDARY_PATH = "data/boundaries/spain_nuts_2024_01m.geojson"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_env() -> dict[str, str]:
    env = {key: value for key, value in dotenv_values(".env").items() if value is not None}
    env.update({key: value for key, value in os.environ.items() if value})
    return env


def env(name: str, default: str, merged_env: dict[str, str]) -> str:
    value = merged_env.get(name, default)
    return value if value else default


def pg_conninfo(merged_env: dict[str, str]) -> str:
    return " ".join(
        [
            f"host={env('POSTGRES_HOST', '127.0.0.1', merged_env)}",
            f"port={env('POSTGRES_PORT', '5432', merged_env)}",
            f"dbname={env('POSTGRES_DB', 'meteovisor', merged_env)}",
            f"user={env('POSTGRES_USER', 'meteovisor', merged_env)}",
            f"password={env('POSTGRES_PASSWORD', 'meteovisor', merged_env)}",
        ]
    )


def parse_args() -> argparse.Namespace:
    root_dir = repo_root()
    parser = argparse.ArgumentParser(
        description="Importa a PostGIS el histórico descargado de focos NASA FIRMS para España."
    )
    parser.add_argument(
        "--input-root",
        default=str(root_dir / "data-store/files/raw/nasa/firms/historical"),
    )
    parser.add_argument("--date-from", default="2025-05-01")
    parser.add_argument("--date-to", default="2025-08-31")
    parser.add_argument(
        "--sources",
        nargs="*",
        default=list(FIRMS_HISTORICAL_SOURCES),
        choices=list(FIRMS_HISTORICAL_SOURCES),
    )
    parser.add_argument(
        "--bbox-regions",
        nargs="*",
        default=list(FIRMS_HISTORICAL_BBOXES.keys()),
        choices=list(FIRMS_HISTORICAL_BBOXES.keys()),
    )
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def normalize_confidence(value: str | None) -> str | None:
    raw = (value or "").strip().lower()
    aliases = {
        "low": "l",
        "l": "l",
        "nominal": "n",
        "n": "n",
        "high": "h",
        "h": "h",
    }
    return aliases.get(raw) if raw else None


def normalize_daynight(value: str | None) -> str | None:
    raw = (value or "").strip().upper()
    if raw in {"D", "N"}:
        return raw
    return None


def normalize_time(value: str | None) -> str:
    raw = (value or "").strip()
    return raw.zfill(4)


def observed_at_iso(acq_date: str, acq_time: str) -> str:
    normalized_time = normalize_time(acq_time)
    return f"{acq_date}T{normalized_time[:2]}:{normalized_time[2:]}:00+00:00"


@lru_cache(maxsize=1)
def load_spain_geometry():
    boundary_path = repo_root() / SPAIN_BOUNDARY_PATH
    if not boundary_path.is_file():
        raise FileNotFoundError(f"No existe el límite NUTS de España: {boundary_path}")
    geojson = json.loads(boundary_path.read_text(encoding="utf-8"))
    features = geojson.get("features", [geojson]) if "features" in geojson else [geojson]
    geometries = [shape(feature["geometry"]) for feature in features if feature.get("geometry")]
    if not geometries:
        raise ValueError(f"El GeoJSON {boundary_path} no contiene geometrías")
    return unary_union(geometries)


def is_in_spain_nuts(latitude: float, longitude: float) -> bool:
    return bool(load_spain_geometry().covers(Point(longitude, latitude)))


def infer_instrument(row: dict[str, str], firms_source: str) -> str | None:
    value = (row.get("instrument") or "").strip()
    if value:
        return value
    if firms_source.startswith("VIIRS_"):
        return "VIIRS"
    if firms_source.startswith("MODIS_"):
        return "MODIS"
    return None


def stable_row_hash(row: dict[str, str]) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def relative_path(path: Path, root_dir: Path) -> str:
    return path.resolve().relative_to(root_dir.resolve()).as_posix()


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_manifest_paths(input_root: Path) -> list[Path]:
    return sorted(input_root.glob("sp/*/*/*/*/*.json"))


def manifest_in_scope(manifest: dict, date_from: str, date_to: str, sources: set[str], bbox_regions: set[str]) -> bool:
    return (
        manifest.get("request_date_to", "") >= date_from
        and manifest.get("request_date_from", "") <= date_to
        and manifest.get("firms_source") in sources
        and manifest.get("bbox_region") in bbox_regions
    )


def create_ingest_record(
    conn: psycopg.Connection,
    file_path: str,
    manifest: dict,
) -> int:
    metadata = {
        "dataset_type": manifest["dataset_type"],
        "firms_source": manifest["firms_source"],
        "bbox_region": manifest["bbox_region"],
        "request_date_from": manifest["request_date_from"],
        "request_date_to": manifest["request_date_to"],
        "request_day_range": manifest["request_day_range"],
        "row_count": manifest["row_count"],
        "import_started_at": utc_now_iso(),
    }
    sql = """
        INSERT INTO ingest.ingest_file (
            dataset_id,
            source_system,
            source_layer,
            origin_format,
            file_path,
            content_hash,
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
                manifest["firms_source"],
                "historical_csv_block",
                file_path,
                manifest["source_file_sha256"],
                json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            ),
        )
        return int(cur.fetchone()[0])


def mark_ingest_status(conn: psycopg.Connection, ingest_id: int, status: str, error: str | None = None) -> None:
    sql = """
        UPDATE ingest.ingest_file
        SET
            status = %s,
            error_json = %s::jsonb
        WHERE ingest_id = %s
    """
    payload = {}
    if error:
        payload = {"message": error}
    with conn.cursor() as cur:
        cur.execute(sql, (status, json.dumps(payload, ensure_ascii=False, sort_keys=True), ingest_id))


def upsert_download_row(conn: psycopg.Connection, ingest_id: int, manifest: dict) -> int:
    minx, miny, maxx, maxy = [float(value) for value in manifest["bbox_value"].split(",")]
    sql = """
        INSERT INTO source.firms_hotspot_download_file (
            dataset_type,
            firms_source,
            bbox_region,
            bbox,
            request_date_from,
            request_date_to,
            request_day_range,
            source_file_path,
            source_file_sha256,
            row_count,
            downloaded_at,
            ingest_id,
            metadata_json
        )
        VALUES (
            %s,
            %s,
            %s,
            ST_MakeEnvelope(%s, %s, %s, %s, 4326),
            %s::date,
            %s::date,
            %s,
            %s,
            %s,
            %s,
            %s::timestamptz,
            %s,
            %s::jsonb
        )
        ON CONFLICT (source_file_path) DO UPDATE
        SET
            dataset_type = EXCLUDED.dataset_type,
            firms_source = EXCLUDED.firms_source,
            bbox_region = EXCLUDED.bbox_region,
            bbox = EXCLUDED.bbox,
            request_date_from = EXCLUDED.request_date_from,
            request_date_to = EXCLUDED.request_date_to,
            request_day_range = EXCLUDED.request_day_range,
            source_file_sha256 = EXCLUDED.source_file_sha256,
            row_count = EXCLUDED.row_count,
            downloaded_at = EXCLUDED.downloaded_at,
            ingest_id = EXCLUDED.ingest_id,
            imported_at = now(),
            metadata_json = EXCLUDED.metadata_json
        RETURNING source_download_id
    """
    metadata_json = json.dumps(
        {
            "source_file_sha256": manifest["source_file_sha256"],
            "response_size_bytes": manifest.get("response_size_bytes"),
            "imported_at": utc_now_iso(),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                manifest["dataset_type"],
                manifest["firms_source"],
                manifest["bbox_region"],
                minx,
                miny,
                maxx,
                maxy,
                manifest["request_date_from"],
                manifest["request_date_to"],
                manifest["request_day_range"],
                manifest["source_file_path"],
                manifest["source_file_sha256"],
                manifest["row_count"],
                manifest["downloaded_at"],
                ingest_id,
                metadata_json,
            ),
        )
        return int(cur.fetchone()[0])


def clear_existing_observations(conn: psycopg.Connection, source_download_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM core.firms_hotspot
            WHERE representative_source_observation_id IN (
                SELECT source_observation_id
                FROM source.firms_hotspot_observation
                WHERE source_download_id = %s
            )
            """,
            (source_download_id,),
        )
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM source.firms_hotspot_observation WHERE source_download_id = %s",
            (source_download_id,),
        )


def build_observation_rows(
    csv_path: Path,
    manifest: dict,
) -> list[tuple]:
    rows: list[tuple] = []
    with csv_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or "latitude" not in reader.fieldnames or "longitude" not in reader.fieldnames:
            return rows
        for source_row_number, row in enumerate(reader, start=1):
            latitude = parse_float(row.get("latitude"))
            longitude = parse_float(row.get("longitude"))
            acq_date = (row.get("acq_date") or "").strip()
            satellite = (row.get("satellite") or "").strip()
            if latitude is None or longitude is None or not acq_date or not satellite:
                continue
            acq_time = normalize_time(row.get("acq_time"))
            in_spain_nuts = is_in_spain_nuts(latitude, longitude)
            rows.append(
                (
                    source_row_number,
                    stable_row_hash(row),
                    manifest["dataset_type"],
                    manifest["firms_source"],
                    manifest["bbox_region"],
                    latitude,
                    longitude,
                    parse_float(row.get("bright_ti4")),
                    parse_float(row.get("scan")),
                    parse_float(row.get("track")),
                    acq_date,
                    acq_time,
                    satellite,
                    infer_instrument(row, manifest["firms_source"]),
                    normalize_confidence(row.get("confidence")),
                    (row.get("version") or "").strip() or None,
                    parse_float(row.get("bright_ti5")),
                    parse_float(row.get("frp")),
                    normalize_daynight(row.get("daynight")),
                    observed_at_iso(acq_date, acq_time),
                    in_spain_nuts,
                    json.dumps(row, ensure_ascii=False, sort_keys=True),
                    json.dumps(
                        {
                            "source_file_path": manifest["source_file_path"],
                            "source_file_sha256": manifest["source_file_sha256"],
                            "in_spain_nuts": in_spain_nuts,
                            "spain_boundary": SPAIN_BOUNDARY_PATH,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                )
            )
    return rows


def insert_observation_rows(
    conn: psycopg.Connection,
    source_download_id: int,
    rows: Iterable[tuple],
) -> int:
    sql = """
        INSERT INTO source.firms_hotspot_observation (
            source_download_id,
            source_row_number,
            source_row_hash,
            dataset_type,
            firms_source,
            bbox_region,
            latitude,
            longitude,
            bright_ti4,
            scan,
            track,
            acq_date,
            acq_time,
            satellite,
            instrument,
            confidence,
            version,
            bright_ti5,
            frp,
            daynight,
            observed_at,
            in_spain_nuts,
            geom,
            raw_json,
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
            %s::date,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s::timestamptz,
            %s,
            ST_SetSRID(ST_MakePoint(%s, %s), 4326),
            %s::jsonb,
            %s::jsonb
        )
    """
    prepared_rows = [
        (
            source_download_id,
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            row[6],
            row[7],
            row[8],
            row[9],
            row[10],
            row[11],
            row[12],
            row[13],
            row[14],
            row[15],
            row[16],
            row[17],
            row[18],
            row[19],
            row[20],
            row[6],
            row[5],
            row[21],
            row[22],
        )
        for row in rows
    ]
    if not prepared_rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql, prepared_rows)
    return len(prepared_rows)


def main() -> int:
    args = parse_args()
    merged_env = load_env()
    conninfo = pg_conninfo(merged_env)
    input_root = Path(args.input_root)
    repo_dir = repo_root()

    if not input_root.is_dir():
        raise FileNotFoundError(f"No existe el directorio {input_root}")

    manifest_paths = iter_manifest_paths(input_root)
    manifests: list[tuple[Path, dict]] = []
    for path in manifest_paths:
        manifest = load_manifest(path)
        if manifest_in_scope(
            manifest,
            args.date_from,
            args.date_to,
            set(args.sources),
            set(args.bbox_regions),
        ):
            manifests.append((path, manifest))

    if not manifests:
        print("No se encontraron manifiestos FIRMS para el rango indicado.", file=sys.stderr)
        return 1

    imported_files = 0
    imported_rows = 0
    failed = 0

    print(f"Importando {len(manifests)} bloques FIRMS históricos desde {input_root}")
    with psycopg.connect(conninfo) as conn:
        for manifest_path, manifest in manifests:
            csv_path = repo_dir / manifest["source_file_path"]
            if not csv_path.is_file():
                print(f"- {manifest['source_file_path']}: ERROR no existe el CSV", file=sys.stderr)
                failed += 1
                continue
            ingest_id = create_ingest_record(conn, manifest["source_file_path"], manifest)
            try:
                source_download_id = upsert_download_row(conn, ingest_id, manifest)
                clear_existing_observations(conn, source_download_id)
                observation_rows = build_observation_rows(csv_path, manifest)
                inserted = insert_observation_rows(conn, source_download_id, observation_rows)
                mark_ingest_status(conn, ingest_id, "ok")
                conn.commit()
                imported_files += 1
                imported_rows += inserted
                rel_manifest_path = relative_path(manifest_path, repo_dir)
                print(
                    f"- {rel_manifest_path}: download_id={source_download_id}, "
                    f"rows={inserted}, manifest_rows={manifest['row_count']}"
                )
            except Exception as exc:
                conn.rollback()
                with psycopg.connect(conninfo) as error_conn:
                    mark_ingest_status(error_conn, ingest_id, "failed", str(exc))
                    error_conn.commit()
                failed += 1
                print(f"- {manifest['source_file_path']}: ERROR {exc}", file=sys.stderr)

    print(
        "Resumen importación FIRMS: "
        f"files={imported_files}, rows={imported_rows}, failed={failed}"
    )
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
