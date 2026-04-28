-- Fase 13: publicación derivada para timeline y estadísticas diarias del histórico FIRMS.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS pub;

CREATE TABLE IF NOT EXISTS pub.firms_hotspot_daily_stat (
    stat_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_type text NOT NULL
        CHECK (dataset_type = 'SP'),
    nominal_date date NOT NULL,
    stat_scope text NOT NULL
        CHECK (stat_scope IN ('country')),
    area_code text NOT NULL,
    area_label text NOT NULL,
    coverage_expected_unit_count integer NOT NULL
        CHECK (coverage_expected_unit_count >= 0),
    coverage_unit_count integer NOT NULL
        CHECK (coverage_unit_count >= 0),
    coverage_complete boolean NOT NULL DEFAULT false,
    hotspot_count integer NOT NULL DEFAULT 0
        CHECK (hotspot_count >= 0),
    high_confidence_count integer NOT NULL DEFAULT 0
        CHECK (high_confidence_count >= 0),
    nominal_confidence_count integer NOT NULL DEFAULT 0
        CHECK (nominal_confidence_count >= 0),
    low_confidence_count integer NOT NULL DEFAULT 0
        CHECK (low_confidence_count >= 0),
    day_count integer NOT NULL DEFAULT 0
        CHECK (day_count >= 0),
    night_count integer NOT NULL DEFAULT 0
        CHECK (night_count >= 0),
    frp_sum_mw double precision,
    frp_max_mw double precision,
    source_count integer NOT NULL DEFAULT 0
        CHECK (source_count >= 0),
    source_list text[] NOT NULL DEFAULT ARRAY[]::text[],
    bbox_region_list text[] NOT NULL DEFAULT ARRAY[]::text[],
    stats_generated_at timestamptz NOT NULL DEFAULT now(),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (dataset_type, nominal_date, stat_scope, area_code)
);

CREATE INDEX IF NOT EXISTS firms_hotspot_daily_stat_nominal_date_idx
    ON pub.firms_hotspot_daily_stat (nominal_date);
CREATE INDEX IF NOT EXISTS firms_hotspot_daily_stat_dataset_type_idx
    ON pub.firms_hotspot_daily_stat (dataset_type);
CREATE INDEX IF NOT EXISTS firms_hotspot_daily_stat_coverage_complete_idx
    ON pub.firms_hotspot_daily_stat (coverage_complete);

CREATE OR REPLACE VIEW pub.firms_hotspot_daily_catalog AS
SELECT
    stat_id,
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
    stats_generated_at
FROM pub.firms_hotspot_daily_stat;

COMMENT ON VIEW pub.firms_hotspot_daily_catalog IS 'Publicación ligera del histórico FIRMS por día, orientada a timeline, control de cobertura y analítica diaria país.';
COMMENT ON TABLE pub.firms_hotspot_daily_stat IS 'Serie diaria publicada del histórico FIRMS para España, incluyendo días sin focos cuando la cobertura source del día es completa.';
COMMENT ON COLUMN pub.firms_hotspot_daily_stat.coverage_expected_unit_count IS 'Número esperado de combinaciones source-región para considerar un día totalmente cubierto.';
COMMENT ON COLUMN pub.firms_hotspot_daily_stat.coverage_unit_count IS 'Número real de combinaciones source-región cubiertas por los bloques descargados para ese día.';
COMMENT ON COLUMN pub.firms_hotspot_daily_stat.coverage_complete IS 'Indica si el día quedó cubierto por todas las fuentes y regiones esperadas.';
COMMENT ON COLUMN pub.firms_hotspot_daily_stat.source_list IS 'Fuentes FIRMS SP que aportaron cobertura o focos al día publicado.';
COMMENT ON COLUMN pub.firms_hotspot_daily_stat.bbox_region_list IS 'Regiones de descarga que participaron en la cobertura diaria publicada.';
