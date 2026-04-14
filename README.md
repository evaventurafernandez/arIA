# MeteoVisor Demo

Demo web para visualizar avisos meteorologicos, focos de incendio y capas geograficas de riesgo en Espana. El proyecto combina una API con FastAPI y un frontend estatico basado en Leaflet.

## Que incluye

- Avisos meteorologicos activos de AEMET, obtenidos desde AEMET OpenData y parseados desde CAP XML.
- Focos de incendio de NASA FIRMS, filtrados para Espana y clasificados por FRP.
- Mapa interactivo con Leaflet, filtros por nivel y tipo de aviso, timeline y listado lateral.
- Capas WMS externas de EFFIS/Copernicus, inundaciones y CORINE Land Cover.
- Capa local `data/landcover.geojson` con usos forestales y agricolas filtrados de CORINE 2018.
- Script auxiliar para generar `data/nucleos.geojson` con nucleos de poblacion del IGN.

## Estructura

```text
.
|-- main.py                  # API FastAPI y servidor del frontend
|-- frontend/                # HTML, CSS y JavaScript del mapa
|-- data/                    # Datos GeoJSON locales generados
|-- generar_landcover.py     # Genera data/landcover.geojson desde CORINE
|-- generar_nucleos.py       # Descarga y genera data/nucleos.geojson desde IGN
|-- requirements.txt         # Dependencias Python principales
`-- .env                     # Variables locales de configuracion
```

## Requisitos

- Python 3.10 o superior.
- Una clave de AEMET OpenData.
- Opcionalmente, una clave de NASA FIRMS para cargar focos de incendio.

Instala las dependencias principales:

```bash
pip install -r requirements.txt
```

Los scripts de generacion de datos usan librerias geoespaciales adicionales como `geopandas`, `pandas` y `shapely`. Si necesitas regenerar esos ficheros, instalalas tambien en tu entorno.

## Configuracion

Crea un fichero `.env` en la raiz del proyecto con estas variables:

```env
AEMET_API_KEY=tu_clave_de_aemet
FIRMS_MAP_KEY=tu_clave_de_firms
```

`FIRMS_MAP_KEY` es opcional. Si no se informa, la API devolvera una lista vacia de focos de incendio.

## Preparar datos locales

El backend espera encontrar `data/landcover.geojson` para servir la capa CORINE filtrada:

```bash
python generar_landcover.py
```

Este script requiere tener disponible el fichero fuente `data/CLC2018_ES.gpkg` con las capas `CLC18_ES` y `CLC18_ES_Canarias`.

Para generar nucleos de poblacion desde la API-Features del IGN:

```bash
python generar_nucleos.py
```

## Ejecutar

Arranca el servidor con Uvicorn:

```bash
uvicorn main:app --reload
```

Despues abre:

```text
http://127.0.0.1:8000
```

## Endpoints

- `GET /api/alerts`: avisos meteorologicos cargados desde AEMET.
- `GET /api/fires`: focos de incendio cargados desde NASA FIRMS.
- `GET /api/stats`: resumen basico de avisos y focos por nivel.
- `GET /api/landcover`: GeoJSON local de CORINE filtrado.

El frontend se sirve desde la carpeta `frontend/` mediante `StaticFiles`.

## Notas

- Al iniciar la aplicacion, se carga una geometria de Espana para filtrar detecciones de FIRMS. Si falla la descarga, se usa una geometria de respaldo basada en bounding boxes.
- Los datos de AEMET y FIRMS se cargan en memoria durante el arranque de la aplicacion.
- Las capas WMS se consultan desde servicios externos, por lo que su disponibilidad depende de esos proveedores.
