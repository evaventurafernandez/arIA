-- Índices para que la ingesta y la reconstrucción AEMET no bloqueen por escaneos
-- caros al borrar/reinsertar bloques source referenciados desde core.

CREATE INDEX IF NOT EXISTS aemet_warning_cap_record_source_download_id_idx
    ON source.aemet_warning_cap_record (source_download_id);

CREATE INDEX IF NOT EXISTS aemet_max_temperature_warning_representative_source_record_id_idx
    ON core.aemet_max_temperature_warning (representative_source_record_id);
