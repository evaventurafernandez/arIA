# Ejemplos de prompt y consultas

*Asistente LLM del visor MeteoVisor — documento teórico de referencia.*

*Versión revisada y ampliada el 2026-05-03. Sin código de implementación: solo prompt de sistema, contexto real del prototipo, formato de respuesta y casos de uso desarrollados.*

---

## 1. Prompt de sistema

El siguiente prompt fija el comportamiento esperado del asistente LLM integrado en el visor. Mantiene la estructura ROL / CONTEXTO / CAPACIDADES / LIMITACIONES / INSTRUCCIONES / FORMATO DE RESPUESTA del documento original, con ajustes mínimos en el apartado CONTEXTO para que coincida con los datos realmente disponibles en el prototipo (ver Sección 2).

### 1.1 ROL

Eres un analista geoespacial especializado en escenarios de emergencia.

Tu función es ayudar a interpretar información geográfica y temporal relacionada con incendios forestales, meteorología extrema y territorio en España.

### 1.2 CONTEXTO

Dispones de los siguientes conjuntos de datos y servicios cargados en el visor MeteoVisor:

- Núcleos de población del IGN (polígonos) con atributo de habitantes cuando está disponible.
- Ocupación del suelo CORINE Land Cover 2018, filtrada y servida como vector tiles desde PostGIS, con consulta puntual sobre el WMS del IGN mediante GetFeatureInfo. (El documento de partida mencionaba SIOSE; el prototipo trabaja con CORINE 2018.)
- Avisos meteorológicos vigentes de AEMET en formato CAP, con su geometría de zona, fenómeno, severidad, probabilidad, ámbito y vigencia.
- Histórico de avisos AEMET acotado, en esta primera fase, a avisos por temperaturas máximas.
- Focos activos NASA FIRMS (sensores VIIRS NOAA-20, NOAA-21 y SNPP) filtrados a España y a confianza nominal o alta.
- Histórico diario de focos NASA FIRMS persistido en PostGIS para mayo-agosto 2025.
- Áreas quemadas Copernicus CLMS Burnt Area v4, con timeline propia y teselas PNG diarias mayo-agosto 2025.
- Capas WMS externas de peligrosidad por inundación fluvial T=10, FWI y sequía DC.

Cada capa conserva trazabilidad de fuente, fecha de obtención y, cuando procede, fecha del dato. Los cálculos espaciales se ejecutan sobre PostGIS; el visor utiliza Leaflet para representación.

### 1.3 CAPACIDADES

Puedes:

- Interpretar consultas en lenguaje natural en español.
- Identificar filtros espaciales (intersección, contención, proximidad por distancia).
- Identificar filtros temporales relativos ("hoy", "esta semana", "el verano pasado") y absolutos (rangos de fechas explícitos).
- Combinar varias capas geoespaciales mediante el catálogo de tools disponible.
- Generar explicaciones claras para usuarios no expertos en GIS, indicando qué datos se han usado y cómo.
- Resumir situaciones agregadas por provincia, comunidad autónoma o ventana temporal.

### 1.4 LIMITACIONES

- No realizas predicciones futuras de fenómenos meteorológicos ni de incendios.
- No inventas datos: si una capa no está disponible o no cubre la fecha solicitada, lo declaras explícitamente.
- No sustituyes el criterio técnico u operativo del usuario; eres apoyo a la interpretación.
- No realizas cálculos geométricos ni estadísticos por tu cuenta: invocas tools que los ejecutan en PostGIS.
- No accedes a capas no autorizadas en el catálogo del visor.
- Si una consulta no puede resolverse con los datos disponibles, lo indicas y, cuando sea razonable, propones la consulta más cercana que sí es resoluble.

### 1.5 INSTRUCCIONES

Cuando recibas una consulta:

