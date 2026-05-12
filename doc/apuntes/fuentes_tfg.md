# Fuentes de datos, consulta y construcción — MeteoVisor España
## Documento de apoyo para el TFG

> Revisión actualizada a abril de 2026 a partir del estado real del prototipo,
> los scripts de generación incluidos en el repositorio y las fuentes oficiales
> consultadas durante el desarrollo.

Este documento resume las fuentes de datos, servicios web, APIs y procesos de
construcción utilizados o recomendados para el visor MeteoVisor España. Se ha
separado el estado de cada fuente para evitar mezclar lo ya implementado con lo
explorado o pendiente.

---

## 0. Estado de integración de las fuentes

| Fuente | Uso en el prototipo | Estado |
|---|---|---|
| AEMET OpenData | Avisos meteorológicos CAP activos | Implementado |
| NASA FIRMS | Hotspots recientes VIIRS, filtrados por España; MODIS opcional para contraste histórico/validación | Implementado |
| EFFIS/Copernicus WMS | FWI y DC diarios | Implementado |
| EFFIS/Copernicus WMTS | Focos VIIRS `viirs.hs.today` evaluados para comparación con FIRMS | Descartado como capa operativa |
| SNCZI/MITECO | Zonas inundables fluviales T=10 vía WMS | Implementado |
| CORINE Land Cover 2018 | WMS completo y GeoJSON local filtrado | Implementado |
| API-Features IGN `nuc` | Núcleos de población descargados a GeoJSON local | Generado, pendiente de integrar en el frontend |
| IGN transportes | Red viaria / transporte | Fuente recomendada, pendiente |
| MITECO ENP / Red Natura 2000 | Exposición ambiental | Fuente recomendada, pendiente |
| Histórico AEMET | Archivo oficial de avisos desde 18/06/2018 | Pendiente |
| Límite territorial de España | Filtro espacial y recorte visual | Implementado con GeoJSON local GISCO/NUTS 2024 |

---

## 1. Avisos meteorológicos — AEMET OpenData

### Fuente principal

La fuente principal de avisos meteorológicos adversos es la API REST oficial
de AEMET OpenData. Los avisos se publican dentro del marco Meteoalerta y se
sirven en formato CAP (Common Alerting Protocol).

- **Portal AEMET OpenData:** https://opendata.aemet.es
- **Página AEMET datos abiertos:** https://www.aemet.es/es/datos_abiertos/AEMET_OpenData
- **Nota legal AEMET:** https://www.aemet.es/es/nota_legal
- **Documentación Swagger:** https://opendata.aemet.es/dist/index.html
- **Catálogo datos.gob.es:** https://datos.gob.es/es/catalogo/e05068001-avisos-meteorologicos
- **FAQ oficial AEMET OpenData:** https://opendata.aemet.es/centrodedescargas/docs/FAQs220424.pdf

### Endpoints usados en el prototipo

```http
GET https://opendata.aemet.es/opendata/api/avisos_cap/ultimoelaborado/area/esp
GET https://opendata.aemet.es/opendata/api/avisos_cap/ultimoelaborado/area/can
```

`esp` cubre Península y Baleares. `can` cubre Canarias, por lo que el backend
consulta ambos ámbitos y combina los avisos resultantes.

### Formato y parseo

Los avisos se sirven como ficheros XML CAP 1.2, normalmente empaquetados en un
TAR comprimido con gzip. AEMET OpenData usa un patrón de doble petición:

1. La primera petición devuelve un JSON de metadatos con el campo `datos`.
2. La segunda petición descarga el recurso real desde la URL indicada en
   `datos`.

Campos extraídos actualmente:

- `identifier`
- `event`
- `onset`
- `expires`
- `areaDesc`
- `polygon`
- `description`
- `instruction`

El namespace CAP usado por el parser es:

```text
urn:oasis:names:tc:emergency:cap:1.2
```

### Clasificación de nivel

El prototipo extrae el nivel meteorológico a partir del texto de `event`,
buscando las palabras clave:

| Texto encontrado | Nivel interno | Color |
|---|---|---|
| `rojo` | Rojo | `#CC0000` |
| `naranja` | Naranja | `#FFA500` |
| `amarillo` | Amarillo | `#FFD700` |
| `verde` | Verde | `#4CAF50` |

Esta lógica es práctica para la demo, pero para una versión más robusta conviene
comprobar si el CAP incluye campos más estructurados o códigos de severidad que
permitan evitar dependencias del texto.

### Histórico AEMET

El catálogo oficial de datos indica que existe distribución de archivo para
avisos de fenómenos meteorológicos adversos con datos desde el **18/06/2018**.
Esto encaja con el objetivo del TFG de construir una base histórica.

Uso recomendado para la siguiente fase:

- descargar avisos por rango de fechas desde el endpoint de archivo documentado
  en Swagger;
- guardar `identifier`, fenómeno, nivel, zona, inicio, fin, geometría y fecha de
  elaboración;
- conservar versiones sucesivas de un mismo aviso para estudiar intensificación,
  actualización y retirada;
- almacenar la fecha/hora de descarga para trazabilidad.

### Limitaciones y notas

- La API requiere clave `AEMET_API_KEY`.
- La API puede devolver errores de límite de uso (`429 Too Many Requests`) si se
  consulta con demasiada frecuencia; conviene cachear resultados y reintentar con
  espera.
