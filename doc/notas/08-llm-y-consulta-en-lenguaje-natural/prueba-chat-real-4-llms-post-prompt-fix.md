---
id: TFG-20260526-prueba-chat-real-4-llms-post-prompt-fix
título: "Prueba comparativa chat e2e (v2) — 4 LLMs sobre el chat real del visor tras enriquecimiento del system prompt"
tipo: decisión
tags:
  - tfg
  - llm
  - chat
  - benchmark
  - end-to-end
  - meteovisor-demo
  - v2-post-prompt-fix
contexto: "Segunda iteración del experimento end-to-end documentado en TFG-20260525-prueba-chat-real-3-llms-comparativa-diseno. La iteración previa (v1, 37 conversaciones) reveló que el system prompt no inducía rechazo controlado en la consulta q5 (multi-capa con T10 no vectorial): 0/15 q5 OK en los 3 modelos. La acción derivada nº1 de su Sección 8.7 era enriquecer el prompt con una REGLA DE BLOQUEO PREVENTIVO que enumerase explícitamente los patrones no ejecutables. Esa regla se materializó en el commit eb68b18 (meteovisor-demo, 2026-05-25) junto con el soporte de la nueva tool queryRoadsNearPoint (commit 71563f6). Esta nota documenta la re-ejecución del experimento contra ese prompt nuevo, ampliando además el set a 4 modelos (los 3 mejores del ranking cualitativo del juicio Opus 4.7 + el modelo desplegado actualmente en la demo)."
fuente_existe: true
fuente_tipo: "elaboración propia + experimento real"
fuente_descripción: "elaboración propia: re-ejecución completa del experimento chat e2e (3 modelos × 5 consultas × 3 temperaturas + 6 cells parciales de gemma) tras aplicar las mejoras al system prompt. Continuación operativa de las notas TFG-20260519-benchmark-llms-locales-diseno-experimento (bench sintético previo + juicio cualitativo) y TFG-20260525-prueba-chat-real-3-llms-comparativa-diseno (v1 del chat e2e)."
fuente_url: ""
autor_o_entidad: "autor del TFG"
fecha_fuente: "2026-05-25 (ejecución) / 2026-05-26 (consolidación y redacción)"
licencia_o_copyright: "uso académico del TFG"
condiciones_de_uso: "uso interno del TFG; respuestas literales del LLM se incluyen como evidencia experimental"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Investigar y arreglar el bug intermitente del spawn de uvicorn (2 cycles perdidos por health_timeout en este v2: qwen3.6:27b T=0.3 y qwen3.6:35b-a3b-q8_0 T=0.7). Probable file handle leak o race condition entre kill+restart de subprocesos. Re-ejecutar SOLO esos 10 cells perdidos cuando se arregle."
  - "Confirmar con el tutor que la mejora parcial observada (0/15 → 3/9 OK en q5; primer q4 OK del experimento) justifica adoptar granite como modelo principal pese a su tozudez en q5."
  - "Probar la REGLA DE BLOQUEO PREVENTIVO con un prompt aún más imperativo para granite (que la ignora a las 3 temperaturas)."
---

# Prueba comparativa chat e2e (v2) — 4 LLMs sobre el chat real del visor tras enriquecimiento del system prompt

## 1. Contexto y motivación

La nota previa de chat e2e (`prueba-chat-real-3-llms-comparativa-diseno.md`, Sección 8) identificó dos patologías sistémicas:

1. **q5 (multi-capa con T10) falla en TODOS los modelos** — 0/15 cells OK. El system prompt no instruía al LLM a reconocer T10 como capa no vectorial.
2. **q4 (cadena AEMET argmax → nearest núcleo) también falla en TODOS los modelos** — 0/15 cells OK por timeout de iteraciones.

La Sección 8.7 derivó dos acciones de máxima prioridad:

- **Acción #1 (🔴 ALTA)**: enriquecer el system prompt con la enumeración explícita de capas no ejecutables (T10) y formato de respuesta cuando una sub-consulta no se puede resolver. Aplicada el 2026-05-25 en los commits:
  - `71563f6`: integración de `queryRoadsNearPoint` y capa `roads` en el catálogo del LLM.
  - `eb68b18`: REGLA DE BLOQUEO PREVENTIVO en `chat/prompt.py`, con tres patrones (B1: cruce T10 + alerts + nucleos no ejecutable; B2: EFFIS/protegidos/series no disponibles; B3: consultas predictivas rechazo absoluto).
