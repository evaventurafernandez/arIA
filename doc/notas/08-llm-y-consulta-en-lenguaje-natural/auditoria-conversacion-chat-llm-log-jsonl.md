---
id: TFG-20260512-auditoria-conversacion-chat-llm-log-jsonl
título: "Auditoría de conversación del chat LLM: log JSONL con sanitización asimétrica"
tipo: decisión
tags:
  - tfg
  - llm
  - auditoria
  - seguridad
  - logging
  - jailbreak
  - sanitizacion
contexto: "Decisión de seguridad y observabilidad del módulo de chat LLM del visor MeteoVisor. Define cómo se audita cada interacción y el orden deliberado entre sanitización y logging para distinguir lo que el usuario intentó de lo que el modelo realmente vio."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada del cierre del módulo de chat LLM (Fase 5 — logging mínimo, RF-64/RF-73 parcial)"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-12"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar el esquema exacto de la línea JSON antes de citarlo en la memoria."
  - "Decidir si la persistencia en BD se considera trabajo futuro o pendiente del TFG."
---

# Auditoría de conversación del chat LLM: log JSONL con sanitización asimétrica

## Contenido
Cada interacción del chat LLM emite **una línea JSON a stdout** con los campos suficientes para auditar la conversación. Cubre parcialmente RF-64 (registro de interacciones) y RF-73 (trazabilidad), dejando la persistencia en base de datos como trabajo posterior.

### Campos por línea
- `user_query`: consulta **original** del usuario, **sin sanitizar**.
- `final_reply`: respuesta final, **con tokens del tipo `sk-...` y `Bearer ...` redactados**.
- `tools_trace`: traza de tools invocadas con sus parámetros y resultados resumidos.
- `latency_ms`: tiempo total.
- `model`: identificador del modelo usado.
- (Otros metadatos: timestamp, sesión, etc.)

### Sanitización asimétrica deliberada
La sanitización del prompt del usuario se aplica **antes de pasarlo al LLM** pero **no antes de loguearlo**. El orden es intencional:

1. La cadena que ve **el modelo** está sanitizada.
2. La cadena que ve **el log** es la original.

Esto permite **distinguir entre dos preguntas distintas en la auditoría**:
- *"¿El usuario intentó algo malicioso?"* → mira `user_query` (original).
- *"¿El modelo lo vio?"* → mira lo que se mandó al modelo, derivable del trace.

Es útil para auditar intentos de **jailbreak** y extracción de tokens incrustados en el mensaje del usuario (`Bearer ...`, `sk-...`, etc.): el intento queda registrado aunque el modelo nunca lo haya visto.

La sanitización aplicada a `final_reply` redacta tokens evidentes para evitar que se filtren por la respuesta del propio modelo.

### Persistencia
Por ahora, salida a **stdout en formato JSONL**. La persistencia en BD se considera deferida; queda planteada como continuación natural del trabajo y cubriría completamente RF-64 y RF-73.

### Encaje con otras decisiones
- [[casos-borde-chat-llm-rechazo-controlado]]: el log permite verificar a posteriori que el rechazo se aplicó.
- [[effis-fuera-de-alcance-en-catalogo-de-tools-llm]]: tests sobre el log pueden detectar regresiones (presencia de tool names prohibidos).
- [[ideas-operaciones-llm-local-en-visor-meteovisor]]: cierra el bullet "Logging persistente por interacción" mencionado en la arquitectura mínima.

## Datos explícitos
- Una línea JSON por interacción a stdout.
- `user_query` se loguea sin sanitizar.
- `final_reply` se loguea con tokens `sk-`/`Bearer` redactados.
- La sanitización del prompt ocurre antes del LLM, no antes del log.
- Persistencia en BD diferida; RF-64/RF-73 cubiertos parcialmente.

## Datos inferidos
- El esquema JSONL facilita ingestion posterior por herramientas estándar (jq, BigQuery, ClickHouse) sin compromiso de schema rígido.
- La sanitización asimétrica es un patrón defendible en la memoria como mecanismo de auditoría de jailbreak.

## Datos faltantes o ambiguos
- Esquema cerrado y versionado de la línea JSON.
- Política de retención de logs.
- Si la BD destino para la persistencia diferida será PostgreSQL/PostGIS u otra.
