# PoC Landcover End-to-End

## 1. Alcance

Este documento resume la implementación completa de la prueba de concepto de `landcover` desde el artefacto bruto hasta la capa de publicación.

El objetivo de esta PoC es demostrar una arquitectura de datos geoespaciales alineada con los principios de:

- separación entre ingestión y explotación,
- uso de `PostgreSQL + PostGIS` como store maestro,
- conservación del dato crudo en filesystem,
- y publicación derivada eficiente a partir de estructuras normalizadas.

## 2. Dataset tratado

- `dataset_id`: `landcover_corine_2018_filtered`
- `source_system`: `copernicus_corine_2018`
- `origin_format`: `FileGDB`
- artefacto bruto actual: [CLC2018_GDB.zip](/home/jose/tfg-eva/meteovisor-demo/data-store/files/CLC2018_GDB.zip)
- dataset interno: `CLC2018_ES.gdb`
- capas de entrada:
  - `CLC18_ES`
  - `CLC18_ES_Canarias`

Clases funcionales incluidas:

- `211`
- `242`
- `311`
- `312`
- `313`
- `321`
- `322`
- `323`
- `324`

## 3. Arquitectura implementada

La PoC queda organizada en cinco niveles operativos:

1. `raw`
2. `staging`
3. `source`
4. `core`
5. `pub`

### 3.1 Raw

El artefacto bruto se conserva en filesystem:

- [CLC2018_GDB.zip](/home/jose/tfg-eva/meteovisor-demo/data-store/files/CLC2018_GDB.zip)

Para la carga completa, el proceso lo descomprime en la ruta canónica:

- [CLC2018_ES.gdb](/home/jose/tfg-eva/meteovisor-demo/data-store/files/raw/copernicus/corine/landcover_corine_2018_filtered/2018/CLC2018_ES.gdb)

### 3.2 Staging

`staging` es una capa técnica de transición para la carga masiva.

Objetivo:

- desacoplar la entrada bulk con GDAL del contrato funcional de `source`

Tablas:

- `staging.landcover_clc18_es_raw`
- `staging.landcover_clc18_es_canarias_raw`

Campos principales:

- `source_objectid`
- `code_18`
- `geom`

Características:

- carga masiva con GDAL
- geometría ya reproyectada a `EPSG:4326`
- no es una capa de consumo

### 3.3 Source

`source` es la representación estructurada cercana al origen.

Tablas:

- `source.landcover_clc18_es`
- `source.landcover_clc18_es_canarias`
- vista unificada `source.landcover_corine_polygon`

Campos funcionales principales:

- `source_fid`
- `source_objectid`
- `ingest_id`
- `code_18`
- `imported_at`
- `geom`

Características:

- mantiene trazabilidad directa con el `FileGDB`
- conserva geometrías reproyectadas a `EPSG:4326`
- puede conservar geometrías no canónicas, incluidas `MultiSurface` o inválidas

### 3.4 Core

`core` es el modelo homogéneo y canónico.

Objetos principales:

- `core.landcover_class`
- `core.landcover_polygon`

`core.landcover_class` define el catálogo semántico:

- `class_code`
- `class_label`
- `class_color`
- `theme`
- `display_order`

`core.landcover_polygon` define la entidad canónica por feature:

- `dataset_id`
- `source_layer`
- `source_fid`
- `source_objectid`
- `ingest_id`
- `class_code`
- `class_label`
- `class_color`
- `theme`
- `imported_at`
- `canonicalized_at`
- `geom`

Características:

- geometría canónica `MultiPolygon`
- `EPSG:4326`
- reparación geométrica aplicada
- trazabilidad completa desde `source`

### 3.5 Pub

`pub` es la estructura derivada para explotación.

Objeto principal:

- `pub.landcover_filtered`

Tipo:

- vista materializada

Payload publicado:

- `feature_id`
- `class_code`
- `class_label`
- `class_color`
- `theme`
- `geom`

Características:

- simplificación por feature
- `dissolve` por `class_code`
- una fila por clase
- equivalente funcional al `data/landcover.geojson` histórico

## 4. Flujo implementado

### 4.1 Carga a source

El flujo implementado es:

1. leer ZIP bruto
2. extraer `FileGDB` si hace falta
3. registrar ingesta en `ingest.ingest_file`
4. cargar en bloque a `staging`
5. consolidar `source` desde `staging`

Script principal:

- [import_landcover_source.py](/home/jose/tfg-eva/meteovisor-demo/infra/ingest/import_landcover_source.py)

### 4.2 Normalización a core

El paso `source -> core`:

1. toma una fila de `source` por feature
2. mapea `code_18` con `core.landcover_class`
3. linealiza `MultiSurface` con `ST_CurveToLine`
4. repara geometrías con `ST_Buffer(geom, 0)`
5. canoniza el resultado a `MultiPolygon`