- La reutilización de datos de AEMET en descarga, visualización y análisis debe
  citar a AEMET como fuente, de acuerdo con su nota legal.
- Los avisos activos cubren el presente y próximas horas, no sustituyen al
  archivo histórico.
- El visor no debe presentar los avisos como decisiones operativas propias:
  siempre deben citar a AEMET como fuente.

---

## 2. Focos de incendio — NASA FIRMS

### Fuente principal

NASA FIRMS (Fire Information for Resource Management System) proporciona
detecciones satelitales de incendios activos o anomalías térmicas. Para la
obtención y tratamiento de focos activos, el prototipo usa principalmente datos
VIIRS recientes en CSV mediante la API de área de FIRMS.

- **Portal FIRMS:** https://firms.modaps.eosdis.nasa.gov
- **API FIRMS:** https://firms.modaps.eosdis.nasa.gov/api/
- **Solicitud de MAP_KEY:** https://firms.modaps.eosdis.nasa.gov/api/map_key
- **Guía de uso de la API:** https://firms.modaps.eosdis.nasa.gov/content/academy/data_api/firms_api_use.html
- **Atributos MODIS y VIIRS:** https://www.earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs
- **VIIRS I-Band 375 m Active Fire Data:** https://www.earthdata.nasa.gov/data/instruments/viirs/viirs-i-band-375-m-active-fire-data
- **VIIRS 375 m Active Fire Product User's Guide v1.2:** https://www.earthdata.nasa.gov/s3fs-public/2025-06/VIIRS_C2_AF-375m_User_Guide_1.2.pdf
- **NOAA/NESDIS - JPSS Satellite and Instruments:** https://www.nesdis.noaa.gov/our-satellites/currently-flying/joint-polar-satellite-system/jpss-satellite-and-instruments
- **NOAA OSPO - Hazard Mapping System Fire and Smoke Product:** https://www.ospo.noaa.gov/Products/land/hms.html
- **FIRMS FAQ:** https://www.earthdata.nasa.gov/data/tools/firms/faq
- **Schroeder et al. (2014), VIIRS 375 m active fire:** https://doi.org/10.1016/j.rse.2013.12.008
- **Giglio et al. (2016), MODIS Collection 6 active fire:** https://doi.org/10.1016/j.rse.2016.02.054
- **Hawbaker et al. (2008), detección MODIS y tamaño de incendio:** https://doi.org/10.1016/j.rse.2007.12.008
- **Hawbaker et al. (2017), áreas quemadas Landsat, no comparativa directa VIIRS/MODIS:** https://doi.org/10.1016/j.rse.2017.06.027

La interpretación de los atributos se apoya en la documentación oficial de NASA
Earthdata. En particular, las páginas de atributos MODIS/VIIRS y del producto
VIIRS I-Band 375 m describen `confidence`, `frp`, `acq_time`, `satellite` y
`daynight`; la FAQ de FIRMS se usa como referencia complementaria para las
limitaciones y cautelas de uso de las detecciones.

### Endpoint usado

```http
GET https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{BBOX}/{DAY_RANGE}
```

Configuración actual del backend:

```text
DAY_RANGE = 1

Fuentes VIIRS NRT:
- VIIRS_NOAA21_NRT
- VIIRS_NOAA20_NRT
- VIIRS_SNPP_NRT

Fuente opcional:
- MODIS_NRT, activable con FIRMS_INCLUDE_MODIS=true

BBOX Península, Baleares, Ceuta y Melilla:
-10.0,35.0,4.6,44.2

BBOX Canarias:
-18.5,27.5,-13.0,29.6
```

La versión antigua del documento mencionaba sólo `VIIRS_SNPP_NRT`; eso ya no
refleja el código actual. El prototipo consulta tres productos VIIRS NRT para
reducir dependencia de un único satélite.

### Criterio de priorización: VIIRS frente a MODIS

Para la detección operativa de puntos calientes de NASA FIRMS, el prototipo
prioriza **VIIRS** y deja **MODIS** como fuente complementaria. La idea principal
es que VIIRS ofrece mayor sensibilidad espacial, mejor utilidad en vigilancia
casi en tiempo real y más precisión para integrar los focos en un visor GIS.

Comparativa técnica clave:

| Característica | VIIRS (NOAA-21/NOAA-20/Suomi NPP) | MODIS (Terra/Aqua) |
|---|---|---|
| Resolución espacial | **375 m** (alta) | **1 km** (media) |
| Sensibilidad a focos pequeños | Muy alta | Limitada |
| Detección nocturna | Excelente para focos térmicos pequeños; requiere cautela con artefactos de plumas muy calientes | Correcta, pero con píxel más grueso |
| Frecuencia de revisita | Aproximadamente 12 h por satélite polar; el uso combinado de 3 productos NRT reduce huecos temporales | Aproximadamente 12 h por satélite polar; 2 plataformas |
| Número de satélites/plataformas en FIRMS NRT | 3 (`NOAA-21`, `NOAA-20`, `Suomi NPP`) | 2 (`Terra`, `Aqua`) |
| Latencia NRT en FIRMS global | `< 3 h` desde la observación satelital hasta la disponibilidad en FIRMS | `< 3 h` desde la observación satelital hasta la disponibilidad en FIRMS |
| Precisión de geolocalización | Alta: centro de píxel nominal de 375 m | Media: centro de píxel de 1 km, no necesariamente ubicación real del fuego |
| Nivel de falsos positivos | Bajo-medio; puede haber artefactos, especialmente en detecciones nocturnas asociadas a plumas supercalentadas | Medio; producto maduro, pero más condicionado por el tamaño de píxel y la mezcla de señales dentro del píxel |
| Madurez del producto | Alta, aunque con una serie temporal más reciente que MODIS | Muy alta; serie histórica larga y muy validada |
| Rol recomendado en MeteoVisor | Fuente principal operativa | Apoyo histórico, contraste y validación |

