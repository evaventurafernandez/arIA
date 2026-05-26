-- Fase source: estructuras cercanas al origen para IGR-RT red viaria.

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

CREATE TABLE IF NOT EXISTS staging.igr_rt_tramo_vial_raw (
    source_objectid bigint NOT NULL,
    source_zip_name text NOT NULL,
    source_gpkg_name text NOT NULL,
    source_layer text NOT NULL,
    territory_code text NOT NULL,
    territory_name text NOT NULL,
    id_tramo bigint,
    id_vial bigint,
    tipo_tramo bigint,
    tipo_tramd text,
    calzada bigint,
    calzadad text,
    acceso bigint,
    accesod text,
    firme bigint,
    firmed text,
    ncarriles text,
    sentido bigint,
    sentidod text,
    situacion bigint,
    situaciond text,
    estadofis bigint,
    estadofisd text,
    tipovehic text,
    tipovehicd text,
    titular bigint,
    titulard text,
    orden text,
    ordend text,
    fuente_t bigint,
    fuente_td text,
    codigo text,
    dgc_via text,
    clase bigint,
    clased text,
    tipo_vial bigint,
    tipo_viald text,
    nombre text,
    nombre_alt text,
    fuente_v bigint,
    fuente_vd text,
    alta_db text,
    geom geometry(Geometry, 4326) NOT NULL
);

