SELECT 'pub.landcover_mvt_source' AS object_name, to_regclass('pub.landcover_mvt_source') IS NOT NULL AS exists;

SELECT
    count(*) AS total,
    count(*) FILTER (WHERE class_code IS NULL) AS null_class_code,
    count(*) FILTER (WHERE class_label IS NULL) AS null_class_label,
    count(*) FILTER (WHERE class_color IS NULL) AS null_class_color,
    count(*) FILTER (WHERE theme IS NULL) AS null_theme,
    count(*) FILTER (WHERE ST_SRID(geom) <> 3857) AS wrong_srid,
    count(*) FILTER (WHERE ST_GeometryType(geom) <> 'ST_MultiPolygon') AS non_multipolygon,
    count(*) FILTER (WHERE NOT ST_IsValid(geom, 0)) AS invalid_geom,
    count(*) FILTER (WHERE ST_IsEmpty(geom)) AS empty_geom
FROM pub.landcover_mvt_source;
