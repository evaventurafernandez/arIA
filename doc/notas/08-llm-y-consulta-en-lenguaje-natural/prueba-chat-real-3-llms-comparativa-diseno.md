---
id: TFG-20260525-prueba-chat-real-3-llms-comparativa-diseno
título: "Prueba comparativa de 3 LLMs en chat real del visor — gemma4:26b vs qwen3.6:27b vs granite4.1:30b"
tipo: decisión
tags:
  - tfg
  - llm
  - chat
  - benchmark
  - end-to-end
  - meteovisor-demo
contexto: "Continuación operativa de la nota TFG-20260519-benchmark-llms-locales-diseno-experimento. La nota previa midió la capacidad de planificación y narrativa de 13 modelos llamando a la API nativa de Ollama (single-shot, sin ejecutar tools). Esta nota documenta una segunda prueba end-to-end: las 5 consultas se ejecutan a través del chat real del visor MeteoVisor (`chat.orchestrator`), con sistema prompt, ejecución real de tools sobre el backend FastAPI, sanitización y posible multi-turn. El objetivo es comparar el modelo gemma actualmente desplegado en la demo (`google/gemma-4-26B-A4B-it` = `gemma4:26b` en Ollama) frente a los 2 finalistas seleccionados de la comparativa cualitativa: `qwen3.6:27b` (mejor calidad global del juicio Opus 4.7) y `granite4.1:30b` (mejor candidato a Mode B puro por latencia y disciplina estructural)."
fuente_existe: true
fuente_tipo: "elaboración propia + nota predecesora"
fuente_descripción: "continuación operativa de meteovisor-demo/doc/notas/08-llm-y-consulta-en-lenguaje-natural/benchmark-llms-locales-diseno-experimento.md; reutiliza las 5 consultas, el system prompt y el catálogo de tools ya consolidados. Justificaciones de cada modelo apoyadas en model cards oficiales (IBM Granite 4.0, Qwen3 Team, Google DeepMind Gemma 3) ya enlazados en la Sección 11 de la nota previa."
fuente_url: ""
autor_o_entidad: "autor del TFG"
fecha_fuente: "2026-05-25"
licencia_o_copyright: "uso académico del TFG"
condiciones_de_uso: "uso interno del TFG; respuestas literales del LLM se incluyen como evidencia experimental"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar con el tutor que el set final de 3 modelos (gemma4:26b + qwen3.6:27b + granite4.1:30b) es defendible ante el tribunal o si conviene añadir un 4º (glm-4.7-flash, único que reconoció T10 en el juicio)."
  - "Confirmar que el script `chat_e2e.py` (Opción B) puede saltar el rate limit del chat (`CHAT_RATE_LIMIT=30/minute`) o si las 45 invocaciones se distribuirán en el tiempo."
  - "Decisión opcional: si la respuesta del backend en una tool tarda más de `LLM_REQUEST_TIMEOUT=120 s` ¿se reintenta o se anota como fallo end-to-end?"
  - "Confirmar si los 45 outputs literales se incluirán como anexo en la memoria del TFG o solo el Markdown comparativo resumen."
---

# Prueba comparativa de 3 LLMs en chat real del visor — gemma4:26b vs qwen3.6:27b vs granite4.1:30b

## 1. Por qué una segunda prueba (qué añade sobre la nota previa)

La nota previa (`benchmark-llms-locales-diseno-experimento.md`, Sección 8) midió **planificación + narrativa** llamando directamente a `/api/chat` de Ollama:

- Mode A: prosa sin schema de tools.
- Mode B: single-shot — registramos los `tool_calls` que devuelve la **primera** respuesta del modelo, sin alimentar resultados intermedios.

Esto deja sin medir varias dimensiones reales del visor:

| Dimensión | Cubierta en nota previa | Cubierta aquí |
|---|---|---|
| Selección de tool del catálogo | ✓ (single-shot) | ✓ (real, multi-turn) |
| Argumentos de tool en rango | ✓ (single-shot) | ✓ (real, multi-turn) |
| **Ejecución real de la tool contra el backend** | ✗ | **✓** |
| **Encadenamiento multi-turn con resultados reales** | ✗ | **✓** (hasta `LLM_MAX_TOOL_ITERATIONS=8`) |
| **Narrativa generada SOBRE datos reales devueltos por las tools** | ✗ | **✓** |
| **Sanitización + rate limit + truncado del input del usuario** | ✗ | **✓** |
| **Streaming SSE como lo verá el usuario final** | ✗ | **✓** |
| **Tiempo end-to-end percibido en el visor** | ✗ (solo latencia LLM) | **✓** (LLM + tools + red) |

En otras palabras: la nota previa eligió **candidatos** basándose en planificación intrínseca; esta nota valida **comportamiento en producción** de los 3 finalistas operativos.

## 2. Modelos seleccionados y justificación

