---
id: TFG-20260513-primitivo-show-historical-layer-at-date
título: "Primitivo showHistoricalLayerAtDate en app.js para activar capa histórica y posicionar el slider de forma atómica"
tipo: decisión
tags:
  - tfg
  - llm
  - chat
  - frontend
  - estado-ui
  - leaflet
  - timeline
contexto: "Decisión de diseño del frontend del visor MeteoVisor para integrar la sincronización de timeline pedida por el chat LLM. Resuelve la carrera entre el frame por defecto que aplica el toggle de capa histórica y el frame objetivo que el chat quiere imponer tras una consulta."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada del cierre del módulo de chat LLM en MeteoVisor"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-13"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar que la memoria del TFG cita los nombres exactos de los símbolos (`showHistoricalLayerAtDate`, `toggleBurntAreaLayer`, `toggleHistoricalFiresLayer`, `toggleAemetMaxTempLayer`, `setHistoricalTimelineFrame`, `historicalTimelineIndex`)."
---

# Primitivo `showHistoricalLayerAtDate` en `app.js` para activar capa histórica y posicionar el slider de forma atómica

## Decisión
Las acciones del chat que piden mostrar una capa histórica (`burnt_area`, `firms_history`, `aemet_max_temp_history`) **en un día concreto** no se resuelven combinando `setVisibleLayers` + `setLayerDate` desde el cliente del chat, sino llamando a un único primitivo en `app.js`:

```js
async function showHistoricalLayerAtDate(layer, dateString) { ... }
```

El handler `chatToolSetLayerDate` (en `chat.js`) se reduce a delegar en esa función. El cliente del chat no contiene polling, ni esperas activas, ni lógica de orden entre acciones.

### Por qué
Sin el primitivo, el flujo era:

1. El orquestador encola `setVisibleLayers([layer])` y `setLayerDate(layer, date)`.
2. `setVisibleLayers` disparaba `change` sobre el checkbox de la capa, lo que ejecutaba `toggleBurntAreaLayer(true)` (o equivalente) como **fire-and-forget**.
3. Ese toggle cargaba el timeline y, al detectar que **no había otras capas históricas visibles**, **reposicionaba `historicalTimelineIndex` al frame por defecto** del histórico (el primer día publicado) y aplicaba `setHistoricalTimelineFrame`.
4. En paralelo, `setLayerDate` intentaba situar el slider en el día objetivo mediante un poll-y-then-set.

La carrera entre 3 y 4 dependía del orden de microtasks, del tiempo de fetch del timeline y del polling. En la práctica, el frame por defecto solía ganar a veces, y el usuario veía la capa activada pero el slider en el día inicial, contradiciendo el texto del chat ("el día con la mayor superficie quemada es 2025-08-16" mientras el visor mostraba 2025-05-01).

La causa raíz no es del chat: es que **el visor no tenía un punto de entrada externo** capaz de decir "activa esta capa y al final déjala en este día" como una sola operación. El chat estaba intentando emular esa atomicidad desde fuera.

### Cómo
El primitivo vive en `app.js`, junto al resto de la lógica de timeline (`setHistoricalTimelineFrame`, `rebuildHistoricalTimeline`, los `toggleXLayer`), y tiene tres responsabilidades:

1. **Marcar el checkbox** de la capa (sin disparar `change`, para evitar duplicar el toggle).
2. **Llamar directamente al toggle subyacente y `await`ear** su promesa. Esto garantiza que cuando el primitivo continúe, el toggle ya habrá ejecutado su `setHistoricalTimelineFrame` con el frame por defecto, en lugar de hacerlo después y pisar al primitivo.
3. **Posicionar el slider en la fecha objetivo**: reconstruye el timeline unificado si la fecha aún no estaba indexada y llama a `setHistoricalTimelineFrame(idx, true)`. Este es el **último escritor** sobre `historicalTimelineIndex`, así que su valor prevalece.

