#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import psycopg
from dotenv import dotenv_values

from daily_window import resolve_date_range


DATASET_ID = "aemet_avisos_cap_archive"
SOURCE_SYSTEM = "aemet"
PRODUCT_ID = "avisos_cap_archive"
TARGET_EVENT_CODE = "AT"
TARGET_LANGUAGE_PREFIX = "es"
NS = "{urn:oasis:names:tc:emergency:cap:1.2}"
LEVEL_LABELS = {
    "verde": "Verde",
    "amarillo": "Amarillo",
    "naranja": "Naranja",
    "rojo": "Rojo",
}
TEMPERATURE_RE = re.compile(r"(-?\d+(?:[,.]\d+)?)\s*(?:º|°)?\s*C", re.IGNORECASE)


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
        description="Importa a PostGIS el histórico CAP de AEMET filtrado a temperaturas máximas."
    )
    parser.add_argument(
        "--input-root",
        default=str(root_dir / "data-store/files/raw/aemet/avisos_cap/archive"),
    )
    parser.add_argument("--date-from", default=None, help="Primer día válido. Si se omite junto a --date-to, se procesa ayer.")
    parser.add_argument("--date-to", default=None, help="Último día válido. Si se omite junto a --date-from, se procesa ayer.")
    parser.add_argument("--elaboration-lookback-days", type=int, default=3)
    parser.add_argument("--skip-hash-check", action="store_true")
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00").replace("-00:00", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def text(node: ET.Element | None, tag: str) -> str | None:
    element = node.find(f"{NS}{tag}") if node is not None else None
    return element.text.strip() if element is not None and element.text else None


def first_coded_value(node: ET.Element, parent_tag: str, value_name: str) -> str | None:
    for element in node.findall(f"{NS}{parent_tag}"):
        if text(element, "valueName") == value_name:
            return text(element, "value")
    return None


def split_aemet_value(value: str | None) -> tuple[str | None, str | None, str | None]:
    if not value:
        return None, None, None
    parts = [part.strip() for part in value.split(";")]
    code = parts[0] if len(parts) >= 1 and parts[0] else None
    label = parts[1] if len(parts) >= 2 and parts[1] else None
    payload = ";".join(parts[2:]).strip() if len(parts) >= 3 else None
    return code, label, payload


def normalize_level(value: str | None, event_text: str | None) -> tuple[str, str]:
    raw = (value or "").strip().lower()
    if raw not in LEVEL_LABELS and event_text:
        lower_event = event_text.lower()
        for candidate in LEVEL_LABELS:
            if candidate in lower_event:
                raw = candidate
                break
    label = LEVEL_LABELS.get(raw, "Verde")
    return raw or label.lower(), label


def extract_temperature_c(parameter_value: str | None, description: str | None) -> float | None:
    haystack = " ".join(value for value in (parameter_value, description) if value)
    match = TEMPERATURE_RE.search(haystack)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def parse_polygon_wkt(polygon_text: str | None) -> str | None:
    if not polygon_text:
        return None
    coords: list[tuple[float, float]] = []
    for pair in polygon_text.strip().split():
        try:
            lat_text, lon_text = pair.split(",", 1)
            lat = float(lat_text)
            lon = float(lon_text)
        except ValueError:
            continue
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            coords.append((lon, lat))
    if len(coords) < 3:
        return None
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    if len(coords) < 4:
        return None
    ring = ", ".join(f"{lon:.8f} {lat:.8f}" for lon, lat in coords)
    return f"POLYGON(({ring}))"


def geocode_value(area: ET.Element | None, value_name: str) -> str | None:
    if area is None:
        return None
    for geocode in area.findall(f"{NS}geocode"):
        if text(geocode, "valueName") == value_name:
            return text(geocode, "value")
    return None


def build_record_hash(payload: dict) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_gzip_payload(payload: bytes) -> bool:
    return payload[:2] == b"\x1f\x8b"


def iter_xml_payloads(payload: bytes, path_parts: tuple[str, ...]) -> Iterable[tuple[str, bytes]]:
    if is_gzip_payload(payload):
        yield from iter_xml_payloads(gzip.decompress(payload), path_parts)
        return

    try:
        with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    continue
                yield from iter_xml_payloads(stream.read(), (*path_parts, member.name))
            return
    except tarfile.TarError:
        pass

    if payload.lstrip().startswith(b"<?xml"):
        yield ("/".join(path_parts), payload)


def iter_archive_xml_payloads(archive_path: Path) -> Iterable[tuple[str, bytes]]:
    payload = archive_path.read_bytes()
    yield from iter_xml_payloads(payload, (archive_path.name,))