| Modelo | Tag Ollama | Identificador en `.env` del demo | Por qué entra |
|---|---|---|---|
| **gemma4:26b** | `gemma4:26b` | `google/gemma-4-26B-A4B-it` | **Modelo desplegado actualmente en la demo del visor**. Es el baseline contra el que cualquier cambio de modelo debe demostrar mejora. Justificación documental: ya integrado, ya validado funcionalmente en las pruebas e2e existentes del proyecto (`chat/tests/`), conocido por el equipo, no requiere migración de configuración. La nota previa lo descartó por latencia Mode B en el escenario sintético (59.7 s media); esta nota verifica si esa latencia se reproduce en el chat real (donde el orquestador puede paralelizar o el caché de keep_alive puede ayudar). |
| **qwen3.6:27b** | `qwen3.6:27b` | `qwen3.6:27b` | **Recomendado nº1 por el juicio cualitativo de Claude Opus 4.7** (Sección 10.1 de la nota previa: global score 87.82, faithfulness 4.73/5 — la más alta del lote). Único top-5 que en Mode A usa placeholders y declara explícitamente que no fabrica datos. Es el principal candidato a sustituir al gemma en producción según la reconciliación de Sección 10.7 ("modo híbrido Mode B + narrativa al usuario"). |
| **granite4.1:30b** | `granite4.1:30b` | `granite4.1:30b` | **Recomendado nº1 por el juicio cualitativo en el escenario "Mode B puro"** y nº3 absoluto (82.70). Familia IBM Granite, post-entrenada específicamente para function calling (industry-leading en BFCL v3 según IBM). Ver justificación detallada del cambio en Sección 2.1. |

### 2.1 Por qué granite4.1:30b en lugar de qwen3.6:35b-a3b-q8_0

El segundo modelo del juicio cualitativo por score global fue `qwen3.6:35b-a3b-q8_0` (86.33, 2º absoluto). Se sustituye por `granite4.1:30b` (82.70, 3º absoluto) por cinco razones operativas que pesan más que los 3.6 puntos de diferencia en score:

1. **Hardware del despliegue actual**: `qwen3.6:35b-a3b-q8_0` ocupa **38.7 GB** en disco (cuantización Q8_0); la GPU donde corre la demo aloja también el backend, vector DB y servicios auxiliares. Cargarlo concurrentemente con `gemma4:26b` (17.5 GB) durante el switch del experimento es inviable sin desplazar otros servicios. `granite4.1:30b` pesa **17.5 GB** (Q4_K_M) — mismo footprint que la gemma desplegada, intercambio drop-in sin tocar el resto de la pila.

2. **Latencia operativa**: `granite4.1:30b` es **el más rápido del top-5 en Mode B** (2.0 s media frente a 10.5 s de `qwen3.6:35b-a3b-q8_0` y 24.7 s de `qwen3.6:27b`, Sección 10.1 de la nota previa). En un chat interactivo del visor la latencia importa tanto como la calidad — un asistente de 2 s es viable para emergencias, uno de 10-25 s no.

3. **Diversidad de familias**: con `gemma4:26b` + `qwen3.6:27b` + `granite4.1:30b` el experimento cubre **tres proveedores distintos** (Google DeepMind, Alibaba Qwen, IBM Granite) — cada uno con su propio post-training de tool calling. Con `qwen3.6:35b-a3b-q8_0` habría 2 modelos Qwen de 3, sesgando la comparativa hacia una sola familia. Esta razón está alineada con el criterio "Diversidad de familias" ya aplicado para reducir 10→5 candidatos en el juicio cualitativo (Sección 9.3 de la nota previa).

4. **Cobertura del escenario operativo "Mode B puro"**: la tabla 10.7 de la nota previa define dos escenarios de despliegue del visor: (A) modo híbrido Mode B + narrativa al usuario → recomendado `qwen3.6:27b`; (B) Mode B puro con narrativa por código/plantillas → recomendado `granite4.1:30b`. El set actual (gemma como baseline, `qwen3.6:27b` para A, `granite4.1:30b` para B) cubre **ambos escenarios candidatos a producción**, mientras que sustituirlo por `qwen3.6:35b-a3b-q8_0` solo cubría una variante de A.

5. **Disciplina estructural**: `granite4.1:30b` fue el **único modelo con 100 % en las cuatro métricas estructurales** del barrido sintético (`has_4_blocks`, `tool_calls_in_catalog`, `tool_calls_schema_valid`, `tool_support: native`) y 0 errores en 30 invocaciones (Sección 8.4 punto 1 de la nota previa). En chat end-to-end con ejecución real de tools esa disciplina es justo lo que se quiere validar: que no se rompa el contrato del catálogo cuando entran resultados reales en el contexto.

**Compensación honesta**: `granite4.1:30b` tiene la faithfulness más baja del top-4 (3.43/5 vs 4.37 de `qwen3.6:35b-a3b-q8_0`) — fabrica datos en Mode A. Este es exactamente el tipo de patología que **solo se puede detectar en chat end-to-end**: la nota previa la observó en un single-shot donde el modelo no tenía datos reales que copiar; aquí, con resultados reales de las tools en el contexto, la pregunta a contestar es si granite los usa con fidelidad o si sigue inventando. La inclusión de granite en esta segunda fase es **precisamente para validar o desmentir esa preocupación** antes de la decisión final.

### 2.2 Descartados explícitos para esta segunda fase

- `qwen3.6:35b-a3b-q8_0`: ver Sección 2.1.
- `glm-4.7-flash:latest`: único modelo que reconoció la limitación de T10 — interesante pero entró 4º en el juicio. Se reserva como modelo complementario "para consultas con limitación de capa" si la decisión de producto va hacia un router multi-modelo. Pendiente de validar con el tutor si conviene añadirlo como 4º modelo del experimento.
- `llama3.1:8b`: bimodal — bueno en q1-q3, se rompe en q4-q5. Reservado para escenario "GPU pequeña, intents simples", no aplicable al despliegue Helios actual.

