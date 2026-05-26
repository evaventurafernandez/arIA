---
id: TFG-20260519-capa-contexto-carreteras-igr-rt
título: "Capa contextual de carreteras IGR-RT"
tipo: decisión
tags:
  - tfg
  - carreteras
  - igr-rt
  - ign
  - postgis
  - visor-gis
contexto: "Decisión y guía para incorporar la red oficial de carreteras como capa de contexto en el visor GIS web del TFG. Tras un primer planteamiento local-first basado en IGR-RT, la decisión vigente es servir la capa primaria desde el WFS de transportes de IDEE y mantener la copia local IGR-RT en PostGIS como fallback consultable cuando el servicio remoto falle. Requiere normalizar atributos INSPIRE TN-RO e IGR-RT a un contrato común para que el visor se comporte igual con cualquiera de las dos fuentes."
fuente_existe: true
fuente_tipo: documentación
fuente_descripción: "Investigación propia verificada contra documentación y servicios de IDEE, IGN/CNIG, SCNE, INSPIRE, OGC y el patrón de ingesta existente en el repositorio."
fuente_url: "https://centrodedescargas.cnig.es/CentroDescargas/redes-transporte"
autor_o_entidad: "IGN/CNIG, IDEE, SCNE, Unión Europea, OGC y elaboración propia pendiente de confirmar"
fecha_fuente: "pendiente de confirmar"
licencia_o_copyright: "IGR-RT: licencia de uso compatible con CC-BY 4.0 según CNIG; resto de documentación y herramientas con condiciones pendientes de confirmar"
condiciones_de_uso: "Para IGR-RT se debe reconocer origen y propiedad usando la fórmula oficial de la versión descargada. En una publicación derivada, usar una fórmula equivalente a 'Obra derivada de IGR-RT [año] CC-BY 4.0 scne.es', ajustando el año a la versión real."
grado_de_confianza: medio
pendientes_de_verificar:
  - "Confirmar autoría de la síntesis y de la decisión de alcance"
  - "Confirmar la versión concreta de IGR-RT descargada y su fórmula exacta de atribución"
  - "Confirmar capacidades reales del WFS de transportes de IDEE: tipos de feature TN-RO publicados, límites de count, CRS y soporte de filtros por bbox"
  - "Definir contrato común de atributos publicables (campos normalizados desde INSPIRE TN-RO y desde IGR-RT)"
  - "Decidir lógica de fallback: front-end por error de petición, probe periódico desde backend, o ambas"
  - "Confirmar política de caché del backend ante el WFS remoto para evitar penalizar la latencia del visor"
---

# Capa contextual de carreteras: WFS IDEE primario con IGR-RT como fallback local

## Contenido
Se plantea añadir al programa una nueva capa de contexto basada en la red oficial de carreteras de España. La capa debe servir para contextualizar fenómenos ya presentes en el visor, como avisos meteorológicos, focos de incendio, usos del suelo, núcleos de población y otras capas de exposición.

La decisión de fondo no es incorporar un simple fondo cartográfico, sino una capa vectorial consultable, filtrable y explotable por atributos.

La estrategia ha evolucionado a lo largo del trabajo: el primer planteamiento fue `local-first` puro sobre IGR-RT, pero se ha decidido invertir el orden para favorecer la frescura del dato oficial y la coherencia con otros servicios del visor que ya consumen IDEE. La capa primaria pasa a servirse desde el WFS de transportes de IDEE y la copia local IGR-RT en PostGIS se conserva como fallback consultable.

La investigación disponible propone un camino técnico razonable, pero no debe tratarse como una receta cerrada. Los pasos se podrán adaptar según convenga al estado real del proyecto, al rendimiento observado y al alcance final del TFG.

## Decisión de alcance
La capa de carreteras se incorpora como una capa contextual más del visor GIS. Su función principal será mejorar la lectura territorial del riesgo, no sustituir capas temáticas como AEMET, FIRMS, landcover, población o espacios protegidos.

Decisión vigente (sustituye al planteamiento `local-first` inicial):

- La fuente primaria del visor es el **WFS de transportes de IDEE** (`https://servicios.idee.es/wfs-inspire/transportes`), que sirve el modelo INSPIRE TN-RO (`tn-ro:RoadLink`, `tn-ro:RoadNode`, `tn-ro:RoadServiceArea` y relacionados).
- La copia local **IGR-RT en PostGIS** (`source/core/pub` sobre `rt_tramo_vial`) se conserva como **fallback** consultable cuando el WFS no responde, está en mantenimiento o devuelve error.
- Backend y frontend hablan en **un contrato común** de atributos: ambos lados publican los mismos campos, sea cual sea la fuente activa, para que filtros, popup y leyenda no cambien al activarse el fallback.

Se justifica el cambio respecto a la decisión inicial por:

- **Frescura del dato**: el WFS oficial publica el estado vigente de la red, sin requerir un ciclo de descarga/refresh manual de IGR-RT. Esto evita que el visor muestre datos desactualizados entre versiones provinciales del CNIG.
- **Coherencia con el resto del visor**: otras capas como inundaciones y CORINE ya se sirven desde servicios IDEE; servir carreteras desde IDEE alinea el patrón.
- **Trazabilidad institucional preservada**: tanto el WFS como IGR-RT proceden del SCNE (IGN/CNIG), por lo que el cambio no degrada la procedencia del dato.

Se justifica conservar la copia local IGR-RT como fallback por:

- **Resiliencia**: el WFS de IDEE puede sufrir caídas, mantenimientos, lentitudes o cuotas de count que dejarían el visor sin la capa primaria.
- **Inversión hecha**: la base completa (10.7M tramos en 52 territorios) ya está cargada y los scripts de ingesta funcionan; tirarla sería desperdicio.
- **Atributos ricos en local**: IGR-RT trae más detalle (titularidad, estado físico, firme, sentido, carriles) que INSPIRE TN-RO; la normalización a un contrato común publica un subconjunto compatible, pero internamente el detalle adicional sigue disponible para futuras tools del chat LLM o explotaciones secundarias.
- **Licencia compatible**: IGR-RT se distribuye bajo condiciones equivalentes a CC-BY 4.0, con reconocimiento obligatorio del origen según la fórmula oficial indicada por CNIG para la versión descargada.

## Verificación realizada
La revisión de la nota frente al proyecto y las fuentes externas deja estos ajustes:

- El Centro de Descargas del CNIG confirma que Redes de Transporte se distribuye en GeoPackage y Shapefile, con unidades provinciales y de toda España.
- La página actual del CNIG indica que los archivos provinciales contienen red de carreteras, viario urbano, carriles bici y caminos, mientras que el archivo nacional contiene solo red de carreteras.
- El servicio OGC API-Features de IDEE expone colecciones INSPIRE de transporte (`TN-RO Road link`, `TN-RO Road node`, `TN-RO Road service area`), y el WFS INSPIRE de transportes expone esos mismos tipos como features WFS estándar.
- Con la decisión actual, **el WFS de transportes de IDEE pasa a ser la fuente primaria**, y la copia local IGR-RT en PostGIS se mantiene como fallback. WMS y OGC API-Features quedan como referencias adicionales.
- El Modelo Físico IGR-RT v1.9 sigue siendo la referencia para nombres de tablas, relaciones y atributos del fallback local.
- La primera muestra local verificada fue `RT_A_CORUNA_gpkg.zip`. Contiene varios GeoPackage por modo de transporte; para la capa de carreteras el archivo relevante es `red_viaria.gpkg`.
- En el GeoPackage provincial verificado, la capa lineal principal no aparece como `rt_tramo_l`, sino como `rt_tramo_vial`. El fichero `leeme_RT_Prov_gpkg.txt` indica que esta capa ya es el resultado de unir `rt_tramo_l` con `rt_vial_a` mediante `rrt_tramo_vial`.
- Tras la descarga manual completa, la carpeta `data-store/files/raw/ign/igr_rt/` contiene 52 ZIP: las 50 provincias y las dos ciudades autónomas, Ceuta y Melilla. No faltan provincias, no hay ZIP inesperados y todos contienen `red_viaria.gpkg`.
- La carga masiva en PostGIS ya está hecha: `source.igr_rt_tramo_vial` contiene **10.719.026 tramos** repartidos en **52 territorios** (las 50 provincias más Ceuta y Melilla). Esta cifra deja obsoleta la indicación previa de la nota que apuntaba a "pendiente de ejecutar la importación completa".
- La publicación del fallback debe alinearse con el patrón que ya usa el proyecto para `landcover`, `AEMET` y `núcleos de población`: PostGIS + vistas/materialized views `pub` + endpoint MVT propio en FastAPI + `Leaflet.VectorGrid` en frontend.
- `pg_tileserv`, Martin y PMTiles quedan como alternativas futuras o de comparación, no como primera implementación, para no introducir una pieza nueva antes de validar la capa con la arquitectura actual.

## Fuentes y referencias identificadas
- Centro de Descargas CNIG, Redes de Transporte: `https://centrodedescargas.cnig.es/CentroDescargas/redes-transporte`
- Sistema Cartográfico Nacional: `https://www.scne.es/`
- Directiva INSPIRE 2007/2/CE: `http://data.europa.eu/eli/dir/2007/2/oj`
- Especificación INSPIRE Transport Networks: `https://inspire.ec.europa.eu/id/document/tg/tn`
- OGC API-Features: `https://api-features.idee.es/collections`
- WFS INSPIRE transportes: `https://servicios.idee.es/wfs-inspire/transportes?REQUEST=GetCapabilities&SERVICE=WFS&VERSION=2.0.0`
- WMS INSPIRE transportes: `https://servicios.idee.es/wms-inspire/transportes?REQUEST=GetCapabilities&SERVICE=WMS&VERSION=1.3.0`
- WMTS Mapa Base IGN: `https://www.ign.es/wmts/mapa-raster`
- Modelo Físico de la IGR-RT v1.9, IGN, 2026: `https://centrodedescargas.cnig.es/CentroDescargas/documentos/ModeloFisico_IGR-RT_V1_9_publicado.pdf`
- PostGIS: `https://postgis.net/`
- GDAL/OGR `ogr2ogr`: `https://gdal.org/programs/ogr2ogr.html`
- pg_tileserv: `https://github.com/CrunchyData/pg_tileserv`
- pg_featureserv: `https://github.com/CrunchyData/pg_featureserv`
- Martin: `https://github.com/maplibre/martin`
- Tippecanoe: `https://github.com/felt/tippecanoe`
- PMTiles: `https://protomaps.com/docs/pmtiles`
- Licencia CC BY 4.0: `https://creativecommons.org/licenses/by/4.0/`

## Hallazgos del WFS de transportes IDEE (verificación real)
Tras `GetCapabilities`, `DescribeFeatureType` y un `GetFeature` real, el modelo publicado es INSPIRE TN-RO v4.0 y tiene tres consecuencias directas sobre el diseño:

1. **`tn-ro:RoadLink` no lleva atributos descriptivos en línea.** Una respuesta real solo contiene:
   - `gml:id` (p. ej. `TN-RO_ROADLINK_VIAL_TR50190097067`),
   - `net:inspireId` con `base:localId` y `base:namespace = "ES.SCNE.IGR-RT"`,
   - `net:centrelineGeometry` (`gml:LineString` en el CRS pedido),
   - `net:beginLifespanVersion` / `net:endLifespanVersion`,
   - `net:fictitious`, `net:startNode`, `net:endNode` (xlink al nodo),
   - `tn:validFrom`, `tn:validTo` (en la práctica `nil`).

   Todo lo demás (nombre, clase funcional, número de carriles, restricción de acceso, sentido de tráfico, propietario, estado, superficie, área de servicio) son **FeatureTypes independientes** publicados por el mismo WFS: `tn-ro:RoadName`, `tn-ro:NumberOfLanes`, `tn-ro:FormOfWay`, `tn-ro:FunctionalRoadClass`, `tn-ro:RoadSurfaceCategory`, `tn:AccessRestriction`, `tn:ConditionOfFacility`, `tn:OwnerAuthority`, `tn:TrafficFlowDirection`, etc. Cada uno apunta a su RoadLink mediante `networkRef`.

2. **La clave de pivote WFS ↔ local es `inspireId.localId`.** El namespace declarado es `ES.SCNE.IGR-RT`, y el `localId` observado es `VIAL_TR50190097067`. Quitando el prefijo `VIAL_TR` queda `50190097067`, que coincide exactamente con `source.igr_rt_tramo_vial.id_tramo`. Verificado con consulta directa a PostGIS: tres filas en el local para ese `id_tramo` (un tramo puede pertenecer a varios viales, coherente con la trampa operativa ya documentada).

