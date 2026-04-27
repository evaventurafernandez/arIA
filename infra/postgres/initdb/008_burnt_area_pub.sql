-- Fase 10: publicacion derivada para disponibilidad y estadisticas de burnt area.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS pub;

CREATE OR REPLACE VIEW pub.burnt_area_daily_file_catalog AS
SELECT
    daily_file_id,
    dataset_id,
    dataset_version,
    delivery_format,
    nominal_date,
    source_item_id,
    source_product_name,
    product_version,
    file_size_bytes,
    remote_uri,
    publication_status,
    local_file_path IS NOT NULL AS has_local_file,
    local_spain_cog_path IS NOT NULL AS has_local_spain_cog,
    local_tiles_path IS NOT NULL AS has_local_tiles,
    canonicalized_at
FROM core.burnt_area_daily_file;

CREATE TABLE IF NOT EXISTS pub.burnt_area_daily_stat (
    stat_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_version text NOT NULL
        CHECK (dataset_version IN ('v3', 'v4')),
    delivery_format text NOT NULL
        CHECK (delivery_format IN ('cog', 'nc')),
    nominal_date date NOT NULL,
    stat_scope text NOT NULL
        CHECK (stat_scope IN ('country', 'autonomous_community', 'province', 'municipality')),
    area_code text NOT NULL,
    area_label text NOT NULL,
    burned_area_ha double precision,
    burned_pixel_count bigint,
    burned_fraction_sum double precision,
    tiles_generated boolean NOT NULL DEFAULT false,
    stats_generated_at timestamptz NOT NULL DEFAULT now(),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (dataset_version, delivery_format, nominal_date, stat_scope, area_code)
);

CREATE INDEX IF NOT EXISTS burnt_area_daily_stat_nominal_date_idx
    ON pub.burnt_area_daily_stat (nominal_date);
CREATE INDEX IF NOT EXISTS burnt_area_daily_stat_scope_idx
    ON pub.burnt_area_daily_stat (stat_scope);
CREATE INDEX IF NOT EXISTS burnt_area_daily_stat_dataset_version_idx
    ON pub.burnt_area_daily_stat (dataset_version);

COMMENT ON VIEW pub.burnt_area_daily_file_catalog IS 'Publicacion ligera de disponibilidad diaria de burnt area para APIs de timeline, catalogo y control operativo';
COMMENT ON TABLE pub.burnt_area_daily_stat IS 'Publicacion derivada de estadisticas diarias de area quemada para Espana y sus divisiones administrativas';
COMMENT ON COLUMN pub.burnt_area_daily_stat.dataset_version IS 'Version mayor del producto CLMS usada para la estadistica';
COMMENT ON COLUMN pub.burnt_area_daily_stat.delivery_format IS 'Formato base del asset del que salio la estadistica';
COMMENT ON COLUMN pub.burnt_area_daily_stat.nominal_date IS 'Dia nominal de la estadistica diaria';
COMMENT ON COLUMN pub.burnt_area_daily_stat.stat_scope IS 'Nivel territorial de la estadistica publicada';
COMMENT ON COLUMN pub.burnt_area_daily_stat.area_code IS 'Codigo territorial estable del ambito de agregacion';
COMMENT ON COLUMN pub.burnt_area_daily_stat.area_label IS 'Etiqueta legible del ambito de agregacion';
COMMENT ON COLUMN pub.burnt_area_daily_stat.burned_area_ha IS 'Area quemada diaria agregada en hectareas';
COMMENT ON COLUMN pub.burnt_area_daily_stat.burned_pixel_count IS 'Conteo de pixeles quemados efectivos usados en la agregacion';
COMMENT ON COLUMN pub.burnt_area_daily_stat.burned_fraction_sum IS 'Suma de BF sobre el ambito territorial; util para auditoria y recalculo';
COMMENT ON COLUMN pub.burnt_area_daily_stat.tiles_generated IS 'Indica si para ese dia existia publicacion raster local al calcular la estadistica';
COMMENT ON COLUMN pub.burnt_area_daily_stat.metadata_json IS 'Metadatos tecnicos de la agregacion diaria';
