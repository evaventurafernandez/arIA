---
id: TFG-20260519-aemet-warnings-near-population-eleccion-nucleo-strategy
título: "Parámetro nucleo_strategy en aemetWarningsNearPopulation: elegir núcleo por proximidad o por población"
tipo: decisión
tags:
  - tfg
  - llm
  - chat
  - aemet
  - postgis
  - exposicion-poblacional
  - semantica-de-consulta
contexto: "Corrección de un bug semántico en la tool aemetWarningsNearPopulation del chat LLM de MeteoVisor: ante una zona AEMET que cubre varios núcleos de población, el LATERAL devolvía siempre el más cercano por geometría, no el más relevante para la consulta del usuario cuando éste pedía 'el núcleo con más habitantes'."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada de pruebas en producción del chat LLM"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-19"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar que la memoria del TFG cita los identificadores exactos (`aemetWarningsNearPopulation`, `nucleo_strategy`, los valores `closest` y `most_populated`)."
---

# Parámetro `nucleo_strategy` en `aemetWarningsNearPopulation`: elegir núcleo por proximidad o por población

## Problema observado
Consulta del usuario al chat: *"cuál es el día del histórico en el que se registró un aviso AEMET con temperatura más alta, y cuál es el núcleo de población con MÁS HABITANTES que estaba más cerca"*.

El LLM encadenó correctamente las dos tools:

1. `queryAemetMaxTempHistory({})` → `peak_day = 2025-08-12 (45.0 °C, zona Vegas del Guadiana, nivel Rojo)`.
2. `aemetWarningsNearPopulation({"date": "2025-08-12"})` → devolvió Gévora (2.310 hab.) como núcleo más cercano de Vegas del Guadiana.

El problema: el polígono "Vegas del Guadiana" cubre Gévora **y** Badajoz (≈150.000 hab.). El usuario esperaba Badajoz; recibió Gévora. La respuesta no era falsa según la tool (Gévora *está* cerca), pero contradecía la intención de "más habitantes" del prompt.

## Causa raíz
El SQL del `LATERAL` ordenaba la subconsulta de núcleos exclusivamente por distancia geométrica usando el operador KNN `<->`:

```sql
JOIN LATERAL (
  SELECT ...
  FROM core.nucleos_poblacion_polygon
  WHERE habitantes IS NOT NULL AND habitantes > 0
    AND ST_DWithin(f.geom::geography, geom::geography, %s)
  ORDER BY f.geom <-> geom        -- ←  sólo geometría, ignora habitantes
  LIMIT 1
) n ON true
```

Para varios núcleos dentro del polígono, todos tienen `ST_Distance = 0`. El operador `<->` rompe el empate por una aproximación interna (bounding box / centroides) que no se corresponde con "el más relevante" desde el punto de vista poblacional. Gévora ganó por estar geométricamente próxima al centroide; Badajoz, pese a ser mucho mayor, quedó fuera del top-1.

El LLM, por su parte, no tenía ningún parámetro para pedir "el más poblado". Aunque su prompt entendió la intención del usuario, la tool sólo sabía hablar de "el más cercano".

## Decisión
Se añade el parámetro `nucleo_strategy` a `aemetWarningsNearPopulation`, con dos valores:

- **`closest`** (por defecto, compat hacia atrás): orden actual por `<->`. Útil cuando el usuario pregunta literalmente por proximidad ("el núcleo más cercano a la zona").
- **`most_populated`**: el `LATERAL` pasa a `ORDER BY habitantes DESC NULLS LAST, ST_Distance(...)`. Entre todos los núcleos dentro o cerca de la zona, gana el de mayor población; en empate de población se rompe por distancia geográfica real (no KNN).

```sql
-- nucleo_strategy = 'most_populated'
ORDER BY habitantes DESC NULLS LAST,
         ST_Distance(f.geom::geography, geom::geography) ASC
LIMIT 1
```

La respuesta de la tool devuelve `filters.nucleo_strategy` y un texto en `operation` que indica qué orden se ha usado, de modo que el LLM pueda razonar y citar correctamente cómo eligió el núcleo.