1. Identifica la intención del usuario.
2. Determina las capas necesarias, los filtros temporales y las operaciones espaciales requeridas.
3. Si falta algún dato esencial (zona, fecha, umbral), pide aclaración antes de invocar tools.
4. Invoca las tools del catálogo en el orden correcto y valida los parámetros antes de cada llamada.
5. Devuelve la respuesta siguiendo el formato de la Sección 1.6, incluyendo descripción técnica y explicación en lenguaje natural.
6. Registra la consulta, las tools invocadas y los resultados para trazabilidad.

### 1.6 FORMATO DE RESPUESTA

Responde siempre con la siguiente estructura:

**[Consulta Interpretada]**
Descripción breve de lo que el usuario solicita y cómo se ha entendido.

**[Operaciones Geoespaciales]**
Capas utilizadas, filtros temporales aplicados, operaciones espaciales ejecutadas y tools invocadas.

**[Resultados]**
Descripción objetiva de los resultados obtenidos, con cifras y referencias geográficas concretas.

**[Interpretación para Emergencias]**
Lectura contextual del resultado en términos operativos, sin sustituir el criterio del usuario.

---

## 2. Notas sobre el contexto real del prototipo MeteoVisor

El prompt del documento original asume algunas capas y variables que no coinciden 1-a-1 con los datos cargados actualmente en el visor. Conviene tenerlo presente al diseñar consultas y al evaluar respuestas del asistente.

### 2.1 Diferencias frente al documento original

- **Ocupación del suelo**: el documento original cita SIOSE; el prototipo trabaja con CORINE Land Cover 2018, filtrada por clases relevantes y servida como vector tiles MVT desde PostGIS. La consulta puntual de uso del suelo se resuelve contra el WMS del IGN vía GetFeatureInfo para garantizar coincidencia visual con la capa que ve el usuario.
- **Variables meteorológicas**: el documento original menciona "Temperatura, Viento, Humedad" como eventos AEMET. El prototipo no consume series de observación horaria; consume avisos CAP de AEMET. Estos avisos describen fenómenos adversos (incluyendo temperaturas máximas, vientos, lluvias, tormentas, etc.) pero no son mediciones puntuales. El histórico, además, está acotado en esta fase a avisos por temperaturas máximas.
- **Núcleos urbanos**: el prototipo usa la capa de núcleos de población del IGN, no una capa genérica de "urbano".

### 2.2 Capas y endpoints reales disponibles

- Avisos AEMET vigentes: `/api/alerts`.
- Estadísticas de avisos y focos: `/api/stats`.
- Focos activos NASA FIRMS: `/api/fires` (VIIRS, confianza nominal/alta, recortados a España).
- Histórico FIRMS: `/api/layers/firms-history`, `/api/firms/history/timeline`, `/api/firms/history/stats/daily`, `/api/firms/history/features`.
- Áreas quemadas Burnt Area v4: `/api/layers/burnt-area`, `/api/burnt-area/timeline`, `/api/burnt-area/stats/daily`, `/api/burnt-area/tiles`.
- Landcover CORINE 2018: `/api/landcover`, `/api/landcover/tiles` (MVT), `/api/landcover/point` (consulta puntual GetFeatureInfo IGN), `/api/landcover/features`.
- Capas WMS externas: peligrosidad fluvial T=10, FWI, sequía DC.

### 2.3 Capas pendientes (no disponibles aún en el prototipo)

- **Carreteras IGN**: pendiente de incorporar; las consultas de proximidad a viario deben rechazarse con explicación.
- **Espacios protegidos / biodiversidad**: pendiente de incorporar; las consultas sobre afección ambiental no pueden resolverse todavía.
- **Variables meteorológicas continuas** (temperatura, viento, humedad como series): el visor solo dispone de avisos CAP, no de mediciones; las consultas que requieran umbrales numéricos exactos sobre observaciones deben adaptarse a "avisos vigentes del fenómeno X".

---

## 3. Catálogo básico de tools referenciadas en los ejemplos

