---
id: TFG-20260428-ideas-operaciones-llm-local-en-visor-meteovisor
título: "Ideas de operaciones para un LLM local integrado en el visor MeteoVisor"
tipo: idea
tags:
  - tfg
  - llm
  - tool-calling
  - mcp
  - visor-gis
  - arquitectura
  - alcance
contexto: "Propuesta inicial para concretar el componente LLM del visor MeteoVisor descrito en los requisitos funcionales RF-46 a RF-73. La nota fija qué operaciones puede asumir un modelo local pequeño (Qwen2.5, Llama 3.2, Gemma 2/3), bajo qué arquitectura (incluida la opción de exponer las operaciones como servidor MCP siguiendo el patrón del CARTO MCP Server), sin invadir cálculos espaciales que deben seguir en PostGIS."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia a partir de la documentación del proyecto (README.md, doc/requisitos_funcionales_visor_emergencias_meteo.md, doc/notas_objetivo_tfg.md), conversación de trabajo del 2026-04-28 y referencia complementaria al artículo de CARTO sobre su MCP Server consultado el 2026-04-30."
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-04-30"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: medio
pendientes_de_verificar:
  - "Confirmar que se considera elaboración propia del autor del TFG."
  - "Confirmar el modelo local concreto a usar y el hardware disponible para servirlo."
  - "Validar con el profesor el alcance: si el TFG defenderá Fase 1 (preparación técnica del LLM) o Fase 2 (asistente operativo básico)."
  - "Mantener actualizada la lista de tools ya materializadas frente al catálogo teórico inicial."
  - "Decidir si las tools del visor se exponen como endpoint propietario, como servidor MCP local, o ambos."
---

# Ideas de operaciones para un LLM local integrado en el visor MeteoVisor

## Contenido

El documento de requisitos funcionales reserva los apartados RF-46 a RF-73 para una interfaz conversacional basada en LLM. Esta nota concreta qué operaciones tiene sentido delegar a un modelo local pequeño dentro del prototipo actual, qué operaciones no, y qué arquitectura mínima sería razonable para el TFG.

### Tesis principal

El LLM no se concibe como cerebro analítico ni como sistema de decisión. Su papel es doble:

1. **Traductor** de lenguaje natural a llamadas estructuradas sobre un catálogo cerrado de operaciones del visor (*tool calling*).
2. **Narrador** de los resultados que devuelven esas operaciones, en lenguaje no técnico y con trazabilidad explícita.

Esto encaja directamente con RF-48 (traducción a acciones del visor), RF-63 (limitación a capacidades autorizadas), RF-65 (validación de resultados críticos) y RF-69 (respuestas basadas en datos de la plataforma).

### Mover el mapa: caso trivial y viable

Mover el mapa es la operación más fácil del catálogo y, a la vez, una de las más útiles para reducir la barrera de uso (RF-47). El LLM no manipula coordenadas: emite un JSON con la intención (por ejemplo `flyTo({region: "Galicia"})` o `flyTo({feature_id: "fire_123"})`) y el frontend traduce esa intención a la llamada Leaflet correspondiente, que el prototipo ya tiene resuelta (`map.setView`, `map.flyTo`, `map.fitBounds`).

Modelos locales como Qwen2.5-7B-Instruct, Llama-3.2-3B-Instruct o Gemma 2/3 9B sirven de sobra para esto si se ejecutan vía Ollama o llama.cpp con interfaz compatible OpenAI y tool calling activado.

### Catálogo escalonado de operaciones por dificultad

#### Nivel 1 — Control puro de la interfaz

Cobertura aproximada de RF-47 y RF-48. Sin alucinación posible si se valida el JSON contra el esquema de tools.

- Navegación cartográfica: centrar el mapa en una región, en una feature concreta o en el bbox de los resultados de una consulta.
- Activación, desactivación y orden de capas (RF-02), incluida transparencia.
- Filtros existentes en el visor: nivel y tipo de aviso AEMET, ventana temporal del timeline, fuente FIRMS, fechas del histórico.
- Cambio de mapa base y reset de vista.

