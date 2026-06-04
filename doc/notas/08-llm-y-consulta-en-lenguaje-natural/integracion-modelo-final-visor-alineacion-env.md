---
id: TFG-20260602-integracion-modelo-final-visor-alineacion-env
título: "Integración del modelo LLM final en el visor: alineación del .env con el modelo seleccionado en el benchmark"
tipo: decisión
tags:
  - tfg
  - llm
  - chat
  - despliegue
  - configuracion
  - seleccion-modelo
  - meteovisor-demo
contexto: "Cierra la acción derivada #1 de TFG-20260527 (v4): integrar el modelo seleccionado en el chat del visor. Al revisar el estado real del despliegue se detectó que el .env activo NO servía el modelo ganador, sino otro (`google/gemma-4-26B-A4B-it`) sobre un endpoint local distinto (`192.168.1.162:30000`) que además no respondía. Esta nota documenta la alineación del .env con la configuración validada en el benchmark y en la validación manual (TFG-20260604-validacion-y-justificacion-eleccion-modelo-llm-chat)."
fuente_existe: true
fuente_tipo: "elaboración propia (configuración del prototipo)"
fuente_descripción: "elaboración propia del autor del TFG: edición del fichero `.env` del backend FastAPI del visor, con copia de seguridad previa en `.env.backup_pre_alineacion_modelo_final_20260602`. Disponibilidad del modelo verificada contra el endpoint Helios (`/api/tags`) y conectividad/auth verificada con una petición de prueba a `/v1/chat/completions`."
fuente_url: ""
autor_o_entidad: "autor del TFG"
fecha_fuente: "2026-06-02"
licencia_o_copyright: "uso académico del TFG"
condiciones_de_uso: "uso interno del TFG"
grado_de_confianza: alto
pendientes_de_verificar:
  - "El modelo qwen3.6:35b-a3b-q8_0 es reasoning: en frío tarda (≈76 s de carga observada) y razona antes de emitir texto. Confirmar que el indicador de progreso del frontend (pendiente desde v4 §8.7 / acción 3) está antes de exponer el chat a usuarios."
  - "Confirmar con el responsable de Helios la disponibilidad sostenida del modelo (≈48 GB VRAM con keep_alive) si el visor va a depender de él en la defensa."
  - "Decidir si el endpoint definitivo será Helios o un servidor propio; si se migra a un servidor OpenAI-compatible (sglang/vLLM), el id del modelo cambiará de la nomenclatura Ollama (`qwen3.6:35b-a3b-q8_0`) a la estilo HuggingFace."
---

# Integración del modelo LLM final en el visor: alineación del .env

## 1. Discrepancia detectada

La acción #1 de la nota v4 (TFG-20260527) era integrar `qwen3.6:35b-a3b-q8_0` como modelo del chat. Al revisar el `.env` activo del visor, el estado real **no coincidía** con el modelo seleccionado:

| Parámetro | Antes (`.env` desalineado) | Benchmark / selección final |
|---|---|---|
| `LLM_MODEL` | `google/gemma-4-26B-A4B-it` | `qwen3.6:35b-a3b-q8_0` |
| `LLM_API_URL` | `http://192.168.1.162:30000/v1/chat/completions` (local) | Helios `http://138.100.63.85:11436/v1/chat/completions` |
| `LLM_TEMPERATURE` | (sin fijar → default del servidor) | 0 (régimen determinista validado) |
| `LLM_REQUEST_TIMEOUT` | 120 s | insuficiente para q4/q5 (latencia máx. observada ≈508 s) |

Además, el endpoint local `192.168.1.162:30000` **no respondía** (HTTP 000), de modo que el chat del visor estaba apuntando a un servidor caído.

## 2. Verificación de disponibilidad

`GET /api/tags` en Helios confirma que el modelo ganador está publicado y cargable:

```
qwen3.6:35b-a3b-q8_0 | family qwen35moe | 36.0B | Q8_0 | 38.7 GB
```

La misma `LLM_API_KEY` del `.env` autentica contra Helios (bearer válido, HTTP 200). Una petición de prueba a `/v1/chat/completions` con este modelo devuelve HTTP 200 y genera tokens (≈76 s en frío por cold-start; ≈2,5 s en caliente). La corrección **end-to-end** de las respuestas de este modelo ya está demostrada en la validación manual (TFG-20260604-validacion-y-justificacion-eleccion-modelo-llm-chat, q1-q5).

## 3. Cambios aplicados al .env

```diff
- LLM_API_URL=http://192.168.1.162:30000/v1/chat/completions
+ LLM_API_URL=http://138.100.63.85:11436/v1/chat/completions
- LLM_MODEL=google/gemma-4-26B-A4B-it
+ LLM_MODEL=qwen3.6:35b-a3b-q8_0
+ LLM_TEMPERATURE=0
- LLM_REQUEST_TIMEOUT=120
+ LLM_REQUEST_TIMEOUT=900
```

Justificación de cada cambio:
- **Modelo y endpoint**: alinear el despliegue con el modelo validado (no tendría sentido defender una elección y servir otro modelo distinto).
- **`LLM_TEMPERATURE=0`**: es la temperatura de planificación recomendada para tool calling (TFG-20260519 §8.5) y la usada en la validación manual. El `llm_client` solo propaga la temperatura si está fijada; sin ella, quedaba al criterio del servidor.
- **`LLM_REQUEST_TIMEOUT=900`**: con 120 s las consultas complejas q4/q5 (mediana 4-8 min en este modelo) caducarían. 900 s es el techo usado en el barrido v4. El `llm_client` no impone `max_tokens`, por lo que el modelo reasoning puede completar su razonamiento.

Copia de seguridad previa: `.env.backup_pre_alineacion_modelo_final_20260602`.

## 4. Consecuencias y pendientes

- El modelo es **reasoning** y lento en frío. El **indicador de progreso del frontend** (pendiente desde v4 §8.7) pasa a ser bloqueante antes de exponer el chat a usuarios reales.
- El visor queda dependiente de Helios. Si Helios no garantiza VRAM sostenida, el plan B documentado es `qwen3.6:27b` (TFG-20260527 §7.2, 80 % éxito, 17,4 GB).

## Datos explícitos
- `.env` alineado al modelo `qwen3.6:35b-a3b-q8_0` sobre Helios, T=0, timeout 900 s.
- Endpoint local previo (`192.168.1.162:30000`) caído en el momento de la revisión.
- Disponibilidad del modelo confirmada vía `/api/tags`; conectividad/auth vía `/v1/chat/completions` (HTTP 200).

## Datos inferidos
- El `.env` desalineado sugiere una prueba previa con un servidor local que quedó sin revertir; la copia de seguridad permite recuperar ese estado si fuera intencionado.

## Datos faltantes o ambiguos
- Motivo del cambio previo a `gemma-4-26B` local (no documentado).
- Endpoint definitivo de producción (Helios vs. servidor propio) pendiente de decisión.