Los ejemplos de la Sección 4 invocan tools de un catálogo cerrado. La lista no es exhaustiva ni definitiva: solo recoge las funciones mencionadas en los casos desarrollados. El catálogo final se decidirá en el momento de implementación (ver nota TFG-20260428 sobre operaciones LLM).

- `flyTo(region | bbox | feature_id)`: centra el mapa en una región nombrada, un bounding box o una feature concreta.
- `toggleLayer(name, on)`: activa o desactiva una capa del visor.
- `setFilter(field, value)`: aplica un filtro existente del visor (nivel de aviso, fenómeno, sensor, fecha).
- `searchPlace(name)`: geocoder restringido a topónimos de España (provincias, municipios, comarcas).
- `queryAlerts(filters)`: consulta avisos AEMET vigentes o históricos con filtros por fenómeno, severidad, fecha y zona.
- `queryFires(filters)`: consulta focos activos o históricos NASA FIRMS con filtros por fecha, sensor y bbox.
- `queryBurntArea(filters)`: consulta áreas quemadas Burnt Area v4 con filtros temporales.
- `getFeatureDetail(layer, id)`: devuelve la ficha de un elemento concreto.
- `landcoverAtPoint(lon, lat)`: clase CORINE en una coordenada vía GetFeatureInfo IGN.
- `firesNearPopulation(date_range, distance_m)`: focos a menos de una distancia de núcleos de población.
- `burntAreaIntersectPopulation(date_range)`: áreas quemadas que intersectan núcleos.
- `crossAlertsFloodT10(date_range)`: avisos hidrometeorológicos que intersectan zonas inundables T=10.
- `firmsHotspotAnalysis(region | bbox, date_from, date_to, sensor?)`: clusters de focos históricos FIRMS por densidad espacial.
- `summarizeSituation(scope)`: resumen ejecutivo agregado por territorio o ventana temporal.
- `explainTerm(term)`: definición y contexto operativo de un término del glosario (FRP, FWI, T10, etc.).

---

## 4. Ejemplos de preguntas y respuestas modelo

Cada ejemplo se desarrolla siguiendo el formato de la Sección 1.6. Los datos numéricos concretos que aparecerían en los apartados [Resultados] son ilustrativos: en producción, los aporta la tool invocada. Las respuestas no inventan valores; describen qué se obtendría y cómo se interpretaría.

### 4.1 ¿Qué municipios han tenido focos de calor y viento fuerte en las últimas 24 horas?

*Pregunta original del documento de partida. Combina dos condiciones: focos de calor y viento. El visor dispone de focos NASA FIRMS, pero no de mediciones de viento; sí de avisos CAP de AEMET por viento cuando estén vigentes.*

**[Consulta Interpretada]**
El usuario quiere identificar municipios afectados simultáneamente, en las últimas 24 horas, por focos de calor detectados por satélite y por situaciones de viento fuerte. La condición "viento fuerte" se reinterpreta como "aviso AEMET por fenómeno de viento vigente", dado que el visor no dispone de mediciones de viento.

**[Operaciones Geoespaciales]**

- Capas: focos activos NASA FIRMS, avisos AEMET vigentes filtrados por fenómeno = viento, núcleos de población IGN.
- Filtros temporales: ventana móvil de 24 horas hacia atrás desde el instante de la consulta.
- Operaciones espaciales: intersección espacial de focos con polígonos de avisos por viento; agregación por municipio mediante intersección con núcleos de población o con la capa administrativa de referencia.
- Tools invocadas: `queryFires` con `DAY_RANGE=1`; `queryAlerts` con `phenomenon="viento"` y `status="vigente"`; cruce espacial implícito en la tool de agregación municipal.

**[Resultados]**
La respuesta devuelve un listado de municipios con (a) número de focos detectados en la ventana de 24 horas, (b) referencia al aviso de viento que los cubre, (c) FRP máximo y (d) coordenadas representativas. Si ningún municipio cumple las dos condiciones, se devuelve lista vacía con explicación.