#### Nivel 2 — Consulta sobre datos cargados

Cobertura aproximada de RF-50, RF-51, RF-52, RF-57. El LLM lee el resultado de un endpoint y lo convierte en respuesta híbrida texto + mapa.

- Resúmenes de situación a partir de `/api/stats`.
- Listados ordenados de focos por FRP, con `flyTo` al foco principal y apertura de su ficha lateral.
- Conteos por territorio sobre los datos ya servidos por la API.
- Explicación de capas, conceptos y términos del glosario (RF-66, RF-67), apoyada en metadatos ya definidos en el catálogo.

#### Nivel 3 — Cruces espaciales explicables

Cobertura aproximada de RF-17, RF-25, RF-32, RF-60. El LLM no calcula geometría: encadena llamadas a tools que ejecutan operaciones PostGIS.

- Avisos hidrometeorológicos que intersectan zona inundable T10 cerca de núcleos, pendiente de ingestar geometría vectorial local de la capa T10.
- Focos en zona forestal a menos de un umbral configurable de un núcleo de población.
- Focos activos a menos de un umbral configurable de núcleos por debajo de un máximo de habitantes, materializado como `activeFiresNearPopulation`.
- Exploración del histórico FIRMS por fecha y comparativa de períodos sobre `/api/firms/history/...`.
- Contextualización de focos con uso del suelo, apoyándose en la consulta puntual ya existente vía GetFeatureInfo del IGN.

#### Nivel 4 — Generación de informes y exportes

Cobertura aproximada de RF-43, RF-45, RF-58.

- Resúmenes ejecutivos por provincia, comunidad autónoma o período temporal.
- Listados CSV exportables a partir de la conversación.
- Generación de fichas de evaluación de riesgo conforme a RF-20 y RF-29 a partir de los datos cruzados.

### Lo que conviene NO delegar al LLM

- Cálculos geométricos, conteos numéricos y priorización: deben vivir en SQL/PostGIS. El LLM solo orquesta y narra. Esto es lo que exige RF-65 (validación de resultados críticos) y RF-69 (respuestas basadas en datos reales).
- Decisiones operativas o ejecutivas sobre emergencias: lo prohíbe RF-71.
- Generación libre de coordenadas, identificadores de capa o fechas no presentes en el catálogo: lo prohíbe RF-63.
- Inferencia "creativa" sobre datos no cargados: violaría RF-69 y RF-70 (indicación de incertidumbre).

### Arquitectura mínima recomendada

1. **Catálogo de tools** declarado como JSON Schema, con funciones del estilo `flyTo`, `toggleLayer`, `setVisibleLayers`, `setFilter`, `showGeoJsonResults`, `setLayerDate`, `queryFires`, `queryAlerts`, `activeFiresNearPopulation`, `summarizeSituation`, `getFeatureDetail`, `searchPlace`. El catálogo es la frontera dura de lo que el LLM puede pedir. Las operaciones previstas pero no ejecutables con datos locales, como `crossAlertsFloodT10`, se documentan como rechazo controlado hasta que exista geometría vectorial local.
2. **Servidor LLM local** con tool calling, expuesto al backend FastAPI. Camino corto razonable: Ollama + Qwen2.5-7B-Instruct con interfaz OpenAI-compatible.
3. **Endpoint nuevo** `POST /api/assistant/chat` que recibe la consulta, llama al LLM, valida cada tool call contra el catálogo y la ejecuta sobre el visor o la base de datos.
4. **Validador** que rechaza tools desconocidas, parámetros fuera de rango o referencias a capas no autorizadas. Cubre RF-63 prácticamente gratis.
5. **Logging persistente** por interacción con `{prompt, intent, tool_calls, payload, response, timestamp}`. Cubre RF-64 y RF-73.
6. **Panel de chat** en el frontend con un bloque "Acciones realizadas" en cada respuesta, mostrando las tools invocadas y los datos consultados. Cubre RF-50 y RF-56.