Matización importante: VIIRS no equivale a observación continua en sentido
estricto, porque depende de pasos orbitales. Lo correcto en la memoria es
presentarlo como una fuente **NRT** con observaciones día/noche y varias
plataformas, no como monitorización instantánea permanente.

Sobre latencia, conviene distinguir entre disponibilidad del producto NRT y
envío de alertas. FIRMS indica una disponibilidad global NRT inferior a 3 horas
para detecciones activas MODIS y VIIRS. En las alertas por correo, la propia FAQ
matiza que normalmente se envían dentro de 3 horas para MODIS y dentro de 4
horas para VIIRS.

La justificación técnica se apoya en NASA FIRMS, NASA Earthdata, NOAA/NESDIS,
NOAA OSPO y la literatura científica. La FAQ de FIRMS identifica productos
activos globales MODIS y VIIRS en NRT, con resolución de 1 km para MODIS y 375 m
para VIIRS, y latencia global inferior a 3 horas. NOAA/NESDIS describe VIIRS
como instrumento de 375 m capaz de detectar, localizar y cartografiar incendios
forestales. La documentación de atributos de NASA Earthdata diferencia
claramente el centro de píxel de 1 km de MODIS frente al píxel nominal de 375 m
de VIIRS, y la documentación del producto VIIRS 375 m señala que la mayor
resolución mejora la respuesta sobre fuegos pequeños y el mapeo de perímetros.
NOAA OSPO añade cautelas sobre artefactos nocturnos en VIIRS cuando existen
plumas supercalentadas, por lo que la mayor sensibilidad no debe interpretarse
como ausencia de falsos positivos.

El algoritmo VIIRS 375 m se describe en Schroeder et al. (2014) y hereda parte
del enfoque de los productos MODIS, pero adaptado a las bandas I de VIIRS. MODIS,
por su parte, es una serie más antigua y valiosa para continuidad histórica;
Giglio et al. (2016) documentan el algoritmo MODIS Collection 6 y sus mejoras,
mientras que Hawbaker et al. (2008) muestra que la detección MODIS disminuye con
el tamaño del incendio y puede infrarrepresentar fuegos pequeños, rápidos o de
baja intensidad.

Conclusión para el TFG:

- Según NASA, NOAA y la literatura técnica, **VIIRS mejora a MODIS en resolución,
  detección temprana de focos pequeños y precisión espacial para integración
  GIS**.
- **VIIRS** debe tratarse como fuente principal de focos activos para uso
  operativo del prototipo.
- **MODIS** sigue siendo útil por madurez e histórico, pero queda como
  complemento no crítico para series históricas, contraste metodológico o
  validación cruzada.
- La referencia "Hawbaker et al. (2017)" debe revisarse antes de citarla como
  comparativa VIIRS/MODIS: la referencia localizada con ese año trata de
  cartografía de áreas quemadas con series Landsat, útil para validación de
  históricos de incendio, pero no como comparación directa de sensores VIIRS y
  MODIS.

### Campos procesados

Campos conservados actualmente:

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

Campos añadidos por el backend:

- `id`
- `acq_datetime_utc`
- `source`
- `firms_source`
- `query_area`
- `level`
- `level_color`
- `intensity_label`
- `intensity_color`
- `confidence_code`
- `confidence_label`

### Simbología por FRP

La simbología visual se basa en Fire Radiative Power (`frp`), expresado en MW.
Según la documentación de NASA Earthdata para VIIRS, `frp` representa la
potencia radiativa integrada del píxel de fuego en megavatios. En el visor se
usa como proxy de intensidad radiativa del foco, no como gravedad oficial del
incendio.

La interpretación de `frp` debe hacerse con cautela porque el valor depende de
factores instrumentales y de observación, entre ellos la saturación térmica del
canal infrarrojo, la geometría de observación, el sensor/plataforma y las
condiciones día/noche. La documentación del producto VIIRS 375 m advierte,
además, de que la recuperación sistemática de FRP tiene limitaciones cuando hay
saturación y se apoya en una aproximación híbrida con datos VIIRS de distinta
resolución.

La documentación oficial no define umbrales universales de severidad basados en
FRP. Por tanto, la representación cartográfica adoptada en el prototipo es:

- Color del punto: intensidad visual derivada de `frp`.
- Simbología secundaria: nivel de `confidence`, representado con el grosor del
  borde.
- Leyenda: potencia radiativa del foco (`FRP`, MW).

| FRP | Categoría visual | Color |
|---|---|---|
| `< 10 MW` | Bajo | `#FFD166` |
| `10 - 50 MW` | Medio | `#F8961E` |
| `50 - 200 MW` | Alto | `#E94F37` |
| `> 200 MW` | Muy alto | `#8E1B1B` |

