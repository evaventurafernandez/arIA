---
id: TFG-20260503-representacion-temporal-acumulada-burnt-area
título: "Representación temporal diaria y acumulada de áreas quemadas"
tipo: decisión
tags:
  - tfg
  - burnt-area
  - copernicus
  - histórico
  - visor-gis
  - interfaz
contexto: "Decisión de interfaz y backend para añadir al visor del TFG una representación acumulada de áreas quemadas históricas junto a la representación diaria ya existente."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia basada en la implementación realizada en el repositorio del visor"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-03"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "uso académico interno; pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría formal de la decisión técnica."
  - "Confirmar si la memoria debe describir el acumulado como geometría aproximada derivada de teselas PNG o como visualización operativa del raster diario."
---

# Representación temporal diaria y acumulada de áreas quemadas

## Contenido
Se añadió al visor una opción para consultar las áreas quemadas históricas de Copernicus CLMS en dos modos temporales: `Diario` y `Acumulado`. La activación de la capa queda separada de la selección del modo de representación. La fila `Áreas quemadas Copernicus` permite activar o desactivar la capa, mientras que dos botones independientes permiten elegir si la barra temporal muestra solo el día seleccionado o la suma visual de los días anteriores hasta esa fecha.

La decisión final fue mantener la misma metodología visual en ambos modos. El modo diario ya no se mostraba como raster visible directo, sino como un localizador vectorial aproximado derivado de los píxeles no transparentes de las teselas PNG. Para evitar incoherencias visuales, el modo acumulado se adaptó al mismo criterio: el backend genera un `FeatureCollection` GeoJSON acumulado con las geometrías de todos los días con teselas hasta la fecha seleccionada, y el frontend lo pinta con el mismo estilo naranja que el modo diario.

Esta decisión corrigió un problema detectado durante la primera integración: al hacer visible la tesela raster acumulada aparecía un fondo blanquecino no deseado. La solución fue apagar el raster en ambos modos (`opacity = 0`) y representar también el acumulado mediante geometrías localizadoras. Así, la capa conserva continuidad visual y evita que una decisión técnica de composición PNG afecte al aspecto final del mapa.

En backend, el endpoint de teselas de `burnt area` acepta el parámetro `mode=daily|cumulative`, pero la representación principal del visor para acumulado se apoya en el endpoint de localizador, también ampliado con `mode=cumulative`. En ese modo, el backend recorre las fechas disponibles hasta la fecha seleccionada, reutiliza la vectorización diaria de teselas no vacías y devuelve una colección acumulada con metadatos como número de fechas incluidas, número de geometrías y conteo aproximado de píxeles.

En frontend, el estado de la capa se gestiona de forma independiente del modo temporal. Si la capa está apagada, no se muestra ninguna geometría. Si está encendida, el modo `Diario` solicita el localizador de la fecha actual de la línea temporal, y el modo `Acumulado` solicita el localizador acumulado hasta esa fecha. El resumen de la barra histórica también cambia de etiqueta para distinguir `BA` diaria de `BA acum.` y utiliza la suma acumulada de hectáreas publicada en la serie temporal.

## Datos explícitos
- El usuario pidió una opción de áreas quemadas históricas acumuladas junto a la existente.
- La opción debía permitir que los días se fueran sumando día tras día.
- Se pidió usar un modelo de botón similar al selector `Todos/Activos` de avisos AEMET.
- Después se corrigió la interfaz para separar activación/desactivación de capa y selección `Diario/Acumulado`.
- Se corrigió el acumulado para que usara la misma metodología de visualización que el diario.
- Se eliminó el fondo blanquecino causado por la representación raster visible del acumulado.
- La implementación afecta a `frontend/index.html`, `frontend/style.css`, `frontend/app.js` y `main.py`.

## Datos inferidos
- La nota se clasifica como `decisión` porque fija un criterio técnico y visual para el visor.
- La ubicación temática principal es `07-historico-y-base-de-datos/`, ya que el añadido trabaja sobre la serie histórica temporal de `burnt area`.
- La fuente se considera elaboración propia porque procede de decisiones e implementación interna del proyecto, no de una fuente externa.

## Datos faltantes o ambiguos
- Autoría formal de la decisión técnica.
- Nivel de detalle con el que se explicará en la memoria la vectorización aproximada a partir de teselas PNG.
