-- Fase pub: publicacion derivada de tramos viarios IGR-RT para vector tiles.
-- Alimenta el endpoint MVT del visor cuando la fuente activa es el fallback
-- local (WFS de IDEE caido o degradado).

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS pub;

DROP MATERIALIZED VIEW IF EXISTS pub.road_network_mvt_source;

CREATE MATERIALIZED VIEW pub.road_network_mvt_source AS
SELECT
    core_feature_id,
    id_tramo,
    inspire_id,
    clase,
    clase_code,
    tipo,
    tipo_code,
    nombre,
    nombre_alt,
    codigo,
    titular,
    titular_code,
    sentido,
    acceso,
    estado_fisico,
    estado_fisico_code,
    firme,
    n_carriles,
    orden,
    territory_code,
    ST_Transform(geom, 3857)::geometry(MultiLineString, 3857) AS geom
FROM core.road_segment
WITH NO DATA;

CREATE UNIQUE INDEX road_network_mvt_source_feature_id_uidx
    ON pub.road_network_mvt_source (core_feature_id);
CREATE UNIQUE INDEX road_network_mvt_source_id_tramo_uidx
    ON pub.road_network_mvt_source (id_tramo);
CREATE INDEX road_network_mvt_source_geom_gix
    ON pub.road_network_mvt_source USING GIST (geom);
CREATE INDEX road_network_mvt_source_clase_code_idx
    ON pub.road_network_mvt_source (clase_code);
CREATE INDEX road_network_mvt_source_tipo_code_idx
    ON pub.road_network_mvt_source (tipo_code);
CREATE INDEX road_network_mvt_source_titular_code_idx
    ON pub.road_network_mvt_source (titular_code);
CREATE INDEX road_network_mvt_source_estado_fisico_code_idx
    ON pub.road_network_mvt_source (estado_fisico_code);
CREATE INDEX road_network_mvt_source_territory_code_idx
    ON pub.road_network_mvt_source (territory_code);

-- Indices parciales para acelerar el render a bajo zoom (escalonado por clase).
-- Sin ellos, una tesela z=7 obliga al index scan a leer ~1M filas urbanas/caminos
-- para acabar publicando solo ~14k autopistas. Con los parciales, el gist
-- devuelve directamente las filas relevantes.
CREATE INDEX IF NOT EXISTS road_network_mvt_source_highways_geom_gix
    ON pub.road_network_mvt_source USING GIST (geom)
    WHERE clase IN ('Autopista de peaje', 'Autopista libre / autovía');
CREATE INDEX IF NOT EXISTS road_network_mvt_source_arterials_geom_gix
    ON pub.road_network_mvt_source USING GIST (geom)
    WHERE clase IN ('Autopista de peaje', 'Autopista libre / autovía', 'Carretera multicarril');
CREATE INDEX IF NOT EXISTS road_network_mvt_source_interurban_geom_gix
    ON pub.road_network_mvt_source USING GIST (geom)
    WHERE clase IN ('Autopista de peaje', 'Autopista libre / autovía', 'Carretera multicarril', 'Carretera convencional');

COMMENT ON MATERIALIZED VIEW pub.road_network_mvt_source IS 'Publicacion derivada de core.road_segment, reproyectada a EPSG:3857 y optimizada para servir vector tiles MVT como fallback cuando el WFS de IDEE no responde';
COMMENT ON COLUMN pub.road_network_mvt_source.core_feature_id IS 'Identificador estable de feature reutilizable para interactividad en cliente';
COMMENT ON COLUMN pub.road_network_mvt_source.id_tramo IS 'Identificador estable IGR-RT del tramo; clave de pivote con el WFS de IDEE';
COMMENT ON COLUMN pub.road_network_mvt_source.inspire_id IS 'Identificador INSPIRE local equivalente al localId del WFS de IDEE';
COMMENT ON COLUMN pub.road_network_mvt_source.geom IS 'Geometria MultiLineString reproyectada a EPSG:3857 para servicio MVT';