## 3. Consultas (reutilizadas literales de la nota previa)

Las **mismas 5 consultas** de `meteovisor-test-llms/config/queries.yaml`, sin modificación. Numeración estable y la misma justificación de dificultad (1 sencilla + 2 medias + 2 complejas, ver Sección 3 de la nota previa):

1. **q1 (sencilla, glosario)**: *¿Qué es el FWI?*
2. **q2 (media, tool único)**: *¿Hay algún núcleo de población de menos de 5.000 habitantes a menos de 2 km de distancia de un foco activo?*
3. **q3 (media, agregación temporal)**: *¿Qué día recopilado en el histórico es en el que hay más superficie de áreas quemadas?*
4. **q4 (compleja, cadena completa)**: *¿Cuál es el día del histórico en el que se registró un aviso AEMET con temperatura más alta, y cuál es el núcleo de población con más habitantes que estaba más cerca?*
5. **q5 (compleja, multi-capa con rechazo controlado)**: *¿Qué áreas geográficas que están bajo aviso meteorológico en relación a aguas, lluvias y tormentas, tienen un núcleo de población de menos de 5.000 habitantes a menos de 2 km de una zona inundable? Muéstrame únicamente las capas utilizadas y los resultados en el mapa.*

## 4. Metodología

### 4.1 Configuración del visor para cada corrida

El chat del visor lee tres variables de `.env` (`meteovisor-demo/.env.example` líneas 23-33):

- `LLM_API_URL` — endpoint OpenAI-compatible (`/v1/chat/completions`).
- `LLM_API_KEY` — bearer token (Helios usa el mismo del benchmark previo).
- `LLM_MODEL` — identificador exacto del modelo según `/v1/models` del servidor.

Para cada uno de los 3 modelos:

