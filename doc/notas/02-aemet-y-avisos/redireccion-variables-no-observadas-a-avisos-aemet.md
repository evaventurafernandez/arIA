---
id: TFG-20260512-redireccion-variables-no-observadas-a-avisos-aemet
título: "Redirección de variables no observadas a avisos AEMET en el chat LLM"
tipo: decisión
tags:
  - tfg
  - llm
  - aemet
  - avisos
  - alcance
  - tool-calling
contexto: "Decisión de diseño del módulo de chat LLM del visor MeteoVisor (worktree feature/chat-llm, fases 0-6). Define cómo el asistente trata consultas sobre variables meteorológicas concretas que el visor no almacena ni sirve como mediciones."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada del cierre del módulo de chat LLM en MeteoVisor"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-12"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar si se cita en la memoria como decisión de alcance o como mecanismo anti-alucinación."
---

# Redirección de variables no observadas a avisos AEMET en el chat LLM

## Contenido
El visor MeteoVisor no consume mediciones meteorológicas horarias (temperatura, viento, precipitación, humedad). Las únicas señales relacionadas con esas variables que viven en la plataforma son los **avisos CAP de AEMET**, que representan riesgo declarado por la agencia para un fenómeno y un nivel, no la medición real del fenómeno.

Para mantener coherencia con los datos disponibles y evitar que el modelo invente valores numéricos, las consultas tipo *"¿dónde hace viento fuerte ahora?"* o *"sitios con temperatura > 35 °C"* se reinterpretan como `queryAlerts(phenomenon='viento'|'temperatura', status='vigente')`. La respuesta del asistente explicita que se basa en avisos CAP de AEMET, no en mediciones.

El patrón se fuerza desde el **system prompt** del asistente: se enumera la lista de variables no observadas, se prohíbe inventar números y se redirige al patrón `queryAlerts(phenomenon=...)`. La sustitución es semántica, no léxica: el modelo decide la reinterpretación a partir de la descripción de tools y la sección de limitaciones del prompt.

Relacionado con [[ideas-operaciones-llm-local-en-visor-meteovisor]] (RF-65, RF-69, RF-70: validación, respuestas basadas en datos reales, indicación de incertidumbre).

## Datos explícitos
- El visor no almacena mediciones horarias de variables meteorológicas.
- Los avisos AEMET en formato CAP sí están persistidos y servidos por la API del visor.
- El system prompt del chat fuerza el patrón de redirección.
- La tool `queryAlerts` acepta el parámetro `phenomenon` para filtrar por substring sobre el campo `event`.

## Datos inferidos
- Sin esta redirección, el modelo tendería a verbalizar valores numéricos plausibles que el visor no puede sustentar.
- La redirección encaja con RF-69 ("respuestas basadas en datos de la plataforma") y RF-65 ("validación de resultados críticos").

## Datos faltantes o ambiguos
- Catálogo final cerrado de "variables no observadas" enumeradas explícitamente en el prompt.
- Mensaje exacto que el asistente devuelve al redirigir la consulta.
