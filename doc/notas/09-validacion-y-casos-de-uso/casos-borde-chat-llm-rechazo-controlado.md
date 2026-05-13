---
id: TFG-20260512-casos-borde-chat-llm-rechazo-controlado
título: "Casos de borde del chat LLM: rechazo controlado y redirección"
tipo: decisión
tags:
  - tfg
  - llm
  - validacion
  - casos-de-uso
  - rechazo
  - alcance
contexto: "Cierre del catálogo de casos de borde del módulo de chat LLM del visor MeteoVisor. Recoge la Sección 6 del documento de partida, ajustada al alcance real del prototipo, para asegurar que el asistente nunca improvisa cuando el dato no existe."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada del cierre del módulo de chat LLM y del documento de partida del TFG"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-12"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar si los textos exactos de rechazo se incluirán en un anexo de la memoria."
---

# Casos de borde del chat LLM: rechazo controlado y redirección

## Contenido
El módulo de chat LLM tiene una política explícita para los casos de borde recurrentes. El system prompt enumera estos patrones para que el asistente los identifique y responda con **rechazo controlado o redirección**, nunca con invención.

### 1. Capa no disponible
Si el usuario pide activar o consultar una capa que no existe en el catálogo (por ejemplo `effis_focos`, ver [[effis-fuera-de-alcance-en-catalogo-de-tools-llm]]), el asistente **rechaza explícitamente** y ofrece **la alternativa más cercana disponible** (por ejemplo capa FIRMS).

### 2. Variable no observada
Si el usuario pide una medición meteorológica que el visor no almacena (*viento*, *temperatura*, *precipitación* puntual), el asistente **redirige a aviso AEMET** vía `queryAlerts` (ver [[redireccion-variables-no-observadas-a-avisos-aemet]]) y explicita que la respuesta no son mediciones, sino avisos CAP.

### 3. Fecha fuera de cobertura
La cobertura temporal del histórico FIRMS persistido es **2025-05-01 a 2025-08-31** (ver [[umbrales-por-defecto-tools-llm-meteovisor]]). Si la consulta pide datos fuera de ese rango, el asistente **declara el rango disponible** y propone reformular la consulta dentro de la ventana.

### 4. Consulta ambigua
Cuando la consulta admite varios significados razonables (radio no especificado, ventana temporal vaga), el asistente **pide aclaración** o aplica los **defaults explícitos** del catálogo (5 km para `firesNearPopulation`, últimas 24 h para vigencia de avisos) **anunciándolos en la respuesta**.

### 5. Consulta predictiva
Si la consulta tiene componente de predicción (*"¿lloverá mañana?"*, *"¿qué riesgo de incendio habrá la semana que viene?"*), el asistente **rechaza** y **remite a las fuentes oficiales** (AEMET para meteorología, EFFIS FWI/DC para peligro de incendio), porque el visor no genera predicción.

### Patrón común
Los cinco casos comparten estructura:
1. Identificar el patrón del caso de borde.
2. Rechazar o redirigir explícitamente, sin improvisar.
3. Ofrecer la alternativa cercana cuando exista.
4. Citar la limitación de forma comprensible para el usuario no técnico.

Esto cubre directamente RF-63 (limitación a capacidades autorizadas), RF-65 (validación), RF-69 (datos reales), RF-70 (indicación de incertidumbre) y RF-71 (no decisiones operativas).

## Datos explícitos
- Los cinco casos de borde están enumerados en el system prompt.
- Cobertura temporal del histórico FIRMS: 2025-05-01 a 2025-08-31.
- Default de radio en proximidad: 5 km.
- Default de ventana de vigencia: últimas 24 h.
- El asistente nunca genera predicción.

## Datos inferidos
- Cada caso de borde admite tests automáticos de regresión específicos.
- La política sirve también como argumento de defensa frente al tribunal sobre robustez y trazabilidad.

## Datos faltantes o ambiguos
- Textos exactos de cada mensaje de rechazo.
- Set de pruebas reales por categoría (capa, variable, fecha, ambigüedad, predicción) con resultados.
