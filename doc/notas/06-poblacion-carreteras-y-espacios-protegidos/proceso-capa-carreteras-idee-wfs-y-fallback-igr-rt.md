---
id: TFG-20260520-proceso-capa-carreteras-idee-wfs-y-fallback-igr-rt
título: "Proceso completo de la capa de carreteras: WFS de IDEE primario con fallback IGR-RT local"
tipo: proceso
tags:
  - tfg
  - carreteras
  - idee
  - wfs
  - igr-rt
  - postgis
  - visor-gis
  - inspire
contexto: "Documenta de extremo a extremo cómo se ha incorporado la capa contextual de carreteras al visor GIS del TFG: decisión, arquitectura híbrida WFS+local, contrato común de atributos, endpoints, frontend, optimizaciones de rendimiento, simbología y estado pendiente. Resume el resultado final que llegó a producción local; el detalle histórico paso a paso queda en la nota hermana `capa-contexto-carreteras-igr-rt.md`."
fuente_existe: true
fuente_tipo: documentación
fuente_descripción: "Síntesis del proceso de implementación verificada contra los servicios WFS/OGC API-Features de IDEE, el catálogo de Redes de Transporte del CNIG, el modelo INSPIRE TN-RO v4.0, el Modelo Físico IGR-RT v1.9 y el código real del repositorio MeteoVisor (main.py, infra/postgres/initdb/019_igr_rt_core.sql, 020_igr_rt_pub.sql, frontend/app.js)."
fuente_url: "https://servicios.idee.es/wfs-inspire/transportes"
autor_o_entidad: "IGN/CNIG e IDEE/SCNE (servicios y datos); INSPIRE (modelo TN-RO); OGC (estándar WFS); elaboración propia del TFG (arquitectura híbrida, contrato común y simbología)"
fecha_fuente: "2026-05-20"
licencia_o_copyright: "IGR-RT del IGN/CNIG con licencia compatible CC-BY 4.0; WFS INSPIRE de IDEE como servicio público; código y notas del proyecto bajo el marco del TFG"
condiciones_de_uso: "Atribución obligatoria a IGN/CNIG (fuente IGR-RT, fórmula oficial pendiente de fijar para la versión concreta descargada) y a IDEE/SCNE (servicio WFS de transportes) en cualquier publicación derivada del visor."
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar la fórmula oficial exacta de atribución para la versión concreta de IGR-RT descargada"
  - "Confirmar que el umbral z=12 entre ruta primaria y fallback MVT es el más adecuado tras uso real"
  - "Confirmar política de refresco del fallback local (cadencia manual o automatizada)"
---

# Proceso completo de la capa de carreteras: WFS de IDEE primario con fallback IGR-RT local

## 1. Decisión

### Por qué existe la capa
El visor GIS del TFG cruza varias capas temáticas (avisos AEMET, focos FIRMS, áreas quemadas, landcover, núcleos de población). Faltaba una **capa contextual de carreteras** que mejorase la lectura territorial del riesgo: dónde están las vías que conectan zonas afectadas, qué titularidad tienen, qué tramos hay próximos a un foco activo, etc. La capa no sustituye a las temáticas, las acompaña.

### Por qué WFS primario + local de respaldo
La primera iteración planteó `local-first` puro sobre IGR-RT (descargar, importar, servir desde PostGIS por MVT). Tras evaluar la capa OGC del IGN se decidió **invertir el orden**:

- **Fuente primaria**: WFS de transportes de IDEE (`https://servicios.idee.es/wfs-inspire/transportes`), tipo `tn-ro:RoadLink`. Aporta **frescura del dato oficial**: el visor refleja el estado vigente publicado por el SCNE sin requerir descargas periódicas.
- **Fuente fallback**: copia local IGR-RT cargada en PostGIS. Aporta **resiliencia ante caídas o degradación del servicio remoto**, aprovecha la inversión técnica ya hecha (10,7 M tramos cargados) y conserva la riqueza atributiva original.

Ambas pertenecen al mismo organismo (IGN/CNIG vía SCNE), por lo que la trazabilidad institucional se preserva en cualquier caso.