Con esta arquitectura, una consulta como "muéveme el mapa a Cáceres y enséñame focos de hoy con FWI" se descompone en algo del estilo `[searchPlace("Cáceres"), flyTo(bbox), toggleLayer("fwi", true), queryFires({date: "today"})]`, sin que el LLM toque coordenadas crudas ni datos de la base. Una consulta como "hay núcleos de menos de 5.000 habitantes a menos de 2 km de focos activos" se resuelve mediante `activeFiresNearPopulation`, y el resultado espacial se envía al mapa mediante `showGeoJsonResults` sin que el LLM tenga que transportar el GeoJSON completo.

### Variante: exponer las tools como servidor MCP

El Model Context Protocol (MCP) es un estándar abierto promovido por Anthropic para que cualquier agente de IA descubra y ejecute herramientas externas de forma uniforme. CARTO ha publicado un *CARTO MCP Server* que expone su catálogo de operaciones geoespaciales (más de 200 componentes de CARTO Workflows, incluidos buffers, joins, geocoding, routing, hotspot analysis y modelos predictivos) como tools MCP consumibles desde Claude, ChatGPT, Gemini o Cursor, manteniendo los datos en el data warehouse del cliente sin replicación.

Aplicado a MeteoVisor, este patrón permitiría montar un **servidor MCP local en Python** (con el SDK oficial `mcp`) que exponga el mismo catálogo de tools descrito más arriba, con dos consecuencias:

- El frontend del visor sigue conectándose a un cliente MCP interno alimentado por un LLM local (Qwen2.5-7B-Instruct vía Ollama), sin cambiar la experiencia de usuario.
- El mismo servidor MCP queda disponible para cualquier cliente compatible (Claude Desktop, Cursor) que pueda conectarse en local. Esto da una demostración secundaria muy potente de cara al tribunal: probar el sistema desde un cliente externo estándar, no solo desde el panel propio.

Comparativa rápida frente al endpoint propietario `/api/assistant/chat`:

- Endpoint propio: menor esfuerzo, acoplado al visor, ad hoc.
- Servidor MCP: mayor esfuerzo inicial, protocolo abierto, las tools son reutilizables por terceros y la defensa académica sube de nivel ("operaciones GIS sobre datos reales expuestas como servicio interoperable estándar").

No es una decisión excluyente. Una opción razonable es implementar el catálogo como **servidor MCP local** y consumirlo desde un endpoint de conveniencia `/api/assistant/chat` que actúa como cliente MCP servido por FastAPI hacia el frontend del visor.

### Caso de uso paralelo al Ejemplo 3 de CARTO

El Ejemplo 3 del artículo de CARTO describe un análisis de hotspots de colisiones de tráfico filtrable por rango de fechas, expuesto como tool y resuelto por un workflow de estadística espacial. La traslación natural a MeteoVisor es un **hotspot analysis del histórico FIRMS** sobre la base ya persistida en `core.firms_history`:

- Consulta tipo: "muéstrame los puntos calientes de incendios en Galicia entre el 1 y el 15 de agosto de 2025".
- Tool propuesta: `firms_hotspot_analysis(region|bbox, date_from, date_to, sensor?)`.
- Implementación: consulta PostGIS con `ST_ClusterDBSCAN` o equivalente sobre `core.firms_history` filtrado por fecha y territorio. El resultado es una capa GeoJSON o MVT con los clusters detectados.
- Respuesta: el frontend hace `flyTo` al bbox, dibuja la capa de clusters y el LLM devuelve un resumen del estilo "se detectan N hotspots, el más intenso en provincia X con FRP medio Y".

Este caso cubre simultáneamente RF-25 (cruce con peligro de propagación), RF-28 (priorización visual), RF-50 (explicación comprensible), RF-60 (consultas evolutivas históricas) y es el primer Nivel 3 del catálogo que merece la pena prototipar.

### Diferencias importantes con el modelo de CARTO

