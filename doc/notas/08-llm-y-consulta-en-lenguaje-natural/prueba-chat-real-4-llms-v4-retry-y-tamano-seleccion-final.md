---
id: TFG-20260527-prueba-chat-real-4-llms-v4-retry-y-tamano-seleccion-final
título: "Prueba comparativa chat e2e (v4) — retry x3 y captura de tamaño, selección final del LLM del visor"
tipo: decisión
tags:
  - tfg
  - llm
  - chat
  - benchmark
  - end-to-end
  - meteovisor-demo
  - v4-retry-y-tamano
  - seleccion-modelo
contexto: "Cuarta y última iteración del experimento end-to-end. Las v1 (2026-05-25), v2 (2026-05-26 post-prompt-fix) y v3 (2026-05-26 post Acción #2 orquestador) dejaron una tasa global de éxito entre 35–56% y un patrón de fallos dominado por errores 5xx transitorios del proxy LLM y timeouts en consultas complejas (q4, q5). El v4 NO modifica modelos, prompt ni orquestador: ataca exclusivamente la robustez del bench refactorizando `chat_e2e.py` con timeouts adaptativos por consulta, retry x3 sobre fallos transitorios y captura del tamaño del modelo (fallback /api/tags porque el proxy Helios bloquea /api/ps). El barrido permite por primera vez una comparación justa entre los 4 candidatos sin que fallos de infraestructura sesguen el ranking, y produce la tabla de descarte definitiva sobre la que se basa la elección final del modelo a integrar en el visor (RF-46 a RF-73)."
fuente_existe: true
fuente_tipo: "elaboración propia + experimento real"
fuente_descripción: "elaboración propia: re-ejecución selectiva (sólo los 36 runs fallidos del v3) del barrido end-to-end con scripts `meteovisor-test-llms/chat_e2e.py` (modificado) y `consolidate_chat_e2e.py` (extendido con columnas de tamaño y retries). Los 24 runs OK del v3 se preservaron sin tocar para no perder las respuestas literales que ya estaban documentadas. Continúa TFG-20260526-prueba-chat-real-4-llms-v3-accion2."
fuente_url: ""
autor_o_entidad: "autor del TFG"
fecha_fuente: "2026-05-27 (lanzamiento del barrido v4) / 2026-05-28 (consolidación final)"
licencia_o_copyright: "uso académico del TFG"
condiciones_de_uso: "uso interno del TFG; las 60 respuestas literales (42 nuevas + 18 finales en fallo) están en `meteovisor-test-llms/results/chat_e2e/_comparativa_chat_e2e_por_modelo.md` como evidencia y como input directo para una eventual fase de juicio cualitativo con LLM externo"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar con el responsable del servidor Helios la causa de los 502 'Fallo de red llamando al LLM' que afectan principalmente a gemma4:26b y a q4/q5 complejas. Hipótesis: límite de tiempo del proxy reverso por delante de Ollama (los retries rescatan algunos pero no todos)."
  - "Confirmar con el responsable de Helios si se puede habilitar `/api/ps` en el proxy. Daría VRAM real en lugar del tamaño en disco (que sólo es proxy razonable cuando hay carga completa en GPU)."
  - "Decidir si vale la pena un v5 modificando el orquestador del demo para exponer `usage` (prompt/completion tokens) en la respuesta — los tokens se descartan actualmente en `chat/llm_client.py`. Coste de implementación: parche de ~30 LOC en `llm_client.py` + `orchestrator.py` + `schemas.py` + `router.py`."
  - "Confirmar con el tutor que la elección de `qwen3.6:35b-a3b-q8_0` es defendible aunque ocupe más del doble en disco (38.7 GB Q8_0 frente a ~17.5 GB Q4_K_M de los otros tres) — el trade-off es éxito 93% frente a 46-80%."
---

# Prueba comparativa chat e2e (v4) — retry x3 y captura de tamaño, selección final del LLM del visor

## 1. Contexto y motivación

El experimento chat e2e ha tenido cuatro iteraciones sobre la misma metodología (mismas 5 consultas, mismos 4 modelos, mismo backend BD/Helios):

