#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg
from dotenv import dotenv_values


DATASET_TYPE = "SP"
COVERAGE_EXPECTED_UNIT_COUNT = 6
PUBLISHED_CONFIDENCE_CODES = ("n", "h")


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
    parser = argparse.ArgumentParser(
        description="Publica la serie diaria del histórico FIRMS en Postgres a partir de source/core."
    )
    parser.add_argument("--date-from", default="2025-05-01")
    parser.add_argument("--date-to", default="2025-08-31")
    return parser.parse_args()


def delete_country_stats(conn: psycopg.Connection, date_from: str, date_to: str) -> None:
    sql = """
        DELETE FROM pub.firms_hotspot_daily_stat
        WHERE dataset_type = %s
          AND nominal_date >= %s::date
          AND nominal_date <= %s::date
          AND stat_scope = 'country'
          AND area_code = 'ES'
    """
    with conn.cursor() as cur:
        cur.execute(sql, (DATASET_TYPE, date_from, date_to))


def upsert_country_stats(conn: psycopg.Connection, date_from: str, date_to: str) -> int:
    sql = """
        WITH calendar AS (
            SELECT generate_series(%s::date, %s::date, interval '1 day')::date AS nominal_date
        ),
        coverage AS (
            SELECT
                gs.nominal_date,
                count(DISTINCT d.firms_source || '|' || d.bbox_region)::integer AS coverage_unit_count,
                ARRAY_AGG(DISTINCT d.firms_source ORDER BY d.firms_source) AS source_list,
                ARRAY_AGG(DISTINCT d.bbox_region ORDER BY d.bbox_region) AS bbox_region_list
            FROM source.firms_hotspot_download_file AS d
            CROSS JOIN LATERAL generate_series(d.request_date_from, d.request_date_to, interval '1 day') AS gs(nominal_date)
            WHERE d.dataset_type = %s
              AND d.request_date_to >= %s::date
              AND d.request_date_from <= %s::date
            GROUP BY gs.nominal_date
        ),
        stats AS (
            SELECT
                acq_date AS nominal_date,
                count(*)::integer AS hotspot_count,
                count(*) FILTER (WHERE confidence = 'h')::integer AS high_confidence_count,
                count(*) FILTER (WHERE confidence = 'n')::integer AS nominal_confidence_count,
                0::integer AS low_confidence_count,
                count(*) FILTER (WHERE daynight = 'D')::integer AS day_count,
                count(*) FILTER (WHERE daynight = 'N')::integer AS night_count,
                coalesce(sum(coalesce(frp, 0.0)), 0.0)::double precision AS frp_sum_mw,
                max(frp)::double precision AS frp_max_mw,
                count(DISTINCT firms_source)::integer AS source_count
            FROM core.firms_hotspot
            WHERE dataset_type = %s
              AND confidence = ANY(%s)
              AND acq_date >= %s::date
              AND acq_date <= %s::date
            GROUP BY acq_date
        )
        INSERT INTO pub.firms_hotspot_daily_stat (
            dataset_type,
            nominal_date,
            stat_scope,
            area_code,
            area_label,
            coverage_expected_unit_count,
            coverage_unit_count,
            coverage_complete,
            hotspot_count,
            high_confidence_count,
            nominal_confidence_count,
            low_confidence_count,
            day_count,
            night_count,
            frp_sum_mw,
            frp_max_mw,
            source_count,
            source_list,
            bbox_region_list,
            stats_generated_at,
            metadata_json
        )
        SELECT
            %s,
            c.nominal_date,
            'country',
            'ES',
            'España',
            %s,
            coalesce(cv.coverage_unit_count, 0),
            coalesce(cv.coverage_unit_count, 0) = %s,
            coalesce(st.hotspot_count, 0),
            coalesce(st.high_confidence_count, 0),
            coalesce(st.nominal_confidence_count, 0),
            coalesce(st.low_confidence_count, 0),
            coalesce(st.day_count, 0),
            coalesce(st.night_count, 0),
            coalesce(st.frp_sum_mw, 0.0),
            st.frp_max_mw,
            coalesce(st.source_count, 0),
            coalesce(cv.source_list, ARRAY[]::text[]),
            coalesce(cv.bbox_region_list, ARRAY[]::text[]),
            now(),
            jsonb_build_object(
                'coverage_expected_unit_count', %s,
                'coverage_unit_count', coalesce(cv.coverage_unit_count, 0),
                'coverage_complete', coalesce(cv.coverage_unit_count, 0) = %s,
                'published_confidence_codes', %s::text[],
                'source_list', coalesce(cv.source_list, ARRAY[]::text[]),
                'bbox_region_list', coalesce(cv.bbox_region_list, ARRAY[]::text[]),
                'source_count_with_hotspots', coalesce(st.source_count, 0)
            )
        FROM calendar AS c
        LEFT JOIN coverage AS cv
            ON cv.nominal_date = c.nominal_date
        LEFT JOIN stats AS st
            ON st.nominal_date = c.nominal_date
        ON CONFLICT (dataset_type, nominal_date, stat_scope, area_code) DO UPDATE
        SET
            coverage_expected_unit_count = EXCLUDED.coverage_expected_unit_count,
            coverage_unit_count = EXCLUDED.coverage_unit_count,
            coverage_complete = EXCLUDED.coverage_complete,
            hotspot_count = EXCLUDED.hotspot_count,
            high_confidence_count = EXCLUDED.high_confidence_count,
            nominal_confidence_count = EXCLUDED.nominal_confidence_count,
            low_confidence_count = EXCLUDED.low_confidence_count,
            day_count = EXCLUDED.day_count,
            night_count = EXCLUDED.night_count,
            frp_sum_mw = EXCLUDED.frp_sum_mw,
            frp_max_mw = EXCLUDED.frp_max_mw,
            source_count = EXCLUDED.source_count,
            source_list = EXCLUDED.source_list,
            bbox_region_list = EXCLUDED.bbox_region_list,
            stats_generated_at = now(),
            metadata_json = EXCLUDED.metadata_json
    """
    params = (
        date_from,
        date_to,
        DATASET_TYPE,
        date_from,
        date_to,
        DATASET_TYPE,
        list(PUBLISHED_CONFIDENCE_CODES),
        date_from,
        date_to,
        DATASET_TYPE,
        COVERAGE_EXPECTED_UNIT_COUNT,
        COVERAGE_EXPECTED_UNIT_COUNT,
        COVERAGE_EXPECTED_UNIT_COUNT,
        COVERAGE_EXPECTED_UNIT_COUNT,
        list(PUBLISHED_CONFIDENCE_CODES),
    )
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def query_summary(conn: psycopg.Connection, date_from: str, date_to: str) -> dict:
    sql = """
        SELECT jsonb_build_object(
            'date_count', count(*),
            'coverage_complete_days', count(*) FILTER (WHERE coverage_complete),
            'hotspot_total', coalesce(sum(hotspot_count), 0),
            'max_daily_hotspots', max(hotspot_count),
            'max_daily_frp_mw', max(frp_max_mw)
        )
        FROM pub.firms_hotspot_daily_stat
        WHERE dataset_type = %s
          AND nominal_date >= %s::date
          AND nominal_date <= %s::date
          AND stat_scope = 'country'
          AND area_code = 'ES'
    """
    with conn.cursor() as cur:
        cur.execute(sql, (DATASET_TYPE, date_from, date_to))
        row = cur.fetchone()
    return row[0] if row and row[0] is not None else {}


def main() -> int:
    args = parse_args()
    merged_env = load_env()
    conninfo = pg_conninfo(merged_env)

    print(
        f"Publicando histórico FIRMS diario en PostgreSQL "
        f"({args.date_from} a {args.date_to}, dataset_type={DATASET_TYPE})"
    )
    with psycopg.connect(conninfo) as conn:
        delete_country_stats(conn, args.date_from, args.date_to)
        upsert_country_stats(conn, args.date_from, args.date_to)
        summary = query_summary(conn, args.date_from, args.date_to)
        conn.commit()

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