3. **Capacidades operativas del servicio:**
   - WFS 2.0.0 funciona.
   - `DefaultCRS = EPSG:4258` (ETRS89 lat/lon, axis order lat,lon). Forzando `SRSNAME=EPSG:4326` el servicio devuelve `gml:posList` como `lon lat`, compatible con Leaflet sin reordenar ejes.
   - `OtherCRS` incluye EPSG:3035 (LAEA).
   - Filtro `BBOX=minLon,minLat,maxLon,maxLat,EPSG:4326` aceptado.
   - Respuestas con `numberMatched` y `numberReturned`; paginación por `next`/`STARTINDEX`.

### Consecuencias sobre el diseño

- Llamar al WFS `tn-ro:RoadLink` aporta **geometría fresca + identificador estable**. NO aporta nombre ni atributos.
- Obtener todos los atributos del contrato común "sólo desde WFS" exigiría 8-10 llamadas adicionales por bbox (una por FeatureType), parsear `networkRef`, hacer joins en memoria y multiplicar la latencia y el riesgo de cuota. No es razonable para un visor interactivo.
- La solución **pragmática y coherente con la inversión local** es: la fuente primaria WFS aporta la geometría vigente y los identificadores; los atributos se resuelven por **join contra el local IGR-RT** por `id_tramo`. Sigue habiendo frescura real (un tramo retirado del WFS deja de mostrarse aunque siga en local; un tramo nuevo aparece aunque no esté aún en local) sobre la geometría y la existencia, sin pagar 10× peticiones por atributos.
- Si el WFS cae, el sistema sirve **todo** desde el local IGR-RT, incluida la geometría. El contrato común no cambia.

### Decisión derivada (rectifica al contrato común genérico anterior)

- **Primaria (WFS de IDEE)**: geometría y `localId`.
- **Atributos**: siempre desde local `core.road_segment`, joineados por `id_tramo`.
- **Fallback total**: geometría y atributos desde local.
- **Etiqueta de fuente** en el popup: `IDEE WFS + IGR-RT local` cuando hay join; `IGR-RT local (fallback)` cuando el WFS no responde.

## Diseño técnico ajustado al proyecto
La arquitectura vigente, ya con la verificación real del WFS aplicada, combina fuente primaria remota y enriquecimiento/fallback local sobre un contrato común:

```text
PRIMARIA (geometría fresca + identidad):
  WFS transportes IDEE
    GetFeature tn-ro:RoadLink?bbox=...&SRSNAME=EPSG:4326
      -> {gml:id, inspireId.localId="VIAL_TR<id_tramo>", centrelineGeometry, lifespan, ...}
    -> backend /api/roads/features
       -> extrae id_tramo del localId (quita prefijo "VIAL_TR")
       -> ENRIQUECIMIENTO: join contra core.road_segment por id_tramo
       -> publica GeoJSON al visor con todos los atributos del contrato común

FALLBACK TOTAL (resiliencia):
  CNIG GeoPackage (ya en data-store/files/raw/ign/igr_rt/)
    -> staging
    -> source.igr_rt_tramo_vial    [hecho, 10.7M tramos]
    -> core.road_segment           [pendiente: 2D, sentinelas, contrato común,
                                    representante único por id_tramo]
    -> pub.road_network_mvt_source [pendiente]
    -> /api/roads/tiles/{z}/{x}/{y}.mvt   (sólo en fallback)
    -> /api/roads/features sirve geometría y atributos desde local
       cuando el WFS falla

CONTROL DE FUENTE:
  /api/roads/health -> probe ligero al WFS de IDEE (cacheado)
                       front-end consulta health y/o reacciona a errores 5xx/timeout
                       en runtime; conmuta a la ruta sólo-local sin cambiar el
                       contrato del popup ni los filtros.
```

Decisiones de diseño asumidas para esta versión:

1. **Fuente primaria de geometría**: WFS de transportes de IDEE (`https://servicios.idee.es/wfs-inspire/transportes`), tipo `tn-ro:RoadLink`, `SRSNAME=EPSG:4326`, filtro `BBOX=minLon,minLat,maxLon,maxLat,EPSG:4326`, paginación por `COUNT`/`STARTINDEX`.
2. **Atributos por enriquecimiento local**: el WFS sólo aporta geometría y `inspireId.localId`. Los atributos del contrato común se resuelven contra `core.road_segment` por `id_tramo` extraído del `localId`. Esto evita 8-10 llamadas adicionales al WFS por bbox.
3. **Proxy en backend**: el frontend nunca llama al WFS directamente. Llama a `/api/roads/features?bbox=...` en FastAPI, que orquesta WFS + join local, cachea por bbox redondeado, controla timeouts y devuelve siempre el mismo contrato.
4. **Contrato común de atributos publicables**: para cada tramo el backend devuelve los mismos campos canónicos, sea cual sea la fuente: `id_tramo`, `inspire_id`, `clase`, `tipo`, `nombre`, `nombre_alt`, `codigo`, `titular`, `sentido`, `acceso`, `estado_fisico`, `firme`, `n_carriles`, `orden`, `tipovehic`, `territory_code`, `fuente`, `geom`. Los códigos sentinela `-997`/`-998` de IGR-RT se mapean a `NULL`.
5. **Representante único por `id_tramo` en `core.road_segment`**: como un tramo puede pertenecer a varios viales en `source.igr_rt_tramo_vial`, el `core` selecciona una fila representante por `id_tramo` (criterio: la de mayor jerarquía por `clase` y, en empate, la más reciente por `imported_at`). Las relaciones tramo↔vial adicionales permanecen disponibles en `source` para futuras explotaciones, pero no se publican en el contrato común.
6. **Fallback local conservado**: la carga masiva ya realizada en `source.igr_rt_tramo_vial` no se desmonta. Se construye `core.road_segment` y `pub.road_network_mvt_source` para servir geometría y atributos desde local cuando el WFS no responde.
7. **Endpoint MVT local**: `/api/roads/tiles/{z}/{x}/{y}.mvt`, siguiendo el patrón de `/api/nucleos/tiles/{z}/{x}/{y}.mvt`, alimenta un VectorGrid de fallback cuando el WFS está caído. Devuelve atributos ya en el contrato común.
8. **Detección de caída**: combinada. `/api/roads/health` hace un `GetCapabilities` o un bbox pequeño con timeout corto y cachea el resultado durante segundos; el front-end lo consulta al activar la capa. Además, errores 5xx/timeout en `/api/roads/features` conmutan a la rama sólo-local en runtime.
9. **Control de capa y estilo** en `frontend/index.html` y `frontend/app.js`, siguiendo el patrón de `chk-nucleos_poblacion`. El popup muestra los campos del contrato común y una etiqueta de fuente: `IDEE WFS + IGR-RT local` cuando hay join, `IGR-RT local (fallback)` cuando el WFS está caído.
10. **Atribución doble**: la leyenda incluye atribución a IGN/CNIG (IGR-RT) y a IDEE/SCNE (WFS) según corresponda; la atribución base permanece visible aunque la fuente activa cambie.
11. **Caché HTTP**: respuestas del proxy WFS se cachean en memoria por bbox redondeado y zoom durante una ventana corta para no martillear el servicio remoto al mover el mapa.
12. **`pg_tileserv`, Martin y PMTiles**: siguen aparcados como evolución posterior; primero validar el contrato común y la conmutación.

