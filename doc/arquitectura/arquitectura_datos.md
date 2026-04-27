# Arquitectura de datos

## 1. Objetivo

Definir una arquitectura de datos homogénea para MeteoVisor que permita:

- integrar fuentes geoespaciales heterogéneas,
- almacenar los datos de forma trazable,
- servirlos de forma eficiente,
- separar ingestión, normalización y publicación,
- y preparar la evolución hacia consultas espaciales por `bbox`, detalle por entidad y publicación optimizada de capas.

Este documento recoge decisiones de arquitectura para su implementación posterior.

## 2. Principios

- El sistema debe tener un **store operativo principal** para explotación.
- Los formatos de origen no deben condicionar el modelo de explotación.
- Los datos crudos deben conservarse para trazabilidad y reproceso.
- La normalización debe producir estructuras homogéneas aunque el origen sea distinto.
- La explotación debe estar separada de la ingestión.
- El almacenamiento debe favorecer consultas espaciales eficientes, no solo intercambio de ficheros.

## 3. Decisión principal de almacenamiento

### 3.1 Store maestro

Se adopta **PostgreSQL + PostGIS** como **store principal de explotación**.

### 3.2 Justificación

PostGIS encaja mejor con los objetivos definidos en la arquitectura GIS del proyecto:

- almacenamiento de geometrías en un soporte consultable,
- índices espaciales,
- consultas por `bbox`,
- filtrado espacial,
- soporte para vistas materializadas y publicaciones derivadas,
- base adecuada para servir capas vectoriales y evolucionar a vector tiles.

### 3.3 Consecuencia arquitectónica

Los ficheros geográficos no deben ser el soporte principal en tiempo de ejecución salvo en fases de prototipo, importación o caché local muy controlada.

## 4. Papel del sistema de ficheros

El sistema de ficheros se mantiene como **zona de aterrizaje y archivo de datos crudos**, no como store operativo principal.

### 4.1 Qué se guarda en filesystem

Se conservarán en filesystem los artefactos originales o casi originales recibidos de cada fuente, por ejemplo:

- `CAP XML`
- `CSV`
- `GeoJSON`
- `GeoPackage`
- respuestas derivadas de `WMTS/WMS`
- snapshots descargados o generados durante procesos de ingesta

### 4.2 Para qué se conserva

- trazabilidad,
- reproceso,
- auditoría,
- comparación entre ejecuciones,
- depuración de incidencias,
- preservación del dato de origen sin reinterpretación.

### 4.3 Regla operativa

El **crudo original** se guarda en filesystem.  
La **BBDD no sustituye** a ese archivo bruto, sino al modelo de explotación.

## 5. Papel de la base de datos sobre los datos crudos

No todo el dato crudo debe cargarse íntegramente en tablas relacionales, pero sí debe existir un registro de ingesta y, cuando aporte valor, una proyección estructurada consultable.

### 5.1 Qué debe entrar siempre en BBDD

Como mínimo, cada ingesta debe registrar:

- identificador de ingesta,
- fuente,
- dataset,
- fecha/hora de captura,
- ruta del fichero bruto,
- hash de contenido,
- formato,
- estado del proceso,
- metadatos técnicos relevantes.

### 5.2 Qué entra además si compensa

Cuando sea útil para validación, cruce, deduplicación o explotación técnica, se almacenará también una versión estructurada del crudo:

- tablas `source_*`,
- atributos originales relevantes,
- geometría original o adaptada,
- campos de control de calidad,
- claves de deduplicación o versionado.

## 6. Modelo lógico por capas

Se adopta una arquitectura de datos en tres niveles.

En los pipelines de carga pesada se admite una capa tecnica adicional de `staging` dentro de PostgreSQL/PostGIS para desacoplar la carga masiva del contrato funcional de `source`.

### 6.1 Nivel `raw`

Datos crudos en filesystem.

Características:

- fidelidad máxima al origen,
- sin normalización semántica obligatoria,
- organizados por fuente, dataset y fecha de captura.

Ejemplo de estructura:

```text
raw/
  aemet/
  firms/
  ign/
  effis/
```

### 6.2 Nivel `source`

Representación estructurada por fuente en PostgreSQL/PostGIS.

Características:

- cercano al origen,
- conserva nombres de campo o semántica original cuando sea útil,
- permite control de calidad y trazabilidad,
- puede conservar geometrías cercanas al origen, incluso si todavía no son canónicas,
- sirve de puente entre el crudo y el modelo homogéneo.

Cuando la ingesta masiva lo requiera, `source` puede poblarse desde tablas `staging` cargadas en bloque con GDAL y consolidadas despues con SQL/PostGIS.

Ejemplos:

- `source_aemet_alert`
- `source_firms_hotspot`
- `source_ign_nucleo`
- `source_effis_detection`

### 6.3 Nivel `core`

Modelo de datos homogéneo del sistema.

Características:

- semántica común entre fuentes,
- campos unificados,
- geometrías normalizadas y, si hace falta, reparadas,
- pensado para consultas funcionales del visor y del backend.

Este nivel debe abstraer las diferencias de origen.

Para la PoC de `landcover`, `core` se materializa como una tabla canonica por feature, no como una geometria disuelta por clase. La disolucion y las simplificaciones orientadas a servicio quedan para `pub`.

En ese `core` de `landcover`:

- la geometria objetivo es `MultiPolygon` en `EPSG:4326`,
- las `MultiSurface` de `source` se linealizan antes de reparar,
- la invalidez topologica se repara en `core` sobre geometria poligonal linealizada,
- y la semantica se homogeneiza con un catalogo de clases y temas estable.