- Acción #2 (🔴 ALTA, **PENDIENTE**): detección de bucle de tool calls en el orquestador para mitigar q4.

Esta nota documenta la **re-ejecución end-to-end** contra el prompt mejorado, validando empíricamente si la Acción #1 mueve la aguja en q4 y q5.

## 2. Modelos seleccionados (4)

Ampliación del set respecto al v1 (que tenía 3 modelos: gemma + qwen3.6:27b + granite4.1:30b). Aquí entran los **3 primeros del ranking cualitativo** de la nota sintética previa (Sección 10.1) + el **baseline gemma demo**:

| # | Modelo | Por qué entra | Score juicio cualitativo (v0) |
|---|---|---|---|
| 1 | `qwen3.6:27b` | #1 ranking cualitativo, faithfulness 4.73/5 (la más alta del lote) | 87.82 |
| 2 | `qwen3.6:35b-a3b-q8_0` | #2 ranking, top en Mode B (94.73), Q8 cuantización (máxima calidad) | 86.33 |
| 3 | `granite4.1:30b` | #3 ranking, **#1 en latencia** (2.0 s Mode B), disciplina estructural perfecta | 82.70 |
| 4 | `gemma4:26b` | **Baseline demo actual** (en producción se sirve sobre vLLM como `google/gemma-4-26B-A4B-it`). Comparativa de referencia | (no en top-5 juicio) |

**Diferencia clave con el v1**: se añade `qwen3.6:35b-a3b-q8_0` como modelo nuevo nunca probado end-to-end, y se confirma la decisión sobre los tres viables (qwen, qwen35b, granite) vs el baseline gemma.

## 3. Consultas (5)

**Sin cambios respecto al v1 y al bench sintético**: las mismas 5 consultas de `meteovisor-test-llms/config/queries.yaml`. Numeración estable.

1. **q1 (sencilla, glosario)**: *¿Qué es el FWI?*
2. **q2 (media, tool único)**: *¿Hay algún núcleo de población de menos de 5.000 habitantes a menos de 2 km de distancia de un foco activo?*
3. **q3 (media, agregación temporal)**: *¿Qué día recopilado en el histórico es en el que hay más superficie de áreas quemadas?*
4. **q4 (compleja, cadena completa)**: *¿Cuál es el día del histórico en el que se registró un aviso AEMET con temperatura más alta, y cuál es el núcleo de población con más habitantes que estaba más cerca?*
5. **q5 (compleja, multi-capa con rechazo controlado)**: *¿Qué áreas geográficas que están bajo aviso meteorológico en relación a aguas, lluvias y tormentas, tienen un núcleo de población de menos de 5.000 habitantes a menos de 2 km de una zona inundable? Muéstrame únicamente las capas utilizadas y los resultados en el mapa.*

## 4. Metodología — qué cambia respecto al v1

| Dimensión | v1 (2026-05-25 mañana) | v2 (2026-05-25 tarde) |
|---|---|---|
| System prompt | Original (sin REGLA DE BLOQUEO PREVENTIVO, sin queryRoadsNearPoint) | **Nuevo** — commits `71563f6` + `eb68b18` aplicados |
| Tamaño prompt | ~9700 chars | ~13100 chars (+35%) |
| Modelos | 3 (gemma, qwen3.6:27b, granite4.1:30b) | 4 (los 3 anteriores + qwen3.6:35b-a3b-q8_0) |
| Temperaturas | [0.0, 0.3, 0.7] | [0.0, 0.3, 0.7] (sin cambios) |
| Producto cartesiano objetivo | 4×5×3 = 60 | 4×5×3 = 60 |
| Total cells ejecutados | 37 (gemma se canceló parcialmente) | 51 (6 gemma + 45 cells del resto) |
| Patches del backend | Soporte `LLM_TEMPERATURE` ya aplicado (commit `d5dbee1`) | Adicionalmente patches `71563f6` + `eb68b18` |
| Resto: BD PostGIS, script, infra, .env | Idénticos | Idénticos |

**Resto del setup operativo invariante**:
- Endpoint: `http://138.100.63.85:11436/v1/chat/completions` (proxy Helios, OpenAI-compatible).
- BD PostGIS poblada con datos AEMET histórico (70 993 features), FIRMS histórico (49 409 puntos), Burnt Area v4 (123 días), núcleos IGN.
- Script `chat_e2e.py` con resume por fichero, timeouts (`LLM_REQUEST_TIMEOUT=180s`, `PER_REQUEST_TIMEOUT=300s`), restore automático del `.env`.