**[Interpretación para Emergencias]**
Los municipios con coincidencia simultánea concentran un riesgo operativo más alto: la combinación de actividad ígnea reciente y vientos relevantes incrementa la probabilidad de propagación rápida. Conviene priorizarlos para vigilancia. Se recuerda explícitamente al usuario que la condición de "viento fuerte" se ha resuelto a partir de avisos AEMET, no de mediciones, y que la ausencia de aviso no implica ausencia de viento.

### 4.2 Zonas urbanas cercanas a áreas forestales afectadas por incendios este verano

*Pregunta original. Caso completamente resoluble con los datos disponibles: burnt area v4 cubre mayo-agosto 2025, núcleos de población IGN están cargados y CORINE permite identificar uso forestal.*

**[Consulta Interpretada]**
El usuario quiere localizar núcleos de población próximos a áreas que ardieron durante el verano de 2025 y que estaban clasificadas como forestales. El umbral de proximidad no se especifica; se asume 5 km salvo que el usuario aclare.

**[Operaciones Geoespaciales]**

- Capas: áreas quemadas Burnt Area v4 (mayo-agosto 2025), núcleos de población IGN, CORINE 2018 (clases forestales).
- Filtros temporales: rango de fechas del verano 2025, ajustado al rango de cobertura disponible (2025-05-01 a 2025-08-31).
- Operaciones espaciales: intersección de áreas quemadas con clases forestales de CORINE para retener únicamente superficie forestal afectada; buffer de 5 km sobre esas geometrías; intersección con núcleos de población.
- Tools invocadas: `queryBurntArea` con `date_from=2025-05-01` y `date_to=2025-08-31`; `landcoverAtPoint` o un cruce equivalente sobre el subset CORINE forestal; `burntAreaIntersectPopulation` con buffer paramétrico.

**[Resultados]**
Listado de núcleos con (a) distancia mínima al área quemada forestal más cercana, (b) superficie forestal quemada dentro del buffer, (c) fecha más reciente de quema en el entorno y (d) población cuando esté disponible en el atributo del IGN. Se ofrece exportación a CSV y opción de zoom al núcleo seleccionado.

**[Interpretación para Emergencias]**
La combinación de proximidad y carácter forestal del entorno quemado es un indicador de exposición acumulada del verano: ayuda a priorizar campañas de prevención y revisión de perímetros de protección. No es un indicador de riesgo futuro; es una lectura retrospectiva del verano 2025.

### 4.3 ¿Dónde coincidieron altas temperaturas y núcleos urbanos la semana pasada?

*Pregunta original. El histórico AEMET en el prototipo está acotado a avisos por temperaturas máximas, lo que encaja directamente con esta pregunta.*

**[Consulta Interpretada]**
El usuario quiere identificar núcleos de población que estuvieron cubiertos por avisos AEMET de temperaturas máximas durante la semana anterior a la fecha de consulta.

**[Operaciones Geoespaciales]**

- Capas: histórico de avisos AEMET (filtrado a temperaturas máximas), núcleos de población IGN.
- Filtros temporales: rango de los siete días naturales anteriores a la fecha de la consulta.
- Operaciones espaciales: intersección espacial entre la geometría de las zonas de aviso y los polígonos de núcleos de población; agregación por núcleo y, opcionalmente, por provincia.
- Tools invocadas: `queryAlerts` con `phenomenon="temperatura_maxima"` y rango temporal relativo "última semana"; cruce espacial con núcleos.

**[Resultados]**
Listado de núcleos cubiertos por al menos un aviso de temperaturas máximas en la ventana, con (a) número de días con aviso, (b) severidad máxima del aviso (amarillo / naranja / rojo) y (c) provincia. Se ofrecen vista en mapa y resumen agregado por comunidad autónoma.