### Por qué un contrato común
INSPIRE TN-RO y IGR-RT publican el mismo grafo viario pero con vocabularios distintos. Para que el visor se comporte exactamente igual con cualquiera de las dos fuentes (filtros, popup, leyenda), el backend devuelve siempre el mismo conjunto de campos canónicos. Los códigos sentinela `-997` y `-998` de IGR-RT se mapean a `NULL`.

## 2. Arquitectura

### Diagrama de flujo

```text
PRIMARIA (frescura):
  WFS transportes IDEE (tn-ro:RoadLink)
    -> backend /api/roads/features?bbox=&zoom=
    -> extrae id_tramo de inspireId.localId (quita prefijo "VIAL_TR")
    -> ENRIQUECIMIENTO: join contra core.road_segment por id_tramo
    -> GeoJSON al visor (Leaflet GeoJSON con SVG)

FALLBACK TOTAL (resiliencia):
  CNIG GeoPackage (descarga manual provincial, 52 ZIP)
    -> source.igr_rt_tramo_vial       (10.719.026 tramos en 52 territorios)
    -> core.road_segment              (9.879.049 representantes por id_tramo)
    -> pub.road_network_mvt_source    (mismas filas, EPSG:3857, índices parciales)
    -> /api/roads/tiles/{z}/{x}/{y}.mvt
    -> Leaflet.VectorGrid (canvas)

CONTROL DE FUENTE:
  /api/roads/health -> probe GetCapabilities al WFS, caché 30 s
                       front-end activa la capa siempre probando el WFS primero;
                       conmuta al fallback solo si el WFS no responde.
```

### Hallazgo clave que condicionó el diseño
`tn-ro:RoadLink` del WFS **no trae atributos descriptivos en línea**: solo geometría (`centrelineGeometry`), `inspireId.localId`, lifespan y referencias a nodos. Los atributos (nombre, clase funcional, número de carriles, restricción de acceso, propietario, estado, dirección de flujo, superficie) viven en **FeatureTypes separados** (`tn-ro:RoadName`, `tn-ro:NumberOfLanes`, `tn-ro:FormOfWay`, `tn-ro:FunctionalRoadClass`, `tn:AccessRestriction`, `tn:ConditionOfFacility`, `tn:OwnerAuthority`, `tn:TrafficFlowDirection`, etc.) que apuntan al RoadLink por `networkRef`.

Resolver atributos sólo por WFS exigiría 8–10 llamadas adicionales por bbox y multiplicaría latencia y cuota. La solución pragmática y verificada es **enriquecer desde el local por `id_tramo`**:

```text
inspireId.localId = "VIAL_TR" || id_tramo
namespace         = "ES.SCNE.IGR-RT"
```

Verificado en PostGIS: `localId = "VIAL_TR50190097067"` → `id_tramo = 50190097067` existe en `source.igr_rt_tramo_vial` (territorio AVILA, 3 filas porque un tramo puede pertenecer a varios viales — consolidado a uno en `core.road_segment`).

### Capacidades del WFS de IDEE comprobadas
- WFS 2.0.0 funcional.
- `DefaultCRS = EPSG:4258` (ETRS89 lat/lon). Forzando `SRSNAME=EPSG:4326` el servicio devuelve `gml:posList` como `lon lat`, compatible con Leaflet.
- `OtherCRS` incluye EPSG:3035.
- Filtro `BBOX=minLon,minLat,maxLon,maxLat,EPSG:4326` aceptado.
- Paginación por `numberMatched`/`numberReturned` y `STARTINDEX`.

## 3. Contrato común de atributos publicables

Independientemente de la fuente activa, el backend devuelve estos campos por cada tramo:

