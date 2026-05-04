-- Fase source: estructuras cercanas al origen para nucleos de poblacion BTN.

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

CREATE TABLE IF NOT EXISTS source.nucleos_poblacion_btn (
    source_fid bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_objectid bigint NOT NULL,
    ingest_id bigint NOT NULL REFERENCES ingest.ingest_file(ingest_id),
    nombre text,
    etiqueta text,
    tipo_0502 text,
    ine_0502 text,
    fecha_ine double precision,
    habit_0502 double precision,
    codigo_ep text,
    id_ep double precision,
    id_bic text,
    id_bicca text,
    id_ng double precision,
    prioridad integer,
    f_alta text,
    capit_0502 text,
    imported_at timestamptz NOT NULL DEFAULT now(),
    geom geometry(Geometry, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS nucleos_poblacion_btn_geom_gix
    ON source.nucleos_poblacion_btn USING GIST (geom);
CREATE INDEX IF NOT EXISTS nucleos_poblacion_btn_source_objectid_idx
    ON source.nucleos_poblacion_btn (source_objectid);
CREATE INDEX IF NOT EXISTS nucleos_poblacion_btn_ingest_id_idx
    ON source.nucleos_poblacion_btn (ingest_id);
CREATE INDEX IF NOT EXISTS nucleos_poblacion_btn_nombre_idx
    ON source.nucleos_poblacion_btn (nombre);
CREATE INDEX IF NOT EXISTS nucleos_poblacion_btn_habit_0502_idx
    ON source.nucleos_poblacion_btn (habit_0502);
CREATE INDEX IF NOT EXISTS nucleos_poblacion_btn_tipo_0502_idx
    ON source.nucleos_poblacion_btn (tipo_0502);
CREATE INDEX IF NOT EXISTS nucleos_poblacion_btn_capit_0502_idx
    ON source.nucleos_poblacion_btn (capit_0502);

CREATE OR REPLACE VIEW source.nucleos_poblacion_btn_polygon AS
SELECT
    'btn0502s_ent_pob'::text AS source_layer,
    source_fid,
    source_objectid,
    ingest_id,
    nombre,
    etiqueta,
    tipo_0502,
    ine_0502,
    fecha_ine,
    habit_0502,
    codigo_ep,
    id_ep,
    id_bic,
    id_bicca,
    id_ng,
    prioridad,
    f_alta,
    capit_0502,
    imported_at,
    geom
FROM source.nucleos_poblacion_btn;

COMMENT ON TABLE source.nucleos_poblacion_btn IS 'Nivel source cercano al origen para nucleos de poblacion BTN del IGN, capa btn0502s_ent_pob del GeoPackage';
COMMENT ON VIEW source.nucleos_poblacion_btn_polygon IS 'Vista source unificada de poligonos de nucleos de poblacion BTN; core normaliza atributos y geometria';

COMMENT ON COLUMN source.nucleos_poblacion_btn.source_fid IS 'Identificador tecnico interno generado por PostgreSQL';
COMMENT ON COLUMN source.nucleos_poblacion_btn.source_objectid IS 'Identificador original id/rowid del GeoPackage BTN';
COMMENT ON COLUMN source.nucleos_poblacion_btn.ingest_id IS 'Referencia a ingest.ingest_file para trazabilidad de ingesta';
COMMENT ON COLUMN source.nucleos_poblacion_btn.nombre IS 'Nombre original del nucleo de poblacion';
COMMENT ON COLUMN source.nucleos_poblacion_btn.etiqueta IS 'Etiqueta original del nucleo de poblacion';
COMMENT ON COLUMN source.nucleos_poblacion_btn.tipo_0502 IS 'Codigo de tipo original BTN 0502';
COMMENT ON COLUMN source.nucleos_poblacion_btn.ine_0502 IS 'Codigo INE original asociado al nucleo cuando esta disponible';
COMMENT ON COLUMN source.nucleos_poblacion_btn.fecha_ine IS 'Fecha o ano INE original, conservado cercano al origen';
COMMENT ON COLUMN source.nucleos_poblacion_btn.habit_0502 IS 'Habitantes originales publicados por BTN 0502 cuando estan disponibles';
COMMENT ON COLUMN source.nucleos_poblacion_btn.codigo_ep IS 'Codigo de entidad de poblacion original';
COMMENT ON COLUMN source.nucleos_poblacion_btn.id_ep IS 'Identificador de entidad de poblacion original';
COMMENT ON COLUMN source.nucleos_poblacion_btn.id_bic IS 'Identificador BIC original cuando existe';
COMMENT ON COLUMN source.nucleos_poblacion_btn.id_bicca IS 'Identificador BICCA original cuando existe';
COMMENT ON COLUMN source.nucleos_poblacion_btn.id_ng IS 'Identificador de nomenclator geografico original cuando existe';
COMMENT ON COLUMN source.nucleos_poblacion_btn.prioridad IS 'Prioridad original de rotulacion o representacion';
COMMENT ON COLUMN source.nucleos_poblacion_btn.f_alta IS 'Fecha de alta original';
COMMENT ON COLUMN source.nucleos_poblacion_btn.capit_0502 IS 'Codigo original de capitalidad BTN 0502';
COMMENT ON COLUMN source.nucleos_poblacion_btn.imported_at IS 'Momento de incorporacion al nivel source';
COMMENT ON COLUMN source.nucleos_poblacion_btn.geom IS 'Geometria reproyectada a EPSG:4326 y aun cercana al origen';
