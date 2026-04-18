-- Smoke test de la Fase 5.
-- Verifica estructuras canonicas de core y su resultado con datos reales.

SELECT 'core.landcover_class' AS object_name, to_regclass('core.landcover_class') IS NOT NULL AS exists;
SELECT 'core.landcover_polygon' AS object_name, to_regclass('core.landcover_polygon') IS NOT NULL AS exists;

SELECT indexname
FROM pg_indexes
WHERE schemaname = 'core'
  AND tablename = 'landcover_polygon'
ORDER BY indexname;

SELECT count(*) AS class_count
FROM core.landcover_class;

SELECT
    count(*) AS total,
    count(*) FILTER (WHERE dataset_id <> 'landcover_corine_2018_filtered') AS wrong_dataset_id,
    count(*) FILTER (WHERE class_code IS NULL) AS null_class_code,
    count(*) FILTER (WHERE class_label IS NULL) AS null_class_label,
    count(*) FILTER (WHERE class_color IS NULL) AS null_class_color,
    count(*) FILTER (WHERE theme IS NULL) AS null_theme,
    count(*) FILTER (WHERE ST_SRID(geom) <> 4326) AS wrong_srid,
    count(*) FILTER (WHERE ST_GeometryType(geom) <> 'ST_MultiPolygon') AS non_multipolygon,
    count(*) FILTER (WHERE NOT ST_IsValid(geom, 0)) AS invalid_geom,
    count(*) FILTER (WHERE ST_IsEmpty(geom)) AS empty_geom
FROM core.landcover_polygon;

SELECT source_layer, count(*) AS n
FROM core.landcover_polygon
GROUP BY 1
ORDER BY 1;

SELECT class_code, class_label, theme, count(*) AS n
FROM core.landcover_polygon
GROUP BY 1, 2, 3
ORDER BY 1;

SELECT
    (SELECT count(*) FROM source.landcover_corine_polygon) AS source_total,
    (SELECT count(*) FROM core.landcover_polygon) AS core_total,
    (SELECT count(*) FROM source.landcover_corine_polygon s
      LEFT JOIN core.landcover_polygon c
        ON c.source_layer = s.source_layer
       AND c.source_fid = s.source_fid
     WHERE c.core_feature_id IS NULL) AS missing_trace_rows;
