---
id: TFG-20260512-encadenamiento-espontaneo-de-tools-via-ejemplos-en-prompt
título: "Encadenamiento espontáneo de tools vía ejemplos en el system prompt"
tipo: reflexión
tags:
  - tfg
  - llm
  - tool-calling
  - prompt-engineering
  - composabilidad
contexto: "Reflexión sobre una propiedad emergente observada en el chat LLM de MeteoVisor: el modelo encadena varias tools sin que el catálogo defina explícitamente operaciones compuestas, a partir de un par de ejemplos en el system prompt."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada del cierre del módulo de chat LLM en MeteoVisor"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-12"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: medio
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Documentar más ejemplos reales de encadenamiento espontáneo observados durante pruebas para la memoria."
---

# Encadenamiento espontáneo de tools vía ejemplos en el system prompt

## Contenido
El system prompt del chat LLM incluye un puñado de **ejemplos** de cómo descomponer una consulta en una secuencia de tools. Por ejemplo:

- *"Centra el mapa en Galicia"* → `searchPlace("Galicia")` → `flyTo(bbox)`.

Lo interesante es que **el modelo extrapola** a consultas no ejemplificadas. Para una consulta como *"¿dónde se concentraron focos en Galicia entre el 1 y el 15 de agosto?"* el modelo:

1. Invoca `searchPlace("Galicia")` para obtener un `bbox` válido.
2. Pasa ese `bbox` y las fechas a `firmsHotspotAnalysis(bbox, date_from, date_to)`.
3. Resume el resultado.

Esa composición ad-hoc emerge sin que el catálogo defina una tool agregada del estilo `hotspotsByRegionAndDate`. **Reduce la presión por mantener tools "compuestas" rígidas**: en lugar de añadir N×M variantes para cubrir todas las combinaciones (región × intervalo × sensor × radio), basta con tools atómicas bien tipadas y unos pocos ejemplos canónicos en el prompt.

### Por qué importa para el TFG

- Encaja con la tesis de [[ideas-operaciones-llm-local-en-visor-meteovisor]]: el LLM como **orquestador**, no como capa de operaciones compuestas hardcodeadas.
- Da una métrica cualitativa de la calidad del prompt: si nuevas consultas se resuelven con composiciones sin tocar el catálogo, la arquitectura es más mantenible.
- Sugiere una pauta de prompt-engineering: añadir ejemplos en lugar de tools cada vez que aparece una composición nueva, mientras las tools atómicas existentes basten.

### Riesgos a vigilar

- Composiciones equivocadas: el modelo puede encadenar tools en un orden inválido (por ejemplo pasar un bbox vacío). Mitigado por la validación de tipos en el orquestador y por la inyección de la cobertura temporal en el prompt.
- Composiciones poco eficientes: una composición espontánea puede invocar 4 tools cuando 2 bastarían. Aceptable mientras la latencia agregada se mantenga razonable.

## Datos explícitos
- El system prompt incluye ejemplos de encadenamiento.
- El modelo aplica el patrón a consultas no presentes en los ejemplos.
- Existe el caso real de `searchPlace` + `firmsHotspotAnalysis` para *"focos en Galicia 1–15 agosto"*.

## Datos inferidos
- Mantener tools atómicas + ejemplos rinde mejor que multiplicar tools compuestas.
- La calidad del prompt es factor de diseño tan crítico como el catálogo.

## Datos faltantes o ambiguos
- Set de casos reales medidos durante las pruebas (consulta, tools invocadas, acierto) para anexar a la memoria.
- Comparativa cuantitativa entre tools compuestas hardcodeadas y composición espontánea (latencia, tasa de éxito).