## Comprobación piloto: A Coruña
Se ha comprobado el archivo local:

```text
data-store/files/raw/ign/igr_rt/RT_A_CORUNA_gpkg.zip
```

Contenido del ZIP:

- `red_viaria.gpkg`: red viaria, archivo prioritario para el TFG.
- `rt_ffcc.gpkg`: ferrocarril.
- `rt_aerea.gpkg`: red aérea.
- `rt_vias_navegables.gpkg`: red marítima o navegable.
- `rt_intermodal.gpkg`: conexiones intermodales.
- `atributos_gpkg.csv`: descripción de atributos.
- `leeme_RT_Prov_gpkg.txt`: explicación de composición de capas.

Capas detectadas en `red_viaria.gpkg`:

| Capa | Geometría | Nº features | Uso inicial |
|---|---:|---:|---|
| `rt_tramo_vial` | 3D Line String | 332589 | Capa principal para carreteras, viales, caminos y carriles bici |
| `rt_portalpk_p` | 3D Point | 359207 | Portales y puntos kilométricos; no prioritaria para primera visualización |
| `rt_nodoctra_p` | 3D Point | 1365 | Nodos de carretera; útil más adelante para conectividad |
| `rt_areactra_s` | 3D Polygon | 765 | Áreas de carretera o servicio; secundaria |
| `rt_puntoctra_p` | 3D Point | 382 | Puntos asociados a carretera; secundaria |

Capas detectadas en el resto de GeoPackage del ZIP:

- `rt_ffcc.gpkg`: `rt_nodoffcc_p`, `rt_estacionffcc_p`, `rt_areaffcc_s`, `rt_tramofc_linea`, `rt_pkffcc_p`.
- `rt_aerea.gpkg`: `rt_aerodromo_p`, `rt_nodoaereo_p`, `rt_areaaereo_s`.
- `rt_vias_navegables.gpkg`: `rt_nodomar_p`, `rt_puerto_p`, `rt_areamar_s`.
- `rt_intermodal.gpkg`: `rt_conexion_a`.

Conclusión operativa: para la primera versión del TFG basta con importar `red_viaria.gpkg` y, dentro de él, empezar por `rt_tramo_vial`. Las capas de puntos y polígonos se pueden dejar para una segunda fase.

## Comprobación completa de ficheros provinciales
Después de descargar manualmente todos los ficheros provinciales, se ha verificado la carpeta:

```text
data-store/files/raw/ign/igr_rt/
```

Resultado:

- Total de ZIP encontrados: 52.
- Provincias esperadas: 50.
- Ciudades autónomas incluidas: Ceuta y Melilla.
- Provincias ausentes: ninguna.
- ZIP inesperados: ninguno.
- ZIP no legibles: ninguno.
- ZIP sin `red_viaria.gpkg`: ninguno.
- Tamaño total aproximado: 3,97 GB.

Esta comprobación permite pasar de la prueba piloto de A Coruña al diseño de un importador que recorra todos los ZIP `RT_*_gpkg.zip` y cargue la capa `red_viaria.gpkg/rt_tramo_vial` de cada unidad territorial.

## Estructura source creada
Se ha creado la primera estructura SQL para incorporar IGR-RT al patrón del proyecto:

```text
infra/postgres/initdb/018_igr_rt_source.sql
```

La estructura creada es deliberadamente solo de fase `source`. No se ha creado todavía `core` ni `pub`, porque primero conviene cargar y medir el volumen real de `rt_tramo_vial` en todas las provincias.

Relaciones creadas:

- `staging.igr_rt_tramo_vial_raw`: tabla de carga masiva previa a `source`.
- `source.igr_rt_tramo_vial`: tabla persistente cercana al origen.
- `source.igr_rt_road_segment`: vista estable para que la futura fase `core` consuma los tramos sin depender del nombre físico original.

Decisiones aplicadas en esta estructura:

- Se conserva `source_objectid` como `fid` original dentro de cada GeoPackage.
- Se añaden `source_zip_name`, `source_gpkg_name` y `source_layer` para mantener trazabilidad de fichero.
- Se añaden `territory_code` y `territory_name`, necesarios porque la carga recorrerá 52 ZIP.
- Se preservan los campos descriptivos ya presentes en `rt_tramo_vial`, como `tipo_tramd`, `clased`, `titulard`, `estadofisd`, `accesod`, etc.
- `ncarriles`, `orden` y `tipovehic` se guardan como texto, respetando el tipo observado en origen.
- La geometría se mantiene como `geometry(Geometry, 4326)` en `source`; la conversión definitiva a 2D queda para `core` o `pub`.
- Se crean índices por geometría, territorio, identificadores, clase, tipo, titularidad, estado físico, código y nombre.

La SQL se ha aplicado correctamente sobre el Postgres local con:

```powershell
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/018_igr_rt_source.sql
```

Comprobación posterior:

- `source.igr_rt_road_segment` existe como vista.
- `source.igr_rt_tramo_vial` existe como tabla base.
- `staging.igr_rt_tramo_vial_raw` existe como tabla base.

Siguiente paso técnico: crear `infra/ingest/import_igr_rt_source.py` para recorrer todos los `RT_*_gpkg.zip`, leer `red_viaria.gpkg/rt_tramo_vial`, cargar `staging.igr_rt_tramo_vial_raw` y consolidar en `source.igr_rt_tramo_vial` con un registro por ZIP en `ingest.ingest_file`.

## Importador source creado
Se ha creado el importador:

```text
infra/ingest/import_igr_rt_source.py
```

Función del script:

- Localiza los ZIP `RT_*_gpkg.zip` en `data-store/files/raw/ign/igr_rt/`.
- Abre el GeoPackage interno `red_viaria.gpkg` mediante `/vsizip/`, sin extraer manualmente los ficheros.
- Lee la capa `rt_tramo_vial`.
- Carga cada ZIP por separado en `staging.igr_rt_tramo_vial_raw`.
- Consolida la carga en `source.igr_rt_tramo_vial`.
- Registra un `ingest.ingest_file` por ZIP importado.
- Añade metadatos de trazabilidad: `source_zip_name`, `source_gpkg_name`, `source_layer`, `territory_code` y `territory_name`.

Variables operativas incluidas:

- `RAW_ZIP`: limita la ejecución a un único ZIP.
- `RAW_DIR`: cambia la carpeta de entrada.
- `ZIP_PATTERN`: cambia el patrón de búsqueda de ZIP.
- `ONLY_ZIPS`: lista separada por comas para importar solo algunos ZIP.
- `MAX_ZIPS`: limita el número de ZIP procesados.
- `MAX_FEATURES_PER_ZIP`: limita filas por ZIP para pruebas de humo.
- `TRUNCATE_SOURCE`: limpia `source.igr_rt_tramo_vial` al inicio; por defecto `1`.
- `TRUNCATE_STAGING`: limpia `staging.igr_rt_tramo_vial_raw` en cada ZIP; por defecto `1`.
- `CONTINUE_ON_ERROR`: permite continuar tras errores; por defecto `0`.

Durante la prueba se detectó un detalle importante: al consultar GeoPackage con GDAL, `fid` y `rowid` pueden ser tratados como FID de capa y no viajar como atributo normal en el `COPY` hacia PostGIS. Para conservar el identificador original en `source_objectid`, el importador usa:

```sql
rowid + 0 AS source_objectid
```

Este ajuste fuerza a GDAL a tratarlo como columna ordinaria.

Verificación realizada:

```powershell
docker compose run --rm gdal python3 -m py_compile /work/infra/ingest/import_igr_rt_source.py
```

Resultado: compilación correcta.

Prueba de humo realizada con 10 filas de A Coruña:

```powershell
docker compose run --rm --env RAW_ZIP=/work/data-store/files/raw/ign/igr_rt/RT_A_CORUNA_gpkg.zip --env MAX_FEATURES_PER_ZIP=10 --env TRUNCATE_SOURCE=1 gdal python3 /work/infra/ingest/import_igr_rt_source.py
```

Resultado:

- `staging.igr_rt_tramo_vial_raw`: 10 filas cargadas.
- `source.igr_rt_tramo_vial`: 10 filas consolidadas.
- Territorio cargado: `A_CORUNA` / `A Coruña`.
- `source_objectid` preservado entre `1` y `10`.
- Se verificaron campos como `id_tramo`, `id_vial`, `clase`, `clased`, `tipo_tramo`, `tipo_tramd`, `titular`, `titulard` y `nombre`.

Quedaron dos registros `failed` en `ingest.ingest_file` de las pruebas previas con `fid`/`rowid`; se conservan como trazabilidad técnica de la depuración. La carga válida queda registrada con estado `ok`.

Prueba de contrato completa realizada sobre los 52 ZIP:

```powershell
docker compose run --rm --env MAX_FEATURES_PER_ZIP=1 --env TRUNCATE_SOURCE=1 gdal python3 /work/infra/ingest/import_igr_rt_source.py
```

Resultado:

- Los 52 ZIP se abren correctamente desde `/vsizip/`.
- Todos exponen `red_viaria.gpkg/rt_tramo_vial` con el contrato de columnas esperado.
- Se consolidó una fila por territorio en `source.igr_rt_tramo_vial`.
- `source.igr_rt_tramo_vial` quedó con 52 filas y 52 territorios distintos.
- `source_objectid` quedó preservado como `1` en esta prueba limitada, porque se cargó solo la primera fila de cada ZIP.
- En `ingest.ingest_file`, las cargas válidas de IGR-RT quedan con estado `ok`; permanecen dos estados `failed` de depuración previa.

Siguiente paso técnico (estado actual): la importación completa de los 52 ZIP ya está ejecutada. `source.igr_rt_tramo_vial` contiene **10.719.026 tramos** repartidos en **52 territorios** (50 provincias + Ceuta + Melilla). Esto confirma que el fallback local ya tiene el dato completo cargado en PostGIS; lo que queda es construir `core.road_segment` y `pub.road_network_mvt_source` para servirlo eficientemente cuando se conmute al fallback.

## Modelo físico y campos relevantes
La capa principal para carreteras en el paquete provincial verificado es `rt_tramo_vial`, que representa tramos lineales y ya incluye información alfanumérica del vial. La investigación señalaba `rt_tramo_l`, `rt_vial_a` y `rrt_tramo_vial` como piezas del modelo físico, pero en el GeoPackage provincial descargado esas relaciones ya vienen resueltas en `rt_tramo_vial`.

Capas y relaciones especialmente relevantes para el piloto:

- `rt_tramo_vial`: tramo lineal ya enriquecido con información de vial; capa principal.
- `rt_nodoctra_p`: nodos de carretera.
- `rt_portalpk_p`: portales y puntos kilométricos.
- `rt_puntoctra_p`: puntos asociados a carretera.
- `rt_areactra_s`: áreas de servicio.

Atributos prioritarios para exploración y filtros:

- `tipo_tramo`
- `clase`
- `calzada`
- `acceso`
- `firme`
- `sentido`
- `estadofis`
- `titular`
- `orden`
- `tipovehic`
- `ncarriles`

## Trampas operativas detectadas
- Los valores `-997` y `-998` funcionan como sentinelas para desconocido o no aplica; no deben tratarse como valores reales.
- `orden` y `tipovehic` son cadenas, no enteros.
- Un tramo puede pertenecer a varias vías; conviene preservar la relación `rrt_tramo_vial` en vez de aplanarla de forma irreversible.
- Los identificadores son `bigint` y pueden tener 12 dígitos.
- La geometría nativa puede ser 3D, pero para MVT probablemente convenga forzar 2D.
- La cobertura nacional puede no incluir todos los caminos, carriles bici y viales urbanos; esos elementos pueden requerir ficheros provinciales.
- Los carriles bici aparecen como `clase = 1005`, por lo que no deben buscarse únicamente como carreteras convencionales.
- Los endpoints internos del portal CNIG pueden ser útiles para automatización experimental, pero no son una API pública documentada y necesitan plan de contingencia.

## Plan de trabajo vigente

