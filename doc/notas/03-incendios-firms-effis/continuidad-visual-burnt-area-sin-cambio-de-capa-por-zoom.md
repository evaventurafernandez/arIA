---
id: TFG-20260427-continuidad-visual-burnt-area-sin-cambio-de-capa-por-zoom
título: "Continuidad visual de burnt area sin cambio de capa por zoom"
tipo: decisión
tags:
  - tfg
  - burnt-area
  - incendios
  - simbología
  - leaflet
  - zoom
  - frontend
contexto: "Nota de trazabilidad sobre el ajuste de la simbología de la capa temporal diaria de áreas quemadas para mantener una representación estable en todos los zooms del visor."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-04-27"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "uso académico interno; pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría de la nota."
---

# Continuidad visual de burnt area sin cambio de capa por zoom

## Contenido
Esta nota documenta un ajuste cartográfico del frontend para la capa temporal diaria de `burnt area`. El objetivo no fue cambiar los datos publicados ni el rango temporal, sino hacer más coherente la percepción visual del usuario al navegar por el mapa.

La situación anterior mezclaba dos representaciones distintas según el nivel de zoom. Por debajo de `zoom 11` el visor enseñaba un localizador vectorial derivado del raster; a partir de `zoom 11` pasaba a las teselas ráster diarias. Aunque ambas vistas procedían del mismo producto, el salto visual hacía que pareciera que el visor estaba cambiando de fuente o de resolución temática.

## Situación anterior
- La capa diaria de `burnt area` cambiaba de representación al cruzar `zoom 11`.
- El localizador vectorial y el raster no compartían exactamente la misma presencia visual.
- Tanto las teselas ráster como la geometría del localizador aplicaban sombras tipo `drop-shadow`.
- Ese tratamiento generaba un halo alrededor de los píxeles o celdas dibujadas.

## Cambios aplicados
- Se eliminó el halo visual quitando las sombras CSS de la capa ráster y del localizador.
- Se fijó una única simbología del localizador para todos los zooms, sin variar grosor ni opacidad según escala.
- Se dejó el localizador de `burnt area` como representación visible estable en todos los niveles de zoom.
- Se desactivó en la práctica el cambio de representación en `zoom 11`, de modo que el usuario no percibe un salto de capa al acercarse.

## Decisiones de implementación
- Se mantuvo el color temático ya definido para `burnt area`, pero con una presentación más limpia y plana.
- El raster diario sigue existiendo en el flujo temporal de la capa, pero deja de ser la representación visible que sustituyó al localizador al superar `zoom 11`.
- La geometría visible sigue apoyándose en el nivel de referencia ya usado para el localizador, con lo que la lectura visual permanece consistente durante el zoom.

## Justificación del cambio
- La prioridad de esta iteración es la continuidad visual, no la alternancia entre dos expresiones cartográficas del mismo dato.
- Evitar el cambio de capa reduce la sensación de “estar viendo otro dataset” al acercarse sobre la misma fecha.
- Quitar sombras y halos mejora la lectura de manchas quemadas pequeñas y evita un efecto de resplandor artificial.

## Limitaciones asumidas
- Este ajuste prioriza la estabilidad visual frente a enseñar una segunda representación distinta al ampliar.
- Si más adelante interesa comparar explícitamente localizador y ráster diario, convendría exponerlo como modos separados y no como cambio automático por zoom.

## Relación con otras notas
- Esta nota complementa `doc/notas/07-historico-y-base-de-datos/proceso-ingesta-burnt-area-v4-espana-mayo-agosto-2025.md`, que documenta la ingesta y publicación del producto diario.
- También encaja en la línea de decisiones de representación del visor, pero aquí el foco está en la coherencia cartográfica de `burnt area`.

## Datos explícitos
- Existía un umbral en `zoom 11` que alternaba la representación visible de `burnt area`.
- La simbología aplicada mostraba sombras y halo alrededor de los píxeles o celdas dibujadas.
- El cambio solicitado ha sido mantener la misma lectura visual en todos los zooms.

## Datos inferidos
- La continuidad visual es más importante en este caso que enseñar automáticamente dos modos de representación.
- Para la defensa del TFG, una simbología estable facilita explicar que el dato no cambia al hacer zoom.

## Datos faltantes o ambiguos
- Confirmación de autoría de la nota.
- Decisión futura sobre si el ráster diario debe recuperarse como modo opcional e independiente.
