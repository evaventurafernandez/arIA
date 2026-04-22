#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from osgeo import gdal, ogr, osr

CODE_FILTER = ("111", "112", "121", "211", "242", "311", "312", "313", "321", "322", "323", "324")
DATASET_ID = "landcover_corine_2018_filtered"
SOURCE_SYSTEM = "copernicus_corine_2018"
ORIGIN_FORMAT = "FileGDB"


@dataclass(frozen=True)
class LayerTarget:
    source_layer: str
    staging_table: str
    source_table: str


TARGETS = (
    LayerTarget("CLC18_ES", "staging.landcover_clc18_es_raw", "source.landcover_clc18_es"),
    LayerTarget("CLC18_ES_Canarias", "staging.landcover_clc18_es_canarias_raw", "source.landcover_clc18_es_canarias"),
)


def env(name: str, default: str) -> str:
    value = os.environ.get(name, default)
    return value if value else default


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def raw_zip_path(root_dir: Path) -> Path:
    return Path(env("RAW_ZIP", str(root_dir / "data-store/files/CLC2018_GDB.zip")))


def canonical_extract_dir(root_dir: Path) -> Path:
    return Path(
        env(
            "EXTRACTED_GDB_DIR",
            str(root_dir / "data-store/files/raw/copernicus/corine/landcover_corine_2018_filtered/2018/CLC2018_ES.gdb"),
        )
    )


def pg_conn_string() -> str:
    db = env("POSTGRES_DB", "meteovisor")
    user = env("POSTGRES_USER", "meteovisor")
    password = env("POSTGRES_PASSWORD", "meteovisor")
    host = env("POSTGRES_HOST", "postgres")
    port = env("POSTGRES_PORT", "5432")
    return f"PG:host={host} port={port} dbname={db} user={user} password={password}"


def sql_literal(value: str) -> str:
    return value.replace("'", "''")


