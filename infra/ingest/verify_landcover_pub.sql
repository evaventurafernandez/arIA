-- Smoke test de la Fase 6.
-- Verifica estructuras publicadas de pub y su resultado con datos reales.

SELECT 'pub.landcover_filtered' AS object_name, to_regclass('pub.landcover_filtered') IS NOT NULL AS exists;

SELECT indexname
FROM pg_indexes
WHERE schemaname = 'pub'
  AND tablename = 'landcover_filtered'
ORDER BY indexname;

SELECT
    count(*) AS total,
    count(*) FILTER (WHERE class_code IS NULL) AS null_class_code,
    count(*) FILTER (WHERE class_label IS NULL) AS null_class_label,
    count(*) FILTER (WHERE class_color IS NULL) AS null_class_color,
    count(*) FILTER (WHERE theme IS NULL) AS null_theme,
    count(*) FILTER (WHERE ST_SRID(geom) <> 4326) AS wrong_srid,
    count(*) FILTER (WHERE ST_GeometryType(geom) <> 'ST_MultiPolygon') AS non_multipolygon,
    count(*) FILTER (WHERE NOT ST_IsValid(geom, 0)) AS invalid_geom,
    count(*) FILTER (WHERE ST_IsEmpty(geom)) AS empty_geom
FROM pub.landcover_filtered;

SELECT class_code, class_label, class_color, theme
FROM pub.landcover_filtered
ORDER BY class_code;

SELECT
    (SELECT count(*) FROM core.landcover_class) AS class_catalog_total,
    (SELECT count(*) FROM pub.landcover_filtered) AS pub_total,
    (SELECT count(*) FROM core.landcover_class c
      LEFT JOIN pub.landcover_filtered p
        ON p.class_code = c.class_code
     WHERE p.feature_id IS NULL) AS missing_pub_classes;
