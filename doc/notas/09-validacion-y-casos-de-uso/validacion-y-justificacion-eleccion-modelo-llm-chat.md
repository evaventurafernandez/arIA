---
id: TFG-20260604-validacion-y-justificacion-eleccion-modelo-llm-chat
título: "Validación del modelo LLM del chat y justificación de la elección: comprobación manual frente a las respuestas de los 4 modelos (5 consultas × 3 temperaturas, 4 criterios)"
tipo: validación
tags:
  - tfg
  - llm
  - validacion
  - casos-de-uso
  - gold-standard
  - exec-accuracy
  - seleccion-modelo
  - benchmark
  - meteovisor-demo
contexto: "Nota de cierre de la validación y selección del modelo LLM del chat del visor. Fusiona y sustituye las notas previas de validación (comprobación del modelo final, rejilla completa de exactitud y justificación por criterios). Construye una resolución manual de referencia (gold-standard) de las 5 consultas del benchmark y la enfrenta a las respuestas de los 4 modelos en las 3 temperaturas, valorando los cuatro criterios que importan para un asistente de emergencias: que complete la consulta, que el dato sea preciso, que no se invente nada y que la redacción sea entendible. Con esa tabla resultado se justifica técnicamente la elección de qwen3.6:35b-a3b-q8_0. Continúa y consolida TFG-20260527 (barrido e2e v4) y TFG-20260519 (ranking cualitativo)."
fuente_existe: true
fuente_tipo: "elaboración propia + verificación contra base de datos + experimento en vivo"
fuente_descripción: "elaboración propia del autor del TFG. Resolución manual de las 5 consultas mediante SQL directo sobre el PostGIS del prototipo (esquemas pub.* y core.*) y el glosario chat/data/glossary.json. Respuestas de los modelos: q1/q3/q4 del barrido e2e v4 (results/chat_e2e/, 2026-05-27, dato histórico fijo); q2/q5 re-ejecutadas en vivo el 2026-06-04 (results/chat_e2e_live_20260604/) capturando por celda la salida íntegra de la tool, más un gold manual independiente simultáneo. Valoración de la redacción mediante criterios técnicos reproducibles sobre las respuestas capturadas."
fuente_url: ""
autor_o_entidad: "autor del TFG"
fecha_fuente: "2026-06-04"
licencia_o_copyright: "uso académico del TFG"
condiciones_de_uso: "uso interno del TFG; tabla resultado y anexo SQL candidatos a anexo de la memoria"
grado_de_confianza: alto
pendientes_de_verificar:
  - "q5 en vivo el 2026-06-04 fue un caso degenerado (0 avisos vigentes de lluvia/tormenta/agua), que discrimina menos que el barrido original (2026-05-27, 22 avisos de tormenta). El rechazo controlado de T10 se observa igualmente, pero la prueba fuerte con avisos presentes está en la sección 4.5."
  - "gemma4:26b falla las consultas en vivo por 502 del proxy Helios (no es error de dato sino de no-completado por infraestructura)."
  - "Confirmar con el tutor la ubicación final (capítulo de validación vs anexo)."
---

# Validación del modelo LLM del chat y justificación de la elección

## 1. Objetivo: qué hueco cubre esta validación

La selección del modelo (TFG-20260527, v4) se apoyó en dos capas de evidencia que **no comparaban la respuesta contra el dato verdadero**:

1. **Métricas estructurales** (ok %, formato de 4 bloques, iteraciones, tool_calls): miden *si* el modelo responde y encadena tools, no *si acierta el dato*.
2. **Juicio cualitativo** del barrido sintético v0 (TFG-20260519): valora plan y fidelidad aparente, pero sin gold-standard exacto.

Esta nota añade la capa que faltaba: **comparar la respuesta del modelo contra una resolución manual de referencia** (la *exec/answer accuracy* del Berkeley Function-Calling Leaderboard: ejecutar y verificar el resultado, no solo que el plan sería correcto). Y lo hace para **toda la rejilla** (4 modelos × 5 consultas × 3 temperaturas), no solo el modelo elegido, valorando cuatro criterios.

### Los cuatro criterios de evaluación