**Wall-clock total v2**: 4981 s (≈ **83 minutos**) sobre los 45 cells "limpios" + ~10 min de gemma cancelado = ~93 min totales.

## 5. Resultados

### 5.1 Tabla agregada por modelo

| Modelo | n | OK | OK % | Lat. media (ms) | Lat. mediana (ms) | Iters media | Tool calls media | Errores |
|---|---|---|---|---|---|---|---|---|
| `gemma4:26b` (parcial) | 6 | 0 | **0** | — | — | — | — | 6 |
| `qwen3.6:27b` | 15† | 8 | 53 | 63 738 | 61 756 | 2.38 | 1.38 | 7 |
| `qwen3.6:35b-a3b-q8_0` | 15† | 8 | 53 | 73 866 | 34 908 | 2.38 | 2.00 | 7 |
| `granite4.1:30b` | 15 | 9 | **60** | **24 133** | **14 723** | 2.67 | 1.67 | 6 |

† Ambos qwen perdieron 1 cycle entero por health_timeout intermitente del spawn de uvicorn (qwen3.6:27b T=0.3 y qwen3.6:35b-a3b-q8_0 T=0.7). Cells válidos efectivos: qwen3.6:27b 8/10 (80 %), qwen3.6:35b-a3b-q8_0 8/10 (80 %). Granite completo 9/15 = 60 %.

**Observaciones**:
- **Granite sigue siendo el más rápido** (mediana 15 s, en línea con la nota previa Sección 8.1 v1: 14.6 s).
- **qwen3.6:35b-a3b-q8_0 es competitivo en mediana** (35 s) pero su media (74 s) está inflada por los q5 OK que tardaron 195-205 s (cadenas largas de queryAlerts + setVisibleLayers).
- **Gemma colapsa**: 0/6 OK en la fase parcial (T=0 completo + q1 T=0.3). Peor que el v1 (que dio 1/15). El prompt más grande (+35 %) empuja a gemma sobre el `LLM_REQUEST_TIMEOUT=180 s` incluso en q1. Tras 3 timeouts consecutivos, el proxy nginx de Helios entra en **circuit-breaker** y devuelve 502 inmediato a las siguientes peticiones (errores "All connection attempts failed" en q4 y q5 a 22 s). Confirmación operativa del diagnóstico de Sección 8.5 v1: **Gemma + adaptador tool calling de Ollama no es viable**; la demo en vLLM funciona porque vLLM tiene un adaptador específico para Gemma mucho más eficiente.

### 5.2 Tabla por consulta (todos los modelos agregados, incluyendo gemma)

| qid | Nivel | n | OK | OK % | Lat. media (ms) | Iters media | Tool calls media | Observación |
|---|---|---|---|---|---|---|---|---|
| q1 | sencilla | 11 | 7 | 64 | 43 629 | 2.00 | 1.00 | Gemma falla q1 a las 3 T (1 cell ejecutado en gemma T=0.3 antes de saltar; 5 más backend_unhealthy). |
| q2 | media | 10 | 7 | 70 | 43 315 | 2.71 | 1.71 | `activeFiresNearPopulation` con args correctos en qwen+qwen35b+granite. |
| q3 | media | 10 | 7 | 70 | 19 764 | 2.71 | 1.86 | Argmax temporal sobre burnt_area diaria. La más rápida del lote (mediana). |
| **q4** | **compleja** | **10** | **1** | **10** | 107 088 | 3.00 | 2.00 | ✅ **PRIMER q4 OK end-to-end** del experimento (v1+v2): qwen3.6:27b T=0.7 en 107 s. Ver Sección 6.1. |
| **q5** | **compleja** | **10** | **3** | **30** | 154 663 | 2.33 | 2.67 | ✅ **PRIMERA APARICIÓN DE q5 OK** del experimento (v1+v2): 3 cells. Todos modelos qwen (qwen3.6:27b T=0.7, qwen3.6:35b-a3b-q8_0 T=0 y T=0.3). Ver Sección 6.2. |

**Comparativa frente a v1 — el dato central de la nota**:

| qid | v1 OK % | v2 OK % | Delta | Interpretación |
|---|---|---|---|---|
| q1 | 75 (6/8) | 64 (7/11) | -11 pts | Aparente regresión causada por incluir gemma fallando q1 con el prompt nuevo. Si se excluye gemma: v2 q1 = 7/7 = 100 % en modelos viables. |
| q2 | 62 (5/8) | 70 (7/10) | +8 pts | Sin cambio cualitativo (tools/args idénticos). |
| q3 | 71 (5/7) | 70 (7/10) | +0 pts | Sin cambio cualitativo. |
| **q4** | **0 (0/7)** | **10 (1/10)** | **+10 pts** | ✅ Primer cell exitoso. Causa: T=0.7 + cadena 2 tools cortas + prompt más imperativo permiten cerrar en 3 iters. |
| **q5** | **0 (0/7)** | **30 (3/10)** | **+30 pts** | ✅ **La REGLA DE BLOQUEO PREVENTIVO funciona en qwen**. 3 cells exitosos con respuesta exactamente del estilo prescrito (setVisibleLayers + declaración explícita de limitación T10). Ver Sección 6.2. |

### 5.3 Tabla por temperatura

| T | n | OK | OK % | Lat. media (ms) | Iters media |
|---|---|---|---|---|---|
| 0.0 | 20 | 10 | 50 | 63 723 | 2.40 |
| 0.3 | 16 | 7 | 44 | 45 837 | 2.57 |
| 0.7 | 15 | 8 | 53 | 44 993 | 2.50 |

**Observación nueva**: T=0.7 no es peor que T=0 en este experimento — al revés, T=0.7 produjo el único q4 OK y un cell q5 OK adicional. Esto contradice ligeramente la regla operativa "fijar T=0 para producción" derivada del bench sintético. Hipótesis: a T alta el modelo es más exploratorio y menos "tozudo" insistiendo en una cadena que no puede completar, lo que ayuda en consultas con rechazo. Ojo: las muestras son pequeñas (n=15-20 por T).

### 5.4 Comparación v1 ↔ v2 por modelo y query (cells comparables qwen+granite)

| Modelo / qid | v1 (OK?) | v2 (OK?) | Comentario |
|---|---|---|---|
| qwen3.6:27b q1 T=0/0.3/0.7 | OK / OK / OK | OK / — / OK | T=0.3 perdido por health_timeout en v2 (no comparable). |
| qwen3.6:27b q4 T=0/0.3/0.7 | FAIL / FAIL / FAIL | FAIL / — / **OK** | T=0.7 mejora gracias al nuevo prompt. |
| qwen3.6:27b q5 T=0/0.3/0.7 | FAIL / FAIL / FAIL | FAIL / — / **OK** | T=0.7 mejora gracias a REGLA DE BLOQUEO PREVENTIVO. |
| granite4.1:30b q1-q3 T=0/0.3/0.7 | OK (todos) | OK (todos) | Granite mantiene su disciplina en consultas simples y medias. |
| granite4.1:30b q4 T=0/0.3/0.7 | FAIL / FAIL / FAIL | FAIL / FAIL / FAIL | **Sin mejora**. La cadena multi-step sigue agotando iteraciones en granite. |
| granite4.1:30b q5 T=0/0.3/0.7 | FAIL / FAIL / FAIL | FAIL / FAIL / FAIL | **Sin mejora**. Granite NO reconoce T10 a ninguna T pese a la REGLA. Ver Sección 6.3. |

**Resultado central**: la REGLA DE BLOQUEO PREVENTIVO es eficaz en **qwen** (especialmente qwen3.6:35b-a3b-q8_0, que la aplica a T=0 y T=0.3) pero **ineficaz en granite** a las 3 temperaturas. Es un hallazgo importante para la decisión de modelo de producción.

## 6. Observaciones cualitativas (de los outputs literales del chat real)

### 6.1 Primer q4 exitoso end-to-end — `qwen3.6:27b` T=0.7 (107 s, 3 iters)

Cadena de tools ejecutada (extracto del JSON real):

```
1. queryAemetMaxTempHistory({}) -> peak_day = "2025-08-12", max_temp = 45.0°C
2. aemetWarningsNearPopulation({
     "date": "2025-08-12",
     "nucleo_strategy": "most_populated",
     "warnings_only": true,
     "limit": 1
   }) -> Vegas del Guadiana (Extremadura), nivel Rojo, núcleo: Badajoz (124 523 hab.)
```

Respuesta final (bloque `[Resultados]`):

