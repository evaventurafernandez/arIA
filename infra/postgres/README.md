# PostgreSQL + PostGIS

Este directorio contiene la base del entorno Docker para la PoC de `landcover`.

## Componentes

- `docker-compose.yml`: levanta PostgreSQL con PostGIS.
- `infra/postgres/initdb/`: scripts SQL ejecutados solo en el primer arranque del clúster.
- `infra/postgres/initdb/002_landcover_source.sql`: estructuras mínimas de `ingest` y `source` para la PoC.
- `infra/postgres/initdb/003_landcover_core.sql`: catalogo semantico y estructura canonica de `core` para landcover.
- `infra/postgres/initdb/004_landcover_pub.sql`: publicacion derivada `pub.landcover_filtered` para explotacion.

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
El bootstrap de base no depende de scripts shell; la carga filtrada de `landcover` se ejecuta aparte en un contenedor GDAL reproducible con Python y bindings oficiales de GDAL.
La canonizacion desde `source` a `core` se ejecuta con SQL reproducible desde `infra/ingest/refresh_landcover_core.sql`.
La publicacion derivada desde `core` a `pub` se refresca con `infra/ingest/refresh_landcover_pub.sql`.

## Estrategia de migraciones

La PoC arranca con bootstrap SQL versionado en `infra/postgres/initdb/`.
Las migraciones posteriores deben vivir en una estructura SQL versionada separada dentro de `infra/postgres/migrations/`.
La importación filtrada inicial de `landcover` queda descrita en `infra/ingest/`.
