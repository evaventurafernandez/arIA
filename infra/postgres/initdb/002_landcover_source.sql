
-- Fase 3: estructuras mínimas para la importación filtrada de landcover.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS ingest;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS source;

CREATE TABLE IF NOT EXISTS ingest.ingest_file (
    ingest_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id text NOT NULL,
    source_system text NOT NULL,
    source_layer text,
    origin_format text NOT NULL,
    file_path text NOT NULL,
    content_hash text,
    captured_at timestamptz,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'ok', 'failed')),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS source.landcover_clc18_es (
    source_fid bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_objectid bigint NOT NULL,
    ingest_id bigint NOT NULL REFERENCES ingest.ingest_file(ingest_id),
    code_18 text NOT NULL CHECK (code_18 IN ('311', '312', '313', '321', '322', '323', '324', '211', '242')),
    imported_at timestamptz NOT NULL DEFAULT now(),
    geom geometry(Geometry, 4326) NOT NULL
);

CREATE TABLE IF NOT EXISTS source.landcover_clc18_es_canarias (
    source_fid bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_objectid bigint NOT NULL,
    ingest_id bigint NOT NULL REFERENCES ingest.ingest_file(ingest_id),
    code_18 text NOT NULL CHECK (code_18 IN ('311', '312', '313', '321', '322', '323', '324', '211', '242')),
    imported_at timestamptz NOT NULL DEFAULT now(),
    geom geometry(Geometry, 4326) NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.landcover_clc18_es_raw (
    source_objectid bigint NOT NULL,
    code_18 text NOT NULL CHECK (code_18 IN ('311', '312', '313', '321', '322', '323', '324', '211', '242')),
    geom geometry(Geometry, 4326) NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.landcover_clc18_es_canarias_raw (
    source_objectid bigint NOT NULL,
    code_18 text NOT NULL CHECK (code_18 IN ('311', '312', '313', '321', '322', '323', '324', '211', '242')),
    geom geometry(Geometry, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS landcover_clc18_es_geom_gix
    ON source.landcover_clc18_es USING GIST (geom);
CREATE INDEX IF NOT EXISTS landcover_clc18_es_code_18_idx
    ON source.landcover_clc18_es (code_18);
CREATE INDEX IF NOT EXISTS landcover_clc18_es_source_objectid_idx
    ON source.landcover_clc18_es (source_objectid);
CREATE INDEX IF NOT EXISTS landcover_clc18_es_canarias_geom_gix
    ON source.landcover_clc18_es_canarias USING GIST (geom);
CREATE INDEX IF NOT EXISTS landcover_clc18_es_canarias_code_18_idx
    ON source.landcover_clc18_es_canarias (code_18);
CREATE INDEX IF NOT EXISTS landcover_clc18_es_canarias_source_objectid_idx
    ON source.landcover_clc18_es_canarias (source_objectid);
CREATE INDEX IF NOT EXISTS landcover_clc18_es_raw_geom_gix
    ON staging.landcover_clc18_es_raw USING GIST (geom);
CREATE INDEX IF NOT EXISTS landcover_clc18_es_raw_code_18_idx
    ON staging.landcover_clc18_es_raw (code_18);
CREATE INDEX IF NOT EXISTS landcover_clc18_es_raw_source_objectid_idx
    ON staging.landcover_clc18_es_raw (source_objectid);
CREATE INDEX IF NOT EXISTS landcover_clc18_es_canarias_raw_geom_gix
    ON staging.landcover_clc18_es_canarias_raw USING GIST (geom);
CREATE INDEX IF NOT EXISTS landcover_clc18_es_canarias_raw_code_18_idx
    ON staging.landcover_clc18_es_canarias_raw (code_18);
CREATE INDEX IF NOT EXISTS landcover_clc18_es_canarias_raw_source_objectid_idx
    ON staging.landcover_clc18_es_canarias_raw (source_objectid);

CREATE OR REPLACE VIEW source.landcover_corine_polygon AS
SELECT
    'CLC18_ES'::text AS source_layer,
    source_fid,
    source_objectid,
    ingest_id,
    code_18,
    imported_at,
    geom
FROM source.landcover_clc18_es
UNION ALL
SELECT
    'CLC18_ES_Canarias'::text AS source_layer,
    source_fid,
    source_objectid,
    ingest_id,
    code_18,
    imported_at,
    geom
FROM source.landcover_clc18_es_canarias;

COMMENT ON TABLE ingest.ingest_file IS 'Control de ingesta y trazabilidad de archivos y cargas';
COMMENT ON TABLE staging.landcover_clc18_es_raw IS 'Staging masivo de CORINE 2018 peninsula y Baleares para carga bulk previa al contrato source';
COMMENT ON TABLE staging.landcover_clc18_es_canarias_raw IS 'Staging masivo de CORINE 2018 Canarias para carga bulk previa al contrato source';
COMMENT ON TABLE source.landcover_clc18_es IS 'Nivel source cercano al origen para CORINE 2018 peninsula y Baleares';
COMMENT ON TABLE source.landcover_clc18_es_canarias IS 'Nivel source cercano al origen para CORINE 2018 Canarias';
COMMENT ON VIEW source.landcover_corine_polygon IS 'Vista unificada del source filtrado de landcover; core asumira la canonizacion y reparacion geometrica';

COMMENT ON COLUMN staging.landcover_clc18_es_raw.source_objectid IS 'OBJECTID original del FileGDB en staging previo a source';
COMMENT ON COLUMN staging.landcover_clc18_es_raw.code_18 IS 'Codigo funcional filtrado antes de consolidar en source';
COMMENT ON COLUMN staging.landcover_clc18_es_raw.geom IS 'Geometria reproyectada a EPSG:4326 cargada en bloque con GDAL';

COMMENT ON COLUMN staging.landcover_clc18_es_canarias_raw.source_objectid IS 'OBJECTID original del FileGDB en staging previo a source';
COMMENT ON COLUMN staging.landcover_clc18_es_canarias_raw.code_18 IS 'Codigo funcional filtrado antes de consolidar en source';
COMMENT ON COLUMN staging.landcover_clc18_es_canarias_raw.geom IS 'Geometria reproyectada a EPSG:4326 cargada en bloque con GDAL';

COMMENT ON COLUMN source.landcover_clc18_es.source_fid IS 'Identificador tecnico interno generado por PostgreSQL';
COMMENT ON COLUMN source.landcover_clc18_es.source_objectid IS 'OBJECTID original del FileGDB';
COMMENT ON COLUMN source.landcover_clc18_es.ingest_id IS 'Referencia a ingest.ingest_file para trazabilidad de ingesta';
COMMENT ON COLUMN source.landcover_clc18_es.code_18 IS 'Codigo funcional filtrado antes de persistir en PostGIS';
COMMENT ON COLUMN source.landcover_clc18_es.imported_at IS 'Momento de incorporacion al nivel source';
COMMENT ON COLUMN source.landcover_clc18_es.geom IS 'Geometria reproyectada a EPSG:4326 y aun cercana al origen; puede conservar MultiSurface o invalidez topologica porque la canonizacion pertenece a core';

COMMENT ON COLUMN source.landcover_clc18_es_canarias.source_fid IS 'Identificador tecnico interno generado por PostgreSQL';
COMMENT ON COLUMN source.landcover_clc18_es_canarias.source_objectid IS 'OBJECTID original del FileGDB';
COMMENT ON COLUMN source.landcover_clc18_es_canarias.ingest_id IS 'Referencia a ingest.ingest_file para trazabilidad de ingesta';
COMMENT ON COLUMN source.landcover_clc18_es_canarias.code_18 IS 'Codigo funcional filtrado antes de persistir en PostGIS';
COMMENT ON COLUMN source.landcover_clc18_es_canarias.imported_at IS 'Momento de incorporacion al nivel source';
COMMENT ON COLUMN source.landcover_clc18_es_canarias.geom IS 'Geometria reproyectada a EPSG:4326 y aun cercana al origen; puede conservar MultiSurface o invalidez topologica porque la canonizacion pertenece a core';