### Hecho
- Estructura `source` aplicada en `infra/postgres/initdb/018_igr_rt_source.sql`.
- Importador `infra/ingest/import_igr_rt_source.py` validado.
- Carga masiva completada en `source.igr_rt_tramo_vial`: 10.719.026 tramos en 52 territorios.
- Verificación real del WFS de IDEE: `GetCapabilities`, `DescribeFeatureType` y `GetFeature` ejecutados; mapeo `inspireId.localId = VIAL_TR<id_tramo>` confirmado contra `source`.
- Estructura `core` aplicada en `019_igr_rt_core.sql` y poblada con `refresh_igr_rt_core.sql`: 9.879.049 tramos representantes únicos por `id_tramo` (~840k duplicados consolidados). Sentinelas a NULL, geometrías 2D MultiLineString EPSG:4326.
- Estructura `pub` aplicada en `020_igr_rt_pub.sql` y poblada: `pub.road_network_mvt_source` con 9.879.049 filas en EPSG:3857. `refresh_igr_rt_pub.sql` usa `REFRESH CONCURRENTLY` para refrescos posteriores.
- Endpoints en `main.py`:
  - `/api/roads/health` (probe `GetCapabilities` al WFS, caché 30s).
  - `/api/roads/features?bbox=&limit=` (proxy WFS `tn-ro:RoadLink` + enriquecimiento contra `core.road_segment`, fallback transparente a sólo-local).
  - `/api/roads/tiles/{z}/{x}/{y}.mvt` (MVT desde `pub.road_network_mvt_source`, min zoom 9).
- Frontend en `frontend/index.html`, `frontend/app.js`, `frontend/style.css`:
  - Checkbox `chk-roads`, etiqueta visible de fuente, pane propio, estilos por `clase`.
  - Conmutación primaria↔fallback automática en cliente.
  - Popup con todos los campos del contrato común y la etiqueta de fuente.
  - Recarga con debounce 350 ms en `moveend` para la ruta primaria.

### Pendiente
1. Verificar visualmente la capa en navegador, especialmente a distintos zooms y sobre tipos heterogéneos (autopista, urbano, camino, carril bici).
2. Decidir si se añade un control UI explícito para forzar la fuente (auto/WFS/local) para pruebas.
3. Filtros UI por `clase`, `titular`, `acceso`, `estado_fisico` si se considera valioso.
4. Documentar fuente, versión y atribución en `README.md` y en la memoria del TFG.
5. Tunear `ROADS_WFS_TIMEOUT_SECONDS` y `ROADS_FEATURE_DEFAULT_LIMIT` con uso real; el WFS de IDEE es variable y conviene observar la frecuencia real de fallback.
6. Evaluar si el visor del TFG quiere también filtrar por `clase` por defecto a bajo zoom (p. ej. ocultar caminos y sendas hasta z≥13).

## Simbología y escalonado por zoom

### Procedencia de la simbología
La paleta y los grosores aplicados en `frontend/app.js` (`ROADS_STYLE_BY_CLASE`) son una **convención propia del proyecto**, no proceden de un estilo SLD oficial publicado por el IGN ni de la documentación de IGR-RT. Se inspiran en convenciones cartográficas ampliamente compartidas:

- **Autopistas (de peaje y libre/autovía) en rojo intenso**: convención de mapas de carreteras europeos, señalización oficial y catálogo TMC. También OpenStreetMap (`highway=motorway` en rojo en el estilo Mapnik default), Google Maps, Apple Maps e IGN Mapa Base.
- **Carretera multicarril en naranja**: gradiente de jerarquía descendente; misma lógica de OSM (`highway=trunk` naranja).
- **Carretera convencional en amarillo**: convención clásica de mapas físicos donde "carretera principal no autopista" se rotula en amarillo; OSM `highway=primary`.
- **Urbano / urbano diseminado en gris**: calles de ciudad sin jerarquía interurbana; OSM `highway=residential`/`unclassified` en gris claro.
- **Camino y senda en marrón punteado/discontinuo**: convención topográfica (IGN Mapa Base, OpenTopoMap).
- **Carril bici en verde discontinuo**: convención OpenCycleMap.

La mezcla concreta de tonalidades, grosores y patrones discontinuos es elección del TFG; el catálogo IGR-RT solo aporta el **código y la descripción de la clase**. Documentar esta procedencia evita confundir la paleta con un estilo institucional.

### Escalonado de clases por zoom
Para que las carreteras aparezcan de forma progresiva (principales antes, detalles después) y para que cada tesela tenga un payload razonable, el backend filtra por `clase` según el zoom. La regla se define en `main.py:ROADS_CLASE_FIRST_VISIBLE_ZOOM` y se aplica tanto en `/api/roads/tiles` como en `/api/roads/features?zoom=`.

| Clase | Primer zoom visible |
|---|---:|
| Autopista de peaje | 7 |
| Autopista libre / autovía | 7 |
| Carretera multicarril | 9 |
| Carretera convencional | 10 |
| Urbano | 14 |
| Urbano diseminado | 14 |
| Camino | 15 |
| Carril bici | 15 |
| Senda | 16 |

Por encima del primer zoom visible, la clase se acumula a la capa: a z=10 se ven autopistas + multicarril + convencional; a z=15 se ven además urbano, urbano diseminado, camino y carril bici; a z=16 todas las clases (incluida senda).

### Optimizaciones aplicadas
Tras observar lentitud en el primer dibujo (sobre todo a zoom bajo), se aplicaron tres optimizaciones combinadas:

1. **Filtrado por clase server-side** en `/api/roads/tiles` y `/api/roads/features` (ya descrito arriba). Reduce drásticamente el número de filas que entran al pipeline de `ST_AsMVTGeom`.
2. **Índices GIST parciales** sobre `pub.road_network_mvt_source` (en `020_igr_rt_pub.sql`): `_highways_geom_gix`, `_arterials_geom_gix` e `_interurban_geom_gix` cubren los conjuntos de clase típicos de zooms 7-12. Sin ellos, el `gist` general devolvía ~1 M filas en la bbox de una tesela z=7 y se filtraban en memoria. Con los parciales, el `gist` devuelve directamente los ~13 k tramos relevantes.
3. **Simplificación geométrica por zoom** en la tesela MVT: `ST_SimplifyPreserveTopology` con tolerancias 500 m (z=7) → 4 m (z=14). Reduce vértices sin alterar la lectura visual.
4. **Compresión gzip** global en FastAPI (`GZipMiddleware`, `minimum_size=1024`). Las teselas MVT comprimen a ~24-35 % de su tamaño nativo.