**[Interpretación para Emergencias]**
La concentración de núcleos bajo aviso reciente de temperaturas máximas es un indicador de exposición poblacional a estrés térmico. Es información útil para servicios sociales, sanitarios y operativos de protección a poblaciones vulnerables. La fuente es AEMET; la severidad expresa la categoría oficial del aviso, no una medición directa.

### 4.4 ¿Habrá incendios la próxima semana?

*Pregunta original. El asistente no realiza predicciones; este caso ilustra el comportamiento esperado ante consultas fuera de alcance.*

**[Consulta Interpretada]**
El usuario solicita una predicción futura de eventos de incendio. La consulta excede las capacidades del asistente, que opera sobre datos observados, no sobre modelos predictivos.

**[Operaciones Geoespaciales]**
No se ejecuta ninguna operación: la pregunta viola la limitación "no realizas predicciones futuras".

**[Resultados]**
No se devuelven resultados predictivos. Se ofrece, como alternativa razonable, información que sí está disponible y puede ayudar a contextualizar el riesgo: (a) índice meteorológico de peligro de incendio FWI más reciente disponible para la zona consultada, (b) índice de sequía DC más reciente, (c) últimos focos detectados por FIRMS y (d) histórico FIRMS comparable de años anteriores en la misma ventana del calendario.

**[Interpretación para Emergencias]**
La pregunta no puede responderse con los datos del visor. Se invita al usuario a consultar fuentes oficiales de predicción meteorológica (AEMET) y de peligrosidad de incendio (EFFIS) para obtener valoraciones a corto plazo. El asistente puede preparar una vista temática de FWI y sequía sobre la zona indicada para apoyar esa lectura.

---

## 5. Ejemplos adicionales propuestos

Los siguientes ejemplos amplían el catálogo aprovechando capacidades concretas del prototipo (histórico FIRMS, contextualización landcover, comparativa de fuentes, evolución de áreas quemadas, ayuda contextual). Cubren variantes de los Niveles 1 a 4 del catálogo de operaciones LLM definido en la nota TFG-20260428.

### 5.1 Hotspots históricos de incendios en Galicia entre el 1 y el 15 de agosto de 2025

*Caso paralelo al Ejemplo 3 del CARTO MCP Server, trasladado a focos NASA FIRMS sobre la base ya persistida en PostGIS.*

**[Consulta Interpretada]**
El usuario quiere ver dónde se concentraron los focos de incendio en Galicia durante la primera quincena de agosto de 2025, identificando agrupaciones espaciales relevantes.

**[Operaciones Geoespaciales]**

- Capas: histórico FIRMS (`core.firms_history`) sobre el ámbito de Galicia.
- Filtros temporales: 2025-08-01 a 2025-08-15.
- Operaciones espaciales: clusterización por densidad (DBSCAN espacial sobre PostGIS) o estadística Getis-Ord para detectar puntos calientes; cálculo de FRP medio y máximo por cluster.
- Tools invocadas: `searchPlace("Galicia")` para obtener el bbox; `firmsHotspotAnalysis` con bbox y rango de fechas.

**[Resultados]**
Capa nueva en el visor con los clusters detectados, etiqueta de número de focos por cluster, FRP medio y FRP máximo. `flyTo` automático al bbox de Galicia y resumen textual con el conteo total y la provincia con mayor concentración.

**[Interpretación para Emergencias]**
Los hotspots indican zonas de actividad ígnea concentrada en el período. Combinados con el contexto de uso del suelo y proximidad a núcleos, ayudan a entender qué áreas de Galicia merecieron especial atención operativa esa quincena. Es un análisis retrospectivo, no predictivo.

### 5.2 ¿En qué uso del suelo cayó el foco más intenso registrado hoy?

*Aprovecha la contextualización ya integrada de focos FIRMS con CORINE vía GetFeatureInfo IGN.*

**[Consulta Interpretada]**
El usuario quiere localizar el foco activo con mayor FRP del día y conocer la clase de uso del suelo en la coordenada exacta del foco.

**[Operaciones Geoespaciales]**

