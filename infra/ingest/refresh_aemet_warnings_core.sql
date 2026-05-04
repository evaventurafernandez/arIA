DELETE FROM core.aemet_max_temperature_warning
WHERE product_id = 'avisos_cap_archive'
  AND phenomenon_code = 'AT';

INSERT INTO core.aemet_max_temperature_warning (
    cap_identifier,
    sent_at,
    cap_status,
    cap_msg_type,
    language,
    event_code,
    phenomenon_code,
    phenomenon_label,
    urgency,
    severity,
    certainty,
    effective_at,
    onset_at,
    expires_at,
    level_code,
    level_label,
    level_rank,
    is_warning,
    parameter_code,
    parameter_label,
    parameter_value,
    temperature_max_c,
    probability,
    area_name,
    area_code,
    headline,
    description,
    instruction,
    representative_source_record_id,
    geom,
    geom_webmercator,
    metadata_json,
    canonicalized_at
)
WITH ranked_source AS (
    SELECT
        src.*,
        d.source_download_id AS download_source_download_id,
        d.source_file_path,
        d.request_elaboration_from,
        d.request_elaboration_to,
        row_number() OVER (
            PARTITION BY src.cap_identifier, src.language, src.area_code
            ORDER BY d.request_elaboration_to DESC, src.source_record_id DESC
        ) AS source_rank,
        count(*) OVER (
            PARTITION BY src.cap_identifier, src.language, src.area_code
        ) AS duplicate_source_count
    FROM source.aemet_warning_cap_record AS src
    JOIN source.aemet_warning_download_file AS d
        ON d.source_download_id = src.source_download_id
    WHERE src.phenomenon_code = 'AT'
      AND src.language = 'es-ES'
      AND src.geom IS NOT NULL
      AND src.area_code IS NOT NULL
)
SELECT
    cap_identifier,
    sent_at,
    cap_status,
    cap_msg_type,
    language,
    event_code,
    phenomenon_code,
    phenomenon_label,
    urgency,
    severity,
    certainty,
    effective_at,
    onset_at,
    expires_at,
    level_code,
    level_label,
    CASE level_label
        WHEN 'Rojo' THEN 3
        WHEN 'Naranja' THEN 2
        WHEN 'Amarillo' THEN 1
        ELSE 0
    END AS level_rank,
    level_label IN ('Amarillo', 'Naranja', 'Rojo') AS is_warning,
    parameter_code,
    parameter_label,
    parameter_value,
    temperature_max_c,
    probability,
    area_name,
    area_code,
    headline,
    description,
    instruction,
    source_record_id AS representative_source_record_id,
    ST_CollectionExtract(ST_MakeValid(geom), 3)::geometry(Geometry, 4326) AS geom,
    ST_Transform(ST_CollectionExtract(ST_MakeValid(geom), 3), 3857)::geometry(Geometry, 3857) AS geom_webmercator,
    metadata_json || jsonb_build_object(
        'canonicalized_from_source', true,
        'duplicate_source_count', duplicate_source_count,
        'source_download_id', download_source_download_id,
        'source_file_path', source_file_path,
        'request_elaboration_from', request_elaboration_from,
        'request_elaboration_to', request_elaboration_to
    ) AS metadata_json,
    now() AS canonicalized_at
FROM ranked_source
WHERE source_rank = 1;
