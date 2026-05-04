-- Fase 16: publicación diaria optimizada de avisos AEMET por temperaturas máximas.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS pub;

CREATE MATERIALIZED VIEW IF NOT EXISTS pub.aemet_max_temperature_daily_feature AS
WITH expanded AS (
    SELECT
        gs.valid_date::date AS valid_date,
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
    FROM core.aemet_max_temperature_warning AS w
    CROSS JOIN LATERAL generate_series(
        (w.onset_at AT TIME ZONE 'Europe/Madrid')::date,
        greatest(
            (w.onset_at AT TIME ZONE 'Europe/Madrid')::date,
            ((w.expires_at - interval '1 second') AT TIME ZONE 'Europe/Madrid')::date
        ),
        interval '1 day'
    ) AS gs(valid_date)
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
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS aemet_max_temperature_daily_feature_id_uidx
    ON pub.aemet_max_temperature_daily_feature (feature_id);
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

CREATE TABLE IF NOT EXISTS pub.aemet_max_temperature_daily_stat (
    stat_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id text NOT NULL DEFAULT 'aemet_max_temperature_warning_historical',
    nominal_date date NOT NULL,
    stat_scope text NOT NULL
        CHECK (stat_scope IN ('country')),
    area_code text NOT NULL,
    area_label text NOT NULL,
    coverage_expected_unit_count integer NOT NULL DEFAULT 1
        CHECK (coverage_expected_unit_count >= 0),
    coverage_unit_count integer NOT NULL DEFAULT 0
        CHECK (coverage_unit_count >= 0),
    coverage_complete boolean NOT NULL DEFAULT false,
    feature_count integer NOT NULL DEFAULT 0
        CHECK (feature_count >= 0),
    warning_count integer NOT NULL DEFAULT 0
        CHECK (warning_count >= 0),
    green_count integer NOT NULL DEFAULT 0
        CHECK (green_count >= 0),
    yellow_count integer NOT NULL DEFAULT 0
        CHECK (yellow_count >= 0),
    orange_count integer NOT NULL DEFAULT 0
        CHECK (orange_count >= 0),
    red_count integer NOT NULL DEFAULT 0
        CHECK (red_count >= 0),
    max_temperature_c double precision,
    warned_area_count integer NOT NULL DEFAULT 0
        CHECK (warned_area_count >= 0),
    source_feature_count integer NOT NULL DEFAULT 0
        CHECK (source_feature_count >= 0),
    stats_generated_at timestamptz NOT NULL DEFAULT now(),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (dataset_id, nominal_date, stat_scope, area_code)
);

CREATE INDEX IF NOT EXISTS aemet_max_temperature_daily_stat_date_idx
    ON pub.aemet_max_temperature_daily_stat (nominal_date);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_daily_stat_coverage_idx
    ON pub.aemet_max_temperature_daily_stat (coverage_complete);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_daily_stat_warning_idx
    ON pub.aemet_max_temperature_daily_stat (warning_count);

CREATE OR REPLACE VIEW pub.aemet_max_temperature_daily_catalog AS
SELECT
    stat_id,
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
    stats_generated_at
FROM pub.aemet_max_temperature_daily_stat;

COMMENT ON MATERIALIZED VIEW pub.aemet_max_temperature_daily_feature IS 'Capa diaria de avisos AEMET por temperaturas máximas, una geometría por zona/día/fenómeno preparada para GeoJSON y MVT.';
COMMENT ON TABLE pub.aemet_max_temperature_daily_stat IS 'Serie diaria publicada para timeline del visor: cobertura de descarga y conteos por nivel de aviso de temperaturas máximas.';
COMMENT ON COLUMN pub.aemet_max_temperature_daily_feature.source_version_count IS 'Número de versiones CAP candidatas consolidadas en la feature diaria de zona.';
COMMENT ON COLUMN pub.aemet_max_temperature_daily_stat.warning_count IS 'Número de zonas con aviso adverso de temperaturas máximas, excluyendo nivel verde.';
COMMENT ON COLUMN pub.aemet_max_temperature_daily_stat.source_feature_count IS 'Número de features diarias publicadas, incluyendo verde, antes del filtro operativo warnings_only.';
