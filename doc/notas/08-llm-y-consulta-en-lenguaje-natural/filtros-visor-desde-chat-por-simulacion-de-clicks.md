---
id: TFG-20260512-filtros-visor-desde-chat-por-simulacion-de-clicks
título: "Filtros del visor desde el chat por simulación de clicks, no mutación de estado"
tipo: decisión
tags:
  - tfg
  - llm
  - frontend
  - arquitectura
  - estado-ui
  - tool-calling
contexto: "Decisión de arquitectura del frontend del visor MeteoVisor para integrar el chat LLM. Define cómo aplican las tools de control de UI (`setFilter`, `toggleLayer`) sus cambios sobre el estado del visor."
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
  - "Confirmar que la memoria del TFG cita los nombres exactos de los handlers (`toggleWMS`, `toggleNucleos`, `toggleBurntAreaLayer`, `renderAll`)."
---

# Filtros del visor desde el chat por simulación de clicks, no mutación de estado

## Decisión
Las tools del chat LLM que cambian el estado de la UI del visor (`setFilter`, `toggleLayer`, control de niveles de aviso, fuentes FIRMS, etc.) **no mutan el estado interno directamente**: **disparan eventos sobre los mismos elementos del DOM** que un usuario manipularía con el ratón.

### Por qué
Para mantener **una sola ruta de cambio de estado UI**. Si el chat tuviera su propio camino paralelo (mutar variables JS, actualizar estados internos), aparecerían dos fuentes de verdad: la de los handlers existentes (`toggleWMS`, `toggleNucleos`, `toggleBurntAreaLayer`, `renderAll`) y la del chat. Cualquier divergencia produce bugs sutiles (capas activadas en el modelo de datos pero no en el mapa, o al revés). Pasar por el DOM garantiza que el visor siempre transita por sus handlers ya probados.

### Cómo
- **`setFilter(level=[...])`**: el chat hace `click` programático sobre `.fbtn.none` (resetea filtros) y luego sobre cada botón de nivel pedido. La cascada de handlers ya cargados decide el render.
- **`toggleLayer`**: el chat dispara el evento `change` sobre el checkbox correspondiente. El handler asociado (`toggleWMS` / `toggleNucleos` / `toggleBurntAreaLayer` / `renderAll`) se encarga del resto.

### Trade-offs aceptados
- Latencia marginalmente mayor que mutación directa: despreciable a escala humana.
- Acoplamiento del chat al DOM del visor: aceptable porque el chat se concibe como UI auxiliar del propio visor, no como cliente externo desacoplado.
- Si la UI se rediseña (por ejemplo migrar de checkboxes a un toggle component), las tools del chat deben actualizar el selector. Es una superficie de cambio pequeña y explícita.

Relacionado con [[ideas-operaciones-llm-local-en-visor-meteovisor]] (Nivel 1, control puro de interfaz).

## Datos explícitos
- `setFilter` simula clicks sobre `.fbtn.none` y los niveles solicitados.
- `toggleLayer` dispara un evento `change` sobre el checkbox.
- Los handlers existentes son `toggleWMS`, `toggleNucleos`, `toggleBurntAreaLayer`, `renderAll`.
- No hay mutación directa del estado interno desde el chat.

## Datos inferidos
- La decisión privilegia la robustez frente al rendimiento.
- Tests de UI sobre el chat pueden reutilizar los tests existentes sobre los handlers del visor.

## Datos faltantes o ambiguos
- Selectores exactos de los checkboxes para cada capa (documentar en la memoria si se desea reproducibilidad fina).
- Comportamiento si un selector deja de existir tras un rediseño (¿error explícito de la tool o silencio?).
