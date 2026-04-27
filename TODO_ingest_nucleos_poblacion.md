# TODO PoC de ingesta `núcleos de población`

## Objetivo

Definir y dejar documentado el plan para incorporar el dataset de `núcleos de población` al flujo GIS del proyecto con una arquitectura parecida a la de `landcover`:

- dato bruto en filesystem,
- ingestión reproducible a `PostgreSQL + PostGIS`,
- separación `staging` / `source` / `core` / `pub`,
- publicación eficiente para mapa,
- y visualización como capa extra en el visor web.

El objetivo funcional final es servir los polígonos de núcleos según entren en la ventana visible del mapa, priorizando `vector tiles (MVT)` para evitar cargar todo el dataset en cada navegación.

## Artefacto de entrada ya disponible

- ZIP bruto: `data-store/files/raw/ign/nucleos_poblacion/BTN_T_Poblaciones_gpkg.zip`
- GeoPackage contenido en el ZIP: `BTN_T_poblaciones.gpkg`

## Decisiones de partida

- El dato bruto de referencia se conservará en `data-store/files/raw/ign/nucleos_poblacion/`.
- La ingestión operativa se hará desde el `GeoPackage` incluido en el ZIP, no desde el `GeoJSON` histórico `data/nucleos.geojson`.
- Se reutilizará la tabla común `ingest.ingest_file` para trazabilidad de carga.
- La publicación orientada al visor será, salvo problema detectado en la inspección, `MVT` por teselas.
- El flujo previsto es:

```text
BTN_T_Poblaciones_gpkg.zip
  -> extracción canónica de BTN_T_poblaciones.gpkg
  -> staging
  -> source
  -> core
  -> pub
  -> endpoints FastAPI
  -> capa Leaflet/VectorGrid en frontend
```

## Identificadores propuestos

- `dataset_id`: `nucleos_poblacion_btn`
- `source_system`: `ign_btn`
- `origin_format`: `GPKG`

Estos nombres son propuestos y podrán ajustarse cuando se inspeccione el esquema exacto del `GeoPackage`.

## Fase 1. Inspección del dataset

- [ ] Abrir el ZIP y validar que contiene el `GeoPackage` esperado.
- [ ] Inspeccionar las capas reales del `.gpkg`.
- [ ] Confirmar nombre de capa, tipo de geometría y `SRID`.
- [ ] Identificar campos disponibles útiles para negocio y popup.
- [ ] Verificar si el dataset contiene todos los núcleos o ya viene filtrado.
- [ ] Comprobar si existe un campo de población utilizable para simbología o filtrado.
- [ ] Medir número aproximado de entidades y extensión espacial.
- [ ] Detectar posibles geometrías inválidas, vacías o multipartes complejas.

Resultado esperado:

- una ficha mínima del origen real que permita fijar el contrato de `source` y `core` sin suposiciones.

## Fase 2. Diseño de BBDD

- [ ] Reutilizar `ingest.ingest_file` para registrar cada carga del dataset.
- [ ] Crear estructuras `staging` específicas para la carga masiva desde GDAL.
- [ ] Crear tablas `source` cercanas al origen, conservando trazabilidad y campos clave.
- [ ] Crear una tabla `core` con geometría normalizada y atributos homogéneos para explotación.
- [ ] Crear estructuras `pub` orientadas a publicación en mapa.
- [ ] Añadir índices `GIST` y atributos auxiliares para consultas espaciales y servicio MVT.

Estructuras candidatas:

- `staging.nucleos_poblacion_raw`
- `source.nucleos_poblacion_btn`
- `core.nucleos_poblacion_polygon`
- `pub.nucleos_poblacion_mvt_source`

Publicaciones opcionales según rendimiento observado:

- `pub.nucleos_poblacion_filtered`
- `pub.nucleos_poblacion_mvt_overview`

## Fase 3. Script de ingesta desde ZIP/GPKG

- [ ] Crear `infra/ingest/import_nucleos_source.py`.
- [ ] Añadir validación de existencia del ZIP bruto.
- [ ] Extraer el `.gpkg` a una ruta canónica estable dentro de `data-store/files/raw/ign/nucleos_poblacion/`.
- [ ] Abrir el `GeoPackage` con GDAL/OGR.
- [ ] Cargar en bloque a `staging` con reproyección a `EPSG:4326` si hace falta.
- [ ] Consolidar desde `staging` a `source`.
- [ ] Registrar hash, tamaño, timestamps y metadatos de la carga en `ingest.ingest_file`.

Ruta canónica prevista para la extracción:

- `data-store/files/raw/ign/nucleos_poblacion/BTN_T_poblaciones.gpkg`

Variables útiles previstas:

- `RAW_ZIP`
- `EXTRACTED_GPKG_PATH`
- `GPKG_LAYER`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

## Fase 4. Normalización `source -> core`

- [ ] Definir qué campos del origen pasan a `core`.
- [ ] Convertir la geometría al tipo canónico que convenga para publicación.
- [ ] Reparar geometrías inválidas si aparecen.
- [ ] Homogeneizar nombres de atributos para el backend y el frontend.
- [ ] Decidir si se conserva una fila por feature original o si hay alguna agregación previa.
- [ ] Añadir un identificador técnico estable para detalle y popup.

Atributos candidatos en `core` si existen o se pueden derivar:

- `nombre`
- `habitantes`
- `codine`
- `cpro`
- `capital`
- `tipo`
- `latitud`
- `longitud`

## Fase 5. Publicación `pub`

- [ ] Crear la publicación principal `MVT` a partir de `core`.
- [ ] Evaluar si basta con una única fuente MVT por feature.
- [ ] Si el bajo zoom resulta pesado, crear una publicación adicional simplificada o agregada.
- [ ] Definir atributos mínimos que viajarán en cada tesela para estilo y popup.
- [ ] Analizar si hace falta una publicación GeoJSON de compatibilidad o si no aporta valor.

Decisión preferente de esta PoC:

- empezar con `pub.nucleos_poblacion_mvt_source` y añadir una variante overview solo si el rendimiento lo exige.

## Fase 6. Backend FastAPI

- [ ] Añadir funciones de consulta en `main.py`.
- [ ] Incorporar validación de disponibilidad de la capa en el arranque.
- [ ] Exponer metadatos de la capa.
- [ ] Exponer endpoint MVT.
- [ ] Añadir, si compensa, endpoint auxiliar por `bbox` para depuración o selección.
- [ ] Añadir, si compensa, endpoint de detalle por `feature_id`.

Endpoints previstos:

- `GET /api/layers/nucleos`
- `GET /api/nucleos/tiles/{z}/{x}/{y}.mvt`
- `GET /api/nucleos/features?bbox=minx,miny,maxx,maxy`
- `GET /api/nucleos/features/{id}`

## Fase 7. Frontend

- [ ] Añadir toggle de capa de `núcleos de población`.
- [ ] Integrar `Leaflet.VectorGrid` con la nueva URL MVT.
- [ ] Definir estilo base de polígonos y visibilidad por zoom.
- [ ] Definir popup con campos principales del núcleo.
- [ ] Añadir leyenda si aporta valor visual.
- [ ] Verificar convivencia visual con `landcover`, avisos y focos.

## Fase 8. Verificación final

- [ ] Verificar conteos de `source`, `core` y `pub`.
- [ ] Verificar que las teselas devuelven datos dentro de zonas urbanas conocidas.
- [ ] Probar navegación del mapa en distintos zooms.
- [ ] Revisar tiempos de respuesta en zoom bajo, medio y alto.
- [ ] Validar popup y estilo en frontend.
- [ ] Confirmar que el visor sigue funcionando en escritorio y móvil.

## Secuencia prevista de ejecución cuando hagamos la importación completa

1. `docker compose up -d postgres`
2. Aplicar SQL base nuevo para `source`, `core` y `pub`.
3. Ejecutar `docker compose run --rm gdal python3 /work/infra/ingest/import_nucleos_source.py`
4. Ejecutar `refresh_nucleos_core.sql`
5. Ejecutar `refresh_nucleos_pub.sql`
6. Ejecutar `refresh_nucleos_mvt.sql`
7. Verificar en base de datos y luego en el visor

## Decisiones pendientes antes de implementar

- [ ] Confirmar el nombre exacto de la capa dentro del `GeoPackage`.
- [ ] Decidir si se usarán todos los núcleos o algún filtro por tamaño/población.
- [ ] Decidir si la simbología dependerá de `habitantes`, `tipo` o un estilo único.
- [ ] Confirmar si necesitamos una fuente MVT simplificada para bajo zoom.
- [ ] Decidir si el `GeoJSON` histórico `data/nucleos.geojson` seguirá existiendo como salida auxiliar o quedará obsoleto.

## Resultado esperado al cerrar esta PoC

Una nueva capa temática de `núcleos de población` integrada en la arquitectura del proyecto, cargada desde `GeoPackage` a `PostGIS`, publicada de forma eficiente para mapa y visible en el frontend como capa adicional estable y reutilizable.
