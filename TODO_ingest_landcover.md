# TODO PoC de ingesta `landcover`

## Objetivo

Definir y ejecutar una prueba de concepto completa para sustituir el flujo actual:

- origen `FileGDB` empaquetado en ZIP en filesystem,
- transformación con `generar_landcover.py`,
- salida final `GeoJSON` local,

por un flujo alineado con la arquitectura objetivo:

- `raw` en filesystem,
- ingestión a `PostgreSQL + PostGIS`,
- separación `source` / `core` / `pub`,
- preparación para servir datos de forma eficiente en fases posteriores.

Este documento recoge las tareas necesarias para construir esa PoC.  
El alcance termina en dejar lista la base de datos, el pipeline de ingesta y la estructura de datos.  
La publicación eficiente de servicios queda fuera de esta fase, pero debe condicionar el diseño.

## Referencias de arquitectura

- [arquitectura_gis.md](/home/jose/tfg-eva/meteovisor-demo/doc/arquitectura/arquitectura_gis.md)
- [arquitectura_datos.md](/home/jose/tfg-eva/meteovisor-demo/doc/arquitectura/arquitectura_datos.md)
- [catalogo-formatos-datos-modelo.md](/home/jose/tfg-eva/meteovisor-demo/doc/arquitectura/catalogo-formatos-datos-modelo.md)
- [catalogo_dataset_landcover_corine_2018_filtered.md](/home/jose/tfg-eva/meteovisor-demo/doc/arquitectura/catalogo_dataset_landcover_corine_2018_filtered.md)
- [generar_landcover.py](/home/jose/tfg-eva/meteovisor-demo/generar_landcover.py)

## Criterios de diseño de la PoC

- Usar como base principal las herramientas recogidas en `arquitectura_gis.md`.
- Adoptar `PostgreSQL + PostGIS` como store maestro.
- Usar GDAL desde Python para la carga inicial filtrada desde `FileGDB` a PostGIS.
- Para la carga completa, usar la secuencia `ZIP -> FileGDB extraido -> staging -> source`.
- Ejecutar la infraestructura de BBDD mediante Docker.
- Garantizar compatibilidad de ejecución tanto en Linux como en Windows.
- Separar claramente ingestión, normalización y publicación.
- Mantener el artefacto bruto `FileGDB` empaquetado como dato crudo de referencia.
- Diseñar la PoC de forma que sea reutilizable para otros datasets.
- Incorporar tests en cada fase cuando sean aplicables y proporcionen verificación real.
- Hacer commit al cerrar cada fase, solo después de verificar que esa fase está completa.

## Restricciones operativas fijadas

- La gestión de la BBDD debe hacerse con Docker.
- La solución debe poder ejecutarse en Linux y en Windows.
- El datastore de ficheros debe vivir en `./data-store/files`.
- El volumen persistente de PostgreSQL debe vivir en `./data-store/postgres/data`.
- Ambos directorios deben quedar excluidos del control de versiones.

## Estado actual de partida

El flujo actual hace esto:

1. Lee `data/CLC2018_ES.gpkg`.
2. Consume las capas `CLC18_ES` y `CLC18_ES_Canarias`.
3. Filtra un subconjunto de clases `CODE_18`.
4. Reproyecta a `EPSG:4326`.
5. Simplifica geometrías.
6. Hace `dissolve` por clase.
7. Añade `label` y `color`.
8. Exporta a `data/landcover.geojson`.

La PoC debe convertir ese flujo en uno basado en BBDD y dejar claro qué parte pertenece a `source`, cuál a `core` y cuál a `pub`.

## Decisiones asumidas para esta PoC