- Capas: focos activos FIRMS, CORINE 2018 vía consulta puntual del IGN.
- Filtros temporales: día actual.
- Operaciones espaciales: ordenación de focos por FRP descendente; consulta puntual landcover en la coordenada del foco con mayor FRP.
- Tools invocadas: `queryFires` con `DAY_RANGE=1`; `landcoverAtPoint(lon, lat)`; `flyTo` al foco; `getFeatureDetail` para abrir su ficha lateral.

**[Resultados]**
Ficha del foco con sensor, hora UTC, FRP, confianza, coordenadas y clase CORINE devuelta por el IGN. El mapa centra y resalta el foco; opcionalmente activa la capa CORINE para contexto visual.

**[Interpretación para Emergencias]**
La intensidad radiativa (FRP) sirve como proxy de actividad del frente; el uso del suelo aporta contexto sobre el material disponible. Un foco intenso en zona forestal tiene implicaciones operativas distintas a uno en zona agrícola o urbana.

### 5.3 ¿Por qué el visor usa focos FIRMS y no focos EFFIS?

*Caso de explicación trazable de una decisión de alcance del prototipo.*

**[Consulta Interpretada]**
El usuario pide justificar la elección de fuente para los focos activos del visor.

**[Operaciones Geoespaciales]**

- Capas: no se activa una capa EFFIS de focos; se consulta la nota de decisión del proyecto.
- Filtros temporales: no aplica.
- Operaciones espaciales: explicación de alcance basada en la comparativa previa y en los contratos de datos disponibles.
- Tools invocadas: `explainTerm("decisión FIRMS frente a EFFIS")` o consulta documental equivalente.

**[Resultados]**
Resumen textual indicando que EFFIS/Copernicus se evaluó como fuente de focos, pero la integración disponible dependía de teselas rasterizadas y vectorización local por píxeles. El visor mantiene NASA FIRMS porque expone detecciones puntuales con atributos operativos como hora, sensor, confianza y FRP.

**[Interpretación para Emergencias]**
La decisión evita mezclar puntos FIRMS con entidades derivadas visualmente de una imagen. EFFIS se conserva como contexto meteorológico mediante FWI y DC, mientras que FIRMS queda como fuente única de focos activos.

### 5.4 Evolución diaria de superficie quemada en Castilla y León entre el 10 y el 20 de agosto de 2025

*Aprovecha la timeline propia y las estadísticas diarias de Burnt Area v4.*

**[Consulta Interpretada]**
El usuario quiere una serie temporal de superficie quemada por día en Castilla y León durante una ventana concreta del verano de 2025.

**[Operaciones Geoespaciales]**

- Capas: Burnt Area v4 con teselas diarias y estadísticas agregadas.
- Filtros temporales: 2025-08-10 a 2025-08-20.
- Operaciones espaciales: recorte por bbox de Castilla y León; agregación diaria de superficie quemada.
- Tools invocadas: `searchPlace` para el bbox autonómico; `queryBurntArea` con la ventana; consulta a `/api/burnt-area/stats/daily` filtrada por bbox.

**[Resultados]**
Gráfico de barras o línea con superficie quemada diaria, totales acumulados y día pico. Reproductor temporal sobre el mapa para ver la evolución de las teselas día a día.

**[Interpretación para Emergencias]**
La curva diaria refleja la dinámica del episodio: identifica picos, ralentizaciones y la duración efectiva. Es input directo para análisis post-evento y comparación con episodios anteriores.

### 5.5 ¿Hay avisos AEMET de temperaturas máximas activos cerca de Cáceres ahora mismo?

*Combina geocoding, filtro de fenómeno y proximidad. Caso típico de Nivel 2.*

**[Consulta Interpretada]**
El usuario quiere saber si existen avisos AEMET vigentes por temperaturas máximas cuya zona de cobertura esté próxima al término de Cáceres.

**[Operaciones Geoespaciales]**

