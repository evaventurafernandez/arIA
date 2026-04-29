TRUNCATE TABLE core.nucleos_poblacion_polygon RESTART IDENTITY;

INSERT INTO core.nucleos_poblacion_polygon (
    dataset_id,
    source_layer,
    source_fid,
    source_objectid,
    ingest_id,
    nombre,
    etiqueta,
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
    imported_at,
    geom
)
WITH normalized AS (
    SELECT
        'nucleos_poblacion_btn'::text AS dataset_id,
        source_layer,
        source_fid,
        source_objectid,
        ingest_id,
        COALESCE(NULLIF(btrim(nombre), ''), format('Nucleo %s', source_objectid)) AS nombre,
        NULLIF(btrim(etiqueta), '') AS etiqueta,
        CASE
            WHEN habit_0502 IS NULL OR habit_0502 < 0 THEN NULL
            ELSE round(habit_0502)::integer
        END AS habitantes,
        NULLIF(btrim(tipo_0502), '') AS tipo_code,
        NULLIF(btrim(ine_0502), '') AS ine_code,
        NULLIF(btrim(codigo_ep), '') AS codigo_ep,
        CASE
            WHEN id_ep IS NULL THEN NULL
            ELSE round(id_ep)::bigint
        END AS id_ep,
        CASE
            WHEN id_ng IS NULL THEN NULL
            ELSE round(id_ng)::bigint
        END AS id_ng,
        prioridad,
        COALESCE(NULLIF(btrim(capit_0502), ''), '0000') AS capital_code,
        COALESCE(NULLIF(btrim(capit_0502), ''), '0000') <> '0000' AS is_capital,
        imported_at,
        ST_CollectionExtract(ST_MakeValid(geom), 3) AS geom
    FROM source.nucleos_poblacion_btn_polygon
    WHERE geom IS NOT NULL
),
classified AS (
    SELECT
        *,
        CASE
            WHEN habitantes IS NULL THEN 'sin_dato'
            WHEN habitantes = 0 THEN 'sin_poblacion'
            WHEN habitantes < 100 THEN 'menor_100'
            WHEN habitantes < 500 THEN '100_499'
            WHEN habitantes < 5000 THEN '500_4999'
            WHEN habitantes < 50000 THEN '5000_49999'
            ELSE '50000_mas'
        END AS population_class,
        CASE
            WHEN habitantes IS NULL THEN 0
            WHEN habitantes = 0 THEN 1
            WHEN habitantes < 100 THEN 2
            WHEN habitantes < 500 THEN 3
            WHEN habitantes < 5000 THEN 4
            WHEN habitantes < 50000 THEN 5
            ELSE 6
        END AS population_rank,
        CASE
            WHEN tipo_code IS NULL THEN 'Sin tipo'
            ELSE format('Tipo %s', tipo_code)
        END AS tipo_label
    FROM normalized
    WHERE NOT ST_IsEmpty(geom)
)
SELECT
    dataset_id,
    source_layer,
    source_fid,
    source_objectid,
    ingest_id,
    nombre,
    etiqueta,
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
    imported_at,
    ST_Multi(geom)::geometry(MultiPolygon, 4326) AS geom
FROM classified;

ANALYZE core.nucleos_poblacion_polygon;