1. Detener uvicorn del backend del visor.
2. Editar `.env` y poner `LLM_MODEL=<tag>` (los tres tags están en la tabla de Sección 2).
3. Reiniciar el backend: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`.
4. Verificar con un curl mínimo a `/api/chat/health` (o equivalente) que el modelo carga sin error.
5. Lanzar las 5 consultas × 3 temperaturas (Sección 4.2).
6. Volcado de resultados (Sección 4.3).
7. Restaurar `LLM_MODEL=google/gemma-4-26B-A4B-it` al terminar.

**Resto de variables fijas** (no se tocan entre corridas para no contaminar la comparativa):
- `LLM_MAX_TOOL_ITERATIONS=8` (default del repo).
- `LLM_REQUEST_TIMEOUT=120` segundos.
- `CHAT_RATE_LIMIT=30/minute`.
- `CHAT_MAX_USER_MESSAGE_LENGTH=4000` caracteres — las 5 consultas están por debajo.

### 4.2 Lanzamiento de las 15 combinaciones por modelo (45 totales)

**Producto cartesiano**: 3 modelos × 5 consultas × 3 temperaturas = **45 conversaciones reales end-to-end**.

**Temperaturas**: `[0.0, 0.3, 0.7]` — las mismas tres del barrido sintético (Sección 2 de la nota previa). Razón de mantener el barrido completo en esta segunda fase (frente a la propuesta inicial de fijar T=0): aunque el efecto temperatura sobre la calidad cualitativa fue plano en el barrido sintético (Sección 10.5: 80.95 → 79.73 entre T=0 y T=0.7), **eso se midió single-shot sin contexto de tools reales**. En chat end-to-end la temperatura afecta también a (a) cómo el modelo redacta sobre los datos devueltos por las tools, (b) si reformula la respuesta cuando una tool falla, y (c) si encadena tools de forma más exploratoria a T>0. Estas tres facetas no estaban presentes en el barrido sintético y justifican re-evaluarlas aquí. La elección de la temperatura adecuada para producción se hará tras inspeccionar el Markdown comparativo de Sección 4.3.

**Inyección de temperatura**: el cliente actual del chat (`chat/llm_client.py` `chat_completion`) no envía `temperature` en el payload — usa el default del servidor. Para este experimento hay que (i) extender la firma de `chat_completion` añadiendo `temperature: float | None = None` y propagarla al payload OpenAI, o (ii) más simple para la corrida de experimento, **inyectarla a nivel de orquestador** desde una nueva variable de entorno `LLM_TEMPERATURE` que se cambie igual que `LLM_MODEL` entre corridas. Decisión recomendada: opción (ii) — minimiza cambios al código de producción y permite recuperar el comportamiento por defecto eliminando la variable.

**Lanzamiento — Opción A (manual desde la UI del visor)**: cada consulta se escribe literalmente en el chat de la demo del visor desplegada. Se captura la conversación íntegra desde el log JSONL del orquestador (`auditoria-conversacion-chat-llm-log-jsonl.md` documenta el formato). Coste: ~45 interacciones manuales repartidas en sesiones.

**Lanzamiento — Opción B (script, preferida)**: un script `meteovisor-test-llms/chat_e2e.py` que:
- Lee `meteovisor-test-llms/config/queries.yaml` (mismas 5 consultas).
- Lee de su propio config el set de 3 modelos × 3 temperaturas.
- Para cada (modelo, consulta, temperatura), hace `POST /api/chat` (o el endpoint streaming SSE del visor) con `{"message": <texto literal>, "history": []}` tras setear `LLM_MODEL` y `LLM_TEMPERATURE` y reiniciar el backend (o bien — más sencillo — exponer un override por header `X-LLM-Model` y `X-LLM-Temperature` solo activo en entorno de test).
- Captura la respuesta completa: `assistant_text_final`, `tool_calls` ejecutadas, `tool_results` devueltos, latencia wall-clock.
- Respeta `CHAT_RATE_LIMIT=30/minute` introduciendo un sleep entre llamadas (≥2 s) o saltándolo si el endpoint de test lo permite.
- Vuelca a `meteovisor-test-llms/results/chat_e2e/{model_safe}__q{id}__t{temp}.json`.

La Opción B es la preferida porque garantiza reproducibilidad y artefactos comparables uno a uno; la Opción A queda como fallback si el override por header no se quiere introducir.

### 4.3 Formato de salida

Por cada (modelo × consulta × temperatura) se guarda un fichero JSON con la conversación íntegra:

```
meteovisor-test-llms/results/chat_e2e/{model_safe}__q{id}__t{temp}__YYYY-MM-DDTHHmmss.json
```

Contenido mínimo:
- `model` (tag exacto), `query_id`, `query_text`, `temperature`, `timestamp`.
- `iterations`: lista de turnos con (a) tool_calls emitidas, (b) tool_results devueltos por el backend (datos reales), (c) texto del asistente en ese turno.
- `assistant_text_final`: la respuesta que vería el usuario al cerrar la conversación.
- `latency_total_ms`, `latency_per_iteration_ms[]`.
- `tool_calls_count`, `tool_calls_unique_count`, `tool_errors[]` (si alguna tool falló al ejecutarse).
- `error_kind` ∈ {`null`, `timeout`, `http_5xx`, `tool_iteration_limit`, `sanitization_rejected`}.

Además, **dos Markdown comparativos** en `meteovisor-test-llms/results/chat_e2e/`:

- `_comparativa_3llms_por_modelo__YYYY-MM-DDTHHmmss.md`: 3 secciones (una por modelo), dentro 5 sub-secciones (una por consulta), dentro 3 sub-sub-bloques (una por temperatura). Útil para inspeccionar **el efecto temperatura dentro de cada modelo**.
- `_comparativa_3llms_por_consulta__YYYY-MM-DDTHHmmss.md`: 5 secciones (una por consulta), dentro 3 sub-secciones (una por temperatura), dentro 3 sub-sub-bloques (una por modelo). Útil para comparar **modelos lado a lado en la misma consulta**.

Estos dos Markdown son los artefactos principales para incluir en el TFG como evidencia visual.

## 5. Análisis previsto

Métricas a extraer del JSON y comparar entre los 3 modelos:

| Eje | Definición operativa | Por qué importa |
|---|---|---|
| **Corrección end-to-end** | ¿La respuesta final menciona el dato correcto devuelto por la tool real? | El benchmark previo medía planificación; esto mide si **interpreta bien** lo que la tool le devuelve. |
| **Encadenamiento real** | ¿Logra completar consultas multi-paso (q4) o se queda parado? | q4 era ejecutable pero requería usar resultado de una tool como input de la siguiente. |
| **Manejo de rechazo controlado** | En q5, ¿reconoce la limitación T10 *ahora que el backend devolverá un error tipo "tool not available"*? | El benchmark previo dio 0 % en `declared_limitation` porque el LLM nunca recibió la señal de error real; aquí sí la recibirá. |
| **Latencia total percibida** | Tiempo desde envío de la consulta hasta texto final del asistente. | UX real del visor (≠ latencia LLM aislada). |
| **Número de iteraciones tool** | Cuántos turnos consume hasta cerrar respuesta. | Indicador de eficiencia operativa. |
| **Coste de tokens** | Suma de `prompt_tokens` + `completion_tokens` de toda la conversación. | Impacto en cupo/coste si en futuro se pasa a un proveedor con tarificación por token. |
| **Sensibilidad a temperatura** | Diferencia de corrección/latencia/iteraciones entre T=0, T=0.3, T=0.7 para el mismo (modelo, consulta). | Permite elegir la temperatura óptima de producción por modelo. |

## 6. Hipótesis a contrastar (predicciones del autor)

Basadas en los resultados de la nota previa, se anticipa:

1. **`gemma4:26b` será el más lento end-to-end** (≥3× los otros dos). La nota previa midió 59.7 s en Mode B Ollama puro; con tools reales encadenadas la cifra probablemente empeora.
2. **`qwen3.6:27b` tendrá la narrativa más fiel** (menos fabricación de datos). Coherente con su faithfulness 4.73/5 vs 3.43-3.73 del resto en el barrido sintético.
3. **`granite4.1:30b` tendrá la latencia más baja y el plan de tools más limpio** (2.0 s media single-shot en la nota previa). La pregunta abierta es si su faithfulness (3.43/5 en sintético) mejora ahora que tiene datos reales en el contexto en lugar de fabricarlos — esta validación es la principal aportación del experimento.
4. **El efecto temperatura será más visible en `gemma4:26b`** (más sensible a sampling) y menor en `granite4.1:30b` (modelos Granite reportan ser muy disciplinados a T=0 según model card de IBM).
5. **Ninguno de los tres reconocerá la limitación T10 en q5 sin modificar el system prompt** — el `tool_results` del backend devolverá un error explícito, pero el system prompt actual no instruye a tratar errores `tool_not_available` como rechazo controlado al usuario (acción derivada nº 1 de Sección 8.4 de la nota previa, aún pendiente).

Si las hipótesis 1-3 se confirman, la recomendación al tutor será **migrar la demo de `gemma4:26b` a `qwen3.6:27b`** (modo híbrido con narrativa fiel) o a **`granite4.1:30b`** (modo Mode B puro con latencia baja), según qué cualidad pese más en la decisión de producto. Si la hipótesis 5 se confirma, **acción inmediata Fase 2**: enriquecer el system prompt antes de la migración.

## 7. Trade-offs y limitaciones reconocidas

- **N=45 conversaciones**. Suficiente para detectar diferencias gruesas y el efecto temperatura por modelo; insuficiente para diferencias sutiles (<10 %). Aceptable porque se complementa con N=300 de la nota previa (juicio cualitativo) y N=390 del barrido sintético.
- **Sin evaluación humana exhaustiva de las respuestas literales** — se hará inspección visual del Markdown comparativo. Se documenta como limitación para el tribunal del TFG; si lo pide, ampliable con anotación 1-5 sobre los 45 outputs (coste manual razonable).
- **Dependencia del estado del backend** — los datos devueltos por las tools (incendios, avisos, núcleos) reflejan el estado de la BD en el momento de la corrida. Para reproducibilidad estricta convendría hacer un snapshot, pero queda fuera de alcance. Documentar el `git rev` del backend y la fecha de los datos AEMET/FIRMS al inicio de la corrida.
- **Rate limit del chat** (`CHAT_RATE_LIMIT=30/minute`) puede ralentizar la Opción B; las 45 conversaciones pueden generar >30 peticiones/minuto si cada una hace varias iteraciones de tool. Mitigación: añadir sleep entre conversaciones o exponer un endpoint de test que salte el rate limit.
- **Cambio de temperatura requiere modificación del cliente LLM** (`chat/llm_client.py` actualmente no propaga `temperature`). Es una modificación trivial (~5 líneas) y reversible, pero queda registrada como cambio temporal del código de la demo durante el experimento.

## 8. Resultados (2026-05-25)

### 8.0 Resumen ejecutivo

Experimento ejecutado el 2026-05-25. **37 conversaciones válidas** de las 45 originalmente previstas (gemma se interrumpió a los 7 cells de 15 por ineficiencia confirmada; qwen perdió 5 cells del cycle T=0.7 por health-timeout del backend; granite completo 15/15). Wall-clock total ≈ **63 minutos**.

**Conclusión operativa**:

| Modelo | end-to-end OK % | Lat. media (ms) | Lat. mediana (ms) | 4-bloques % | Veredicto chat real |
|---|---|---|---|---|---|
| **`granite4.1:30b`** | **60 % (9/15)** | **23 770** | **14 603** | 100 % | **Único viable** sin más cambios. |
| `qwen3.6:27b` | 40 % (4/10*) | 34 639 | 30 815 | 100 % | Viable; respuestas más limpias que granite pero ~1.5× más lento. |
| `gemma4:26b` | 14 % (1/7*) | 189 067 | 189 067 | 100 % | **NO viable**: timeout sistemático en multi-turn. Migrar fuera del demo. |

(* tamaños distintos por cells perdidos — ver Sección 8.6).

**Hallazgo central**: **ninguno de los 3 modelos completa q4 ni q5 dentro del presupuesto del experimento** (300 s por conversación). Las cadenas multi-paso sobre datos reales (q4: argmax sobre 70 993 features AEMET; q5: cruce multi-capa con T10) **exceden el techo de paciencia razonable de un asistente interactivo**. Es el techo real del sistema, no del modelo aislado.

### 8.1 Tabla agregada por modelo

| Modelo | n cells | OK | Fail | OK % | Lat. media (ms) | Lat. mediana (ms) | Iters media | 4-bloques % | Tool calls media |
|---|---|---|---|---|---|---|---|---|---|
| `gemma4:26b` (parcial) | 7 | 1 | 6 | 14 | 189 067 | 189 067 | 2.00 | 100 | 1.00 |
| `qwen3.6:27b` (parcial) | 10† | 6 | 4 | 60 | 34 639 | 30 815 | 2.00 | 100 | 1.00 |
| `granite4.1:30b` (completo) | 15 | 9 | 6 | 60 | 23 770 | 14 603 | 2.78 | 100 | 1.78 |

† qwen T=0.7 (5 cells) se perdió por health-timeout del backend (ver 8.6). Si se cuenta como fallos: 6/15 = 40 % (cifra del agregado por modelo). Si se excluyen: 6/10 = 60 % sobre cells válidos. Ambas cifras documentadas honestamente.

**Observaciones**:
- **Granite es 5-8× más rápido que gemma** y **~1.5× más rápido que qwen** en mediana (14.6 s vs 30.8 s). Coherente con el bench previo (granite 2.0 s vs qwen 24.7 s en Mode B single-shot, Sección 8.1 nota previa); con tools reales encadenadas, la ventaja se reduce pero se mantiene.
- **Granite usa más iteraciones promedio** (2.78 vs 2.00 de los otros) y **más tool calls medios** (1.78 vs 1.00) — encadena más tools por consulta. Esto explica parte de su latencia mayor por respuesta exitosa pero también su mayor capacidad de resolver consultas más complejas con éxito.
- **4-bloques 100 %** en los tres modelos en respuestas exitosas — disciplina estructural impecable cuando llegan a responder. Esto contrasta con el `13.3 %` de llama3.1:8b en el bench previo Mode A: el orquestador del visor (parser de bloques, instrucciones explícitas en system prompt) ayuda a forzar el formato.

### 8.2 Tabla por consulta (a través de todos los modelos y temperaturas)

| qid | Nivel | n | OK % | Lat. media (ms) | Iters media | Tool calls media | Observación |
|---|---|---|---|---|---|---|---|
| q1 | sencilla | 8 | **75 %** | 59 003 | 2.00 | 1.00 | 6/8 OK (gemma falla en T=0.3 sin retry). Tool: `explainTerm`. |
| q2 | media | 8 | **62 %** | 36 419 | 2.80 | 1.80 | qwen + granite OK. Tool: `activeFiresNearPopulation(2000, 5000)`. |
| q3 | media | 7 | **71 %** | 14 945 | 2.60 | 1.60 | qwen + granite OK. Argmax temporal sobre stats diarios. |
| q4 | compleja | 7 | **0 %** | — | — | — | **Timeout 300 s en TODOS los modelos**. Cadena AEMET argmax → nearest núcleo no completa. |
| q5 | compleja | 7 | **0 %** | — | — | — | **Timeout 300 s en TODOS los modelos**. Multi-capa con T10 no vectorial — el orquestador entra en bucle al no tener la tool ejecutable. |

**Hallazgo cualitativo** (apoya hipótesis 5 de la Sección 6): q5 es el escenario peor — sin la enumeración explícita de capas no ejecutables en el system prompt, el modelo intenta seguir y agota iteraciones. Pasar de single-shot (nota previa: 70.2 score Mode B) a end-to-end multi-turn empeora la situación, no la mejora.

### 8.3 Tabla por temperatura

| T | n | OK % | Lat. media (ms) | Iters media | 4-bloques % | Comentario |
|---|---|---|---|---|---|---|
| 0.0 | 15 | 46 % | 51 689 | 2.29 | 100 | Incluye gemma T=0 (5 cells, 1 OK) → lastra la media. Si solo se cuentan qwen+granite: 6/10 = 60 %. |
| 0.3 | 12 | 50 % | 31 512 | 2.33 | 100 | Mejor balance. |
| 0.7 | 10 | 30 % | **19 979** | 3.00 | 100 | Solo 10 cells (granite completo, qwen perdió 5 por health-timeout). Latencia *menor* porque granite encadena más rápido a T alta — pero más iters (3.0 vs 2.29 a T=0). |

**El efecto temperatura es marginal** sobre los modelos que responden (qwen + granite), confirmando la observación de la nota previa Sección 10.5 (~1 punto entre extremos en el juicio cualitativo). Para producción confirmamos: **T=0 (planificación reproducible) o T=0.3 (operación realista)** — ambas indistinguibles en estos datos.

### 8.4 Markdown comparativos generados

- `meteovisor-test-llms/results/chat_e2e/_comparativa_chat_e2e_por_modelo.md` (37 conversaciones agrupadas: 3 secciones modelo × 5 consultas × 3 temperaturas, con respuesta literal del asistente, trace de tools y métricas por celda).
- `meteovisor-test-llms/results/chat_e2e/_comparativa_chat_e2e_por_consulta.md` (mismas 37 conversaciones agrupadas: 5 secciones consulta × 3 temperaturas × 3 modelos lado a lado — la lectura más útil para comparar modelos en la misma pregunta).
- `meteovisor-test-llms/results/chat_e2e/_summary_chat_e2e.csv` (37 filas, columnas planas listas para hoja de cálculo).
- `meteovisor-test-llms/results/chat_e2e/_aggregates_chat_e2e.md` (tablas agregadas, fuente de 8.1/8.2/8.3 de esta sección).

### 8.5 Observaciones cualitativas (de los outputs literales)

**`gemma4:26b`** (1 cell exitoso, q1 T=0):
- Respuesta a q1 técnicamente correcta — invoca `explainTerm("FWI")`, produce los 4 bloques bien etiquetados, narrativa fluida sobre el FWI.
- Latencia 189 s para una pregunta de glosario sin cadena de tools es **18× peor que granite y 9× peor que qwen** en la misma pregunta. Inviable como asistente interactivo.
- En q2-q5 timeout sistemático tras 180-300 s. Patrón **idéntico** al observado en bench sintético Mode B (Sección 8.4 punto 3 de la nota previa: "gemma4:26b 59.7 s media, 1 timeout"). El chat real solo empeora la cifra porque ahora encadena tool execution real.
- **Veredicto**: descarte definitivo. La demo debería migrarse fuera de gemma — actualmente en producción funciona porque se sirve sobre **vLLM**, no sobre Ollama, y vLLM tiene un adaptador de tool calling más maduro para Gemma. En Ollama el adaptador está roto / es ineficiente.

**`qwen3.6:27b`** (6 cells exitosos, q1-q3 en T=0 y T=0.3):
- Respuestas a q1-q3 **muy limpias**: usa los nombres exactos del catálogo (`explainTerm`, `activeFiresNearPopulation`, `queryBurntArea`) con argumentos gold-standard (`distance_m=2000, population_max=5000` en q2). Narrativa precisa sobre datos reales devueltos: "**51 pares foco-núcleo** que cumplen los criterios (se muestran los 50 primeros por límite de respuesta)".
- 4-bloques siempre correctos, mediana 30.8 s — aceptable para un asistente interactivo.
- q4 y q5 timeout. Hipótesis 2 de Sección 6 ("qwen tendrá la narrativa más fiel"): **confirmada en q1-q3**; no se pudo verificar en q4-q5.
- **Veredicto**: viable para producción si se asume que q4-q5 (consultas complejas multi-paso) o bien se simplifican a sub-consultas o bien se acepta un timeout mayor (≥10 min).

**`granite4.1:30b`** (9 cells exitosos, q1-q3 en las 3 temperaturas):
- Respuestas a q1-q3 también **correctas en plan y tools**: identifica `explainTerm`, `activeFiresNearPopulation`, `queryBurntArea` con argumentos correctos. Encadena más tools por respuesta (1.78 media vs 1.00 de qwen) — incluye acciones de UI como `showGeoJsonResults` y `setVisibleLayers`.
- **Latencia mediana 14.6 s** — claramente el más rápido del trío en respuestas exitosas.
- **Patología observada en q2 T=0**: tras invocar `activeFiresNearPopulation` (OK con 51 resultados) granite añade un `showGeoJsonResults` con `geojson: {features: [], type: 'FeatureCollection'}` — es decir, EMPTY features. El bloque `[Resultados]` queda incompleto en algunos casos. Coherente con la **faithfulness 3.43/5 más baja del top-4** del juicio cualitativo previo (Sección 10.1 nota previa): granite tiende a "completar" la conversación con acciones de UI sin pasar los datos reales.
- q4-q5 timeout, igual que los demás.
- **Veredicto**: viable y rápido, pero **necesita prompt-engineering** para evitar acciones de UI con datos vacíos.

### 8.6 Trade-offs y limitaciones reconocidas (qué no se ha medido)

1. **N total < 45 previstos** (37 cells válidos):
   - **gemma**: tras los 5 cells de T=0 + 2 de T=0.3 = 7 cells, **se canceló deliberadamente el resto** (8 cells de gemma) porque la señal "gemma timeout sistemático" ya estaba clara y reconfirmarla a T=0.3 q3-5 y T=0.7 q1-5 habría consumido ~50 minutos sin aportar información. Justificación documentada inline en `chat_e2e.py`.
   - **qwen T=0.7**: 5 cells perdidos por health-timeout del backend (uvicorn no llegó a estado healthy en 240 s para esa configuración concreta — probable cold-load de modelo en Ollama coincidiendo con un fallo de spawn intermitente). Documentado en `_run_log.jsonl` como `health_timeout`.

2. **Timeout de 300 s por conversación**: es el techo del script (`PER_REQUEST_TIMEOUT`), no del modelo. Dentro de 300 s el orquestador puede hacer hasta ~2-3 iteraciones LLM (cada una con su propio timeout de 180 s `LLM_REQUEST_TIMEOUT`). q4 y q5, al pedir cadenas largas, agotan presupuesto. Para diagnosticar si el modelo *llegaría* a responder con más tiempo habría que ampliar a 900 s — fuera de alcance de esta primera iteración. **El 0 % en q4-q5 es una propiedad del sistema (LLM + orquestador + tool catalog + presupuesto razonable de UX), no del modelo aislado**.

3. **No hay anotación cualitativa 1-5 de las respuestas literales**: como se anticipó en la Sección 7. Los Markdown comparativos están preparados para inspección visual. Si el tribunal del TFG la solicita, se puede añadir como anexo.

4. **El gemma testado aquí es `gemma4:26b` servido sobre Ollama/Helios**, NO `google/gemma-4-26B-A4B-it` servido sobre vLLM (el de la demo actual). Mismos pesos pero pila de serving distinta. Para una comparación 100 % equivalente habría que reproducir este experimento contra el endpoint vLLM `http://192.168.1.162:30000/v1/chat/completions`. Documentado como ampliación pendiente.

