-- Fase 6: reconstruccion reproducible de pub a partir de core.

REFRESH MATERIALIZED VIEW pub.landcover_filtered;

ANALYZE pub.landcover_filtered;