- El artefacto bruto principal de esta PoC es `data-store/files/CLC2018_GDB.zip`.
- La primera carga a BBDD se hará desde `FileGDB` dentro del ZIP, no desde `GeoJSON`.
- El filtrado funcional principal debe hacerse en la primera carga, antes de persistir en PostGIS.
- La carga completa eficiente se hará descomprimiendo primero el `FileGDB` a una ruta canónica y cargando en bloque a `staging`.
- La PoC debe modelar `landcover` como **capa temática estática**.
- El nombre lógico del dataset es `landcover_corine_2018_filtered`.
- La organización `raw` usará como artefacto bruto principal `./data-store/files/CLC2018_GDB.zip`.
- El artefacto bruto se conservará por copia, no por enlace simbólico.
- La homogeneización semántica debe quedar reflejada en tablas o vistas `core`.
- Debe existir una capa `pub` preparada para futuras consultas eficientes aunque aún no se exponga por API.
- La BBDD se levantará con contenedores Docker y persistencia en ruta del repo.
- La definición del entorno debe evitar dependencias de rutas no portables entre Linux y Windows.

## Bloque 1. Definir el dataset en el catálogo

- [x] Crear la ficha del dataset `landcover_corine_2018_filtered`.
- [x] Definir `dataset_id`, `source_system`, `dataset_type`, `origin_format` y `update_frequency`.
- [ ] Confirmar la licencia/atribución exacta del origen si se va a publicar fuera del repo.
- [x] Registrar que el artefacto bruto actual para la PoC es `data-store/files/CLC2018_GDB.zip`.
- [x] Registrar que las capas de entrada son `CLC18_ES` y `CLC18_ES_Canarias`.
- [x] Registrar que el subconjunto temático actual está definido por `CODE_18`.
- [x] Documentar que la salida funcional actual es equivalente a `data/landcover.geojson`.
- [x] Fijar la categoría del dataset como `capa_tematica_estatica`.

Estado del bloque:

- Resuelto el catálogo operativo del dataset.
- Pendiente de verificación externa: la licencia/atribución exacta del origen si se va a publicar fuera del repo.

## Bloque 2. Diseñar la organización `raw`

- [x] Fijar `./data-store/files` como raíz canónica del almacenamiento bruto.
- [x] Decidir una convención de rutas por fuente, dataset y versión.
- [x] Diseñar la estructura interna bajo `./data-store/files`, por ejemplo `raw/<source>/<dataset>/<version>/`.
- [x] Mover o referenciar el artefacto bruto bajo esa estructura.
- [x] Definir si el artefacto bruto se almacenará por copia, por enlace o por convención de ubicación estable.
- [x] Añadir metadatos mínimos del artefacto crudo:
  - hash,
  - tamaño,
  - timestamp de captura o incorporación,
  - formato,
  - capas incluidas.
- [x] Definir cómo se valida que el fichero existe y contiene las capas esperadas.

Estado del bloque:

- Resuelta la convención `raw` para la PoC.
- El `FileGDB` empaquetado queda identificado como artefacto de referencia de entrada, no como producto transformado.

## Bloque 3. Diseñar el registro de ingesta en BBDD

- [x] Diseñar una tabla general de control de ingestas, por ejemplo `ingest_file`.
- [x] Definir al menos estos campos:
  - `ingest_id`,
  - `dataset_id`,
  - `source_system`,
  - `origin_format`,
  - `file_path`,
  - `content_hash`,
  - `captured_at`,
  - `ingested_at`,
  - `status`,
  - `metadata_json`.
- [x] Definir una política de estados de ingesta:
  - `pending`,
  - `running`,
  - `ok`,
  - `failed`.
- [x] Definir qué errores se registran y en qué formato.
- [x] Definir si la tabla de control será común a todos los datasets desde el primer momento.

## Bloque 4. Diseñar la estructura de BBDD

### 4.1 Preparación de PostgreSQL/PostGIS

- [x] Crear la instancia local de PostgreSQL mediante Docker.
- [x] Instalar y habilitar la extensión PostGIS.
- [x] Fijar `./data-store/postgres/data` como directorio persistente del clúster PostgreSQL.
- [x] Diseñar `docker-compose` para levantar la BBDD de forma reproducible.
- [ ] Verificar que el montaje de volúmenes funciona en Linux y en Windows.
- [x] Evitar dependencias de shell o rutas que solo funcionen en uno de los dos sistemas.
- [x] Decidir naming de schemas.
- [x] Crear al menos los schemas:
  - `ingest`,
  - `source`,
  - `core`,
  - `pub`.
