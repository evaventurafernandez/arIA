-- Fase 5: reconstruccion reproducible de core a partir de source.

TRUNCATE TABLE core.landcover_polygon RESTART IDENTITY;

WITH prepared AS (
    SELECT
        source_layer,
        source_fid,
        source_objectid,
        ingest_id,
        code_18,
        imported_at,
        geom,
        ST_GeometryType(geom) AS geom_type
    FROM source.landcover_corine_polygon
),
canonical AS (
    SELECT
        source_layer,
        source_fid,
        source_objectid,
        ingest_id,
        code_18,
        imported_at,
        CASE
            WHEN geom_type = 'ST_MultiPolygon' AND ST_IsValid(geom, 0) THEN geom::geometry(MultiPolygon, 4326)
            ELSE ST_Multi(
                ST_CollectionExtract(
                    ST_Buffer(
                        CASE
                            WHEN geom_type = 'ST_MultiSurface' THEN ST_CurveToLine(geom)
                            ELSE geom
                        END,
                        0
                    ),
                    3
                )
            )::geometry(MultiPolygon, 4326)
        END AS geom
    FROM prepared
),
non_empty AS (
    SELECT *
    FROM canonical
    WHERE NOT ST_IsEmpty(geom)
)
INSERT INTO core.landcover_polygon (
    dataset_id,
    source_layer,
    source_fid,
    source_objectid,
    ingest_id,
    class_code,
    class_label,
    class_color,
    theme,
    imported_at,
    canonicalized_at,
    geom
)
SELECT
    'landcover_corine_2018_filtered' AS dataset_id,
    ne.source_layer,
    ne.source_fid,
    ne.source_objectid,
    ne.ingest_id,
    lc.class_code,
    lc.class_label,
    lc.class_color,
    lc.theme,
    ne.imported_at,
    now() AS canonicalized_at,
    ne.geom
FROM non_empty AS ne
JOIN core.landcover_class AS lc
  ON lc.class_code = CASE
      WHEN ne.code_18 IN ('111', '112') THEN '1001'
      ELSE ne.code_18
  END;
