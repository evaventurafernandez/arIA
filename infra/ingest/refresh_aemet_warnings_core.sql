\set ON_ERROR_STOP on

BEGIN;

CREATE SCHEMA IF NOT EXISTS ingest;

CREATE TABLE IF NOT EXISTS ingest.aemet_warning_refresh_key (
    cap_identifier text NOT NULL,
    language text NOT NULL,
    area_code text NOT NULL,
    queued_at timestamptz NOT NULL DEFAULT now(),
    reason text NOT NULL DEFAULT 'import',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (cap_identifier, language, area_code)
);

CREATE TABLE IF NOT EXISTS ingest.aemet_warning_refresh_date (
    valid_date date PRIMARY KEY,
    queued_at timestamptz NOT NULL DEFAULT now(),
    reason text NOT NULL DEFAULT 'core-refresh',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS aemet_warning_refresh_key_queued_at_idx
    ON ingest.aemet_warning_refresh_key (queued_at);
CREATE INDEX IF NOT EXISTS aemet_warning_refresh_date_queued_at_idx
    ON ingest.aemet_warning_refresh_date (queued_at);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ingest.aemet_warning_refresh_key)
       AND NOT EXISTS (SELECT 1 FROM core.aemet_max_temperature_warning) THEN
        INSERT INTO ingest.aemet_warning_refresh_key (
            cap_identifier,
            language,
            area_code,
            reason
        )
        SELECT DISTINCT
            src.cap_identifier,
            src.language,
            src.area_code,
            'bootstrap-core-empty'
        FROM source.aemet_warning_cap_record AS src
        WHERE src.phenomenon_code = 'AT'
          AND src.language = 'es-ES'
          AND src.geom IS NOT NULL
          AND src.area_code IS NOT NULL
        ON CONFLICT (cap_identifier, language, area_code) DO NOTHING;
    END IF;
END $$;

SELECT (count(*) > 0) AS has_refresh_keys
FROM ingest.aemet_warning_refresh_key \gset

\if :has_refresh_keys

SELECT count(*) AS pending_refresh_keys
FROM ingest.aemet_warning_refresh_key;

CREATE TEMP TABLE _aemet_refresh_key
ON COMMIT DROP AS
SELECT
    cap_identifier,
    language,
    area_code
FROM ingest.aemet_warning_refresh_key;

CREATE TEMP TABLE _aemet_old_valid_date
ON COMMIT DROP AS
SELECT DISTINCT
    gs.valid_date::date AS valid_date
FROM core.aemet_max_temperature_warning AS w
JOIN _aemet_refresh_key AS k
    ON k.cap_identifier = w.cap_identifier
   AND k.language = w.language
   AND k.area_code = w.area_code
CROSS JOIN LATERAL generate_series(
    (w.onset_at AT TIME ZONE 'Europe/Madrid')::date,
    greatest(
        (w.onset_at AT TIME ZONE 'Europe/Madrid')::date,
        ((w.expires_at - interval '1 second') AT TIME ZONE 'Europe/Madrid')::date
    ),
    interval '1 day'
) AS gs(valid_date);

CREATE TEMP TABLE _aemet_canonical_source
ON COMMIT DROP AS
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
    JOIN _aemet_refresh_key AS k
        ON k.cap_identifier = src.cap_identifier
       AND k.language = src.language
       AND k.area_code = src.area_code
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
    ) AS metadata_json
FROM ranked_source
WHERE source_rank = 1;

CREATE TEMP TABLE _aemet_new_valid_date
ON COMMIT DROP AS
SELECT DISTINCT
    gs.valid_date::date AS valid_date
FROM _aemet_canonical_source AS w
CROSS JOIN LATERAL generate_series(
    (w.onset_at AT TIME ZONE 'Europe/Madrid')::date,
    greatest(
        (w.onset_at AT TIME ZONE 'Europe/Madrid')::date,
        ((w.expires_at - interval '1 second') AT TIME ZONE 'Europe/Madrid')::date
    ),
    interval '1 day'
) AS gs(valid_date);

WITH deleted AS (
    DELETE FROM core.aemet_max_temperature_warning AS w
    USING _aemet_refresh_key AS k
    WHERE k.cap_identifier = w.cap_identifier
      AND k.language = w.language
      AND k.area_code = w.area_code
    RETURNING 1
)
SELECT count(*) AS deleted_core_rows
FROM deleted;

WITH inserted AS (
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
        now()
    FROM _aemet_canonical_source
    ON CONFLICT (cap_identifier, language, area_code) DO UPDATE
    SET
        sent_at = EXCLUDED.sent_at,
        cap_status = EXCLUDED.cap_status,
        cap_msg_type = EXCLUDED.cap_msg_type,
        event_code = EXCLUDED.event_code,
        phenomenon_code = EXCLUDED.phenomenon_code,
        phenomenon_label = EXCLUDED.phenomenon_label,
        urgency = EXCLUDED.urgency,
        severity = EXCLUDED.severity,
        certainty = EXCLUDED.certainty,
        effective_at = EXCLUDED.effective_at,
        onset_at = EXCLUDED.onset_at,
        expires_at = EXCLUDED.expires_at,
        level_code = EXCLUDED.level_code,
        level_label = EXCLUDED.level_label,
        level_rank = EXCLUDED.level_rank,
        is_warning = EXCLUDED.is_warning,
        parameter_code = EXCLUDED.parameter_code,
        parameter_label = EXCLUDED.parameter_label,
        parameter_value = EXCLUDED.parameter_value,
        temperature_max_c = EXCLUDED.temperature_max_c,
        probability = EXCLUDED.probability,
        area_name = EXCLUDED.area_name,
        headline = EXCLUDED.headline,
        description = EXCLUDED.description,
        instruction = EXCLUDED.instruction,
        representative_source_record_id = EXCLUDED.representative_source_record_id,
        geom = EXCLUDED.geom,
        geom_webmercator = EXCLUDED.geom_webmercator,
        metadata_json = EXCLUDED.metadata_json,
        canonicalized_at = now()
    RETURNING 1
)
SELECT count(*) AS inserted_core_rows
FROM inserted;

INSERT INTO ingest.aemet_warning_refresh_date (
    valid_date,
    reason,
    metadata_json
)
SELECT DISTINCT
    valid_date,
    'core-refresh',
    '{}'::jsonb
FROM (
    SELECT valid_date FROM _aemet_old_valid_date
    UNION
    SELECT valid_date FROM _aemet_new_valid_date
) AS affected_dates
ON CONFLICT (valid_date) DO UPDATE
SET
    queued_at = now(),
    reason = EXCLUDED.reason;

WITH consumed AS (
    DELETE FROM ingest.aemet_warning_refresh_key AS q
    USING _aemet_refresh_key AS k
    WHERE k.cap_identifier = q.cap_identifier
      AND k.language = q.language
      AND k.area_code = q.area_code
    RETURNING 1
)
SELECT count(*) AS consumed_refresh_keys
FROM consumed;

ANALYZE core.aemet_max_temperature_warning;

\else

SELECT 0 AS pending_refresh_keys;

\endif

COMMIT;