> Día pico: **12 de agosto de 2025**. Temperatura máxima registrada: **45.0 °C**. Zona más afectada: **Vegas del Guadiana (Extremadura)**, bajo aviso **Rojo** (nivel máximo). Núcleo de población más importante: **Badajoz**, con **124 523 habitantes**, situado dentro de la zona del aviso.

Y bloque `[Interpretación para Emergencias]`:

> El 12 de agosto de 2025 marcó el techo térmico del histórico analizado, con avisos rojos por temperaturas extremas en el suroeste peninsular. La capital extremeña, Badajoz, fue el núcleo urbano de mayor entidad expuesto directamente a estas condiciones críticas, lo que implica un riesgo muy elevado [...].

**Valoración**: respuesta operativamente perfecta. Eligió la `nucleo_strategy="most_populated"` correcta (como instruye el ejemplo del prompt del visor), encadenó las dos tools con el resultado de la primera como input de la segunda, y produjo narrativa fiel sobre datos reales devueltos por el backend (Badajoz, 124 523 hab. — dato exacto de la BD IGN).

### 6.2 Los 3 q5 exitosos — la REGLA DE BLOQUEO PREVENTIVO en acción

**Caso A** — `qwen3.6:27b` T=0.7 (63 s, 2 iters):

Tool única invocada:
```
setVisibleLayers({"names": ["alerts", "flood", "nucleos"]})
```

Bloque `[Interpretación para Emergencias]`:

> Dado que no podemos filtrar algorítmicamente por la proximidad a la inundabilidad, te recomiendo:
> 1. Observar el mapa con las capas activas.
> 2. Identificar visualmente las zonas con avisos de lluvia/tormenta (capa `alerts`).
> 3. Verificar si esas zonas coinciden espacialmente con las áreas de riesgo [...].

**Valoración**: respuesta libro de texto. Exactamente lo que la REGLA (B1) instruye: activar las tres capas relevantes con `setVisibleLayers`, declarar que el cruce algorítmico no es ejecutable, y derivar el análisis al usuario para inspección visual. **0 fabricación de datos**.

**Caso B** — `qwen3.6:35b-a3b-q8_0` T=0.0 (195 s, 2 iters reportadas pero 3 tools efectivas):

```
1. queryAlerts({"phenomenon": "lluvia", "status": "vigente"})
2. queryAlerts({"phenomenon": "tormenta", "status": "vigente"})
3. setVisibleLayers({"names": ["alerts", "flood", "nucleos"]})
```

Bloque `[Resultados]`:

> Avisos vigentes de lluvias (nivel Amarillo): 1. Litoral oriental asturiano [...] 2. Cordillera y Picos de Europa [...]. Avisos vigentes de tormentas (nivel Amarillo, 16 zonas): Asturias, Castilla y León y Galicia [...].

Bloque `[Interpretación para Emergencias]`:

> El visor permite **inspección visual** de la superposición de las tres capas, pero **no ofrece un resultado automatizado de cruces espaciales** entre avisos hidrometeorológicos y zonas inundables T10. Para evaluar la exposición real de núcleos pequeños a riesgo de inundación bajo estos avisos, se requeriría [...].

**Valoración**: más rico que el caso A — además de aplicar la REGLA (B1), el modelo enriqueció la respuesta con datos REALES de avisos vigentes a esa fecha (lluvia y tormenta) que el usuario puede contrastar con la capa T10 visualmente. **Respeta la limitación sin omitir el valor informativo**.

**Caso C** — `qwen3.6:35b-a3b-q8_0` T=0.3 (205 s, 3 iters, 4 tools):

```
1. setVisibleLayers({"names": ["alerts", "flood", "nucleos"]})
2. queryAlerts({"phenomenon": "lluvia", "status": "vigente"})
3. queryAlerts({"phenomenon": "tormenta", "status": "vigente"})
4. queryAlerts({"phenomenon": "aguas", "status": "vigente"})
```

Bloque `[Resultados]`:

> Avisos de lluvias vigentes: 2 zonas en Asturias (Amarillo). Avisos de tormentas vigentes: 16 zonas en Asturias, Castilla y León y Galicia (Amarillo). Avisos de aguas vigentes: ninguno. **No se ha podido calcular la superposición con la capa T10 ni la distancia a núcleos de población**.

**Valoración**: idéntico patrón al caso B, con búsqueda exhaustiva (3 fenómenos: lluvia, tormenta y aguas — los tres que menciona la consulta literal). Declaración explícita y honesta de la limitación.

### 6.3 Granite NO aplica la REGLA — análisis del fallo de q5 en granite