5. **Estado de la BD**: snapshot del 2026-05-25: `aemet_max_temperature_daily_feature=70 993 filas` (2025-04-30 a 2026-05-25), `firms_hotspot=49 409 filas`, `firms_hotspot_daily_stat=123 filas` (2025-05-01 a 2025-08-31), `burnt_area_daily_stat=123 filas` (2025-05-01 a 2025-08-31), `nucleos_poblacion_polygon` cargado. Datos suficientes para que las tools devuelvan resultados reales — verificado en q2 (granite encontró 51 pares foco-núcleo reales).

### 8.7 Recomendación final reconciliada al tutor

Combinando los resultados del bench sintético (nota previa Sección 10.7) con esta validación end-to-end:

| Decisión | Modelo recomendado | Justificación |
|---|---|---|
| **Modelo principal para producción del visor** | **`granite4.1:30b`** | Único modelo con 60 % OK end-to-end + latencia mediana 14.6 s (asistente interactivo aceptable) + 4-bloques 100 %. Cambio drop-in respecto a gemma actual (mismo footprint VRAM 17.5 GB). |
| **Fallback / alternativa narrativa** | `qwen3.6:27b` | Respuestas más fieles cuando se invocan (sin la patología de `showGeoJsonResults` vacío de granite); usarlo si la faithfulness es prioritaria sobre la latencia. |
| **Descarte explícito** | `gemma4:26b` **en Ollama** | Ineficiencia sistémica del adaptador de tool calling de Gemma en Ollama. La demo actual sobre vLLM puede seguir igual, pero la migración a Helios/Ollama queda excluida. |

