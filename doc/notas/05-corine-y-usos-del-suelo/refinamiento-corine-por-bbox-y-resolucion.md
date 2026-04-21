---
id: TFG-20260420-refinamiento-corine-por-bbox-y-resolucion
título: "Refinamiento de CORINE por bbox y resolución"
tipo: decisión
tags:
  - tfg
  - corine
  - usos-del-suelo
  - postgis
  - fastapi
  - rendimiento
contexto: "Nota de trabajo sobre la evolución del servicio REST de landcover/CORINE para mostrar más detalle geométrico en el visor HTML sin cargar todo el país en cada petición."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-04-20"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría de la nota"
---

# Refinamiento de CORINE por bbox y resolución

## Contenido
Se ha trabajado en la sustitución del flujo antiguo basado en `data/landcover.geojson` por un servicio REST que consulta PostGIS. El objetivo inmediato ha sido mejorar el detalle de los polígonos CORINE cuando el usuario se acerca en el visor HTML, evitando cargar toda España en cada petición.

El resultado actual es funcional pero todavía no óptimo. En términos prácticos, la experiencia en `zoom 12` es aceptable, mientras que en `zoom 10` sigue siendo lenta en ventanas relativamente amplias.

## Pasos dados
- Se sustituyó el endpoint antiguo que servía un fichero estático por acceso a `PostgreSQL + PostGIS` desde `main.py`.
- Se mantuvo el contrato del frontend para seguir usando `properties.label` y `properties.color`.
- Se añadió un endpoint de detalle espacial por ventana visible: `GET /api/landcover/features?bbox=...`.
- El frontend dejó de pedir toda la capa y pasó a refrescar CORINE por `bbox` y `zoom` al mover o ampliar el mapa.
- Se introdujo refresco con `debounce` y cancelación de peticiones anteriores para evitar solapes innecesarios.
- Se probó una simplificación variable según zoom y tamaño de la zona visible.
- Después se refinó la estrategia para calcular la simplificación con la resolución real del mapa visible, enviando desde el HTML:
  - `bbox`
  - `zoom`
  - `width`
  - `height`
- En backend se calculó una métrica `units_per_pixel` para derivar la tolerancia geométrica de forma menos arbitraria.
- Se detectó que una versión intermedia del endpoint recortaba por número de features individuales de `core`, lo que provocaba que faltasen clases de uso del suelo en ventanas amplias.
- Se corrigió el endpoint para volver a construir la respuesta temática por clase dentro del `bbox`.
- Se detectó además un fallo de PostgreSQL por ejecución paralela de la consulta espacial (`could not attach to dynamic shared area`), que se mitigó desactivando el paralelismo solo para esa consulta.

## Estado actual observado
- La mejora visual existe: al reducir la zona visible, los polígonos dejan de verse tan facetados.
- `zoom 12` ofrece un comportamiento razonable.
- `zoom 10` sigue siendo lento cuando la ventana visible abarca bastante superficie.
- El problema ya no es solo de simplificación visual, sino de coste de agregación espacial en tiempo real.

## Causa técnica del cuello de botella actual
- El endpoint espacial trabaja sobre `core.landcover_polygon`.
- Para responder temáticamente por clases dentro del `bbox`, recorta geometrías, las simplifica y luego hace una agregación/dissolve por clase.
- Esa agregación es correcta desde el punto de vista funcional, pero resulta costosa en vistas amplias o medias.
- En consecuencia, la calidad temática ha mejorado, pero a costa de tiempo de respuesta.

## Posibles soluciones

### 1. Mantener el endpoint actual y ajustar la generalización por resolución
Seguir afinando la tolerancia geométrica a partir de `bbox`, `width` y `height`, con reglas más suaves o más agresivas según el número de vértices y la superficie visible.

Ventaja:
- cambio pequeño sobre la arquitectura actual.

Limitación:
- no elimina el coste de disolver por clase en tiempo real.

### 2. Crear niveles de detalle publicados en PostGIS
Generar una o varias capas derivadas/materialized views para explotación:
- vista muy general
- vista intermedia
- vista detallada

El backend elegiría la capa adecuada según resolución o zoom.