def parse_cap_xml_records(source_member_path: str, xml_payload: bytes) -> list[dict]:
    root = ET.fromstring(xml_payload)
    cap_identifier = text(root, "identifier")
    if not cap_identifier:
        return []

    alert_base = {
        "cap_identifier": cap_identifier,
        "cap_sender": text(root, "sender"),
        "sent_at": text(root, "sent"),
        "cap_status": text(root, "status"),
        "cap_msg_type": text(root, "msgType"),
        "cap_scope": text(root, "scope"),
    }

    parsed_records: list[dict] = []
    for info in root.findall(f"{NS}info"):
        language = text(info, "language") or ""
        if not language.lower().startswith(TARGET_LANGUAGE_PREFIX):
            continue

        event_code_value = first_coded_value(info, "eventCode", "AEMET-Meteoalerta fenomeno")
        phenomenon_code, phenomenon_label, _ = split_aemet_value(event_code_value)
        if phenomenon_code != TARGET_EVENT_CODE:
            continue

        event_text = text(info, "event") or phenomenon_label or "Temperaturas máximas"
        level_value = first_coded_value(info, "parameter", "AEMET-Meteoalerta nivel")
        level_code, level_label = normalize_level(level_value, event_text)
        parameter_value = first_coded_value(info, "parameter", "AEMET-Meteoalerta parametro")
        parameter_code, parameter_label, parameter_payload = split_aemet_value(parameter_value)
        probability = first_coded_value(info, "parameter", "AEMET-Meteoalerta probabilidad")
        description = text(info, "description")
        temperature_max_c = extract_temperature_c(parameter_payload or parameter_value, description)
        onset = text(info, "onset")
        expires = text(info, "expires")
        if not onset or not expires:
            continue

        areas = info.findall(f"{NS}area") or [None]
        for area in areas:
            area_name = text(area, "areaDesc") if area is not None else None
            if not area_name:
                continue
            area_code = geocode_value(area, "AEMET-Meteoalerta zona")
            polygon_text = text(area, "polygon") if area is not None else None
            geom_wkt = parse_polygon_wkt(polygon_text)
            raw_json = {
                **alert_base,
                "language": language,
                "category": text(info, "category"),
                "event": event_text,
                "event_code": event_code_value,
                "response_type": text(info, "responseType"),
                "urgency": text(info, "urgency"),
                "severity": text(info, "severity"),
                "certainty": text(info, "certainty"),
                "effective_at": text(info, "effective"),
                "onset_at": onset,
                "expires_at": expires,
                "sender_name": text(info, "senderName"),
                "headline": text(info, "headline"),
                "description": description,
                "instruction": text(info, "instruction"),
                "web": text(info, "web"),
                "contact": text(info, "contact"),
                "level_code": level_code,
                "level_label": level_label,
                "parameter_code": parameter_code,
                "parameter_label": parameter_label,
                "parameter_value": parameter_payload,
                "probability": probability,
                "area_name": area_name,
                "area_code": area_code,
                "polygon_text": polygon_text,
                "source_member_path": source_member_path,
            }
            parsed_records.append(
                {
                    **raw_json,
                    "source_record_hash": build_record_hash(raw_json),
                    "phenomenon_code": phenomenon_code,
                    "phenomenon_label": phenomenon_label or "Temperaturas máximas",
                    "temperature_max_c": temperature_max_c,
                    "geom_wkt": geom_wkt,
                    "raw_json": raw_json,
                }
            )
    return parsed_records


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_manifest_paths(input_root: Path) -> list[Path]:
    return sorted(input_root.glob("*/*/*.json"))


def manifest_in_scope(manifest: dict, date_from: date, date_to: date, lookback_days: int) -> bool:
    request_from = parse_iso_datetime(manifest.get("request_elaboration_from"))
    request_to = parse_iso_datetime(manifest.get("request_elaboration_to"))
    if request_from is None or request_to is None:
        return False
    scope_from = datetime.combine(date_from - timedelta(days=lookback_days), datetime.min.time(), tzinfo=UTC)
    scope_to = datetime.combine(date_to, datetime.max.time(), tzinfo=UTC)
    return request_to >= scope_from and request_from <= scope_to


def relative_path(path: Path, root_dir: Path) -> str:
    return path.resolve().relative_to(root_dir.resolve()).as_posix()


def verify_file_hash(path: Path, expected_sha256: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"Hash inesperado para {path}: {actual} != {expected_sha256}")


@lru_cache(maxsize=1)
def relation_exists(conninfo: str, relation_name: str) -> bool:
    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (relation_name,))
            row = cur.fetchone()
    return bool(row and row[0])


