# Carga actual de `landcover`

Esta guía describe el flujo vigente para cargar y publicar `landcover` en PostgreSQL/PostGIS a partir del `FileGDB` de CORINE.

Además, el repositorio incorpora ya el pipeline base de `burnt area` diario para Copernicus CLMS:

- `source.burnt_area_catalog_item`
- `core.burnt_area_daily_file`
- `pub.burnt_area_daily_file_catalog`
- `pub.burnt_area_daily_stat`

La ingesta puede trabajar con `all.zip` o con la carpeta extraída `data/copernicus/data_burnt_areas`, consolidar una fila por día/version/formato y completar después el tramo raster con recorte a España, teselas PNG locales y estadística diaria país.

También incorpora un pipeline histórico diario para focos NASA FIRMS en España, con separación `raw -> source -> core -> pub`:

- `source.firms_hotspot_download_file`
- `source.firms_hotspot_observation`
- `core.firms_hotspot`
- `pub.firms_hotspot_daily_catalog`
- `pub.firms_hotspot_daily_stat`

El flujo descarga bloques CSV `SP` de `VIIRS_NOAA20_SP` y `VIIRS_SNPP_SP`, conserva los ficheros brutos y sus manifiestos en `data-store/files/raw/nasa/firms/historical`, deduplica en `core` y publica una serie diaria país que mantiene días con `0` focos si la cobertura del día es completa.

## Pipeline histórico FIRMS

1. Asegura las nuevas estructuras:

   ```bash
   docker compose up -d postgres
   docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/009_firms_history_source.sql
   docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/010_firms_history_core.sql
   docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/011_firms_history_pub.sql
   ```

2. Descarga el histórico bruto:

   ```bash
   venv\Scripts\python.exe infra/ingest/download_firms_historical_sources.py --date-from 2025-05-01 --date-to 2025-08-31 --block-days 5
   ```

3. Importa `source`:

   ```bash
   venv\Scripts\python.exe infra/ingest/import_firms_historical_source.py --date-from 2025-05-01 --date-to 2025-08-31
   ```

4. Reconstruye `core`:

   ```bash
   docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_firms_historical_core.sql
   ```

5. Publica la serie diaria país:

   ```bash
   venv\Scripts\python.exe infra/ingest/publish_firms_historical.py --date-from 2025-05-01 --date-to 2025-08-31
   ```

## Resultado final de la carga

Una ejecución completa deja actualizados estos niveles:

- `source.landcover_clc18_es`
- `source.landcover_clc18_es_canarias`
- `source.landcover_corine_polygon`
- `core.landcover_polygon`
- `pub.landcover_filtered`
- `pub.landcover_mvt_source`
- `pub.landcover_mvt_class_source`

Uso actual de cada publicación:

- `pub.landcover_filtered`: salida GeoJSON agregada de compatibilidad.
- `pub.landcover_mvt_source`: fuente MVT detallada por feature para zoom medio y alto.
- `pub.landcover_mvt_class_source`: fuente MVT agregada por clase para bajo zoom (`z <= 8`).

## Flujo vigente

El pipeline actual es:

```text
CLC2018_GDB.zip
  -> extracción canónica del FileGDB
  -> staging
  -> source
  -> core
  -> pub.landcover_filtered
  -> pub.landcover_mvt_source + pub.landcover_mvt_class_source
```

## Artefactos y scripts

- `import_landcover_source.py`: descomprime el `FileGDB`, carga a `staging` con GDAL y consolida `source`.
- `refresh_landcover_core.sql`: reconstruye `core` desde `source`.
- `refresh_landcover_pub.sql`: refresca `pub.landcover_filtered`.
- `refresh_landcover_mvt.sql`: refresca `pub.landcover_mvt_source` y `pub.landcover_mvt_class_source`.
- `verify_landcover_source.sql`: comprobaciones de `source`.
- `verify_landcover_core.sql`: comprobaciones de `core`.
- `verify_landcover_pub.sql`: comprobaciones de `pub.landcover_filtered`.
- `verify_landcover_mvt.sql`: comprobaciones de las dos publicaciones MVT.

## Origen de entrada

Por defecto se usa este ZIP bruto:

```text
./data-store/files/CLC2018_GDB.zip
```

Durante la carga se extrae, si hace falta, a esta ruta canónica:

```text
./data-store/files/raw/copernicus/corine/landcover_corine_2018_filtered/2018/CLC2018_ES.gdb
```

Si el `FileGDB` ya está extraído y el ZIP no ha cambiado, la extracción se reutiliza.

## Primera carga

Los comandos siguientes asumen la configuración por defecto del proyecto:

- base: `meteovisor`
- usuario: `meteovisor`
- servicio: `postgres`

Si has cambiado `POSTGRES_DB` o `POSTGRES_USER` en `.env`, sustituye esos valores en los comandos.

1. Arranca PostgreSQL/PostGIS:

   ```bash
   docker compose up -d postgres
   ```

