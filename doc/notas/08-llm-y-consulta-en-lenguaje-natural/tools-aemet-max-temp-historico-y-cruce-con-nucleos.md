---
id: TFG-20260513-tools-aemet-max-temp-historico-y-cruce-con-nucleos
título: "Tools del chat para histórico AEMET de temperaturas máximas y cruce con núcleos IGN"
tipo: decisión
tags:
  - tfg
  - llm
  - chat
  - aemet
  - tool-calling
  - postgis
  - exposicion-poblacional
contexto: "Extensión del catálogo de tools server-side del chat LLM de MeteoVisor para responder consultas combinadas sobre el histórico de avisos AEMET de temperaturas máximas y su impacto poblacional, reutilizando datos ya disponibles en BD para la capa aemet_max_temp_history."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada de iteraciones sobre el módulo de chat LLM en MeteoVisor"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-13"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar que la memoria del TFG cita los identificadores exactos (`queryAemetMaxTempHistory`, `aemetWarningsNearPopulation`, `pub.aemet_max_temperature_daily_stat`, `pub.aemet_max_temperature_daily_feature`)."
---

# Tools del chat para histórico AEMET de temperaturas máximas y cruce con núcleos IGN

## Decisión
Se añaden al catálogo server-side del chat LLM dos tools nuevas que exponen, como funciones invocables por el modelo, datos que el visor ya tenía servidos para la capa `aemet_max_temp_history` pero que el chat no podía consultar:

- **`queryAemetMaxTempHistory({date_from?, date_to?, limit?})`**: histórico diario de avisos AEMET filtrados al fenómeno `AT;Temperaturas máximas`. Lee `pub.aemet_max_temperature_daily_stat`. Devuelve:
  - serie por día con `warning_count`, `max_temperature_c` y desglose `red/orange/yellow/green_count`;
  - `peak_day` calculado por la **máxima temperatura nominal** del rango (no por número de avisos);
  - totales agregados (`total_warning_count`, `totals_by_level`).
- **`aemetWarningsNearPopulation({date, level?, min_temperature_c?, warnings_only=true, distance_m=50000, limit=50})`**: para una fecha concreta, cruza `pub.aemet_max_temperature_daily_feature` (polígonos de zonas AEMET en aviso por temperaturas máximas) con `core.nucleos_poblacion_polygon` (IGN) usando `ST_DWithin` y `ST_Distance` sobre `geography`. Devuelve, por cada zona, el **núcleo más cercano** (`LATERAL ... LIMIT 1`), ordenado por temperatura nominal descendente, junto a `peak_temperature_c` del listado.

### Por qué
Hasta ahora, una consulta como "qué día del histórico se registró el aviso AEMET con temperatura más alta y qué núcleo de población es el más cercano" llegaba a un callejón sin salida: la capa `aemet_max_temp_history` mostraba conteos por día y polígonos en el mapa, pero el chat no tenía cómo:

1. localizar el día con mayor temperatura nominal del histórico;
2. obtener la geometría de la zona AEMET correspondiente;
3. cruzarla con la capa de núcleos para responder la parte espacial.

La solución NO es ampliar el prompt para que el modelo "infiera" estos datos, sino exponer las funciones de acceso ya existentes en `main.py` (`query_aemet_max_temperature_stats_rows`, `query_aemet_max_temperature_feature_rows`) como **tools deterministas**. El razonamiento del LLM queda como orquestación entre tools verificables, no como suposición sobre datos.

### Cómo
- **Tools**: `chat/tools/server/query_aemet_max_temp_history.py` y `chat/tools/server/aemet_warnings_near_population.py`, registradas en `chat/tools/server/__init__.py`.
- **SQL para el cruce zona ↔ núcleo**: misma estructura que `firesNearPopulation` para mantener simetría:
  - `ST_DWithin(f.geom::geography, n.geom::geography, %s)` para el filtro de distancia,
  - operador `<->` para el orden y `LIMIT 1` dentro de un `LATERAL` para devolver un núcleo por zona,
  - `ORDER BY f.temperature_max_c DESC NULLS LAST, f.level_rank DESC, f.area_name`.
- **Auto-acciones de visor en el orquestador** (`chat/orchestrator.py`):
  - `SERVER_TOOL_TO_LAYERS`: `queryAemetMaxTempHistory → ('aemet_max_temp_history',)` y `aemetWarningsNearPopulation → ('aemet_max_temp_history', 'nucleos')`.
  - `_HISTORICAL_DATE_LAYER`: ambas mapean a `aemet_max_temp_history`. Si el LLM consulta con `date_from == date_to` (o `date` único en la segunda tool), el slider del timeline se sitúa en ese día.
  - `_auto_layer_date_from_result` extiende su lógica de `peak_day` a `queryAemetMaxTempHistory` cuando hay rango amplio: usa `peak_day.nominal_date` como destino del slider.
- **Prompt**: ambas tools entran en el inventario (A) con descripción operativa y se añade un ejemplo de encadenamiento para la consulta exacta del usuario (`queryAemetMaxTempHistory → peak_day → aemetWarningsNearPopulation(date=peak_day.nominal_date)`).

### Encaje con el resto del sistema
- **Coherencia con notas previas**: respeta la decisión registrada en `auto-acciones-de-visor-segun-tools-llm.md` (el orquestador encola `setVisibleLayers` + `setLayerDate` automáticamente al cierre del turno). Las dos nuevas tools no requieren tocar nada en el prompt sobre visibilidad.
- **Coherencia con `filtros-visor-desde-chat-por-simulacion-de-clicks.md`**: el chat sigue sin tocar estado interno del visor; cualquier sincronización pasa por las client tools (`setVisibleLayers`, `setLayerDate`) que ya disparan `change` sobre el DOM.

### Trade-offs aceptados
- Se asume que el `peak_day` operativamente útil para el visor es **el del aviso más caliente**, no el del mayor número de avisos. Para la otra lectura el LLM dispone de los conteos por nivel en la serie y puede destacarla en el texto, aunque el slider apunte al día más caliente.
- `distance_m=50000` por defecto en la segunda tool es generoso: las zonas AEMET son administrativas y suelen contener núcleos dentro (distancia 0). Se acepta porque el peor caso es devolver el núcleo más cercano "fuera" de la zona cuando ningún núcleo está dentro, hipótesis muy poco frecuente en zonas pobladas.

## Datos explícitos
- `pub.aemet_max_temperature_daily_stat` ya alimenta la capa del visor con `warning_count` y `max_temperature_c` por día.
- `pub.aemet_max_temperature_daily_feature` contiene la geometría WGS84 de cada zona AEMET en aviso, con `temperature_max_c`, `level_label` y `area_name`.
- `core.nucleos_poblacion_polygon` (IGN) tiene `geom`, `nombre`, `habitantes` y se usa ya en `firesNearPopulation`/`activeFiresNearPopulation`.

## Datos inferidos
- La nota se clasifica en `08-llm-y-consulta-en-lenguaje-natural/` por ser una decisión del módulo chat LLM (extensión del catálogo de tools).
- Tipo `decisión`.

## Datos faltantes o ambiguos
- Confirmación de autoría como elaboración propia.
- Decidir si la memoria del TFG cita los identificadores de tabla y de tool exactos, o solo el principio rector.