- CARTO se apoya en data warehouses cloud (BigQuery, Snowflake, Redshift, Databricks); MeteoVisor trabaja sobre PostgreSQL/PostGIS local. Es ventaja para el TFG: demo offline, sin claves cloud, sin coste por consulta.
- CARTO ofrece más de 200 componentes; el alcance defendible para el TFG es exponer entre 5 y 10 tools específicas de avisos meteorológicos e incendios.
- CARTO devuelve mapas embebidos en CARTO Builder; MeteoVisor devuelve cambios sobre el mismo Leaflet del visor, lo que evita dependencia de un visor externo.

### Referencias externas consultadas

- CARTO. "CARTO MCP Server: Turn your AI agents into geospatial experts". Consultado el 2026-04-30. URL aportada por el usuario en la conversación de origen. Licencia y condiciones de reutilización pendientes de verificar antes de citarlo en la memoria del TFG.

### Encaje con las fases del documento de requisitos

- Fase 1 (MVP): preparar la arquitectura de tools y el catálogo funcional, sin asistente visible.
- Fase 2: asistente conversacional básico con cobertura de Nivel 1 y Nivel 2.
- Fase 3: asistente analítico con cobertura de Nivel 3 y Nivel 4.

Para el TFG, un alcance defendible parece ser Fase 1 cerrada y Nivel 1 + Nivel 2 demostrables sobre el prototipo actual.

## Datos explícitos

- El proyecto MeteoVisor ya integra avisos AEMET, focos NASA FIRMS, FWI/DC de EFFIS, CORINE, núcleos de población, burnt area Copernicus e histórico FIRMS persistido en PostGIS.
- El frontend ya expone primitivas Leaflet para mover el mapa, activar capas WMS, alternar núcleos, aplicar filtros y abrir fichas.
- El patrón `map_geojson` → `showGeoJsonResults` permite que una tool server-side devuelva resultados cartográficos temporales sin crear capas persistentes nuevas.
- Los requisitos RF-46 a RF-73 dedican una sección entera a la interfaz conversacional con LLM.
- La nota de objetivos del TFG limita el papel del LLM a interfaz de consulta con trazabilidad, no a sistema de decisión.
- CARTO ha publicado un servidor MCP que expone más de 200 componentes geoespaciales como tools consumibles por agentes compatibles con MCP (Claude, ChatGPT, Gemini, Cursor), manteniendo los datos en el data warehouse del cliente.
- El Ejemplo 3 del artículo de CARTO describe un análisis de hotspots de colisiones de tráfico filtrable por rango de fechas, resuelto por un workflow de estadística espacial encapsulado como tool.

## Datos inferidos

- Modelos locales pequeños (3B-9B) con tool calling cubren sin problema los Niveles 1 y 2 propuestos.
- El cuello de botella del componente LLM no será el modelo, sino la calidad del catálogo de tools y la trazabilidad del logging.
- El endpoint `/api/assistant/chat` cabe en la arquitectura FastAPI actual sin rediseño.
- "Gemma 4" y "Qwen 3.6" mencionados en la conversación de origen no existen como tales; las familias vivas son Gemma 2/3 y Qwen2.5/Qwen3.
- El SDK oficial de MCP en Python permite montar un servidor MCP local que exponga las tools del visor sin acoplarlas a una plataforma cloud concreta.
- Una arquitectura híbrida (servidor MCP local + endpoint FastAPI cliente del MCP) probablemente sea más defendible académicamente que un endpoint propietario aislado.

## Datos faltantes o ambiguos

- Hardware disponible para servir el modelo en local y restricciones de latencia aceptables.
- Modelo concreto que se va a usar en el prototipo final.
- Catálogo definitivo de tools y nombres exactos de cada operación. Nombres ya materializados relevantes para esta nota: `activeFiresNearPopulation`, `setVisibleLayers`, `showGeoJsonResults`, `setLayerDate`.
- Si el TFG defenderá Fase 1 cerrada o Fase 2 demostrable.
- Cómo se va a validar la calidad del asistente de cara al tribunal: episodios reales, casos de uso predefinidos o evaluación cualitativa.
- Si las tools se expondrán como endpoint propietario, como servidor MCP local o como ambos.
- Licencia y condiciones de reutilización del artículo de CARTO antes de citarlo formalmente en la memoria.
