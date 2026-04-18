-- Fase 5: estructuras canónicas de core para landcover.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE IF NOT EXISTS core.landcover_class (
    class_code text PRIMARY KEY CHECK (class_code IN ('311', '312', '313', '321', '322', '323', '324', '211', '242')),
    class_label text NOT NULL,
    class_color text NOT NULL CHECK (class_color ~ '^#[0-9A-Fa-f]{6}$'),
    theme text NOT NULL CHECK (theme IN ('forest', 'grassland', 'shrubland', 'agriculture')),
    display_order smallint NOT NULL UNIQUE
);

INSERT INTO core.landcover_class (class_code, class_label, class_color, theme, display_order)
VALUES
    ('311', 'Bosque de frondosas', '#4ce600', 'forest', 10),
    ('312', 'Bosque de coniferas', '#267300', 'forest', 20),
    ('313', 'Bosque mixto', '#70a800', 'forest', 30),
    ('321', 'Pastizales naturales', '#d4e6a5', 'grassland', 40),
    ('322', 'Brezales y matorrales', '#a8a800', 'shrubland', 50),
    ('323', 'Vegetacion esclerofila', '#d4a46a', 'shrubland', 60),
    ('324', 'Matorral en transicion', '#c8c800', 'shrubland', 70),
    ('211', 'Tierras de labor secano', '#ffffa8', 'agriculture', 80),
    ('242', 'Mosaico de cultivos', '#e6e600', 'agriculture', 90)
ON CONFLICT (class_code) DO UPDATE
SET class_label = EXCLUDED.class_label,
    class_color = EXCLUDED.class_color,
    theme = EXCLUDED.theme,
    display_order = EXCLUDED.display_order;

CREATE TABLE IF NOT EXISTS core.landcover_polygon (
    core_feature_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id text NOT NULL DEFAULT 'landcover_corine_2018_filtered',
    source_layer text NOT NULL CHECK (source_layer IN ('CLC18_ES', 'CLC18_ES_Canarias')),
    source_fid bigint NOT NULL,
    source_objectid bigint NOT NULL,
    ingest_id bigint NOT NULL REFERENCES ingest.ingest_file(ingest_id),
    class_code text NOT NULL REFERENCES core.landcover_class(class_code),
    class_label text NOT NULL,
    class_color text NOT NULL CHECK (class_color ~ '^#[0-9A-Fa-f]{6}$'),
    theme text NOT NULL CHECK (theme IN ('forest', 'grassland', 'shrubland', 'agriculture')),
    imported_at timestamptz NOT NULL,
    canonicalized_at timestamptz NOT NULL DEFAULT now(),
    geom geometry(MultiPolygon, 4326) NOT NULL,
    UNIQUE (source_layer, source_fid)
);

CREATE INDEX IF NOT EXISTS landcover_polygon_geom_gix
    ON core.landcover_polygon USING GIST (geom);
CREATE INDEX IF NOT EXISTS landcover_polygon_class_code_idx
    ON core.landcover_polygon (class_code);
CREATE INDEX IF NOT EXISTS landcover_polygon_theme_idx
    ON core.landcover_polygon (theme);
CREATE INDEX IF NOT EXISTS landcover_polygon_ingest_id_idx
    ON core.landcover_polygon (ingest_id);
CREATE INDEX IF NOT EXISTS landcover_polygon_source_objectid_idx
    ON core.landcover_polygon (source_objectid);

COMMENT ON TABLE core.landcover_class IS 'Catalogo semantico canonico de clases CORINE usadas por la PoC de landcover';
COMMENT ON TABLE core.landcover_polygon IS 'Nivel core canonico de landcover: semantica homogenea y geometria MultiPolygon valida en EPSG:4326';

COMMENT ON COLUMN core.landcover_polygon.dataset_id IS 'Identificador logico estable del dataset homogeneo';
COMMENT ON COLUMN core.landcover_polygon.source_layer IS 'Capa fisica de origen dentro del FileGDB ya consolidada en source';
COMMENT ON COLUMN core.landcover_polygon.source_fid IS 'Identificador tecnico de source del que procede la feature canonica';
COMMENT ON COLUMN core.landcover_polygon.source_objectid IS 'OBJECTID original conservado para trazabilidad frente al FileGDB';
COMMENT ON COLUMN core.landcover_polygon.ingest_id IS 'Carga concreta de ingest.ingest_file desde la que procede la feature';
COMMENT ON COLUMN core.landcover_polygon.class_code IS 'Codigo CORINE funcional estable usado como clase canonica';
COMMENT ON COLUMN core.landcover_polygon.class_label IS 'Etiqueta de negocio homogenea derivada del catalogo de clases';
COMMENT ON COLUMN core.landcover_polygon.class_color IS 'Color canonico asociado a la clase para explotacion posterior';
COMMENT ON COLUMN core.landcover_polygon.theme IS 'Tema homogeneo de explotacion: forest, grassland, shrubland o agriculture';
COMMENT ON COLUMN core.landcover_polygon.imported_at IS 'Momento en que la feature entro en source';
COMMENT ON COLUMN core.landcover_polygon.canonicalized_at IS 'Momento en que la feature fue normalizada a core';
COMMENT ON COLUMN core.landcover_polygon.geom IS 'Geometria canonica validada como MultiPolygon EPSG:4326';
