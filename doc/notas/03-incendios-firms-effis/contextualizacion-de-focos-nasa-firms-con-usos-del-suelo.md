---
id: TFG-20260422-contextualizacion-de-focos-nasa-firms-con-usos-del-suelo
título: "Contextualización de focos NASA FIRMS con usos del suelo"
tipo: decisión
tags:
  - tfg
  - firms
  - incendios
  - usos-del-suelo
  - ign
  - sidebar
  - leaflet
contexto: "Nota de trazabilidad sobre la integración entre los focos NASA FIRMS del visor y la consulta puntual de usos del suelo del IGN, tanto en mapa como en el listado lateral."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-04-22"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría de la nota."
---

# Contextualización de focos NASA FIRMS con usos del suelo

## Contenido
Esta nota documenta una mejora de interacción importante para el TFG: pasar de mostrar los focos `NASA FIRMS` como puntos aislados a acompañarlos de contexto territorial inmediato, indicando sobre qué uso del suelo cae cada foco y permitiendo inspeccionar el polígono asociado directamente en el mapa.

El objetivo no era cambiar la fuente de focos, sino enriquecer su interpretación. Un punto de `FIRMS` informa de coordenadas, tiempo y potencia radiativa, pero no explica por sí mismo si cae sobre bosque de coníferas, mosaico agrícola, matorral o combinación de vegetación. Para la narrativa del visor y para la defensa del TFG, esa contextualización resulta mucho más útil que dejar el punto desacoplado de su entorno.

## Situación anterior
- Los focos `NASA FIRMS` se mostraban con símbolo, `FRP`, fecha, hora y satélite.
- Al hacer clic en un foco se activaba contexto relacionado de incendio, pero el usuario tenía que inferir visualmente el uso del suelo mirando el mapa.
- Las cards del sidebar no incluían ninguna referencia explícita al uso del suelo.
- El primer resaltado del polígono asociado llegó a existir, pero su visibilidad dependía de resolver correctamente la geometría devuelta por el servicio puntual.

## Cambios aplicados
- Al hacer clic en un foco `NASA FIRMS` del mapa, el visor centra la vista, activa automáticamente `effis_fwi` y `corine_wms`, y lanza la consulta puntual de usos del suelo.
- Al hacer clic en una card de foco en el sidebar, se ejecuta el mismo flujo de recentrado y activación automática del `WMS`.
- El popup asociado al punto muestra la clase de uso del suelo devuelta por `GetFeatureInfo`.
- El polígono correspondiente se resalta en el mapa con un borde más fino y color `cyan` (`#00f0f0`) para que destaque sin competir demasiado con la cartografía de fondo.
- Las cards de `NASA FIRMS` incluyen una línea adicional del tipo `Cae en: <uso del suelo>`.

## Proceso seguido
1. Primero se resolvió el flujo de consulta puntual y resaltado del polígono a partir del clic en mapa.
2. Después se detectó que el polígono no se veía bien porque la geometría necesitaba normalización de CRS antes de dibujarse.
3. Una vez corregido el resaltado, se ajustó el estilo visual: se pasó de un borde más grueso y magenta a un trazo más fino en `cyan`, menos invasivo pero claramente distinguible.
4. Con el flujo de mapa ya estable, se extendió la misma lógica a los focos `NASA FIRMS`.
5. Finalmente, se incorporó la consulta de uso del suelo al listado lateral, añadiendo una carga en segundo plano con caché para no repetir la misma petición muchas veces.

## Decisiones de implementación
- Para las cards del sidebar no se reutiliza ciegamente el zoom actual del usuario, sino una escala de consulta fijada explícitamente (`zoom 16` con una ventana `101x101`). La razón es hacer más estable la clasificación puntual entre cards y evitar que la respuesta dependa de cómo estuviera colocado el mapa en ese instante.
- Las consultas de usos del suelo para focos se cachean por coordenada redondeada y se limitan en concurrencia para no cargar innecesariamente el servicio externo.
- El resaltado del polígono solo se dibuja cuando hay interacción focalizada en el mapa; en las cards se muestra el texto contextual y, cuando el usuario entra en una, se ejecuta además la navegación cartográfica asociada.

## Justificación del cambio
- Añadir el uso del suelo a cada foco convierte un punto aislado en un evento geográfico contextualizado.
- La mejora refuerza la lectura temática del visor: no solo dónde hay un foco, sino en qué tipo de superficie aparece.
- La integración reduce la distancia entre mapa y listado lateral, lo que mejora la experiencia de uso y también la capacidad de explicar el prototipo en la memoria o en una defensa oral.
- Usar el `WMS` oficial del `IGN` para esta contextualización mantiene coherencia con la cartografía visible al usuario.

## Limitaciones asumidas
- La etiqueta `Cae en:` sigue siendo una clasificación puntual, no un análisis espacial completo del entorno del incendio.
- La información depende de la disponibilidad del servicio externo y de la estrategia de escala elegida para la consulta de las cards.
- La respuesta mostrada en la card debe entenderse como contexto cartográfico del punto, no como delimitación de un perímetro de incendio.

## Relación con otras notas
- Esta nota depende conceptualmente de `evolucion-consulta-puntual-landcover-de-core-a-getfeatureinfo-ign.md`, porque la contextualización de focos se apoya en ese cambio de fuente puntual.
- Complementa las notas ya existentes sobre `CORINE` y visualización, pero se centra en la integración concreta entre `FIRMS` y usos del suelo dentro del flujo de interacción del visor.

## Datos explícitos
- Los focos `NASA FIRMS` ya estaban integrados en el visor antes de este cambio.
- Las cards del sidebar no mostraban el tipo de uso del suelo.
- Se añadió activación automática de `corine_wms` al interactuar con focos y cards.
- Se añadió una línea textual con el uso del suelo en cada card de foco.
- El polígono resaltado pasó a usar un borde más fino y `cyan`.
- Se introdujo caché para evitar consultas repetidas por foco.

## Datos inferidos
- Esta mejora aporta más valor analítico al TFG que una simple mejora estética del popup.
- La escala fija para las cards es una decisión de estabilidad funcional, no una verdad cartográfica universal.
- El siguiente paso natural, si el TFG siguiera creciendo, sería cruzar focos no solo con la clase puntual sino también con otras capas de exposición o proximidad.

## Datos faltantes o ambiguos
- Confirmación de autoría de la nota.
- Criterio final para decidir si conviene documentar en la memoria el `zoom 16` como parámetro estable o como detalle interno de implementación.