Para un asistente de emergencias una respuesta sirve solo si cumple **a la vez**:

| Criterio | Pregunta | Cómo se mide |
|---|---|---|
| **1. Completado** | ¿Termina la consulta y cierra con respuesta? | tasa de celdas OK sobre 15 (5 consultas × 3 T) |
| **2. Precisión** | Al completar, ¿el dato coincide con la resolución manual? | cotejo contra gold (SQL / glosario / tool en vivo) |
| **3. No-invención** | ¿Cero fabricación de cifras, fechas, núcleos? | verificación de cada cifra contra la BD |
| **4. Redacción entendible** | ¿Es clara para un usuario no técnico? | criterios técnicos reproducibles (sección 5) |

## 2. Método

- **Modelos**: los 4 del barrido v4 — `qwen3.6:35b-a3b-q8_0`, `qwen3.6:27b`, `granite4.1:30b`, `gemma4:26b`.
- **Consultas**: q1 (FWI), q2 (focos activos < 2 km de núcleo < 5.000 hab), q3 (día de más área quemada), q4 (día AEMET más caliente + núcleo más poblado más cercano), q5 (cruce avisos + T10 + núcleos).
- **Temperaturas**: 0.0, 0.3, 0.7.
- **Gold-standard**: resolución manual ejecutando la **misma operación que la tool** directamente contra la BD (SQL sobre `pub.*`/`core.*`) o el glosario. SQL en el anexo (sección 8).
- **Procedencia de las respuestas**:
  - **q1, q3, q4** (dato fijo: histórico en BD / glosario) → respuestas capturadas en el barrido v4 (2026-05-27).
  - **q2, q5** (dato en tiempo real: focos FIRMS en vivo / avisos AEMET vigentes) → **re-ejecutadas en vivo el 2026-06-04**, capturando por celda la salida íntegra de su tool (= la operación manual ejecutada en ese instante) y un gold manual independiente snapshotado en paralelo.

**Por qué la comparación no es redundante con las otras capas.** Como el chat ejecuta las tools reales contra PostGIS, si la tool es correcta el dato del modelo *debería* coincidir con el SQL manual. Esta comparación detecta lo que las otras capas no ven: (a) tool/argumentos equivocados, (b) mala interpretación de la salida, y sobre todo (c) **transcripción errónea del dato en la narrativa** (la tool devolvió la cifra correcta pero el bloque `[Resultados]` dice otra) — el fallo más peligroso en emergencias.

## 3. Resolución manual de referencia (el gold por consulta)

| q | Gold | Valor de referencia |
|---|---|---|
| q1 | glosario `explainTerm("FWI")` | definición canónica del Fire Weather Index |
| q2 | SQL focos en vivo + `core.nucleos_poblacion_polygon` | **en vivo 2026-06-04: 14 coincidencias / 39 focos candidatos** |
| q3 | `argmax`/`sum` sobre `pub.burnt_area_daily_stat` | **2025-08-16 · 32.305,51 ha** (pico); 248.383,15 ha en 123 días (total) |
| q4 | `argmax` `pub.aemet_max_temperature_daily_stat` + LATERAL núcleos | **2025-08-12 · 45 °C** (Vegas del Guadiana, Rojo); Badajoz 124.523 (a 0 m de la zona más caliente); Sevilla 683.312 (núcleo más poblado del día) |
| q5 | política de rechazo controlado + avisos vigentes | declarar T10 no ejecutable (WMS externo sin geometría local); **en vivo 2026-06-04: 0 avisos vigentes** |

**Matiz verificado en q4 (empate):** la temperatura pico de 45 °C empata entre **2025-08-12** y **2025-08-17**; el `argmax` de la tool rompe el empate por fecha ascendente → 2025-08-12. La "respuesta correcta" depende de ese criterio de desempate documentado.

**Estabilidad del dato vivo (q2/q5).** El gold manual independiente fue **constante durante todo el barrido del 2026-06-04** (07:56 → 09:12 UTC: q2 = 14/39; q5 = 0 avisos), sin deriva, de modo que todas las celdas vivas comparten el mismo gold. La salida de la tool del primer modelo coincidió exactamente con el gold independiente (14/39) → **reproducibilidad confirmada**.

