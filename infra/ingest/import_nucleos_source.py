#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from osgeo import gdal, ogr, osr

DATASET_ID = "nucleos_poblacion_btn"
SOURCE_SYSTEM = "ign_btn"
ORIGIN_FORMAT = "GPKG"
DEFAULT_GPKG_LAYER = "btn0502s_ent_pob"
STAGING_TABLE = "staging.nucleos_poblacion_btn_raw"
SOURCE_TABLE = "source.nucleos_poblacion_btn"


def env(name: str, default: str) -> str:
    value = os.environ.get(name, default)
    return value if value else default


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def raw_zip_path(root_dir: Path) -> Path:
    return Path(
        env(
            "RAW_ZIP",
            str(root_dir / "data-store/files/raw/ign/nucleos_poblacion/BTN_T_Poblaciones_gpkg.zip"),
        )
    )


def canonical_gpkg_path(root_dir: Path) -> Path:
    return Path(
        env(
            "EXTRACTED_GPKG_PATH",
            str(root_dir / "data-store/files/raw/ign/nucleos_poblacion/BTN_T_poblaciones.gpkg"),
        )
    )


def gpkg_layer() -> str:
    return env("GPKG_LAYER", DEFAULT_GPKG_LAYER)


def pg_conn_string() -> str:
    db = env("POSTGRES_DB", "meteovisor")
    user = env("POSTGRES_USER", "meteovisor")
    password = env("POSTGRES_PASSWORD", "meteovisor")
    host = env("POSTGRES_HOST", "postgres")
    port = env("POSTGRES_PORT", "5432")
    return f"PG:host={host} port={port} dbname={db} user={user} password={password}"


def sql_literal(value: object) -> str:
    return str(value).replace("'", "''")


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


def max_features() -> int:
    return int(env("MAX_FEATURES", env("MAX_FEATURES_PER_LAYER", "0")))


def should_clean_source() -> bool:
    return env("TRUNCATE_SOURCE", "1").lower() not in {"0", "false", "no"}


def should_clean_staging() -> bool:
    return env("TRUNCATE_STAGING", "1").lower() not in {"0", "false", "no"}


def extraction_marker(raw_zip: Path) -> str:
    return f"{raw_zip.stat().st_size}:{int(raw_zip.stat().st_mtime)}"


def find_gpkg_member(archive: zipfile.ZipFile) -> str:
    members = [
        member
        for member in archive.namelist()
        if not member.endswith("/") and member.lower().endswith(".gpkg")
    ]
    if not members:
        raise RuntimeError("No se encontro ningun GeoPackage dentro del ZIP")
    preferred = [member for member in members if Path(member).name == "BTN_T_poblaciones.gpkg"]
    return preferred[0] if preferred else members[0]


def ensure_extracted_gpkg(raw_zip: Path, extracted_gpkg_path: Path) -> Path:
    if not raw_zip.is_file():
        raise FileNotFoundError(f"ZIP no encontrado: {raw_zip}")

    marker_file = extracted_gpkg_path.with_suffix(extracted_gpkg_path.suffix + ".extract.marker")
    expected_marker = extraction_marker(raw_zip)
    existing_marker = marker_file.read_text(encoding="utf-8").strip() if marker_file.is_file() else ""
    if extracted_gpkg_path.is_file() and existing_marker == expected_marker:
        return extracted_gpkg_path

    extracted_gpkg_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(raw_zip) as archive:
        member = find_gpkg_member(archive)
        with archive.open(member) as source, extracted_gpkg_path.open("wb") as target:
            shutil.copyfileobj(source, target)

    marker_file.write_text(expected_marker, encoding="utf-8")
    return extracted_gpkg_path


def open_source_dataset(extracted_gpkg_path: Path) -> ogr.DataSource:
    ds = ogr.Open(str(extracted_gpkg_path), update=0)
    if ds is None:
        raise RuntimeError(f"No se pudo abrir el GeoPackage extraido: {extracted_gpkg_path}")
    return ds


def validate_layer(ds: ogr.DataSource, layer_name: str) -> None:
    names = {ds.GetLayerByIndex(i).GetName() for i in range(ds.GetLayerCount())}
    if layer_name not in names:
        raise RuntimeError(f"Falta la capa esperada en el GeoPackage: {layer_name}")


def open_pg_dataset(pg_conn: str) -> ogr.DataSource:
    ds = ogr.Open(pg_conn, update=1)
    if ds is None:
        raise RuntimeError("No se pudo abrir la conexion PostgreSQL en modo escritura")
    return ds


