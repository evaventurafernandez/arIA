# MeteoVisor Demo

Demo web para visualizar avisos meteorológicos, focos de incendio y capas geográficas de riesgo en España. El proyecto combina una API con FastAPI y un frontend estático basado en Leaflet.

## Qué incluye

- Avisos meteorológicos activos de AEMET, obtenidos desde AEMET OpenData y parseados desde CAP XML.
- Focos de incendio de NASA FIRMS, filtrados para España y clasificados por FRP.
- Mapa interactivo con Leaflet, filtros por nivel y tipo de aviso, timeline y listado lateral.
- Capas WMS externas de EFFIS/Copernicus, inundaciones y CORINE Land Cover.
- Capa CORINE 2018 filtrada servida como `vector tiles (MVT)` desde `PostgreSQL + PostGIS`.
- Script auxiliar para generar `data/nucleos.geojson` con núcleos de población del IGN.
- Script auxiliar para generar `data/copernicus/fires/effis_viirs_hs_today_wfs.geojson` con focos activos EFFIS/Copernicus vectorizados desde teselas WMTS.

## Estructura

```text
.
|-- main.py                  # API FastAPI y servidor del frontend
|-- frontend/                # HTML, CSS y JavaScript del mapa
|-- data/                    # Datos GeoJSON locales generados
|-- generar_landcover.py     # Utilidad auxiliar fuera del flujo actual de ingesta
|-- infra/                   # Infraestructura Docker, SQL e ingesta PostGIS
|-- generar_nucleos.py       # Descarga y genera data/nucleos.geojson desde IGN
|-- generar_effis_wfs.py     # Genera una capa vectorial local desde EFFIS/Copernicus
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

Para generar núcleos de población desde la API-Features del IGN:

```bash
python generar_nucleos.py
```

Para generar la capa local de focos activos EFFIS/Copernicus:

```bash
python generar_effis_wfs.py --source effis --timeout 30 --retries 3
```

El script escribe por defecto `data/copernicus/fires/effis_viirs_hs_today_wfs.geojson`. El archivo es un `FeatureCollection` GeoJSON con una feature por componente detectado en las teselas de la capa `viirs.hs.today`. Cada feature incluye geometría `Point`, coordenadas WGS84, tesela de origen (`zoom`, `tile_x`, `tile_y`), número de píxeles detectados, caja de píxeles (`pixel_bbox`), caja geográfica (`bbox_wgs84`) y color medio (`avg_color`).

El origen principal es el WMTS de EFFIS/Copernicus. El backend sirve el GeoJSON local en `/api/effis/wmts`; las subrutas `/api/effis/wmts/{layer}/{z}/{y}/{x}.png` se mantienen como proxy de teselas PNG para regenerar la capa. Como esas teselas no son entidades vectoriales nativas, el script vectoriza los píxeles no transparentes de cada tesela. Si una tesela WMTS falla o llega incompleta, usa un fallback WMS para el mismo bbox de la tesela. La metadata del GeoJSON guarda el número de teselas procesadas, fallos y teselas resueltas por fallback.

También puede ejecutarse contra el proxy local del backend, siempre que Uvicorn esté arrancado:

```bash
python generar_effis_wfs.py --source endpoint --endpoint-url http://127.0.0.1:8000/api/effis/wmts
```

Parámetros útiles:

- `--layer`: capa WMTS a descargar. Por defecto `viirs.hs.today`.
- `--zoom`: zoom de teselas. Por defecto `8`.
- `--bbox`: área WGS84 `min_lon,min_lat,max_lon,max_lat`. Por defecto cubre España e islas.
- `--geometry`: salida como `point` o `bbox`. Por defecto `point`.
- `--output` y `--output-dir`: ruta exacta o carpeta de salida.
- `--concurrency`, `--timeout` y `--retries`: control de descargas.
- `--dry-run`: muestra las teselas que se procesarían sin descargar datos.

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
- `GET /api/landcover`: `FeatureCollection` GeoJSON agregado desde `pub.landcover_filtered`.
- `GET /api/layers/landcover`: metadatos de la capa publicada.
- `GET /api/landcover/tiles/{z}/{x}/{y}.mvt`: teselas vectoriales `MVT` para render principal de landcover.
- `GET /api/landcover/features?bbox=minx,miny,maxx,maxy`: endpoint auxiliar de depuración/detalle espacial desde `core.landcover_polygon`.
- `GET /api/landcover/features/{id}`: detalle GeoJSON de una feature individual de `core.landcover_polygon`.
- `GET /api/effis/wmts`: GeoJSON local de focos EFFIS/Copernicus vectorizados.

El frontend se sirve desde la carpeta `frontend/` mediante `StaticFiles`.

## Notas

- Al iniciar la aplicación, se carga `data/boundaries/spain_nuts_2024_01m.geojson` para filtrar detecciones de FIRMS por punto en MultiPolygon. Este GeoJSON local procede de GISCO/NUTS 2024 y cubre Península, Baleares, Canarias, Ceuta y Melilla.
- La consulta FIRMS usa por defecto `VIIRS_NOAA21_NRT`, `VIIRS_NOAA20_NRT` y `VIIRS_SNPP_NRT`, con `DAY_RANGE=1` y sin parámetro `DATE` para recibir los datos más recientes. Se lanzan dos consultas territoriales por producto: Península/Baleares/Ceuta/Melilla y Canarias; después se aplica siempre el filtro final por MultiPolygon.
- Los avisos de AEMET se cargan en memoria durante el arranque. Los focos NASA FIRMS se piden al backend cada vez que el visor se carga o recarga.
- La capa `landcover` se valida en arranque comprobando acceso a `pub.landcover_filtered`, `pub.landcover_mvt_source` y, si existe, `pub.landcover_mvt_class_source`.
- El visor renderiza `landcover` con `Leaflet.VectorGrid` sobre teselas `MVT` servidas por FastAPI desde PostGIS, usando `pub.landcover_mvt_class_source` hasta `z=8` y `pub.landcover_mvt_source` a partir de `z=9`.
- Las capas WMS se consultan desde servicios externos, por lo que su disponibilidad depende de esos proveedores.