## 4. Resultados: rejilla completa de exactitud (4 × 5 × 3)

`O` = completa y **acierta** el gold · `N` = completa pero **no** acierta · `x` = **no** completa · (T0.0 · T0.3 · T0.7).

| modelo | q1 | q2 | q3 | q4 | q5 |
|---|---|---|---|---|---|
| **qwen3.6:35b-a3b-q8_0** | `OOO` | `OOO` | `OOO` | `OOx` | `OOO` |
| qwen3.6:27b | `OOO` | `OOO` | `OOO` | `xxO` | `OOO` |
| granite4.1:30b | `OOO` | `OOO` | `OOO` | `xxx` | `OOO` |
| gemma4:26b | `OOO` | `xxx` | `OOO` | `xxx` | `xxx` |

**Hallazgo central:** en las 60 celdas **no hay ni un solo `N`** — ningún modelo que completa una consulta inventa o yerra el dato. Todos los fallos son `x` (no-completado). Es decir: **la precisión del dato no diferencia a los modelos; lo que los diferencia es completar y redactar bien.**

### 4.1 q1 (semántico) — 12/12
Todos reproducen la definición del FWI con fidelidad (índice canadiense adimensional; capa WMS EFFIS; peligro ≠ actividad detectada).

### 4.2 q2 (vivo, gold 14/39) — completan qwen35b, qwen27b, granite (gemma falla)
Los tres que completan **citan correctamente las 14 coincidencias** de su propia traza; las poblaciones citadas son reales y exactas en `core.nucleos_poblacion_polygon` (Castillejo 2, Toral de los Vados 1.276, Ororbia 758, Morata de Jalón 1.058…). gemma falla las 3 por 502 del proxy.

### 4.3 q3 (exacto) — 12/12
Todos aciertan 2025-08-16 / 32.305,51 ha / 248.383,15 ha / 123 días. *(Nota: granite escribe las cifras con espacio fino como separador de miles; el cotejo automático exige normalizar formatos numéricos para no producir falsos negativos.)*

### 4.4 q4 (exacto, la más difícil) — 3 completados, los 3 aciertan
Solo qwen35b (T0/T0.3) y qwen27b (T0.7) completan, y los tres aciertan el día pico (12-ago, 45 °C, Vegas del Guadiana), Badajoz 124.523 y/o Sevilla 683.312. El resto no completa (no encadena AEMET→núcleos), no se equivoca.

### 4.5 q5 (rechazo controlado)
- **En vivo 2026-06-04 (degenerado, 0 avisos):** los tres que completan reportan correctamente que no hay avisos vigentes, no alucinan avisos y mantienen el rechazo de T10. Caso de baja exigencia por la ausencia de avisos.
- **Prueba fuerte (capturada 2026-05-27, 22 avisos de tormenta):** el modelo elegido declaró explícitamente *"Cruce espacial con zona inundable (T10): No se ha podido realizar"* explicando la causa (WMS externo de MITECO sin geometría vectorial local). Esto contrasta con el barrido sintético v0, donde **ningún** modelo declaraba la limitación (0 % `declared_limitation`) antes de enriquecer el system prompt: evidencia de que la corrección del prompt funcionó end-to-end.

## 5. Valoración de la calidad de redacción (criterio 4)

Como la precisión no separa a los modelos (100 % al completar), la calidad de cara al usuario se decide en la **legibilidad de la respuesta**. La valoración se hace aplicando a las respuestas capturadas cuatro criterios técnicos reproducibles:

- **(a)** ausencia de jerga de implementación dirigida al usuario (no exponer endpoints, nombres de campos, llamadas a tools);
- **(b)** adherencia al formato de 4 bloques del visor;
- **(c)** aportación de contexto interpretativo útil **sin** invención;
- **(d)** concisión sin pérdida de información (ni telegráfico ni redundante).

Comparando las respuestas a una misma consulta (q3@T=0, donde los 4 modelos dan la respuesta correcta, lo que aísla la prosa):