Estas categorías son una regla visual del prototipo y no una escala oficial de
riesgo o severidad publicada por NASA FIRMS.

La confianza de detección no se usa como color principal porque mide una cosa
distinta de la potencia radiativa. El frontend la representa con el borde del
punto:

| `confidence` | Etiqueta | Borde |
|---|---|---|
| `n` | nominal | fino |
| `h` | alta | marcado |

### Filtrado geográfico

El filtrado final ya no usa `world-geojson`. Ahora se usa el fichero local:

```text
data/boundaries/spain_nuts_2024_01m.geojson
```

Este GeoJSON contiene el límite nacional de España de GISCO/NUTS 2024
(`NUTS_ID = ES`) y cubre Península, Baleares, Canarias, Ceuta y Melilla. El
backend lo carga con `shapely`, fusiona las geometrías y conserva sólo los
puntos FIRMS cuyo `Point(lon, lat)` cae dentro del MultiPolygon.

### Filtro por `confidence`

Para las fuentes VIIRS de FIRMS, `confidence` representa el nivel de confianza
del algoritmo en que el píxel corresponda realmente a un foco activo. NASA
Earthdata lo describe como una clasificación cualitativa baja, nominal o alta
(`l`, `n`, `h` en los CSV de FIRMS).

En el prototipo, `confidence` se emplea como criterio de filtrado y no como
variable principal de color. Para reducir falsos positivos, se conservan sólo:

```text
confidence in ("n", "h")
```

Es decir, se descartan detecciones de confianza baja para reducir falsos
positivos. Este filtro afecta al número de focos mostrados y forma parte de la
justificación para mantener FIRMS como fuente operativa de focos tras evaluar
EFFIS/Copernicus. Si se activa la fuente opcional `MODIS_NRT`, conviene revisar
esta regla porque su codificación de confianza no
es necesariamente equivalente a la categórica de VIIRS.

### Limitaciones

- FIRMS detecta anomalías térmicas, no incendios confirmados administrativamente.
- Puede haber falsos positivos, duplicados temporales o detecciones cercanas del
  mismo evento.
- Las categorías visuales de intensidad por `frp` son una convención propia del
  visor. No deben presentarse como clases oficiales de NASA FIRMS ni como
  umbrales universales de severidad.
- `confidence` y `frp` miden atributos distintos: el primero resume confianza de
  detección; el segundo cuantifica potencia radiativa del foco en MW.
- El `DAY_RANGE=1` devuelve datos recientes; para histórico se deben usar
  productos estándar o consultas por fecha si están disponibles para el producto.
- El uso de `MAP_KEY` está sujeto a ventana de transacciones; NASA ofrece el
  endpoint `mapkey_status` para comprobar consumo.

---

## 3. EFFIS / Copernicus — peligro de incendio y focos activos evaluados

### Fuente

EFFIS (European Forest Fire Information System) forma parte del componente de
alerta temprana del Copernicus Emergency Management Service. Proporciona
información sobre peligro meteorológico de incendio, focos activos, áreas
quemadas y estadísticas.

- **Portal EFFIS:** https://forest-fire.emergency.copernicus.eu
- **Datos y servicios:** https://forest-fire.emergency.copernicus.eu/applications/data-and-services
- **Instrucciones de descarga:** https://forest-fire.emergency.copernicus.eu/downloads-instructions
- **Peligro de incendio FWI:** https://forest-fire.emergency.copernicus.eu/about-effis/technical-background/fire-danger-forecast
- **Detección de fuegos activos:** https://forest-fire.emergency.copernicus.eu/about-effis/technical-background/active-fire-detection
- **Licencia:** https://forest-fire.emergency.copernicus.eu/about-effis/data-license

### Servicios usados

```text
WMS índices:
https://maps.effis.emergency.copernicus.eu/effis
```

### Capas implementadas

| Capa | Servicio | Uso | Estado |
|---|---|---|---|
| `mf010.fwi` | WMS | Fire Weather Index, modelo MeteoFrance ~10 km | Implementada |
| `mf010.dc` | WMS | Drought Code, subcomponente del FWI | Implementada |

La capa `viirs.hs.today` de focos activos EFFIS/Copernicus se llegó a evaluar
como contexto y contraste frente a `NASA FIRMS`, pero se ha retirado del visor
como capa operativa. La implementación disponible dependía de vectorizar
teselas `WMTS/WMS` rasterizadas, por lo que el resultado no conservaba atributos
originales equivalentes a los de FIRMS ni ofrecía un contrato vectorial estable.

La decisión final es mantener EFFIS en el visor para el contexto meteorológico
de propagación (`FWI` y `DC`) y usar `NASA FIRMS` como única fuente visible de
focos activos. La comparativa queda documentada como criterio de alcance: se
revisó EFFIS/Copernicus, pero se descartó publicar una capa diaria derivada por
píxeles para evitar ambigüedad analítica, mantenimiento extra y duplicidad de
mensajes frente a FIRMS.

### Parámetros WMS relevantes

Para `mf010.fwi` y `mf010.dc`:

```text
SERVICE=WMS
VERSION=1.1.1
REQUEST=GetMap
LAYERS=mf010.fwi / mf010.dc
STYLES=
FORMAT=image/png
TRANSPARENT=true
TIME=YYYY-MM-DD
```

