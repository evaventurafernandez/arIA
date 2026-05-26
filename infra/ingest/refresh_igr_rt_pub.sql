-- Refresca la materialized view pub.road_network_mvt_source desde core.road_segment.
-- CONCURRENTLY requiere indices unicos, ya provistos en 020_igr_rt_pub.sql.

REFRESH MATERIALIZED VIEW CONCURRENTLY pub.road_network_mvt_source;

ANALYZE pub.road_network_mvt_source;