def create_ingest_record(conn: psycopg.Connection, file_path: str, manifest: dict) -> int:
    metadata = {
        "product_id": manifest["product_id"],
        "request_elaboration_from": manifest["request_elaboration_from"],
        "request_elaboration_to": manifest["request_elaboration_to"],
        "response_size_bytes": manifest["response_size_bytes"],
        "outer_member_count": manifest.get("outer_member_count", 0),
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
            %s::timestamptz,
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
                PRODUCT_ID,
                "aemet_cap_archive_tar",
                file_path,
                manifest["source_file_sha256"],
                manifest.get("downloaded_at"),
                json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            ),
        )
        return int(cur.fetchone()[0])


def mark_ingest_status(conn: psycopg.Connection, ingest_id: int, status: str, error: str | None = None) -> None:
    payload = {"message": error} if error else {}
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest.ingest_file
            SET status = %s, error_json = %s::jsonb
            WHERE ingest_id = %s
            """,
            (status, json.dumps(payload, ensure_ascii=False, sort_keys=True), ingest_id),
        )


def upsert_download_row(
    conn: psycopg.Connection,
    ingest_id: int,
    manifest: dict,
    xml_member_count: int,
    filtered_record_count: int,
) -> int:
    metadata_json = {
        "aemet_response": manifest.get("aemet_response", {}),
        "imported_at": utc_now_iso(),
    }
    sql = """
        INSERT INTO source.aemet_warning_download_file (
            request_elaboration_from,
            request_elaboration_to,
            source_file_path,
            source_file_sha256,
            response_size_bytes,
            outer_member_count,
            xml_member_count,
            filtered_record_count,
            downloaded_at,
            ingest_id,
            metadata_json
        )
        VALUES (
            %s::timestamptz,
            %s::timestamptz,
            %s,
            %s,
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
            request_elaboration_from = EXCLUDED.request_elaboration_from,
            request_elaboration_to = EXCLUDED.request_elaboration_to,
            source_file_sha256 = EXCLUDED.source_file_sha256,
            response_size_bytes = EXCLUDED.response_size_bytes,
            outer_member_count = EXCLUDED.outer_member_count,
            xml_member_count = EXCLUDED.xml_member_count,
            filtered_record_count = EXCLUDED.filtered_record_count,
            downloaded_at = EXCLUDED.downloaded_at,
            ingest_id = EXCLUDED.ingest_id,
            imported_at = now(),
            metadata_json = EXCLUDED.metadata_json
        RETURNING source_download_id
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                manifest["request_elaboration_from"],
                manifest["request_elaboration_to"],
                manifest["source_file_path"],
                manifest["source_file_sha256"],
                manifest["response_size_bytes"],
                manifest.get("outer_member_count", 0),
                xml_member_count,
                filtered_record_count,
                manifest.get("downloaded_at"),
                ingest_id,
                json.dumps(metadata_json, ensure_ascii=False, sort_keys=True),
            ),
        )
        return int(cur.fetchone()[0])