Según las instrucciones de descarga de EFFIS, el parámetro `TIME` es necesario
para la mayoría de capas temporales. En el visor se usa la fecha local del día
actual.

### Clasificación FWI oficial usada en la leyenda

EFFIS agrupa el FWI en seis clases. La clase "Very Extreme" se introdujo en
junio de 2021 para distinguir situaciones mediterráneas con FWI superior a 70.

| Clase en visor | Clase EFFIS | Umbral FWI | Color usado |
|---|---|---|---|
| Bajo | Low | `< 11.2` | `#9CFFC0` |
| Moderado | Moderate | `11.2 - 21.3` | `#CDE24E` |
| Alto | High | `21.3 - 38.0` | `#E6AC00` |
| Muy alto | Very High | `38.0 - 50.0` | `#D97010` |
| Extremo | Extreme | `50.0 - 70.0` | `#AD060E` |
| Muy extremo | Very Extreme | `> 70.0` | `#3A0015` |

Corrección frente a la versión antigua: se elimina la clase separada "Muy bajo
< 5.2", porque no es la clasificación que usa actualmente la leyenda del
prototipo ni la tabla EFFIS consultada.

### Clasificación DC oficial usada en la leyenda

| Clase en visor | Umbral DC | Color usado |
|---|---|---|
| Bajo | `< 256.1` | `#9CFFC0` |
| Moderado | `256.1 - 334.1` | `#CDE24E` |
| Alto | `334.1 - 450.6` | `#E6AC00` |
| Muy alto | `450.6 - 600.0` | `#D97010` |
| Extremo | `600.0 - 749.4` | `#AD060E` |
| Muy extremo | `> 749.4` | `#3A0015` |

Corrección frente a la versión antigua: la clasificación `100 / 300 / 600` era
demasiado genérica y no coincidía con la tabla EFFIS usada en el frontend.

---

## 4. Zonas inundables — MITECO / SNCZI

### Fuente

El Sistema Nacional de Cartografía de Zonas Inundables (SNCZI), gestionado en
el ámbito de MITECO, publica mapas de peligrosidad de inundación conforme a la
Directiva 2007/60/CE y al Real Decreto 903/2010.

- **Portal SNCZI:** https://www.miteco.gob.es/es/agua/temas/gestion-de-los-riesgos-de-inundacion/snczi.html
- **Visor SNCZI:** https://sig.miteco.gob.es/snczi/
- **Ficha datos.gob.es del WMS:** https://datos.gob.es/es/catalogo/e0dat0002-servicio-wms-web-map-service-peligrosidad-por-inundacion
- **Endpoint WMS:** `https://servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones`
- **GetCapabilities:** `https://servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities`

### Capas relevantes

| Capa | Descripción | Probabilidad aproximada |
|---|---|---|
| `NZ.Flood.FluvialT10` | Inundación fluvial frecuente | Alta |

Capa implementada:

```text
NZ.Flood.FluvialT10
```

Se usa como escenario estándar de peligrosidad alta para cruzarlo en el futuro
con avisos de lluvia, tormenta, deshielo, DANA u otros fenómenos hidrológicos.

### Nota técnica WMS

El servicio se consume como WMS 1.3.0. En Leaflet, al no fijar un CRS manual,
las teselas se solicitan con el CRS del mapa. Si se hacen peticiones manuales
con `EPSG:4326` y WMS 1.3.0, hay que recordar el orden de ejes propio de esa
versión; usar `CRS:84` evita confusiones de orden lon/lat.

---

## 5. Usos del suelo — CORINE Land Cover 2018

### Fuente

CORINE Land Cover es un inventario europeo de cobertura del suelo coordinado
por la Agencia Europea de Medio Ambiente dentro de Copernicus Land Monitoring
Service. En España se distribuye a través de IGN/CNIG.

- **Centro de Descargas CNIG:** https://centrodedescargas.cnig.es/CentroDescargas/corine-land-cover
- **Producto CLMS CLC 2018:** https://land.copernicus.eu/en/products/corine-land-cover/clc2018
- **FAQ CLMS CORINE:** https://land.copernicus.eu/en/faq/products/corine-land-cover
- **WMS IDEE ocupación del suelo:** `https://servicios.idee.es/wms-inspire/ocupacion-suelo`
- **GetCapabilities:** `https://servicios.idee.es/wms-inspire/ocupacion-suelo?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities`
- **Portal SIOSE:** https://www.siose.es/presentacion

### WMS consultado en el visor

| Capa | Uso |
|---|---|
| `LC.LandCoverSurfaces` | Cobertura terrestre completa |
| `LU.ExistingLandUse` | Usos del suelo existentes |

El frontend incluye una capa WMS completa de CORINE/SIOSE y, además, una capa
GeoJSON local filtrada para análisis de incendio.

### GeoPackage de origen

El script de procesado espera:

```text
data/CLC2018_ES.gpkg
```

Capas leídas:

| Capa | Ámbito |
|---|---|
| `CLC18_ES` | Península, Baleares, Ceuta y Melilla |
| `CLC18_ES_Canarias` | Canarias |

El CNIG distribuye CORINE 2018 para toda España en GeoPackage y Geodatabase. El
sistema de referencia es ETRS89 para Península, Baleares, Ceuta y Melilla, y
REGCAN95 para Canarias, con proyección UTM en el huso correspondiente.

