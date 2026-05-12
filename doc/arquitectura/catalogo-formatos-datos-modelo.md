# Catálogo de formatos de datos del modelo

## Alcance

Este documento describe los formatos de datos que maneja la implementación actual de MeteoVisor Demo a partir del código de `main.py`, los scripts de generación y los ficheros locales presentes en `data/`.

El objetivo no es definir un modelo ideal, sino documentar el modelo real que hoy usa la aplicación. El foco está en los datos estáticos o semiestáticos que se almacenan localmente y se sirven al frontend.

## Resumen

El sistema trabaja con varios formatos de entrada heterogéneos, pero converge casi siempre en dos formas de representación:

1. Diccionarios JSON normalizados en memoria para datos dinámicos de avisos y focos.
2. `GeoJSON FeatureCollection` como formato canónico para capas geográficas locales.

En la práctica, `GeoJSON` es el formato dominante del modelo para capas estáticas.

## Inventario de formatos

| Elemento | Naturaleza | Formato de origen | Formato consumido/publicado | Observaciones |
| --- | --- | --- | --- | --- |
| Avisos AEMET | Dinámico | `tar`/`gzip` con ficheros `CAP XML` | Lista JSON de objetos normalizados | Se carga al arrancar el backend |
| Focos NASA FIRMS | Dinámico | `CSV` remoto | Lista JSON de objetos normalizados | Se consulta en vivo al abrir el visor |
| Límite de España | Estático local | `GeoJSON` | `GeoJSON FeatureCollection` | Se usa para filtro espacial y recorte visual |
| CORINE filtrado | Estático generado | `GPKG` | `GeoJSON FeatureCollection` | Capa temática simplificada y disuelta |
| Núcleos de población | Estático generado | API Features IGN en JSON | `GeoJSON FeatureCollection` | Dataset auxiliar, hoy no conectado al visor |
| Capas externas EFFIS/MITECO/IGN | Dinámico externo | `WMS` | Teselas ráster `PNG` | Se consumen directamente en Leaflet |

## Modelo lógico actual

No existe un paquete de modelos o esquemas tipados explícitos. El modelo está repartido entre:

- normalizadores ad hoc en `main.py`,
- contratos implícitos en los scripts de generación,
- y supuestos de consumo en `frontend/app.js`.

Esto significa que el contrato de datos actual es implícito y está definido por nombres de campo, no por clases Pydantic o esquemas JSON formales.

## Datos estáticos y semiestáticos

### 1. Límite territorial de España

**Fichero:** `data/boundaries/spain_nuts_2024_01m.geojson`

**Tipo real actual:** `FeatureCollection`

**Geometría observada:** `MultiPolygon`

**Claves de nivel superior observadas:**

- `type`
- `name`
- `source`
- `features`

**Propiedades observadas en las features:**

- `CNTR_CODE`
- `COAST_TYPE`
- `LEVL_CODE`
- `MOUNT_TYPE`
- `NAME_LATN`
- `NUTS_ID`
- `NUTS_NAME`
- `URBN_TYPE`

**Uso en el sistema:**

- Se carga en backend para construir una geometría Shapely única usada por `is_in_spain`.
- Se expone en `/api/boundaries/spain`.
- Se carga también en frontend para recortar visualmente capas WMS de EFFIS al contorno de España.

**Rol en el modelo:**

No es una capa temática de negocio, sino una geometría de soporte para filtro espacial y clipping.

### 2. CORINE filtrado

**Fichero:** `data/landcover.geojson`

**Origen:** `data/CLC2018_ES.gpkg`, capas `CLC18_ES` y `CLC18_ES_Canarias`

**Script generador:** `generar_landcover.py`

**Tipo real actual:** `FeatureCollection`

**Número de features observado:** `9`

**Geometría observada:** `MultiPolygon`

**Propiedades observadas en las features:**

- `CODE_18`
- `color`
- `label`

**Transformación aplicada:**

- filtrado por códigos CORINE de interés,
- reproyección a `EPSG:4326`,
- simplificación geométrica,
- `dissolve` por clase,
- exportación a GeoJSON.

**Semántica del dataset:**

