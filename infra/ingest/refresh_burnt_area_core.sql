INSERT INTO core.burnt_area_daily_file (
    dataset_version,
    delivery_format,
    nominal_date,
    source_catalog_id,
    source_item_id,
    source_product_name,
    product_version,
    content_start_at,
    content_end_at,
    catalog_ingested_at,
    catalog_modified_at,
    file_size_bytes,
    checksum_algorithm,
    checksum_value,
    remote_uri,
    coverage_bbox,
    metadata_json,
    canonicalized_at
)
SELECT DISTINCT ON (src.dataset_version, src.delivery_format, src.nominal_date)
    src.dataset_version,
    src.delivery_format,
    src.nominal_date,
    src.source_catalog_id,
    src.source_item_id,
    src.product_name,
    src.product_version,
    src.content_start_at,
    src.content_end_at,
    src.catalog_ingested_at,
    src.catalog_modified_at,
    src.content_length_bytes,
    src.checksum_algorithm,
    src.checksum_value,
    src.remote_uri,
    src.bbox,
    src.metadata_json,
    now()
FROM source.burnt_area_catalog_item AS src
ORDER BY
    src.dataset_version,
    src.delivery_format,
    src.nominal_date,
    COALESCE(src.catalog_modified_at, src.catalog_ingested_at, src.imported_at) DESC,
    src.source_catalog_id DESC
ON CONFLICT (dataset_version, delivery_format, nominal_date) DO UPDATE
SET source_catalog_id = EXCLUDED.source_catalog_id,
    source_item_id = EXCLUDED.source_item_id,
    source_product_name = EXCLUDED.source_product_name,
    product_version = EXCLUDED.product_version,
    content_start_at = EXCLUDED.content_start_at,
    content_end_at = EXCLUDED.content_end_at,
    catalog_ingested_at = EXCLUDED.catalog_ingested_at,
    catalog_modified_at = EXCLUDED.catalog_modified_at,
    file_size_bytes = EXCLUDED.file_size_bytes,
    checksum_algorithm = EXCLUDED.checksum_algorithm,
    checksum_value = EXCLUDED.checksum_value,
    remote_uri = EXCLUDED.remote_uri,
    coverage_bbox = EXCLUDED.coverage_bbox,
    metadata_json = EXCLUDED.metadata_json,
    canonicalized_at = now(),
    local_file_path = COALESCE(core.burnt_area_daily_file.local_file_path, EXCLUDED.local_file_path),
    local_spain_cog_path = COALESCE(core.burnt_area_daily_file.local_spain_cog_path, EXCLUDED.local_spain_cog_path),
    local_tiles_path = COALESCE(core.burnt_area_daily_file.local_tiles_path, EXCLUDED.local_tiles_path),
    publication_status = CASE
        WHEN core.burnt_area_daily_file.publication_status <> 'cataloged'
            THEN core.burnt_area_daily_file.publication_status
        ELSE EXCLUDED.publication_status
    END,
    publication_notes = COALESCE(core.burnt_area_daily_file.publication_notes, EXCLUDED.publication_notes);
