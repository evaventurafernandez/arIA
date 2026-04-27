-- Smoke test de la Fase 4.
-- Devuelve filas con objetos esperados, calidad del contrato source y su estado de existencia.

SELECT 'ingest.ingest_file' AS object_name, to_regclass('ingest.ingest_file') IS NOT NULL AS exists;
SELECT 'staging.landcover_clc18_es_raw' AS object_name, to_regclass('staging.landcover_clc18_es_raw') IS NOT NULL AS exists;
SELECT 'staging.landcover_clc18_es_canarias_raw' AS object_name, to_regclass('staging.landcover_clc18_es_canarias_raw') IS NOT NULL AS exists;
SELECT 'source.landcover_clc18_es' AS object_name, to_regclass('source.landcover_clc18_es') IS NOT NULL AS exists;
SELECT 'source.landcover_clc18_es_canarias' AS object_name, to_regclass('source.landcover_clc18_es_canarias') IS NOT NULL AS exists;
SELECT 'source.landcover_corine_polygon' AS object_name, to_regclass('source.landcover_corine_polygon') IS NOT NULL AS exists;

SELECT indexname
FROM pg_indexes
WHERE schemaname IN ('staging', 'source')
  AND tablename IN (
      'landcover_clc18_es',
      'landcover_clc18_es_canarias',
      'landcover_clc18_es_raw',
      'landcover_clc18_es_canarias_raw'
  )
ORDER BY indexname;

SELECT
  'staging' AS stage_name,
  count(*) AS total,
  count(*) FILTER (WHERE source_objectid IS NULL) AS null_source_objectid,
  count(*) FILTER (WHERE code_18 IS NULL) AS null_code_18,
  count(*) FILTER (WHERE ST_SRID(geom) <> 4326) AS wrong_srid
FROM (
  SELECT source_objectid, code_18, geom FROM staging.landcover_clc18_es_raw
  UNION ALL
  SELECT source_objectid, code_18, geom FROM staging.landcover_clc18_es_canarias_raw
) AS stage_union;

SELECT
  count(*) AS total,
  count(*) FILTER (WHERE ingest_id IS NULL) AS null_ingest_id,
  count(*) FILTER (WHERE source_objectid IS NULL) AS null_source_objectid,
  count(*) FILTER (WHERE code_18 IS NULL) AS null_code_18,
  count(*) FILTER (WHERE ST_SRID(geom) <> 4326) AS wrong_srid,
  count(*) FILTER (WHERE NOT ST_IsValid(geom)) AS invalid_geom,
  count(*) FILTER (WHERE ST_GeometryType(geom) = 'ST_MultiSurface') AS multi_surface_geom
FROM source.landcover_corine_polygon;

SELECT source_layer, ST_GeometryType(geom) AS geom_type, count(*) AS n
FROM source.landcover_corine_polygon
GROUP BY 1, 2
ORDER BY 1, 2;