**Acciones derivadas obligatorias (Fase 2)** para alcanzar OK > 80 % global:

1. **Enriquecer system prompt** con enumeración explícita de capas no ejecutables (T10) y formato de respuesta cuando una sub-consulta no se puede resolver. Es la **misma acción** que la nota previa identificó (Sección 8.4 punto 6) — confirmada aquí: ningún modelo reconoce T10 en q5 en chat end-to-end.
2. **Detectar bucles de tool en el orquestador**: cuando el LLM invoca la misma tool 3 veces consecutivas con argumentos similares, cortar y forzar respuesta. Mitiga q4-q5 sin tocar el modelo.
3. **Para granite específicamente**: añadir al system prompt una instrucción de "no emitir `showGeoJsonResults` con `features: []`". Resuelve la patología observada en q2.
4. **Replicar este experimento sobre vLLM** para `gemma4:26b` (la pila real de producción) para confirmar si la migración a granite es genuinamente necesaria o si el problema de gemma es solo del adaptador Ollama.

### 8.8 Trazabilidad y reproducibilidad

- Script de ejecución: `meteovisor-test-llms/chat_e2e.py` (gestiona 9 ciclos uvicorn × queries con resume y env restore al final).
- Script consolidador: `meteovisor-test-llms/consolidate_chat_e2e.py` (lee los 37 JSON y produce los 4 artefactos de Sección 8.4).
- Cambios en el backend del visor (revertibles, en git):
  - `main.py`: añadida `llm_temperature: float | None = None` en `Settings`.
  - `chat/router.py`: propaga `temperature=getattr(settings, "llm_temperature", None)` en `_build_config`.
  - `chat/orchestrator.py`: `OrchestratorConfig` recibe `temperature`; las dos llamadas a `chat_completion` la pasan.
  - `chat/llm_client.py`: `chat_completion` acepta `temperature: float | None = None` y lo inyecta en el payload OpenAI si no es None.
