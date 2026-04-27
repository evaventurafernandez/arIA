-- Fase 8: estructuras source para el catalogo diario de burnt area.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS ingest;
CREATE SCHEMA IF NOT EXISTS source;

CREATE TABLE IF NOT EXISTS source.burnt_area_catalog_item (
    source_catalog_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id text NOT NULL DEFAULT 'burnt_area_global_300m_daily_catalog',
    product_family text NOT NULL DEFAULT 'ba_global_300m_daily'
        CHECK (product_family = 'ba_global_300m_daily'),
    dataset_version text NOT NULL
        CHECK (dataset_version IN ('v3', 'v4')),
    delivery_format text NOT NULL
        CHECK (delivery_format IN ('cog', 'nc')),
    product_version text NOT NULL,
    catalog_entry_path text NOT NULL,
    catalog_zip_path text NOT NULL,
    source_item_id text NOT NULL,
    product_name text NOT NULL,
    content_length_bytes bigint NOT NULL CHECK (content_length_bytes > 0),
    nominal_date date NOT NULL,
    content_start_at timestamptz,
    content_end_at timestamptz,
    catalog_ingested_at timestamptz,
    catalog_modified_at timestamptz,
    checksum_algorithm text,
    checksum_value text,
    remote_uri text NOT NULL,
    bbox geometry(Polygon, 4326),
    ingest_id bigint NOT NULL REFERENCES ingest.ingest_file(ingest_id),
    imported_at timestamptz NOT NULL DEFAULT now(),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (dataset_version, delivery_format, nominal_date, product_name)
);

CREATE INDEX IF NOT EXISTS burnt_area_catalog_item_nominal_date_idx
    ON source.burnt_area_catalog_item (nominal_date);
CREATE INDEX IF NOT EXISTS burnt_area_catalog_item_dataset_version_idx
    ON source.burnt_area_catalog_item (dataset_version);
CREATE INDEX IF NOT EXISTS burnt_area_catalog_item_delivery_format_idx
    ON source.burnt_area_catalog_item (delivery_format);
CREATE INDEX IF NOT EXISTS burnt_area_catalog_item_ingest_id_idx
    ON source.burnt_area_catalog_item (ingest_id);
CREATE INDEX IF NOT EXISTS burnt_area_catalog_item_bbox_gix
    ON source.burnt_area_catalog_item USING GIST (bbox);

COMMENT ON TABLE source.burnt_area_catalog_item IS 'Catalogo diario Copernicus CLMS de burnt area cercano al origen, una fila por asset listado en los CSV de COG/NetCDF';
COMMENT ON COLUMN source.burnt_area_catalog_item.dataset_id IS 'Identificador logico estable del catalogo bruto de burnt area';
COMMENT ON COLUMN source.burnt_area_catalog_item.product_family IS 'Familia de producto CLMS; en esta PoC se limita a ba_global_300m_daily';
COMMENT ON COLUMN source.burnt_area_catalog_item.dataset_version IS 'Version mayor del producto diario, por ejemplo v3 o v4';
COMMENT ON COLUMN source.burnt_area_catalog_item.delivery_format IS 'Formato publicado por Copernicus, COG o NetCDF';
COMMENT ON COLUMN source.burnt_area_catalog_item.product_version IS 'Version completa embebida en el nombre de producto, por ejemplo V4.0.1';
COMMENT ON COLUMN source.burnt_area_catalog_item.catalog_entry_path IS 'Ruta interna del CSV dentro de all.zip';
COMMENT ON COLUMN source.burnt_area_catalog_item.catalog_zip_path IS 'Ruta fisica del ZIP catalogo usado para la importacion';
COMMENT ON COLUMN source.burnt_area_catalog_item.source_item_id IS 'UUID original del item en el catalogo Copernicus';
COMMENT ON COLUMN source.burnt_area_catalog_item.product_name IS 'Nombre completo del asset remoto tal y como aparece en el catalogo';
COMMENT ON COLUMN source.burnt_area_catalog_item.content_length_bytes IS 'Tamano del asset remoto en bytes';
COMMENT ON COLUMN source.burnt_area_catalog_item.nominal_date IS 'Dia nominal del producto diario';
COMMENT ON COLUMN source.burnt_area_catalog_item.content_start_at IS 'Inicio de validez temporal del asset segun el catalogo';
COMMENT ON COLUMN source.burnt_area_catalog_item.content_end_at IS 'Fin de validez temporal del asset segun el catalogo';
COMMENT ON COLUMN source.burnt_area_catalog_item.catalog_ingested_at IS 'Timestamp de ingestiondate informado por Copernicus Data Space';
COMMENT ON COLUMN source.burnt_area_catalog_item.catalog_modified_at IS 'Timestamp modificationdate informado por Copernicus Data Space';
COMMENT ON COLUMN source.burnt_area_catalog_item.checksum_algorithm IS 'Algoritmo de checksum proporcionado por el catalogo';
COMMENT ON COLUMN source.burnt_area_catalog_item.checksum_value IS 'Checksum proporcionado por el catalogo';
COMMENT ON COLUMN source.burnt_area_catalog_item.remote_uri IS 'URI remota s3://eodata/... del asset diario';
COMMENT ON COLUMN source.burnt_area_catalog_item.bbox IS 'Huella espacial declarada en el catalogo, almacenada en EPSG:4326';
COMMENT ON COLUMN source.burnt_area_catalog_item.ingest_id IS 'Referencia a ingest.ingest_file para trazabilidad de la carga del catalogo';
COMMENT ON COLUMN source.burnt_area_catalog_item.metadata_json IS 'Metadatos tecnicos adicionales de la fila de catalogo';