Granite hizo timeout 300 s en q5 a las 3 temperaturas. El log del orquestador no captura el detalle (el timeout corta antes de que el `log_interaction` escriba), pero el patrón es consistente con su comportamiento del v1 Sección 8.5: granite es **disciplinado al máximo en invocar tools** (Sección 8.4 nota previa: 100 % en `tool_calls_in_catalog`, `tool_calls_schema_valid` y `tool_support: native`). Cuando recibe un prompt que pide NO invocar tools y declarar limitación, su entrenamiento de "ser obediente al catálogo" lo empuja a seguir intentando combinaciones de tools del catálogo hasta agotar las 8 iteraciones permitidas.

**Hipótesis para Fase 2**: granite necesita una formulación más imperativa — algo como un control-flow explícito en el prompt:

```
SI la consulta menciona "T10" O "zona inundable" O "cruce con flood":
  EMITE primero y única vez setVisibleLayers(["alerts","flood","nucleos"]).
  EMITE texto final declarando limitación.
  NO emitas más tool_calls.
```

Esta variante NO se prueba en este experimento; se anota como ampliación pendiente.

### 6.4 gemma colapsa con el prompt nuevo — análisis del 0/6 OK

El prompt v2 es ~35 % más grande que el v1 (~9700 → ~13100 chars, +3 400 chars ≈ +850-1000 prompt tokens). El adaptador de tool calling de Gemma en Ollama mete adicionalmente el JSON Schema completo del catálogo como texto descriptivo (~3 000-4 000 tokens extra), por lo que el prompt efectivo que ve gemma supera 5 000 tokens. A los ~30 tokens/segundo de gemma sirviendo en Ollama, el **prompt eval solo** consume ~170 s, agotando el `LLM_REQUEST_TIMEOUT=180 s` antes de empezar a generar respuesta.

Patrón observado en gemma T=0:

| qid | Latencia | Tipo de fallo |
|---|---|---|
| q1 | 181 s | Timeout LLM (justo en el límite) |
| q2 | 231 s | Timeout LLM (excedió ampliamente) |
| q3 | 132 s | Conexión cerrada mid-call (probable kill upstream tras los timeouts) |
| q4 | 22 s | `All connection attempts failed` (circuit-breaker nginx) |
| q5 | 22 s | `All connection attempts failed` (idem) |

**Confirmación operativa**: la decisión de Sección 8.7 v1 ("descarte explícito de gemma4:26b en Ollama") queda reforzada. Si se quiere mantener Gemma como modelo del visor, **debe servirse sobre vLLM** (como hace la demo actual), no sobre Ollama.

### 6.5 Hallazgo inesperado — T=0.7 no es la peor temperatura

El bench sintético previo (Sección 10.5 de la nota TFG-20260519) reportó un efecto temperatura prácticamente plano (80.95 → 79.73 entre T=0 y T=0.7). En este v2 end-to-end, sin embargo, T=0.7 **no es peor que T=0** en OK %:

- T=0: 50 % (10/20)
- T=0.3: 44 % (7/16)
- T=0.7: **53 % (8/15)** ← incluye el único q4 OK + un q5 OK adicional

Hipótesis: cuando el modelo se enfrenta a un problema con rechazo controlado (q5) o una cadena ambigua (q4), T más alta produce planes más diversos y permite "saltar" patrones de bucle. A T=0 el modelo es más determinista y, si engancha un camino erróneo, lo repite hasta agotar iteraciones. **Implicación operativa**: para producción, podría considerarse T=0.3 como compromiso (planificación reproducible pero con margen exploratorio), reservando T=0 sólo para llamadas estructuradas puramente determinas (un solo tool).

Caveat: muestras pequeñas (n=15-20 por T). Necesitaría más datos para validar estadísticamente.

## 7. Limitaciones reconocidas

1. **2 cycles perdidos por bug intermitente del spawn de uvicorn**: qwen3.6:27b T=0.3 y qwen3.6:35b-a3b-q8_0 T=0.7. Los 10 cells correspondientes quedan como `backend_unhealthy` y NO se pueden re-correr trivialmente con el resume del script (porque el JSON existe). Mitigación pendiente: arreglar el bug del spawn (probable file handle leak en `spawn_uvicorn` que abre un handle de log sin cerrarlo) o borrar manualmente los 10 JSON y relanzar.