| Campo canónico | Origen ruta primaria (WFS + join local) | Origen ruta fallback (sólo local) |
|---|---|---|
| `id_tramo` | `inspireId.localId` sin prefijo `VIAL_TR` | `id_tramo` |
| `inspire_id` | `inspireId.localId` completo | `'VIAL_TR' \|\| id_tramo` |
| `clase` | `core.road_segment.clase` | `clased` |
| `tipo` | `core.road_segment.tipo` | `tipo_tramd` |
| `nombre` | `core.road_segment.nombre` | `nombre` |
| `nombre_alt`, `codigo`, `titular`, `sentido`, `acceso`, `estado_fisico`, `firme`, `n_carriles`, `orden`, `tipovehic`, `territory_code` | desde `core.road_segment` | desde `core.road_segment` |
| `fuente` | `"IDEE WFS + IGR-RT local"` | `"IGR-RT local (fallback)"` |
| `geom` | `net:centrelineGeometry` con `SRSNAME=EPSG:4326` | `ST_Force2D(geom)` desde `core.road_segment` |

Notas operativas:

- En la ruta primaria, los tramos del WFS que no encuentran su `id_tramo` en local se publican igualmente con geometría y atributos a `NULL`, con `fuente = "IDEE WFS (sin enriquecer)"`.
- Un `id_tramo` con varias filas en `source` se colapsa a un representante en `core.road_segment` (criterio: menor `clase_code` por jerarquía, desempate por `imported_at DESC`, luego `source_fid`).

## 4. Modelo de datos

### Esquemas y materializaciones
- `infra/postgres/initdb/018_igr_rt_source.sql`: `staging.igr_rt_tramo_vial_raw`, `source.igr_rt_tramo_vial` (tabla persistente cercana al origen), `source.igr_rt_road_segment` (vista estable).
- `infra/postgres/initdb/019_igr_rt_core.sql`: `core.road_segment` con `UNIQUE (id_tramo)`, `inspire_id`, todos los campos del contrato común, geometría `MultiLineString(4326)`, 2D, sentinelas a `NULL`.
- `infra/postgres/initdb/020_igr_rt_pub.sql`: `pub.road_network_mvt_source` con reproyección a EPSG:3857.
- `infra/ingest/refresh_igr_rt_core.sql`: consolidación deduplicada por `id_tramo`, limpieza de sentinelas, `ST_Force2D` + `ST_MakeValid` + envoltorio a `MultiLineString`.
- `infra/ingest/refresh_igr_rt_pub.sql`: `REFRESH MATERIALIZED VIEW CONCURRENTLY` (no en el primer refresh, que va sin `CONCURRENTLY`).

### Volúmenes reales
- `source.igr_rt_tramo_vial`: 10.719.026 tramos en 52 territorios (50 provincias + Ceuta + Melilla).
- `core.road_segment`: 9.879.049 representantes únicos por `id_tramo` (~840 k filas colapsadas).
- `pub.road_network_mvt_source`: 9.879.049 filas en EPSG:3857.
- Tiempo de refresh inicial completo de `core`: ≈ 49 min en local. Refresh de `pub`: ≈ 22 min en local.

## 5. Endpoints FastAPI

### `/api/roads/health`
Probe ligero al WFS con `GetCapabilities` (timeout 6 s) y caché en memoria 30 s.
Respuesta: `{ status: "ok|degraded|down", latency_ms, checked_at, http_status?, error? }`.

### `/api/roads/features?bbox=&limit=&zoom=`
- Pide `tn-ro:RoadLink` al WFS con `SRSNAME=EPSG:4326`, `COUNT=limit`, `BBOX=lonMin,latMin,lonMax,latMax,EPSG:4326`.
- Parsea GML, extrae `localId` y geometría, obtiene `id_tramo`, joina contra `core.road_segment`.
- Si `zoom` se pasa, filtra el resultado por las clases visibles a ese zoom (escalonado, ver sección 6).
- En excepción (5xx, timeout, conexión) **cae internamente** a `fetch_roads_local_by_bbox` con el mismo filtro de clase y publica `source = "IGR-RT local (fallback)"`. El contrato del cliente no cambia.
- Caché por `(bbox redondeado, limit, set de clases)` durante 30 s, máx. 64 entradas.

