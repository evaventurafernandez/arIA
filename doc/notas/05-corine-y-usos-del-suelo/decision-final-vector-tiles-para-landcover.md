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
  - optimizacion
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

En una iteración posterior, ya con `vector tiles` activos, se detectó una incidencia de rendimiento adicional. La estrategia `MVT` seguía siendo correcta, pero la explotación concreta del servicio necesitaba una segunda optimización: reducir el coste de las consultas auxiliares y separar mejor la publicación de bajo zoom de la publicación detallada.

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
- Fuente de datos para tiles de detalle: `pub.landcover_mvt_source`
- Fuente de datos para tiles de bajo zoom: `pub.landcover_mvt_class_source`
- Formato de publicación: `MVT` (`application/vnd.mapbox-vector-tile`)
- Servicio actual: endpoint FastAPI propio
- Cliente actual: `Leaflet.VectorGrid`
- Se mantiene `pub.landcover_filtered` como salida GeoJSON agregada de compatibilidad
- El backend conserva en memoria el estado publicado de `landcover` y cachea temporalmente los metadatos de capa

## Incidencia de rendimiento y solución aplicada
Tras la adopción inicial de `vector tiles`, apareció una segunda incidencia: el visor seguía cargando con demasiada lentitud en peticiones de `landcover`, especialmente al resolver metadatos de capa y al pedir teselas de zoom bajo.

En la revisión técnica quedaron registrados varios costes altos:
- una consulta de validación sobre `core.landcover_polygon` (`COUNT(*)` y `MAX(canonicalized_at)`) tardaba aproximadamente `11,3 s`;
- la consulta de metadatos sobre `pub.landcover_filtered` y `pub.landcover_mvt_source` tardaba aproximadamente `8,2 s`;
- una tesela detallada representativa en `z=6/x=30/y=24` llegaba a aproximadamente `20,7 s`, con unas `13.713` geometrías candidatas.

El problema no invalidaba la decisión de usar `MVT`, pero sí mostraba que la explotación concreta seguía cargando demasiado trabajo en tiempo de petición. La solución aplicada combinó ajustes en backend y en publicación:
- se introdujo una caché en memoria para el estado publicado de `landcover`;
- se añadió una caché temporal para los metadatos de capa servidos por FastAPI;
- se creó `pub.landcover_mvt_class_source` como publicación agregada por clase para bajo zoom;
- y el visor pasó a usar la publicación agregada hasta `z=8`, reservando `pub.landcover_mvt_source` para `z>=9`.

Como verificación operativa posterior, al arrancar manualmente `uvicorn` en el entorno de trabajo la respuesta del visor pasó a ser fluida y los tiempos observados se consideraron correctos para el uso previsto en el TFG.

## Evolución futura prevista
Aunque la decisión final del TFG es usar `vector tiles` para la renderización de `landcover`, queda abierta como línea posterior la posibilidad de introducir:
- `pg_tileserv` como servidor especializado de MVT
- y más adelante `GeoServer` como pieza de interoperabilidad GIS más general

La previsión es que esa evolución quede fuera del alcance inmediato del TFG y se aborde después, cuando interese ampliar la publicación estándar de capas y la integración con servicios OGC.

## Datos explícitos
- Se ha elegido `vector tiles` como estrategia final de renderizado para `landcover`.
- La motivación principal es la mejora de rendimiento de visualización.
- La implementación actual usa `MVT` y `Leaflet.VectorGrid`.
- La publicación actual separa `pub.landcover_mvt_class_source` para zoom bajo y `pub.landcover_mvt_source` para zoom medio y alto.
- Se añadieron cachés en FastAPI para evitar recalcular en cada petición el estado publicado y los metadatos de `landcover`.
- En la revisión de rendimiento se registraron consultas de entre `8,2 s` y `20,7 s` antes de la optimización operativa.
- Tras arrancar manualmente `uvicorn`, el visor respondió con tiempos considerados correctos.
- `GeoServer` se deja como línea futura, no como solución inmediata del TFG.

## Datos inferidos
- La decisión afecta a la arquitectura de publicación, no a la ingesta base.
- La lentitud observada no dependía de un único factor, sino de la combinación entre consultas pesadas, estrategia de publicación por zoom y condiciones de ejecución del servicio.
- El siguiente refinamiento técnico probable será consolidar una estrategia de benchmark reproducible y, si hiciera falta, externalizar el servicio de tiles.

## Datos faltantes o ambiguos
- Confirmación de autoría de la nota.
- Medición comparativa cerrada que aísle cuánto de la mejora final proviene del arranque manual de `uvicorn` y cuánto de la optimización de consultas/publicaciones.
- Decisión futura concreta entre `pg_tileserv`, `GeoServer` u otra pieza de publicación adicional tras el TFG.
