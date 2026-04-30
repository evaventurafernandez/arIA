-- Fase core: modelo canonico para nucleos de poblacion BTN.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE IF NOT EXISTS core.nucleos_poblacion_polygon (
    core_feature_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id text NOT NULL DEFAULT 'nucleos_poblacion_btn',
    source_layer text NOT NULL DEFAULT 'btn0502s_ent_pob',
    source_fid bigint NOT NULL,
    source_objectid bigint NOT NULL,
    ingest_id bigint NOT NULL REFERENCES ingest.ingest_file(ingest_id),
    nombre text NOT NULL,
    etiqueta text,
    habitantes integer,
    population_class text NOT NULL CHECK (
        population_class IN ('menor_100', '100_499', '500_4999', '5000_49999', '50000_mas')
    ),
    population_rank smallint NOT NULL CHECK (population_rank BETWEEN 1 AND 5),
    tipo_code text,
    tipo_label text NOT NULL,
    ine_code text,
    codigo_ep text,
    id_ep bigint,
    id_ng bigint,
    prioridad integer,
    capital_code text,
    is_capital boolean NOT NULL DEFAULT false,
    imported_at timestamptz NOT NULL,
    canonicalized_at timestamptz NOT NULL DEFAULT now(),
    geom geometry(MultiPolygon, 4326) NOT NULL,
    UNIQUE (source_layer, source_fid)
);

CREATE INDEX IF NOT EXISTS nucleos_poblacion_polygon_geom_gix
    ON core.nucleos_poblacion_polygon USING GIST (geom);
CREATE INDEX IF NOT EXISTS nucleos_poblacion_polygon_source_objectid_idx
    ON core.nucleos_poblacion_polygon (source_objectid);
CREATE INDEX IF NOT EXISTS nucleos_poblacion_polygon_ingest_id_idx
    ON core.nucleos_poblacion_polygon (ingest_id);
CREATE INDEX IF NOT EXISTS nucleos_poblacion_polygon_nombre_idx
    ON core.nucleos_poblacion_polygon (nombre);
CREATE INDEX IF NOT EXISTS nucleos_poblacion_polygon_habitantes_idx
    ON core.nucleos_poblacion_polygon (habitantes);
CREATE INDEX IF NOT EXISTS nucleos_poblacion_polygon_population_class_idx
    ON core.nucleos_poblacion_polygon (population_class);
CREATE INDEX IF NOT EXISTS nucleos_poblacion_polygon_tipo_code_idx
    ON core.nucleos_poblacion_polygon (tipo_code);
CREATE INDEX IF NOT EXISTS nucleos_poblacion_polygon_is_capital_idx
    ON core.nucleos_poblacion_polygon (is_capital);
CREATE INDEX IF NOT EXISTS nucleos_poblacion_polygon_canonicalized_at_idx
    ON core.nucleos_poblacion_polygon (canonicalized_at DESC);

COMMENT ON TABLE core.nucleos_poblacion_polygon IS 'Nivel core canonico de nucleos de poblacion: atributos homogeneos y geometria MultiPolygon valida en EPSG:4326';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.dataset_id IS 'Identificador logico estable del dataset homogeneo';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.source_layer IS 'Capa fisica de origen dentro del GeoPackage BTN';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.source_fid IS 'Identificador tecnico de source del que procede la feature canonica';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.source_objectid IS 'Identificador original id/rowid del GeoPackage BTN';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.ingest_id IS 'Carga concreta de ingest.ingest_file desde la que procede la feature';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.nombre IS 'Nombre homogeneo publicado para el nucleo';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.etiqueta IS 'Etiqueta original conservada como apoyo de rotulacion';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.habitantes IS 'Habitantes normalizados a entero; la capa core excluye registros sin dato o con 0 habitantes';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.population_class IS 'Clase de tamano poblacional positiva para simbologia y filtrado';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.population_rank IS 'Orden numerico de la clase poblacional';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.tipo_code IS 'Codigo de tipo BTN 0502';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.tipo_label IS 'Etiqueta generica derivada del codigo de tipo BTN 0502';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.ine_code IS 'Codigo INE original cuando esta disponible';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.codigo_ep IS 'Codigo de entidad de poblacion original';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.id_ep IS 'Identificador de entidad de poblacion normalizado a entero cuando existe';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.id_ng IS 'Identificador de nomenclator geografico normalizado a entero cuando existe';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.prioridad IS 'Prioridad original de rotulacion o representacion';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.capital_code IS 'Codigo original de capitalidad BTN 0502';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.is_capital IS 'Indicador operativo derivado de capital_code distinto de 0000';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.imported_at IS 'Momento en que la feature entro en source';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.canonicalized_at IS 'Momento en que la feature fue normalizada a core';
COMMENT ON COLUMN core.nucleos_poblacion_polygon.geom IS 'Geometria canonica validada como MultiPolygon EPSG:4326';