Ejemplos:

- `core_event`
- `core_observation`
- `core_feature_layer`
- `core_boundary`

### 6.4 Nivel `pub`

Estructuras optimizadas para servir al frontend o a servicios de mapas.

Características:

- vistas o tablas derivadas,
- payload mínimo,
- simplificación por escala,
- preparación para `bbox`, detalle o teselas vectoriales.

Ejemplos:

- `pub_alerts_current`
- `pub_fires_active`
- `pub_landcover_simplified_z8`
- `pub_boundary_spain`

Para la PoC de `landcover`, `pub` se concreta como `pub.landcover_filtered`.

Decisiones de esta PoC:

- `pub.landcover_filtered` es una vista materializada, no una vista simple.
- El motivo es que la simplificacion y el dissolve por clase tienen coste batch apreciable y no deben recalcularse por peticion.
- El pipeline de `pub` parte de `core.landcover_polygon`, simplifica cada feature con tolerancia `0.005`, agrega por `class_code` y persiste una geometria `MultiPolygon` en `EPSG:4326`.
- El payload publicado queda reducido a `feature_id`, `class_code`, `class_label`, `class_color`, `theme` y `geom`.
- Ese resultado es el equivalente funcional del `data/landcover.geojson` historico, pero separado del nivel canonico `core`.

Para la evolución a `vector tiles`, `pub` incorpora además una segunda publicación:

- `pub.landcover_mvt_source` como vista materializada por feature en `EPSG:3857`.
- Esta publicación no hace `dissolve` por clase; preserva una fila por feature para teselado vectorial.
- El payload publicado queda reducido a `core_feature_id`, `class_code`, `class_label`, `class_color`, `theme` y `geom`.
- Su finalidad es servir `MVT` desde el backend sin reproyectar `core` en cada petición.
- El render principal del visor puede apoyarse en esta publicación mientras `pub.landcover_filtered` se mantiene como salida GeoJSON agregada de compatibilidad.

## 7. Decisión sobre homogeneización

La homogeneización debe hacerse en `core`, no en `raw`.

Eso implica:

- mantener en `raw` y `source` la trazabilidad del origen,
- permitir en `source` geometrías todavía no canónicas, por ejemplo `MultiSurface` o features inválidas,
- definir en `core` un conjunto pequeño y estable de entidades,
- no forzar que todas las fuentes encajen artificialmente en el mismo esquema demasiado pronto.

La homogeneización debe ser suficiente para explotación común, no una pérdida innecesaria de información.

## 8. Tipos de datasets a distinguir

Para evitar ambigüedad, los datasets del sistema se clasificarán al menos en estas categorías:

### 8.1 Referencia espacial

Geometrías de soporte usadas para recorte, filtro o contexto.

Ejemplo:

- límite de España

### 8.2 Capa temática estática

Información geográfica de actualización poco frecuente.

Ejemplos:

- CORINE filtrado
- núcleos de población

### 8.3 Snapshot derivado

Capa local generada a partir de una fuente dinámica o ráster, pero almacenada como producto vectorial temporal.

Ejemplo:

- focos EFFIS vectorizados desde WMTS/WMS

### 8.4 Dato dinámico operacional

Información consultada periódicamente y normalizada para consumo del visor.

Ejemplos:

- avisos AEMET
- focos NASA FIRMS

## 9. Estrategia de servicio

La explotación debe salir del nivel `pub` o de vistas equivalentes sobre `core`.

### 9.1 Principio

No servir directamente:

- ficheros crudos,
- tablas `source`,
- datasets completos cuando el cliente solo necesita una ventana espacial o un subconjunto temático.

### 9.2 Objetivo de API

La API debe evolucionar hacia contratos como:

- metadatos de capas,
- consulta por `bbox`,
- detalle por entidad,
- colecciones filtradas,
- y, si compensa, tiles vectoriales o ráster cacheados.

## 10. Metadatos mínimos por dataset

Cada dataset incorporado al sistema debería registrar al menos:

- `dataset_id`
- `source_system`
- `dataset_type`
- `origin_format`
- `normalized_store`
- `geometry_type`
- `srid`
- `update_frequency`
- `capture_timestamp`
- `effective_timestamp` si aplica
- `license`
- `lineage`
- `quality_notes`

## 11. Decisiones ya adoptadas

### Decisión 1

El store operativo principal será **PostgreSQL + PostGIS**.

### Decisión 2

El filesystem se usará para conservar el **dato crudo original** y los artefactos de ingesta.

### Decisión 3

La BBDD almacenará siempre el **registro de ingesta** y, cuando aporte valor operativo, una representación estructurada del dato de origen.

### Decisión 4

La arquitectura de almacenamiento se organizará en niveles `raw`, `source`, `core` y `pub`.

### Decisión 5

La homogeneización principal del modelo se realizará en `core`.

## 12. Próximos pasos

1. Definir el catálogo de datasets inicial del proyecto.
2. Identificar para cada fuente su paso por `raw`, `source`, `core` y `pub`.
3. Diseñar el esquema mínimo de metadatos de ingesta.
4. Diseñar las primeras tablas `source_*`.
5. Proponer el modelo homogéneo `core_*`.
6. Diseñar los primeros endpoints sobre `pub`.

## 13. Cuestiones abiertas

- Qué entidades exactas formarán el modelo `core`.
- Qué datasets requieren versionado temporal explícito.
- Qué capas deben servirse como features y cuáles como tiles.
- Cuándo introducir GeoServer/MapServer y GeoWebCache.
- Qué política de refresco tendrá cada fuente.