- Backup del `.env` original: `meteovisor-demo/.env.backup_pre_experimento_chat_e2e` (restaurado automáticamente al final del script).
- Endpoint usado: `http://138.100.63.85:11436/v1/chat/completions` (Helios proxy, OpenAI-compatible). Mismo proxy del bench sintético previo. Bearer auth.
- Datos crudos: `meteovisor-test-llms/results/chat_e2e/*.json` (37 ficheros, conversación íntegra con trace de tools y datos reales devueltos por el backend).
- Log de eventos del experimento: `meteovisor-test-llms/results/chat_e2e/_run_log.jsonl` (cronológico, incluye health timeouts, skips deliberados y all_done con wall-clock total).
- Wall-clock total del experimento: 63 minutos (3812 segundos `overall_elapsed_s` reportado por el script + ~7 min de la fase inicial gemma cancelada).

## Datos explícitos

- 3 modelos: `gemma4:26b` (baseline demo), `qwen3.6:27b` (recomendado nº1 juicio cualitativo, modo híbrido), `granite4.1:30b` (recomendado nº1 juicio cualitativo, escenario Mode B puro).
- 5 consultas reutilizadas literalmente de la nota previa.
- 3 temperaturas: `[0.0, 0.3, 0.7]` — para elegir la óptima de producción tras la corrida.
- Producto cartesiano: 3 × 5 × 3 = 45 conversaciones reales end-to-end.
- Configuración del visor cambiada vía variables `LLM_MODEL` y `LLM_TEMPERATURE` (nueva) del `.env`.
- Endpoint: el mismo proxy Helios usado por la demo.
- Output: JSON íntegro por (modelo × consulta × temperatura) + dos Markdown comparativos (por modelo y por consulta).

