\set ON_ERROR_STOP on

BEGIN;

CREATE SCHEMA IF NOT EXISTS ingest;

CREATE TABLE IF NOT EXISTS ingest.aemet_warning_refresh_date (
    valid_date date PRIMARY KEY,
    queued_at timestamptz NOT NULL DEFAULT now(),
    reason text NOT NULL DEFAULT 'core-refresh',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS aemet_warning_refresh_date_queued_at_idx
    ON ingest.aemet_warning_refresh_date (queued_at);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ingest.aemet_warning_refresh_date)
       AND NOT EXISTS (SELECT 1 FROM pub.aemet_max_temperature_daily_feature) THEN
        INSERT INTO ingest.aemet_warning_refresh_date (
            valid_date,
            reason
        )
        SELECT DISTINCT
            gs.valid_date::date,
            'bootstrap-pub-empty'
        FROM core.aemet_max_temperature_warning AS w
        CROSS JOIN LATERAL generate_series(
            (w.onset_at AT TIME ZONE 'Europe/Madrid')::date,
            greatest(
                (w.onset_at AT TIME ZONE 'Europe/Madrid')::date,
                ((w.expires_at - interval '1 second') AT TIME ZONE 'Europe/Madrid')::date
            ),
            interval '1 day'
        ) AS gs(valid_date)
        ON CONFLICT (valid_date) DO NOTHING;
    END IF;
END $$;

SELECT (count(*) > 0) AS has_refresh_dates
FROM ingest.aemet_warning_refresh_date \gset

\if :has_refresh_dates

SELECT count(*) AS pending_refresh_dates
FROM ingest.aemet_warning_refresh_date;

CREATE TEMP TABLE _aemet_refresh_date
ON COMMIT DROP AS
SELECT valid_date
FROM ingest.aemet_warning_refresh_date;

WITH deleted AS (
    DELETE FROM pub.aemet_max_temperature_daily_feature AS f
    USING _aemet_refresh_date AS d
    WHERE d.valid_date = f.valid_date
    RETURNING 1
)
SELECT count(*) AS deleted_pub_rows
FROM deleted;

WITH expanded AS (
    SELECT
        d.valid_date,
        w.warning_id,
        w.cap_identifier,
        w.sent_at,
        w.onset_at,
        w.expires_at,
        w.level_code,
        w.level_label,
        w.level_rank,
        w.is_warning,
        w.event_code,
        w.phenomenon_code,
        w.phenomenon_label,
        w.parameter_value,
        w.temperature_max_c,
        w.probability,
        w.area_name,
        w.area_code,
        w.headline,
        w.description,
        w.instruction,
        w.geom,
        w.geom_webmercator,
        w.metadata_json,
        w.canonicalized_at
    FROM _aemet_refresh_date AS d
    JOIN core.aemet_max_temperature_warning AS w
      ON d.valid_date >= (w.onset_at AT TIME ZONE 'Europe/Madrid')::date
     AND d.valid_date <= greatest(
            (w.onset_at AT TIME ZONE 'Europe/Madrid')::date,
            ((w.expires_at - interval '1 second') AT TIME ZONE 'Europe/Madrid')::date
        )
),
ranked AS (
    SELECT
        *,
        row_number() OVER (
            PARTITION BY valid_date, area_code, phenomenon_code
            ORDER BY level_rank DESC, sent_at DESC NULLS LAST, onset_at DESC, warning_id DESC
        ) AS daily_rank,
        count(*) OVER (
            PARTITION BY valid_date, area_code, phenomenon_code
        ) AS source_version_count
    FROM expanded
),
inserted AS (
    INSERT INTO pub.aemet_max_temperature_daily_feature (
        feature_id,
        valid_date,
        warning_id,
        cap_identifier,
        sent_at,
        onset_at,
        expires_at,
        level_code,
        level_label,
        level_color,
        level_rank,
        is_warning,
        event_code,
        phenomenon_code,
        phenomenon_label,
        parameter_value,
        temperature_max_c,
        probability,
        area_name,
        area_code,
        headline,
        description,
        instruction,
        source_version_count,
        geom,
        geom_webmercator,
        metadata_json,
        canonicalized_at
    )
    SELECT
        valid_date::text || ':' || area_code || ':' || phenomenon_code AS feature_id,
        valid_date,
        warning_id,
        cap_identifier,
        sent_at,
        onset_at,
        expires_at,
        level_code,
        level_label,
        CASE level_label
            WHEN 'Rojo' THEN '#CC0000'
            WHEN 'Naranja' THEN '#FFA500'
            WHEN 'Amarillo' THEN '#FFD700'
            ELSE '#4CAF50'
        END AS level_color,
        level_rank,
        is_warning,
        event_code,
        phenomenon_code,
        phenomenon_label,
        parameter_value,
        temperature_max_c,
        probability,
        area_name,
        area_code,
        headline,
        description,
        instruction,
        source_version_count::integer,
        geom,
        geom_webmercator,
        metadata_json || jsonb_build_object(
            'daily_rank_strategy', 'max_level_then_latest_sent',
            'source_version_count', source_version_count
        ) AS metadata_json,
        canonicalized_at
    FROM ranked
    WHERE daily_rank = 1
    ON CONFLICT (feature_id) DO UPDATE
    SET
        valid_date = EXCLUDED.valid_date,
        warning_id = EXCLUDED.warning_id,
        cap_identifier = EXCLUDED.cap_identifier,
        sent_at = EXCLUDED.sent_at,
        onset_at = EXCLUDED.onset_at,
        expires_at = EXCLUDED.expires_at,
        level_code = EXCLUDED.level_code,
        level_label = EXCLUDED.level_label,
        level_color = EXCLUDED.level_color,
        level_rank = EXCLUDED.level_rank,
        is_warning = EXCLUDED.is_warning,
        event_code = EXCLUDED.event_code,
        phenomenon_code = EXCLUDED.phenomenon_code,
        phenomenon_label = EXCLUDED.phenomenon_label,
        parameter_value = EXCLUDED.parameter_value,
        temperature_max_c = EXCLUDED.temperature_max_c,
        probability = EXCLUDED.probability,
        area_name = EXCLUDED.area_name,
        area_code = EXCLUDED.area_code,
        headline = EXCLUDED.headline,
        description = EXCLUDED.description,
        instruction = EXCLUDED.instruction,
        source_version_count = EXCLUDED.source_version_count,
        geom = EXCLUDED.geom,
        geom_webmercator = EXCLUDED.geom_webmercator,
        metadata_json = EXCLUDED.metadata_json,
        canonicalized_at = EXCLUDED.canonicalized_at
    RETURNING 1
)
SELECT count(*) AS inserted_pub_rows
FROM inserted;

WITH consumed AS (
    DELETE FROM ingest.aemet_warning_refresh_date AS q
    USING _aemet_refresh_date AS d
    WHERE d.valid_date = q.valid_date
    RETURNING 1
)
SELECT count(*) AS consumed_refresh_dates
FROM consumed;

ANALYZE pub.aemet_max_temperature_daily_feature;

\else

SELECT 0 AS pending_refresh_dates;

\endif

COMMIT;
