---
id: TFG-20260604-retirada-pipeline-geopackage-mvt-landcover-corine-solo-wms
título: "Retirada del pipeline GeoPackage→MVT de landcover: CORINE pasa a servirse solo por WMS del IGN"
tipo: decisión
tags:
  - tfg
  - corine
  - landcover
  - arquitectura
  - limpieza
  - wms
  - meteovisor-demo
contexto: "Al revisar el estado real del visor se constató que la capa CORINE filtrada servida desde PostGIS como vector tiles (MVT) propios —generada a partir del GeoPackage CLC2018_ES.gpkg— NO se usaba: no se mostraba (la función de toggle no tenía ningún llamador en el frontend) ni se operaba (ninguna operación espacial la consultaba). Tanto la visualización general como la consulta puntual por foco se resuelven contra el WMS del IGN (LC.LandCoverSurfaces / GetFeatureInfo). En consecuencia se retira por completo el pipeline local GeoPackage→core→pub→MVT, dejando CORINE como capa WMS externa. Esta nota deja constancia de la decisión y supersede a las notas previas que asumían el flujo de vector tiles local."
fuente_existe: true
fuente_tipo: "elaboración propia (decisión de arquitectura + limpieza de código)"
fuente_descripción: "elaboración propia del autor del TFG: verificación exhaustiva de uso (frontend, backend, tools del chat, tests) y retirada del pipeline local de landcover en `meteovisor-demo`, conservando la vía WMS. Verificado que el visor sigue funcionando (backend arranca, WMS de landcover y resto de capas operativos) tras la retirada."
fuente_url: ""
autor_o_entidad: "autor del TFG"
fecha_fuente: "2026-06-04"
licencia_o_copyright: "uso académico del TFG"
condiciones_de_uso: "uso interno del TFG"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Si en el futuro se reactivara una capa de análisis filtrada de usos del suelo, habría que re-ingerir el GeoPackage y volver a publicar MVT; queda fuera del alcance actual."
---

# Retirada del pipeline GeoPackage→MVT de landcover

## 1. Hallazgo que motiva la decisión

La capa CORINE entraba al visor por dos vías independientes:

- **WMS del IGN** (`LC.LandCoverSurfaces`): cobertura general en el mapa **y** consulta puntual por foco vía `GetFeatureInfo` (endpoint `/api/landcover/point`, tool `landcoverAtPoint`). **Esta es la vía que el visor usa de verdad.**
- **Vector tiles MVT propios** desde PostGIS (`pub.landcover_mvt_source`), generados a partir de `data/CLC2018_ES.gpkg` filtrado a clases forestales/agrícolas. **Esta vía estaba muerta**: la función `toggleCorine` del frontend no tenía ningún llamador (la capa nunca se añadía al mapa) y ninguna operación espacial consultaba `core.landcover_polygon` / `pub.landcover_*`.

Es decir: se procesaba el GeoPackage y se mantenía toda la infraestructura local, pero **el resultado no se mostraba ni se operaba**.

## 2. Decisión

**Retirar por completo el pipeline local GeoPackage→core→pub→MVT de landcover.** CORINE queda como **capa WMS externa del IGN**, que ya cubre tanto la visualización general como la consulta puntual por foco. Esto supersede a [[decision-final-vector-tiles-para-landcover]] (que optaba por vector tiles propios) y se alinea con [[evolucion-consulta-puntual-landcover-de-core-a-getfeatureinfo-ign]] (que ya había movido la consulta puntual de `core` al WMS del IGN).

## 3. Qué se retiró (en `meteovisor-demo`)

- **Backend (`main.py`)**: 17 funciones auxiliares + 5 endpoints (`/api/landcover`, `/api/layers/landcover`, `/api/landcover/features`, `/api/landcover/features/{id}`, `/api/landcover/tiles`), el bloque de comprobación de landcover del *lifespan* y los globals de caché. Se conservó `/api/landcover/point` (proxy WMS GetFeatureInfo) y toda la familia `*_wms_*`.
- **Frontend (`app.js`)**: la capa MVT huérfana (`buildCorineLayer`, `toggleCorine`, `getCorineFeatureStyle`, tooltip de hover, rama de leyenda, `CORINE_CLASSES/LEGEND`, `CORINE_VECTOR_TILE_URL`). Se conservó `corine_wms`, el click WMS y el enriquecimiento foco↔uso del suelo.
- **Ingesta**: `generar_landcover.py`, `infra/ingest/import_landcover_source.py`, `verify_landcover_source_bbox.py`, y los SQL `refresh_landcover_*` / `verify_landcover_*`.
- **SQL de provisión**: `infra/postgres/initdb/002–005_landcover_*.sql` (los esquemas compartidos los crea `001_init.sql`, así que la provisión de una BD nueva no se rompe).
- **Datos**: `data/landcover.geojson` y `data/CLC2018_ES.gpkg` (2,9 GB).
- **Base de datos**: `DROP` de los objetos `source/staging/core/pub` de landcover.
- **Documentación**: limpieza de `README.md`, `infra/ingest/README.md`, `infra/postgres/README.md` y de la metadata muerta `TRACEABLE_LAYERS["corine"]`.

## 4. Qué NO se tocó
- La vía WMS de CORINE (visualización + `GetFeatureInfo`): intacta y operativa.
- La ingesta GeoPackage de **núcleos de población** y **carreteras IGR-RT** (otras capas vivas que también usan GeoPackage como origen).

## 5. Verificación
Backend arranca (`/api/chat/health` 200), `/api/landcover/point` (WMS) 200, `/api/nucleos/tiles` y `/api/layers/burnt-area` 200, endpoints retirados → 404. Frontend sin errores de consola (carga real verificada); 14 tests en verde. La memoria del TFG (`tfg-latex`) se actualizó en paralelo para no describir el pipeline retirado (Cuadros 3.3 y 3.4, prosa de metodología, cap. 4 y conclusiones).

## Datos explícitos
- CORINE se sirve solo por WMS del IGN tras esta retirada.
- Se eliminó el pipeline local (código backend/frontend, ingesta, SQL, datos y tablas de BD).
- Supersede a [[decision-final-vector-tiles-para-landcover]].

## Datos inferidos
- El trabajo de vectorización/MVT quedó como infraestructura no consumida; retirarlo simplifica el sistema y libera 2,9 GB.

## Datos faltantes o ambiguos
- Reactivación futura de una capa de análisis filtrada: requeriría rehacer ingesta + publicación MVT.
