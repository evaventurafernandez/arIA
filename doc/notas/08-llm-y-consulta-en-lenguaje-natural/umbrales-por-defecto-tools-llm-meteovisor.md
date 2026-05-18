---
id: TFG-20260512-umbrales-por-defecto-tools-llm-meteovisor
título: "Umbrales por defecto de las tools del chat LLM y cobertura temporal"
tipo: decisión
tags:
  - tfg
  - llm
  - tool-calling
  - firms
  - dbscan
  - umbrales
  - exposicion-poblacional
contexto: "Decisión de diseño del módulo de chat LLM del visor MeteoVisor. Fija los valores por defecto de los parámetros sensibles de las tools de análisis y la ventana temporal de cobertura inyectada en el prompt."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada del cierre del módulo de chat LLM y del documento de partida del TFG"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-18"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar si los valores DBSCAN se citan en la memoria con la justificación empírica del verano 2025."
---

# Umbrales por defecto de las tools del chat LLM y cobertura temporal

## Contenido
Tres parámetros sensibles del catálogo de tools del chat LLM se fijan con valores por defecto explícitos. El asistente no debe inventarlos y, si el usuario no los aporta, los aplica anunciándolos en la respuesta:

- `firesNearPopulation.distance_m = 5000` (5 km). Origen: documento de partida del TFG, donde la proximidad operativa retrospectiva "focos junto a núcleos" se define con ese radio.
- `activeFiresNearPopulation.distance_m = 2000` (2 km) y `population_max = 5000`. Origen: caso de uso operativo añadido para focos activos: "núcleos de menos de 5.000 habitantes a menos de 2 km de un foco activo". El umbral de población se interpreta como límite superior exclusivo (`habitantes < 5000`).
- `firmsHotspotAnalysis.eps_meters = 1500` y `min_points = 4`. Origen: validación empírica sobre el histórico FIRMS persistido para España (mayo–agosto 2025). Con esos valores el clustering DBSCAN detecta concentraciones reales sin fragmentar episodios grandes ni unir incendios independientes. Valores menores fragmentan; valores mayores fusionan.
- Cobertura temporal del histórico FIRMS: **2025-05-01 a 2025-08-31**. El rango se **inyecta dinámicamente en el prompt de sistema** desde la API, no se hardcodea, para que el asistente rechace fechas fuera de cobertura sin necesidad de redespliegue cuando la base se amplíe.

Relacionado con [[proceso-creacion-historico-focos-nasa-firms-espana-mayo-agosto-2025]] (proceso de ingesta del histórico) y con [[ideas-operaciones-llm-local-en-visor-meteovisor]] (Nivel 3 del catálogo de tools).

## Datos explícitos
- `firesNearPopulation.distance_m=5000 m` por defecto.
- `activeFiresNearPopulation.distance_m=2000 m` y `population_max=5000` por defecto.
- `firmsHotspotAnalysis.eps_meters=1500 m` y `min_points=4` por defecto.
- Cobertura temporal del histórico FIRMS persistido: 2025-05-01 a 2025-08-31.
- La cobertura temporal se inyecta dinámicamente en el system prompt.
- Los valores DBSCAN se han probado sobre el histórico FIRMS verano 2025.

## Datos inferidos
- El usuario puede sobrescribir los umbrales por consulta; el valor por defecto solo aplica si no los proporciona.
- La inyección dinámica del rango evita prompts desactualizados cuando se amplíe el histórico.
- Los defaults reducen el espacio de respuestas no reproducibles del modelo.

## Datos faltantes o ambiguos
- Documentar en la memoria del TFG la pequeña tabla de pruebas DBSCAN (eps×min_points) y por qué (1500, 4) fue el punto elegido.
- Decidir si se expone al usuario en la UI del chat una pista visible sobre los defaults aplicados.
- Confirmar si el umbral de 2 km para focos activos se mantendrá como caso de uso fijo o será configurable en la memoria como ejemplo parametrizable.
