---
id: TFG-20260513-auto-acciones-de-visor-segun-tools-llm
título: "Auto-acciones del visor derivadas de las tools de datos del chat LLM"
tipo: decisión
tags:
  - tfg
  - llm
  - chat
  - tool-calling
  - estado-ui
  - trazabilidad
  - geojson
contexto: "Decisión de diseño del orquestador del chat LLM en MeteoVisor: tras una consulta, el visor debe reflejar SOLO las capas usadas por la respuesta (apagando las activas por defecto que no se consultaron), sincronizar el slider del timeline histórico con la fecha citada en el texto y pintar resultados GeoJSON temporales cuando una tool de datos los produzca."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada de iteraciones sobre el módulo de chat LLM en MeteoVisor"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-18"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar que la memoria del TFG cita los nombres exactos de los símbolos (`SERVER_TOOL_TO_LAYERS`, `_auto_layer_date_from_result`, `_build_auto_client_actions`, `_auto_client_actions_from_result`, `_compact_result_for_model`)."
---

# Auto-acciones del visor derivadas de las tools de datos del chat LLM

## Decisión
El orquestador del chat (`chat/orchestrator.py`) emite **acciones de visor deterministas** en función de las tools de datos (server-side) que el LLM haya invocado con éxito. El objetivo es que el estado visible del visor refleje exactamente lo consultado, sin depender de que el LLM "se acuerde" de pedir `toggleLayer`, `setLayerDate` o `showGeoJsonResults` en cada respuesta.

### Reglas

1. **`setVisibleLayers` automático**. Cada server tool tiene un mapeo cerrado a un conjunto de capas (`SERVER_TOOL_TO_LAYERS`):
   - `queryAlerts` → `alerts`
   - `queryFires` → `fires`
   - `queryBurntArea` → `burnt_area`
   - `firesNearPopulation` → `firms_history`, `nucleos`
   - `activeFiresNearPopulation` → `fires`, `nucleos`
   - `firmsHotspotAnalysis` → `firms_history`
   - `landcoverAtPoint` → `corine_wms`
   - `summarizeSituation` → `alerts`, `fires`
   - `searchPlace`, `explainTerm` → (vacío)

   Al final del turno, si el LLM **no** emitió por su cuenta una acción que modifica visibilidad (`toggleLayer` o `setVisibleLayers`), el orquestador encola un único `setVisibleLayers` con la unión de capas asociadas a las tools usadas. Esto apaga el resto del catálogo, incluidas las capas activas por defecto (`alerts`, `fires`) si la consulta no las tocó.

2. **`setLayerDate` automático**. Para tools históricas con timeline (`queryBurntArea`, `firesNearPopulation`, `firmsHotspotAnalysis`) el orquestador deriva una fecha objetivo según dos reglas:
   - Si `filters.date_from == filters.date_to`, el usuario pidió un día concreto → se sincroniza el slider a esa fecha (aunque el resultado venga vacío).
   - En `queryBurntArea` con rango amplio, si el resultado expone `peak_day` con `burned_area_ha > 0`, se sincroniza al día pico para que el slider muestre justamente el día citado por el texto.

3. **`showGeoJsonResults` automático para resultados calculados**. Si una server tool devuelve un `map_geojson` de tipo `FeatureCollection`, el orquestador no obliga al LLM a copiar ese GeoJSON en una tool client-side. En su lugar:
   - valida el payload contra el schema de `showGeoJsonResults`;
   - encola una `ClientAction` con el GeoJSON completo para el frontend;
   - compacta la observación que vuelve al LLM sustituyendo `map_geojson` por `map_geojson_summary`;
   - añade `client_actions_queued` para que el modelo sepa que el resultado ya está enviado al mapa.

   El primer caso aplicado es `activeFiresNearPopulation`, que devuelve puntos de foco, puntos de núcleo y líneas de distancia para mostrar los pares foco-núcleo encontrados.

4. **Respeto a la intención explícita del LLM**. Si el LLM ya emitió `toggleLayer` o `setVisibleLayers` durante el turno, el `setVisibleLayers` automático se omite. El LLM mantiene la capacidad de pedir capas adicionales cuando el usuario lo solicita explícitamente ("mantén también la capa X").

### Por qué
Sin estas auto-acciones, el LLM podía responder con texto correcto pero el visor seguía mostrando las capas activas por defecto y el slider en el día inicial del histórico, contradiciendo lo que el chat acababa de afirmar. Hacer la sincronización en el backend, no en el prompt, garantiza dos propiedades:

- **Determinismo**: la regla se cumple aunque el modelo varíe su salida o "olvide" emitir la acción de visor.
- **Económico en tokens**: no hace falta forzar al LLM a emitir `toggleLayer`/`setLayerDate` adicionales que el orquestador puede inferir del trace de tools.
- **Robusto con geometrías**: el LLM recibe resúmenes compactos; el frontend recibe los GeoJSON completos. Esto evita que respuestas espaciales con muchos resultados rompan la segunda llamada al LLM por exceso de payload.

### Cómo
- Helpers `_auto_layer_date_from_result(tool_name, result)`, `_build_auto_client_actions(...)`, `_auto_client_actions_from_result(...)` y `_compact_result_for_model(...)` en `chat/orchestrator.py`.
- Cada turno acumula `server_tools_used: list[str]`, `pending_layer_dates: list[tuple[str, str]]` y un flag `layer_actions_from_llm`.
- En `run_chat` y `run_chat_stream`, las `ClientAction` extra se devuelven junto a la respuesta o se emiten como eventos `client_action`. Las acciones derivadas de `map_geojson` se pueden encolar justo después de ejecutar la server tool; las acciones de visibilidad y fecha se calculan al cierre del turno.
- El catálogo de client tools incorpora `setLayerDate({layer, date})` con `enum` cerrado de capas con timeline (`burnt_area`, `firms_history`, `aemet_max_temp_history`) y patrón `YYYY-MM-DD`.
- El catálogo incorpora `showGeoJsonResults({title?, geojson, fit?, clear_existing?})` para pintar una capa temporal de resultados sin persistir una nueva capa en la base de datos.

### Trade-offs aceptados
- Pierde algo de "libertad estilística" del LLM: aunque el modelo no emita visor-actions, el visor cambiará. Se acepta porque la regla operativa del TFG es que el visor refleje siempre lo consultado.
- Si el LLM combina varias tools de datos (p. ej. `queryAlerts` + `queryFires`), el `setVisibleLayers` automático las activa todas. Si el usuario quería ver solo una, debe pedirlo explícitamente.

## Datos explícitos
- El orquestador `chat/orchestrator.py` calcula y emite las acciones determinísticas.
- El mapeo `SERVER_TOOL_TO_LAYERS` es cerrado y vive en código, no en prompt.
- El nuevo client tool `setLayerDate` permite mover el slider del timeline a una fecha concreta.
- El nuevo client tool `showGeoJsonResults` permite dibujar resultados GeoJSON temporales calculados por server tools.
- El resultado pesado `map_geojson` se omite de la observación del LLM y se sustituye por `map_geojson_summary`.

## Datos inferidos
- La nota se clasifica en `08-llm-y-consulta-en-lenguaje-natural/` por ser una decisión del módulo chat LLM.
- Tipo `decisión` (registro de elección de arquitectura, no idea ni recurso).

## Datos faltantes o ambiguos
- Confirmación de autoría como elaboración propia.
- Decidir si la memoria del TFG cita los identificadores de símbolos en código o solo el principio rector.
- Decidir si `showGeoJsonResults` se documenta como capa temporal de análisis o como acción efímera de interfaz.