- [x] Definir una estrategia inicial de migraciones basada en bootstrap SQL versionado.
- [x] Decidir cómo se versionará la estructura de BBDD dentro del repo.

Estado del bloque:

- Resuelta la infraestructura base de PostgreSQL/PostGIS para la PoC.
- Resuelto el bootstrap de schemas base y el enfoque inicial de migraciones.
- Pendiente solo la verificación real del montaje de volúmenes en Linux y Windows.

### 4.2 Tabla `source`

- [x] Diseñar la tabla `source.landcover_corine_polygon`.
- [x] Asegurar que `source` solo reciba el subconjunto funcional necesario, no la capa completa original.
- [x] Decidir si la carga se hará en una sola tabla unificada o en tablas separadas por capa de origen.
- [x] Incluir los atributos originales necesarios del FileGDB.
- [x] Conservar al menos:
  - identificador técnico,
  - capa de origen,
  - `CODE_18`,
  - trazabilidad de ingesta efectiva mediante `ingest.ingest_file`,
  - geometría reproyectada a `EPSG:4326`,
  - metadatos de ingesta.
- [x] Decidir que `source` no conserva geometría original sin simplificar; esa referencia queda en `raw` y la geometría de trabajo vive ya reproyectada en `source`.
- [x] Crear índice espacial `GiST`.
- [x] Crear índices adicionales sobre `CODE_18` y campos de trazabilidad que se consulten.
- [x] Definir una vista unificada `source.landcover_corine_polygon` con `source_layer` derivado del origen físico.
- [x] Definir una estructura mínima en `source` con `source_fid`, `ingest_id`, `code_18`, `imported_at` y `geom` reproyectada a `EPSG:4326`.

### 4.2 bis Tabla `staging`

- [x] Diseñar tablas `staging` simples para recibir la carga masiva desde GDAL.
- [x] Definir `staging.landcover_clc18_es_raw` y `staging.landcover_clc18_es_canarias_raw`.
- [x] Incluir en `staging` solo los campos mínimos para transición a `source`:
  - `source_objectid`,
  - `code_18`,
  - `geom`.
- [x] Reproyectar ya en la carga bulk para dejar `staging` y `source` en `EPSG:4326`.
- [x] Añadir índices mínimos sobre geometría, `code_18` y `source_objectid`.
- [x] Fijar que `staging` es zona técnica de transición y no contrato funcional.

### 4.3 Tabla o vista `core`

- [x] Diseñar la estructura `core` para representar una capa temática homogénea.
- [x] Decidir si `landcover` entra en una tabla genérica tipo `core_feature_layer` o en una tabla específica de PoC.
- [x] Definir los campos semánticos mínimos:
  - `dataset_id`,
  - `feature_id`,
  - `class_code`,
  - `class_label`,
  - `class_color`,
  - `theme`,
  - `geometry`.
- [x] Normalizar `CODE_18` a una semántica estable de negocio.
- [x] Definir si `theme` debe valer algo como `forest_agriculture`.
- [x] Registrar la procedencia desde `source`.
- [x] Crear índice espacial `GiST`.

Estado del bloque:

- Resuelto `core.landcover_polygon` como tabla canonica especifica de la PoC con una fila por feature de `source`.
- Resuelto el catalogo semantico `core.landcover_class` para `CODE_18 -> label/color/theme`.
- Resuelta la canonizacion geometrica a `MultiPolygon` valido en `EPSG:4326`.
- Resuelta la trazabilidad minima por `source_layer`, `source_fid`, `source_objectid` e `ingest_id`.
- Pendiente para fases posteriores la derivacion `pub` con `dissolve` y simplificacion.

### 4.4 Tabla o vista `pub`

