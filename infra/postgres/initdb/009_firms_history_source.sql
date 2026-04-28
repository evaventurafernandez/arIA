-- Fase 11: estructuras source para el histórico vectorial de focos NASA FIRMS.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS ingest;
CREATE SCHEMA IF NOT EXISTS source;

CREATE TABLE IF NOT EXISTS source.firms_hotspot_download_file (
    source_download_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id text NOT NULL DEFAULT 'firms_hotspot_historical_download',
    source_system text NOT NULL DEFAULT 'nasa_firms'
        CHECK (source_system = 'nasa_firms'),
    dataset_type text NOT NULL DEFAULT 'SP'
        CHECK (dataset_type = 'SP'),
    firms_source text NOT NULL
        CHECK (firms_source IN ('VIIRS_NOAA20_SP', 'VIIRS_SNPP_SP')),
    bbox_region text NOT NULL
        CHECK (bbox_region IN ('peninsula_baleares', 'canarias', 'ceuta_melilla')),
    bbox geometry(Polygon, 4326) NOT NULL,
    request_date_from date NOT NULL,
    request_date_to date NOT NULL,
    request_day_range integer NOT NULL
        CHECK (request_day_range BETWEEN 1 AND 10),
    source_file_path text NOT NULL,
    source_file_sha256 text NOT NULL,
    row_count integer NOT NULL DEFAULT 0
        CHECK (row_count >= 0),
    downloaded_at timestamptz,
    ingest_id bigint NOT NULL REFERENCES ingest.ingest_file(ingest_id),
    imported_at timestamptz NOT NULL DEFAULT now(),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_file_path),
    UNIQUE (firms_source, bbox_region, request_date_from, request_date_to)
);

CREATE TABLE IF NOT EXISTS source.firms_hotspot_observation (
    source_observation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id text NOT NULL DEFAULT 'firms_hotspot_historical_observation',
    source_download_id bigint NOT NULL REFERENCES source.firms_hotspot_download_file(source_download_id) ON DELETE CASCADE,
    source_row_number integer NOT NULL
        CHECK (source_row_number > 0),
    source_row_hash text NOT NULL,
    dataset_type text NOT NULL DEFAULT 'SP'
        CHECK (dataset_type = 'SP'),
    firms_source text NOT NULL
        CHECK (firms_source IN ('VIIRS_NOAA20_SP', 'VIIRS_SNPP_SP')),
    bbox_region text NOT NULL
        CHECK (bbox_region IN ('peninsula_baleares', 'canarias', 'ceuta_melilla')),
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
    satellite text NOT NULL,
    instrument text,
    confidence text,
    version text,
    bright_ti5 double precision,
    frp double precision,
    daynight text
        CHECK (daynight IN ('D', 'N')),
    observed_at timestamptz NOT NULL,
    in_spain_nuts boolean NOT NULL DEFAULT false,
    geom geometry(Point, 4326) NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    raw_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_download_id, source_row_number)
);

ALTER TABLE source.firms_hotspot_observation
    ADD COLUMN IF NOT EXISTS in_spain_nuts boolean;
ALTER TABLE source.firms_hotspot_observation
    ALTER COLUMN in_spain_nuts SET DEFAULT false;
UPDATE source.firms_hotspot_observation
SET in_spain_nuts = false
WHERE in_spain_nuts IS NULL;
ALTER TABLE source.firms_hotspot_observation
    ALTER COLUMN in_spain_nuts SET NOT NULL;

CREATE INDEX IF NOT EXISTS firms_hotspot_download_file_request_from_idx
    ON source.firms_hotspot_download_file (request_date_from);
CREATE INDEX IF NOT EXISTS firms_hotspot_download_file_request_to_idx
    ON source.firms_hotspot_download_file (request_date_to);
CREATE INDEX IF NOT EXISTS firms_hotspot_download_file_firms_source_idx
    ON source.firms_hotspot_download_file (firms_source);
CREATE INDEX IF NOT EXISTS firms_hotspot_download_file_bbox_region_idx
    ON source.firms_hotspot_download_file (bbox_region);
CREATE INDEX IF NOT EXISTS firms_hotspot_download_file_ingest_id_idx
    ON source.firms_hotspot_download_file (ingest_id);
CREATE INDEX IF NOT EXISTS firms_hotspot_download_file_bbox_gix
    ON source.firms_hotspot_download_file USING GIST (bbox);

CREATE INDEX IF NOT EXISTS firms_hotspot_observation_acq_date_idx
    ON source.firms_hotspot_observation (acq_date);
CREATE INDEX IF NOT EXISTS firms_hotspot_observation_observed_at_idx
    ON source.firms_hotspot_observation (observed_at);
CREATE INDEX IF NOT EXISTS firms_hotspot_observation_firms_source_idx
    ON source.firms_hotspot_observation (firms_source);
CREATE INDEX IF NOT EXISTS firms_hotspot_observation_bbox_region_idx
    ON source.firms_hotspot_observation (bbox_region);
CREATE INDEX IF NOT EXISTS firms_hotspot_observation_in_spain_nuts_idx
    ON source.firms_hotspot_observation (in_spain_nuts);
CREATE INDEX IF NOT EXISTS firms_hotspot_observation_source_download_id_idx
    ON source.firms_hotspot_observation (source_download_id);
CREATE INDEX IF NOT EXISTS firms_hotspot_observation_geom_gix
    ON source.firms_hotspot_observation USING GIST (geom);

COMMENT ON TABLE source.firms_hotspot_download_file IS 'Bloques CSV descargados desde NASA FIRMS para el histórico de focos en España, incluyendo ficheros vacíos y trazabilidad de cobertura temporal.';
COMMENT ON TABLE source.firms_hotspot_observation IS 'Observaciones históricas FIRMS cercanas al origen, una fila por registro CSV importado antes de la deduplicación canónica.';
COMMENT ON COLUMN source.firms_hotspot_download_file.dataset_type IS 'Tipo de dataset FIRMS; en este pipeline histórico queda fijado a SP.';
COMMENT ON COLUMN source.firms_hotspot_download_file.bbox_region IS 'Región operativa usada para particionar la descarga del histórico de España.';
COMMENT ON COLUMN source.firms_hotspot_download_file.request_date_from IS 'Primer día incluido en la petición del bloque CSV.';
COMMENT ON COLUMN source.firms_hotspot_download_file.request_date_to IS 'Último día incluido en la petición del bloque CSV.';
COMMENT ON COLUMN source.firms_hotspot_download_file.row_count IS 'Número de observaciones válidas detectadas en el CSV descargado.';
COMMENT ON COLUMN source.firms_hotspot_observation.source_row_hash IS 'Hash estable del payload bruto de la fila CSV para auditoría y comparaciones.';
COMMENT ON COLUMN source.firms_hotspot_observation.observed_at IS 'Fecha y hora UTC derivadas de acq_date y acq_time.';
COMMENT ON COLUMN source.firms_hotspot_observation.in_spain_nuts IS 'Indica si la observación cae dentro del recorte NUTS de España persistido localmente en el repositorio.';
COMMENT ON COLUMN source.firms_hotspot_observation.raw_json IS 'Fila bruta del CSV preservada en JSONB para trazabilidad y reproceso.';