2. **Gemma sólo se ejecutó parcialmente** (T=0 completo + q1 T=0.3 = 6 de 15 cells previstos). Decisión deliberada del autor durante la ejecución para no malgastar ~30 minutos confirmando el patrón "gemma falla siempre" ya evidente tras los primeros 6 cells. Los 9 cells restantes de gemma se anotan como "no ejecutados — patrón confirmado por evidencia anterior".

3. **El timeout del script (`PER_REQUEST_TIMEOUT=300 s`) sigue cortando q4 antes de que algunos modelos puedan completarlo**. Si el experimento permitiera 600-900 s, podríamos ver más q4 OK. No se modificó en esta corrida para mantener comparabilidad con el v1.

4. **Sin validación humana de las 51 respuestas**. Los Markdown comparativos están preparados para inspección visual; si el tribunal del TFG pide anotación 1-5 sobre los outputs, se puede añadir como anexo.

5. **El experimento solo testa el adaptador Ollama de Gemma**. No probamos Gemma servido sobre vLLM (la pila REAL del demo) en chat e2e. Para una decisión definitiva sobre migrar fuera de Gemma habría que ejecutar este experimento contra `http://192.168.1.162:30000/v1/chat/completions` con la misma metodología — fuera del alcance de esta nota.

## 8. Recomendación final reconciliada al tutor

Combinando las 3 fuentes de evidencia (bench sintético Mode B + juicio cualitativo Opus 4.7 + chat e2e v1 + chat e2e v2):