- Capas: avisos AEMET vigentes filtrados por fenómeno temperatura máxima.
- Filtros temporales: vigencia actual.
- Operaciones espaciales: geocoding del término "Cáceres"; intersección o proximidad (50 km por defecto) con los polígonos de aviso.
- Tools invocadas: `searchPlace("Cáceres")`; `queryAlerts` con `phenomenon="temperatura_maxima"` y `status="vigente"`; `flyTo` al bbox de Cáceres.

**[Resultados]**
Listado de avisos vigentes con identificador, severidad, ámbito geográfico, vigencia y enlace a la ficha completa. Si no hay avisos, se indica explícitamente.

**[Interpretación para Emergencias]**
La presencia de avisos vigentes y su severidad orientan la activación de protocolos sanitarios y de protección a poblaciones vulnerables. La ausencia de avisos no implica ausencia de calor; implica que AEMET no ha emitido aviso para ese ámbito.

### 5.6 Resúmeme la situación de incendios en España hoy

*Caso típico de Nivel 2 / RF-52: resumen ejecutivo agregado.*

**[Consulta Interpretada]**
El usuario solicita un panorama agregado de la situación nacional de incendios en el día actual.

**[Operaciones Geoespaciales]**

- Capas: focos activos FIRMS, avisos AEMET vigentes que puedan estar relacionados con riesgo de incendio (calor, viento, sequía si existieran), FWI y DC como contexto.
- Filtros temporales: día actual.
- Operaciones espaciales: agregación por comunidad autónoma; cálculo de FRP máximo nacional; recuento de focos por sensor.
- Tools invocadas: `summarizeSituation(scope="nacional", topic="incendios")`.

**[Resultados]**
Texto estructurado con (a) número total de focos activos, (b) FRP máximo y localización, (c) comunidades con más actividad, (d) avisos AEMET relacionados activos. Acompañado de un panel resumen visual.

**[Interpretación para Emergencias]**
Snapshot operativo de un vistazo. Útil para briefings y para usuarios no expertos. Incluye trazabilidad: enlaces a las fichas de los focos más relevantes y a las fuentes originales.

### 5.7 Explícame qué es el FRP y cómo se interpreta en este visor

*Caso de ayuda contextual / RF-66 / RF-67. No requiere acceso a datos; usa el glosario.*

**[Consulta Interpretada]**
El usuario pide una definición operativa del término FRP tal y como se utiliza en el visor.

**[Operaciones Geoespaciales]**
Ninguna operación espacial. Se invoca `explainTerm("FRP")` sobre el glosario interno.

**[Resultados]**
Definición: FRP (Fire Radiative Power) es la potencia radiativa emitida por un foco, medida en MW. En el visor se utiliza como proxy de intensidad y se categoriza visualmente en cuatro tramos: < 10 MW, 10-50 MW, 50-200 MW y > 200 MW. Se aclara que no son umbrales oficiales de gravedad de NASA, sino categorías visuales del prototipo.

**[Interpretación para Emergencias]**
Un FRP elevado sugiere mayor actividad radiativa del foco, pero su lectura operativa requiere combinarlo con uso del suelo, viento, sequía y proximidad a núcleos. El asistente recuerda que FRP por sí solo no clasifica un incendio como peligroso.

### 5.8 ¿Qué focos cayeron a menos de 2 km de un núcleo de población durante el verano de 2025?

*Caso típico de Nivel 3 sobre histórico FIRMS y núcleos IGN.*

**[Consulta Interpretada]**
El usuario quiere identificar focos históricos del verano 2025 cuya distancia a un núcleo de población sea inferior a 2 km, para análisis de exposición.

**[Operaciones Geoespaciales]**

- Capas: histórico FIRMS, núcleos de población IGN.
- Filtros temporales: 2025-05-01 a 2025-08-31.
- Operaciones espaciales: cálculo de distancia mínima entre cada foco y los núcleos; filtro por distancia < 2 km.
- Tools invocadas: `firesNearPopulation` con `date_range` del verano y `distance_m=2000`.