| Iteración | Fecha | Diferencia clave | OK% global | OK% q5 |
|---|---|---|---|---|
| **v1** | 2026-05-25 mañana | system prompt original (sin REGLA DE BLOQUEO PREVENTIVO) | 13/37 = 35 % | 0/15 = 0 % |
| **v2** | 2026-05-25 tarde | + REGLA DE BLOQUEO PREVENTIVO en el prompt (Acción #1) | 25/45 = 56 % | 3/9 = 33 % |
| **v3** | 2026-05-26 | + detección de bucle en orquestador (Acción #2, código) | 25/60 = 42 % | 4/12 = 33 % |
| **v4** | 2026-05-27 | + retry x3 / timeouts adaptativos / captura de tamaño (sin tocar modelos ni prompt ni orquestador) | **42/60 = 70 %** | **6/12 = 50 %** |

La motivación del v4 era completar el experimento con un dataset comparable entre los 4 modelos. Las v1-v3 mezclaban fallos del modelo (incapaz de encadenar tools, repite, agota iteraciones) con fallos de infraestructura (502 del proxy, ReadTimeout por hilo lento de Ollama), y el 58% de fallos del v3 enmascaraba qué modelo era realmente bueno. Sin retry no se podía distinguir "el modelo no sabe" de "el proxy se cayó a mitad de stream". El v4 separa las dos causas.

## 2. Modelos y consultas (sin cambios respecto a v1-v3)

**4 modelos** — los 3 mejores del ranking cualitativo de la nota TFG-20260519 + el baseline demo:

| # | Modelo | Score juicio cualitativo (v0) | Tamaño en disco | Parámetros / cuantización |
|---|---|---|---|---|
| 1 | `qwen3.6:27b` | 87.82 | 17.42 GB | 27.8B / Q4_K_M |
| 2 | `qwen3.6:35b-a3b-q8_0` | 86.33 | **38.70 GB** | 36.0B / **Q8_0** |
| 3 | `granite4.1:30b` | 82.70 | 17.49 GB | 28.9B / Q4_K_M |
| 4 | `gemma4:26b` | baseline (no en top-5) | 17.99 GB | 25.8B / Q4_K_M |

`qwen3.6:35b-a3b-q8_0` ocupa más del doble que el resto porque usa cuantización Q8_0 frente a Q4_K_M (≈1 byte por peso frente a ≈0.5 byte; ver documentación de cuantización GGUF [llama.cpp](https://github.com/ggerganov/llama.cpp/blob/master/examples/quantize/README.md)).

**5 consultas** — sin cambios desde el v1 (definición en `meteovisor-test-llms/config/queries.yaml`):

| qid | nivel | tool dominante esperada |
|---|---|---|
| q1 | sencilla | `explainTerm("FWI")` |
| q2 | media | `activeFiresNearPopulation(distance_m=2000, population_max=5000)` |
| q3 | media | `queryBurntArea` (argmax temporal) |
| q4 | compleja | cadena: histórico AEMET argmax temperatura → vecino más cercano por habitantes |
| q5 | compleja | multi-capa con rechazo controlado (T10 inundable no ejecutable) |

**3 temperaturas**: 0.0 (con `seed=42` cuando aplicable, no aquí porque va por backend FastAPI), 0.3 y 0.7. Total cells: 4 × 5 × 3 = 60.

## 3. Cambios técnicos del v4 frente al v3

Los cambios están aislados en el bench harness `meteovisor-test-llms/chat_e2e.py` y la consolidación `consolidate_chat_e2e.py`. Ni el orquestador (`meteovisor-demo/chat/orchestrator.py`) ni el system prompt han cambiado.

### 3.1. Timeouts adaptativos por consulta

| Parámetro | v3 | v4 | Justificación |
|---|---|---|---|
| `PER_REQUEST_TIMEOUT` | 300s (fijo) | 600s (q1-q3) / 900s (q4-q5) | El v3 mostró que q4/q5 estaban al límite de 300s en los modelos lentos (gemma4:26b mediana 130s; qwen3.6:35b mediana q5 218s). Subimos el techo de q4-q5 a 900s para diferenciar "modelo lento que llega" de "modelo que de verdad no encadena". |
| `HEALTH_TIMEOUT_SECONDS` | 240s | 480s | El cold-start de modelos 30B+ tras `keep_alive=0` del modelo anterior puede tardar 5-7 min. El v3 perdió 13 cells por health_timeout. |

Referencia del patrón "timeout per operation": [httpx — Timeouts](https://www.python-httpx.org/advanced/#timeout-configuration).

### 3.2. Retry x3 sobre 5xx y ReadTimeout

```python
MAX_QUERY_ATTEMPTS = 3
QUERY_BACKOFF_SECONDS = [5, 15]   # tras intento 1 y 2
```

Una query se reintenta si el resultado es **retriable**: HTTP 5xx (proxy LLM cayó, "Fallo de red llamando al LLM"), error de red sin status (timeout, conexión rechazada). NO se reintenta si es 4xx (error del cliente — no se va a arreglar repitiendo).

Cada reintento usa un `session_id` distinto (`…_a1`, `…_a2`, `…_a3`) para que los logs del backend permitan reconstruir la cadena. El registro de cada run incluye `result.attempts[]` con `(attempt, ok, http_status, error, latency_total_ms)` para que la tabla de descarte pueda decir literalmente "esta query no se completó tras 3 reintentos".

Justificación del patrón retry+backoff exponencial: [AWS Architecture — Error retries and exponential backoff](https://docs.aws.amazon.com/general/latest/gr/api-retries.html) y [Google SRE Book — Handling Overload, "client-side throttling and retry"](https://sre.google/sre-book/handling-overload/). Backoff finito (5s, 15s) elegido porque los 502 observados en v1-v3 eran transitorios (~5-30s); no requería backoff exponencial agresivo.

### 3.3. Retry x2 de cold-start (`MAX_CFG_ATTEMPTS = 2`)

Si el health-check de uvicorn falla (modelo no se carga en 480s o LLM proxy no responde al ping), se mata uvicorn y se reintenta una vez con espera de 10s. Solo si fallan los dos intentos se marca la config entera como `backend_unhealthy_after_retries` y se vuelcan las 5 queries de esa (modelo, T) como fallo persistente. El v3 perdía 5 queries por cada cold-start fallido sin posibilidad de recuperación.

### 3.4. Captura del tamaño del modelo (`get_vram_for_model`)

Intento principal: `GET {Helios}/api/ps` para obtener `size_vram` real. El proxy Helios actual responde 404 a `/api/ps`. Fallback: `GET {Helios}/api/tags` que sí responde y devuelve `size` (bytes en disco) + `details` (`family`, `parameter_size`, `quantization_level`).

El campo `source` del record distingue `"api_ps"` (VRAM real) de `"api_tags_fallback"` (tamaño en disco). Para este barrido todos los runs son `api_tags_fallback`. El tamaño en disco es proxy razonable de VRAM cuando el modelo se carga completamente en GPU; no lo es si hay offload a RAM. Limitación documentada en Sección 7.

Patrón tomado del v0 bench sintético `meteovisor-test-llms/bench.py` (TFG-20260519), que ya hacía el mismo fallback. Documentación oficial del endpoint: [Ollama API — list-running-models](https://github.com/ollama/ollama/blob/main/docs/api.md#list-running-models) y [Ollama API — list-local-models](https://github.com/ollama/ollama/blob/main/docs/api.md#list-local-models).

### 3.5. Skip selectivo: sólo los fallidos del v3

`chat_e2e.py` salta una query existente sólo si su JSON ya tiene `result.ok=True`. Los 24 runs OK del v3 se conservaron intactos (responder literales ya capturadas, no se quería cambiarlas, especialmente en T>0 donde la respuesta no es determinista). Los 36 fallidos se movieron a `meteovisor-test-llms/results/chat_e2e_v3_failed_backup/` como evidencia histórica antes de re-ejecutarlos.

## 4. Parámetros del barrido v4

| Parámetro | Valor |
|---|---|
| Modelos | gemma4:26b, qwen3.6:27b, qwen3.6:35b-a3b-q8_0, granite4.1:30b |
| Consultas | q1-q5 de `config/queries.yaml` |
| Temperaturas | 0.0, 0.3, 0.7 |
| Total cells | 60 (4 × 5 × 3) |
| Cells re-ejecutadas en v4 | 36 (las fallidas del v3) |
| Cells preservadas del v3 OK | 24 |
| `PER_REQUEST_TIMEOUT_SHORT` | 600s (q1-q3) |
| `PER_REQUEST_TIMEOUT_LONG` | 900s (q4-q5) |
| `HEALTH_TIMEOUT_SECONDS` | 480s |
| `MAX_QUERY_ATTEMPTS` | 3 |
| `QUERY_BACKOFF_SECONDS` | [5, 15] |
| `MAX_CFG_ATTEMPTS` | 2 |
| Backend del visor | FastAPI uvicorn 127.0.0.1:8000 (spawn por config) |
| LLM endpoint | `http://138.100.63.85:11436/v1/chat/completions` (proxy Helios → Ollama remoto) |
| Modelo de orquestación | mismo orquestador del demo, max_tool_iterations=8 |
| Fecha lanzamiento | 2026-05-27 12:18 UTC |
| Fecha fin | 2026-05-27 22:30 UTC |
| Duración total | **36682 s ≈ 10 h 11 min** |
| Retries usados (totales) | 41 `query_retry_backoff` |
| Cold-starts fallidos | 0 (todas las configs subieron al primer intento) |

## 5. Métricas capturadas por run

Por cada (modelo, qid, T) se vuelca un JSON `{model_safe}__q{id}__t{T}.json` con:

- `result.ok`, `result.http_status`, `result.latency_total_ms`
- `result.attempts[]`: cadena de los hasta 3 intentos con `(attempt, ok, http_status, error, latency_total_ms)`
- `result.response.reply.iterations`: número de iteraciones LLM (incluye llamadas con tool_calls + llamada final de cierre)
- `result.response.reply.trace[]`: lista de `{tool, arguments, result_summary, ok, error}` por cada tool ejecutada
- `result.response.reply.client_actions[]`: acciones UI emitidas (setVisibleLayers, showGeoJsonResults, etc.)
- `result.response.reply.blocks`: los 4 bloques del formato MeteoVisor (`interpretacion`, `operaciones`, `resultados`, `interpretacion_emergencia`)
- `vram`: `{source, size_vram, size_total, details: {family, parameter_size, quantization_level}, expires_at, note}`
- `cfg_attempts[]`: intentos de levantamiento de uvicorn para esta config
- `per_query_timeout_s`: 600 o 900 según qid

Lo que **no** se captura (limitación reconocida):
- **VRAM real**: proxy Helios bloquea `/api/ps` → usamos tamaño en disco como proxy.
- **Tokens prompt/completion**: el orquestador del demo descarta `usage` del LLM en `chat/llm_client.py`. Para tener tokens habría que parchear el demo.
- **Latencia desglosada (load_ms / prompt_eval_ms / eval_ms)**: sólo disponibles vía `/api/generate` nativo (lo que hace `bench.py` del v0), no vía `/v1/chat/completions` que usa el orquestador.

## 6. Resultados consolidados

Las 60 respuestas literales están en `meteovisor-test-llms/results/chat_e2e/_comparativa_chat_e2e_por_modelo.md` y `_comparativa_chat_e2e_por_consulta.md`. Las tablas siguientes salen de `_aggregates_chat_e2e.md` y `_tabla_descarte_modelos.md`.

### 6.1. Por modelo

| modelo | params/quant | tamaño (GB) | n | ok % | lat media (ms) | lat mediana | iters media | 4-bloques % | tool_calls medias | fallos | retries totales |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `gemma4:26b` | 25.8B/Q4_K_M | 17.99 | 15 | 46 | 131284 | 130558 | 2 | 100 | 1 | 8 | 20 |
| `qwen3.6:27b` | 27.8B/Q4_K_M | 17.42 | 15 | 80 | 107284 | 51071 | 2.17 | 100 | 1.17 | 3 | 7 |
| **`qwen3.6:35b-a3b-q8_0`** | 36.0B/Q8_0 | **38.70** | 15 | **93** | 131581 | 45087 | 2.86 | 100 | 2.36 | **1** | 2 |
| `granite4.1:30b` | 28.9B/Q4_K_M | 17.49 | 15 | 60 | 29893 | 32838 | 2.44 | 100 | 1.44 | 6 | 12 |

### 6.2. Por consulta

| qid | n | ok % | lat media (ms) | iters media | 4-bloques % | tool_calls medias |
|---|---|---|---|---|---|---|
| q1 | 12 | **100** | 74330 | 2 | 100 | 1 |
| q2 | 12 | 75 | 42668 | 2.33 | 100 | 1.33 |
| q3 | 12 | **100** | 53491 | 2.17 | 100 | 1.17 |
| q4 | 12 | **25** | 369269 | 3.33 | 100 | 2.33 |
| q5 | 12 | 50 | 215312 | 3.5 | 100 | 3.67 |

q4 es de lejos la más dura (25% éxito agregado): sólo qwen3.6:35b-a3b-q8_0 la completa con consistencia.

### 6.3. Por temperatura

| T | n | ok % | lat media (ms) | iters media | 4-bloques % |
|---|---|---|---|---|---|
| 0.0 | 20 | 65 | 94272 | 2.46 | 100 |
| 0.3 | 20 | 70 | 147322 | 2.36 | 100 |
| 0.7 | 20 | 75 | 68633 | 2.47 | 100 |

T=0.7 sale mejor en éxito, pero la diferencia (75% vs 65%) está dentro del ruido del experimento (n=20). T no es la variable diferenciadora — el modelo sí.

## 7. Tabla de descarte y selección final

Reproducida de `_tabla_descarte_modelos.md`:

| modelo | tamaño (GB) | runs OK / total | % éxito | lat mediana OK (s) | lat máx OK (s) | iters media | 4-bloques % | consultas no completadas tras 3 reintentos |
|---|---|---|---|---|---|---|---|---|
| `gemma4:26b` | 17.99 | 7/15 | 46 | 130.6 | 195.2 | 2 | 100 | q2@T=0.0, q2@T=0.3, q2@T=0.7, q4@T=0.0, q4@T=0.3, q4@T=0.7, q5@T=0.0, q5@T=0.3 |
| `qwen3.6:27b` | 17.42 | 12/15 | 80 | 51.1 | 682.7 | 2.17 | 100 | q4@T=0.0, q4@T=0.3, q5@T=0.0 |
| **`qwen3.6:35b-a3b-q8_0`** | **38.70** | **14/15** | **93** | 45.1 | 508.8 | 2.86 | 100 | q4@T=0.7 |
| `granite4.1:30b` | 17.49 | 9/15 | 60 | **32.8** | 62.3 | 2.44 | 100 | q4@T=0.0, q4@T=0.3, q4@T=0.7, q5@T=0.0, q5@T=0.3, q5@T=0.7 |

### 7.1. Descartes

- **`gemma4:26b` — descarte fuerte.** 46% de éxito incluso con retry, peor latencia mediana (130s), y falla q2 (que es single-tool, no compleja) en las 3 temperaturas. El backend devuelve 502 reincidente en todos los reintentos: el modelo no funciona estable en este proxy. Es el peor candidato en todos los ejes excepto tamaño (a la par con los Q4).
- **`granite4.1:30b` — descarte por capacidad.** **No completa NINGUNA q4 ni q5 en ninguna T** tras los 3 reintentos. Es funcional sólo para consultas single-tool (q1-q3, donde es el más rápido con 33s mediana). Si el alcance del visor incluye consultas multi-tool encadenadas (RF-46/RF-73), granite no sirve. Si el visor se limitara a consultas simples, granite sería competitivo por latencia.
- **`qwen3.6:27b` — candidato secundario.** 80% éxito, falla las dos q4 más conservadoras (T=0.0, T=0.3) y q5@T=0.0. Completa q4@T=0.7 y q5@T=0.3/0.7. Latencia mediana 51s. Tamaño manejable (17.4 GB). Útil como **fallback** si la VRAM no permite cargar `qwen3.6:35b-a3b-q8_0` concurrente con otros servicios.

### 7.2. Selección final: `qwen3.6:35b-a3b-q8_0`

**Decisión**: integrar `qwen3.6:35b-a3b-q8_0` como modelo LLM por defecto del chat MeteoVisor.

**Justificación**:
- **93% éxito** end-to-end con todas las herramientas reales del visor. Único fallo: q4@T=0.7 (multi-tool extrema, recuperable bajando T).
- Único modelo que **completa q4 y q5** en al menos 2 de 3 temperaturas — son las consultas más cercanas al caso de uso real del visor (cadenas multi-tool con datos AEMET + IGN).
- **iters media 2.86** y **tool_calls media 2.36** — el modelo encadena tools voluntariamente, no se queda en respuestas textuales superficiales.
- **Latencia mediana 45s** — el mejor de los tres modelos viables (qwen3.6:27b 51s, granite4.1:30b 32.8s pero descartado).
- **0 retries necesarios** en la mayoría de las queries — el modelo es estable en este proxy.

**Coste asumido**:
- Tamaño **38.7 GB** en disco (2.2× los otros). Requiere GPU con ≥48 GB de VRAM si se quiere mantener cargado (`keep_alive=-1`). En una A100 80 GB es asumible incluso concurrente con embeddings y otros servicios; en una L4 24 GB no cabe.
- Latencia máxima de 508s en q4 (≈8 min). UX requiere indicador de progreso en el frontend (acción derivada de la nota v3 Sección 8.7 — ya pendiente).

**Plan B**: si Helios no puede mantener 48 GB sostenidos para este modelo, fallback a `qwen3.6:27b @ T=0.7` (80% éxito, 17.4 GB). Aceptar 20% de fallo en q4/q5 y mostrar mensaje de "no he podido resolver esta consulta, prueba reformulando".

## 8. Limitaciones honestas

1. **Tamaño en disco ≠ VRAM real.** El proxy Helios bloquea `/api/ps`. El tamaño en disco correlaciona con VRAM sólo cuando el modelo carga completo en GPU. Para confirmar VRAM real habría que (a) habilitar `/api/ps` en el proxy, o (b) tener acceso SSH al host de Helios y medir con `nvidia-smi` durante el barrido.
2. **Tokens no capturados.** El orquestador del demo descarta `usage` del LLM (`chat/llm_client.py` línea 67-71). Para una comparación rigurosa de coste habría que parchearlo.
3. **Latencia desglosada no capturada.** `/v1/chat/completions` (endpoint OpenAI-compatible) no devuelve `load_ms`/`prompt_eval_ms`/`eval_ms`. El v0 bench (`bench.py`) sí los tiene porque usa `/api/chat` nativo de Ollama.
4. **n=15 por modelo**. Cada (modelo, T) son 5 cells, cada modelo son 15. El experimento es ilustrativo, no estadísticamente potente. Para un IC95 fiable habría que repetir el barrido completo 3-5 veces.
5. **Una sola GPU / un solo proxy.** Los resultados están condicionados al hardware concreto de Helios y a su saturación cuando se ejecutó el barrido (afortunadamente bajo: ningún cold-start falló).
6. **Las temperaturas T=0.3/0.7 no fijan seed.** Las respuestas literales en esas T son una sola muestra; otra ejecución daría texto distinto. El % éxito agregado es robusto a esto (un run que pasa, pasa; el modelo es capaz), pero el contenido literal no.

## 9. Acciones derivadas

1. **Integrar `qwen3.6:35b-a3b-q8_0` como modelo del chat** en `meteovisor-demo/.env` (`LLM_MODEL=qwen3.6:35b-a3b-q8_0`) y validar con tests `chat/tests/test_e2e_*`.
2. **Confirmar capacidad sostenida de VRAM con Helios** antes de declarar la integración estable. Si no hay 48 GB sostenidos, fallback a `qwen3.6:27b`.
3. **Frontend del chat — indicador de progreso de iteraciones**. Pendiente desde nota v3 §8.7. Crítico ahora que la mediana en q4-q5 es de 4-8 min con qwen3.6:35b.
4. **(Opcional, v5) parchear el orquestador del demo para exponer `usage` (tokens prompt/completion)** — habilitaría comparación de coste energético entre modelos.
5. **(Opcional, v5) pedir al admin del proxy Helios habilitar `/api/ps`** — habilitaría VRAM real.
6. **(Opcional, v5) test de re-runs (3-5 repeticiones del barrido) para tener IC95 real del % éxito por modelo**, no sólo una muestra.

## 10. Referencias

- Helios proxy + Ollama remoto (interno del laboratorio, sin URL pública).
- [Ollama API — list-running-models](https://github.com/ollama/ollama/blob/main/docs/api.md#list-running-models) — `/api/ps` y campos `size_vram`/`size_total`/`details`.
- [Ollama API — list-local-models](https://github.com/ollama/ollama/blob/main/docs/api.md#list-local-models) — `/api/tags` fallback.
- [OpenAI — Function Calling](https://platform.openai.com/docs/guides/function-calling) — semántica de `tools` y `tool_calls`.
- [AWS Architecture — Error retries and exponential backoff](https://docs.aws.amazon.com/general/latest/gr/api-retries.html) — justificación del patrón retry+backoff.
- [Google SRE Book — Handling Overload](https://sre.google/sre-book/handling-overload/) — sección sobre client-side throttling y retry.
- [httpx — Timeout configuration](https://www.python-httpx.org/advanced/#timeout-configuration) — patrón de timeout per operation.
- [llama.cpp — Quantize README](https://github.com/ggerganov/llama.cpp/blob/master/examples/quantize/README.md) — diferencias Q4_K_M vs Q8_0 en tamaño y precisión.
- Nota TFG-20260519: bench sintético v0 + ranking cualitativo con Opus 4.7.
- Nota TFG-20260525-prueba-chat-real-3-llms-comparativa-diseno: diseño del experimento e2e.
- Nota TFG-20260526-prueba-chat-real-4-llms-post-prompt-fix: v2 con REGLA DE BLOQUEO PREVENTIVO.
- Nota TFG-20260526-prueba-chat-real-4-llms-v3-accion2: v3 con detección de bucle en orquestador.

## Datos explícitos
- 60 cells totales (4 modelos × 5 consultas × 3 temperaturas).
- 36 cells re-ejecutadas (los fallidos del v3) + 24 cells preservadas del v3 OK.
- Duración total: 36682s ≈ 10h 11min.
- 42 OK / 18 fallos persistentes tras 3 reintentos.
- Timeouts: 600s q1-q3, 900s q4-q5. Health 480s. Retry x3 con backoff [5,15]. Cold-start retry x2.
- Tamaños en disco capturados vía `/api/tags` (fallback porque `/api/ps` da 404 en Helios).
- Modelo seleccionado: `qwen3.6:35b-a3b-q8_0` con 93% éxito.

## Datos inferidos
- Hipótesis de los 502 = límite de tiempo del proxy reverso (no confirmado con admin de Helios).
- Estimación de capacidad necesaria: ≥48 GB VRAM sostenidos para qwen3.6:35b-a3b-q8_0 con keep_alive=-1.
- T=0.7 sale mejor en % éxito, pero la diferencia con T=0.0/0.3 está dentro del ruido del experimento (n=20 por T).

## Datos faltantes o ambiguos
- Causa exacta de los 502 reincidentes en gemma4:26b — pendiente con admin Helios.
- VRAM real ocupada por cada modelo — pendiente de habilitar `/api/ps` o medir con `nvidia-smi`.
- Tokens prompt/completion por consulta — descartados por el orquestador, parche pendiente.