Ventaja:
- reduce mucho el coste en tiempo de consulta.

Limitación:
- añade complejidad de mantenimiento y refresco.

### 3. Publicar una capa temática preagregada por clase y por nivel de detalle
En lugar de disolver en cada petición, preparar previamente geometrías ya agregadas por clase para distintos LOD.

Ventaja:
- es una solución coherente con una arquitectura profesional de publicación.

Limitación:
- requiere diseñar y mantener una estrategia clara de LOD.

### 4. Vector tiles o servicio especializado
Dar el salto a teselas vectoriales o a un servicio especializado como `GeoServer`, `pg_tileserv` o similar.

Ventaja:
- es la solución más escalable y profesional para visualización eficiente.

Limitación:
- no es el camino más corto; requiere más infraestructura y publicación de capas.

## Resumen comparativo: GeoServer vs vector tiles
La comparación útil para este caso no es exactamente entre tecnologías equivalentes, porque `GeoServer` es un servidor GIS completo y `vector tiles` es una estrategia de publicación/servicio orientada a mapas web. Aun así, para el problema actual de rendimiento del visor la comparación práctica es clara:

- `GeoServer` encaja mejor cuando se prioriza interoperabilidad OGC, publicación estándar de capas, estilos centralizados y una plataforma GIS más general.
- `vector tiles` encaja mejor cuando se prioriza rendimiento, escalabilidad y navegación fluida en un visor web interactivo.

Conclusiones resumidas:
- para optimizar la visualización en el HTML, `vector tiles` es la opción más adecuada;
- para una línea futura de publicación GIS más completa e interoperable, `GeoServer` sigue siendo una opción valiosa;
- `GeoServer` probablemente no resolvería por sí solo de la forma más eficiente el cuello de botella actual del visor, mientras que `vector tiles` sí ataca mejor el problema de servir solo lo visible y con el nivel de detalle apropiado.

## Decisión provisional para el proyecto
Se adopta como línea preferente para el proyecto la evolución hacia `vector tiles` como mecanismo de optimización del servicio de mapas, por encajar mejor con:
- el uso desde HTML/Leaflet u otro cliente web moderno;
- la necesidad de servir solo las zonas visibles;
- la gestión natural del nivel de detalle por zoom;
- la mejora esperable de rendimiento frente al `bbox + dissolve` dinámico actual.

`GeoServer` se mantiene como línea futura probable, pero no como siguiente paso inmediato del TFG. La previsión es considerarlo después del TFG, cuando interese ampliar la interoperabilidad GIS, la publicación estándar de capas y una arquitectura más general de servicios geoespaciales.

### 5. Separar claramente capa temática y capa de detalle
Usar:
- una capa temática simplificada y muy rápida para vista general
- una capa de detalle por feature o por clase solo cuando el usuario se acerca lo suficiente

Ventaja:
- alinea rendimiento y necesidad real de detalle.

Limitación:
- exige una transición clara en frontend y backend.

## Recomendación provisional
La solución más razonable a corto plazo parece ser combinar:
- cálculo de simplificación por resolución real
- una capa publicada preagregada para vista general o intermedia
- y dejar `core` para detalle cuando el zoom ya sea suficientemente alto

Eso permitiría conservar el detalle visual conseguido al acercarse sin obligar a hacer una agregación pesada por clase en cada ventana amplia.

## Datos explícitos
- El flujo antiguo servía un `GeoJSON` estático.
- El backend REST se ha migrado a PostGIS.
- El visor HTML ya pide la capa por `bbox`.
- Se ha introducido `width/height` para calcular simplificación basada en resolución.
- `zoom 12` funciona aceptablemente.
- `zoom 10` sigue siendo lento.

## Datos inferidos
- La siguiente mejora importante no pasa por seguir ajustando solo parámetros, sino por introducir una estrategia de publicación por niveles de detalle.
- Esta nota documenta una decisión técnica provisional y sirve como recordatorio para la siguiente iteración de arquitectura.

## Datos faltantes o ambiguos
- Confirmación de autoría de la nota.
- Decisión final sobre si el siguiente paso será una materialized view por LOD, una capa temática intermedia o vector tiles.
