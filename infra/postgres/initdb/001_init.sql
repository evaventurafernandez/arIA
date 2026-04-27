CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS ingest;
CREATE SCHEMA IF NOT EXISTS source;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS pub;

COMMENT ON SCHEMA ingest IS 'Control de ingesta, trazabilidad y bootstrap de datos';
COMMENT ON SCHEMA source IS 'Representacion estructurada cercana al origen';
COMMENT ON SCHEMA core IS 'Modelo homogeneo y normalizado';
COMMENT ON SCHEMA pub IS 'Estructuras optimizadas para exposicion';