def sql_json(value: dict[str, object]) -> str:
    return sql_literal(json.dumps(value, ensure_ascii=False, sort_keys=True))


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iso_timestamp_from_stat(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def attribute_filter() -> str:
    custom = os.environ.get("WHERE_CLAUSE")
    if custom:
        return custom
    values = ",".join(f"'{value}'" for value in CODE_FILTER)
    return f"CODE_18 IN ({values})"


def max_features() -> int:
    return int(env("MAX_FEATURES_PER_LAYER", "0"))


def should_clean_source() -> bool:
    return env("TRUNCATE_SOURCE", "1").lower() not in {"0", "false", "no"}


def should_clean_staging() -> bool:
    return env("TRUNCATE_STAGING", "1").lower() not in {"0", "false", "no"}


def extraction_marker(raw_zip: Path) -> str:
    return f"{raw_zip.stat().st_size}:{int(raw_zip.stat().st_mtime)}"


def ensure_extracted_gdb(raw_zip: Path, extracted_gdb_dir: Path) -> Path:
    if not raw_zip.is_file():
        raise FileNotFoundError(f"ZIP no encontrado: {raw_zip}")

    marker_file = extracted_gdb_dir.parent / ".extract.marker"
    expected_marker = extraction_marker(raw_zip)
    existing_marker = marker_file.read_text(encoding="utf-8").strip() if marker_file.is_file() else ""
    gdbtable_exists = extracted_gdb_dir.is_dir() and any(extracted_gdb_dir.glob("*.gdbtable"))
    if gdbtable_exists and existing_marker == expected_marker:
        return extracted_gdb_dir

    extracted_gdb_dir.parent.mkdir(parents=True, exist_ok=True)
    if extracted_gdb_dir.exists():
        shutil.rmtree(extracted_gdb_dir)

    target_prefix = f"{extracted_gdb_dir.name}/"
    with zipfile.ZipFile(raw_zip) as archive:
        members = [member for member in archive.namelist() if member.startswith(target_prefix)]
        if not members:
            raise RuntimeError(f"No se encontro {extracted_gdb_dir.name} dentro de {raw_zip}")
        archive.extractall(path=extracted_gdb_dir.parent, members=members)

    marker_file.write_text(expected_marker, encoding="utf-8")
    return extracted_gdb_dir


def open_source_dataset(extracted_gdb_dir: Path) -> ogr.DataSource:
    ds = ogr.Open(str(extracted_gdb_dir), update=0)
    if ds is None:
        raise RuntimeError(f"No se pudo abrir el dataset FileGDB extraido: {extracted_gdb_dir}")
    return ds


def validate_layers(ds: ogr.DataSource) -> None:
    names = {ds.GetLayerByIndex(i).GetName() for i in range(ds.GetLayerCount())}
    missing = [target.source_layer for target in TARGETS if target.source_layer not in names]
    if missing:
        raise RuntimeError(f"Faltan capas esperadas en el FileGDB: {', '.join(missing)}")


def open_pg_dataset(pg_conn: str) -> ogr.DataSource:
    ds = ogr.Open(pg_conn, update=1)
    if ds is None:
        raise RuntimeError("No se pudo abrir la conexion PostgreSQL en modo escritura")
    return ds


def exec_sql(pg_ds: ogr.DataSource, sql: str) -> None:
    layer = pg_ds.ExecuteSQL(sql)
    if layer is not None:
        pg_ds.ReleaseResultSet(layer)


def fetch_one_value(pg_ds: ogr.DataSource, sql: str, field_name: str) -> int | str:
    layer = pg_ds.ExecuteSQL(sql)
    if layer is None:
        raise RuntimeError(f"No se pudo ejecutar SQL: {sql}")
    try:
        feature = layer.GetNextFeature()
        if feature is None:
            raise RuntimeError(f"Consulta sin filas: {sql}")
        return feature.GetField(field_name)
    finally:
        pg_ds.ReleaseResultSet(layer)


def create_ingest_record(
    pg_ds: ogr.DataSource,
    raw_zip: Path,
    extracted_gdb_dir: Path,
    target: LayerTarget,
    filter_expr: str,
    feature_limit: int,
) -> int:
    metadata = {
        "raw_gdb_dir": str(extracted_gdb_dir),
        "filter_expr": filter_expr,
        "target_layer": target.source_layer,
        "staging_table": target.staging_table,
        "source_table": target.source_table,
        "load_mode": "bulk_gdal_to_staging_sql_to_source",
        "max_features_per_layer": feature_limit,
    }
    sql = (
        "INSERT INTO ingest.ingest_file (dataset_id, source_system, source_layer, origin_format, file_path, content_hash, captured_at, status, metadata_json) "
        f"VALUES ('{sql_literal(DATASET_ID)}', '{sql_literal(SOURCE_SYSTEM)}', '{sql_literal(target.source_layer)}', '{sql_literal(ORIGIN_FORMAT)}', "
        f"'{sql_literal(str(raw_zip))}', '{sql_literal(file_hash(raw_zip))}', '{sql_literal(iso_timestamp_from_stat(raw_zip))}', 'running', "
        f"'{sql_json(metadata)}'::jsonb) RETURNING ingest_id"
    )
    ingest_id = fetch_one_value(pg_ds, sql, "ingest_id")
    return int(ingest_id)


def update_ingest_record(
    pg_ds: ogr.DataSource,
    ingest_id: int,
    status: str,
    metadata: dict[str, object] | None = None,
    error: dict[str, object] | None = None,
) -> None:
    sql = (
        "UPDATE ingest.ingest_file "
        f"SET status = '{sql_literal(status)}', ingested_at = now(), metadata_json = '{sql_json(metadata or {})}'::jsonb, "
        f"error_json = '{sql_json(error or {})}'::jsonb WHERE ingest_id = {ingest_id}"
    )
    exec_sql(pg_ds, sql)


def bulk_load_to_staging(pg_conn: str, extracted_gdb_dir: Path, target: LayerTarget, filter_expr: str, feature_limit: int) -> None:
    sql = f"SELECT OBJECTID AS source_objectid, CODE_18 FROM {target.source_layer} WHERE {filter_expr}"
    options = gdal.VectorTranslateOptions(
        format="PostgreSQL",
        accessMode="append",
        SQLStatement=sql,
        SQLDialect="OGRSQL",
        layerName=target.staging_table,
        dstSRS="EPSG:4326",
        reproject=True,
        geometryType="PROMOTE_TO_MULTI",
        limit=feature_limit if feature_limit > 0 else None,
    )
    result = gdal.VectorTranslate(pg_conn, str(extracted_gdb_dir), options=options)
    if result is None:
        raise RuntimeError(f"Fallo la carga GDAL a staging para {target.source_layer}")
    result = None


def stage_count(pg_ds: ogr.DataSource, target: LayerTarget) -> int:
    return int(fetch_one_value(pg_ds, f"SELECT count(*) AS n FROM {target.staging_table}", "n"))


def consolidate_source(pg_ds: ogr.DataSource, target: LayerTarget, ingest_id: int) -> int:
    sql = (
        f"INSERT INTO {target.source_table} (source_objectid, ingest_id, code_18, geom) "
        f"SELECT source_objectid, {ingest_id}, code_18, geom FROM {target.staging_table}"
    )
    exec_sql(pg_ds, sql)
    return int(fetch_one_value(pg_ds, f"SELECT count(*) AS n FROM {target.source_table} WHERE ingest_id = {ingest_id}", "n"))


def truncate_tables(pg_ds: ogr.DataSource) -> None:
    if should_clean_staging():
        for target in TARGETS:
            exec_sql(pg_ds, f"TRUNCATE TABLE {target.staging_table}")
    if should_clean_source():
        for target in TARGETS:
            exec_sql(pg_ds, f"TRUNCATE TABLE {target.source_table} RESTART IDENTITY")


def report_counts(pg_ds: ogr.DataSource) -> None:
    for target in TARGETS:
        source_count = fetch_one_value(pg_ds, f"SELECT count(*) AS n FROM {target.source_table}", "n")
        print(f"{target.source_table}: {source_count} features persistidas")


def import_layer(
    pg_ds: ogr.DataSource,
    pg_conn: str,
    raw_zip: Path,
    extracted_gdb_dir: Path,
    target: LayerTarget,
    filter_expr: str,
    feature_limit: int,
) -> None:
    ingest_id = create_ingest_record(pg_ds, raw_zip, extracted_gdb_dir, target, filter_expr, feature_limit)
    try:
        if should_clean_staging():
            exec_sql(pg_ds, f"TRUNCATE TABLE {target.staging_table}")

        bulk_load_to_staging(pg_conn, extracted_gdb_dir, target, filter_expr, feature_limit)
        staged_features = stage_count(pg_ds, target)
        exec_sql(pg_ds, f"DELETE FROM {target.source_table} WHERE ingest_id = {ingest_id}")
        source_features = consolidate_source(pg_ds, target, ingest_id)
        update_ingest_record(
            pg_ds,
            ingest_id,
            "ok",
            metadata={
                "staged_features": staged_features,
                "imported_features": source_features,
                "staging_table": target.staging_table,
                "source_table": target.source_table,
                "source_layer": target.source_layer,
                "filter_expr": filter_expr,
                "raw_gdb_dir": str(extracted_gdb_dir),
                "load_mode": "bulk_gdal_to_staging_sql_to_source",
                "max_features_per_layer": feature_limit,
            },
        )
        print(f"{target.source_layer}: staging={staged_features}, source={source_features}")
    except Exception as exc:
        update_ingest_record(
            pg_ds,
            ingest_id,
            "failed",
            metadata={
                "staging_table": target.staging_table,
                "source_table": target.source_table,
                "source_layer": target.source_layer,
                "raw_gdb_dir": str(extracted_gdb_dir),
                "load_mode": "bulk_gdal_to_staging_sql_to_source",
                "max_features_per_layer": feature_limit,
            },
            error={"message": str(exc)},
        )
        raise


def main() -> int:
    gdal.UseExceptions()
    ogr.UseExceptions()
    osr.UseExceptions()
    gdal.SetConfigOption("OGR_ORGANIZE_POLYGONS", env("OGR_ORGANIZE_POLYGONS", "SKIP"))
    gdal.SetConfigOption("PG_USE_COPY", "YES")

    root_dir = repo_root()
    raw_zip = raw_zip_path(root_dir)
    extracted_gdb_dir = canonical_extract_dir(root_dir)
    filter_expr = attribute_filter()
    feature_limit = max_features()
    pg_conn = pg_conn_string()

    print(f"ZIP de entrada: {raw_zip}")
    print(f"Directorio GDB extraido: {extracted_gdb_dir}")
    print(f"Filtro: {filter_expr}")
    if feature_limit > 0:
        print(f"MAX_FEATURES_PER_LAYER={feature_limit}")

    extracted_gdb_dir = ensure_extracted_gdb(raw_zip, extracted_gdb_dir)
    source_ds = open_source_dataset(extracted_gdb_dir)
    validate_layers(source_ds)
    source_ds = None

    pg_ds = open_pg_dataset(pg_conn)
    truncate_tables(pg_ds)

    for target in TARGETS:
        print(f"Importando {target.source_layer} -> {target.staging_table} -> {target.source_table}")
        import_layer(pg_ds, pg_conn, raw_zip, extracted_gdb_dir, target, filter_expr, feature_limit)

    report_counts(pg_ds)
    print("Importación bulk staging -> source completada.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
