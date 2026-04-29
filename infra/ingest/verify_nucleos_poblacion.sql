SELECT 'source.nucleos_poblacion_btn' AS object_name, to_regclass('source.nucleos_poblacion_btn') IS NOT NULL AS exists;
SELECT 'core.nucleos_poblacion_polygon' AS object_name, to_regclass('core.nucleos_poblacion_polygon') IS NOT NULL AS exists;
SELECT 'pub.nucleos_poblacion_mvt_source' AS object_name, to_regclass('pub.nucleos_poblacion_mvt_source') IS NOT NULL AS exists;

SELECT 'source' AS stage, count(*) AS total
FROM source.nucleos_poblacion_btn
UNION ALL
SELECT 'core', count(*)
FROM core.nucleos_poblacion_polygon
UNION ALL
SELECT 'mvt', count(*)
FROM pub.nucleos_poblacion_mvt_source;

SELECT
    population_class,
    count(*) AS total,
    min(habitantes) AS min_habitantes,
    max(habitantes) AS max_habitantes
FROM core.nucleos_poblacion_polygon
GROUP BY population_class, population_rank
ORDER BY population_rank;

SELECT
    ST_XMin(ST_Extent(geom)) AS minx,
    ST_YMin(ST_Extent(geom)) AS miny,
    ST_XMax(ST_Extent(geom)) AS maxx,
    ST_YMax(ST_Extent(geom)) AS maxy
FROM core.nucleos_poblacion_polygon;

SELECT
    count(*) FILTER (WHERE NOT ST_IsValid(geom)) AS invalid_geometries,
    count(*) FILTER (WHERE ST_IsEmpty(geom)) AS empty_geometries
FROM core.nucleos_poblacion_polygon;