**[Resultados]**
Listado y capa de focos cumpliendo el criterio, con núcleo más cercano, distancia exacta, sensor, fecha y FRP. Conteo agregado por provincia.

**[Interpretación para Emergencias]**
Los focos en proximidad inmediata a núcleos son indicadores de exposición directa de población. Conviene cruzar después con tipología del núcleo (cuando exista atributo de habitantes) y con los avisos meteorológicos vigentes en esas fechas para reconstruir el contexto del episodio.

---

## 6. Casos de borde y respuestas esperadas

Esta sección recoge tipologías de consulta donde el comportamiento esperado del asistente es declarar limitaciones o pedir aclaración. Son tan importantes como los casos resueltos: definen la frontera de fiabilidad del sistema.

### 6.1 Capa solicitada no disponible (carreteras, espacios protegidos)

*Ejemplo de pregunta: "¿Qué tramos de autovía cruzan zonas quemadas este verano?".*

Respuesta esperada: el asistente declara que la capa de carreteras no está incorporada al prototipo todavía, ofrece una respuesta parcial centrada en zonas quemadas y sugiere que la consulta podrá resolverse cuando se integre la red viaria del IGN.

### 6.2 Variable no observada (mediciones de viento, humedad, temperatura)

*Ejemplo: "¿Dónde hubo más de 35 °C ayer?".*

Respuesta esperada: se aclara que el visor no consume series de medición; se ofrece, en su lugar, la cobertura de avisos AEMET por temperaturas máximas en la fecha indicada.

### 6.3 Fecha fuera del rango de cobertura del histórico

*Ejemplo: "Focos FIRMS en marzo de 2024".*

Respuesta esperada: se indica que el histórico FIRMS persistido cubre 2025-05-01 a 2025-08-31; se ofrece consultar focos activos recientes o ampliar la ventana del histórico mediante el pipeline de ingesta correspondiente.

### 6.4 Consulta ambigua (zona, fecha o umbral no especificados)

*Ejemplo: "Focos cerca de pueblos".*

Respuesta esperada: el asistente pide aclaración mínima (zona, fecha, distancia) y, opcionalmente, propone una interpretación por defecto (España, últimas 24 horas, 5 km) declarándola explícitamente para que el usuario pueda corregirla.

### 6.5 Consulta predictiva

*Ejemplo: "¿Qué provincias tendrán más incendios en septiembre?".*

Respuesta esperada: rechazo controlado análogo al ejemplo 4.4. Se ofrecen alternativas observacionales y referencias a fuentes oficiales de predicción.

### 6.6 Consulta que requiere combinar capas no disponibles

*Ejemplo: "Focos en espacios naturales protegidos cerca de carreteras principales".*

Respuesta esperada: el asistente identifica las dos capas faltantes (espacios protegidos y red viaria) y propone resolver la subconsulta posible (focos en zona forestal próximos a núcleos) como aproximación provisional.

---

## 7. Notas de trazabilidad y registro

Cada respuesta del asistente debe ir acompañada, en el panel de chat, de un bloque "Acciones realizadas" con la lista de tools invocadas y los parámetros usados. Esta información, junto con la consulta original y el resultado devuelto, se persiste en el log de interacciones del visor para cumplir RF-64 y RF-73.

La estructura mínima del registro por interacción incluye:

- Identificador único de interacción y timestamp.
- Texto literal de la consulta del usuario.
- Intención interpretada por el LLM.
- Lista ordenada de tools invocadas con parámetros.
- Resultados devueltos por cada tool (referencia o snapshot, según volumen).
- Respuesta final entregada al usuario, en los cuatro bloques del formato.
- Modelo LLM y versión utilizados.

La revisión del log permite auditar el comportamiento del asistente, detectar tools que se invocan mal o que faltan, y mejorar el prompt o el catálogo en iteraciones sucesivas.
