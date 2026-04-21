-- Fase 7: publicacion derivada de landcover para vector tiles.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS pub;

DROP MATERIALIZED VIEW IF EXISTS pub.landcover_mvt_source;

CREATE MATERIALIZED VIEW pub.landcover_mvt_source AS
SELECT
    core_feature_id,
    class_code,
    class_label,
    class_color,
    theme,
    ST_Transform(geom, 3857)::geometry(MultiPolygon, 3857) AS geom
FROM core.landcover_polygon
WITH NO DATA;

CREATE UNIQUE INDEX landcover_mvt_source_feature_id_uidx
    ON pub.landcover_mvt_source (core_feature_id);
CREATE INDEX landcover_mvt_source_class_code_idx
    ON pub.landcover_mvt_source (class_code);
CREATE INDEX landcover_mvt_source_theme_idx
    ON pub.landcover_mvt_source (theme);
CREATE INDEX landcover_mvt_source_geom_gix
    ON pub.landcover_mvt_source USING GIST (geom);

COMMENT ON MATERIALIZED VIEW pub.landcover_mvt_source IS 'Publicacion derivada de landcover optimizada para servir vector tiles MVT, una fila por feature en EPSG:3857';
COMMENT ON COLUMN pub.landcover_mvt_source.core_feature_id IS 'Identificador estable de feature reutilizable para detalle e interactividad en cliente';
COMMENT ON COLUMN pub.landcover_mvt_source.class_code IS 'Codigo CORINE funcional publicado para teselas vectoriales';
COMMENT ON COLUMN pub.landcover_mvt_source.class_label IS 'Etiqueta publicada para la feature de landcover';
COMMENT ON COLUMN pub.landcover_mvt_source.class_color IS 'Color publicado para renderizado tematico en cliente';
COMMENT ON COLUMN pub.landcover_mvt_source.theme IS 'Tema homogeneo heredado de core';
COMMENT ON COLUMN pub.landcover_mvt_source.geom IS 'Geometria MultiPolygon reproyectada a EPSG:3857 para servicio MVT';