def clear_existing_records(conn: psycopg.Connection, conninfo: str, source_download_id: int) -> None:
    if relation_exists(conninfo, "core.aemet_max_temperature_warning"):
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM core.aemet_max_temperature_warning
                WHERE representative_source_record_id IN (
                    SELECT source_record_id
                    FROM source.aemet_warning_cap_record
                    WHERE source_download_id = %s
                )
                """,
                (source_download_id,),
            )
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM source.aemet_warning_cap_record WHERE source_download_id = %s",
            (source_download_id,),
        )


def insert_record_rows(conn: psycopg.Connection, source_download_id: int, records: Iterable[dict]) -> int:
    rows = list(records)
    if not rows:
        return 0
    sql = """
        INSERT INTO source.aemet_warning_cap_record (
            source_download_id,
            source_member_path,
            source_record_hash,
            cap_identifier,
            cap_sender,
            sent_at,
            cap_status,
            cap_msg_type,
            cap_scope,
            language,
            category,
            event,
            event_code,
            phenomenon_code,
            phenomenon_label,
            response_type,
            urgency,
            severity,
            certainty,
            effective_at,
            onset_at,
            expires_at,
            sender_name,
            headline,
            description,
            instruction,
            web,
            contact,
            level_code,
            level_label,
            parameter_code,
            parameter_label,
            parameter_value,
            temperature_max_c,
            probability,
            area_name,
            area_code,
            polygon_text,
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
            %s::timestamptz,
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
            %s::timestamptz,
            %s::timestamptz,
            %s::timestamptz,
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
            ST_GeomFromText(%s, 4326),
            %s::jsonb,
            %s::jsonb
        )
    """
    prepared_rows = [
        (
            source_download_id,
            row["source_member_path"],
            row["source_record_hash"],
            row["cap_identifier"],
            row.get("cap_sender"),
            row.get("sent_at"),
            row.get("cap_status"),
            row.get("cap_msg_type"),
            row.get("cap_scope"),
            row["language"],
            row.get("category"),
            row["event"],
            row["event_code"],
            row["phenomenon_code"],
            row["phenomenon_label"],
            row.get("response_type"),
            row.get("urgency"),
            row.get("severity"),
            row.get("certainty"),
            row.get("effective_at"),
            row["onset_at"],
            row["expires_at"],
            row.get("sender_name"),
            row.get("headline"),
            row.get("description"),
            row.get("instruction"),
            row.get("web"),
            row.get("contact"),
            row["level_code"],
            row["level_label"],
            row.get("parameter_code"),
            row.get("parameter_label"),
            row.get("parameter_value"),
            row.get("temperature_max_c"),
            row.get("probability"),
            row["area_name"],
            row.get("area_code"),
            row.get("polygon_text"),
            row.get("geom_wkt"),
            json.dumps(row["raw_json"], ensure_ascii=False, sort_keys=True),
            json.dumps(
                {
                    "source_member_path": row["source_member_path"],
                    "parsed_at": utc_now_iso(),
                    "target_filter": "eventCode AT;Temperaturas máximas, language es-*",
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        for row in rows
    ]
    with conn.cursor() as cur:
        cur.executemany(sql, prepared_rows)
    return len(prepared_rows)


def parse_archive_records(archive_path: Path) -> tuple[int, list[dict]]:
    xml_member_count = 0
    filtered_records: list[dict] = []
    for source_member_path, xml_payload in iter_archive_xml_payloads(archive_path):
        xml_member_count += 1
        try:
            filtered_records.extend(parse_cap_xml_records(source_member_path, xml_payload))
        except ET.ParseError:
            continue
    return xml_member_count, filtered_records


def main() -> int:
    args = parse_args()
    input_root = Path(args.input_root)
    repo_dir = repo_root()
    if not input_root.is_dir():
        raise FileNotFoundError(f"No existe el directorio {input_root}")

    date_from, date_to, automatic_daily_window = resolve_date_range(args.date_from, args.date_to)
    manifest_paths = iter_manifest_paths(input_root)
    manifests: list[tuple[Path, dict]] = []
    for path in manifest_paths:
        manifest = load_manifest(path)
        if manifest_in_scope(manifest, date_from, date_to, args.elaboration_lookback_days):
            manifests.append((path, manifest))

    if not manifests:
        print("No se encontraron manifiestos AEMET para el rango indicado.", file=sys.stderr)
        return 1

    merged_env = load_env()
    conninfo = pg_conninfo(merged_env)
    imported_files = 0
    imported_xml_members = 0
    imported_records = 0
    failed = 0

    window_label = "ventana diaria automática" if automatic_daily_window else "rango explícito"
    print(
        f"Importando {len(manifests)} bloques AEMET CAP desde {input_root} "
        f"({date_from.isoformat()} a {date_to.isoformat()}, {window_label})"
    )
    with psycopg.connect(conninfo) as conn:
        for manifest_path, manifest in manifests:
            archive_path = repo_dir / manifest["source_file_path"]
            if not archive_path.is_file():
                print(f"- {manifest['source_file_path']}: ERROR no existe el tar", file=sys.stderr)
                failed += 1
                continue

            ingest_id = create_ingest_record(conn, manifest["source_file_path"], manifest)
            try:
                if not args.skip_hash_check:
                    verify_file_hash(archive_path, manifest["source_file_sha256"])
                xml_member_count, records = parse_archive_records(archive_path)
                source_download_id = upsert_download_row(conn, ingest_id, manifest, xml_member_count, len(records))
                clear_existing_records(conn, conninfo, source_download_id)
                inserted = insert_record_rows(conn, source_download_id, records)
                mark_ingest_status(conn, ingest_id, "ok")
                conn.commit()

                imported_files += 1
                imported_xml_members += xml_member_count
                imported_records += inserted
                rel_manifest_path = relative_path(manifest_path, repo_dir)
                print(
                    f"- {rel_manifest_path}: download_id={source_download_id}, "
                    f"xml={xml_member_count}, AT_records={inserted}"
                )
            except Exception as exc:
                conn.rollback()
                with psycopg.connect(conninfo) as error_conn:
                    mark_ingest_status(error_conn, ingest_id, "failed", str(exc))
                    error_conn.commit()
                failed += 1
                print(f"- {manifest['source_file_path']}: ERROR {exc}", file=sys.stderr)

    print(
        "Resumen importación AEMET: "
        f"files={imported_files}, xml_members={imported_xml_members}, records={imported_records}, failed={failed}"
    )
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