Latencias medidas tras las optimizaciones (Madrid centro, primera carga):

| Zoom | Latencia | Tamaño nativo | Tamaño en cable (gzip) |
|---:|---:|---:|---:|
| 7 | 0,72 s | 1,61 MB | 386 KB |
| 9 | 0,35 s | 783 KB | 201 KB |
| 11 | 0,14 s | 293 KB | 84 KB |
| 13 | 0,03 s | 14 KB | 5 KB |
| 14 | 0,05 s | 103 KB | 34 KB |

Comparativa con el estado anterior:

- z=7 antes de optimizar: 31 s, 1,71 MB sin gzip. Ahora: 0,7 s, 386 KB. **~50× más rápido en latencia, ~4,4× menos en transferencia**.
- z=9 antes: 1,4 s. Ahora: 0,35 s.
- z=13 antes: 0,36 s con todas las clases (incluida Urbano). Ahora: 25 ms con la clase Urbano subida a z=14.

### Conmutación entre ruta primaria y fallback en el cliente
`frontend/app.js` usa la ruta MVT (`/api/roads/tiles`) **siempre** por debajo de zoom 12, porque a bajo zoom la bbox del WFS sería enorme y el WFS no acepta filtros por clase. A z ≥ 12, intenta la ruta primaria `/api/roads/features` con WFS + enriquecimiento local; si el WFS falla o devuelve `source = "IGR-RT local (fallback)"`, el cliente se queda en MVT. Al cruzar el umbral por movimiento de mapa, conmuta automáticamente.

## Contrato común de atributos
Tras la verificación real del WFS, el contrato común queda como sigue. La fuente primaria WFS sólo provee geometría e identificador; el resto de campos se enriquece desde el local IGR-RT por join sobre `id_tramo`. En modo fallback, todos los campos vienen del local.

| Campo canónico | Tipo | Origen ruta WFS+local (primaria) | Origen ruta sólo-local (fallback) |
|---|---|---|---|
| `id_tramo` | bigint | `inspireId.localId` sin prefijo `VIAL_TR` | `id_tramo` |
| `inspire_id` | text | `inspireId.localId` completo | `'VIAL_TR' \|\| id_tramo` |
| `clase` | text | `core.road_segment.clase` (join) | `clased` |
| `tipo` | text | `core.road_segment.tipo` (join) | `tipo_tramd` |
| `nombre` | text | `core.road_segment.nombre` (join) | `nombre` |
| `nombre_alt` | text | `core.road_segment.nombre_alt` (join) | `nombre_alt` |
| `codigo` | text | `core.road_segment.codigo` (join) | `codigo` |
| `titular` | text | `core.road_segment.titular` (join) | `titulard` |
| `sentido` | text | `core.road_segment.sentido` (join) | `sentidod` |
| `acceso` | text | `core.road_segment.acceso` (join) | `accesod` |
| `estado_fisico` | text | `core.road_segment.estado_fisico` (join) | `estadofisd` |
| `firme` | text | `core.road_segment.firme` (join) | `firmed` |
| `n_carriles` | int | `core.road_segment.n_carriles` (join) | parsea `ncarriles` a int |
| `orden` | text | `core.road_segment.orden` (join) | `ordend` |
| `tipovehic` | text | `core.road_segment.tipovehic` (join) | `tipovehicd` |
| `territory_code` | text | `core.road_segment.territory_code` (join) | `territory_code` |
| `fuente` | text | constante `"IDEE WFS + IGR-RT local"` | constante `"IGR-RT local (fallback)"` |
| `geom` | LineString/MultiLineString EPSG:4326 | desde `net:centrelineGeometry` con `SRSNAME=EPSG:4326` | `ST_Force2D(geom)` desde `core.road_segment` |

Notas operativas:

- El WFS devuelve `gml:posList` como `lon lat` solo si se fuerza `SRSNAME=EPSG:4326`; con el `DefaultCRS=EPSG:4258` el orden es `lat lon`.
- En la ruta primaria, los tramos del WFS que no encuentran `id_tramo` en local se publican con geometría y los atributos a `NULL` y `fuente = "IDEE WFS (sin enriquecer)"` para no ocultarlos.
- Un `id_tramo` con varias filas en `source.igr_rt_tramo_vial` se colapsa a una representante en `core.road_segment` (criterio: mayor jerarquía por `clase`, desempate por `imported_at` reciente).

## Primer paso operativo (estado actual)
Pasos ya completados:

- Comprobación del ZIP piloto de A Coruña:
  ```powershell
  docker compose run --rm gdal ogrinfo -so /vsizip//work/data-store/files/raw/ign/igr_rt/RT_A_CORUNA_gpkg.zip/red_viaria.gpkg
  ```
- Estructura `source` mínima creada y aplicada (`018_igr_rt_source.sql`).
- Importador validado y carga completa de 10.719.026 tramos en `source.igr_rt_tramo_vial`.
- **Verificación del WFS de IDEE realizada** (`GetCapabilities`, `DescribeFeatureType` `tn-ro:RoadLink`, `GetFeature` con bbox real):
  - `tn-ro:RoadLink` publicado, `DefaultCRS=EPSG:4258`, `OtherCRS=EPSG:3035`, soporta `SRSNAME=EPSG:4326`.
  - Atributos descriptivos NO inline en `RoadLink`; viven en FeatureTypes separados con `networkRef`.
  - `inspireId.localId = "VIAL_TR" + id_tramo` (`namespace = "ES.SCNE.IGR-RT"`). Verificado contra `source.igr_rt_tramo_vial`: `id_tramo = 50190097067` existe en AVILA con 3 filas (varios viales por tramo).
  - Decisión tomada: ruta primaria = WFS para geometría + enriquecimiento por join local sobre `id_tramo`.

Pasos completados con esta iteración:

1. **`infra/postgres/initdb/019_igr_rt_core.sql`** aplicado: `core.road_segment` con `UNIQUE (id_tramo)`, `inspire_id`, todos los atributos del contrato común y geometría `MultiLineString` EPSG:4326.
2. **`infra/ingest/refresh_igr_rt_core.sql`** ejecutado: `INSERT 0 9879049` (de 10.719.026 filas en `source`, los ~840k restantes son duplicados por tramo en varios viales, ya consolidados a una fila representante por `id_tramo`). Tiempo: 49 minutos. Sentinelas residuales: 0.
3. **`infra/postgres/initdb/020_igr_rt_pub.sql`** aplicado: `pub.road_network_mvt_source` con reproyección a EPSG:3857.
4. Primer refresh de `pub` ejecutado (no `CONCURRENTLY` por estar vacía): 9.879.049 filas en EPSG:3857. **`infra/ingest/refresh_igr_rt_pub.sql`** queda como `REFRESH MATERIALIZED VIEW CONCURRENTLY` para refrescos posteriores.
5. **Endpoints FastAPI implementados en `main.py`**:
   - `/api/roads/health`: probe `GetCapabilities` al WFS de IDEE con timeout 6s y caché 30s. Probado: 387 ms en condición normal.
   - `/api/roads/features?bbox=&limit=`: orquesta WFS `tn-ro:RoadLink` + join enriquecedor contra `core.road_segment` por `id_tramo`. Caché por (bbox redondeado, limit) durante 30s. En excepción cae al modo sólo-local devolviendo el mismo contrato. Probado contra Madrid centro: devuelve atributos completos del contrato común con `fuente = "IDEE WFS + IGR-RT local"` cuando el WFS responde.
   - `/api/roads/tiles/{z}/{x}/{y}.mvt`: vector tiles MVT sobre `pub.road_network_mvt_source`, mínimo zoom 9. Probado: z=12 → 84 KB en 60 ms, z=14 → 10 KB en 44 ms.
6. **Frontend integrado** en `frontend/index.html`, `frontend/app.js` y `frontend/style.css`:
   - Nuevo checkbox `chk-roads` "Carreteras (IDEE WFS + IGR-RT)" en el bloque de capas de riesgo.
   - Etiqueta `#roads-source-label` que muestra la fuente activa (`WFS · N ms` en verde, `fallback local` en amarillo, `sin datos` en rojo).
   - Pane dedicado `roadsLayerPane`, estilos por `clase` (autopistas en rojo, multicarril naranja, convencional amarillo, urbano gris, caminos marrón punteado, carriles bici verde discontinuo).
   - Ruta primaria: capa GeoJSON desde `/api/roads/features` reconsultada con debounce de 350 ms al `moveend`. Si el backend devuelve `source` que empieza por `"IGR-RT local"`, el cliente conmuta automáticamente a la capa fallback `Leaflet.VectorGrid` sobre `/api/roads/tiles/...`.
   - Popup con todos los campos del contrato común y la etiqueta de fuente, igual para WFS+local que para fallback local.
   - `map.on('moveend', ...)` recarga la primaria; en modo fallback el VectorGrid se encarga del refresco por tesela.

Comportamiento observado en pruebas: el WFS de IDEE responde rápido con `COUNT≤10` (~500 ms) pero agota timeout con `COUNT≥20` de forma intermitente. El sistema cae al fallback de forma transparente y limpia, sin desaparición visual de la capa.

## Datos explícitos
- Se incorpora al visor una capa de contexto de carreteras.
- La fuente primaria es el **WFS de transportes de IDEE** (INSPIRE TN-RO).
- La fuente fallback es la copia local **IGR-RT** del IGN/CNIG, ya cargada en PostGIS.
- El cambio respecto a la decisión inicial se justifica por la frescura del dato y la coherencia con otras capas del visor que ya consumen IDEE.
- La copia local se conserva por resiliencia ante caídas o degradación del servicio remoto, por la inversión técnica ya realizada y por la riqueza atributiva de IGR-RT.
- Backend y frontend hablan en un contrato común; la fuente activa se etiqueta visiblemente en el popup.
- IGR-RT es una red lineal 3D de cobertura nacional conforme con INSPIRE y mantenida por el IGN en cooperación con el SCNE.
- El ZIP provincial de A Coruña contiene `red_viaria.gpkg`, `rt_ffcc.gpkg`, `rt_aerea.gpkg`, `rt_vias_navegables.gpkg` y `rt_intermodal.gpkg`.
- En `red_viaria.gpkg`, la capa principal `rt_tramo_vial` contiene 332589 tramos lineales 3D.
- La descarga manual completa contiene todos los ZIP provinciales esperados y también Ceuta/Melilla; cada ZIP incluye `red_viaria.gpkg`.
- Se ha creado y aplicado la estructura `source` inicial para `rt_tramo_vial`.
- La carga masiva está completada: 10.719.026 tramos en 52 territorios en `source.igr_rt_tramo_vial`.
- Para mantener uniformidad con el proyecto, el fallback usa MVT desde el backend FastAPI actual antes de evaluar `pg_tileserv`, Martin o PMTiles.
- La licencia indicada por CNIG para IGR-RT es compatible con CC-BY 4.0 y exige reconocer origen y propiedad.
- El Modelo Físico IGR-RT v1.9 es relevante para trabajar con nombres reales de tablas y atributos del fallback local.

## Datos inferidos
- La nota pertenece a la categoría de población, carreteras y espacios protegidos porque trata de una capa territorial de exposición/contexto.
- El tipo más adecuado es `decisión`, porque fija una dirección de arquitectura y alcance, aunque todavía admite ajustes técnicos finos (mapeo definitivo INSPIRE TN-RO ↔ contrato común tras `DescribeFeatureType`).
- La capa será útil para lectura de riesgo alrededor de avisos meteorológicos, focos de incendio y otras capas del visor.
- Servir desde WFS encaja con el patrón ya empleado en `flood` y `corine_wms`, que también consumen `servicios.idee.es`.
- El fallback local debe completarse en paralelo aunque la fuente primaria sea remota, porque la conmutación tiene que estar lista antes de exponer la capa al usuario.

## Datos faltantes o ambiguos
- Capacidades reales del WFS de transportes IDEE: tipos publicados, atributos, CRS soportados, versiones, límites de count y políticas de uso.
- Mapeo definitivo INSPIRE TN-RO ↔ contrato común, pendiente de `DescribeFeatureType`.
- Estrategia exacta de detección de caída: solo en runtime, probe periódico, o ambos.
- Ventana y tamaño de la caché del proxy WFS para no penalizar la latencia ni martillear el servicio.
- Versión concreta de IGR-RT en el fallback y fórmula exacta de atribución oficial.
- Cliente de visualización definitivo a medio plazo: Leaflet actual o MapLibre futuro.
- Política definitiva de actualización del fallback local: manual, semestral, anual o automatizada.
- Ubicación exacta de la atribución IGN/CNIG y IDEE/SCNE en la interfaz y en la memoria.
