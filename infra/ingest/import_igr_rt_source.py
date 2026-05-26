#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from osgeo import gdal, ogr, osr

DATASET_ID = "igr_rt_red_viaria"
SOURCE_SYSTEM = "ign_igr_rt"
ORIGIN_FORMAT = "GPKG_ZIP"
GPKG_MEMBER = "red_viaria.gpkg"
SOURCE_LAYER = "rt_tramo_vial"
STAGING_TABLE = "staging.igr_rt_tramo_vial_raw"
SOURCE_TABLE = "source.igr_rt_tramo_vial"

STAGING_SECONDARY_INDEXES = (
    ("igr_rt_tramo_vial_raw_geom_gix", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_raw_geom_gix ON {STAGING_TABLE} USING GIST (geom)"),
    ("igr_rt_tramo_vial_raw_territory_code_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_raw_territory_code_idx ON {STAGING_TABLE} (territory_code)"),
    ("igr_rt_tramo_vial_raw_source_objectid_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_raw_source_objectid_idx ON {STAGING_TABLE} (source_objectid)"),
    ("igr_rt_tramo_vial_raw_id_tramo_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_raw_id_tramo_idx ON {STAGING_TABLE} (id_tramo)"),
    ("igr_rt_tramo_vial_raw_clase_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_raw_clase_idx ON {STAGING_TABLE} (clase)"),
)

SOURCE_SECONDARY_INDEXES = (
    ("igr_rt_tramo_vial_geom_gix", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_geom_gix ON {SOURCE_TABLE} USING GIST (geom)"),
    ("igr_rt_tramo_vial_ingest_id_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_ingest_id_idx ON {SOURCE_TABLE} (ingest_id)"),
    ("igr_rt_tramo_vial_territory_code_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_territory_code_idx ON {SOURCE_TABLE} (territory_code)"),
    ("igr_rt_tramo_vial_source_zip_name_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_source_zip_name_idx ON {SOURCE_TABLE} (source_zip_name)"),
    ("igr_rt_tramo_vial_source_objectid_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_source_objectid_idx ON {SOURCE_TABLE} (source_objectid)"),
    ("igr_rt_tramo_vial_id_tramo_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_id_tramo_idx ON {SOURCE_TABLE} (id_tramo)"),
    ("igr_rt_tramo_vial_id_vial_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_id_vial_idx ON {SOURCE_TABLE} (id_vial)"),
    ("igr_rt_tramo_vial_clase_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_clase_idx ON {SOURCE_TABLE} (clase)"),
    ("igr_rt_tramo_vial_tipo_tramo_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_tipo_tramo_idx ON {SOURCE_TABLE} (tipo_tramo)"),
    ("igr_rt_tramo_vial_tipo_vial_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_tipo_vial_idx ON {SOURCE_TABLE} (tipo_vial)"),
    ("igr_rt_tramo_vial_titular_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_titular_idx ON {SOURCE_TABLE} (titular)"),
    ("igr_rt_tramo_vial_estadofis_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_estadofis_idx ON {SOURCE_TABLE} (estadofis)"),
    ("igr_rt_tramo_vial_codigo_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_codigo_idx ON {SOURCE_TABLE} (codigo)"),
    ("igr_rt_tramo_vial_nombre_idx", f"CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_nombre_idx ON {SOURCE_TABLE} (nombre)"),
)

TERRITORY_NAMES = {
    "A_CORUNA": "A Coruña",
    "ALBACETE": "Albacete",
    "ALICANTE_ALACANT": "Alicante/Alacant",
    "ALMERIA": "Almería",
    "ARABA_ALAVA": "Araba/Álava",
    "ASTURIAS": "Asturias",
    "AVILA": "Ávila",
    "BADAJOZ": "Badajoz",
    "BARCELONA": "Barcelona",
    "BIZKAIA": "Bizkaia",
    "BURGOS": "Burgos",
    "CACERES": "Cáceres",
    "CADIZ": "Cádiz",
    "CANTABRIA": "Cantabria",
    "CASTELLON_CASTELLO": "Castellón/Castelló",
    "CEUTA": "Ceuta",
    "CIUDAD_REAL": "Ciudad Real",
    "CORDOBA": "Córdoba",
    "CUENCA": "Cuenca",
    "GIPUZKOA": "Gipuzkoa",
    "GIRONA": "Girona",
    "GRANADA": "Granada",
    "GUADALAJARA": "Guadalajara",
    "HUELVA": "Huelva",
    "HUESCA": "Huesca",
    "ILLES_BALEARS": "Illes Balears",
    "JAEN": "Jaén",
    "LA_RIOJA": "La Rioja",
    "LAS_PALMAS": "Las Palmas",
    "LEON": "León",
    "LLEIDA": "Lleida",
    "LUGO": "Lugo",
    "MADRID": "Madrid",
    "MALAGA": "Málaga",
    "MELILLA": "Melilla",
    "MURCIA": "Murcia",
    "NAVARRA": "Navarra",
    "OURENSE": "Ourense",
    "PALENCIA": "Palencia",
    "PONTEVEDRA": "Pontevedra",
    "SALAMANCA": "Salamanca",
    "SANTA_CRUZ_DE_TENERIFE": "Santa Cruz de Tenerife",
    "SEGOVIA": "Segovia",
    "SEVILLA": "Sevilla",
    "SORIA": "Soria",
    "TARRAGONA": "Tarragona",
    "TERUEL": "Teruel",
    "TOLEDO": "Toledo",
    "VALENCIA": "Valencia/València",
    "VALLADOLID": "Valladolid",
    "ZAMORA": "Zamora",
    "ZARAGOZA": "Zaragoza",
}


@dataclass(frozen=True)
class ZipTarget:
    path: Path
    territory_code: str
    territory_name: str


def env(name: str, default: str) -> str:
    value = os.environ.get(name, default)
    return value if value else default


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def raw_dir_path(root_dir: Path) -> Path:
    return Path(env("RAW_DIR", str(root_dir / "data-store/files/raw/ign/igr_rt")))


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


def max_features_per_zip() -> int:
    return int(env("MAX_FEATURES_PER_ZIP", env("MAX_FEATURES_PER_LAYER", "0")))


def max_zips() -> int:
    return int(env("MAX_ZIPS", "0"))


def should_clean_source() -> bool:
    return env("TRUNCATE_SOURCE", "1").lower() not in {"0", "false", "no"}


def should_clean_staging() -> bool:
    return env("TRUNCATE_STAGING", "1").lower() not in {"0", "false", "no"}


def should_continue_on_error() -> bool:
    return env("CONTINUE_ON_ERROR", "0").lower() in {"1", "true", "yes"}


def should_drop_indexes_for_bulk() -> bool:
    return env("DROP_INDEXES_FOR_BULK", "1").lower() not in {"0", "false", "no"}


def selected_zip_names() -> set[str]:
    raw = env("ONLY_ZIPS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def territory_code_from_zip_name(zip_name: str) -> str:
    stem = zip_name
    if stem.lower().endswith(".zip"):
        stem = stem[:-4]
    if stem.startswith("RT_"):
        stem = stem[3:]
    if stem.endswith("_gpkg"):
        stem = stem[:-5]
    return stem


def territory_name_from_code(code: str) -> str:
    if code in TERRITORY_NAMES:
        return TERRITORY_NAMES[code]
    return code.replace("_", " ").title()


def build_zip_target(path: Path) -> ZipTarget:
    code = territory_code_from_zip_name(path.name)
    return ZipTarget(path=path, territory_code=code, territory_name=territory_name_from_code(code))


def iter_zip_targets(root_dir: Path) -> list[ZipTarget]:
    raw_zip = os.environ.get("RAW_ZIP")
    if raw_zip:
        paths = [Path(raw_zip)]
    else:
        raw_dir = raw_dir_path(root_dir)
        paths = sorted(raw_dir.glob(env("ZIP_PATTERN", "RT_*_gpkg.zip")))

    only_zips = selected_zip_names()
    if only_zips:
        paths = [path for path in paths if path.name in only_zips]

    limit = max_zips()
    if limit > 0:
        paths = paths[:limit]

    targets = [build_zip_target(path) for path in paths]
    missing = [str(target.path) for target in targets if not target.path.is_file()]
    if missing:
        raise FileNotFoundError(f"ZIP no encontrado: {', '.join(missing)}")
    if not targets:
        raise RuntimeError("No se encontraron ZIP IGR-RT para importar")
    return targets


def vsi_gpkg_path(raw_zip: Path) -> str:
    zip_path = str(raw_zip).replace("\\", "/")
    return f"/vsizip/{zip_path}/{GPKG_MEMBER}"


def validate_zip_member(raw_zip: Path) -> None:
    with zipfile.ZipFile(raw_zip) as archive:
        names = {member.filename for member in archive.infolist()}
    if GPKG_MEMBER not in names:
        raise RuntimeError(f"{raw_zip.name} no contiene {GPKG_MEMBER}")


def open_source_dataset(vsi_path: str) -> ogr.DataSource:
    ds = ogr.Open(vsi_path, update=0)
    if ds is None:
        raise RuntimeError(f"No se pudo abrir el GeoPackage interno: {vsi_path}")
    return ds


def validate_layer(ds: ogr.DataSource) -> None:
    names = {ds.GetLayerByIndex(i).GetName() for i in range(ds.GetLayerCount())}
    if SOURCE_LAYER not in names:
        raise RuntimeError(f"Falta la capa esperada en {GPKG_MEMBER}: {SOURCE_LAYER}")


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


def create_ingest_record(pg_ds: ogr.DataSource, target: ZipTarget, feature_limit: int) -> int:
    metadata = {
        "raw_zip": str(target.path),
        "source_gpkg_name": GPKG_MEMBER,
        "source_layer": SOURCE_LAYER,
        "territory_code": target.territory_code,
        "territory_name": target.territory_name,
        "staging_table": STAGING_TABLE,
        "source_table": SOURCE_TABLE,
        "load_mode": "bulk_gdal_to_staging_sql_to_source",
        "max_features_per_zip": feature_limit,
    }
    sql = (
        "INSERT INTO ingest.ingest_file (dataset_id, source_system, source_layer, origin_format, file_path, content_hash, captured_at, status, metadata_json) "
        f"VALUES ('{sql_literal(DATASET_ID)}', '{sql_literal(SOURCE_SYSTEM)}', '{sql_literal(SOURCE_LAYER)}', '{sql_literal(ORIGIN_FORMAT)}', "
        f"'{sql_literal(str(target.path))}', '{sql_literal(file_hash(target.path))}', '{sql_literal(iso_timestamp_from_stat(target.path))}', 'running', "
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


def build_staging_sql(target: ZipTarget) -> str:
    return f"""
        SELECT
            rowid + 0 AS source_objectid,
            '{sql_literal(target.path.name)}' AS source_zip_name,
            '{GPKG_MEMBER}' AS source_gpkg_name,
            '{SOURCE_LAYER}' AS source_layer,
            '{sql_literal(target.territory_code)}' AS territory_code,
            '{sql_literal(target.territory_name)}' AS territory_name,
            id_tramo,
            id_vial,
            tipo_tramo,
            tipo_tramd,
            calzada,
            calzadad,
            acceso,
            accesod,
            firme,
            firmed,
            ncarriles,
            sentido,
            sentidod,
            situacion,
            situaciond,
            estadofis,
            estadofisd,
            tipovehic,
            tipovehicd,
            titular,
            titulard,
            orden,
            ordend,
            fuente_t,
            fuente_td,
            codigo,
            dgc_via,
            clase,
            clased,
            tipo_vial,
            tipo_viald,
            nombre,
            nombre_alt,
            fuente_v,
            fuente_vd,
            alta_db,
            geom
        FROM {SOURCE_LAYER}
        WHERE geom IS NOT NULL
    """


def bulk_load_to_staging(pg_conn: str, target: ZipTarget, feature_limit: int) -> None:
    options = gdal.VectorTranslateOptions(
        format="PostgreSQL",
        accessMode="append",
        SQLStatement=build_staging_sql(target),
        SQLDialect="SQLite",
        layerName=STAGING_TABLE,
        dstSRS="EPSG:4326",
        reproject=True,
        layerCreationOptions=["GEOMETRY_NAME=geom"],
        forceNullable=True,
        emptyStrAsNull=True,
        limit=feature_limit if feature_limit > 0 else None,
    )
    result = gdal.VectorTranslate(pg_conn, vsi_gpkg_path(target.path), options=options)
    if result is None:
        raise RuntimeError(f"Fallo la carga GDAL a staging para {target.path.name}")
    result = None


def truncate_initial_tables(pg_ds: ogr.DataSource) -> None:
    if should_clean_source():
        exec_sql(pg_ds, f"TRUNCATE TABLE {SOURCE_TABLE} RESTART IDENTITY")
    if should_clean_staging():
        exec_sql(pg_ds, f"TRUNCATE TABLE {STAGING_TABLE}")


def truncate_staging(pg_ds: ogr.DataSource) -> None:
    if should_clean_staging():
        exec_sql(pg_ds, f"TRUNCATE TABLE {STAGING_TABLE}")


def stage_count(pg_ds: ogr.DataSource) -> int:
    return int(fetch_one_value(pg_ds, f"SELECT count(*) AS n FROM {STAGING_TABLE}", "n") or 0)


def consolidate_source(pg_ds: ogr.DataSource, target: ZipTarget, ingest_id: int) -> int:
    exec_sql(pg_ds, f"DELETE FROM {SOURCE_TABLE} WHERE source_zip_name = '{sql_literal(target.path.name)}'")
    sql = f"""
        INSERT INTO {SOURCE_TABLE} (
            source_objectid,
            ingest_id,
            source_zip_name,
            source_gpkg_name,
            source_layer,
            territory_code,
            territory_name,
            id_tramo,
            id_vial,
            tipo_tramo,
            tipo_tramd,
            calzada,
            calzadad,
            acceso,
            accesod,
            firme,
            firmed,
            ncarriles,
            sentido,
            sentidod,
            situacion,
            situaciond,
            estadofis,
            estadofisd,
            tipovehic,
            tipovehicd,
            titular,
            titulard,
            orden,
            ordend,
            fuente_t,
            fuente_td,
            codigo,
            dgc_via,
            clase,
            clased,
            tipo_vial,
            tipo_viald,
            nombre,
            nombre_alt,
            fuente_v,
            fuente_vd,
            alta_db,
            geom
        )
        SELECT
            source_objectid,
            {ingest_id},
            source_zip_name,
            source_gpkg_name,
            source_layer,
            territory_code,
            territory_name,
            id_tramo,
            id_vial,
            tipo_tramo,
            tipo_tramd,
            calzada,
            calzadad,
            acceso,
            accesod,
            firme,
            firmed,
            ncarriles,
            sentido,
            sentidod,
            situacion,
            situaciond,
            estadofis,
            estadofisd,
            tipovehic,
            tipovehicd,
            titular,
            titulard,
            orden,
            ordend,
            fuente_t,
            fuente_td,
            codigo,
            dgc_via,
            clase,
            clased,
            tipo_vial,
            tipo_viald,
            nombre,
            nombre_alt,
            fuente_v,
            fuente_vd,
            alta_db,
            geom
        FROM {STAGING_TABLE}
        WHERE geom IS NOT NULL
          AND source_objectid IS NOT NULL
    """
    exec_sql(pg_ds, sql)
    return int(fetch_one_value(pg_ds, f"SELECT count(*) AS n FROM {SOURCE_TABLE} WHERE ingest_id = {ingest_id}", "n") or 0)


def analyze_tables(pg_ds: ogr.DataSource) -> None:
    exec_sql(pg_ds, f"ANALYZE {STAGING_TABLE}")
    exec_sql(pg_ds, f"ANALYZE {SOURCE_TABLE}")


def drop_secondary_indexes(pg_ds: ogr.DataSource) -> None:
    for index_name, _ in STAGING_SECONDARY_INDEXES:
        exec_sql(pg_ds, f"DROP INDEX IF EXISTS staging.{index_name}")
    for index_name, _ in SOURCE_SECONDARY_INDEXES:
        exec_sql(pg_ds, f"DROP INDEX IF EXISTS source.{index_name}")


def recreate_secondary_indexes(pg_ds: ogr.DataSource) -> None:
    for _, create_sql in (*STAGING_SECONDARY_INDEXES, *SOURCE_SECONDARY_INDEXES):
        exec_sql(pg_ds, create_sql)


def report_counts(pg_ds: ogr.DataSource) -> None:
    total = fetch_one_value(pg_ds, f"SELECT count(*) AS n FROM {SOURCE_TABLE}", "n")
    territories = fetch_one_value(pg_ds, f"SELECT count(DISTINCT territory_code) AS n FROM {SOURCE_TABLE}", "n")
    print(f"{SOURCE_TABLE}: {total} features persistidas en {territories} territorios")


def import_zip(pg_ds: ogr.DataSource, pg_conn: str, target: ZipTarget, feature_limit: int) -> None:
    validate_zip_member(target.path)
    ds = open_source_dataset(vsi_gpkg_path(target.path))
    validate_layer(ds)
    ds = None

    ingest_id = create_ingest_record(pg_ds, target, feature_limit)
    try:
        truncate_staging(pg_ds)
        bulk_load_to_staging(pg_conn, target, feature_limit)
        staged_features = stage_count(pg_ds)
        source_features = consolidate_source(pg_ds, target, ingest_id)
        update_ingest_record(
            pg_ds,
            ingest_id,
            "ok",
            metadata={
                "staged_features": staged_features,
                "imported_features": source_features,
                "staging_table": STAGING_TABLE,
                "source_table": SOURCE_TABLE,
                "source_gpkg_name": GPKG_MEMBER,
                "source_layer": SOURCE_LAYER,
                "territory_code": target.territory_code,
                "territory_name": target.territory_name,
                "raw_zip": str(target.path),
                "load_mode": "bulk_gdal_to_staging_sql_to_source",
                "max_features_per_zip": feature_limit,
            },
        )
        print(f"{target.path.name}: staging={staged_features}, source={source_features}")
    except Exception as exc:
        update_ingest_record(
            pg_ds,
            ingest_id,
            "failed",
            metadata={
                "staging_table": STAGING_TABLE,
                "source_table": SOURCE_TABLE,
                "source_gpkg_name": GPKG_MEMBER,
                "source_layer": SOURCE_LAYER,
                "territory_code": target.territory_code,
                "territory_name": target.territory_name,
                "raw_zip": str(target.path),
                "load_mode": "bulk_gdal_to_staging_sql_to_source",
                "max_features_per_zip": feature_limit,
            },
            error={"message": str(exc)},
        )
        raise


def main() -> int:
    gdal.UseExceptions()
    ogr.UseExceptions()
    osr.UseExceptions()
    gdal.SetConfigOption("PG_USE_COPY", "YES")

    root_dir = repo_root()
    targets = iter_zip_targets(root_dir)
    feature_limit = max_features_per_zip()
    pg_conn = pg_conn_string()

    print(f"ZIP IGR-RT a importar: {len(targets)}")
    print(f"GeoPackage interno: {GPKG_MEMBER}")
    print(f"Capa GPKG: {SOURCE_LAYER}")
    if feature_limit > 0:
        print(f"MAX_FEATURES_PER_ZIP={feature_limit}")
    drop_indexes = should_drop_indexes_for_bulk() and should_clean_source()
    if drop_indexes:
        print("DROP_INDEXES_FOR_BULK=1: indices secundarios se reconstruiran al final")

    pg_ds = open_pg_dataset(pg_conn)
    if drop_indexes:
        drop_secondary_indexes(pg_ds)
    truncate_initial_tables(pg_ds)

    errors: list[tuple[str, str]] = []
    try:
        for index, target in enumerate(targets, start=1):
            print(f"[{index}/{len(targets)}] Importando {target.path.name} ({target.territory_name})")
            try:
                import_zip(pg_ds, pg_conn, target, feature_limit)
            except Exception as exc:
                if not should_continue_on_error():
                    raise
                message = str(exc)
                errors.append((target.path.name, message))
                print(f"ERROR en {target.path.name}: {message}", file=sys.stderr)
    finally:
        if drop_indexes:
            print("Reconstruyendo indices secundarios IGR-RT")
            recreate_secondary_indexes(pg_ds)

    analyze_tables(pg_ds)
    report_counts(pg_ds)

    if errors:
        print("Importacion completada con errores:", file=sys.stderr)
        for zip_name, message in errors:
            print(f"- {zip_name}: {message}", file=sys.stderr)
        return 1

    print("Importacion IGR-RT staging -> source completada.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