### `/api/roads/tiles/{z}/{x}/{y}.mvt`
- `ST_AsMVT` sobre `pub.road_network_mvt_source` recortado por `ST_TileEnvelope`.
- Aplica filtro `clase = ANY(...)` según zoom (escalonado server-side).
- Aplica `ST_SimplifyPreserveTopology` con tolerancia decreciente por zoom (500 m a z=7, 4 m a z=14, 0 en z≥15).
- Devuelve `b""` cuando `z < ROADS_TILE_MIN_ZOOM` (7).
- Compresión gzip automática por `GZipMiddleware` global.

## 6. Escalonado por zoom

Las clases se publican progresivamente para que las principales se vean antes y los detalles aparezcan al hacer zoom:

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

Definido en `main.py:ROADS_CLASE_FIRST_VISIBLE_ZOOM`. Se aplica server-side tanto en `/api/roads/tiles` (filtro SQL) como en `/api/roads/features?zoom=` (filtro post-join). El cliente no necesita conocer la tabla: pasa su `map.getZoom()` y el backend decide.

## 7. Frontend

### Capa y pane
- Pane dedicado `roadsLayerPane` con `z-index = 290`. Decisión deliberada: las carreteras son **contexto** y van **por debajo** de las capas temáticas (`AEMET_MAX_TEMP_PANE = 330`, `NUCLEOS_PANE = 345`, `overlayPane = 400` donde viven focos FIRMS y avisos CAP). Así los focos, avisos, núcleos y AEMET reciben los clicks por encima de las carreteras, sin que el canvas MVT del fallback los bloquee.
- Ruta primaria: `L.geoJSON` sobre `/api/roads/features` (SVG, los clicks atraviesan el hueco entre rutas).
- Ruta fallback: `L.vectorGrid.protobuf` sobre `/api/roads/tiles/{z}/{x}/{y}.mvt` con `rendererFactory: L.canvas.tile`.

### Decisión de cuándo usar cada ruta
- `z < 12` (constante `ROADS_PRIMARY_MIN_ZOOM`): siempre MVT local. A ese zoom el bbox es tan grande que el WFS no puede entregar una muestra representativa (el `COUNT` máximo lo trunca y la mayoría serían urbanos). No es un fallo del WFS, es elección de diseño.
- `z ≥ 12`: ruta primaria WFS + enriquecimiento. Si el WFS falla, el backend ya devuelve `IGR-RT local (fallback)` y el cliente conmuta al VectorGrid MVT.
- En cada `moveend` (con debounce 350 ms) se reintenta la ruta primaria si procede.
- Re-probe periódico al WFS cada 60 s mientras la capa está activa: si vuelve y estamos en fallback a `z ≥ 12`, se recupera la primaria automáticamente.

### Badge de estado junto al checkbox
Texto compacto + tooltip con detalle (latencia exacta, hora de la última prueba):

| Texto visible | Color | Significado |
|---|---|---|
| `probando…` | gris itálica | Esperando primera respuesta del WFS al activar la capa |
| `WFS+local` | verde | Ruta primaria activa: geometría WFS + atributos enriquecidos del local |
| `MVT local · zoom bajo` | azul | El WFS responde, pero a este zoom servimos teselas locales por diseño |
| `MVT local · WFS no responde` | ámbar | Fallback real: el WFS se contactó y falló |
| `WFS no responde` | rojo | Caso extremo: ni WFS ni teselas disponibles |

### Popup
Mismo formato sea cual sea la fuente: tabla con `id_tramo`, `clase`, `tipo`, `nombre`, `código`, `titular`, `sentido`, `acceso`, `estado físico`, `firme`, `nº carriles`, `orden`, `vehículos`, `territorio`, y una línea final con `fuente`.

## 8. Optimizaciones aplicadas

Tras observar lentitud en el primer dibujo (especialmente a z=7, que llegaba a 31 s y 1,7 MB), se combinaron cuatro optimizaciones:

1. **Filtrado por clase server-side** (ver sección 6): reduce drásticamente las filas que entran al pipeline de `ST_AsMVTGeom`.
2. **Índices GIST parciales** sobre `pub.road_network_mvt_source` (en `020_igr_rt_pub.sql`):
   - `road_network_mvt_source_highways_geom_gix` → autopistas (peaje + libre/autovía), ~142 k filas.
   - `road_network_mvt_source_arterials_geom_gix` → autopistas + multicarril.
   - `road_network_mvt_source_interurban_geom_gix` → autopistas + multicarril + convencional.
   Sin ellos, una tesela z=7 forzaba al `gist` general a leer ~1 M filas urbanas/caminos en la bbox y filtrarlas en memoria. Con los parciales, devuelve directamente los ~14 k tramos relevantes.