### Clases filtradas para riesgo de incendio

Script:

```text
generar_landcover.py
```

Salida:

```text
data/landcover.geojson
```

El fichero actual contiene 9 features, una por clase disuelta:

| Código | Clase | Color | Uso funcional |
|---|---|---|---|
| 211 | Tierras de labor secano | `#ffffa8` | Agrícola |
| 242 | Mosaico de cultivos | `#e6e600` | Agrícola |
| 311 | Bosque de frondosas | `#4ce600` | Forestal |
| 312 | Bosque de coníferas | `#267300` | Forestal |
| 313 | Bosque mixto | `#70a800` | Forestal |
| 321 | Pastizales naturales | `#d4e6a5` | Vegetación natural |
| 322 | Brezales y matorrales | `#a8a800` | Matorral |
| 323 | Vegetación esclerófila | `#d4a46a` | Matorral mediterráneo |
| 324 | Matorral en transición | `#c8c800` | Matorral/transición |

Nota de coherencia: la capa local sí contiene la clase `324`. Si la leyenda del
frontend lista sólo ocho clases, conviene añadir `Matorral en transición` para
que la documentación, el dato y la interfaz coincidan.

### Pipeline de procesado

1. Leer `CLC18_ES` y `CLC18_ES_Canarias` con `geopandas`.
2. Filtrar los códigos de interés (`CODE_18`).
3. Reproyectar a EPSG:4326.
4. Combinar Península/Baleares/Ceuta/Melilla y Canarias.
5. Simplificar geometrías con `tolerance=0.005` y `preserve_topology=True`.
6. Disolver por `CODE_18`.
7. Añadir color y etiqueta.
8. Exportar a `data/landcover.geojson`.

### Limitaciones

- CORINE trabaja a escala 1:100.000.
- La unidad mínima de mapeo es 25 ha para polígonos de estado.
- No es adecuado para análisis local fino o zooms muy altos.
- Para más detalle se podría valorar SIOSE o SIOSE Alta Resolución.

---

## 6. Núcleos de población — API-Features IGN

### Fuente

La API-Features del IGN expone datos vectoriales mediante OGC API Features.
La colección `nuc` contiene núcleos de población identificados por el INE.

- **Portal API-Features IGN:** https://api-features.ign.es
- **Colecciones:** https://api-features.ign.es/collections
- **OpenAPI HTML:** https://api-features.ign.es/openapi?f=html
- **Colección `nuc`:** https://api-features.ign.es/collections/nuc/items?f=html

### Colecciones relevantes

| Colección | Descripción | Uso potencial |
|---|---|---|
| `/collections/nuc` | Núcleos de población | Exposición humana |
| `/collections/namedplace` | Nomenclátor / topónimos | Búsqueda geográfica |
| `/collections/administrativeunit` | Unidades administrativas | Agregación territorial |
| `/collections/administrativeboundary` | Límites administrativos | Cruces por municipio/provincia |

### Consulta ejemplo

```http
GET https://api-features.ign.es/collections/nuc/items?bbox=-4.5,40,-3.5,41&limit=50&f=json
```

### Datos actuales observados

La colección `nuc` publica 37.497 elementos. Campos de interés:

- `nombre`
- `habitantes`
- `codine`
- `cpro`
- `capital`
- `tipo`
- `latitud`
- `longitud`
- `altitud`
- `fecha`

Las geometrías devueltas son polígonos o multipolígonos del núcleo, no simples
puntos. Esto es útil para visualización de exposición, pero aumenta el tamaño de
transferencia.

### Procesado local

Script:

```text
generar_nucleos.py
```

Salida:

```text
data/nucleos.geojson
```

Configuración:

```text
MIN_HABITANTES = 500
LIMIT = 100
```

El fichero local actual contiene **6.237 núcleos** con 500 habitantes o más.
Las geometrías se simplifican con `tolerance=0.0002`.

Estado: el fichero está generado, pero aún no se sirve ni se visualiza desde el
frontend. Para integrarlo convendría añadir endpoint `/api/nucleos`, capa
Leaflet y visibilidad por zoom.

---

## 7. Límite territorial de España — GISCO / NUTS 2024

### Uso en el prototipo

El límite territorial se usa para:

- filtrar hotspots FIRMS dentro de España;
- recortar visualmente capas WMS EFFIS al ámbito español;
- evitar que los BBOX de consulta incluyan puntos de Portugal, Marruecos o mar.

Fichero local:

```text
data/boundaries/spain_nuts_2024_01m.geojson
```

Contenido:

```text
NUTS_ID = ES
LEVL_CODE = 0
CNTR_CODE = ES
NUTS_NAME = España
```

La versión antigua del documento citaba `world-geojson`. Esa referencia queda
obsoleta para el prototipo actual.

Fuente recomendada para citar:

- **Eurostat GISCO / NUTS:** https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units/territorial-units-statistics

---

## 8. Red viaria y transportes — IGN / IDEE

### Fuente recomendada

Para cubrir el requisito de afección a carreteras, la fuente más coherente con
el resto del proyecto es la red de transporte del Sistema Cartográfico Nacional
publicada por IGN/IDEE.