- [ ] Diseñar `pub.landcover_filtered`.
- [ ] Decidir si `pub` será tabla materializada, vista materializada o vista simple en esta PoC.
- [ ] Reflejar en `pub` el resultado funcional actual equivalente al `GeoJSON` de salida.
- [ ] Incluir solo los campos mínimos para explotación posterior:
  - `feature_id`,
  - `class_code`,
  - `class_label`,
  - `class_color`,
  - `geometry`.
- [ ] Diseñar una versión simplificada para escala media o baja.
- [ ] Evaluar una segunda publicación por nivel de simplificación, aunque no se exponga todavía.

## Bloque 5. Diseñar la transformación del dato

- [x] Traducir el comportamiento actual de `generar_landcover.py` a operaciones reproducibles en el pipeline de ingesta con GDAL Python y PostGIS.
- [x] Definir dónde se hace cada transformación:
  - carga inicial con GDAL Python,
  - filtrado temático en la primera carga,
  - reproyección,
  - simplificación,
  - disolución por clase,
  - enriquecimiento con `label` y `color`.
- [x] Fijar como criterio que PostGIS no recibirá la capa CORINE completa, sino solo las features filtradas por `CODE_18`.
- [x] Decidir si la simplificación se hace en `core`, en `pub` o en ambas.
- [x] Decidir si el `dissolve` por clase pertenece al nivel `pub` en lugar de `source`.
- [x] Definir el mapping oficial de `CODE_18 -> label, color`.
- [x] Extraer ese mapping del script actual a un recurso reutilizable.
- [ ] Definir cómo se asegura reproducibilidad del resultado respecto al flujo actual.

## Bloque 6. Diseñar el pipeline técnico de ingesta

- [x] Definir la importación inicial con GDAL Python aplicando ya el filtro funcional.
- [x] Sustituir la carga completa feature-a-feature por una carga bulk a `staging`.
- [ ] Decidir si la carga se hará por capa o mediante una carga unificada.
- [x] Decidir dónde se ejecutará el importador GDAL Python:
  - en el host,
  - en un contenedor auxiliar,
  - o dentro de una imagen de herramientas de ingesta.
- [ ] Priorizar una opción reproducible en Linux y Windows.
- [x] Definir las opciones GDAL de importación para:
  - conexión a PostGIS,
  - nombre de tabla destino,
  - geometría,
  - reproyección si aplica,
  - overwrite o append,
  - promoción a multi geometría si hace falta.
- [x] Definir cómo aplicar en GDAL Python:
  - selección de layer,
  - filtro por `CODE_18`,
  - selección mínima de columnas,
  - reproyección.
- [x] Diseñar el paso de poscarga en SQL para consolidar ambas capas filtradas en `source`.
- [x] Implementar extracción controlada del ZIP a una ruta canónica para evitar acceso pesado sobre `/vsizip` en la carga completa.
- [ ] Diseñar el paso SQL para construir `core`.
- [ ] Diseñar el paso SQL para construir `pub`.
- [ ] Definir si la orquestación se implementará con:
  - script shell,
  - script Python,
  - Python + GDAL.
- [ ] Si hay scripts de automatización, asegurar una alternativa portable para Linux y Windows.
- [x] Mantener como preferencia la combinación más cercana a la arquitectura objetivo: `GDAL Python + PostGIS`.
- [x] Encapsular la importación en `infra/ingest/import_landcover_source.py` y añadir el servicio `gdal` en Docker Compose.
- [ ] Ejecutar la importación real completa con `data-store/files/CLC2018_GDB.zip` usando la vía bulk `staging -> source` y dejar su tiempo registrado.
- [x] Diseñar el paso SQL para construir `core`.

## Bloque 7. Calidad y validación

- [x] Verificar de forma mecánica que el bootstrap SQL crea `ingest`, `source` y la vista unificada.
- [x] Verificar de forma mecánica la existencia de índices y tablas de `source` con consultas SQL directas.
- [x] Verificar la importación real completa con datos sobre `data-store/files/CLC2018_GDB.zip` usando la vía bulk.

