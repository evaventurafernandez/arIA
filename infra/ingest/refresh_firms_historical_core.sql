DELETE FROM core.firms_hotspot
WHERE dataset_type = 'SP';

INSERT INTO core.firms_hotspot (
    dataset_type,
    firms_source,
    satellite,
    instrument,
    confidence,
    version,
    daynight,
    latitude,
    longitude,
    bright_ti4,
    scan,
    track,
    acq_date,
    acq_time,
    observed_at,
    bright_ti5,
    frp,
    bbox_regions,
    source_download_count,
    source_observation_count,
    representative_source_observation_id,
    geom,
    metadata_json,
    canonicalized_at
)
WITH canonical_source AS (
    SELECT
        src.dataset_type,
        src.firms_source,
        src.satellite,
        max(src.instrument) AS instrument,
        max(src.confidence) AS confidence,
        max(src.version) AS version,
        max(src.daynight) AS daynight,
        src.latitude,
        src.longitude,
        max(src.bright_ti4) AS bright_ti4,
        max(src.scan) AS scan,
        max(src.track) AS track,
        src.acq_date,
        src.acq_time,
        max(src.observed_at) AS observed_at,
        max(src.bright_ti5) AS bright_ti5,
        max(src.frp) AS frp,
        ARRAY_AGG(DISTINCT src.bbox_region ORDER BY src.bbox_region) AS bbox_regions,
        count(DISTINCT src.source_download_id)::integer AS source_download_count,
        count(*)::integer AS source_observation_count,
        min(src.source_observation_id) AS representative_source_observation_id,
        ST_SetSRID(ST_MakePoint(src.longitude, src.latitude), 4326) AS geom,
        jsonb_build_object(
            'bbox_regions', ARRAY_AGG(DISTINCT src.bbox_region ORDER BY src.bbox_region),
            'source_download_ids', ARRAY_AGG(DISTINCT src.source_download_id ORDER BY src.source_download_id),
            'source_observation_count', count(*),
            'canonicalized_from_source', true,
            'spain_boundary', 'data/boundaries/spain_nuts_2024_01m.geojson'
        ) AS metadata_json
    FROM source.firms_hotspot_observation AS src
    WHERE src.in_spain_nuts
    GROUP BY
        src.dataset_type,
        src.firms_source,
        src.satellite,
        src.latitude,
        src.longitude,
        src.acq_date,
        src.acq_time
)
SELECT
    dataset_type,
    firms_source,
    satellite,
    instrument,
    confidence,
    version,
    daynight,
    latitude,
    longitude,
    bright_ti4,
    scan,
    track,
    acq_date,
    acq_time,
    observed_at,
    bright_ti5,
    frp,
    bbox_regions,
    source_download_count,
    source_observation_count,
    representative_source_observation_id,
    geom,
    metadata_json,
    now()
FROM canonical_source;