- **Servicios web IGN:** https://www.ign.es/web/en/ide-area-nodo-ide-ign
- **Ficha datos.gob.es WMS transporte:** https://datos.gob.es/es/catalogo/e0dat0002-wms-de-redes-de-transporte-de-espana
- **Ficha datos.gob.es WFS transporte:** https://datos.gob.es/es/catalogo/e0dat0002-wfs-de-redes-e-infraestructuras-del-transporte-de-espana
- **WMS transportes:** `https://servicios.idee.es/wms-inspire/transportes`
- **WFS transportes:** `https://servicios.idee.es/wfs-inspire/transportes`

### Uso propuesto

| Necesidad | Servicio recomendado |
|---|---|
| Visualización simple de carreteras | WMS |
| Cruces espaciales y cálculo de proximidad | WFS o descarga vectorial |
| Clasificación red principal/secundaria | WFS/descarga, si los atributos lo permiten |

Pendiente: identificar las capas y atributos concretos mediante
`GetCapabilities`/`DescribeFeatureType`, y decidir si se usa servicio remoto o
una capa vectorial local simplificada.

---

## 9. Espacios protegidos y biodiversidad — MITECO

### Fuentes recomendadas

Para valorar afección ambiental en incendios o episodios de riesgo, las fuentes
más adecuadas son el Banco de Datos de la Naturaleza de MITECO, Red Natura 2000
y Espacios Naturales Protegidos.

- **Red Natura 2000:** https://www.miteco.gob.es/es/biodiversidad/servicios/banco-datos-naturaleza/informacion-disponible/red_natura_2000_inf_disp.html
- **Espacios Naturales Protegidos:** https://www.miteco.gob.es/es/biodiversidad/servicios/banco-datos-naturaleza/informacion-disponible/enp.html
- **Servidor cartográfico WMS biodiversidad:** https://www.miteco.gob.es/es/biodiversidad/servicios/banco-datos-naturaleza/servidor-cartografico-wms-.html
- **WMS Red Natura 2000:** `https://wms.mapama.gob.es/sig/Biodiversidad/RedNatura/wms.aspx`
- **WMS Inventario ENP/RN2000/AAPP internacionales:** `https://wms.mapama.gob.es/sig/Biodiversidad/IEAAPP/wms.aspx`

### Uso propuesto

| Capa | Uso en el TFG |
|---|---|
| Red Natura 2000 | Identificar espacios protegidos potencialmente afectados |
| Espacios Naturales Protegidos | Priorizar afección ambiental |
| Áreas protegidas internacionales | Complemento si el alcance lo permite |

Estado: pendiente de integrar. Para análisis real no basta con WMS; conviene
descargar o consumir vectorialmente la capa para calcular intersecciones con
avisos, focos y áreas de influencia.

---

## 10. Infraestructura IDEE / IGN

### Servicios base consultados

| Servicio | URL base | Uso |
|---|---|---|
| Ocupación del suelo | `https://servicios.idee.es/wms-inspire/ocupacion-suelo` | CORINE/SIOSE |
| Inundaciones | `https://servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones` | SNCZI T=10 |
| Transportes | `https://servicios.idee.es/wms-inspire/transportes` | Red viaria pendiente |
| Transportes WFS | `https://servicios.idee.es/wfs-inspire/transportes` | Análisis vectorial pendiente |
| Mapa base IGN | `https://www.ign.es/wms-inspire/ign-base` | Cartografía base alternativa |
| API-Features IGN | `https://api-features.ign.es` | Núcleos, topónimos, límites |

### Estándares usados

- OGC WMS 1.1.1: EFFIS.
- OGC WMS 1.3.0: IDEE/GeoServer.
- OGC API Features: API-Features IGN.
- CAP 1.2: avisos AEMET.
- GeoJSON: capas locales procesadas.

---

## 11. Stack tecnológico del prototipo

### Backend

- **FastAPI:** https://fastapi.tiangolo.com
- **Uvicorn:** https://www.uvicorn.org
- **httpx:** https://www.python-httpx.org
- **pydantic-settings:** https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- **shapely:** https://shapely.readthedocs.io
- **geopandas:** https://geopandas.org
- **pandas:** https://pandas.pydata.org
- **Pillow:** https://pillow.readthedocs.io

### Frontend

- **Leaflet 1.9.4:** https://leafletjs.com
- **Mapa base actual:** `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png`
- **WMS/GeoJSON/MVT:** capas consumidas desde Leaflet o desde endpoints locales.

Corrección frente a la versión antigua: el frontend actual usa CartoCDN
`light_all`, no `dark_all`.

### Ficheros locales relevantes

| Fichero | Descripción |
|---|---|
| `data/landcover.geojson` | CORINE filtrado y disuelto |
| `data/nucleos.geojson` | Núcleos IGN >= 500 habitantes |
| `data/boundaries/spain_nuts_2024_01m.geojson` | Límite nacional España |

---

## 12. Notas técnicas relevantes para la memoria

### AEMET y trazabilidad

Conviene explicar el patrón de doble petición y guardar tanto la fecha del dato
como la fecha de descarga. Para histórico, el `identifier` no debe tratarse como
única dimensión temporal: un aviso puede cambiar o ser reemplazado.

### FIRMS frente a EFFIS

FIRMS proporciona detecciones puntuales con atributos satelitales (`FRP`,
sensor, hora de adquisición, confianza, etc.). La capa de focos activos EFFIS
evaluada durante el prototipo se obtenía desde teselas rasterizadas, de modo que
la comparación no ofrecía equivalencia directa de atributos. Por eso se decidió
mantener `NASA FIRMS` como única fuente visible de focos activos y dejar EFFIS
como contexto meteorológico mediante `FWI` y `DC`.

