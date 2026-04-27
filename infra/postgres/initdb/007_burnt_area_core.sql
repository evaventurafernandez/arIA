-- Fase 9: estructuras core para la capa temporal diaria de burnt area.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE IF NOT EXISTS core.burnt_area_daily_file (
    daily_file_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id text NOT NULL DEFAULT 'burnt_area_global_300m_daily',
    dataset_version text NOT NULL
        CHECK (dataset_version IN ('v3', 'v4')),
    delivery_format text NOT NULL
        CHECK (delivery_format IN ('cog', 'nc')),
    nominal_date date NOT NULL,
    source_catalog_id bigint NOT NULL REFERENCES source.burnt_area_catalog_item(source_catalog_id),
    source_item_id text NOT NULL,
    source_product_name text NOT NULL,
    product_version text NOT NULL,
    content_start_at timestamptz,
    content_end_at timestamptz,
    catalog_ingested_at timestamptz,
    catalog_modified_at timestamptz,
    file_size_bytes bigint NOT NULL CHECK (file_size_bytes > 0),
    checksum_algorithm text,
    checksum_value text,
    remote_uri text NOT NULL,
    coverage_bbox geometry(Polygon, 4326),
    local_file_path text,
    local_spain_cog_path text,
    local_tiles_path text,
    publication_status text NOT NULL DEFAULT 'cataloged'
        CHECK (publication_status IN ('cataloged', 'downloaded', 'cropped', 'tiled', 'published', 'failed')),
    publication_notes text,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    canonicalized_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (dataset_version, delivery_format, nominal_date)
);

CREATE INDEX IF NOT EXISTS burnt_area_daily_file_nominal_date_idx
    ON core.burnt_area_daily_file (nominal_date);
CREATE INDEX IF NOT EXISTS burnt_area_daily_file_dataset_version_idx
    ON core.burnt_area_daily_file (dataset_version);
CREATE INDEX IF NOT EXISTS burnt_area_daily_file_delivery_format_idx
    ON core.burnt_area_daily_file (delivery_format);
CREATE INDEX IF NOT EXISTS burnt_area_daily_file_status_idx
    ON core.burnt_area_daily_file (publication_status);
CREATE INDEX IF NOT EXISTS burnt_area_daily_file_bbox_gix
    ON core.burnt_area_daily_file USING GIST (coverage_bbox);

COMMENT ON TABLE core.burnt_area_daily_file IS 'Nivel core canonico de burnt area diario: una fila por dia, version y formato con trazabilidad al catalogo y estado local de publicacion';
COMMENT ON COLUMN core.burnt_area_daily_file.dataset_id IS 'Identificador logico estable del producto diario de burnt area';
COMMENT ON COLUMN core.burnt_area_daily_file.dataset_version IS 'Version mayor del producto diario que se publica en la capa temporal';
COMMENT ON COLUMN core.burnt_area_daily_file.delivery_format IS 'Formato preferido de trabajo para cada dia, COG o NetCDF';
COMMENT ON COLUMN core.burnt_area_daily_file.nominal_date IS 'Dia nominal del raster diario';
COMMENT ON COLUMN core.burnt_area_daily_file.source_catalog_id IS 'Fila source concreta de la que procede la version core elegida';
COMMENT ON COLUMN core.burnt_area_daily_file.source_item_id IS 'UUID original del item remoto';
COMMENT ON COLUMN core.burnt_area_daily_file.source_product_name IS 'Nombre completo del asset diario segun Copernicus';
COMMENT ON COLUMN core.burnt_area_daily_file.product_version IS 'Version completa del asset publicada por Copernicus';
COMMENT ON COLUMN core.burnt_area_daily_file.content_start_at IS 'Inicio de validez temporal del asset';
COMMENT ON COLUMN core.burnt_area_daily_file.content_end_at IS 'Fin de validez temporal del asset';
COMMENT ON COLUMN core.burnt_area_daily_file.catalog_ingested_at IS 'ingestiondate del catalogo original';
COMMENT ON COLUMN core.burnt_area_daily_file.catalog_modified_at IS 'modificationdate del catalogo original';
COMMENT ON COLUMN core.burnt_area_daily_file.file_size_bytes IS 'Tamano bruto del asset remoto';
COMMENT ON COLUMN core.burnt_area_daily_file.checksum_algorithm IS 'Algoritmo de checksum asociado al asset remoto';
COMMENT ON COLUMN core.burnt_area_daily_file.checksum_value IS 'Checksum asociado al asset remoto';
COMMENT ON COLUMN core.burnt_area_daily_file.remote_uri IS 'URI remota s3://eodata/... del asset diario';
COMMENT ON COLUMN core.burnt_area_daily_file.coverage_bbox IS 'Huella global declarada para el asset remoto';
COMMENT ON COLUMN core.burnt_area_daily_file.local_file_path IS 'Ruta local del asset bruto descargado si ya existe';
COMMENT ON COLUMN core.burnt_area_daily_file.local_spain_cog_path IS 'Ruta local del recorte COG a Espana usado como fuente raster operativa';
COMMENT ON COLUMN core.burnt_area_daily_file.local_tiles_path IS 'Directorio raiz de teselas PNG generadas para el dia';
COMMENT ON COLUMN core.burnt_area_daily_file.publication_status IS 'Estado operativo del asset dentro del pipeline local';
COMMENT ON COLUMN core.burnt_area_daily_file.publication_notes IS 'Notas de proceso o incidencia del pipeline local';
COMMENT ON COLUMN core.burnt_area_daily_file.metadata_json IS 'Metadatos auxiliares para el pipeline raster';
COMMENT ON COLUMN core.burnt_area_daily_file.canonicalized_at IS 'Momento de consolidacion del catalogo source al core canonico';
