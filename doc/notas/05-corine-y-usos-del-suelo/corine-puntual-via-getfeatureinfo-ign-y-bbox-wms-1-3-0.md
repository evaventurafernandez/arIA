---
id: TFG-20260512-corine-puntual-via-getfeatureinfo-ign-y-bbox-wms-1-3-0
título: "CORINE puntual desde el chat vía GetFeatureInfo del IGN y bug del bbox en WMS 1.3.0 / EPSG:4326"
tipo: decisión
tags:
  - tfg
  - corine
  - landcover
  - wms
  - ign
  - llm
  - bug-aprendido
contexto: "Decisión de diseño del módulo de chat LLM del visor MeteoVisor sobre cómo resolver consultas puntuales de uso del suelo desde una herramienta del catálogo de tools, y registro del bug aprendido durante la implementación (Fase 3) sobre el orden del bbox en WMS 1.3.0."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada del cierre del módulo de chat LLM, alineada con la evolución previa de la consulta puntual de landcover"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-12"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar la cita formal de la especificación OGC WMS 1.3.0 antes de incluirla en la memoria."
---

# CORINE puntual desde el chat vía GetFeatureInfo del IGN y bug del bbox en WMS 1.3.0 / EPSG:4326

## Contenido
La tool del chat LLM que responde *"qué uso del suelo hay en este punto"* se resuelve mediante **GetFeatureInfo contra el WMS del IGN**, no contra la tabla local `core.landcover_polygon`, a pesar de tener los polígonos persistidos en PostGIS.

Motivo central: **coherencia visual**. Cuando un usuario hace click en el visor, la ficha de landcover que ya recibe proviene de GetFeatureInfo del IGN. Si la tool del chat consultara la tabla PostGIS local, en el límite de polígonos o en zonas con desfase entre la geometría servida por IGN y la persistida localmente la tool podría devolver una clase distinta de la que el usuario ve. Para evitar esa disonancia entre lo visible y lo respondido, **la tool comparte la misma fuente que el click manual**.

Trade-offs aceptados:
- Dependencia del servicio WMS del IGN para la respuesta (ya presente en el visor).
- Mayor latencia que una consulta PostGIS local.
- A cambio se elimina cualquier discrepancia visual entre click manual y respuesta del asistente.

### Bug aprendido en Fase 3 — orden del bbox en WMS 1.3.0 / EPSG:4326

Durante la implementación se encontró un bug significativo: **WMS 1.3.0 combinado con EPSG:4326 exige el bbox en orden `lat,lon` (south, west, north, east)**, no en orden `lon,lat`. La especificación OGC WMS 1.3.0 normaliza el orden de ejes según el CRS declarado: para EPSG:4326 el eje 1 es latitud, no longitud. Pasar el bbox como `lon,lat` devuelve respuestas vacías o erróneas sin lanzar error.

Este detalle vale la pena documentar porque es una fuente recurrente de bugs sutiles en clientes WMS y conviene dejarlo escrito en la memoria del TFG como aprendizaje técnico del visor.

Relacionado con [[evolucion-consulta-puntual-landcover-de-core-a-getfeatureinfo-ign]] y [[decision-final-vector-tiles-para-landcover]].

## Datos explícitos
- La tool de landcover del chat usa GetFeatureInfo del IGN, no la tabla local `core.landcover_polygon`.
- El visor sí dispone de `core.landcover_polygon` persistido.
- WMS 1.3.0 + EPSG:4326 requiere bbox en orden `south, west, north, east`.
- El bug se identificó y corrigió durante la Fase 3 del módulo de chat LLM.

## Datos inferidos
- La coherencia entre click manual y respuesta del asistente prima sobre la latencia y la independencia de servicios externos.
- El bug del bbox afectaba a las primeras versiones de la tool antes de fijar el orden correcto.

## Datos faltantes o ambiguos
- Comportamiento de la tool si el WMS del IGN está caído (fallback a consulta local o respuesta de degradación).
- Referencia exacta de la sección de la especificación OGC WMS 1.3.0 sobre orden de ejes.
