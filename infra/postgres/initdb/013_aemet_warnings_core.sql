-- Fase 15: estructuras core para avisos AEMET de temperaturas máximas.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE IF NOT EXISTS core.aemet_max_temperature_warning (
    warning_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id text NOT NULL DEFAULT 'aemet_max_temperature_warning_historical',
    source_system text NOT NULL DEFAULT 'aemet'
        CHECK (source_system = 'aemet'),
    product_id text NOT NULL DEFAULT 'avisos_cap_archive'
        CHECK (product_id = 'avisos_cap_archive'),
    cap_identifier text NOT NULL,
    sent_at timestamptz,
    cap_status text,
    cap_msg_type text,
    language text NOT NULL DEFAULT 'es-ES',
    event_code text NOT NULL DEFAULT 'AT;Temperaturas máximas',
    phenomenon_code text NOT NULL DEFAULT 'AT'
        CHECK (phenomenon_code = 'AT'),
    phenomenon_label text NOT NULL DEFAULT 'Temperaturas máximas',
    urgency text,
    severity text,
    certainty text,
    effective_at timestamptz,
    onset_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    level_code text NOT NULL,
    level_label text NOT NULL
        CHECK (level_label IN ('Verde', 'Amarillo', 'Naranja', 'Rojo')),
    level_rank integer NOT NULL
        CHECK (level_rank BETWEEN 0 AND 3),
    is_warning boolean NOT NULL DEFAULT false,
    parameter_code text,
    parameter_label text,
    parameter_value text,
    temperature_max_c double precision,
    probability text,
    area_name text NOT NULL,
    area_code text NOT NULL,
    headline text,
    description text,
    instruction text,
    representative_source_record_id bigint NOT NULL REFERENCES source.aemet_warning_cap_record(source_record_id),
    geom geometry(Geometry, 4326) NOT NULL,
    geom_webmercator geometry(Geometry, 3857) NOT NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    canonicalized_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (cap_identifier, language, area_code)
);

CREATE INDEX IF NOT EXISTS aemet_max_temperature_warning_sent_at_idx
    ON core.aemet_max_temperature_warning (sent_at);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_warning_onset_at_idx
    ON core.aemet_max_temperature_warning (onset_at);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_warning_expires_at_idx
    ON core.aemet_max_temperature_warning (expires_at);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_warning_level_label_idx
    ON core.aemet_max_temperature_warning (level_label);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_warning_is_warning_idx
    ON core.aemet_max_temperature_warning (is_warning);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_warning_area_code_idx
    ON core.aemet_max_temperature_warning (area_code);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_warning_temp_idx
    ON core.aemet_max_temperature_warning (temperature_max_c);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_warning_representative_source_record_id_idx
    ON core.aemet_max_temperature_warning (representative_source_record_id);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_warning_geom_gix
    ON core.aemet_max_temperature_warning USING GIST (geom);
CREATE INDEX IF NOT EXISTS aemet_max_temperature_warning_geom_webmercator_gix
    ON core.aemet_max_temperature_warning USING GIST (geom_webmercator);

COMMENT ON TABLE core.aemet_max_temperature_warning IS 'Avisos AEMET de temperaturas máximas deduplicados desde CAP histórico, con geometría lista para publicación diaria.';
COMMENT ON COLUMN core.aemet_max_temperature_warning.level_rank IS 'Jerarquía operativa de nivel: Verde=0, Amarillo=1, Naranja=2, Rojo=3.';
COMMENT ON COLUMN core.aemet_max_temperature_warning.is_warning IS 'True para niveles adversos publicados en el visor histórico: Amarillo, Naranja o Rojo.';
COMMENT ON COLUMN core.aemet_max_temperature_warning.temperature_max_c IS 'Umbral numérico de temperatura máxima en grados Celsius cuando el CAP lo informa.';
COMMENT ON COLUMN core.aemet_max_temperature_warning.geom_webmercator IS 'Geometría reproyectada a EPSG:3857 para servir teselas vectoriales MVT sin reproyección por petición.';
