# MeteoVisor Demo

Demo web para visualizar avisos meteorológicos, focos de incendio y capas geográficas de riesgo en España. El proyecto combina una API con FastAPI y un frontend estático basado en Leaflet.

## Qué incluye

- Avisos meteorológicos activos de AEMET, obtenidos desde AEMET OpenData y parseados desde CAP XML.
- Focos de incendio de NASA FIRMS, filtrados para España y confianza nominal/alta, con intensidad visual por FRP.
- Mapa interactivo con Leaflet, filtros por nivel y tipo de aviso, timeline y listado lateral.
- Capas WMS externas de EFFIS/Copernicus, inundaciones y CORINE Land Cover.
- Capa CORINE 2018 filtrada servida como `vector tiles (MVT)` desde `PostgreSQL + PostGIS`.
- Base de capa temporal diaria de `burnt area` Copernicus CLMS con metadata, timeline propia y endpoint de teselas locales por fecha.
- Pipeline histórico diario de focos NASA FIRMS persistido en `PostgreSQL + PostGIS`, con timeline, estadísticas país y GeoJSON por fecha.
- Script auxiliar para generar `data/nucleos.geojson` con núcleos de población del IGN.
- Decisión documentada de usar NASA FIRMS como fuente de focos activos tras contrastarla con EFFIS/Copernicus, evitando publicar una capa EFFIS derivada de teselas.

## Estructura