Scripts SQL:

- [003_landcover_core.sql](/home/jose/tfg-eva/meteovisor-demo/infra/postgres/initdb/003_landcover_core.sql)
- [refresh_landcover_core.sql](/home/jose/tfg-eva/meteovisor-demo/infra/ingest/refresh_landcover_core.sql)

### 4.3 Derivación a pub

El paso `core -> pub`:

1. simplifica cada feature con tolerancia `0.005`
2. agrupa por clase
3. hace `dissolve`
4. persiste una geometría `MultiPolygon` publicada

Scripts SQL:

- [004_landcover_pub.sql](/home/jose/tfg-eva/meteovisor-demo/infra/postgres/initdb/004_landcover_pub.sql)
- [refresh_landcover_pub.sql](/home/jose/tfg-eva/meteovisor-demo/infra/ingest/refresh_landcover_pub.sql)

## 5. Ejecución operativa

### 5.1 Arranque de base de datos

```bash
docker compose up -d postgres
```

### 5.2 Carga completa a source

```bash
docker compose run --rm gdal python3 /work/infra/ingest/import_landcover_source.py
```

### 5.3 Reconstrucción de core

```bash
docker compose exec -T postgres psql -U ${POSTGRES_USER:-meteovisor} -d ${POSTGRES_DB:-meteovisor} < infra/ingest/refresh_landcover_core.sql
```

### 5.4 Reconstrucción de pub

```bash
docker compose exec -T postgres psql -U ${POSTGRES_USER:-meteovisor} -d ${POSTGRES_DB:-meteovisor} < infra/ingest/refresh_landcover_pub.sql
```

## 6. Validación obtenida

### 6.1 Source

Resultado validado sobre carga completa:

- `CLC18_ES`: `150756`
- `CLC18_ES_Canarias`: `859`
- total: `151615`

### 6.2 Core

Resultado validado:

- total: `151615`
- `missing_trace_rows`: `0`
- `invalid_geom`: `0`
- `non_multipolygon`: `0`
- `wrong_srid`: `0`

### 6.3 Pub

Resultado validado:

- total: `9`
- `missing_pub_classes`: `0`
- `invalid_geom`: `0`
- `non_multipolygon`: `0`
- `wrong_srid`: `0`

Comparación funcional:

- mismo número de clases que `data/landcover.geojson`
- misma extensión funcional
- mismo conjunto de `class_code` y `class_color`

## 7. Decisiones relevantes

### 7.1 Por qué existe staging

Porque la carga bulk directa a `source` complicaba:

- el rendimiento,
- el control del `FID`,
- y la separación entre carga técnica y contrato funcional.

### 7.2 Por qué core no hace dissolve

Porque `core` representa la entidad homogénea por feature y debe conservar trazabilidad y granularidad. La agregación temática es una decisión de publicación y por eso vive en `pub`.

### 7.3 Por qué pub es vista materializada

Porque:

- la simplificación tiene coste,
- el `dissolve` por clase tiene coste,
- y ambos son cálculos batch, no apropiados para recomputarse por petición.

## 8. Limitaciones abiertas

- Falta endurecer tests automáticos más allá del smoke test SQL.
- Falta medir formalmente tiempos y tamaño de salida de `pub`.
- Falta decidir si habrá una segunda publicación por escala.
- Falta cerrar la licencia/atribución exacta del origen en la documentación final.

## 9. Ficheros clave

- [docker-compose.yml](/home/jose/tfg-eva/meteovisor-demo/docker-compose.yml)
- [README.md](/home/jose/tfg-eva/meteovisor-demo/infra/ingest/README.md)
- [import_landcover_source.py](/home/jose/tfg-eva/meteovisor-demo/infra/ingest/import_landcover_source.py)
- [001_init.sql](/home/jose/tfg-eva/meteovisor-demo/infra/postgres/initdb/001_init.sql)
- [002_landcover_source.sql](/home/jose/tfg-eva/meteovisor-demo/infra/postgres/initdb/002_landcover_source.sql)
- [003_landcover_core.sql](/home/jose/tfg-eva/meteovisor-demo/infra/postgres/initdb/003_landcover_core.sql)
- [004_landcover_pub.sql](/home/jose/tfg-eva/meteovisor-demo/infra/postgres/initdb/004_landcover_pub.sql)
- [refresh_landcover_core.sql](/home/jose/tfg-eva/meteovisor-demo/infra/ingest/refresh_landcover_core.sql)
- [refresh_landcover_pub.sql](/home/jose/tfg-eva/meteovisor-demo/infra/ingest/refresh_landcover_pub.sql)
- [TODO_ingest_landcover.md](/home/jose/tfg-eva/meteovisor-demo/TODO_ingest_landcover.md)