3. **Simplificación geométrica por zoom** con `ST_SimplifyPreserveTopology` y tolerancias 500 m (z=7), 250 m (z=8), 120 m (z=9), 60 m (z=10), 30 m (z=11), 15 m (z=12), 8 m (z=13), 4 m (z=14), 0 (z≥15).
4. **Compresión gzip global** en FastAPI (`GZipMiddleware`, `minimum_size=1024`). MVT comprime a ~24–35 % del tamaño nativo.

Resultado verificado (Madrid centro, primera carga):

| Zoom | Latencia | Nativo | En cable (gzip) |
|---:|---:|---:|---:|
| 7 | 0,72 s | 1,61 MB | 386 KB |
| 9 | 0,35 s | 783 KB | 201 KB |
| 11 | 0,14 s | 293 KB | 84 KB |
| 13 | 0,03 s | 14 KB | 5 KB |
| 14 | 0,05 s | 103 KB | 34 KB |

Comparativa con el estado anterior:

- z=7 antes: **31 s, 1,71 MB**. Después: **0,72 s, 386 KB en cable**. ~50× más rápido en latencia, ~4,4× menos en transferencia.
- z=9 antes: 1,4 s. Después: 0,35 s.

## 9. Simbología

### Procedencia
La paleta y los grosores aplicados en `frontend/app.js:ROADS_STYLE_BY_CLASE` son **convención propia del proyecto**, no proceden de un estilo SLD oficial publicado por IGN/IDEE ni del catálogo IGR-RT (que solo aporta código y descripción de la clase). Están inspirados en convenciones cartográficas ampliamente compartidas:

- Autopistas en rojo intenso: señalización europea, OpenStreetMap default Mapnik (`highway=motorway`), Google Maps, Apple Maps, IGN Mapa Base.
- Multicarril en naranja: jerarquía descendente; OSM `highway=trunk`.
- Convencional en amarillo: mapas físicos clásicos; OSM `highway=primary`.
- Urbano / urbano diseminado en gris: calles sin jerarquía interurbana; OSM `highway=residential|unclassified`.
- Camino y senda en marrón punteado/discontinuo: convención topográfica (IGN Mapa Base, OpenTopoMap).
- Carril bici en verde discontinuo: convención OpenCycleMap.

La mezcla concreta de tonalidades, grosores y patrones es elección del TFG. Documentar la procedencia evita confundir la paleta con un estilo institucional.

### Tabla de estilos efectiva
```text
Autopista de peaje         → color #B71C1C, weight 3.0
Autopista libre / autovía  → color #D32F2F, weight 3.0
Carretera multicarril      → color #E65100, weight 2.5
Carretera convencional     → color #FBC02D, weight 2.0
Urbano                     → color #90A4AE, weight 1.6
Urbano diseminado          → color #B0BEC5, weight 1.3
Camino                     → color #8D6E63, weight 1.0, dash '3,3'
Senda                      → color #A1887F, weight 0.8, dash '2,3'
Carril bici                → color #388E3C, weight 1.5, dash '5,4'
(fallback)                 → color #9E9E9E, weight 1.2
```

## 10. Atribución y licencia

- **IGR-RT (IGN/CNIG)**: licencia compatible CC-BY 4.0. Atribución obligatoria con la fórmula oficial de la versión descargada (pendiente de fijar el literal exacto para la versión actual). En memoria del TFG y en el visor debe figurar "Obra derivada de IGR-RT [año] CC-BY 4.0 scne.es" o el literal vigente del CNIG en el momento de la descarga.
- **WFS de transportes de IDEE**: servicio público bajo SCNE, atribución a IDEE/IGN.
- **INSPIRE TN-RO v4.0**: estándar europeo, no requiere licencia adicional.