def exec_sql(pg_ds: ogr.DataSource, sql: str) -> None:
    layer = pg_ds.ExecuteSQL(sql)
    if layer is not None:
        pg_ds.ReleaseResultSet(layer)


def fetch_one_value(pg_ds: ogr.DataSource, sql: str, field_name: str) -> int | str | None:
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


def relation_column_exists(pg_ds: ogr.DataSource, schema: str, table: str, column: str) -> bool:
    sql = (
        "SELECT count(*) AS n FROM information_schema.columns "
        f"WHERE table_schema = '{sql_literal(schema)}' "
        f"AND table_name = '{sql_literal(table)}' "
        f"AND column_name = '{sql_literal(column)}'"
    )
    return int(fetch_one_value(pg_ds, sql, "n") or 0) > 0


def create_ingest_record(
    pg_ds: ogr.DataSource,
    raw_zip: Path,
    extracted_gpkg_path: Path,
    layer_name: str,
    feature_limit: int,
) -> int:
    metadata = {
        "raw_zip": str(raw_zip),
        "extracted_gpkg_path": str(extracted_gpkg_path),
        "source_layer": layer_name,
        "staging_table": STAGING_TABLE,
        "source_table": SOURCE_TABLE,
        "load_mode": "bulk_gdal_to_staging_sql_to_source",
        "max_features": feature_limit,
    }
    sql = (
        "INSERT INTO ingest.ingest_file (dataset_id, source_system, source_layer, origin_format, file_path, content_hash, captured_at, status, metadata_json) "
        f"VALUES ('{sql_literal(DATASET_ID)}', '{sql_literal(SOURCE_SYSTEM)}', '{sql_literal(layer_name)}', '{sql_literal(ORIGIN_FORMAT)}', "
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


def truncate_tables(pg_ds: ogr.DataSource) -> None:
    if should_clean_staging():
        exec_sql(pg_ds, f"DROP TABLE IF EXISTS {STAGING_TABLE}")
    if should_clean_source():
        exec_sql(pg_ds, f"TRUNCATE TABLE {SOURCE_TABLE} RESTART IDENTITY")


def build_staging_sql(layer_name: str) -> str:
    return f"""
        SELECT
            rowid AS source_objectid,
            nombre,
            etiqueta,
            tipo_0502,
            ine_0502,
            fecha_ine,
            habit_0502,
            codigo_ep,
            id_ep,
            id_bic,
            id_bicca,
            id_ng,
            prioridad,
            f_alta,
            capit_0502,
            geometry
        FROM {layer_name}
    """


def bulk_load_to_staging(pg_conn: str, extracted_gpkg_path: Path, layer_name: str, feature_limit: int) -> None:
    options = gdal.VectorTranslateOptions(
        format="PostgreSQL",
        accessMode="overwrite",
        SQLStatement=build_staging_sql(layer_name),
        SQLDialect="SQLite",
        layerName=STAGING_TABLE,
        dstSRS="EPSG:4326",
        reproject=True,
        geometryType="PROMOTE_TO_MULTI",
        layerCreationOptions=["GEOMETRY_NAME=geom"],
        forceNullable=True,
        emptyStrAsNull=True,
        limit=feature_limit if feature_limit > 0 else None,
    )
    result = gdal.VectorTranslate(pg_conn, str(extracted_gpkg_path), options=options)
    if result is None:
        raise RuntimeError("Fallo la carga GDAL a staging para nucleos de poblacion")
    result = None


def ensure_staging_contract(pg_ds: ogr.DataSource) -> None:
    if not relation_column_exists(pg_ds, "staging", "nucleos_poblacion_btn_raw", "source_objectid"):
        raise RuntimeError("La tabla staging no contiene source_objectid")
    has_geom = relation_column_exists(pg_ds, "staging", "nucleos_poblacion_btn_raw", "geom")
    has_geometry = relation_column_exists(pg_ds, "staging", "nucleos_poblacion_btn_raw", "geometry")
    if not has_geom and has_geometry:
        exec_sql(pg_ds, f"ALTER TABLE {STAGING_TABLE} RENAME COLUMN geometry TO geom")
        has_geom = True
    if not has_geom:
        raise RuntimeError("La tabla staging no contiene columna geometrica geom")
    exec_sql(pg_ds, f"CREATE INDEX IF NOT EXISTS nucleos_poblacion_btn_raw_geom_gix ON {STAGING_TABLE} USING GIST (geom)")
    exec_sql(pg_ds, f"CREATE INDEX IF NOT EXISTS nucleos_poblacion_btn_raw_source_objectid_idx ON {STAGING_TABLE} (source_objectid)")
    exec_sql(pg_ds, f"ANALYZE {STAGING_TABLE}")


def stage_count(pg_ds: ogr.DataSource) -> int:
    return int(fetch_one_value(pg_ds, f"SELECT count(*) AS n FROM {STAGING_TABLE}", "n") or 0)


def consolidate_source(pg_ds: ogr.DataSource, ingest_id: int) -> int:
    sql = f"""
        INSERT INTO {SOURCE_TABLE} (
            source_objectid,
            ingest_id,
            nombre,
            etiqueta,
            tipo_0502,
            ine_0502,
            fecha_ine,
            habit_0502,
            codigo_ep,
            id_ep,
            id_bic,
            id_bicca,
            id_ng,
            prioridad,
            f_alta,
            capit_0502,
            geom
        )
        SELECT
            source_objectid::bigint,
            {ingest_id},
            nombre,
            etiqueta,
            tipo_0502,
            ine_0502,
            fecha_ine,
            habit_0502,
            codigo_ep,
            id_ep,
            id_bic,
            id_bicca,
            id_ng,
            prioridad,
            f_alta,
            capit_0502,
            geom
        FROM {STAGING_TABLE}
        WHERE geom IS NOT NULL
          AND source_objectid IS NOT NULL
    """
    exec_sql(pg_ds, sql)
    exec_sql(pg_ds, f"ANALYZE {SOURCE_TABLE}")
    return int(fetch_one_value(pg_ds, f"SELECT count(*) AS n FROM {SOURCE_TABLE} WHERE ingest_id = {ingest_id}", "n") or 0)


def report_counts(pg_ds: ogr.DataSource) -> None:
    source_count = fetch_one_value(pg_ds, f"SELECT count(*) AS n FROM {SOURCE_TABLE}", "n")
    print(f"{SOURCE_TABLE}: {source_count} features persistidas")


def main() -> int:
    gdal.UseExceptions()
    ogr.UseExceptions()
    osr.UseExceptions()
    gdal.SetConfigOption("PG_USE_COPY", "YES")

    root_dir = repo_root()
    raw_zip = raw_zip_path(root_dir)
    extracted_gpkg_path = canonical_gpkg_path(root_dir)
    layer_name = gpkg_layer()
    feature_limit = max_features()
    pg_conn = pg_conn_string()

    print(f"ZIP de entrada: {raw_zip}")
    print(f"GeoPackage extraido: {extracted_gpkg_path}")
    print(f"Capa GPKG: {layer_name}")
    if feature_limit > 0:
        print(f"MAX_FEATURES={feature_limit}")

    extracted_gpkg_path = ensure_extracted_gpkg(raw_zip, extracted_gpkg_path)
    source_ds = open_source_dataset(extracted_gpkg_path)
    validate_layer(source_ds, layer_name)
    source_ds = None

    pg_ds = open_pg_dataset(pg_conn)
    truncate_tables(pg_ds)

    ingest_id = create_ingest_record(pg_ds, raw_zip, extracted_gpkg_path, layer_name, feature_limit)
    try:
        bulk_load_to_staging(pg_conn, extracted_gpkg_path, layer_name, feature_limit)
        ensure_staging_contract(pg_ds)
        staged_features = stage_count(pg_ds)
        source_features = consolidate_source(pg_ds, ingest_id)
        update_ingest_record(
            pg_ds,
            ingest_id,
            "ok",
            metadata={
                "staged_features": staged_features,
                "imported_features": source_features,
                "staging_table": STAGING_TABLE,
                "source_table": SOURCE_TABLE,
                "source_layer": layer_name,
                "raw_zip": str(raw_zip),
                "extracted_gpkg_path": str(extracted_gpkg_path),
                "load_mode": "bulk_gdal_to_staging_sql_to_source",
                "max_features": feature_limit,
            },
        )
        print(f"{layer_name}: staging={staged_features}, source={source_features}")
    except Exception as exc:
        update_ingest_record(
            pg_ds,
            ingest_id,
            "failed",
            metadata={
                "staging_table": STAGING_TABLE,
                "source_table": SOURCE_TABLE,
                "source_layer": layer_name,
                "raw_zip": str(raw_zip),
                "extracted_gpkg_path": str(extracted_gpkg_path),
                "load_mode": "bulk_gdal_to_staging_sql_to_source",
                "max_features": feature_limit,
            },
            error={"message": str(exc)},
        )
        raise

    report_counts(pg_ds)
    print("Importacion bulk staging -> source de nucleos completada.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
