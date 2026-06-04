# PostgreSQL + PostGIS

Este directorio contiene la base del entorno Docker PostgreSQL/PostGIS del proyecto.

## Componentes

- `docker-compose.yml`: levanta PostgreSQL con PostGIS.
- `infra/postgres/initdb/`: scripts SQL ejecutados solo en el primer arranque del clúster.
- `infra/postgres/initdb/006_burnt_area_source.sql`: catalogo diario `source` de burnt area Copernicus CLMS.
- `infra/postgres/initdb/007_burnt_area_core.sql`: estructura canonica `core` por dia, version y formato de burnt area.
- `infra/postgres/initdb/008_burnt_area_pub.sql`: publicacion ligera de disponibilidad y tabla de estadisticas diarias de burnt area.
- `infra/postgres/initdb/009_firms_history_source.sql`: bloques CSV descargados y observaciones `source` del historico diario NASA FIRMS.
- `infra/postgres/initdb/010_firms_history_core.sql`: estructura canonica deduplicada `core` del historico de focos FIRMS.
- `infra/postgres/initdb/011_firms_history_pub.sql`: publicacion diaria `pub` con cobertura y estadisticas pais del historico FIRMS.

## Estructura base

El bootstrap crea estos schemas:

- `ingest`
- `staging`
- `source`
- `core`
- `pub`

## Persistencia

La base de datos usa el volumen local:

- `./data-store/postgres/data`

El directorio se ignora en Git para no versionar datos persistentes ni artefactos generados.

## Portabilidad

La configuración usa rutas relativas para funcionar en Linux y en Windows con Docker Desktop.
El bootstrap de base no depende de scripts shell. Los pipelines de ingesta y refresco por capa (avisos AEMET, focos FIRMS y áreas quemadas) se documentan en `infra/ingest/README.md`.

## Estrategia de migraciones

La PoC arranca con bootstrap SQL versionado en `infra/postgres/initdb/`.
Las migraciones posteriores deben vivir en una estructura SQL versionada separada dentro de `infra/postgres/migrations/`.
Los flujos de ingesta y publicación por capa quedan descritos en `infra/ingest/`.
