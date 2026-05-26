-- Refresca core.road_segment desde source.igr_rt_tramo_vial.
-- Reglas aplicadas:
--   1. Una fila por id_tramo. Si un tramo aparece en varios viales en source,
--      se elige una fila representante por: clase ASC NULLS LAST (heuristica:
--      codigo menor = jerarquia mayor), imported_at DESC, source_fid ASC.
--   2. Sentinelas -997 y -998 mapeadas a NULL en los codigos numericos.
--   3. Descripciones (clased, titulard, etc.) recortadas y vaciadas a NULL si
--      quedan en blanco.
--   4. ncarriles parseado a entero; NULL si no es entero valido en origen.
--   5. Geometria forzada a 2D, MakeValid y empaquetada como MultiLineString
--      EPSG:4326; se descartan filas con geometria nula, invalida o no lineal.

TRUNCATE TABLE core.road_segment RESTART IDENTITY;

INSERT INTO core.road_segment (
    dataset_id,
    id_tramo,
    inspire_id,
    id_vial,
    source_fid,
    source_objectid,
    ingest_id,
    territory_code,
    territory_name,
    clase,
    clase_code,
    tipo,
    tipo_code,
    nombre,
    nombre_alt,
    codigo,
    dgc_via,
    titular,
    titular_code,
    sentido,
    sentido_code,
    acceso,
    acceso_code,
    estado_fisico,
    estado_fisico_code,
    firme,
    firme_code,
    n_carriles,
    orden,
    tipovehic,
    imported_at,
    geom
)
WITH cleaned AS (
    SELECT
        s.source_fid,
        s.source_objectid,
        s.ingest_id,
        s.territory_code,
        s.territory_name,
        s.id_tramo,
        s.id_vial,
        NULLIF(btrim(s.clased), '') AS clase,
        CASE WHEN s.clase IN (-997, -998) THEN NULL ELSE s.clase END AS clase_code,
        NULLIF(btrim(s.tipo_tramd), '') AS tipo,
        CASE WHEN s.tipo_tramo IN (-997, -998) THEN NULL ELSE s.tipo_tramo END AS tipo_code,
        NULLIF(btrim(s.nombre), '') AS nombre,
        NULLIF(btrim(s.nombre_alt), '') AS nombre_alt,
        NULLIF(btrim(s.codigo), '') AS codigo,
        NULLIF(btrim(s.dgc_via), '') AS dgc_via,
        NULLIF(btrim(s.titulard), '') AS titular,
        CASE WHEN s.titular IN (-997, -998) THEN NULL ELSE s.titular END AS titular_code,
        NULLIF(btrim(s.sentidod), '') AS sentido,
        CASE WHEN s.sentido IN (-997, -998) THEN NULL ELSE s.sentido END AS sentido_code,
        NULLIF(btrim(s.accesod), '') AS acceso,
        CASE WHEN s.acceso IN (-997, -998) THEN NULL ELSE s.acceso END AS acceso_code,
        NULLIF(btrim(s.estadofisd), '') AS estado_fisico,
        CASE WHEN s.estadofis IN (-997, -998) THEN NULL ELSE s.estadofis END AS estado_fisico_code,
        NULLIF(btrim(s.firmed), '') AS firme,
        CASE WHEN s.firme IN (-997, -998) THEN NULL ELSE s.firme END AS firme_code,
        CASE
            WHEN s.ncarriles IS NULL THEN NULL
            WHEN btrim(s.ncarriles) ~ '^-?\d+$' THEN
                CASE
                    WHEN btrim(s.ncarriles)::integer IN (-997, -998) THEN NULL
                    ELSE btrim(s.ncarriles)::integer
                END
            ELSE NULL
        END AS n_carriles,
        NULLIF(btrim(s.ordend), '') AS orden,
        NULLIF(btrim(s.tipovehicd), '') AS tipovehic,
        s.imported_at,
        ST_CollectionExtract(ST_MakeValid(ST_Force2D(s.geom)), 2) AS geom_2d
    FROM source.igr_rt_tramo_vial s
    WHERE s.geom IS NOT NULL
      AND s.id_tramo IS NOT NULL
),
filtered AS (
    SELECT *
    FROM cleaned
    WHERE geom_2d IS NOT NULL
      AND NOT ST_IsEmpty(geom_2d)
      AND ST_GeometryType(geom_2d) IN ('ST_MultiLineString', 'ST_LineString')
),
ranked AS (
    SELECT
        f.*,
        ROW_NUMBER() OVER (
            PARTITION BY f.id_tramo
            ORDER BY
                f.clase_code ASC NULLS LAST,
                f.imported_at DESC,
                f.source_fid ASC
        ) AS rn
    FROM filtered f
)
SELECT
    'igr_rt_road_segment'::text AS dataset_id,
    id_tramo,
    'VIAL_TR' || id_tramo::text AS inspire_id,
    id_vial,
    source_fid,
    source_objectid,
    ingest_id,
    territory_code,
    territory_name,
    clase,
    clase_code,
    tipo,
    tipo_code,
    nombre,
    nombre_alt,
    codigo,
    dgc_via,
    titular,
    titular_code,
    sentido,
    sentido_code,
    acceso,
    acceso_code,
    estado_fisico,
    estado_fisico_code,
    firme,
    firme_code,
    n_carriles,
    orden,
    tipovehic,
    imported_at,
    CASE
        WHEN ST_GeometryType(geom_2d) = 'ST_LineString' THEN ST_Multi(geom_2d)
        ELSE geom_2d
    END AS geom
FROM ranked
WHERE rn = 1;

ANALYZE core.road_segment;
