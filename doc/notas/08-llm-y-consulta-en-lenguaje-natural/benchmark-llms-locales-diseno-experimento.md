---
id: TFG-20260519-benchmark-llms-locales-diseno-experimento
título: "Benchmark comparativo de LLMs locales del servidor Helios — diseño del experimento"
tipo: decisión
tags:
  - tfg
  - llm
  - benchmark
  - tool-calling
  - ollama
  - experimento
  - alcance
contexto: "Documenta los parámetros, modelos, consultas y métricas elegidos para el experimento comparativo de modelos LLM locales que se ejecutará contra el servidor Ollama (proxy Helios) del laboratorio. El experimento alimenta la decisión técnica pendiente identificada en la nota TFG-20260428 (`ideas-operaciones-llm-local-en-visor-meteovisor.md`) sobre qué modelo concreto integrará el visor MeteoVisor para la interfaz conversacional (RF-46 a RF-73). Los resultados se añadirán a esta misma nota cuando el barrido completo se haya ejecutado."
fuente_existe: true
fuente_tipo: "elaboración propia + literatura externa (papers + model cards + documentación oficial)"
fuente_descripción: "elaboración propia para la adaptación al dominio MeteoVisor, apoyada en (a) los model cards oficiales de los 13 modelos evaluados (IBM, Qwen Team, Z.ai, Google DeepMind, OpenAI, Meta — ver Sección 11.6), (b) papers fundacionales de LLM-as-a-judge (Zheng+2023 MT-Bench, Liu+2023 G-Eval) y de sesgos del juez (Panickssery+2024, Li+2025) — ver Sección 11.1-11.2, (c) Berkeley Function-Calling Leaderboard (Patil+2024-2025) como referencia para tool calling — ver Sección 11.3, (d) literatura sobre temperatura y reproducibilidad LLM (Renze+2024, Atil+2024) — ver Sección 11.4, (e) documentación oficial de Ollama para num_ctx — Sección 11.5, y (f) la lista de modelos publicados en el servidor Ollama interno (Helios, http://138.100.63.85:11436), las consultas-ejemplo de `ejemplo-de-prompt-y-consultas-completado.md`, el catálogo de tools y niveles de operación de `ideas-operaciones-llm-local-en-visor-meteovisor.md`, y la conversación de trabajo del 2026-05-19."
fuente_url: "ver Sección 11 — Referencias bibliográficas"
autor_o_entidad: "autor del TFG (diseño y ejecución del experimento); fuentes externas atribuidas en Sección 11"
fecha_fuente: "2026-05-19 / 2026-05-25 (consolidación bibliográfica)"
licencia_o_copyright: "elaboración propia bajo licencia del TFG; fuentes externas bajo sus respectivas licencias (Apache 2.0 para modelos open-weights, CC-BY en mayoría de papers arXiv)"
condiciones_de_uso: "uso académico para el TFG; redistribución de fragmentos de papers/model cards permitida con atribución"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría del experimento (autor del TFG)."
  - "Validar con el tutor la recomendación final reconciliada (Sección 10.7): granite4.1:30b para Mode B puro / qwen3.6:27b para narrativa fiel / glm-4.7-flash si se prioriza rechazo controlado."
  - "Replicar el barrido reducido cuando el catálogo de tools final del visor se cierre."
  - "Enriquecer el system prompt con la enumeración explícita de capas no ejecutables (T10) — confirmado por juicio cualitativo como la mayor debilidad transversal del sistema (q5 limit_handling 1.97/5)."
  - "Decisión opcional Fase 2: calibrar el juez Opus contra evaluación humana (kappa de Cohen sobre subconjunto de ≥30 invocaciones, ≥2 anotadores) según el protocolo de Zheng+2023 si el tribunal lo solicita."
---

# Benchmark comparativo de LLMs locales del servidor Helios — diseño del experimento

## Contenido

Esta nota fija los parámetros del experimento comparativo de los modelos LLM publicados en el servidor Ollama del laboratorio (proxy Helios autenticado en `http://138.100.63.85:11436`). El objetivo es producir evidencia cuantitativa para decidir qué modelo integrará la interfaz conversacional del visor MeteoVisor, comparando simultáneamente **calidad de respuesta**, **latencias**, **tokens consumidos** y **memoria GPU ocupada** en condiciones equivalentes para todos los modelos.

El experimento se materializa en un script Python configurable que lanza un barrido completo del producto cartesiano *modelos × consultas × temperaturas × modos de invocación* y vuelca los resultados en un fichero JSON por modelo (nombre = nombre exacto del modelo en Ollama + timestamp) más un CSV-resumen global comparable directamente en hoja de cálculo.

## 1. Modelos seleccionados

Lista de **13 modelos** resultantes del cribado de la lista completa del servidor (25 modelos), descartando: modelos de embedding (`qwen3-embedding:8b`), fine-tunes privados desconocidos (`rodolfo/novaai:latest`, `gemma-tuned:latest`), modelos demasiado pequeños (`smollm:135m`), especializados que no aplican (`translategemma:27b`, `llama3:8b`, `deepseek-coder:33b`) y, por petición expresa, todos los modelos coder/agentic-código (`qwen3-coder-next:latest`, `qwen3-coder:30b`, `qwen2.5-coder:32b`, `devstral-small-2:24b`, `devstral:latest`).

**Criterio explícito de inclusión** — todos los candidatos cumplen tres requisitos: (i) están publicados en el servidor Ollama del laboratorio (restricción de plataforma del TFG), (ii) son modelos *instruction-tuned* de propósito general — no especializados a un dominio (código, traducción, embedding) — porque la tarea del visor MeteoVisor exige razonamiento + tool calling sobre lenguaje natural en español, y (iii) declaran soporte de *function calling* en su model card oficial o en el adaptador de Ollama (verificable en `/api/chat` con campo `tools`). El criterio (iii) es necesario porque la arquitectura prevista (`ideas-operaciones-llm-local-en-visor-meteovisor.md`, Nivel 3) depende de tool calling estructurado; un modelo que solo emita prosa requeriría un parser ad-hoc que rompe el contrato del backend FastAPI.

### 1.1 Fichas técnicas de los modelos evaluados

Datos extraídos de los model cards oficiales (Hugging Face, ai.google.dev, ibm.com/granite, z.ai, openai.com, meta.ai) y del adaptador de Ollama (`/api/tags` del servidor Helios). Los enlaces a referencias completas están en la Sección 11.

**Gama alta:**

| Modelo | Familia | Params | Quant |
|---|---|---|---|
| `qwen3.6:35b-a3b-q8_0` | qwen3.5-moe | 36B MoE | Q8_0 |
| `qwen3.6:35b` | qwen3.5-moe | 36B MoE | Q4_K_M |
| `qwen3.5:35b` | qwen3.5-moe | 36B MoE | Q4_K_M |
| `qwen3.6:27b` | qwen3.5 dense | 27.8B | Q4_K_M |
| `qwen3.5:27b` | qwen3.5 dense | 27.8B | Q4_K_M |
| `granite4.1:30b` | granite | 28.9B | Q4_K_M |
| `gemma4:31b` | gemma4 | 31.3B | Q4_K_M |
| `gemma4:26b` | gemma4 | 25.8B | Q4_K_M |
| `glm-4.7-flash:latest` | glm4-moe-lite | 29.9B MoE | Q4_K_M |
| `gpt-oss:20b` | gptoss | 20.9B | MXFP4 |

**Gama ligera:**

| Modelo | Params |
|---|---|
| `qwen3:14b` | 14.8B |
| `qwen3:8b` | 8.2B |
| `llama3.1:8b-instruct-q4_K_M` | 8B |

#### Ficha por familia