| Modelo | Observación con evidencia textual | Puntuación (1-5) |
|---|---|---|
| **qwen3.6:35b-a3b-q8_0** | Prosa clara y contextualizada; añade interpretación útil sin inventar (*"El día 16 de agosto representa aproximadamente el 13 % del total quemado en la temporada"*) y explica la acción del visor. Cumple (a)-(d). | **5** |
| qwen3.6:27b | Igual de claro y correcto, algo más esquemático (listas). Cumple (a)-(d) con prosa más escueta. | 4,5 |
| gemma4:26b | Cuando completa, prosa correcta pero **mínima** (q3: solo el titular, sin total ni contexto → incumple (d)); además completa poco. | 3,5 |
| granite4.1:30b | Contenido correcto pero **expone el mecanismo interno al usuario** de forma recurrente — *"La llamada a `explainTerm` devolvió los siguientes datos"* (q1), *"El endpoint devolvió un objeto que incluye el campo `peak_day`"* (q3). Incumple (a): registro de desarrollador, no de asistente de emergencias. | 3 |

El criterio (a) es el que penaliza a granite pese a su precisión: una respuesta que menciona "el endpoint devolvió un objeto" no es utilizable por un técnico de emergencias sin formación en la arquitectura del sistema.

## 6. Tabla resultado final y decisión justificada

| Modelo | 1. Completado | 2. Precisión (al completar) | 3. No-invención | 4. Redacción | Veredicto |
|---|---|---|---|---|---|
| **qwen3.6:35b-a3b-q8_0** | **14/15** | **100 %** | **Sí** | **5/5** | **ELEGIDO** |
| qwen3.6:27b | 13/15 | 100 % | Sí | 4,5/5 | fallback |
| granite4.1:30b | 12/15 | 100 % | Sí | 3/5 | descartado |
| gemma4:26b | 6/15 | 100 % | Sí | 3,5/5 | descartado |

**Se elige `qwen3.6:35b-a3b-q8_0`**, respaldado en los cuatro criterios simultáneamente:

1. **Máxima tasa de completado** (14/15), incluida la consulta multi-tool q4 que el resto no encadena.
2. **Precisión perfecta** al completar, combinada con la mayor cobertura.
3. **Sin invención** de datos.
4. **Mejor redacción** para el usuario no técnico, sin fugas de jerga.

Los descartes quedan justificados por eliminación: **gemma** por completado (6/15, inviable en las consultas en vivo/complejas); **granite** por no completar q4 **y** por una redacción que expone internals; **qwen3.6:27b** es el segundo mejor en todos los ejes y queda como **fallback** documentado (si Helios no sostiene la VRAM del modelo Q8, ver [[proyecto-modelo-desplegado-visor]] y [[integracion-modelo-final-visor-alineacion-env]]).

Argumento de cierre: como ningún modelo que completa se equivoca en el dato, elegir el modelo es **maximizar cuántas consultas resuelve bien y cómo de claro las explica** — y en ambos gana qwen3.6:35b-a3b-q8_0.

## 7. Limitaciones honestas

1. **q5 en vivo (2026-06-04) fue degenerado** (0 avisos): discrimina menos que el barrido original. La prueba fuerte del rechazo controlado, con 22 avisos presentes, está en la sección 4.5 (datos capturados 2026-05-27).
2. **q2 es dato vivo**: la comparación es exacta para el snapshot de hoy (estable durante el barrido), pero no es el del 2026-05-27; q2/q5 se documentan como sub-experimento en vivo fechado 2026-06-04.
3. **gemma y el proxy**: sus fallos en vivo son 502 de Helios, no errores de dato.
4. **n = 1 por celda viva** y, en general, el experimento es ilustrativo, no estadísticamente potente.
5. El **criterio 4 (redacción)** es una valoración con criterios técnicos reproducibles sobre las respuestas; formalizable con rúbrica multi-anotador si se requiere mayor rigor estadístico.

## 8. Anexo reproducible — SQL del gold-standard

Ejecutado contra `meteovisor-postgres` (`psql -U meteovisor -d meteovisor`).