CREATE TABLE IF NOT EXISTS source.igr_rt_tramo_vial (
    source_fid bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_objectid bigint NOT NULL,
    ingest_id bigint NOT NULL REFERENCES ingest.ingest_file(ingest_id),
    source_zip_name text NOT NULL,
    source_gpkg_name text NOT NULL,
    source_layer text NOT NULL DEFAULT 'rt_tramo_vial',
    territory_code text NOT NULL,
    territory_name text NOT NULL,
    id_tramo bigint,
    id_vial bigint,
    tipo_tramo bigint,
    tipo_tramd text,
    calzada bigint,
    calzadad text,
    acceso bigint,
    accesod text,
    firme bigint,
    firmed text,
    ncarriles text,
    sentido bigint,
    sentidod text,
    situacion bigint,
    situaciond text,
    estadofis bigint,
    estadofisd text,
    tipovehic text,
    tipovehicd text,
    titular bigint,
    titulard text,
    orden text,
    ordend text,
    fuente_t bigint,
    fuente_td text,
    codigo text,
    dgc_via text,
    clase bigint,
    clased text,
    tipo_vial bigint,
    tipo_viald text,
    nombre text,
    nombre_alt text,
    fuente_v bigint,
    fuente_vd text,
    alta_db text,
    imported_at timestamptz NOT NULL DEFAULT now(),
    geom geometry(Geometry, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_raw_geom_gix
    ON staging.igr_rt_tramo_vial_raw USING GIST (geom);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_raw_territory_code_idx
    ON staging.igr_rt_tramo_vial_raw (territory_code);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_raw_source_objectid_idx
    ON staging.igr_rt_tramo_vial_raw (source_objectid);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_raw_id_tramo_idx
    ON staging.igr_rt_tramo_vial_raw (id_tramo);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_raw_clase_idx
    ON staging.igr_rt_tramo_vial_raw (clase);

CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_geom_gix
    ON source.igr_rt_tramo_vial USING GIST (geom);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_ingest_id_idx
    ON source.igr_rt_tramo_vial (ingest_id);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_territory_code_idx
    ON source.igr_rt_tramo_vial (territory_code);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_source_zip_name_idx
    ON source.igr_rt_tramo_vial (source_zip_name);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_source_objectid_idx
    ON source.igr_rt_tramo_vial (source_objectid);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_id_tramo_idx
    ON source.igr_rt_tramo_vial (id_tramo);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_id_vial_idx
    ON source.igr_rt_tramo_vial (id_vial);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_clase_idx
    ON source.igr_rt_tramo_vial (clase);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_tipo_tramo_idx
    ON source.igr_rt_tramo_vial (tipo_tramo);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_tipo_vial_idx
    ON source.igr_rt_tramo_vial (tipo_vial);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_titular_idx
    ON source.igr_rt_tramo_vial (titular);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_estadofis_idx
    ON source.igr_rt_tramo_vial (estadofis);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_codigo_idx
    ON source.igr_rt_tramo_vial (codigo);
CREATE INDEX IF NOT EXISTS igr_rt_tramo_vial_nombre_idx
    ON source.igr_rt_tramo_vial (nombre);

CREATE OR REPLACE VIEW source.igr_rt_road_segment AS
SELECT
    source_layer,
    source_fid,
    source_objectid,
    ingest_id,
    source_zip_name,
    source_gpkg_name,
    territory_code,
    territory_name,
    id_tramo,
    id_vial,
    tipo_tramo,
    tipo_tramd,
    calzada,
    calzadad,
    acceso,
    accesod,
    firme,
    firmed,
    ncarriles,
    sentido,
    sentidod,
    situacion,
    situaciond,
    estadofis,
    estadofisd,
    tipovehic,
    tipovehicd,
    titular,
    titulard,
    orden,
    ordend,
    fuente_t,
    fuente_td,
    codigo,
    dgc_via,
    clase,
    clased,
    tipo_vial,
    tipo_viald,
    nombre,
    nombre_alt,
    fuente_v,
    fuente_vd,
    alta_db,
    imported_at,
    geom
FROM source.igr_rt_tramo_vial;

COMMENT ON TABLE staging.igr_rt_tramo_vial_raw IS 'Staging masivo de IGR-RT red_viaria.gpkg/rt_tramo_vial para carga bulk previa al contrato source';
COMMENT ON TABLE source.igr_rt_tramo_vial IS 'Nivel source cercano al origen para IGR-RT red viaria provincial, capa rt_tramo_vial de red_viaria.gpkg';
COMMENT ON VIEW source.igr_rt_road_segment IS 'Vista source unificada de tramos viarios IGR-RT; core normalizara codigos, sentinelas y geometria 2D para publicacion';

COMMENT ON COLUMN staging.igr_rt_tramo_vial_raw.source_objectid IS 'fid original dentro de rt_tramo_vial en el GeoPackage provincial';
COMMENT ON COLUMN staging.igr_rt_tramo_vial_raw.source_zip_name IS 'Nombre del ZIP provincial RT_*_gpkg.zip del que procede la feature';
COMMENT ON COLUMN staging.igr_rt_tramo_vial_raw.source_gpkg_name IS 'GeoPackage interno del ZIP; para esta fase red_viaria.gpkg';
COMMENT ON COLUMN staging.igr_rt_tramo_vial_raw.source_layer IS 'Capa interna del GeoPackage; para esta fase rt_tramo_vial';
COMMENT ON COLUMN staging.igr_rt_tramo_vial_raw.territory_code IS 'Codigo estable derivado del nombre del ZIP provincial o ciudad autonoma';
COMMENT ON COLUMN staging.igr_rt_tramo_vial_raw.territory_name IS 'Nombre legible de la provincia o ciudad autonoma';
COMMENT ON COLUMN staging.igr_rt_tramo_vial_raw.geom IS 'Geometria cargada desde IGR-RT y reproyectada a EPSG:4326; puede conservar Z en source/staging';

COMMENT ON COLUMN source.igr_rt_tramo_vial.source_fid IS 'Identificador tecnico interno generado por PostgreSQL';
COMMENT ON COLUMN source.igr_rt_tramo_vial.source_objectid IS 'fid original dentro de rt_tramo_vial en el GeoPackage provincial';
COMMENT ON COLUMN source.igr_rt_tramo_vial.ingest_id IS 'Referencia a ingest.ingest_file para trazabilidad de ingesta';
COMMENT ON COLUMN source.igr_rt_tramo_vial.source_zip_name IS 'Nombre del ZIP provincial RT_*_gpkg.zip del que procede la feature';
COMMENT ON COLUMN source.igr_rt_tramo_vial.source_gpkg_name IS 'GeoPackage interno del ZIP; para esta fase red_viaria.gpkg';
COMMENT ON COLUMN source.igr_rt_tramo_vial.source_layer IS 'Capa interna del GeoPackage; para esta fase rt_tramo_vial';
COMMENT ON COLUMN source.igr_rt_tramo_vial.territory_code IS 'Codigo estable derivado del nombre del ZIP provincial o ciudad autonoma';
COMMENT ON COLUMN source.igr_rt_tramo_vial.territory_name IS 'Nombre legible de la provincia o ciudad autonoma';
COMMENT ON COLUMN source.igr_rt_tramo_vial.id_tramo IS 'Identificador original del tramo viario';
COMMENT ON COLUMN source.igr_rt_tramo_vial.id_vial IS 'Identificador original del vial asociado; rt_tramo_vial ya incorpora la union tramo-vial del paquete provincial';
COMMENT ON COLUMN source.igr_rt_tramo_vial.tipo_tramo IS 'Codigo original de tipo de tramo';
COMMENT ON COLUMN source.igr_rt_tramo_vial.tipo_tramd IS 'Descripcion original de tipo de tramo';
COMMENT ON COLUMN source.igr_rt_tramo_vial.calzada IS 'Codigo original de tipo de calzada';
COMMENT ON COLUMN source.igr_rt_tramo_vial.calzadad IS 'Descripcion original de tipo de calzada';
COMMENT ON COLUMN source.igr_rt_tramo_vial.acceso IS 'Codigo original de acceso';
COMMENT ON COLUMN source.igr_rt_tramo_vial.accesod IS 'Descripcion original de acceso';
COMMENT ON COLUMN source.igr_rt_tramo_vial.firme IS 'Codigo original de firme';
COMMENT ON COLUMN source.igr_rt_tramo_vial.firmed IS 'Descripcion original de firme';
COMMENT ON COLUMN source.igr_rt_tramo_vial.ncarriles IS 'Numero de carriles conservado como texto porque el origen lo publica como campo String';
COMMENT ON COLUMN source.igr_rt_tramo_vial.sentido IS 'Codigo original de sentido de circulacion';
COMMENT ON COLUMN source.igr_rt_tramo_vial.sentidod IS 'Descripcion original de sentido de circulacion';
COMMENT ON COLUMN source.igr_rt_tramo_vial.situacion IS 'Codigo original de situacion del tramo';
COMMENT ON COLUMN source.igr_rt_tramo_vial.situaciond IS 'Descripcion original de situacion del tramo';
COMMENT ON COLUMN source.igr_rt_tramo_vial.estadofis IS 'Codigo original de estado fisico';
COMMENT ON COLUMN source.igr_rt_tramo_vial.estadofisd IS 'Descripcion original de estado fisico';
COMMENT ON COLUMN source.igr_rt_tramo_vial.tipovehic IS 'Mascara o codigo textual de vehiculos permitidos conservado como texto';
COMMENT ON COLUMN source.igr_rt_tramo_vial.tipovehicd IS 'Descripcion original de vehiculos permitidos';
COMMENT ON COLUMN source.igr_rt_tramo_vial.titular IS 'Codigo original de titularidad';
COMMENT ON COLUMN source.igr_rt_tramo_vial.titulard IS 'Descripcion original de titularidad';
COMMENT ON COLUMN source.igr_rt_tramo_vial.orden IS 'Orden/categoria textual del vial, conservado como texto';
COMMENT ON COLUMN source.igr_rt_tramo_vial.ordend IS 'Descripcion original de orden/categoria';
COMMENT ON COLUMN source.igr_rt_tramo_vial.fuente_t IS 'Codigo original de fuente del tramo';
COMMENT ON COLUMN source.igr_rt_tramo_vial.fuente_td IS 'Descripcion original de fuente del tramo';
COMMENT ON COLUMN source.igr_rt_tramo_vial.codigo IS 'Codigo o identificador textual de carretera/vial publicado por IGR-RT';
COMMENT ON COLUMN source.igr_rt_tramo_vial.dgc_via IS 'Codigo DGC de via cuando existe en origen';
COMMENT ON COLUMN source.igr_rt_tramo_vial.clase IS 'Codigo original de clase de via';
COMMENT ON COLUMN source.igr_rt_tramo_vial.clased IS 'Descripcion original de clase de via';
COMMENT ON COLUMN source.igr_rt_tramo_vial.tipo_vial IS 'Codigo original de tipo de vial';
COMMENT ON COLUMN source.igr_rt_tramo_vial.tipo_viald IS 'Descripcion original de tipo de vial';
COMMENT ON COLUMN source.igr_rt_tramo_vial.nombre IS 'Nombre original del vial';
COMMENT ON COLUMN source.igr_rt_tramo_vial.nombre_alt IS 'Nombre alternativo original del vial';
COMMENT ON COLUMN source.igr_rt_tramo_vial.fuente_v IS 'Codigo original de fuente del vial';
COMMENT ON COLUMN source.igr_rt_tramo_vial.fuente_vd IS 'Descripcion original de fuente del vial';
COMMENT ON COLUMN source.igr_rt_tramo_vial.alta_db IS 'Fecha de alta o modificacion en la base de datos IGR-RT, conservada como texto de origen';
COMMENT ON COLUMN source.igr_rt_tramo_vial.imported_at IS 'Momento de incorporacion al nivel source';
COMMENT ON COLUMN source.igr_rt_tramo_vial.geom IS 'Geometria original reproyectada a EPSG:4326 y cercana al origen; core decidira ST_Force2D y validacion para MVT';
