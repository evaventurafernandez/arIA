-- Fase core: modelo canonico para tramos viarios IGR-RT.
-- Sirve como fallback total y como fuente de enriquecimiento atributivo
-- cuando la geometria llega desde el WFS de transportes de IDEE.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE IF NOT EXISTS core.road_segment (
    core_feature_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id text NOT NULL DEFAULT 'igr_rt_road_segment',
    id_tramo bigint NOT NULL,
    inspire_id text NOT NULL,
    id_vial bigint,
    source_fid bigint NOT NULL,
    source_objectid bigint NOT NULL,
    ingest_id bigint NOT NULL REFERENCES ingest.ingest_file(ingest_id),
    territory_code text NOT NULL,
    territory_name text NOT NULL,
    clase text,
    clase_code integer,
    tipo text,
    tipo_code integer,
    nombre text,
    nombre_alt text,
    codigo text,
    dgc_via text,
    titular text,
    titular_code integer,
    sentido text,
    sentido_code integer,
    acceso text,
    acceso_code integer,
    estado_fisico text,
    estado_fisico_code integer,
    firme text,
    firme_code integer,
    n_carriles integer,
    orden text,
    tipovehic text,
    imported_at timestamptz NOT NULL,
    canonicalized_at timestamptz NOT NULL DEFAULT now(),
    geom geometry(MultiLineString, 4326) NOT NULL,
    UNIQUE (id_tramo)
);

CREATE INDEX IF NOT EXISTS road_segment_geom_gix
    ON core.road_segment USING GIST (geom);
CREATE INDEX IF NOT EXISTS road_segment_id_tramo_idx
    ON core.road_segment (id_tramo);
CREATE INDEX IF NOT EXISTS road_segment_inspire_id_idx
    ON core.road_segment (inspire_id);
CREATE INDEX IF NOT EXISTS road_segment_id_vial_idx
    ON core.road_segment (id_vial);
CREATE INDEX IF NOT EXISTS road_segment_territory_code_idx
    ON core.road_segment (territory_code);
CREATE INDEX IF NOT EXISTS road_segment_clase_code_idx
    ON core.road_segment (clase_code);
CREATE INDEX IF NOT EXISTS road_segment_tipo_code_idx
    ON core.road_segment (tipo_code);
CREATE INDEX IF NOT EXISTS road_segment_titular_code_idx
    ON core.road_segment (titular_code);
CREATE INDEX IF NOT EXISTS road_segment_estado_fisico_code_idx
    ON core.road_segment (estado_fisico_code);
CREATE INDEX IF NOT EXISTS road_segment_codigo_idx
    ON core.road_segment (codigo);
CREATE INDEX IF NOT EXISTS road_segment_nombre_idx
    ON core.road_segment (nombre);
CREATE INDEX IF NOT EXISTS road_segment_canonicalized_at_idx
    ON core.road_segment (canonicalized_at DESC);

COMMENT ON TABLE core.road_segment IS 'Nivel core canonico de tramos viarios IGR-RT: contrato comun usado por el visor con WFS primario o con fallback local';
COMMENT ON COLUMN core.road_segment.dataset_id IS 'Identificador logico estable del dataset homogeneo';
COMMENT ON COLUMN core.road_segment.id_tramo IS 'Identificador estable del tramo IGR-RT; clave de pivote con el WFS de IDEE (inspireId.localId = VIAL_TR || id_tramo)';
COMMENT ON COLUMN core.road_segment.inspire_id IS 'Identificador INSPIRE local equivalente al localId del WFS: VIAL_TR || id_tramo';
COMMENT ON COLUMN core.road_segment.id_vial IS 'Identificador del vial asociado al tramo en la fila representante elegida';
COMMENT ON COLUMN core.road_segment.source_fid IS 'PK tecnica de source.igr_rt_tramo_vial de la fila representante';
COMMENT ON COLUMN core.road_segment.source_objectid IS 'fid original dentro del GeoPackage provincial';
COMMENT ON COLUMN core.road_segment.ingest_id IS 'Carga concreta de ingest.ingest_file desde la que procede la fila representante';
COMMENT ON COLUMN core.road_segment.territory_code IS 'Codigo estable de la provincia o ciudad autonoma de procedencia';
COMMENT ON COLUMN core.road_segment.territory_name IS 'Nombre legible de la provincia o ciudad autonoma';
COMMENT ON COLUMN core.road_segment.clase IS 'Descripcion homogenea de clase de via; sentinelas -997 y -998 mapeadas a NULL';
COMMENT ON COLUMN core.road_segment.clase_code IS 'Codigo numerico original de clase de via';
COMMENT ON COLUMN core.road_segment.tipo IS 'Descripcion homogenea de tipo de tramo';
COMMENT ON COLUMN core.road_segment.tipo_code IS 'Codigo numerico original de tipo de tramo';
COMMENT ON COLUMN core.road_segment.nombre IS 'Nombre publicado del vial asociado';
COMMENT ON COLUMN core.road_segment.nombre_alt IS 'Nombre alternativo del vial asociado';
COMMENT ON COLUMN core.road_segment.codigo IS 'Codigo o identificador textual de carretera/vial publicado';
COMMENT ON COLUMN core.road_segment.dgc_via IS 'Codigo DGC de via cuando existe en origen';
COMMENT ON COLUMN core.road_segment.titular IS 'Descripcion homogenea de titularidad';
COMMENT ON COLUMN core.road_segment.titular_code IS 'Codigo numerico original de titularidad';
COMMENT ON COLUMN core.road_segment.sentido IS 'Descripcion homogenea de sentido de circulacion';
COMMENT ON COLUMN core.road_segment.sentido_code IS 'Codigo numerico original de sentido';
COMMENT ON COLUMN core.road_segment.acceso IS 'Descripcion homogenea de acceso';
COMMENT ON COLUMN core.road_segment.acceso_code IS 'Codigo numerico original de acceso';
COMMENT ON COLUMN core.road_segment.estado_fisico IS 'Descripcion homogenea de estado fisico';
COMMENT ON COLUMN core.road_segment.estado_fisico_code IS 'Codigo numerico original de estado fisico';
COMMENT ON COLUMN core.road_segment.firme IS 'Descripcion homogenea de firme';
COMMENT ON COLUMN core.road_segment.firme_code IS 'Codigo numerico original de firme';
COMMENT ON COLUMN core.road_segment.n_carriles IS 'Numero de carriles parseado a entero; NULL si origen no es entero valido';
COMMENT ON COLUMN core.road_segment.orden IS 'Orden/categoria textual del vial';
COMMENT ON COLUMN core.road_segment.tipovehic IS 'Descripcion homogenea de vehiculos permitidos';
COMMENT ON COLUMN core.road_segment.imported_at IS 'Momento en que la fila representante entro en source';
COMMENT ON COLUMN core.road_segment.canonicalized_at IS 'Momento en que el tramo fue normalizado a core';
COMMENT ON COLUMN core.road_segment.geom IS 'Geometria canonica validada como MultiLineString EPSG:4326, forzada a 2D';