**q3 — día pico y total de área quemada:**
```sql
SELECT nominal_date, burned_area_ha, burned_pixel_count
FROM pub.burnt_area_daily_stat
WHERE dataset_version='v4' AND delivery_format='cog' AND stat_scope='country'
  AND nominal_date BETWEEN '2025-05-01' AND '2025-08-31'
ORDER BY burned_area_ha DESC NULLS LAST LIMIT 1;          -- 2025-08-16 | 32305.51 | 8749
SELECT count(*), round(sum(burned_area_ha)::numeric,2)
FROM pub.burnt_area_daily_stat
WHERE dataset_version='v4' AND delivery_format='cog' AND stat_scope='country'
  AND nominal_date BETWEEN '2025-05-01' AND '2025-08-31'; -- 123 | 248383.15
```

**q4 — día pico de temperatura (con empate) y núcleos:**
```sql
SELECT nominal_date, max_temperature_c
FROM pub.aemet_max_temperature_daily_stat
WHERE stat_scope='country' AND area_code='ES' AND max_temperature_c >= 45
ORDER BY nominal_date;                                    -- 2025-08-12 | 2025-08-17 (empate)

SELECT f.area_name, f.level_label, f.temperature_max_c, n.nombre, n.habitantes,
       round(ST_Distance(f.geom::geography, n.geom::geography)::numeric,1) AS dist_m
FROM pub.aemet_max_temperature_daily_feature f
JOIN LATERAL (
  SELECT nombre, habitantes, geom
  FROM core.nucleos_poblacion_polygon
  WHERE habitantes IS NOT NULL AND habitantes > 0
    AND ST_DWithin(f.geom::geography, geom::geography, 50000)
  ORDER BY habitantes DESC NULLS LAST, ST_Distance(f.geom::geography, geom::geography) ASC
  LIMIT 1
) n ON true
WHERE f.valid_date='2025-08-12' AND f.is_warning
ORDER BY f.temperature_max_c DESC NULLS LAST, f.level_rank DESC, f.area_name LIMIT 3;
-- Vegas del Guadiana | Rojo | 45 | Badajoz | 124523 | 0.0
-- Campiña gaditana   | Rojo | 44 | Sevilla | 683312 | 45790.5
```

**q2/q5 (en vivo)** — gold reproducido con `meteovisor-demo/gold_live_q2q5.py` (ejecuta `activeFiresNearPopulation(2000, 5000)` y `queryAlerts` sin pasar por el LLM); respuestas de los modelos en `results/chat_e2e_live_20260604/`.

## Datos explícitos
- Tabla resultado (4 ejes): qwen35b 14/15·100 %·sí·5; qwen27b 13/15·100 %·sí·4,5; granite 12/15·100 %·sí·3; gemma 6/15·100 %·sí·3,5.
- 0 casos de "completa pero falla el dato" en las 60 celdas.
- Gold q3: 2025-08-16 / 32.305,51 ha / 248.383,15 ha / 123 días. Gold q4: 2025-08-12 / 45 °C / Badajoz 124.523 / Sevilla 683.312 (empate con 2025-08-17). Gold q2 vivo: 14/39. Gold q5 vivo: 0 avisos.
- Barrido en vivo: 24 celdas en ~85 min; 18 OK, 6 fallo (gemma, 502).

## Datos inferidos
- El diferenciador entre modelos es la tasa de completado y la legibilidad, no la exactitud del dato.
- El modelo elegido domina la frontera de los 4 criterios; el único coste (VRAM Q8) está cubierto por el fallback qwen3.6:27b.

## Datos faltantes o ambiguos
- Exactitud de q5 con avisos presentes para los 4 modelos (la versión en vivo de hoy fue degenerada).
- Ubicación final en la memoria (capítulo vs anexo).

## Referencias
- [[casos-borde-chat-llm-rechazo-controlado]] — política de rechazo controlado (q5).
- [[integracion-modelo-final-visor-alineacion-env]] — alineación del .env al modelo elegido.
- [[proyecto-modelo-desplegado-visor]] — modelo desplegado y fallback.
- TFG-20260527 (v4) — barrido e2e y tabla de descarte. TFG-20260519 (v0) — ranking cualitativo.