- [x] Verificar que las dos capas del `FileGDB` se cargan correctamente.
- [x] Verificar que el filtro en GDAL Python excluye todas las clases no objetivo antes de persistir en PostGIS.
- [x] Verificar que no se pierden las geometrías válidas de las clases objetivo en la carga.
- [x] Verificar que el SRID queda unificado.
- [x] Verificar que todas las features esperadas con `CODE_18` objetivo aparecen en `source`.
- [x] Verificar que la trazabilidad de ingesta queda registrada en `ingest.ingest_file` y enlazada desde `source`.
- [x] Verificar que `core` contiene la semántica homogénea esperada.
- [ ] Verificar que `pub` reproduce el conjunto final actual.
- [ ] Comparar el resultado de `pub` con el `GeoJSON` generado por `generar_landcover.py`.
- [ ] Medir al menos:
  - número de features,
  - tipos geométricos,
  - extensión espacial,
  - tiempos de carga,
  - tamaño de salida aproximado.
- [x] Validar geometrías con herramientas de PostGIS.

## Bloque 7 bis. Tests

- [ ] Identificar qué partes de la PoC admiten tests automáticos útiles.
- [ ] Definir tests mínimos para el pipeline de ingestión cuando sea aplicable.
- [ ] Añadir tests de validación del mapping `CODE_18 -> label, color`.
- [ ] Añadir tests o comprobaciones automatizadas para verificar que solo se cargan las clases objetivo.
- [ ] Añadir tests o comprobaciones automatizadas sobre el número esperado de clases publicadas en `pub`.
- [x] Añadir tests de esquema mínimos para comprobar existencia de tablas, vistas, índices y schemas esperados.
- [ ] Añadir tests o validaciones de compatibilidad del flujo Docker cuando sea razonable automatizarlos.
- [ ] Documentar qué comprobaciones quedan fuera de tests automáticos y se validan manualmente.
- [x] Definir el comando único o conjunto mínimo de comandos para ejecutar la validación de la fase.

## Bloque 8. Preparación para servicio eficiente futuro

Aunque esta fase no implementa servicios, hay que dejar la PoC preparada para ellos.

- [ ] Asegurar que `pub` no depende de campos innecesarios.
- [ ] Asegurar que hay geometrías aptas para consultas por `bbox`.
- [ ] Dejar preparada una vista compatible con un futuro `/features?bbox=...`.
- [ ] Definir una posible clave de entidad estable para detalle por feature.
- [ ] Evaluar si conviene una versión simplificada adicional para mapas a pequeña escala.
- [ ] Evaluar si el `dissolve` actual responde a una necesidad real de visualización o si perjudica la futura interacción por feature.
- [ ] Documentar qué parte del diseño está pensada para GeoServer / MapServer en una fase posterior.

## Bloque 9. Entregables técnicos de la PoC

- [ ] Documento de catálogo del dataset actualizado.
- [ ] Definición Docker reproducible para PostgreSQL + PostGIS.
- [ ] Esquema inicial de BBDD con `ingest`, `source`, `core` y `pub`.
- [ ] Scripts o migraciones de creación de tablas y vistas.
- [x] Script Python de ingesta desde `FileGDB` a PostGIS.
- [x] Estructura `staging` y consolidación SQL a `source`.
- [ ] Mapping reutilizable de clases CORINE seleccionadas.
- [ ] Tests y validaciones automatizadas aplicables a la PoC.
- [ ] Validación comparativa con la salida actual `landcover.geojson`.
- [ ] Documento breve del flujo extremo a extremo de la PoC.

## Bloque 10. Orden recomendado de ejecución

1. Catalogar el dataset.
2. Preparar `raw`.
3. Crear PostgreSQL + PostGIS.
4. Crear schemas y tabla de control de ingesta.
5. Importar las capas del `FileGDB` con GDAL Python.
6. Consolidar `source`.
7. Construir `core`.
8. Construir `pub`.
9. Añadir y ejecutar tests y validaciones aplicables.
10. Validar contra el flujo actual.
11. Documentar resultados y decisiones.

