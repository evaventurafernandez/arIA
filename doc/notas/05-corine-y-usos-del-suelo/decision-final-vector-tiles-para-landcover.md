---
id: TFG-20260421-decision-final-vector-tiles-para-landcover
título: "Decisión final de usar vector tiles para landcover"
tipo: decisión
tags:
  - tfg
  - corine
  - vector-tiles
  - mvt
  - rendimiento
  - visor-gis
contexto: "Decisión de arquitectura para evolucionar la visualización de la capa landcover/CORINE del visor GIS web del TFG desde GeoJSON por bbox hacia vector tiles."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-04-21"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría de la nota"
---

# Decisión final de usar vector tiles para landcover

## Contenido
Se adopta `vector tiles` como solución de publicación para la capa `landcover` del visor web. La razón principal es que ofrece una vía más adecuada para renderizar geometrías numerosas y densas con mejor rendimiento que el enfoque anterior basado en GeoJSON construido por `bbox`.

La implementación realizada en esta fase utiliza `MVT` servido desde el backend FastAPI sobre una publicación derivada en PostGIS (`pub.landcover_mvt_source`). El frontend sigue en Leaflet, pero pasa a renderizar la capa con `Leaflet.VectorGrid`.

## Motivos de la decisión
- El render por `bbox` con GeoJSON obligaba a construir y transferir respuestas grandes.
- La agregación temática por clase en tiempo real resultaba costosa en ventanas medias o amplias.
- Los `vector tiles` permiten servir solo las teselas visibles.
- El nivel de detalle puede ajustarse mejor al zoom.
- El navegador recibe fragmentos más pequeños y manejables que un `FeatureCollection` grande.
- La solución encaja con la arquitectura de datos ya adoptada: `PostGIS` como store maestro y `pub` como nivel de publicación optimizado.

## Ventajas observadas
- Mejora clara del patrón de renderizado en cliente.
- Separación más limpia entre modelo canónico (`core`) y publicación para visualización.
- Base técnica más adecuada para evolucionar a estrategias de caché o publicación especializada.
- Mejor alineación con una arquitectura GIS web moderna.

## Implementación actual
- Fuente de datos para tiles: `pub.landcover_mvt_source`
- Formato de publicación: `MVT` (`application/vnd.mapbox-vector-tile`)
- Servicio actual: endpoint FastAPI propio
- Cliente actual: `Leaflet.VectorGrid`
- Se mantiene `pub.landcover_filtered` como salida GeoJSON agregada de compatibilidad

## Evolución futura prevista
Aunque la decisión final del TFG es usar `vector tiles` para la renderización de `landcover`, queda abierta como línea posterior la posibilidad de introducir:
- `pg_tileserv` como servidor especializado de MVT
- y más adelante `GeoServer` como pieza de interoperabilidad GIS más general

La previsión es que esa evolución quede fuera del alcance inmediato del TFG y se aborde después, cuando interese ampliar la publicación estándar de capas y la integración con servicios OGC.

## Datos explícitos
- Se ha elegido `vector tiles` como estrategia final de renderizado para `landcover`.
- La motivación principal es la mejora de rendimiento de visualización.
- La implementación actual usa `MVT` y `Leaflet.VectorGrid`.
- `GeoServer` se deja como línea futura, no como solución inmediata del TFG.

## Datos inferidos
- La decisión afecta a la arquitectura de publicación, no a la ingesta base.
- El siguiente refinamiento técnico probable será mejorar LOD, caché o externalizar el servicio de tiles.

## Datos faltantes o ambiguos
- Confirmación de autoría de la nota.
- Decisión futura concreta entre `pg_tileserv`, `GeoServer` u otra pieza de publicación adicional tras el TFG.