Mapeo capa → handler:

```js
const HISTORICAL_LAYER_DESCRIPTORS = {
  burnt_area: { checkboxId: 'chk-burnt_area_daily',          toggleFn: () => toggleBurntAreaLayer,         timeline: () => burntAreaTimeline },
  firms_history: { checkboxId: 'chk-firms_history',          toggleFn: () => toggleHistoricalFiresLayer,  timeline: () => historicalFiresTimeline },
  aemet_max_temp_history: { checkboxId: 'chk-aemet_max_temp_history', toggleFn: () => toggleAemetMaxTempLayer, timeline: () => aemetMaxTempTimeline },
};
```

Y en `chat.js`:

```js
async function chatToolSetLayerDate(args) {
  if (typeof showHistoricalLayerAtDate !== 'function') return false;
  return showHistoricalLayerAtDate(args.layer, args.date);
}
```

### Encaje con notas previas
- Coherente con `filtros-visor-desde-chat-por-simulacion-de-clicks.md`: el chat sigue pasando por la capa de presentación del visor (`toggleXLayer`, `setHistoricalTimelineFrame`), no manipula `historicalTimelineIndex` ni los timelines internos directamente. El primitivo es una **API estable** del visor, no un atajo a su estado.
- Coherente con `auto-acciones-de-visor-segun-tools-llm.md`: el orquestador sigue encolando `setVisibleLayers` + `setLayerDate` automáticamente. La diferencia es que el handler de `setLayerDate` deja de ser frágil porque delega en una operación atómica.

### Trade-offs aceptados
- `setVisibleLayers` sigue siendo síncrono y se ejecuta antes que `setLayerDate`. Eso activa la capa **dos veces** (una por `setVisibleLayers` via `change`, otra por `showHistoricalLayerAtDate` via llamada directa). El segundo `await toggleXLayer(true)` ve `hadVisibleHistoricalLayers === true` (porque la primera invocación ya marcó `burntAreaVisible = true`), así que **no** reaplica el frame por defecto. Coste real: una segunda iteración del toggle que es prácticamente idempotente.
- La función vive en `app.js`, no en un módulo separado. Se prioriza cohesión con el resto del código del timeline sobre la modularidad. Si en el futuro se extrae un módulo de timeline, este primitivo debería migrar con él.

### Por qué no se hizo solo en `chat.js`
Versiones anteriores intentaban resolver la carrera desde el cliente del chat: polling sobre `burntAreaTimeline`, espera activa con `setTimeout`, secuenciación de acciones... Todo eso requería que el chat conociese detalles internos del visor (qué timelines existen, cuándo están cargados, qué función reconstruye el timeline unificado). Eso rompía la regla de "el chat no toca el estado del visor, lo pasa por sus handlers" y producía un cliente del chat frágil ante cambios en el visor. La solución en `app.js` deja al chat como simple invocador de una **operación con semántica clara**.

## Datos explícitos
- El visor tiene tres capas históricas con timeline: `burnt_area`, `firms_history`, `aemet_max_temp_history`.
- Los toggles `toggleBurntAreaLayer`, `toggleHistoricalFiresLayer`, `toggleAemetMaxTempLayer` aplican el frame por defecto cuando se activan sin haber otras capas históricas visibles.
- El cliente del chat ejecuta las `client_actions` que recibe del backend, sin lógica de ordenación interna.

## Datos inferidos
- La nota se clasifica en `08-llm-y-consulta-en-lenguaje-natural/` por documentar una decisión del módulo chat LLM (a pesar de que el código vive en `app.js`).
- Tipo `decisión`: registra una elección entre dos arquitecturas (lógica en el chat vs. primitivo en el visor).

## Datos faltantes o ambiguos
- Confirmación de autoría como elaboración propia.
- Si la memoria del TFG entra al nivel de microtasks o se queda en el principio ("operación atómica en la capa del visor").
