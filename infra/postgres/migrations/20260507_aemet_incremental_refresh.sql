-- Estructuras de cola para refrescos incrementales AEMET y conversión de la
-- capa diaria publicada desde materialized view a tabla actualizable.

CREATE SCHEMA IF NOT EXISTS ingest;
CREATE SCHEMA IF NOT EXISTS pub;

CREATE TABLE IF NOT EXISTS ingest.aemet_warning_refresh_key (
    cap_identifier text NOT NULL,
    language text NOT NULL,
    area_code text NOT NULL,
    queued_at timestamptz NOT NULL DEFAULT now(),
    reason text NOT NULL DEFAULT 'import',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (cap_identifier, language, area_code)
);

CREATE INDEX IF NOT EXISTS aemet_warning_refresh_key_queued_at_idx
    ON ingest.aemet_warning_refresh_key (queued_at);

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
    IF EXISTS (
        SELECT 1
        FROM pg_class AS c
        JOIN pg_namespace AS n
            ON n.oid = c.relnamespace
        WHERE n.nspname = 'pub'
          AND c.relname = 'aemet_max_temperature_daily_feature'
          AND c.relkind = 'm'
    ) THEN
        CREATE TEMP TABLE aemet_max_temperature_daily_feature_backup
        ON COMMIT DROP AS
        SELECT *
        FROM pub.aemet_max_temperature_daily_feature;

        DROP MATERIALIZED VIEW pub.aemet_max_temperature_daily_feature;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS pub.aemet_max_temperature_daily_feature (
    feature_id text PRIMARY KEY,
    valid_date date NOT NULL,
    warning_id bigint NOT NULL REFERENCES core.aemet_max_temperature_warning(warning_id) ON DELETE CASCADE,
    cap_identifier text NOT NULL,
    sent_at timestamptz,
    onset_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    level_code text NOT NULL,
    level_label text NOT NULL,
    level_color text NOT NULL,
    level_rank integer NOT NULL,
    is_warning boolean NOT NULL,
    event_code text NOT NULL,
    phenomenon_code text NOT NULL,
    phenomenon_label text NOT NULL,
    parameter_value text,
    temperature_max_c double precision,
    probability text,
    area_name text NOT NULL,
    area_code text NOT NULL,
    headline text,
    description text,
    instruction text,
    source_version_count integer NOT NULL,
    geom geometry(Geometry, 4326) NOT NULL,
    geom_webmercator geometry(Geometry, 3857) NOT NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    canonicalized_at timestamptz NOT NULL
);

DO $$
BEGIN
    IF to_regclass('pg_temp.aemet_max_temperature_daily_feature_backup') IS NOT NULL THEN
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
        FROM pg_temp.aemet_max_temperature_daily_feature_backup
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
            canonicalized_at = EXCLUDED.canonicalized_at;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS aemet_max_temperature_daily_feature_valid_date_idx
    ON pub.aemet_max_temperature_daily_feature (valid_date);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_daily_feature_warning_idx
    ON pub.aemet_max_temperature_daily_feature (is_warning);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_daily_feature_level_idx
    ON pub.aemet_max_temperature_daily_feature (level_label);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_daily_feature_area_idx
    ON pub.aemet_max_temperature_daily_feature (area_code);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_daily_feature_geom_gix
    ON pub.aemet_max_temperature_daily_feature USING GIST (geom);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_daily_feature_geom_webmercator_gix
    ON pub.aemet_max_temperature_daily_feature USING GIST (geom_webmercator);

INSERT INTO ingest.aemet_warning_refresh_date (
    valid_date,
    reason,
    metadata_json
)
SELECT DISTINCT
    gs.valid_date::date,
    'migration-daily-feature-table',
    '{}'::jsonb
FROM core.aemet_max_temperature_warning AS w
CROSS JOIN LATERAL generate_series(
    (w.onset_at AT TIME ZONE 'Europe/Madrid')::date,
    greatest(
        (w.onset_at AT TIME ZONE 'Europe/Madrid')::date,
        ((w.expires_at - interval '1 second') AT TIME ZONE 'Europe/Madrid')::date
    ),
    interval '1 day'
) AS gs(valid_date)
ON CONFLICT (valid_date) DO UPDATE
SET
    queued_at = now(),
    reason = EXCLUDED.reason,
    metadata_json = ingest.aemet_warning_refresh_date.metadata_json || EXCLUDED.metadata_json;

COMMENT ON TABLE pub.aemet_max_temperature_daily_feature IS 'Capa diaria de avisos AEMET por temperaturas máximas, una geometría por zona/día/fenómeno preparada para GeoJSON y MVT.';
COMMENT ON TABLE ingest.aemet_warning_refresh_key IS 'Cola de claves CAP/zona pendientes de recanonizar de source a core.';
COMMENT ON TABLE ingest.aemet_warning_refresh_date IS 'Cola de fechas válidas pendientes de republicar en pub.aemet_max_temperature_daily_feature.';