```text
.
|-- main.py                  # API FastAPI y servidor del frontend
|-- frontend/                # HTML, CSS y JavaScript del mapa
|-- data/                    # Datos GeoJSON locales generados
|-- generar_landcover.py     # Utilidad auxiliar fuera del flujo actual de ingesta
|-- infra/                   # Infraestructura Docker, SQL e ingesta PostGIS
|-- generar_nucleos.py       # Descarga y genera data/nucleos.geojson desde IGN
|-- requirements.txt         # Dependencias Python principales
`-- .env                     # Variables locales de configuración
```

## Requisitos

- Python 3.10 o superior.
- Una clave de AEMET OpenData.
- Docker Compose para levantar PostgreSQL/PostGIS.
- Opcionalmente, una clave de NASA FIRMS para cargar focos de incendio.

Instala las dependencias principales:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Los scripts de generación de datos usan librerías geoespaciales adicionales como `geopandas`, `pandas` y `shapely`. Si necesitas regenerar esos ficheros, instálalas también en tu entorno.

## Configuración

Crea un fichero `.env` en la raíz del proyecto con estas variables:

```env
AEMET_API_KEY=tu_clave_de_aemet
FIRMS_MAP_KEY=tu_clave_de_firms
POSTGRES_HOST=127.0.0.1
POSTGRES_DB=meteovisor
POSTGRES_USER=meteovisor
POSTGRES_PASSWORD=meteovisor
POSTGRES_PORT=5432
FIRMS_HISTORICAL_DEFAULT_DATE_FROM=2025-05-01
FIRMS_HISTORICAL_DEFAULT_DATE_TO=2025-08-31
```

`FIRMS_MAP_KEY` es opcional. Si no se informa, la API devolverá una lista vacía de focos de incendio.

## Preparar datos

La capa `landcover` se publica actualmente desde PostGIS. El backend:

- mantiene `pub.landcover_filtered` como publicación GeoJSON agregada de compatibilidad;
- usa `pub.landcover_mvt_source` como fuente MVT detallada por feature;
- y usa `pub.landcover_mvt_class_source` como fuente MVT agregada por clase para bajo zoom.

Los comandos siguientes asumen la configuración por defecto del proyecto (`POSTGRES_DB=meteovisor`, `POSTGRES_USER=meteovisor`). Si has cambiado esos valores en `.env`, sustitúyelos también aquí.

Levanta antes la base de datos:

```bash
docker compose up -d postgres
```

Si la base ya existía y necesitas asegurar o actualizar las publicaciones MVT:

```bash
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/005_landcover_mvt.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_landcover_mvt.sql
```

Si necesitas rehacer la ingesta completa de landcover desde el `FileGDB` real:

```bash
docker compose run --rm gdal python3 /work/infra/ingest/import_landcover_source.py
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_landcover_core.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_landcover_pub.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_landcover_mvt.sql
```

`import_landcover_source.py` solo deja datos en `source`; la capa no aparece en el visor hasta reconstruir `core` y refrescar `pub.landcover_filtered`, `pub.landcover_mvt_source` y `pub.landcover_mvt_class_source`.

La guía completa de primera carga, validaciones y recargas está en [infra/ingest/README.md](infra/ingest/README.md).

La nueva capa temporal diaria de `burnt area` se apoya en el catálogo Copernicus CLMS, ya sea como `all.zip` o como carpeta extraída, y en una timeline propia del visor:

1. Asegura las estructuras nuevas en PostgreSQL/PostGIS:

```bash
docker compose up -d postgres
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/006_burnt_area_source.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/007_burnt_area_core.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/008_burnt_area_pub.sql
```

2. Importa el catálogo diario a `source`:

```bash
venv\Scripts\python.exe infra/ingest/import_burnt_area_catalog.py
```

3. Consolida `core`:

```bash
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_burnt_area_core.sql
```

4. Descarga a disco local los TIFF diarios del producto `v4/cog`:

```bash
venv\Scripts\python.exe infra/ingest/download_burnt_area_daily_sources.py --dataset-version v4 --delivery-format cog --date-from 2025-05-01 --date-to 2025-08-31
```

5. Procesa los días del estudio desde la copia local, recorta a España, genera teselas PNG y escribe manifiestos diarios:

```bash
docker compose --profile tools run --rm gdal python3 /work/infra/ingest/process_burnt_area_daily.py --dataset-version v4 --delivery-format cog --date-from 2025-05-01 --date-to 2025-08-31 --skip-remote
```

6. Publica en PostgreSQL el estado local y la estadística diaria de España:

```bash
venv\Scripts\python.exe infra/ingest/publish_burnt_area_manifests.py --dataset-version v4 --delivery-format cog --date-from 2025-05-01 --date-to 2025-08-31
```

Si no defines `BURNT_AREA_CATALOG_ROOT`, el backend intenta localizar la carpeta `data/copernicus/data_burnt_areas`. Si tampoco existe, cae a `BURNT_AREA_CATALOG_ZIP`, `data-store/files/...` o `~/Downloads/all.zip`.

Para descargar los `COG` remotos durante la ingesta necesitas credenciales CDSE en `.env`:

```bash
CDSE_USERNAME=
CDSE_PASSWORD=
```

O bien claves S3 ya generadas:

```bash
CDSE_S3_ACCESS_KEY=
CDSE_S3_SECRET_KEY=
CDSE_S3_ENDPOINT=eodata.dataspace.copernicus.eu
```

En `v4/cog` cada día se publica como un prefijo S3 con cuatro TIFF (`BF`, `CP`, `DOB`, `LFP`). El downloader los guarda en `data/copernicus/burnt_area/raw/...`, el procesado local monta un `VRT` por día y desde ahí genera el recorte a España, las teselas PNG y la estadística diaria.

El procesado diario usa `DOB == día seleccionado` para publicar la evolución diaria. La acumulada queda preparada en el mismo script con `--mode cumulative`, aunque el visor sigue conectado por defecto a la variante diaria.

El histórico diario de focos NASA FIRMS sigue un patrón similar, pero adaptado a vectoriales y con persistencia directa en PostGIS:

1. Asegura las estructuras del histórico FIRMS:

```bash
docker compose up -d postgres
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/009_firms_history_source.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/010_firms_history_core.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/011_firms_history_pub.sql
```

2. Descarga los bloques históricos `SP` de `VIIRS_NOAA20` y `VIIRS_SNPP` para España:

```bash
venv\Scripts\python.exe infra/ingest/download_firms_historical_sources.py --date-from 2025-05-01 --date-to 2025-08-31 --block-days 5
```

3. Importa el `raw` descargado a `source`:

```bash
venv\Scripts\python.exe infra/ingest/import_firms_historical_source.py --date-from 2025-05-01 --date-to 2025-08-31
```

4. Reconstruye el nivel canónico deduplicado:

```bash
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_firms_historical_core.sql
```

5. Publica la serie diaria país, incluidos los días con `0` focos cuando la cobertura de fuentes y regiones está completa:

```bash
venv\Scripts\python.exe infra/ingest/publish_firms_historical.py --date-from 2025-05-01 --date-to 2025-08-31
```

Los CSV brutos y sus manifiestos quedan en `data-store/files/raw/nasa/firms/historical/...`. La API histórica resultante se expone en `/api/layers/firms-history`, `/api/firms/history/timeline`, `/api/firms/history/stats/daily` y `/api/firms/history/features?date=YYYY-MM-DD`.

Para generar núcleos de población desde la API-Features del IGN:

```bash
python generar_nucleos.py
```

Los focos activos de EFFIS/Copernicus se evaluaron como posible capa de contexto y comparación con NASA FIRMS, pero no se mantienen como capa operativa del visor. La razón principal es que el acceso disponible para ese prototipo procedía de teselas WMTS/WMS rasterizadas, no de un servicio vectorial con atributos equivalentes a FIRMS. Para evitar una capa diaria derivada por píxeles, sin atributos originales y con mantenimiento adicional, el visor publica únicamente focos NASA FIRMS y conserva EFFIS para índices FWI/DC.

## Ejecutar

Arranca el servidor con Uvicorn:

```bash
uvicorn main:app --reload
```

Después abre:

```text
http://127.0.0.1:8000
```

## Endpoints

- `GET /api/alerts`: avisos meteorológicos cargados desde AEMET.
- `GET /api/fires`: focos de incendio recientes cargados en vivo desde NASA FIRMS al abrir o recargar el visor.
- `GET /api/stats`: resumen básico de avisos y focos por nivel.
- `GET /api/layers/burnt-area`: metadata de la capa temporal diaria de áreas quemadas.
- `GET /api/burnt-area/timeline?version=v4&format=cog&date_from=2025-05-01&date_to=2025-08-31`: fechas disponibles para la barra temporal propia.
- `GET /api/burnt-area/stats/daily?version=v4&format=cog&date_from=2025-05-01&date_to=2025-08-31`: serie diaria de estadísticas publicadas o placeholder si aún no se han calculado.
- `GET /api/burnt-area/tiles/{version}/{date}/{z}/{x}/{y}.png`: teselas PNG locales por día; mientras no existan, devuelve una tesela transparente.
- `GET /api/layers/firms-history`: metadata del histórico diario FIRMS persistido en PostGIS.
- `GET /api/firms/history/timeline?date_from=2025-05-01&date_to=2025-08-31`: fechas publicadas del histórico FIRMS con cobertura y conteos diarios.
- `GET /api/firms/history/stats/daily?date_from=2025-05-01&date_to=2025-08-31`: serie diaria país del histórico FIRMS.
- `GET /api/firms/history/features?date=2025-08-16&source=VIIRS_NOAA20_SP`: GeoJSON de focos históricos por fecha, con filtro opcional de fuente y `bbox`.
- `GET /api/landcover`: `FeatureCollection` GeoJSON agregado desde `pub.landcover_filtered`.
- `GET /api/layers/landcover`: metadatos de la capa publicada.
- `GET /api/landcover/tiles/{z}/{x}/{y}.mvt`: teselas vectoriales `MVT` para render principal de landcover.
- `GET /api/landcover/point?lon=...&lat=...&bbox=...&width=...&height=...&i=...&j=...&crs=EPSG:3857`: consulta de atributos por punto vía `GetFeatureInfo` sobre el WMS de IGN.
- `GET /api/landcover/features?bbox=minx,miny,maxx,maxy`: endpoint auxiliar de depuración/detalle espacial desde `core.landcover_polygon`.
- `GET /api/landcover/features/{id}`: detalle GeoJSON de una feature individual de `core.landcover_polygon`.

El frontend se sirve desde la carpeta `frontend/` mediante `StaticFiles`.

## Notas

- Al iniciar la aplicación, se carga `data/boundaries/spain_nuts_2024_01m.geojson` para filtrar detecciones de FIRMS por punto en MultiPolygon. Este GeoJSON local procede de GISCO/NUTS 2024 y cubre Península, Baleares, Canarias, Ceuta y Melilla.
- La consulta FIRMS usa por defecto `VIIRS_NOAA21_NRT`, `VIIRS_NOAA20_NRT` y `VIIRS_SNPP_NRT`, con `DAY_RANGE=1` y sin parámetro `DATE` para recibir los datos más recientes. Se lanzan dos consultas territoriales por producto: Península/Baleares/Ceuta/Melilla y Canarias; después se aplica siempre el filtro final por MultiPolygon y se conservan sólo detecciones `confidence` nominal/alta (`n`/`h`).
- La simbología FIRMS usa `frp` como potencia radiativa del foco en MW mediante categorías visuales de intensidad: <10, 10-50, 50-200 y >200 MW. No son umbrales oficiales NASA de gravedad.
- Los avisos de AEMET se cargan en memoria durante el arranque. Los focos NASA FIRMS se piden al backend cada vez que el visor se carga o recarga.
- La capa `landcover` se valida en arranque comprobando acceso a `pub.landcover_filtered`, `pub.landcover_mvt_source` y, si existe, `pub.landcover_mvt_class_source`.
- El visor renderiza `landcover` con `Leaflet.VectorGrid` sobre teselas `MVT` servidas por FastAPI desde PostGIS, usando `pub.landcover_mvt_class_source` hasta `z=8` y `pub.landcover_mvt_source` a partir de `z=9`.
- Las capas WMS se consultan desde servicios externos, por lo que su disponibilidad depende de esos proveedores.
