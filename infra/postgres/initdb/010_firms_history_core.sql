-- Fase 12: estructuras core para el histórico vectorial de focos NASA FIRMS.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE IF NOT EXISTS core.firms_hotspot (
    hotspot_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id text NOT NULL DEFAULT 'firms_hotspot_historical',
    dataset_type text NOT NULL DEFAULT 'SP'
        CHECK (dataset_type = 'SP'),
    firms_source text NOT NULL
        CHECK (firms_source IN ('VIIRS_NOAA20_SP', 'VIIRS_SNPP_SP')),
    satellite text NOT NULL,
    instrument text,
    confidence text,
    version text,
    daynight text
        CHECK (daynight IN ('D', 'N')),
    latitude double precision NOT NULL
        CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision NOT NULL
        CHECK (longitude BETWEEN -180 AND 180),
    bright_ti4 double precision,
    scan double precision,
    track double precision,
    acq_date date NOT NULL,
    acq_time text NOT NULL
        CHECK (acq_time ~ '^[0-9]{4}$'),
    observed_at timestamptz NOT NULL,
    bright_ti5 double precision,
    frp double precision,
    bbox_regions text[] NOT NULL DEFAULT ARRAY[]::text[],
    source_download_count integer NOT NULL DEFAULT 1
        CHECK (source_download_count > 0),
    source_observation_count integer NOT NULL DEFAULT 1
        CHECK (source_observation_count > 0),
    representative_source_observation_id bigint NOT NULL REFERENCES source.firms_hotspot_observation(source_observation_id),
    geom geometry(Point, 4326) NOT NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    canonicalized_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (firms_source, latitude, longitude, acq_date, acq_time, satellite)
);

CREATE INDEX IF NOT EXISTS firms_hotspot_acq_date_idx
    ON core.firms_hotspot (acq_date);
CREATE INDEX IF NOT EXISTS firms_hotspot_observed_at_idx
    ON core.firms_hotspot (observed_at);
CREATE INDEX IF NOT EXISTS firms_hotspot_firms_source_idx
    ON core.firms_hotspot (firms_source);
CREATE INDEX IF NOT EXISTS firms_hotspot_confidence_idx
    ON core.firms_hotspot (confidence);
CREATE INDEX IF NOT EXISTS firms_hotspot_daynight_idx
    ON core.firms_hotspot (daynight);
CREATE INDEX IF NOT EXISTS firms_hotspot_geom_gix
    ON core.firms_hotspot USING GIST (geom);

COMMENT ON TABLE core.firms_hotspot IS 'Nivel core canónico del histórico FIRMS: una fila por foco deduplicado con trazabilidad al source y geometría POINT en EPSG:4326.';
COMMENT ON COLUMN core.firms_hotspot.dataset_type IS 'Tipo de dataset FIRMS, útil para distinguir histórico SP de otros modos futuros.';
COMMENT ON COLUMN core.firms_hotspot.bbox_regions IS 'Conjunto de regiones de descarga source en las que apareció el foco antes de deduplicar.';
COMMENT ON COLUMN core.firms_hotspot.source_download_count IS 'Número de bloques source distintos que contenían el foco deduplicado.';
COMMENT ON COLUMN core.firms_hotspot.source_observation_count IS 'Número de filas source agregadas en este foco canónico.';
COMMENT ON COLUMN core.firms_hotspot.representative_source_observation_id IS 'Fila source representativa usada como referencia directa del foco canónico.';
