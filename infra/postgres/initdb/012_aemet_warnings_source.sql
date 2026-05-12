-- Fase 14: estructuras source para el histórico de avisos AEMET CAP.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS ingest;
CREATE SCHEMA IF NOT EXISTS source;

CREATE TABLE IF NOT EXISTS source.aemet_warning_download_file (
    source_download_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id text NOT NULL DEFAULT 'aemet_avisos_cap_archive_download',
    source_system text NOT NULL DEFAULT 'aemet'
        CHECK (source_system = 'aemet'),
    product_id text NOT NULL DEFAULT 'avisos_cap_archive'
        CHECK (product_id = 'avisos_cap_archive'),
    request_elaboration_from timestamptz NOT NULL,
    request_elaboration_to timestamptz NOT NULL,
    source_file_path text NOT NULL,
    source_file_sha256 text NOT NULL,
    response_size_bytes bigint NOT NULL DEFAULT 0
        CHECK (response_size_bytes >= 0),
    outer_member_count integer NOT NULL DEFAULT 0
        CHECK (outer_member_count >= 0),
    xml_member_count integer NOT NULL DEFAULT 0
        CHECK (xml_member_count >= 0),
    filtered_record_count integer NOT NULL DEFAULT 0
        CHECK (filtered_record_count >= 0),
    downloaded_at timestamptz,
    ingest_id bigint NOT NULL REFERENCES ingest.ingest_file(ingest_id),
    imported_at timestamptz NOT NULL DEFAULT now(),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_file_path),
    UNIQUE (request_elaboration_from, request_elaboration_to)
);

CREATE TABLE IF NOT EXISTS source.aemet_warning_cap_record (
    source_record_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id text NOT NULL DEFAULT 'aemet_avisos_cap_archive_record',
    source_download_id bigint NOT NULL REFERENCES source.aemet_warning_download_file(source_download_id) ON DELETE CASCADE,
    source_member_path text NOT NULL,
    source_record_hash text NOT NULL,
    cap_identifier text NOT NULL,
    cap_sender text,
    sent_at timestamptz,
    cap_status text,
    cap_msg_type text,
    cap_scope text,
    language text NOT NULL,
    category text,
    event text NOT NULL,
    event_code text NOT NULL,
    phenomenon_code text NOT NULL,
    phenomenon_label text NOT NULL,
    response_type text,
    urgency text,
    severity text,
    certainty text,
    effective_at timestamptz,
    onset_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    sender_name text,
    headline text,
    description text,
    instruction text,
    web text,
    contact text,
    level_code text NOT NULL,
    level_label text NOT NULL,
    parameter_code text,
    parameter_label text,
    parameter_value text,
    temperature_max_c double precision,
    probability text,
    area_name text NOT NULL,
    area_code text,
    polygon_text text,
    geom geometry(Polygon, 4326),
    imported_at timestamptz NOT NULL DEFAULT now(),
    raw_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_download_id, source_member_path, language, area_code)
);

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

CREATE INDEX IF NOT EXISTS aemet_warning_download_request_from_idx
    ON source.aemet_warning_download_file (request_elaboration_from);
CREATE INDEX IF NOT EXISTS aemet_warning_download_request_to_idx
    ON source.aemet_warning_download_file (request_elaboration_to);
CREATE INDEX IF NOT EXISTS aemet_warning_download_ingest_id_idx
    ON source.aemet_warning_download_file (ingest_id);

CREATE INDEX IF NOT EXISTS aemet_warning_cap_record_source_download_id_idx
    ON source.aemet_warning_cap_record (source_download_id);
CREATE INDEX IF NOT EXISTS aemet_warning_cap_record_identifier_idx
    ON source.aemet_warning_cap_record (cap_identifier);
CREATE INDEX IF NOT EXISTS aemet_warning_cap_record_sent_at_idx
    ON source.aemet_warning_cap_record (sent_at);
CREATE INDEX IF NOT EXISTS aemet_warning_cap_record_onset_at_idx
    ON source.aemet_warning_cap_record (onset_at);
CREATE INDEX IF NOT EXISTS aemet_warning_cap_record_expires_at_idx
    ON source.aemet_warning_cap_record (expires_at);
CREATE INDEX IF NOT EXISTS aemet_warning_cap_record_event_code_idx
    ON source.aemet_warning_cap_record (event_code);
CREATE INDEX IF NOT EXISTS aemet_warning_cap_record_level_label_idx
    ON source.aemet_warning_cap_record (level_label);
CREATE INDEX IF NOT EXISTS aemet_warning_cap_record_area_code_idx
    ON source.aemet_warning_cap_record (area_code);
CREATE INDEX IF NOT EXISTS aemet_warning_cap_record_geom_gix
    ON source.aemet_warning_cap_record USING GIST (geom);
CREATE INDEX IF NOT EXISTS aemet_warning_refresh_key_queued_at_idx
    ON ingest.aemet_warning_refresh_key (queued_at);
CREATE INDEX IF NOT EXISTS aemet_warning_refresh_date_queued_at_idx
    ON ingest.aemet_warning_refresh_date (queued_at);

COMMENT ON TABLE source.aemet_warning_download_file IS 'Ficheros tar del archivo histórico de avisos CAP de AEMET descargados por rango de elaboración.';
COMMENT ON TABLE source.aemet_warning_cap_record IS 'Registros CAP filtrados a temperaturas máximas, cercanos al origen y con geometría de zona AEMET en EPSG:4326.';
COMMENT ON TABLE ingest.aemet_warning_refresh_key IS 'Cola de claves CAP/zona pendientes de recanonizar de source a core.';
COMMENT ON TABLE ingest.aemet_warning_refresh_date IS 'Cola de fechas válidas pendientes de republicar en pub.aemet_max_temperature_daily_feature.';
COMMENT ON COLUMN source.aemet_warning_download_file.request_elaboration_from IS 'Inicio UTC del rango de fecha/hora de elaboración solicitado al endpoint de archivo AEMET.';
COMMENT ON COLUMN source.aemet_warning_download_file.request_elaboration_to IS 'Fin UTC del rango de fecha/hora de elaboración solicitado al endpoint de archivo AEMET.';
COMMENT ON COLUMN source.aemet_warning_cap_record.event_code IS 'Código y etiqueta original del fenómeno, por ejemplo AT;Temperaturas máximas.';
COMMENT ON COLUMN source.aemet_warning_cap_record.parameter_value IS 'Valor umbral original del parámetro CAP, por ejemplo 37 ºC.';
COMMENT ON COLUMN source.aemet_warning_cap_record.temperature_max_c IS 'Umbral numérico de temperatura máxima extraído del parámetro TA cuando está disponible.';
COMMENT ON COLUMN source.aemet_warning_cap_record.area_code IS 'Código de zona Meteoalerta comunicado en el bloque geocode del CAP.';
COMMENT ON COLUMN source.aemet_warning_cap_record.geom IS 'Polígono de la zona de aviso publicado por AEMET, con coordenadas normalizadas a lon/lat.';