Cada feature representa una clase temática agregada, no una tesela ni una entidad administrativa. El dataset es una cartografía temática ya reducida al subconjunto que interesa al visor.

**Rol en el modelo:**

Es el principal ejemplo de capa estática temática normalizada a un formato de intercambio simple.

### 3. Núcleos de población

**Fichero:** `data/nucleos.geojson`

**Origen:** API-Features del IGN

**Script generador:** `generar_nucleos.py`

**Tipo real actual:** `FeatureCollection`

**Número de features observado:** `6237`

**Geometría observada:** `MultiPolygon`

**Propiedades observadas en las features:**

- `nombre`
- `habitantes`
- `codine`
- `cpro`
- `capital`
- `tipo`
- `latitud`
- `longitud`

**Transformación aplicada:**

- descarga paginada,
- filtrado por `habitantes >= 500`,
- simplificación geométrica,
- exportación a GeoJSON.

**Rol en el modelo:**

Dataset auxiliar preparado para integrarse, pero actualmente no aparece conectado a endpoints ni al frontend.

## Datos dinámicos normalizados en JSON

### 4. Avisos AEMET

**Formato de entrada:** `CAP XML` empaquetado en `tar` comprimido con `gzip`

**Normalización en backend:** `parse_cap_xml`

**Formato expuesto:** lista JSON de objetos con esta estructura lógica:

- `id`
- `event`
- `level`
- `level_color`
- `area_name`
- `description`
- `instruction`
- `onset`
- `expires`
- `polygon`
- `source`

**Observación:**

El campo `polygon` no se convierte a GeoJSON, sino que se conserva como cadena CAP y se parsea después en el frontend.

### 5. Focos NASA FIRMS

**Formato de entrada:** `CSV`

**Normalización en backend:** `parse_firms_csv`

**Formato expuesto:** lista JSON de objetos con al menos estos campos:

- `id`
- `latitude`
- `longitude`
- `bright_ti4`
- `scan`
- `track`
- `acq_date`
- `acq_time`
- `satellite`
- `confidence`
- `version`
- `bright_ti5`
- `frp`
- `daynight`
- `level`
- `level_color`
- `acq_datetime_utc`
- `source`
- `firms_source`
- `query_area`

**Observación:**

Aquí sí hay una normalización semántica explícita: clasificación por `FRP`, deduplicación y filtrado espacial contra el GeoJSON local de España.

## Formatos externos consumidos directamente

### 6. Teselas WMS

El frontend consume varias capas ráster externas:

- EFFIS `mf010.fwi`
- EFFIS `mf010.dc`
- MITECO `NZ.Flood.FluvialT100`
- IGN `LC.LandCoverSurfaces`

En estos casos el modelo local no almacena entidades ni atributos. Solo se manejan parámetros de capa, opacidad, versión y, en algunos casos, clipping visual contra España.

## Conclusiones de la revisión

### 1. GeoJSON es el formato canónico de las capas estáticas

Todas las capas geográficas locales relevantes del proyecto convergen en `GeoJSON FeatureCollection`, incluso cuando el origen real es muy distinto (`GPKG`, API JSON).

### 2. El modelo actual está orientado a consumo, no a tipado formal

Los contratos están pensados para que el visor funcione con poco procesamiento adicional, pero no están centralizados en esquemas reutilizables. El resultado es práctico, aunque deja el modelo repartido entre backend, scripts y frontend.

### 3. Hay dos tipos principales de dato estático local

Conviene distinguirlos en la documentación del TFG:

- **Estático de referencia:** límite de España.
- **Estático temático generado:** CORINE filtrado, núcleos.

Meterlos en la misma categoría que los datos dinámicos puede ocultar diferencias importantes de trazabilidad y caducidad.

### 4. Hay una oportunidad clara de normalización

Si el proyecto evoluciona, tiene sentido definir un pequeño catálogo formal de datasets con:

- identificador del dataset,
- origen,
- formato de entrada,
- formato normalizado,
- campos obligatorios,
- frecuencia de actualización,
- consumidor principal.

La base ya existe en la implementación; falta hacerla explícita.
