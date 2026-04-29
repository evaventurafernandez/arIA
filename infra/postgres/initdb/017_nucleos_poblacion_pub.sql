-- Fase pub: publicacion derivada de nucleos de poblacion para vector tiles.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS pub;

DROP MATERIALIZED VIEW IF EXISTS pub.nucleos_poblacion_mvt_source;

CREATE MATERIALIZED VIEW pub.nucleos_poblacion_mvt_source AS
SELECT
    core_feature_id,
    nombre,
    habitantes,
    population_class,
    population_rank,
    tipo_code,
    tipo_label,
    ine_code,
    codigo_ep,
    id_ep,
    id_ng,
    prioridad,
    capital_code,
    is_capital,
    ST_Transform(geom, 3857)::geometry(MultiPolygon, 3857) AS geom
FROM core.nucleos_poblacion_polygon
WITH NO DATA;

CREATE UNIQUE INDEX nucleos_poblacion_mvt_source_feature_id_uidx
    ON pub.nucleos_poblacion_mvt_source (core_feature_id);
CREATE INDEX nucleos_poblacion_mvt_source_geom_gix
    ON pub.nucleos_poblacion_mvt_source USING GIST (geom);
CREATE INDEX nucleos_poblacion_mvt_source_population_class_idx
    ON pub.nucleos_poblacion_mvt_source (population_class);
CREATE INDEX nucleos_poblacion_mvt_source_population_rank_idx
    ON pub.nucleos_poblacion_mvt_source (population_rank);
CREATE INDEX nucleos_poblacion_mvt_source_tipo_code_idx
    ON pub.nucleos_poblacion_mvt_source (tipo_code);
CREATE INDEX nucleos_poblacion_mvt_source_is_capital_idx
    ON pub.nucleos_poblacion_mvt_source (is_capital);

COMMENT ON MATERIALIZED VIEW pub.nucleos_poblacion_mvt_source IS 'Publicacion derivada de nucleos de poblacion optimizada para servir vector tiles MVT en EPSG:3857';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.core_feature_id IS 'Identificador estable de feature reutilizable para interactividad en cliente';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.nombre IS 'Nombre publicado del nucleo';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.habitantes IS 'Habitantes normalizados cuando estan disponibles';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.population_class IS 'Clase de tamano poblacional para simbologia';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.population_rank IS 'Orden numerico de la clase poblacional';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.tipo_code IS 'Codigo de tipo BTN 0502';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.tipo_label IS 'Etiqueta generica del tipo BTN 0502';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.ine_code IS 'Codigo INE original cuando esta disponible';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.codigo_ep IS 'Codigo de entidad de poblacion original';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.id_ep IS 'Identificador de entidad de poblacion normalizado cuando existe';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.id_ng IS 'Identificador de nomenclator geografico normalizado cuando existe';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.prioridad IS 'Prioridad original de rotulacion o representacion';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.capital_code IS 'Codigo original de capitalidad BTN 0502';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.is_capital IS 'Indicador operativo de capitalidad';
COMMENT ON COLUMN pub.nucleos_poblacion_mvt_source.geom IS 'Geometria MultiPolygon reproyectada a EPSG:3857 para servicio MVT';