## Bloque 11. Cierre por fases y commits

- [ ] Definir qué se considera "fase" dentro de esta PoC.
- [ ] No cerrar una fase sin evidencia de validación suficiente.
- [ ] Hacer commit solo cuando la fase esté completa y verificada.
- [ ] Asociar cada commit a un bloque funcional reconocible del TODO.
- [ ] Incluir en cada cierre de fase:
  - comprobaciones ejecutadas,
  - resultado,
  - limitaciones conocidas,
  - siguiente fase habilitada.
- [ ] Mantener los commits con alcance reducido y coherente.

### Fases sugeridas para esta PoC

- [ ] Fase 1: catálogo del dataset y organización `raw`.
- [ ] Fase 2: entorno Docker PostgreSQL/PostGIS y estructura base de BBDD.
- [ ] Fase 3: importación filtrada inicial con GDAL Python.
- [x] Fase 4: construcción de `source` y validación.
- [ ] Fase 5: construcción de `core` y validación.
- [ ] Fase 6: construcción de `pub` y validación comparativa.
- [ ] Fase 7: tests, endurecimiento y documentación final.

## Decisiones abiertas que habrá que cerrar durante la PoC

- Si `core` será una tabla genérica reutilizable o una tabla específica para `landcover`.
- Si `source` conservará una tabla por layer del `FileGDB` o una tabla consolidada con campo `source_layer` (en esta PoC ya queda consolidada por vista).
- Si la simplificación debe aplicarse una sola vez o por niveles.
- Si el `dissolve` por clase es parte del modelo canónico o solo de publicación.
- Si la salida `pub` debe almacenar geometría simplificada persistida o derivada bajo demanda.
- Si la carga se ejecutará manualmente o como pipeline repetible automatizado.
- Si el importador GDAL Python se ejecutará siempre desde contenedor para maximizar portabilidad.
- Si el filtrado en la primera carga se expresará solo con `where` o si hará falta una capa intermedia temporal.

## Riesgos a vigilar

- Perder trazabilidad al saltar directamente del fichero a una tabla final.
- Mezclar el modelo de explotación con decisiones de visualización concretas.
- Perder la frontera entre `source` cercano al origen y `core` canónico.
- Diseñar `core` demasiado específico para `landcover`.
- Repetir en SQL una lógica difícil de mantener si el mapping de clases sigue embebido en scripts.
- Cargar geometrías pesadas sin una estrategia de simplificación coherente.
- Cargar por error la capa completa en PostGIS y perder el beneficio del filtrado temprano.
- Introducir scripts o montajes Docker que funcionen en Linux pero no en Windows.
- Dejar fases aparentemente terminadas sin validación reproducible.

## Resultado esperado de esta PoC

Al terminar, el proyecto debe tener un ejemplo completo y replicable de ingestión geoespacial:

- un dato crudo en filesystem,
- un registro de ingesta en BBDD,
- una representación `source` ya filtrada funcionalmente en la primera carga,
- una representación homogénea `core`,
- una representación `pub` preparada para servir datos de manera eficiente en fases posteriores.


### Observación de la Fase 3

La estructura y el pipeline filtrado inicial están definidos e implementados.
La ejecución completa contra datos reales sigue pendiente porque el `FileGDB` comprimido requiere una ventana de ejecución más larga que esta validación interactiva.

### Observación de la Subfase 4b

Queda implementada la vía eficiente `ZIP -> GDB extraido -> staging -> source`.
El importador feature-a-feature deja de ser la opción para carga completa; se mantiene solo como referencia histórica de la PoC.
La validación real con carga completa ha dejado `151615` features en `source` y `staging`, con trazabilidad correcta en `ingest.ingest_file`.
Como tradeoff del modo rápido con `OGR_ORGANIZE_POLYGONS=SKIP`, `source` conserva más geometrías inválidas que en la vía lenta; esto queda asumido y se resolverá en `core`.
