#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg


def env(name: str, default: str) -> str:
    value = os.environ.get(name, default)
    return value if value else default


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


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


def parse_args() -> argparse.Namespace:
    root_dir = repo_root()
    parser = argparse.ArgumentParser(
        description="Publica en Postgres los manifiestos diarios procesados de burnt area."
    )
    parser.add_argument("--dataset-version", default="v4", choices=["v3", "v4"])
    parser.add_argument("--delivery-format", default="cog", choices=["cog", "nc"])
    parser.add_argument("--mode", default="daily", choices=["daily", "cumulative"])
    parser.add_argument("--date-from", default="2025-05-01")
    parser.add_argument("--date-to", default="2025-08-31")
    parser.add_argument("--manifest-root", default=str(root_dir / "data/copernicus/burnt_area/manifests"))
    return parser.parse_args()


def iter_manifest_paths(manifest_dir: Path, date_from: str, date_to: str) -> list[Path]:
    if not manifest_dir.is_dir():
        raise FileNotFoundError(f"No existe el directorio de manifiestos {manifest_dir}")
    paths = []
    for path in sorted(manifest_dir.glob("*.json")):
        if path.stem < date_from or path.stem > date_to:
            continue
        paths.append(path)
    return paths


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def update_core_row(conn: psycopg.Connection, manifest: dict) -> None:
    sql = """
        UPDATE core.burnt_area_daily_file
        SET
            local_file_path = %s,
            local_spain_cog_path = %s,
            local_tiles_path = %s,
            publication_status = %s,
            publication_notes = %s,
            metadata_json = COALESCE(metadata_json, '{}'::jsonb) || %s::jsonb,
            canonicalized_at = now()
        WHERE dataset_version = %s
          AND delivery_format = %s
          AND nominal_date = %s::date
    """
    metadata_json = json.dumps(
        {
            "burnt_area_publish_manifest": {
                "mode": manifest["mode"],
                "generated_at": manifest["generated_at"],
                "source_descriptor": manifest.get("source_descriptor"),
                "tile_count": manifest.get("tile_count"),
                "tiles_generated": manifest.get("tiles_generated"),
                "metadata_json": manifest.get("metadata_json", {}),
            }
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                manifest.get("local_file_path"),
                manifest.get("local_spain_cog_path"),
                manifest.get("local_tiles_path") if bool(manifest.get("tiles_generated")) else None,
                manifest["publication_status"],
                manifest.get("publication_notes"),
                metadata_json,
                manifest["dataset_version"],
                manifest["delivery_format"],
                manifest["nominal_date"],
            ),
        )
        if cur.rowcount != 1:
            raise RuntimeError(
                "No se encontro la fila core.burnt_area_daily_file para "
                f"{manifest['dataset_version']}/{manifest['delivery_format']}/{manifest['nominal_date']}"
            )


def delete_country_stat(conn: psycopg.Connection, manifest: dict) -> None:
    sql = """
        DELETE FROM pub.burnt_area_daily_stat
        WHERE dataset_version = %s
          AND delivery_format = %s
          AND nominal_date = %s::date
          AND stat_scope = 'country'
          AND area_code = 'ES'
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                manifest["dataset_version"],
                manifest["delivery_format"],
                manifest["nominal_date"],
            ),
        )


def upsert_country_stat(conn: psycopg.Connection, manifest: dict) -> None:
    sql = """
        INSERT INTO pub.burnt_area_daily_stat (
            dataset_version,
            delivery_format,
            nominal_date,
            stat_scope,
            area_code,
            area_label,
            burned_area_ha,
            burned_pixel_count,
            burned_fraction_sum,
            tiles_generated,
            stats_generated_at,
            metadata_json
        )
        VALUES (
            %s,
            %s,
            %s::date,
            'country',
            'ES',
            'España',
            %s,
            %s,
            %s,
            %s,
            now(),
            %s::jsonb
        )
        ON CONFLICT (dataset_version, delivery_format, nominal_date, stat_scope, area_code) DO UPDATE
        SET
            burned_area_ha = EXCLUDED.burned_area_ha,
            burned_pixel_count = EXCLUDED.burned_pixel_count,
            burned_fraction_sum = EXCLUDED.burned_fraction_sum,
            tiles_generated = EXCLUDED.tiles_generated,
            stats_generated_at = now(),
            metadata_json = EXCLUDED.metadata_json
    """
    metadata_json = json.dumps(
        {
            "mode": manifest["mode"],
            "tile_count": manifest.get("tile_count"),
            "generated_at": manifest.get("generated_at"),
            "source_product_name": manifest.get("source_product_name"),
            "source_descriptor": manifest.get("source_descriptor"),
            "metadata_json": manifest.get("metadata_json", {}),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                manifest["dataset_version"],
                manifest["delivery_format"],
                manifest["nominal_date"],
                manifest.get("burned_area_ha"),
                manifest.get("burned_pixel_count"),
                manifest.get("burned_fraction_sum"),
                bool(manifest.get("tiles_generated")),
                metadata_json,
            ),
        )


def main() -> int:
    args = parse_args()
    manifest_dir = Path(args.manifest_root) / args.dataset_version / args.mode
    manifest_paths = iter_manifest_paths(manifest_dir, args.date_from, args.date_to)
    if not manifest_paths:
        print("No hay manifiestos para publicar en ese rango.", file=sys.stderr)
        return 1

    conninfo = pg_conninfo()
    print(f"Publicando {len(manifest_paths)} manifiestos desde {manifest_dir}")
    print(f"PostgreSQL: {conninfo}")

    published = 0
    failed = 0
    with psycopg.connect(conninfo) as conn:
        for path in manifest_paths:
            manifest = load_manifest(path)
            try:
                update_core_row(conn, manifest)
                delete_country_stat(conn, manifest)
                if manifest["publication_status"] == "published":
                    upsert_country_stat(conn, manifest)
                    published += 1
                else:
                    failed += 1
                conn.commit()
                print(f"- {manifest['nominal_date']}: {manifest['publication_status']}")
            except Exception:
                conn.rollback()
                raise

    print(f"Resumen publicado: ok={published}, failed={failed}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
