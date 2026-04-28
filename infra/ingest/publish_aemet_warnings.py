#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg
from dotenv import dotenv_values


DATASET_ID = "aemet_max_temperature_warning_historical"
COVERAGE_EXPECTED_UNIT_COUNT = 1


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
        description="Publica la serie diaria de avisos AEMET de temperaturas máximas para el visor."
    )
    parser.add_argument("--date-from", default="2025-05-01")
    parser.add_argument("--date-to", default="2025-08-31")
    return parser.parse_args()


def delete_country_stats(conn: psycopg.Connection, date_from: str, date_to: str) -> None:
    sql = """
        DELETE FROM pub.aemet_max_temperature_daily_stat
        WHERE dataset_id = %s
          AND nominal_date >= %s::date
          AND nominal_date <= %s::date
          AND stat_scope = 'country'
          AND area_code = 'ES'
    """
    with conn.cursor() as cur:
        cur.execute(sql, (DATASET_ID, date_from, date_to))


def upsert_country_stats(conn: psycopg.Connection, date_from: str, date_to: str) -> int:
    sql = """
        WITH calendar AS (
            SELECT generate_series(%s::date, %s::date, interval '1 day')::date AS nominal_date
        ),
        coverage AS (
            SELECT
                gs.coverage_date::date AS nominal_date,
                count(DISTINCT d.source_download_id)::integer AS source_file_count
            FROM source.aemet_warning_download_file AS d
            CROSS JOIN LATERAL generate_series(
                (d.request_elaboration_from AT TIME ZONE 'UTC')::date,
                (d.request_elaboration_to AT TIME ZONE 'UTC')::date,
                interval '1 day'
            ) AS gs(coverage_date)
            WHERE d.request_elaboration_to >= %s::date
              AND d.request_elaboration_from < (%s::date + interval '1 day')
            GROUP BY gs.coverage_date::date
        ),
        stats AS (
            SELECT
                valid_date AS nominal_date,
                count(*)::integer AS feature_count,
                count(*) FILTER (WHERE is_warning)::integer AS warning_count,
                count(*) FILTER (WHERE level_label = 'Verde')::integer AS green_count,
                count(*) FILTER (WHERE level_label = 'Amarillo')::integer AS yellow_count,
                count(*) FILTER (WHERE level_label = 'Naranja')::integer AS orange_count,
                count(*) FILTER (WHERE level_label = 'Rojo')::integer AS red_count,
                max(temperature_max_c) FILTER (WHERE is_warning)::double precision AS max_temperature_c,
                count(DISTINCT area_code) FILTER (WHERE is_warning)::integer AS warned_area_count,
                coalesce(sum(source_version_count), 0)::integer AS source_feature_count
            FROM pub.aemet_max_temperature_daily_feature
            WHERE valid_date >= %s::date
              AND valid_date <= %s::date
            GROUP BY valid_date
        )
        INSERT INTO pub.aemet_max_temperature_daily_stat (
            dataset_id,
            nominal_date,
            stat_scope,
            area_code,
            area_label,
            coverage_expected_unit_count,
            coverage_unit_count,
            coverage_complete,
            feature_count,
            warning_count,
            green_count,
            yellow_count,
            orange_count,
            red_count,
            max_temperature_c,
            warned_area_count,
            source_feature_count,
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
            CASE WHEN coalesce(cv.source_file_count, 0) > 0 THEN 1 ELSE 0 END,
            coalesce(cv.source_file_count, 0) > 0,
            coalesce(st.feature_count, 0),
            coalesce(st.warning_count, 0),
            coalesce(st.green_count, 0),
            coalesce(st.yellow_count, 0),
            coalesce(st.orange_count, 0),
            coalesce(st.red_count, 0),
            st.max_temperature_c,
            coalesce(st.warned_area_count, 0),
            coalesce(st.source_feature_count, 0),
            now(),
            jsonb_build_object(
                'coverage_source_file_count', coalesce(cv.source_file_count, 0),
                'coverage_expected_unit_count', %s,
                'published_warning_levels', ARRAY['Amarillo', 'Naranja', 'Rojo']::text[],
                'daily_feature_strategy', 'one_feature_per_day_area_max_level_latest_sent'
            )
        FROM calendar AS c
        LEFT JOIN coverage AS cv
            ON cv.nominal_date = c.nominal_date
        LEFT JOIN stats AS st
            ON st.nominal_date = c.nominal_date
        ON CONFLICT (dataset_id, nominal_date, stat_scope, area_code) DO UPDATE
        SET
            coverage_expected_unit_count = EXCLUDED.coverage_expected_unit_count,
            coverage_unit_count = EXCLUDED.coverage_unit_count,
            coverage_complete = EXCLUDED.coverage_complete,
            feature_count = EXCLUDED.feature_count,
            warning_count = EXCLUDED.warning_count,
            green_count = EXCLUDED.green_count,
            yellow_count = EXCLUDED.yellow_count,
            orange_count = EXCLUDED.orange_count,
            red_count = EXCLUDED.red_count,
            max_temperature_c = EXCLUDED.max_temperature_c,
            warned_area_count = EXCLUDED.warned_area_count,
            source_feature_count = EXCLUDED.source_feature_count,
            stats_generated_at = now(),
            metadata_json = EXCLUDED.metadata_json
    """
    params = (
        date_from,
        date_to,
        date_from,
        date_to,
        date_from,
        date_to,
        DATASET_ID,
        COVERAGE_EXPECTED_UNIT_COUNT,
        COVERAGE_EXPECTED_UNIT_COUNT,
    )
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def query_summary(conn: psycopg.Connection, date_from: str, date_to: str) -> dict:
    sql = """
        SELECT jsonb_build_object(
            'date_count', count(*),
            'coverage_complete_days', count(*) FILTER (WHERE coverage_complete),
            'warning_day_count', count(*) FILTER (WHERE warning_count > 0),
            'warning_total_area_days', coalesce(sum(warning_count), 0),
            'max_daily_warning_count', coalesce(max(warning_count), 0),
            'max_temperature_c', max(max_temperature_c)
        )
        FROM pub.aemet_max_temperature_daily_stat
        WHERE dataset_id = %s
          AND nominal_date >= %s::date
          AND nominal_date <= %s::date
          AND stat_scope = 'country'
          AND area_code = 'ES'
    """
    with conn.cursor() as cur:
        cur.execute(sql, (DATASET_ID, date_from, date_to))
        row = cur.fetchone()
    return row[0] if row and row[0] is not None else {}


def main() -> int:
    args = parse_args()
    merged_env = load_env()
    conninfo = pg_conninfo(merged_env)

    print(
        "Publicando avisos AEMET de temperaturas máximas "
        f"({args.date_from} a {args.date_to})"
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