2. Si la base es nueva, el bootstrap SQL se aplica automáticamente al arrancar el contenedor.

   Si reutilizas una base ya existente y necesitas asegurar las estructuras, ejecuta:

   ```bash
   docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/002_landcover_source.sql
   docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/003_landcover_core.sql
   docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/004_landcover_pub.sql
   docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/005_landcover_mvt.sql
   ```

3. Carga `source` con el contenedor `gdal`:

   ```bash
   docker compose run --rm gdal python3 /work/infra/ingest/import_landcover_source.py
   ```

4. Reconstruye `core`:

   ```bash
   docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_landcover_core.sql
   ```

5. Refresca la publicación agregada:

   ```bash
   docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_landcover_pub.sql
   ```

6. Refresca las publicaciones MVT:

   ```bash
   docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_landcover_mvt.sql
   ```

## Recarga normal

Si el esquema ya existe y solo quieres volver a cargar el dataset o aplicar un cambio en el filtro:

```bash
docker compose run --rm gdal python3 /work/infra/ingest/import_landcover_source.py
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_landcover_core.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_landcover_pub.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_landcover_mvt.sql
```

## Verificación rápida

Para comprobar que la carga ha llegado a todos los niveles:

```bash
docker compose exec -T postgres psql -U meteovisor -d meteovisor -c "SELECT 'source' AS stage, count(*) AS total FROM source.landcover_corine_polygon UNION ALL SELECT 'core', count(*) FROM core.landcover_polygon UNION ALL SELECT 'pub', count(*) FROM pub.landcover_filtered UNION ALL SELECT 'mvt_detail', count(*) FROM pub.landcover_mvt_source UNION ALL SELECT 'mvt_overview', count(*) FROM pub.landcover_mvt_class_source;"
```

Resultado esperado en una carga completa:

- `source` > 0
- `core` > 0
- `pub` > 0
- `mvt_detail` > 0
- `mvt_overview` > 0

## Verificación completa

Si necesitas validación detallada:

```bash
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/verify_landcover_source.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/verify_landcover_core.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/verify_landcover_pub.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/verify_landcover_mvt.sql
```

## Validación rápida con muestra

Para una prueba de humo puedes limitar la importación:

```bash
docker compose run --rm -e MAX_FEATURES_PER_LAYER=100 gdal python3 /work/infra/ingest/import_landcover_source.py
```

Úsalo solo sobre una base de prueba o justo antes de repetir la carga completa, porque con `TRUNCATE_SOURCE=1` dejará `source` con una muestra parcial.

## Variables útiles

- `RAW_ZIP`: ZIP de entrada. Por defecto `./data-store/files/CLC2018_GDB.zip`.
- `EXTRACTED_GDB_DIR`: ruta canónica del `FileGDB` descomprimido.
- `WHERE_CLAUSE`: filtro funcional por `CODE_18`.
- `MAX_FEATURES_PER_LAYER`: límite de features por capa para pruebas rápidas. `0` significa sin límite.
- `TRUNCATE_STAGING`: limpia `staging` antes de recargar. Por defecto `1`.
- `TRUNCATE_SOURCE`: limpia `source` antes de recargar. Por defecto `1`.
- `OGR_ORGANIZE_POLYGONS`: estrategia de GDAL para polígonos complejos. Por defecto `SKIP`.

## Notas operativas

- `import_landcover_source.py` solo carga `source`; no publica automáticamente `core` ni `pub`.
- `docker compose exec ... -f /ruta/al.sql` se usa para que los comandos funcionen igual en Bash y en PowerShell.
- La carga bulk usa el driver PostgreSQL de GDAL con `PG_USE_COPY=YES`.
- El subconjunto actual de `CODE_18` en `source` es `111`, `112`, `121`, `211`, `242`, `311`, `312`, `313`, `321`, `322`, `323`, `324`.
- En `core`, `pub.landcover_filtered`, `pub.landcover_mvt_source` y `pub.landcover_mvt_class_source`, los códigos de origen `111` y `112` se agrupan bajo el código canónico `1001` con la etiqueta `Tejido urbano`.
- Los códigos canónicos publicados actualmente son `1001`, `121`, `211`, `242`, `311`, `312`, `313`, `321`, `322`, `323`, `324`.
- Si amplías o reduces el subconjunto de origen o cambias una agrupación canónica, sincroniza `CODE_FILTER` en `import_landcover_source.py`, las `CHECK` de `002_landcover_source.sql`, el catálogo `core.landcover_class` de `003_landcover_core.sql` y el mapeo de `refresh_landcover_core.sql` antes de volver a cargar.
- `source` conserva trazabilidad cercana al origen; la canonización geométrica se resuelve en `core`.
- `core` mantiene una fila por feature y `pub.landcover_filtered` agrega por clase.
- `pub.landcover_mvt_class_source` se usa en el visor hasta `z=8` y `pub.landcover_mvt_source` a partir de `z=9`.
