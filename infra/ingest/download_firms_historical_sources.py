#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
from dotenv import dotenv_values


FIRMS_API_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
FIRMS_HISTORICAL_SOURCES = ("VIIRS_NOAA20_SP", "VIIRS_SNPP_SP")
FIRMS_HISTORICAL_BBOXES = {
    "peninsula_baleares": "-10.0,35.0,5.0,44.5",
    "canarias": "-18.5,27.5,-13.0,29.5",
    "ceuta_melilla": "-6.0,35.0,-1.5,36.5",
}
HTTP_TRUST_ENV_SEQUENCE = (False, True, False)


@dataclass(frozen=True)
class DownloadPlan:
    firms_source: str
    bbox_region: str
    bbox_value: str
    request_date_from: date
    request_date_to: date

    @property
    def request_day_range(self) -> int:
        return (self.request_date_to - self.request_date_from).days + 1


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


def parse_csv_row_count(text: str) -> int:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "latitude" not in reader.fieldnames or "longitude" not in reader.fieldnames:
        return 0
    return sum(1 for _ in reader)


def normalized_rel_path(path: Path, root_dir: Path) -> str:
    return path.resolve().relative_to(root_dir.resolve()).as_posix()


def build_plan_output_paths(plan: DownloadPlan, output_root: Path) -> tuple[Path, Path]:
    year = f"{plan.request_date_from.year:04d}"
    month = f"{plan.request_date_from.month:02d}"
    stem = f"{plan.request_date_from.isoformat()}_{plan.request_date_to.isoformat()}"
    base_dir = output_root / "sp" / plan.firms_source / plan.bbox_region / year / month
    return base_dir / f"{stem}.csv", base_dir / f"{stem}.json"


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


def build_download_plans(
    date_from: date,
    date_to: date,
    block_days: int,
    sources: tuple[str, ...],
    bbox_regions: tuple[str, ...],
) -> list[DownloadPlan]:
    plans: list[DownloadPlan] = []
    for firms_source in sources:
        for bbox_region in bbox_regions:
            bbox_value = FIRMS_HISTORICAL_BBOXES[bbox_region]
            for request_date_from, request_date_to in iter_date_blocks(date_from, date_to, block_days):
                plans.append(
                    DownloadPlan(
                        firms_source=firms_source,
                        bbox_region=bbox_region,
                        bbox_value=bbox_value,
                        request_date_from=request_date_from,
                        request_date_to=request_date_to,
                    )
                )
    return plans


def parse_args() -> argparse.Namespace:
    root_dir = repo_root()
    parser = argparse.ArgumentParser(
        description="Descarga bloques CSV del histórico diario NASA FIRMS para España y guarda manifiestos locales."
    )
    parser.add_argument("--date-from", default="2025-05-01")
    parser.add_argument("--date-to", default="2025-08-31")
    parser.add_argument("--block-days", type=int, default=5)
    parser.add_argument(
        "--output-root",
        default=str(root_dir / "data-store/files/raw/nasa/firms/historical"),
    )
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
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def fetch_csv_text(map_key: str, plan: DownloadPlan) -> str:
    url = (
        f"{FIRMS_API_BASE}/{map_key}/{plan.firms_source}/{plan.bbox_value}/"
        f"{plan.request_day_range}/{plan.request_date_from.isoformat()}"
    )
    last_transport_error: Exception | None = None
    for attempt_number, trust_env in enumerate(HTTP_TRUST_ENV_SEQUENCE, start=1):
        try:
            with httpx.Client(timeout=60, follow_redirects=True, trust_env=trust_env) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError:
            raise
        except httpx.TransportError as exc:
            last_transport_error = exc
            if attempt_number >= len(HTTP_TRUST_ENV_SEQUENCE):
                break
            time.sleep(0.5 * attempt_number)
    if last_transport_error is not None:
        raise last_transport_error
    raise RuntimeError("No se pudo descargar el CSV de FIRMS")


def download_plan(plan: DownloadPlan, output_root: Path, map_key: str, overwrite: bool) -> tuple[str, int]:
    csv_path, manifest_path = build_plan_output_paths(plan, output_root)
    if csv_path.is_file() and manifest_path.is_file() and not overwrite:
        return "skipped", 0

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    text = fetch_csv_text(map_key, plan)
    payload_bytes = text.encode("utf-8")
    row_count = parse_csv_row_count(text)
    sha256 = hashlib.sha256(payload_bytes).hexdigest()
    csv_path.write_text(text, encoding="utf-8", newline="")

    manifest = {
        "dataset_type": "SP",
        "firms_source": plan.firms_source,
        "bbox_region": plan.bbox_region,
        "bbox_value": plan.bbox_value,
        "request_date_from": plan.request_date_from.isoformat(),
        "request_date_to": plan.request_date_to.isoformat(),
        "request_day_range": plan.request_day_range,
        "downloaded_at": utc_now_iso(),
        "row_count": row_count,
        "response_size_bytes": len(payload_bytes),
        "source_file_sha256": sha256,
        "source_file_path": normalized_rel_path(csv_path, repo_root()),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return "downloaded", row_count


def main() -> int:
    args = parse_args()
    env = load_env()
    map_key = env.get("FIRMS_MAP_KEY", "").strip()
    if not map_key:
        raise RuntimeError("Falta FIRMS_MAP_KEY en .env o en el entorno.")

    date_from = parse_date(args.date_from)
    date_to = parse_date(args.date_to)
    if args.block_days < 1 or args.block_days > 10:
        raise ValueError("block_days debe estar entre 1 y 10")

    output_root = Path(args.output_root)
    plans = build_download_plans(
        date_from=date_from,
        date_to=date_to,
        block_days=args.block_days,
        sources=tuple(args.sources),
        bbox_regions=tuple(args.bbox_regions),
    )

    downloaded = 0
    skipped = 0
    total_rows = 0
    failures = 0

    print(
        f"Descargando {len(plans)} bloques FIRMS históricos "
        f"({date_from.isoformat()} a {date_to.isoformat()}, block_days={args.block_days})"
    )
    for index, plan in enumerate(plans, start=1):
        label = (
            f"{plan.firms_source} {plan.bbox_region} "
            f"{plan.request_date_from.isoformat()}..{plan.request_date_to.isoformat()}"
        )
        try:
            status, row_count = download_plan(plan, output_root, map_key, args.overwrite)
            total_rows += row_count
            if status == "downloaded":
                downloaded += 1
            else:
                skipped += 1
            print(f"[{index}/{len(plans)}] {label}: {status}, rows={row_count}")
        except Exception as exc:
            failures += 1
            print(f"[{index}/{len(plans)}] {label}: ERROR {exc}", file=sys.stderr)
        if args.sleep_seconds > 0 and index < len(plans):
            time.sleep(args.sleep_seconds)

    print(
        "Resumen descarga FIRMS: "
        f"downloaded={downloaded}, skipped={skipped}, failures={failures}, total_rows={total_rows}"
    )
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