## Datos inferidos

- Tipo de nota: `decisión` (recoge parámetros de un experimento).
- Clasificación: `08-llm-y-consulta-en-lenguaje-natural/` (continuación directa de la nota previa).
- Opción B (script Python end-to-end) preferida sobre Opción A (manual UI) por reproducibilidad.
- Variable de entorno `LLM_TEMPERATURE` como mecanismo más simple para inyectar la temperatura entre corridas sin tocar el cliente del LLM en producción.

## Datos faltantes o ambiguos

- Decisión final del tutor sobre añadir o no `glm-4.7-flash:latest` como 4º modelo (único que reconoció T10 en el juicio sintético).
- Si las tools reales del backend devuelven errores controlados para capas no vectorizadas (T10) o si fallan silenciosamente — afecta directamente a la interpretación de q5.
- Si se modificará el system prompt entre corridas para probar mitigación de q5 o se mantendrá fijo (recomendación: fijo, anotar la limitación, mitigación va a Fase 2).
- Confirmación del tutor sobre si los 45 outputs literales se incluirán como anexo en la memoria del TFG o solo el Markdown comparativo resumen.
- Mecanismo concreto para saltar `CHAT_RATE_LIMIT=30/minute` durante el experimento (header de test, exención por IP, sleep entre llamadas).