| Familia | Proveedor | Tool calling oficial | Contexto nativo | Licencia | Arquitectura | Fuente principal |
|---|---|---|---|---|---|---|
| **Granite 4 / 4.1** | IBM Research | **Sí, nativo en chat template** (etiquetas `<tool_call>`, schema OpenAI). Reportado *industry-leading* en BFCL v3 según IBM | Hasta 128K (`granite-4.1-h-small`) | Apache 2.0 | Híbrida Mamba-2 + Transformer; algunas variantes MoE | [Granite 4 announcement, IBM (2025)](https://www.ibm.com/new/announcements/ibm-granite-4-0-hyper-efficient-high-performance-hybrid-models); [HF `ibm-granite/granite-4.1-8b`](https://huggingface.co/ibm-granite/granite-4.1-8b) |
| **Qwen3 / Qwen3.5 / Qwen3.6** (dense + MoE) | Alibaba / Qwen Team | **Sí, nativo** vía `Qwen-Agent` (Function Calling + MCP). Q3-Coder es estado del arte agentic entre modelos abiertos | Hasta 256K (1M con extrapolación) | Apache 2.0 (mayoría) | Dense y MoE (A3B = 3B activos / 36B totales en versiones MoE) | [Qwen-Agent repo](https://github.com/QwenLM/Qwen-Agent); [Qwen3-Coder blog (Qwen, 2025)](https://qwenlm.github.io/blog/qwen3-coder/) |
| **GLM-4.5 / 4.7-flash** | Zhipu AI / Z.ai | **Sí, nativo**. Tool-calling success 90.6 % reportado por Z.ai (superando Claude 4 Sonnet 89.5 %). 76.4 en BFCL-v3 | 128K | Apache 2.0 (pesos abiertos) | MoE hybrid reasoning (modo thinking + non-thinking). GLM-4.5-Air: 106B totales / 12B activos | [GLM-4.5 blog Z.ai](https://z.ai/blog/glm-4.5); [HF `zai-org/GLM-4.5`](https://huggingface.co/zai-org/GLM-4.5) |
| **Gemma 3 / 4** | Google DeepMind | **Sí**, function calling, planificación y razonamiento documentados como componentes "core" de agentes Gemma 3 | 128K en 27B; 32K en variantes menores | Gemma Terms of Use (uso comercial permitido con restricciones) | Decoder-only, multimodal en Gemma 3 | [Gemma 3 Technical Report (arXiv 2503.19786, 2025)](https://arxiv.org/pdf/2503.19786); [HF `google/gemma-3-27b-it`](https://huggingface.co/google/gemma-3-27b-it) |
| **gpt-oss** | OpenAI | **Sí**, requiere formato propietario *Harmony*. Soporta function calling, structured outputs y reasoning levels | 128K | Apache 2.0 | MoE — 3.6B activos sobre 20B totales (gpt-oss:20b) | [Introducing gpt-oss, OpenAI (2025)](https://openai.com/index/introducing-gpt-oss/); [HF `openai/gpt-oss-20b`](https://huggingface.co/openai/gpt-oss-20b) |
| **Llama 3.1** | Meta AI | **Sí, fine-tuned para function calling** (single, parallel, nested, multi-turn). Reportado peor que variantes 70B/405B en formato estricto | 128K | Llama 3.1 Community License | Decoder-only Transformer | [vLLM Tool Calling docs](https://docs.vllm.ai/en/latest/features/tool_calling/); [Meta Llama 3.1 card](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) |

**Notas sobre los nombres en Ollama**: los `:tag` del servidor Helios (p.ej. `qwen3.6:35b-a3b-q8_0`, `granite4.1:30b`) son alias internos del registry local; el campo `details.family` del `/api/tags` (Sección 8.7) permite trazar cada uno a su modelo upstream. La columna "Quant" (Q4_K_M, Q8_0, MXFP4) sigue la nomenclatura de [llama.cpp / GGUF](https://github.com/ggerganov/llama.cpp/blob/master/docs/quantize.md): Q4_K_M es el estándar de la comunidad para inferencia local en GPU 16-24 GB y MXFP4 es el formato nativo de gpt-oss optimizado para hardware OpenAI Triton.

**Trazabilidad descartes razonados**:

- *Modelos coder* (`qwen3-coder-*`, `qwen2.5-coder:32b`, `devstral*`, `deepseek-coder:33b`): pese a tener tool calling muy potente — Qwen3-Coder es estado del arte agentic — están post-entrenados con énfasis en generación de código (Python/Java/JS), no en razonamiento conversacional en español. La narrativa de los 4 bloques del visor (`[Consulta Interpretada]` / `[Operaciones Geoespaciales]` / `[Resultados]` / `[Interpretación para Emergencias]`) no es su caso de uso. Descarte de producto.
- *Fine-tunes desconocidos* (`rodolfo/novaai:latest`, `gemma-tuned:latest`): sin model card pública, sin trazabilidad de datos de entrenamiento; incumple criterio de transparencia para el TFG.
- *Modelos especializados* (`qwen3-embedding:8b` → embeddings, no generación; `translategemma:27b` → traducción; `llama3:8b` → versión anterior dense ya sustituida por `llama3.1:8b-instruct-q4_K_M`): fuera del scope.
- *Modelos demasiado pequeños* (`smollm:135m`): 135 M parámetros no soporta tool calling con un schema de ~30 tools.

## 2. Temperaturas

Tres valores fijos, idénticos para todos los modelos:

| T | Rol | Referencia |
|---|---|---|
| **0.0** | Determinista — referencia para tool-calling y planificación reproducible. Se acompaña de `seed=42` para forzar reproducibilidad. | Renze (2024) recomienda T=0 para tareas de *problem solving* porque maximiza reproducibilidad sin pérdida de exactitud [Renze+2024]. |
| **0.3** | Equilibrada — operación realista del asistente del visor. | Convención de la documentación de OpenAI y Anthropic para *creative writing controlado* / *coherent generation*; coincide con el valor mediano del rango típico [0, 1] reportado en guías de sampling [SurePrompts2026]. |
| **0.7** | Creativa — estresa la narrativa y la coherencia bajo aleatoriedad alta. | Renze (2024) y la guía de muestreo 2026 documentan T≈0.7 como umbral en el que la calidad empieza a degradarse en tareas de razonamiento — ideal para estresar el sistema sin entrar en régimen incoherente [Renze+2024][SurePrompts2026]. |

**Justificación del barrido (no un único valor)**: la literatura de benchmarking [Atil+2024] muestra que incluso a T=0 los LLMs presentan drift entre ejecuciones por *batching*, scheduling y aritmética no asociativa en GPU. Reportar un solo valor de temperatura es metodológicamente insuficiente; el barrido cubre el régimen determinista (T=0 + seed), el operativo realista (T=0.3) y el extremo creativo (T=0.7) para detectar si el ranking de modelos es estable o sensible al hiperparámetro.

**Seed fijo (`seed=42`) solo con T=0**: Ollama acepta `seed` como opción de muestreo. La práctica estándar (documentación oficial OpenAI/`seed` y guías de reproducibilidad LLM 2025) es fijarla con T=0 para *best-effort reproducibility*; a T>0 el seed reduce varianza pero no garantiza repetición exacta entre versiones de runtime [KeywordsAI2025]. El valor `42` no tiene significado técnico — convención cultural ampliamente usada en literatura ML.

Si un modelo ignora el parámetro internamente (caso típico de modelos *reasoning*), se detectará en el análisis al observar respuestas idénticas entre temperaturas. El script registra el valor enviado, no el efectivo.

## 3. Consultas seleccionadas (1 sencilla + 2 medias + 2 complejas)

Todas extraídas o adaptadas del bloque adicional de consultas aportado el 2026-05-19 y de los ejemplos de `ejemplo-de-prompt-y-consultas-completado.md`. La numeración es estable porque los ficheros de salida se indexan por número de consulta.

**Justificación de la distribución 1 sencilla + 2 medias + 2 complejas**: la estratificación por dificultad es práctica estándar en benchmarks de tool calling — la Berkeley Function-Calling Leaderboard (BFCL) [Patil+2024 / 2025] organiza sus 2 000 pares pregunta-función en categorías de complejidad creciente (single, parallel, nested, multi-turn) precisamente porque "los modelos top aciertan las preguntas one-shot pero tropiezan cuando deben recordar contexto, gestionar conversaciones largas o decidir cuándo NO actuar" [BFCL2024]. La proporción 1+2+2 sobrepondera la franja media-compleja (4/5 invocaciones) porque es donde se manifiestan las diferencias entre modelos: en consultas triviales la varianza inter-modelo es baja (confirmado en Sección 10.4: q1 score 92.73, q5 score 63.57). Esta sobreponderación está alineada con el principio de "test cases at varying levels of difficulty" del BFCL paper y con la metodología de Nexus Function Calling Leaderboard, que también clasifica en categorías single / parallel / nested.

| # | Nivel | Consulta | Justificación |
|---|---|---|---|
| **1** | Sencilla (Nivel 2, glosario) | *¿Qué es el FWI?* | Sin cadena de tools — solo `explainTerm("FWI")`. Análoga al ejemplo 5.7 del doc (FRP). Mide narrativa, precisión léxica y respeto al formato de 4 bloques sin necesidad de planificación. |
| **2** | Media (Nivel 3, tool único ya implementado) | *¿Hay algún núcleo de población de menos de 5.000 habitantes a menos de 2 km de distancia de un foco activo?* | Caso 5.9 del doc, marcado `*` por el usuario. Tool gold-standard `activeFiresNearPopulation(distance_m=2000, population_max=5000)`. Mide extracción correcta de parámetros numéricos y selección de la tool exacta. |
| **3** | Media (Nivel 2-3, agregación temporal) | *¿Qué día recopilado en el histórico es en el que hay más superficie de áreas quemadas?* | Agregación sobre `/api/burnt-area/stats/daily`. Mide si el modelo: (a) elige `queryBurntArea` o el endpoint de stats, (b) detecta que es un argmax temporal, (c) no inventa una fecha concreta. |
| **4** | Compleja (Nivel 3, cadena completa ejecutable) | *¿Cuál es el día del histórico en el que se registró un aviso AEMET con temperatura más alta, y cuál es el núcleo de población con más habitantes que estaba más cerca?* | Combina dos sub-consultas: (i) argmax sobre histórico AEMET filtrado a temperaturas máximas, (ii) vecino más cercano ponderado por habitantes sobre núcleos IGN. Mide planificación secuencial y propagación de resultado entre tools. Todas las capas están disponibles en el prototipo. |
| **5** | Compleja (Nivel 3, multi-capa con rechazo controlado) | *¿Qué áreas geográficas que están bajo aviso meteorológico en relación a aguas, lluvias y tormentas, tienen un núcleo de población de menos de 5.000 habitantes a menos de 2 km de una zona inundable? Muéstrame únicamente las capas utilizadas y los resultados en el mapa.* | Multi-capa: avisos AEMET + núcleos IGN + zona inundable T10. La capa T10 se sirve solo como WMS externo sin geometría vectorial local (Sección 2.3 del doc; `crossAlertsFloodT10` documentada como **no ejecutable**). Mide si el modelo reconoce la limitación y devuelve un rechazo controlado o una sub-consulta resoluble, además de emitir acciones de UI (`setVisibleLayers`, `showGeoJsonResults`). |

**Descartadas razonadas**

- *Carretera municipal más cercana al foco más potente de hoy*: su valor analítico (rechazo por capa de carreteras no disponible — Sección 2.3 del doc) se solapa con #5, que ya cubre rechazo controlado además de planificación multi-capa.
- *Focos a <2 km de un núcleo durante el verano de 2025*: su perfil (proximidad histórica) es casi idéntico al de #2 con `date_range`. Duplicarla no aporta señal nueva al benchmark.

## 4. Modos de invocación (ambos)

Para cada combinación (modelo × consulta × temperatura) se ejecutan **dos invocaciones**, capturando dos facetas distintas de la capacidad del modelo:

- **Mode A — narrativa**: sin esquema de tools. El modelo produce los 4 bloques `[Consulta Interpretada]` / `[Operaciones Geoespaciales]` / `[Resultados]` / `[Interpretación para Emergencias]` y menciona las tools en prosa. Coincide con el formato de respuesta que verá el usuario final del visor.
- **Mode B — tool calling nativo**: se pasa el catálogo completo como JSON Schema en el parámetro `tools` de `/api/chat`. *Single-shot*: registramos los `tool_calls` que devuelva la primera respuesta del modelo, sin alimentar resultados intermedios. Mide la capacidad real de planificación estructurada que necesitará el validador previsto en la arquitectura mínima (punto 4 de la nota TFG-20260428).

**Por qué evaluar ambos modos**: la literatura de evaluación de agentes [Latitude2026][ConfidentAI-Agent] distingue explícitamente entre la *evaluación de la respuesta del LLM* (output textual al usuario) y la *evaluación del agente* (trayectoria de acciones, tool selection, argument correctness). Son señales distintas y un modelo puede ser bueno en una y malo en la otra — exactamente el patrón observado en `llama3.1:8b` (93 % tool-correctness, 13 % 4-bloques) y en `granite4.1:30b` (Mode B perfecto, faithfulness 3.43/5 en Mode A). Reducir el barrido a un solo modo habría sesgado la decisión hacia uno de los dos perfiles.

**Por qué single-shot en Mode B**: el BFCL v1-v2 [Patil+2024] usa específicamente evaluación AST (Abstract Syntax Tree) single-shot sobre la primera respuesta del modelo, sin ejecutar las funciones, porque permite escalar a miles de casos sin infrastructure de tools reales y porque "una llamada estructuralmente correcta" es condición necesaria y empíricamente suficiente para validar capacidad de planificación. Multi-turn (BFCL v3+) sí ejecuta funciones, pero exige stubs deterministas para cada tool — fuera de alcance de esta primera fase del experimento. Esta decisión queda alineada con la práctica estándar pre-2024 y se anota como ampliación para Fase 2.

Si un modelo ignora el campo `tools` y responde en prosa, se marca `tool_support: "text-only"` y se procesa la respuesta como texto sin abortar el bucle.

**Total de invocaciones del barrido completo: 13 × 5 × 3 × 2 = 390**.

## 5. Métricas capturadas por invocación

Por cada uno de los 390 puntos del producto cartesiano:

- **Identificación**: `model`, `query_id`, `query_level`, `temperature`, `mode` (`"narrative"` | `"tools"`), `timestamp_iso`, `run_id` (UUID).
- **Latencias** (ns convertidos a ms; campos nativos de Ollama): `total_duration_ms`, `load_duration_ms`, `prompt_eval_duration_ms`, `eval_duration_ms`.
- **Tokens**: `prompt_tokens` (`prompt_eval_count`), `completion_tokens` (`eval_count`), `total_tokens`, `throughput_tps`.
- **GPU / VRAM** (snapshot único por modelo desde `GET /api/ps` justo después del warm-up): `vram_bytes`, `total_size_bytes`, `vram_pct`, `quantization`, `parameter_size`, `context_length`.
- **Respuesta (Mode A)**: `response_text` íntegro, `response_chars`, `response_lines`, `tool_names_mentioned` (extracción por regex sobre el bloque `[Operaciones Geoespaciales]` contra el catálogo cerrado), `has_4_blocks` (bool), `declared_limitation` (bool — detecta frases de rechazo controlado).
- **Respuesta (Mode B)**: `response_text` (cuando lo emite), `tool_calls` íntegros (`{name, arguments_raw, arguments_parsed}`), `tool_calls_count`, `tool_calls_in_catalog` (bool), `tool_calls_schema_valid` (bool), `invalid_tool_names`, `tool_support` ∈ {`native`, `text-only`, `unknown`}.
- **Errores**: `error_kind` ∈ {`null`, `timeout`, `http_4xx`, `http_5xx`, `parse`, `empty`, `no_tool_support`}, `error_message`.
- **Sistema**: `ollama_version`, `proxy_url`, `keep_alive` usado, `seed` (fijo a 42 con T=0.0).

## 6. Diseño del script y persistencia

- **Lenguaje**: Python 3.11+, dependencias mínimas (`httpx`, `pyyaml`, `python-dotenv`, `tenacity`).
- **Ubicación**: `C:\Users\evave\Documents\meteovisor-test-llms\` (directorio dedicado, separado de `meteovisor-demo`). El benchmark no depende del backend FastAPI del visor.
- **Configuración**: YAML (`config/bench.yaml`, `config/queries.yaml`) más copia literal de la Sección 1 del doc de prompt como `config/system_prompt.md` y JSON Schema completo del catálogo en `config/tool_catalog.json`. CLI con `--models`, `--temperatures`, `--queries`, `--modes`, `--out`, `--dry-run`, `--resume`.
- **`num_ctx: 8192`** (`config/bench.yaml`, sección `inference`): el contexto por defecto de Ollama es 4096 tokens [OllamaFAQ], y la documentación oficial recomienda elevarlo *"to 64000 for agents etc"* en escenarios de tool calling con system prompts y schemas extensos. El system prompt de MeteoVisor + el catálogo JSON Schema completo ocupan ~4 400 tokens medidos (`prompt_eval_count` típico, Sección 8.7); 8 192 deja un margen ≥3 700 tokens para la respuesta del modelo (suficiente para los 4 bloques + reasoning trace en consultas complejas, verificado empíricamente en Sección 8). Subir a 64 K habría inflado el KV cache desplazando modelos grandes de VRAM (Ollama documenta degradación 20-50× cuando el KV cache hace offload a CPU RAM [Autodidacts2024]), perjudicando la comparabilidad de latencias.
- **Flujo por modelo (secuencial)**:
  1. Descarga del modelo previo (`POST /api/generate` con `keep_alive: 0`).
  2. Warm-up (`POST /api/generate` con `keep_alive: -1`), captura `load_duration`.
  3. Snapshot VRAM (`GET /api/ps`).
  4. Bucle de 30 invocaciones (5×3×2) con `POST /api/chat`, timeout 180 s, reintentos sobre 5xx.
  5. Descarga del modelo (`keep_alive: 0`).
  6. Volcado del JSON por modelo + append al CSV global.
- **Salida**:
  - Fichero por modelo: `{out_dir}/{model_safe}__{YYYY-MM-DDTHHmmss}.json`. `model_safe` reemplaza `:` y `/` por `_` (Windows no permite `:` en nombres de fichero); el JSON conserva el campo `"model"` con el nombre exacto de Ollama.
  - Resumen global: `{out_dir}/_summary__{YYYY-MM-DDTHHmmss}.csv` con una fila por `(model, query_id, temperature, mode)` y columnas planas (latencias, tokens, VRAM, longitudes, banderas de calidad estructural y de tool-correctness).

## 7. Coste estimado del barrido completo

- **390 invocaciones**. Latencia media estimada 15-40 s en modelos ~30B y 3-8 s en ~8-14B, más ~30-90 s de carga por modelo.
- **Tiempo total estimado**: **90-180 minutos** en una GPU bien dimensionada. El script no requiere supervisión y permite cancelar/reanudar (`--resume`) sin perder lo recogido.

## 8. Resultados del barrido (2026-05-19 / 2026-05-20)

Ejecución completa: **390 invocaciones, 359.6 min de wall-clock (~6 h)** sobre el proxy Helios. **8 timeouts** registrados (180 s), 382 invocaciones útiles. La intermitencia inicial del servidor obligó a añadir un *circuit-breaker* (aborta el barrido tras 6 fallos de conexión consecutivos) y reclasificar errores. El barrido final se ejecutó sin caer en el breaker.

**Limitación de instrumentación**: el API key disponible solo da acceso a la API nativa de Ollama (`/api/chat`, `/api/generate`, `/api/tags`); los endpoints `/api/ps` y `/api/v1/ollama/*` del proxy Helios no son accesibles con bearer. La memoria GPU **`size_vram` real** no se ha podido medir. Como sustituto, el script captura el **tamaño en disco** del modelo desde `/api/tags`, que es un proxy razonable para modelos completamente cargados en VRAM con la cuantización dada. Esta limitación queda documentada en cada JSON (`vram.source: "api_tags_fallback"`).

### 8.1 Tabla agregada por modelo

Ordenada por **`tool_calls_in_catalog` %** descendente y, en empate, por latencia media de Mode B. Latencias en estado estacionario (excluyendo la primera invocación que carga el modelo en memoria).

| Modelo | Tamaño disco (GB) | Errores | A: lat. media (s) | A: tok out medios | A: throughput (tok/s) | A: 4-bloques % | B: lat. media (s) | B: tok out medios | B: throughput (tok/s) | B: tools en catálogo % | B: schema válido % | B: tool_support nativo % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **granite4.1:30b** | 17.5 | 0 | 20.4 | 1 063 | 55.1 | **100.0** | **2.0** | 32 | 54.2 | **100.0** | 100.0 | 100.0 |
| **qwen3.6:35b-a3b-q8_0** | 38.7 | 0 | 32.3 | 3 301 | 110.1 | **100.0** | 10.5 | 950 | 109.5 | **100.0** | 100.0 | 100.0 |
| qwen3.6:27b | 17.4 | 0 | 83.0 | 3 724 | 46.6 | **100.0** | 24.7 | 997 | 46.4 | **100.0** | 100.0 | 100.0 |
| llama3.1:8b | 4.9 | 0 | **2.6** | 382 | **189.4** | 13.3 | **0.9** | 66 | 178.1 | 93.3 | 100.0 | 93.3 |
| qwen3.6:35b | 23.9 | 0 | 28.5 | 3 251 | 124.2 | 100.0 | 14.6 | 1 514 | 123.1 | 93.3 | 100.0 | 93.3 |
| glm-4.7-flash:latest | 19.0 | 0 | 23.2 | 2 524 | 115.7 | 100.0 | 8.8 | 800 | 110.2 | 86.7 | 100.0 | 86.7 |
| qwen3.5:27b | 17.4 | 0 | 37.0 | 1 626 | 46.2 | 100.0 | 13.2 | 476 | 46.1 | 86.7 | 100.0 | 86.7 |
| gemma4:26b | 18.0 | 1 | 72.8 | 2 818 | 43.9 | 78.6 | 59.7 | 733 | 30.1 | 86.7 | 100.0 | 86.7 |
| qwen3.5:35b | 23.9 | 0 | 20.2 | 2 275 | 123.8 | 93.3 | 5.3 | 457 | 123.2 | 80.0 | 100.0 | 80.0 |
| gemma4:31b | 19.9 | 2 | 103.6 | 1 333 | 14.1 | 100.0 | 118.7 | 538 | 6.9 | 80.0 | 100.0 | 80.0 |
| qwen3:8b | 5.2 | 0 | 7.1 | 1 054 | 159.1 | **100.0** | 6.7 | 878 | 148.6 | 66.7 | 100.0 | 66.7 |
| qwen3:14b | 9.3 | 0 | 12.8 | 1 194 | 97.6 | **100.0** | 8.4 | 687 | 93.5 | 60.0 | 100.0 | 60.0 |
| **gpt-oss:20b** | 13.8 | 5 | 14.9 | 2 109 | 190.1 | 69.2 | 15.3 | 1 264 | 187.2 | **8.3** | 100.0 | **16.7** |

`A:` Mode A narrativa. `B:` Mode B tool-calling nativo. Tamaño disco desde `/api/tags`.

### 8.2 Tabla por consulta (todos los modelos agregados)

| #  | Nivel    | Errores | A: lat. media (s) | A: tok out medios | A: 4-bloques % | A: limitación declarada % | B: lat. media (s) | B: tok out medios | B: tools en catálogo % |
|---|---|---|---|---|---|---|---|---|---|
| 1 | sencilla | 0 | 22.7 | 1 614 | 92.3 | 0.0 | 19.8 | 178 | 92.3 |
| 2 | media    | 1 | 35.0 | 1 967 | 86.8 | 0.0 | 13.6 | 546 | 82.1 |
| 3 | media    | 2 | 34.7 | 1 861 | 94.7 | 7.9 | 17.9 | 627 | 92.1 |
| 4 | compleja | 2 | 40.0 | 2 415 | 86.8 | 2.6 | 28.9 | 962 | 76.3 |
| 5 | compleja | 3 | 37.6 | 2 277 | 83.8 | **0.0** | 33.1 | 1 275 | 63.2 |

### 8.3 Tabla por temperatura

| T   | A: lat. media (s) | A: tok out medios | A: 4-bloques % | B: lat. media (s) | B: tools en catálogo % |
|---|---|---|---|---|---|
| 0.0 | 35.9 | 1 924 | 88.7 | 21.6 | **85.5** |
| 0.3 | 30.8 | 1 948 | 92.1 | 22.3 | 80.0 |
| 0.7 | 37.6 | 2 093 | 86.2 | 23.7 | 78.5 |

### 8.4 Observaciones cualitativas

1. **`granite4.1:30b` domina la combinación calidad + eficiencia.** Único modelo con **100 % en las cuatro métricas estructurales** (4-bloques, en-catálogo, schema-válido, soporte nativo) y a la vez el **más rápido en Mode B** (2.0 s media, 32 tokens completion). 0 errores en 30 invocaciones. Granite 4 está específicamente afinado para tool calling y se nota.
2. **`gpt-oss:20b` no es viable para tool-calling estructurado.** Solo 8.3 % de tool_calls dentro del catálogo y 16.7 % `tool_support: native`. En la mayoría de los casos responde texto sin emitir `tool_calls`. Tampoco respeta el formato de 4 bloques con fiabilidad (69.2 %). Además acumula 5 de los 8 errores totales (timeouts). Descarte claro.
3. **`gemma4:31b` y `gemma4:26b` son lentos para Mode B.** 118 s y 59 s respectivamente — un orden de magnitud peor que el resto. Es probable que el adaptador de tool calling de Gemma en Ollama esté generando overhead. Aceptables en calidad (80-86 % tools en catálogo, 78-100 % 4-bloques) pero **inviables por latencia** para asistente interactivo.
4. **Los modelos pequeños (`llama3.1:8b`, `qwen3:8b`) son los más rápidos pero peores en estructura/correctness.**
   - `llama3.1:8b`: el más rápido del lote (0.9 s en Mode B) y razonable en tool calling (93.3 %), pero **falla la estructura narrativa** (solo 13.3 % de respuestas con los 4 bloques). Sirve si el modo de operación final es Mode B puro.
   - `qwen3:8b`: 100 % 4-bloques pero solo 66.7 % en catálogo. Verboso (878 tokens completion en Mode B — probable thinking trace).
5. **La correctness de tool calling cae con la complejidad de la consulta**: 92.3 % en sencilla → 63.2 % en la compleja con rechazo controlado (q5). Esto era esperable.
6. **Hallazgo importante sobre rechazo controlado**: la consulta q5 (multi-capa con T10 no vectorizada, explícitamente diseñada para detectar capacidad de rechazo) tiene **0 % de `declared_limitation`** en Mode A. **Ningún modelo, en ninguna temperatura, reconoce la limitación de la capa T10 en su narrativa.** Esto es coherente con que el system prompt no lista qué capas están en rechazo controlado (solo lo enumera el documento, no el prompt). Es decir: el comportamiento esperado de la Sección 6 del documento de prompt no se observa porque el prompt del visor no es suficientemente específico sobre las capas no ejecutables. **Acción derivada para Fase 2 del TFG**: enumerar explícitamente las capas/tools en estado "no ejecutable" en el system prompt de producción.
7. **Efecto temperatura**: confirma la intuición — la correctness de tool calling cae monotónicamente con T (85.5 % → 80.0 % → 78.5 %). Para el visor en producción, **fijar T=0** en las llamadas de planificación. La narrativa al usuario puede ser opcionalmente T=0.3 para legibilidad.
8. **Mode A vs Mode B en eficiencia**: Mode B es 1.5-15× más rápido que Mode A en casi todos los modelos (menos completion tokens). Excepción: `gpt-oss:20b` (donde Mode B no aporta, ver punto 2) y `gemma4` (donde Mode B es anómalamente lento, punto 3).
9. **Validación del Mode B como modo de evaluación**: en Mode A, **`tool_names_mentioned` por regex sobre el texto es prácticamente cero en todos los modelos**. Es decir, ningún modelo cita los nombres del catálogo en la prosa del bloque `[Operaciones Geoespaciales]` — usan descripciones genéricas como "la API de focos" o "consulta WMS". **El benchmark sin Mode B no habría producido datos útiles de tool-correctness.** Decisión validada empíricamente.

### 8.5 Recomendación final

**Modelo principal recomendado: `granite4.1:30b`**.

Trade-off resuelto:
- **Calidad estructural perfecta** (100 % en las cuatro métricas).
- **Latencia mejor del top-tier** en Mode B (2.0 s vs 5-25 s del resto), gracias a respuestas muy concisas (32 tokens completion media).
- **Tamaño manejable**: 17.5 GB en disco — cabe en una GPU de 24 GB con margen para el contexto.
- **Cero errores** en 30 invocaciones.
- Familia IBM Granite, soporte nativo y estable de tool calling.

**Modelo secundario** (si se necesita más capacidad narrativa o multilingüe): `qwen3.6:35b-a3b-q8_0`. Otro 100 %/100 %/100 % pero pesa 38.7 GB (requiere GPU mayor) y es 5× más lento en Mode B (10.5 s).

**Modelo de fallback ligero** (latencia ultra-baja, hardware limitado): `llama3.1:8b-instruct-q4_K_M`. Solo 4.9 GB, 0.9 s por tool call, 93.3 % de correctness. **Requiere reformular** el system prompt si se quiere obtener narrativa de 4 bloques fiable (hoy solo 13.3 %).

**Descartados**: `gpt-oss:20b` (tool calling roto), `gemma4:31b/26b` (latencia inviable en Mode B).

**Configuración recomendada para producción del visor**:
- Modelo: `granite4.1:30b`.
- Temperatura: `0.0` con `seed` fijo para llamadas de planificación de tools; opcionalmente `0.3` para narrativa al usuario en un segundo turno.
- `num_ctx: 8192` suficiente (prompt + schema completo cabe en ~4 400 tokens; el resto queda para reasoning).
- Mode B (tool-calling nativo) como contrato principal; Mode A como fallback narrativo cuando el modelo no necesite tool calls.

### 8.6 Acciones derivadas para el TFG (Fase 2)

1. **Enriquecer el system prompt** del visor con la lista explícita de tools/capas en "estado no ejecutable" (Sección 6 del documento de prompt). El barrido demuestra que la formulación actual no induce `declared_limitation` cuando procede.
2. Validar `granite4.1:30b` con el catálogo de tools materializado en el backend FastAPI del visor — el benchmark ha medido planificación, no ejecución end-to-end.
3. Replicar el barrido reducido (solo `granite4.1:30b` + `qwen3.6:35b-a3b-q8_0` + `llama3.1:8b`) sobre el catálogo de tools final cuando se cierre, para confirmar que las métricas se mantienen.
4. Considerar una segunda pasada con **LLM-as-judge** sobre los 390 `response_text` para añadir calidad cualitativa cuantificada. Queda fuera de este informe inicial.

### 8.7 Datos crudos

- Ficheros JSON por modelo: `meteovisor-test-llms/results/{model_safe}__{timestamp}.json` (13 ficheros, 30 runs cada uno, response_text y tool_calls íntegros).
- CSV global: `meteovisor-test-llms/results/_summary__2026-05-19T191023.csv` (391 filas con cabecera).
- Hash SHA-256 del system prompt usado: `66c69a45c81c11b5...` (trazado en cada JSON).

## 9. Selección de candidatos para juicio experto cualitativo

Las métricas estructurales de la Sección 8 (`has_4_blocks`, `tool_calls_in_catalog`, `tool_calls_schema_valid`, latencias, errores) son **objetivas pero superficiales**: dicen *si* el modelo produce los 4 bloques y *si* emite tools del catálogo con schema válido, pero no *qué tal* interpreta la consulta, *cómo de fiel* es a los datos disponibles, *si reconoce* limitaciones de capa, o *si su narrativa* es útil para un usuario de emergencias. Para esa lectura cualitativa hace falta un juez con criterio.

**Apoyo bibliográfico al método LLM-as-judge**: el paper fundacional MT-Bench de Zheng et al. (NeurIPS 2023) [Zheng+2023] demostró que GPT-4 actuando como juez alcanza ~80 % de acuerdo con expertos humanos en evaluación de outputs de LLM — el mismo nivel de acuerdo que muestran dos humanos entre sí sobre la misma tarea. G-Eval (Liu et al., EMNLP 2023) [Liu+2023] consolidó la metodología añadiendo *chain-of-thought* y escala Likert 1-5 sobre criterios separados. Ambos son referencia estándar para la evaluación cualitativa de outputs de LLM cuando no existe gold-standard exacto, que es exactamente el caso del visor MeteoVisor: la respuesta correcta a "¿qué día se registró el aviso con T_max más alta?" depende de datos AEMET que el LLM no ha ejecutado, así que la evaluación debe juzgar el *plan* y la *fidelidad*, no comparar contra una respuesta exacta.

### 9.1 Modelos descartados del juicio experto (3)

Excluidos antes del juicio porque la Sección 8 ya cuantifica un motivo suficiente de descarte para producción. Aplicar un juicio cualitativo sobre ellos no cambiaría la decisión.

| Modelo | Motivo medido en CSV | Coste evitado |
|---|---|---|
| `gpt-oss:20b` | Tool calling estructuralmente roto: **8.3 %** `tool_calls_in_catalog`, **16.7 %** `tool_support: native`, **5 timeouts** sobre 30. No tiene sentido valorar narrativa cuando la planificación es inviable. | 30 invocaciones |
| `gemma4:31b` | Latencia outlier en Mode B: **118.7 s** media (10-50× peor que el resto), throughput 6.9 tok/s, 2 timeouts. Inviable como asistente interactivo aunque la narrativa fuera buena. | 30 invocaciones |
| `gemma4:26b` | Mismo patrón menos extremo: **59.7 s** en Mode B, 1 timeout. Inviable por latencia. | 30 invocaciones |

### 9.2 Candidatos al juicio experto (10)

Pasan el filtro cuantitativo y entran en la valoración cualitativa. Total: 10 modelos × 5 consultas × 3 temperaturas × 2 modos = **300 invocaciones a juzgar**.

| # | Modelo | Tool-cat. % | 4-blocks % | Lat. Mode B (s) | Familia | Comentario para el juicio |
|---|---|---|---|---|---|---|
| 1 | `granite4.1:30b` | 100.0 | 100.0 | 2.0 | IBM Granite | Top cuantitativo — ¿la narrativa está a la altura? |
| 2 | `qwen3.6:35b-a3b-q8_0` | 100.0 | 100.0 | 10.5 | Qwen 3.6 MoE (Q8) | Top cuantitativo — máxima cuantización |
| 3 | `qwen3.6:27b` | 100.0 | 100.0 | 24.7 | Qwen 3.6 dense | Perfecto en correctness, lento — ¿calidad justifica el tiempo? |
| 4 | `qwen3.6:35b` | 93.3 | 100.0 | 14.6 | Qwen 3.6 MoE (Q4) | Versión Q4 del #2, prácticamente perfecta |
| 5 | `glm-4.7-flash:latest` | 86.7 | 100.0 | 8.8 | Zhipu GLM 4.7 | Familia distinta, eficiencia interesante |
| 6 | `qwen3.5:27b` | 86.7 | 100.0 | 13.2 | Qwen 3.5 dense | Versión previa de `qwen3.6:27b` |
| 7 | `qwen3.5:35b` | 80.0 | 93.3 | 5.3 | Qwen 3.5 MoE | Versión previa de `qwen3.6:35b-a3b-q8_0` |
| 8 | `qwen3:14b` | 60.0 | 100.0 | 8.4 | Qwen 3 | Borderline en tool catalog |
| 9 | `qwen3:8b` | 66.7 | 100.0 | 6.7 | Qwen 3 | Borderline en tool catalog |
| 10 | `llama3.1:8b-instruct-q4_K_M` | 93.3 | **13.3** | 0.9 | Llama 3.1 | Anómalo: tool calling muy bien, narrativa fatal — el juez resuelve si es viable en Mode B puro |

### 9.3 Sub-selección para juicio Claude Opus 4.7 (5 de los 10)

El **juicio cualitativo profundo** se ejecuta con **Claude Opus 4.7** dentro del cupo de la suscripción Claude Max (la API REST no está incluida en Max según [support.claude.com](https://support.claude.com/en/articles/9876003), por tanto el juicio se hace dentro de sesiones interactivas de Claude Code). El coste en cupo Max es significativo, así que la sub-selección se restringe a **5 modelos representativos** en lugar de los 10 candidatos.

Sub-set propuesto:

| Pos. | Modelo | Por qué entra en el top-5 |
|---|---|---|
| 1 | `granite4.1:30b` | Ganador cuantitativo absoluto. Familia única (IBM Granite). Es el candidato principal a producción y exige juicio cualitativo de respaldo. |
| 2 | `qwen3.6:35b-a3b-q8_0` | Versión más reciente y mejor cuantizada de la familia Qwen MoE. Único Q8 del set — referencia de calidad para la familia. |
| 3 | `qwen3.6:27b` | Versión más reciente y mejor cuantizada de la familia Qwen dense. Complementa al MoE para cubrir las dos arquitecturas de Qwen 3.6. |
| 4 | `glm-4.7-flash:latest` | Única familia GLM (Zhipu) del lote. Aporta diversidad de proveedor frente a IBM y Alibaba; necesario para no sobre-pesar Qwen. |
| 5 | `llama3.1:8b-instruct-q4_K_M` | Único Llama del lote y única banda ligera (8B) — representante de "asistente rápido con narrativa simple". El juez resuelve si su 13.3 % `has_4_blocks` es un problema bloqueante o un detalle menor cuando se opera en Mode B puro. |

**Criterios aplicados (ordenados por peso)**:

1. **Versiones más nuevas de cada familia**: Qwen 3.6 desplaza a Qwen 3.5 (y a Qwen 3); GLM 4.7 es la versión actual; Granite 4.1 y Llama 3.1 son los más recientes en el lote.
2. **Diversidad de familias**: el subset cubre **5 familias distintas** (Granite, Qwen-MoE, Qwen-dense, GLM, Llama). Si se incluyera `qwen3.5:27b` se subiría a 4 modelos Qwen sobre 5 — sesgo de familia que el juicio no resolvería.
3. **Diversidad de tamaños y cuantizaciones**: 8B Q4 (Llama) → 27.8B Q4 (qwen3.6:27b) → 28.9B Q4 (granite) → 29.9B Q4 (glm-flash) → 36B Q8 (qwen3.6 MoE). Cubre la franja real candidata a producción.
4. **Foco en candidatos viables a producción**: los 5 elegidos están todos en la zona de operación realista. Los descartados del top-10 son:
   - `qwen3.6:35b` (Q4): redundante con su versión Q8 (#2 del subset) — misma arquitectura, peor cuantización.
   - `qwen3.5:35b`, `qwen3.5:27b`: versiones anteriores ya sustituidas por sus equivalentes Qwen 3.6.
   - `qwen3:14b`, `qwen3:8b`: tool_calls_in_catalog < 70 % — ya cuantitativamente débiles; añadir juicio cualitativo no cambia el descarte de producción.
5. **Coste Max acotado**: 5 modelos × 30 invocaciones = **150 casos a juzgar** (frente a 300 si se cubriese el top-10). Cabe en el cupo Max de Claude Code sin riesgo de bloqueo por límite.

**Justificación del modelo juez**: Claude Opus 4.7 es el razonador más capaz disponible para el autor del TFG en su suscripción Claude Max y, a fecha de esta nota, el estado-del-arte en juicios cualitativos estructurados (LLM-as-judge). No participa en el conjunto a juzgar — es un juez externo a la familia Ollama, sin sesgo de auto-evaluación que sí existiría si se usara, por ejemplo, `qwen3.6` como juez de otros Qwen. La restricción a 5 modelos respeta los términos de la suscripción Max ([uso interactivo en Claude Code CLI, no consumo programático desde API](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan)).

**Apoyo documental al juez externo**: la literatura reciente identifica dos sesgos relevantes que justifican la decisión de usar un juez de familia distinta a la evaluada:

1. **Self-preference bias** [Panickssery+2024, arXiv 2410.21819]: modelos como GPT-4o y Claude 3.5 Sonnet asignan sistemáticamente puntuaciones más altas a sus propios outputs. Esto descartaría usar cualquier modelo Qwen/Granite/GLM/Llama como juez de su propia familia.
2. **Family bias / preference leakage** [Li+2025, arXiv 2502.01534]: los jueces puntúan más alto a modelos de su misma familia o con relación de herencia (mismo entrenamiento base). Esto invalidaría usar `qwen3.6` como juez de otros Qwen o `glm-4.7-flash` como juez de GLM-Air. Una mitigación recomendada en [Adaline2026] es *cross-model judging*.

Claude Opus 4.7 satisface ambas condiciones de mitigación: (i) familia Anthropic, no aparece en el set evaluado (Qwen/Granite/GLM/Llama), por lo que no hay self-preference posible; (ii) entrenado con datos independientes a Ollama / Hugging Face open-weights, sin relación de inheritance documentada con los modelos del barrido.

**Limitación reconocida**: una validación más estricta sería el método de Zheng+2023 — calibrar el juez Opus contra un subconjunto de invocaciones puntuadas por al menos dos humanos expertos y reportar el coeficiente kappa de Cohen / Spearman. No se realiza en esta primera versión por coste (≥3 evaluadores humanos para 150 casos), pero se anota como ampliación recomendada para Fase 2 si el tribunal del TFG lo solicita.

### 9.4 Rúbrica de juicio (6 ejes, escala 1-5)

Por cada `(modelo, consulta, temperatura, modo)` del sub-set top-5, el juez Claude Opus 4.7 puntúa estos 6 ejes y emite un `final_score` agregado en 0-100:

| Eje | Peso | Pregunta | Fuente del criterio |
|---|---|---|---|
| Tool correctness | 25 % | ¿Eligió la(s) tool(s) correcta(s) del catálogo del bench con argumentos en rango? | [BFCL/Patil+2024-2025] — *tool selection + argument correctness* son las dos métricas centrales del Berkeley Function-Calling Leaderboard. |
| Plan correctness | 20 % | ¿El plan implícito (orden + selección) resolvería la consulta? | [BFCL multi-turn v3+, Patil+2025] — *Multi-Turn Accuracy* solo cuenta una trayectoria como correcta si todas las llamadas coinciden con la referencia; aproximamos esto evaluando el plan implícito. También alineado con *agent trajectory evaluation* [ConfidentAI-Agent]. |
| Faithfulness | 20 % | ¿Cero fabricación de datos, fechas, núcleos, IDs? | [Liu+2023, G-Eval] — *consistency / faithfulness to source* es una de las cuatro dimensiones canónicas de evaluación NLG. Crítico en dominio emergencias: una fecha inventada es peor que un "no lo sé". |
| Limitation handling | 15 % | ¿Reconoce las limitaciones de q3 (cobertura temporal) y q5 (T10 no vectorizada)? | [Zheng+2023] discute *limited reasoning ability* como sesgo del juez; aquí lo invertimos como dimensión a *evaluar en el evaluado*. Específico de MeteoVisor (Sección 6 del documento de prompt y Sección 2.3 del documento de capas), no transferible directamente a otros benchmarks. |
| Format adherence | 10 % | ¿4 bloques canónicos en Mode A? ¿Tool-call-first en Mode B? | [Liu+2023, G-Eval] — *fluency / format compliance*. Específico del contrato de respuesta acordado con el visor (Sección 1 del documento de prompt). |
| Narrative quality | 10 % | ¿Lenguaje claro, sin jerga innecesaria, sin sustituir criterio operativo? | [Zheng+2023, MT-Bench] — *helpfulness + relevance*; [Liu+2023] — *coherence + fluency*. Único eje que captura calidad subjetiva de cara al usuario final. |

**Trazabilidad de los 6 ejes**: la rúbrica es una **adaptación al dominio MeteoVisor** de dos esquemas estándar — el *agent rubric* (tool selection, argument correctness, tool order, state management, recovery, policy adherence, efficiency, task completion) que la literatura de evaluación de agentes consolida [ConfidentAI-Agent][Galtea2026] y las cuatro dimensiones de G-Eval (relevance, coherence, consistency, fluency) [Liu+2023]. La condensación a 6 ejes balancea:

- **Cobertura de las dos facetas** del experimento: tres ejes orientados a tool calling (tool, plan, format en Mode B) + tres orientados a narrativa (faithfulness, format en Mode A, narrative quality).
- **Pesos justificados por riesgo operativo del visor**: tool/plan/faithfulness suman 65 % porque un tool mal elegido o un dato inventado puede llevar a una decisión equivocada en emergencias; format/narrative suman 20 % porque son cosméticos comparados con corrección; limitation handling es 15 % porque la consulta q5 está diseñada específicamente para medirlo y supone el escenario más peligroso ("respuesta plausible pero ejecutada sobre datos no disponibles").
- **Compatibilidad con escala 1-5 estilo G-Eval**: cada eje se puntúa Likert 1-5 (no binario), de forma que el agregado `final_score = (Σ peso_i × score_i / 5) × 100` quede en 0-100 y sea comparable con MT-Bench (que reporta también puntuaciones 0-10/0-100).

**Por qué pesos heterogéneos (no media simple)**: la literatura de rubric-based LLM-as-a-judge [Masood2026][AWS-Nova-Rubric] recomienda explícitamente *weighted multi-criteria* sobre media simple cuando algunas dimensiones son críticas para el dominio. La media simple sería defendible si los seis ejes fueran intercambiables; en MeteoVisor no lo son (fabricar datos en emergencias > usar formato no canónico).

**Por qué no añadir un séptimo eje "latency"**: la latencia se mide objetivamente en Sección 8.1 (en milisegundos desde Ollama), no es subjetiva y mezclarla con los ejes cualitativos confundiría la lectura. Se reconcilia en Sección 10.7 como filtro externo a la rúbrica.

El juez razona sobre el `response_text` y los `tool_calls` íntegros de los JSON de `meteovisor-test-llms/results/`, contrastando contra las consultas de `config/queries.yaml` y el catálogo de tools de `config/tool_catalog.json`. La salida se persiste en un CSV `results/_judge__opus47__{timestamp}.csv` con 150 filas, fusionable con `_summary__*.csv` por `(model, query_id, temperature, mode)`.

### 9.5 Trade-offs aceptados

- **Sin validación cruzada con un juez automático**: no hay coeficiente Pearson/Spearman comparando Opus con un juez Ollama. Se acepta porque Opus 4.7 es referencia externa fuerte y el coste de añadir un segundo juez no compensa para 150 casos.
- **5 modelos no cubren el efecto "versión anterior frente a posterior" dentro del juicio**: para ese análisis se usan las métricas estructurales de la Sección 8 (donde sí están las 4 versiones: qwen3.5 y qwen3.6 de 27B y 35B). El juicio cualitativo no añade valor incremental sobre esa comparación porque las diferencias de versión son típicamente estilísticas, no de comprensión.
- **`gemma4:31b/26b` quedan fuera del juicio aunque su narrativa pudiera ser correcta**: la decisión de exclusión es de producto (latencia), no de calidad. Si el laboratorio actualiza Ollama/Gemma y la latencia se normaliza, conviene reintroducirlos en un barrido futuro.

## 10. Resultados del juicio experto con Claude Opus 4.7 (2026-05-20)

### 10.1 Tabla ejecutiva final — modelos ordenados por preferencia

> **TL;DR** — Combina (a) la calidad cualitativa juzgada por Claude Opus 4.7 sobre 150 invocaciones reales y (b) las métricas estructurales y de latencia de la Sección 8. La preferencia opera bajo el supuesto **"asistente del visor en Mode B principal + narrativa al usuario opcional en Mode A"**.

| Pos. | Modelo | Score juicio (0-100) | Mode B juicio | Mode A juicio | Lat. Mode B (s) | Faithfulness | Disco (GB) | Veredicto operativo |
|---|---|---|---|---|---|---|---|---|
| **🥇 1** | **`qwen3.6:27b`** | **87.8** | 92.4 | **83.2** | 24.7 | **4.73 / 5** | 17.4 | **Mejor calidad cualitativa global**. Faithfulness más alta del lote — el que menos inventa datos. Lento en Mode B pero aceptable. Recomendación principal del juez. |
| **🥈 2** | `qwen3.6:35b-a3b-q8_0` | 86.3 | **94.7** | 77.9 | 10.5 | 4.37 / 5 | 38.7 | **Top Mode B absoluto**. Necesita GPU ≥ 48 GB. Buen balance velocidad/calidad si cabe. |
| **🥉 3** | `granite4.1:30b` | 82.7 | 91.1 | 74.3 | **2.0** | 3.43 / 5 | 17.5 | **Ultra-rápido y disciplinado en tool calls**, pero faithfulness más baja del top-4 — tiende a fabricar datos en Mode A. Mejor para Mode B *puro*. |
| 4 | `glm-4.7-flash:latest` | 81.3 | 92.5 | 70.1 | 8.8 | 3.73 / 5 | 19.0 | Único que **reconoce explícitamente la limitación de T10** en q5. Mode B sólido. Mode A con fabricaciones. |
| 5 | `llama3.1:8b-instruct-q4_K_M` | 63.9 | 69.7 | 58.1 | **0.9** | 3.10 / 5 | **4.9** | **Bimodal**: bueno en intents simples (q1-q3), se rompe en q4-q5. Viable solo para asistente simple en GPU pequeña. |

**Lectura rápida**:
- Si el visor opera **siempre con Mode B activo + narrativa generada por una segunda pasada controlada** → **`qwen3.6:27b`** (1ª) o **`qwen3.6:35b-a3b-q8_0`** (2ª) son las mejores apuestas.
- Si la **latencia es prioritaria** (UX interactiva sub-3s) → **`granite4.1:30b`**, asumiendo que la narrativa al usuario va a un módulo distinto del LLM (templates, post-procesado de tool results).
- Si el visor necesita **rechazo controlado fiable** (q5-like queries) → **`glm-4.7-flash:latest`** es el único que lo hizo bien en el barrido.
- Si la **GPU del despliegue es ligera** (4-8 GB) → **`llama3.1:8b`** es el único viable, restringido a intents simples.

### 10.2 Metodología del juicio

- **Juez**: `claude-opus-4-7` (Claude Opus 4.7), modelo más capaz del autor en suscripción Claude Max. Externo al set de modelos Ollama evaluados → sin sesgo de auto-evaluación ni de familia.
- **Ejecución**: 5 subagentes Opus en paralelo dentro de Claude Code CLI, uno por modelo, cada uno juzga las 30 invocaciones de su modelo (5 consultas × 3 temperaturas × 2 modos). Tiempo wall total: **~3 minutos** para 150 evaluaciones (vs. ~6 h del barrido Ollama). Cada subagente leyó el JSON íntegro con `response_text` y `tool_calls` originales y aplicó la rúbrica.
- **Rúbrica**: 6 ejes en escala 1-5, ponderados:
  - `tool_correctness` 25 % · `plan_correctness` 20 % · `faithfulness` 20 % · `limitation_handling` 15 % · `format_adherence` 10 % · `narrative_quality` 10 %
  - `final_score (0-100) = (0.25·tool + 0.20·plan + 0.20·faith + 0.15·limit + 0.10·format + 0.10·narr) × 20`
- **Salida**: 5 ficheros JSON (`results/_judge__opus47__<model>.json`) con 30 runs scored cada uno + consolidado `results/_judge__opus47__summary.csv` (150 filas).

### 10.3 Tabla detallada por modelo (6 ejes de la rúbrica)

| Modelo | Media global | Mediana | Min | Max | Runs < 50 | Mode A media | Mode B media | tool_corr | plan_corr | faith | limit_hand | format_adh | narr_qual |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3.6:27b | **87.82** | 92.0 | 46.0 | 96.0 | 1 | 83.23 | 92.40 | 4.00 | 4.60 | **4.73** | 4.30 | 5.00 | 3.57 |
| qwen3.6:35b-a3b-q8_0 | 86.33 | 89.5 | 55.0 | 100.0 | 0 | 77.93 | **94.73** | 3.83 | 4.40 | 4.37 | 4.13 | 5.00 | **4.33** |
| granite4.1:30b | 82.70 | 83.0 | 56.0 | 98.0 | 0 | 74.27 | 91.13 | 3.93 | 4.37 | 3.43 | 4.13 | 5.00 | 3.70 |
| glm-4.7-flash:latest | 81.27 | 90.0 | 50.0 | 100.0 | 0 | 70.07 | 92.47 | 3.87 | 4.37 | 3.73 | **4.23** | 4.47 | 3.90 |
| llama3.1:8b | 63.93 | 60.0 | 28.0 | 100.0 | 9 | 58.13 | 69.73 | 2.87 | 3.40 | 3.10 | 3.20 | 4.10 | 3.63 |

### 10.4 Tabla por consulta

| #  | Nivel | Media global | Mode A | Mode B | tool_corr | faith | limit_hand | Runs < 50 |
|---|---|---|---|---|---|---|---|---|
| 1 | sencilla | **92.73** | 87.07 | 98.40 | 4.33 | 4.63 | 4.90 | 0 |
| 2 | media | 85.37 | 76.13 | 94.60 | 3.93 | 3.90 | 4.73 | 0 |
| 3 | media | 80.37 | 69.27 | 91.47 | 3.83 | 3.37 | 4.43 | 2 |
| 4 | compleja | 80.02 | 74.23 | 85.80 | 3.60 | 3.77 | 3.97 | 3 |
| **5** | **compleja** | **63.57** | 56.93 | 70.20 | 2.80 | 3.70 | **1.97** | **5** |

**Hallazgo central**: la consulta de rechazo controlado (q5) sigue siendo el **talón de Aquiles del sistema**. El `limit_handling` promedio cae a **1.97/5** — los modelos siguen sin reconocer que la capa T10 no es vectorizable, incluso con el juez aplicando criterio cualitativo. Confirma cuantitativamente la observación de Sección 8.4 punto 6: el system prompt necesita enumeración explícita de las capas no ejecutables.

### 10.5 Tabla por temperatura

| T | Media global | tool_corr | faith |
|---|---|---|---|
| 0.0 | 80.95 | 3.70 | 3.88 |
| 0.3 | 80.55 | 3.74 | 3.84 |
| 0.7 | 79.73 | 3.66 | 3.90 |

**Efecto temperatura prácticamente plano** (~1 punto entre extremos). La temperatura afecta más a la **selección estructural de tools** (visto en Sección 8.3: 85.5 % → 78.5 %) que a la **calidad cualitativa global** (sólo 80.95 → 79.73). Para producción confirma: `T=0` para planificación, pero la diferencia con T=0.3 es marginal incluso en calidad.

### 10.6 Veredictos cualitativos por modelo (síntesis de los 5 jueces)

**🥇 `qwen3.6:27b`** — *Modelo viable y sólido para el visor. En Mode B es prácticamente perfecto: elige siempre la tool correcta con argumentos exactos (`explainTerm`, `activeFiresNearPopulation`, `queryBurntArea`, `queryAlerts`) y opta sensatamente por `setVisibleLayers` en q5 evitando inventar `crossAlertsFloodT10`. En Mode A respeta el formato de 4 bloques, declara explícitamente que no fabrica datos, y usa placeholders. Debilidades: (i) inventa nombres de tools en la prosa de Mode A en lugar de citar el catálogo, (ii) no reconoce la limitación de T10 como WMS no vectorial en q5, (iii) un fallo de fabricación bajo T=0.7 en la escala de FWI y en T=0.3 en q5. Apto para producción con prompt-engineering que fuerce citar nombres del catálogo y reconocer T10.*

**🥈 `qwen3.6:35b-a3b-q8_0`** — *Modelo viable, con un perfil muy asimétrico. En Mode B es excelente: emite los tool calls correctos del catálogo con args exactos (10/15 perfectos a 100). En Mode A la calidad cae por dos patrones: (1) inventa nombres de tools fuera del catálogo aunque el intent sea correcto, y (2) en q3 fabrica fechas y hectáreas concretas (14-15 julio, 11.820/12.450 ha) y en q5 ignora la limitación T10 presentando cruces como ejecutados. Recomendable usarlo siempre en Mode B con tool catalog explícito.*

**🥉 `granite4.1:30b`** — *Modelo viable para el visor en Mode B (tools), con planificación de tool-calls casi perfecta y determinista entre temperaturas (selecciona correctamente `explainTerm`, `activeFiresNearPopulation`, `queryBurntArea`, `queryAlerts` con argumentos exactos). Debilidades graves en Mode A: fabrica fechas, núcleos y cifras concretas como si hubiera ejecutado consultas, e ignora la limitación crítica de T10 en q5. Recomendación: usarlo como planificador de tools, no como redactor autónomo de resultados.*

**4. `glm-4.7-flash:latest`** — *Modelo VIABLE para el visor en modo tools, con asimetría marcada. En Mode B brilla: emite tool_calls del catálogo con argumentos correctos en todas las consultas, **maneja excelentemente el rechazo controlado de q5** (declara `crossAlertsFloodT10` no ejecutable — único del lote). En Mode A tiende a fabricar datos (fechas, núcleos, temperaturas) violando el single-shot, y usa nombres genéricos en vez del catálogo canónico. Recomendable usarlo con tools activadas; el modo narrativo requiere prompt engineering adicional para suprimir fabricación.*

**5. `llama3.1:8b-instruct-q4_K_M`** — *Modelo BIMODAL. En Mode B, las consultas simples y medias (q1, q2, q3) son sobresalientes (88-100) — emite la tool correcta con args casi exactos. Pero en consultas complejas (q4, q5) el plan se desmorona: usa `getFeatureDetail` con IDs ficticios en vez de `queryAlerts`, confunde inundación con incendios (`firesNearPopulation`), no declara la limitación T10, y en un run pierde el modo nativo y emite el JSON como texto. En Mode A, fabrica fechas, núcleos y cifras sistemáticamente y solo respeta los 4 bloques canónicos en q3. **Viable en Mode B puro para intents simples y de un solo paso**; NO viable para planificación multi-paso ni cuando se requiera narrativa al usuario.*

### 10.7 Reconciliación con la recomendación final (actualiza Sección 8.5)

La Sección 8.5 propuso `granite4.1:30b` como **modelo principal** basándose en métricas estructurales y latencia. El juicio cualitativo de Opus 4.7 introduce un matiz importante:

- **`granite4.1:30b` tiene faithfulness 3.43/5** — la **más baja del top-4**. Fabrica datos en Mode A (fechas, núcleos, cifras) y no reconoce limitaciones críticas (T10). Su disciplina en Mode B sigue siendo perfecta.
- **`qwen3.6:27b` tiene faithfulness 4.73/5** — la **más alta del lote**. Es el único modelo del top-5 que usa placeholders y declara explícitamente que no fabrica datos cuando no ha ejecutado tools. Pero es **12× más lento** en Mode B (24.7 s vs 2.0 s).

**Recomendación final reconciliada** (sobreescribe la 8.5):

| Escenario operativo | Modelo recomendado | Razón |
|---|---|---|
| **Modo Mode B puro** (visor invoca tools y formatea la respuesta del usuario por código, sin pedir narrativa al LLM) | `granite4.1:30b` | Latencia 2 s, tool calling 100 % correcto, faithfulness no aplica (no genera prosa libre). |
| **Modo híbrido Mode B + narrativa al usuario** | `qwen3.6:27b` | Mejor faithfulness del lote, mejor Mode A (83.2), planificación correcta. Asume latencia ~25 s aceptable. |
| **Modo híbrido con GPU grande disponible (≥ 48 GB)** | `qwen3.6:35b-a3b-q8_0` | Top en Mode B (94.7) y narrativa decente (77.9). Q8 = máxima calidad. |
| **Requiere rechazo controlado fiable** | `glm-4.7-flash:latest` | Único que reconoce T10 explícitamente. Considerar como complemento de razonamiento en consultas con limitaciones de capa. |
| **GPU pequeña, intents simples** | `llama3.1:8b` | 4.9 GB, 0.9 s, solo q1-q3. No para multi-paso. |

**Decisión sugerida al tutor**: arrancar Fase 2 del TFG con **`granite4.1:30b` como planificador de tools** y una **segunda llamada a `qwen3.6:27b` o a un módulo de plantillas** para la narrativa al usuario. Esto da la mejor combinación latencia (2 s para el primer turno) + calidad final (faithfulness alta en la respuesta visible). Como alternativa más simple, `qwen3.6:27b` para ambas funciones (un solo modelo en producción, latencia mayor pero aceptable).

### 10.8 Datos crudos del juicio

- Ficheros por modelo: `meteovisor-test-llms/results/_judge__opus47__<model>.json` (5 ficheros, 30 runs cada uno con scores y justificación).
- CSV consolidado: `meteovisor-test-llms/results/_judge__opus47__summary.csv` (150 filas).
- Script de consolidación y agregados: `meteovisor-test-llms/consolidate_judge.py`.
- Juez: `claude-opus-4-7` (Claude Opus 4.7), accedido vía Claude Code CLI con suscripción Claude Max.
- Wall-clock total: ~3 minutos (5 subagentes Opus en paralelo).

## 11. Referencias bibliográficas

Referencias usadas inline en las secciones 1.1, 2, 3, 4, 6 y 9. Agrupadas por tema y ordenadas cronológicamente dentro de cada grupo.

### 11.1 LLM-as-judge — fundamentos metodológicos

- **[Zheng+2023]** Zheng, L. et al. *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*. NeurIPS 2023 Datasets and Benchmarks. arXiv:2306.05685 — <https://arxiv.org/abs/2306.05685>. Demuestra que GPT-4 alcanza ~80 % de acuerdo con expertos humanos, equivalente al inter-rater agreement humano, y caracteriza los sesgos típicos (position, verbosity, self-enhancement, limited reasoning).
- **[Liu+2023]** Liu, Y. et al. *G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment*. EMNLP 2023. <https://aclanthology.org/2023.emnlp-main.153.pdf>. Introduce la rúbrica de cuatro dimensiones (coherence, consistency, fluency, relevance) con escala Likert 1-5 y CoT explícito; base directa de la rúbrica de Sección 9.4.
- **[Masood2026]** Masood, A. *Rubric-Based Evaluations & LLM-as-a-Judge — Methodologies, Biases, and Empirical Validation in Domain-Specific Contexts*. Medium, abril 2026. <https://medium.com/@adnanmasood/rubric-based-evals-llm-as-a-judge-methodologies-and-empirical-validation-in-domain-context-71936b989e80>. Revisión profesional reciente con énfasis en weighted multi-criteria para dominios específicos.
- **[Galtea2026]** Galtea. *LLM as a Judge: The Complete Guide*. 2026. <https://galtea.ai/blog/llm-as-a-judge-the-complete-guide>. Visión panorámica de la metodología.
- **[ConfidentAI-Agent]** Confident AI. *LLM Agent Evaluation: Assessing Tool Use, Task Completion, Agentic Reasoning, and More*. <https://www.confident-ai.com/blog/llm-agent-evaluation-complete-guide>. Establece la distinción entre evaluación de respuesta vs. evaluación de agente (trayectoria), base de la decisión Mode A + Mode B.
- **[AWS-Nova-Rubric]** AWS. *Evaluate generative AI models with an Amazon Nova rubric-based LLM judge on SageMaker AI*. 2026. <https://aws.amazon.com/blogs/machine-learning/evaluate-generative-ai-models-with-an-amazon-nova-rubric-based-llm-judge-on-amazon-sagemaker-ai-part-2/>. Patrón industrial de rubric ponderada.

### 11.2 Sesgos del juez (justifican el juez externo)

- **[Panickssery+2024]** Panickssery, A. et al. *Self-Preference Bias in LLM-as-a-Judge*. arXiv:2410.21819 — <https://arxiv.org/abs/2410.21819>. Cuantifica que GPT-4o y Claude 3.5 Sonnet sobre-puntúan sus propias respuestas.
- **[Li+2025]** Li, D. et al. *Preference Leakage: A Contamination Problem in LLM-as-a-judge*. arXiv:2502.01534 — <https://arxiv.org/pdf/2502.01534>. Identifica family bias / inheritance bias e introduce el concepto de *preference leakage*.
- **[Adaline2026]** Adaline. *LLM-as-a-Judge: Why Frontier Models Fail 50%+ Bias Tests*. 2026. <https://www.adaline.ai/blog/llm-as-a-judge-reliability-bias>. Recomendación de cross-model judging.

### 11.3 Tool calling — benchmarks de referencia

- **[Patil+2024]** Patil, S. et al. *Berkeley Function-Calling Leaderboard (BFCL)* — repositorio y v1-v2. <https://gorilla.cs.berkeley.edu/leaderboard.html>; <https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard>.
- **[Patil+2025]** Patil, S. et al. *The Berkeley Function Calling Leaderboard (BFCL): From Tool Use to Agentic Evaluation of Large Language Models*. ICML 2025 / Proceedings of MLR vol. 267. <https://proceedings.mlr.press/v267/patil25a.html>; preprint OpenReview <https://openreview.net/pdf?id=2GmDdhBdDk>. Justifica AST-based single-shot evaluation y la estratificación por categorías de complejidad.
- **[Databricks2024]** Databricks. *Beyond the Leaderboard: Unpacking Function Calling Evaluation*. <https://www.databricks.com/blog/unpacking-function-calling-eval>. Análisis crítico de BFCL aplicable a benchmarks de tool calling propios.
- **[BFCL2024]** Genspark/BFCL community. *Understanding BFCL and Nexus Tool Use Benchmark*. <https://www.genspark.ai/spark/understanding-bfcl-and-nexus-tool-use-benchmark/6c1dbd78-ddb9-4de9-acd4-7bf33b592ebe>. Resumen pedagógico de niveles de dificultad.

### 11.4 Temperaturas y reproducibilidad

- **[Renze+2024]** Renze, M. & Guven, E. *The Effect of Sampling Temperature on Problem Solving in Large Language Models*. arXiv:2402.05201. <https://arxiv.org/html/2402.05201v2>. Recomienda T=0 para problem-solving sin pérdida de exactitud.
- **[Atil+2024]** Atil, B. et al. *Non-Determinism of "Deterministic" LLM Settings*. arXiv:2408.04667. <https://arxiv.org/html/2408.04667v5>. Demuestra drift incluso a T=0; justifica barrido de temperaturas en vez de un único valor.
- **[KeywordsAI2025]** Keywords AI. *How to get consistent and reproducible LLM outputs in 2025 (OpenAI, Gemini, Claude, vLLM…)*. 2025. <https://www.keywordsai.co/blog/llm_consistency_2025>. Guía operativa de seed + T=0 best-effort.
- **[SurePrompts2026]** SurePrompts. *LLM Temperature and Sampling: The Complete 2026 Reference Guide*. <https://sureprompts.com/blog/llm-temperature-sampling-complete-guide-2026>. Convenciones operativas (T≈0.3 equilibrada, T≈0.7 creativa).

### 11.5 Ollama y contexto

- **[OllamaFAQ]** Ollama. *FAQ — context length*. <https://docs.ollama.com/faq>. Default 4096, recomendación 64000 para agentes, override por `OLLAMA_CONTEXT_LENGTH` o `options.num_ctx`.
- **[Autodidacts2024]** Autodidacts. *How to increase Ollama context length — num_ctx*. <https://www.autodidacts.io/increase-ollama-context-length-num-ctx/>. Documenta el offload KV-cache → CPU RAM y la degradación 20-50× de throughput.

### 11.6 Fichas técnicas de los modelos evaluados

#### Granite 4 / 4.1 (IBM)
- IBM. *Granite 4.0 announcement — Hyper-efficient, High Performance Hybrid Models for Enterprise*. 2025. <https://www.ibm.com/new/announcements/ibm-granite-4-0-hyper-efficient-high-performance-hybrid-models>.
- IBM Granite docs. <https://www.ibm.com/granite/docs/models/granite>.
- HF model card. <https://huggingface.co/ibm-granite/granite-4.1-8b>.
- Ollama library. <https://ollama.com/library/granite4>.

#### Qwen3 / Qwen3.5 / Qwen3.6 (Alibaba)
- Qwen Team. *Qwen3-Coder: Agentic Coding in the World*. <https://qwenlm.github.io/blog/qwen3-coder/>.
- Qwen-Agent repo (Function Calling + MCP). <https://github.com/QwenLM/Qwen-Agent>.
- Qwen-Agent docs. <https://qwen.readthedocs.io/en/latest/framework/qwen_agent.html>.

#### GLM-4.5 / 4.7 (Z.ai / Zhipu)
- Z.ai. *GLM-4.5: Reasoning, Coding, and Agentic Abilities*. <https://z.ai/blog/glm-4.5>.
- HF model card. <https://huggingface.co/zai-org/GLM-4.5>.
- Z.ai docs. <https://docs.z.ai/guides/llm/glm-4.5>.

#### Gemma 3 / 4 (Google DeepMind)
- Gemma Team. *Gemma 3 Technical Report*. arXiv:2503.19786, marzo 2025. <https://arxiv.org/pdf/2503.19786>.
- Google blog. *Gemma 3: Google's new open model based on Gemini 2.0*. <https://blog.google/technology/developers/gemma-3/>.
- HF model card. <https://huggingface.co/google/gemma-3-27b-it>.

#### gpt-oss (OpenAI)
- OpenAI. *Introducing gpt-oss*. 2025. <https://openai.com/index/introducing-gpt-oss/>.
- HF model card. <https://huggingface.co/openai/gpt-oss-20b>.
- Repo + Harmony format. <https://github.com/openai/gpt-oss>.

#### Llama 3.1 (Meta)
- Meta. *Llama 3.1 model card*. <https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct>.
- vLLM docs — *Tool Calling*. <https://docs.vllm.ai/en/latest/features/tool_calling/>. Reporta soporte single/parallel/nested/multi-turn y caveat sobre fiabilidad de la variante 8B.

### 11.7 Evaluación de agentes vs. evaluación de LLMs

- **[Latitude2026]** Latitude. *Agent Evaluation vs. LLM Evaluation: Why Traditional Tools Fall Short*. 2026. <https://latitude.so/blog/agent-evaluation-vs-llm-evaluation-traditional-tools-fall-short-2026>. Justifica la separación Mode A / Mode B.

## Datos explícitos

- 13 modelos seleccionados por el usuario tras dos pasadas de cribado (descarte de embeddings, fine-tunes desconocidos, traducción especializada, modelos demasiado pequeños y modelos coder).
- 3 temperaturas fijas: 0.0, 0.3, 0.7.
- 5 consultas seleccionadas con criterio 1 sencilla + 2 medias + 2 complejas.
- Métricas pedidas: calidad de respuesta, tiempos, tokens entrada/salida, memoria GPU ocupada.
- Output configurable; nombre de fichero = nombre exacto del modelo Ollama + timestamp.
- Servidor Ollama: `http://138.100.63.85:11436` (proxy Helios, autenticado por bearer token).
- Modo elegido: ambos (narrativa + tool-calling nativo).

## Datos inferidos

- Tipo de nota: `decisión` (recoge parámetros adoptados para un experimento específico).
- Clasificación temática: `08-llm-y-consulta-en-lenguaje-natural/` (encaja con la nota TFG-20260428 a la que esta da continuidad).
- Reemplazo de `:` por `_` en nombres de fichero por restricción de Windows (`model_safe`).
- Seed `42` con T=0 para forzar reproducibilidad sin alterar el resto del barrido.

## Datos faltantes o ambiguos

- Hardware concreto de la GPU donde se ejecuta Ollama (afecta a la interpretación de las latencias). Nota: no se ha podido medir VRAM real (`/api/ps` no accesible con el bearer disponible) — se usa tamaño en disco de `/api/tags` como proxy (Sección 8 limitación de instrumentación).
- Confirmación de tutor sobre alcance del experimento de cara al tribunal y sobre si exige calibración humana del juez Opus (Zheng+2023 protocol).
- Versión exacta de Ollama del servidor Helios en la fecha del barrido (`ollama_version` queda registrada en cada JSON pero no se ha consolidado a la nota).
- Convergencia: el campo `details.family` del `/api/tags` para `qwen3.6:35b-a3b-q8_0` reporta `qwen35moe` (no `qwen36moe`); pendiente confirmar si es un alias del registry local o una imprecisión del adaptador Ollama. No afecta a las conclusiones del experimento.
