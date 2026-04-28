#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import tarfile
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, time as dt_time, timedelta
from pathlib import Path

import httpx
from dotenv import dotenv_values


AEMET_API_BASE = "https://opendata.aemet.es/opendata/api"
AEMET_ARCHIVE_PATH = "/avisos_cap/archivo/fechaini/{date_from}/fechafin/{date_to}"
HTTP_TRUST_ENV_SEQUENCE = (False, True, False)
RETRYABLE_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class DownloadPlan:
    request_date_from: date
    request_date_to: date

    @property
    def request_datetime_from(self) -> datetime:
        return datetime.combine(self.request_date_from, dt_time.min, tzinfo=UTC)

    @property
    def request_datetime_to(self) -> datetime:
        return datetime.combine(self.request_date_to, dt_time(23, 59, 59), tzinfo=UTC)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_env() -> dict[str, str]:
    env = {key: value for key, value in dotenv_values(".env").items() if value is not None}
    env.update({key: value for key, value in os.environ.items() if value})
    return env


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def format_aemet_utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SUTC")


def parse_aemet_json(response: httpx.Response) -> dict:
    text = response.content.decode(response.encoding or "iso-8859-15", errors="replace")
    return json.loads(text)


def normalized_rel_path(path: Path, root_dir: Path) -> str:
    return path.resolve().relative_to(root_dir.resolve()).as_posix()


def iter_date_blocks(date_from: date, date_to: date, block_days: int) -> list[tuple[date, date]]:
    if date_to < date_from:
        raise ValueError("date_to debe ser mayor o igual que date_from")
    blocks: list[tuple[date, date]] = []
    current = date_from
    while current <= date_to:
        block_end = min(current + timedelta(days=block_days - 1), date_to)
        blocks.append((current, block_end))
        current = block_end + timedelta(days=1)
    return blocks


def build_download_plans(valid_date_from: date, valid_date_to: date, block_days: int, lookback_days: int) -> list[DownloadPlan]:
    request_date_from = valid_date_from - timedelta(days=lookback_days)
    request_date_to = valid_date_to
    return [DownloadPlan(start, end) for start, end in iter_date_blocks(request_date_from, request_date_to, block_days)]


def build_plan_output_paths(plan: DownloadPlan, output_root: Path) -> tuple[Path, Path]:
    year = f"{plan.request_date_from.year:04d}"
    month = f"{plan.request_date_from.month:02d}"
    stem = f"{plan.request_date_from.isoformat()}_{plan.request_date_to.isoformat()}"
    base_dir = output_root / year / month
    return base_dir / f"{stem}.tar", base_dir / f"{stem}.json"