## 11. Estado pendiente

1. **Fijar el literal exacto de atribución IGR-RT** para la versión concreta descargada y publicarlo en `README.md` y en la memoria.
2. **Validar visualmente el escalonado y el badge** en sesiones reales (navegador con caché limpia) a distintos zooms y áreas del territorio.
3. **Tunear `ROADS_WFS_TIMEOUT_SECONDS` y `ROADS_FEATURE_DEFAULT_LIMIT`** con uso real. El WFS de IDEE es variable; con `limit ≤ 10` responde en <600 ms, con `limit ≥ 20` agota timeout intermitentemente.
4. **Confirmar el umbral `ROADS_PRIMARY_MIN_ZOOM = 12`** tras observar comportamiento. Si la latencia del WFS resulta aceptable a z=11 con limit alto, podría bajarse.
5. **Filtros UI por `clase`, `titular`, `acceso`, `estado_fisico`** si se decide ofrecer al usuario controles más finos que el escalonado automático por zoom.
6. **Política de refresco del fallback local**: hoy manual (descarga del CNIG, importador, refresh `core` y `pub`). Decidir cadencia (semestral, anual) y si automatizar.
7. **Exposición al chat LLM**: evaluar tools `roads_near_point`, `road_class_at_bbox` reusando el contrato común, dentro del módulo `chat/`.
8. **Documentar en `README.md`** la nueva capa, sus dependencias (PostGIS, datos en `data-store/files/raw/ign/igr_rt/`, refresh SQL) y los endpoints `/api/roads/*`.

## 12. Referencias clave

- IDEE WFS transportes: `https://servicios.idee.es/wfs-inspire/transportes?REQUEST=GetCapabilities&SERVICE=WFS&VERSION=2.0.0`
- OGC API-Features IDEE: `https://api-features.idee.es/collections`
- INSPIRE Transport Networks: `https://inspire.ec.europa.eu/id/document/tg/tn`
- Centro de Descargas CNIG, Redes de Transporte: `https://centrodedescargas.cnig.es/CentroDescargas/redes-transporte`
- Modelo Físico IGR-RT v1.9: `https://centrodedescargas.cnig.es/CentroDescargas/documentos/ModeloFisico_IGR-RT_V1_9_publicado.pdf`
- Sistema Cartográfico Nacional: `https://www.scne.es/`
- Nota hermana con el detalle histórico paso a paso: `doc/notas/06-poblacion-carreteras-y-espacios-protegidos/capa-contexto-carreteras-igr-rt.md`

## Datos explícitos
- WFS de IDEE es la fuente primaria, IGR-RT local es el fallback.
- El contrato común publica los mismos campos sea cual sea la fuente activa.
- El pivote WFS↔local es `inspireId.localId = "VIAL_TR" + id_tramo`.
- `core.road_segment` tiene 9.879.049 filas; `source.igr_rt_tramo_vial` tiene 10.719.026.
- El escalonado por zoom va desde z=7 (autopistas) hasta z=16 (senda).
- Los índices parciales `_highways_`, `_arterials_` e `_interurban_` aceleran z=7-10.
- La simplificación geométrica y el gzip llevan z=7 de 31 s/1,7 MB a 0,72 s/386 KB.
- El pane `roadsLayerPane` está a `z-index 290`, por debajo de las capas temáticas para no bloquear sus clicks.
- La simbología es propia del proyecto, inspirada en OSM, IGN y Google Maps.
- IGR-RT se distribuye bajo licencia compatible CC-BY 4.0; el WFS es servicio público de IDEE.

## Datos inferidos
- La nota pertenece al área `06-poblacion-carreteras-y-espacios-protegidos/`.
- Tipo `proceso` porque consolida una decisión ya cerrada y describe el flujo completo de implementación.
- La fecha de elaboración del proceso documentado es 2026-05-20.

## Datos faltantes o ambiguos
- Fórmula literal exacta de atribución para la versión IGR-RT concreta descargada.
- Si la política de refresco del fallback local será manual o automatizada.
- Si el umbral z=12 entre primaria y fallback necesita ajuste tras uso real.