### WMS frente a datos vectoriales

Las capas WMS son adecuadas para visualización, pero no para análisis espacial
serio. Para calcular intersecciones, distancias o exposición se necesita:

- descargar vectorialmente los datos;
- consumir WFS/OGC API Features;
- o generar capas locales simplificadas y trazables.

Esto afecta especialmente a inundabilidad, carreteras y espacios protegidos.

### CORINE y escala

CORINE es útil para contexto territorial y clases generales de vegetación o
cultivo. No debe usarse para tomar conclusiones a escala de parcela. En la
memoria se debe indicar su escala 1:100.000 y unidad mínima de 25 ha.

### Núcleos de población

La colección `nuc` es útil porque representa superficies de núcleos, no sólo
puntos. Para rendimiento web, conviene mostrarla por zoom, simplificar por
escala o usar clustering/teselado vectorial si crece el alcance.

### LLM

El LLM debe presentarse como interfaz de consulta y ayuda operativa sobre datos
del visor. No debe inventar riesgo ni sustituir reglas GIS. Cada respuesta debe
indicar fuentes, filtros y operaciones aplicadas.

---

## 13. Fuentes pendientes recomendadas para cerrar el TFG

| Necesidad | Fuente recomendada | Motivo |
|---|---|---|
| Histórico de avisos | Archivo AEMET CAP desde 18/06/2018 | Evolución temporal y validación |
| Red viaria | IGN/IDEE Transportes WFS | Proximidad e impacto en movilidad |
| Exposición ambiental | MITECO ENP / Red Natura 2000 | Afección a espacios protegidos |
| Población | API-Features IGN `nuc` | Exposición humana |
| Validación incendio | FIRMS + CORINE + FWI/DC, con nota de comparación previa frente a EFFIS | Coherencia entre fuente de focos y contexto |
| Validación inundación | AEMET + SNCZI T10 + población/carreteras | Priorización por exposición |

---

## 14. Referencias generales

### Normativa y estándares

- Directiva INSPIRE 2007/2/CE.
- Directiva 2007/60/CE de evaluación y gestión de riesgos de inundación.
- Real Decreto 903/2010, de 9 de julio.
- Ley 42/2007, de Patrimonio Natural y de la Biodiversidad.
- OGC Web Map Service (WMS): https://www.ogc.org/standard/wms/
- OGC Web Map Tile Service (WMTS): https://www.ogc.org/standard/wmts/
- OGC API Features: https://ogcapi.ogc.org/features/
- Common Alerting Protocol 1.2: https://docs.oasis-open.org/emergency/cap/v1.2/

### Fuentes de datos principales

- AEMET OpenData: https://opendata.aemet.es
- NASA FIRMS: https://firms.modaps.eosdis.nasa.gov
- NASA Earthdata - Active Fire Data Attributes for MODIS and VIIRS: https://www.earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs
- NASA Earthdata - VIIRS I-Band 375 m Active Fire Data: https://www.earthdata.nasa.gov/data/instruments/viirs/viirs-i-band-375-m-active-fire-data
- NASA Earthdata - VIIRS 375 m Active Fire Product User's Guide v1.2: https://www.earthdata.nasa.gov/s3fs-public/2025-06/VIIRS_C2_AF-375m_User_Guide_1.2.pdf
- NOAA/NESDIS - JPSS Satellite and Instruments: https://www.nesdis.noaa.gov/our-satellites/currently-flying/joint-polar-satellite-system/jpss-satellite-and-instruments
- NOAA OSPO - Hazard Mapping System Fire and Smoke Product: https://www.ospo.noaa.gov/Products/land/hms.html
- NASA Earthdata - FIRMS FAQ: https://www.earthdata.nasa.gov/data/tools/firms/faq
- Schroeder et al. (2014) - The New VIIRS 375m active fire detection data product: https://doi.org/10.1016/j.rse.2013.12.008
- Giglio et al. (2016) - The Collection 6 MODIS active fire detection algorithm and fire products: https://doi.org/10.1016/j.rse.2016.02.054
- Hawbaker et al. (2008) - Detection rates of the MODIS active fire product in the United States: https://doi.org/10.1016/j.rse.2007.12.008
- Hawbaker et al. (2017) - Mapping burned areas using dense time-series of Landsat data: https://doi.org/10.1016/j.rse.2017.06.027
- EFFIS/Copernicus: https://forest-fire.emergency.copernicus.eu
- Copernicus EMS: https://emergency.copernicus.eu
- Copernicus Land Monitoring Service: https://land.copernicus.eu
- IGN/CNIG: https://www.ign.es
- IDEE: https://www.idee.es
- MITECO/SNCZI: https://www.miteco.gob.es
- API-Features IGN: https://api-features.ign.es

---

*Documento de apoyo para la memoria del TFG de MeteoVisor España.*
*Proyecto: visor web GIS para avisos meteorológicos, focos de incendio y capas de exposición/peligrosidad en España.*
*Tecnologías principales: FastAPI, Leaflet, AEMET OpenData, NASA FIRMS, EFFIS/Copernicus, IGN/IDEE y MITECO.*
