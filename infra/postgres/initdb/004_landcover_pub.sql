-- Fase 6: publicacion derivada de landcover para explotacion.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS pub;

DROP MATERIALIZED VIEW IF EXISTS pub.landcover_filtered;

CREATE MATERIALIZED VIEW pub.landcover_filtered AS
WITH simplified AS (
    SELECT
        format('landcover_%s', class_code) AS feature_id,
        class_code,
        class_label,
        class_color,
        theme,
        ST_SimplifyPreserveTopology(geom, 0.005) AS geom
    FROM core.landcover_polygon
),
aggregated AS (
    SELECT
        feature_id,
        class_code,
        class_label,
        class_color,
        theme,
        ST_Multi(
            ST_CollectionExtract(
                ST_UnaryUnion(ST_Collect(geom)),
                3
            )
        )::geometry(MultiPolygon, 4326) AS geom
    FROM simplified
    GROUP BY feature_id, class_code, class_label, class_color, theme
)
SELECT
    feature_id,
    class_code,
    class_label,
    class_color,
    theme,
    geom
FROM aggregated
WITH NO DATA;

CREATE UNIQUE INDEX landcover_filtered_feature_id_uidx
    ON pub.landcover_filtered (feature_id);
CREATE UNIQUE INDEX landcover_filtered_class_code_uidx
    ON pub.landcover_filtered (class_code);
CREATE INDEX landcover_filtered_geom_gix
    ON pub.landcover_filtered USING GIST (geom);

COMMENT ON MATERIALIZED VIEW pub.landcover_filtered IS 'Publicacion derivada de landcover equivalente al flujo historico: simplificacion por feature, dissolve por clase y payload minimo para explotacion';
COMMENT ON COLUMN pub.landcover_filtered.feature_id IS 'Identificador estable de explotacion, una fila por clase publicada';
COMMENT ON COLUMN pub.landcover_filtered.class_code IS 'Codigo canonico publicado como identificador funcional de clase';
COMMENT ON COLUMN pub.landcover_filtered.class_label IS 'Etiqueta de explotacion publicada para la clase';
COMMENT ON COLUMN pub.landcover_filtered.class_color IS 'Color de explotacion publicado para la clase';
COMMENT ON COLUMN pub.landcover_filtered.theme IS 'Tema homogeneo heredado de core para filtrado funcional posterior';
COMMENT ON COLUMN pub.landcover_filtered.geom IS 'Geometria MultiPolygon agregada por clase en EPSG:4326 tras simplificacion 0.005 y dissolve';