| Escenario operativo | Modelo recomendado | Razón |
|---|---|---|
| **Visor en producción, modo híbrido (Mode B + narrativa al usuario)** | **`qwen3.6:27b`** a **T=0.7** | Único modelo que en v2 dio un cycle 5/5 perfecto. Combina alta faithfulness (4.73/5 del juicio Opus) + capacidad de aplicar la REGLA DE BLOQUEO PREVENTIVO + cadenas multi-step exitosas en q4. Trade-off: lat. mediana 62 s (mayor que granite). |
| **Visor en producción, prioridad latencia ultra-baja** | **`granite4.1:30b`** a **T=0.0** | Lat. mediana 15 s — la mejor. Disciplina perfecta en q1-q3 (100 % OK). **Riesgo conocido**: NO aplica la REGLA DE BLOQUEO PREVENTIVO en q5, hay que mitigar con código en el orquestador (detección de bucle, Acción #2 pendiente). |
| **Visor con GPU grande (≥48 GB)** | **`qwen3.6:35b-a3b-q8_0`** a **T=0 o T=0.3** | Único modelo que aplica la REGLA a las dos temperaturas bajas (más reproducible que qwen3.6:27b). Q8 = máxima calidad. Trade-off: 38.7 GB de VRAM. |
| **Descarte explícito** | **`gemma4:26b` sobre Ollama** | Confirmado por dos experimentos (v1 y v2). La demo actual sólo funciona porque usa vLLM. Si se decide migrar fuera de Gemma, esta es la prueba definitiva. |

**Recomendación operativa de la migración**:

1. **Adoptar `qwen3.6:27b` como modelo principal** del visor, configurado con `LLM_TEMPERATURE=0.7` (sí, esto contradice la recomendación T=0 del bench sintético; el v2 muestra que T=0.7 es necesario para que q4/q5 se resuelvan).
2. **Mantener `granite4.1:30b` como fallback rápido** para consultas simples y medias (q1-q3) donde la disciplina y la latencia son críticas.
3. **NO usar `gemma4:26b` con Ollama**. Mantener la demo en vLLM hasta migrar.
4. **Implementar Acción #2 (detección de bucle en orquestador)** para mitigar q4 a través de los 3 modelos.

## 9. Trazabilidad y reproducibilidad

- Script de ejecución: `meteovisor-test-llms/chat_e2e.py` (commit `e24dd81` + ajustes en sesión: MODELS list incluye `qwen3.6:35b-a3b-q8_0`).
- Script consolidador: `meteovisor-test-llms/consolidate_chat_e2e.py` (mismo commit + ajuste MODELS).
- Commits relevantes en `meteovisor-demo`:
  - `d5dbee1` (2026-05-25): soporte `LLM_TEMPERATURE` en el chat.
  - `17a38a3` (2026-05-25): notas TFG (benchmark + v1 chat e2e).
  - `71563f6` (2026-05-25): integración `queryRoadsNearPoint` y capa `roads`.
  - `eb68b18` (2026-05-25): REGLA DE BLOQUEO PREVENTIVO en `chat/prompt.py`. **Esta es la causa raíz de las mejoras observadas en v2**.
- Datos crudos del experimento v2: `meteovisor-test-llms/results/chat_e2e/` (51 ficheros JSON: 6 gemma + 15×3 modelos restantes; los 2 cycles perdidos no producen JSON).
- Datos crudos del v1 archivados en: `meteovisor-test-llms/results/chat_e2e_v1_pre_prompt_fix/` (37 JSON + 4 artefactos consolidados).
- Artefactos consolidados v2:
  - `results/chat_e2e/_summary_chat_e2e.csv` (51 filas, columnas planas para hoja de cálculo).
  - `results/chat_e2e/_aggregates_chat_e2e.md` (tablas por modelo/consulta/temperatura — fuente de Sección 5).
  - `results/chat_e2e/_comparativa_chat_e2e_por_modelo.md` (lectura: 4 modelos × 5 consultas × 3 temperaturas con respuestas literales).
  - `results/chat_e2e/_comparativa_chat_e2e_por_consulta.md` (lectura: 5 consultas × 3 temperaturas × 4 modelos lado a lado).
- Log de eventos del experimento: `results/chat_e2e/_run_log.jsonl` (cronológico).
- Endpoint usado: `http://138.100.63.85:11436/v1/chat/completions` (Helios proxy, OpenAI-compatible, bearer auth). Mismo que v1.
- Datos del backend (snapshot): aemet_max_temperature_daily_feature 70 993 filas (2025-04-30 a 2026-05-25), firms_hotspot 49 409 (2025-05-01 a 2025-08-31), burnt_area_daily_stat 123 (2025-05-01 a 2025-08-31), núcleos IGN cargados.
- Wall-clock total del experimento v2: 4 981 s (≈ 83 min de cycles limpios) + ~10 min de gemma cancelado = ~93 min totales.

## Datos explícitos

- 4 modelos evaluados: `gemma4:26b` (parcial), `qwen3.6:27b`, `qwen3.6:35b-a3b-q8_0`, `granite4.1:30b`.
- 5 consultas idénticas al v1 y al bench sintético.
- 3 temperaturas: 0.0, 0.3, 0.7.
- Producto cartesiano objetivo: 60 cells; ejecutados: 51 (6 gemma parcial + 45 cells válidos de los 3 modelos restantes).
- System prompt v2 con REGLA DE BLOQUEO PREVENTIVO (commit `eb68b18`) y queryRoadsNearPoint (commit `71563f6`).
- Total wall-clock: ~93 min.
- Resultados centrales: q4 0 % → 10 % (1 cell nuevo OK), q5 0 % → 30 % (3 cells nuevos OK), todos en modelos qwen.

## Datos inferidos

- Tipo de nota: `decisión` (recoge parámetros de un experimento y deriva acciones).
- Clasificación: `08-llm-y-consulta-en-lenguaje-natural/` (continuación directa de las notas previas del área).
- Hipótesis sobre T=0.7 mejor que T=0 en consultas con rechazo: requiere más muestras para confirmar.
- Hipótesis sobre granite siendo "tozudo": coherente con su entrenamiento centrado en tool-calling (Granite 4.0 BFCL leading); validable con prompts más restrictivos.
- Causa raíz del bug del spawn intermitente de uvicorn: probable file handle leak en `spawn_uvicorn` de `chat_e2e.py` (abre `_uvicorn.log` con `open(...)` sin cerrar handle previo entre spawns). Pendiente de verificar.

## Datos faltantes o ambiguos

- Resultados de gemma a T=0.3 (q2-q5) y T=0.7 (q1-q5) — 9 cells no ejecutados.
- Resultados de qwen3.6:27b T=0.3 y qwen3.6:35b-a3b-q8_0 T=0.7 — 10 cells perdidos por health_timeout intermitente del backend.
- ¿Habría alguna T intermedia (0.5?) en la que granite SÍ aplicase la REGLA? — no probado.
- ¿Replicar este v2 contra el endpoint vLLM real del demo (`192.168.1.162:30000`) cambiaría la conclusión sobre gemma? — no probado, recomendado en Sección 7 punto 5.
- Decisión del tutor sobre si los 51 outputs literales se incluyen como anexo en la memoria del TFG o solo el Markdown comparativo resumen.
- Validación cualitativa con anotación humana 1-5 sobre los 51 outputs — no realizada en esta primera versión.