## Cómo aprende el LLM a elegir la estrategia
La regla vive en el system prompt (`chat/prompt.py`), no en código:

> "Que núcleo CON MÁS HABITANTES estaba dentro del aviso de temperatura más alta" / "ciudad más grande afectada por el aviso" → usa `aemetWarningsNearPopulation` con `nucleo_strategy="most_populated"`. Las zonas AEMET cubren provincias enteras y suelen incluir varias ciudades dentro; el default `closest` devolvería una población pequeña cercana al centroide, no la capital del área. Si el usuario habla de tamaño/población, SIEMPRE `most_populated`.

Esto sigue el patrón de las otras tools: el catálogo expone capacidades distintas como parámetros con nombres descriptivos, y el prompt enseña qué pista lingüística mapea a cada uno.

## Validación end-to-end
Probado con un script de probe que envía un único turno al LLM real (`google/gemma-4-26B-A4B-it` vía vLLM) con la consulta literal del usuario:

- Iteración 1: el modelo emite `queryAemetMaxTempHistory({})` ✓
- Iteración 2 (inyectando como observación un `peak_day = 2025-08-12, max_temperature_c = 45.0`): el modelo emite `aemetWarningsNearPopulation({"date":"2025-08-12","nucleo_strategy":"most_populated"})` ✓

El modelo eligió la estrategia correcta sin que el usuario nombrase explícitamente el parámetro. La pista "MÁS HABITANTES" fue suficiente con el prompt actualizado.

## Tests añadidos
En `chat/tests/test_aemet_warnings_near_population.py`:

- `test_nucleo_strategy_closest_uses_knn_order`: por defecto el SQL conserva `ORDER BY f.geom <-> geom`.
- `test_nucleo_strategy_most_populated_orders_by_habitantes`: con la estrategia nueva, el `LATERAL` ordena por `habitantes DESC` y rompe empates por `ST_Distance` (sin `<->`).
- `test_nucleo_strategy_echoed_in_filters`: la respuesta declara `filters.nucleo_strategy` y `operation` para que el LLM pueda razonar sobre qué criterio acaba de aplicar.

## Trade-offs aceptados
- **No es el "más relevante" en sentido general**, solo "más poblado". Si el usuario pidiera "el núcleo histórico más vulnerable" o "el más turístico", la tool seguiría devolviendo Badajoz. Ese tipo de consultas exigirían nuevas estrategias o joins adicionales (con datasets que el TFG no incluye).
- **El default sigue siendo `closest`** para no romper las consultas formuladas en términos de proximidad estricta (e.g. "el pueblo más cercano al aviso"). El precio es que el LLM debe identificar cuándo cambiar de estrategia, riesgo asumido tras ver que el prompt actual lo consigue.
- **No se devuelven varios núcleos por zona**, sólo uno. Si el usuario quisiera ver la lista entera ("todas las ciudades dentro del aviso"), habría que añadir un parámetro `nucleos_per_zone`. Se deja para una iteración futura.

## Datos explícitos
- `core.nucleos_poblacion_polygon` incluye el campo `habitantes` validado y ya se usa en otras tools (`firesNearPopulation`).
- El polígono AEMET para "Vegas del Guadiana" (2025-08-12, nivel Rojo, 45 °C) cubre Badajoz (capital de provincia) y Gévora (pedanía).
- El LLM `google/gemma-4-26B-A4B-it` distingue correctamente entre "núcleo más cercano" y "núcleo con más habitantes" cuando el prompt explicita el mapeo.

## Datos inferidos
- La carpeta `08-llm-y-consulta-en-lenguaje-natural/` por ser una decisión sobre la semántica de una tool del chat.
- Tipo `decisión` (corrección de bug con elección de diseño explícita).

## Datos faltantes o ambiguos
- Confirmar autoría como elaboración propia.
- Decidir si la memoria del TFG cita el caso concreto Badajoz/Gévora como ejemplo de validación o describe sólo el principio.
- Si en futuras versiones se añaden estrategias adicionales (por superficie de núcleo, por densidad, por proximidad al centroide), revisar si conviene mover la enumeración a un módulo de "estrategias de selección espacial" reusable.