def parse_args() -> argparse.Namespace:
    root_dir = repo_root()
    parser = argparse.ArgumentParser(
        description=(
            "Descarga el archivo histórico CAP de AEMET por rangos de elaboración. "
            "La descarga se guarda bruta para poder reimportar y auditar."
        )
    )
    parser.add_argument("--date-from", default="2025-05-01", help="Primer día válido que se publicará.")
    parser.add_argument("--date-to", default="2025-08-31", help="Último día válido que se publicará.")
    parser.add_argument(
        "--elaboration-lookback-days",
        type=int,
        default=3,
        help="Margen hacia atrás para capturar avisos válidos emitidos antes del primer día.",
    )
    parser.add_argument("--block-days", type=int, default=2, help="Días de elaboración por petición AEMET.")
    parser.add_argument(
        "--output-root",
        default=str(root_dir / "data-store/files/raw/aemet/avisos_cap/archive"),
    )
    parser.add_argument("--sleep-seconds", type=float, default=0.3)
    parser.add_argument("--max-retries", type=int, default=6)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def retry_delay_seconds(response: httpx.Response | None, attempt_number: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(1.0, min(float(retry_after), 120.0))
            except ValueError:
                pass
    return min(2.0 * (2 ** (attempt_number - 1)), 90.0)


def request_archive_metadata(api_key: str, plan: DownloadPlan, max_retries: int) -> dict:
    date_from = format_aemet_utc(plan.request_datetime_from)
    date_to = format_aemet_utc(plan.request_datetime_to)
    endpoint = AEMET_ARCHIVE_PATH.format(date_from=date_from, date_to=date_to)
    url = f"{AEMET_API_BASE}{endpoint}"
    last_transport_error: Exception | None = None

    for attempt_number in range(1, max_retries + 1):
        trust_env = HTTP_TRUST_ENV_SEQUENCE[(attempt_number - 1) % len(HTTP_TRUST_ENV_SEQUENCE)]
        try:
            with httpx.Client(timeout=60, follow_redirects=True, trust_env=trust_env) as client:
                response = client.get(url, headers={"api_key": api_key})
                if response.status_code in RETRYABLE_HTTP_STATUS_CODES and attempt_number < max_retries:
                    time.sleep(retry_delay_seconds(response, attempt_number))
                    continue
                response.raise_for_status()
                metadata = parse_aemet_json(response)
                metadata["_request_url"] = url
                return metadata
        except httpx.HTTPStatusError:
            raise
        except httpx.TransportError as exc:
            last_transport_error = exc
            if attempt_number >= max_retries:
                break
            time.sleep(retry_delay_seconds(None, attempt_number))

    if last_transport_error is not None:
        raise last_transport_error
    raise RuntimeError("No se pudo solicitar el metadato de descarga AEMET")


def fetch_archive_bytes(data_url: str, max_retries: int) -> bytes:
    last_transport_error: Exception | None = None
    for attempt_number in range(1, max_retries + 1):
        trust_env = HTTP_TRUST_ENV_SEQUENCE[(attempt_number - 1) % len(HTTP_TRUST_ENV_SEQUENCE)]
        try:
            with httpx.Client(timeout=180, follow_redirects=True, trust_env=trust_env) as client:
                response = client.get(data_url)
                if response.status_code in RETRYABLE_HTTP_STATUS_CODES and attempt_number < max_retries:
                    time.sleep(retry_delay_seconds(response, attempt_number))
                    continue
                response.raise_for_status()
                return response.content
        except httpx.HTTPStatusError:
            raise
        except httpx.TransportError as exc:
            last_transport_error = exc
            if attempt_number >= max_retries:
                break
            time.sleep(retry_delay_seconds(None, attempt_number))

    if last_transport_error is not None:
        raise last_transport_error
    raise RuntimeError("No se pudo descargar el tar histórico AEMET")


def count_outer_members(payload: bytes) -> int:
    try:
        with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
            return sum(1 for member in archive.getmembers() if member.isfile())
    except tarfile.TarError:
        return 0


def download_plan(plan: DownloadPlan, output_root: Path, api_key: str, overwrite: bool, max_retries: int) -> tuple[str, int]:
    tar_path, manifest_path = build_plan_output_paths(plan, output_root)
    if tar_path.is_file() and manifest_path.is_file() and not overwrite:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return "skipped", int(manifest.get("response_size_bytes") or 0)

    tar_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = request_archive_metadata(api_key, plan, max_retries)
    if int(metadata.get("estado") or 0) != 200 or not metadata.get("datos"):
        raise RuntimeError(f"AEMET no devolvió datos para el bloque: {metadata}")

    payload = fetch_archive_bytes(str(metadata["datos"]), max_retries)
    sha256 = hashlib.sha256(payload).hexdigest()
    tar_path.write_bytes(payload)

    manifest = {
        "dataset_id": "aemet_avisos_cap_archive_download",
        "source_system": "aemet",
        "product_id": "avisos_cap_archive",
        "request_elaboration_from": plan.request_datetime_from.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "request_elaboration_to": plan.request_datetime_to.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "downloaded_at": utc_now_iso(),
        "source_file_path": normalized_rel_path(tar_path, repo_root()),
        "source_file_sha256": sha256,
        "response_size_bytes": len(payload),
        "outer_member_count": count_outer_members(payload),
        "aemet_response": {
            "descripcion": metadata.get("descripcion"),
            "estado": metadata.get("estado"),
            "datos": metadata.get("datos"),
            "metadatos": metadata.get("metadatos"),
            "request_url": metadata.get("_request_url"),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return "downloaded", len(payload)


def main() -> int:
    args = parse_args()
    if args.block_days < 1 or args.block_days > 7:
        raise ValueError("block_days debe estar entre 1 y 7")
    if args.elaboration_lookback_days < 0 or args.elaboration_lookback_days > 7:
        raise ValueError("elaboration-lookback-days debe estar entre 0 y 7")

    env = load_env()
    api_key = env.get("AEMET_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Falta AEMET_API_KEY en .env o en el entorno.")

    valid_date_from = parse_date(args.date_from)
    valid_date_to = parse_date(args.date_to)
    output_root = Path(args.output_root)
    plans = build_download_plans(
        valid_date_from=valid_date_from,
        valid_date_to=valid_date_to,
        block_days=args.block_days,
        lookback_days=args.elaboration_lookback_days,
    )

    downloaded = 0
    skipped = 0
    failures = 0
    total_bytes = 0

    print(
        f"Descargando {len(plans)} bloques AEMET CAP "
        f"(válido {valid_date_from.isoformat()} a {valid_date_to.isoformat()}, "
        f"lookback={args.elaboration_lookback_days}, block_days={args.block_days})"
    )
    for index, plan in enumerate(plans, start=1):
        label = f"{plan.request_date_from.isoformat()}..{plan.request_date_to.isoformat()}"
        try:
            status, size_bytes = download_plan(plan, output_root, api_key, args.overwrite, args.max_retries)
            total_bytes += size_bytes
            if status == "downloaded":
                downloaded += 1
            else:
                skipped += 1
            print(f"[{index}/{len(plans)}] {label}: {status}, bytes={size_bytes}")
        except Exception as exc:
            failures += 1
            print(f"[{index}/{len(plans)}] {label}: ERROR {exc}", file=sys.stderr)
        if args.sleep_seconds > 0 and index < len(plans):
            time.sleep(args.sleep_seconds)

    print(
        "Resumen descarga AEMET: "
        f"downloaded={downloaded}, skipped={skipped}, failures={failures}, total_bytes={total_bytes}"
    )
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
