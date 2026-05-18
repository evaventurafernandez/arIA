---
id: TFG-20260518-distancia-focos-activos-nucleos-y-resultados-geojson
título: "Distancia entre focos activos y núcleos: resultados GeoJSON desde tools del chat"
tipo: decisión
tags:
  - tfg
  - llm
  - tool-calling
  - postgis
  - firms
  - nucleos
  - geojson
contexto: "Extensión del catálogo de tools del chat LLM de MeteoVisor para resolver consultas de proximidad entre focos activos NASA FIRMS y núcleos de población del IGN, y para representar los resultados calculados como una capa temporal en el visor sin sobrecargar al LLM."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada de iteraciones sobre el módulo de chat LLM en MeteoVisor"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-18"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar si la memoria citará los identificadores exactos (`activeFiresNearPopulation`, `showGeoJsonResults`, `_compact_result_for_model`)."
---

# Distancia entre focos activos y núcleos: resultados GeoJSON desde tools del chat

## Contenido
Se añade al chat LLM una operación geoespacial ejecutable para responder preguntas como:

> ¿Hay algún núcleo de población de menos de 5.000 habitantes a menos de 2 km de distancia de un foco activo?

La solución evita que el LLM calcule distancias o copie geometrías. El modelo solo invoca una tool; la geometría y las distancias se calculan en backend.

### Tool server-side añadida
La tool **`activeFiresNearPopulation`** cruza los focos NASA FIRMS activos con la capa local `core.nucleos_poblacion_polygon`.

Parámetros principales:

- `distance_m`: distancia máxima en metros. Por defecto, 2.000 m para el caso de uso de exposición inmediata.
- `population_max`: umbral superior exclusivo de habitantes. Por defecto, 5.000.
- `sensor`, `bbox`, `min_frp`, `confidence`: filtros opcionales sobre los focos activos.
- `limit`: máximo de pares foco-núcleo devueltos.

La implementación toma los focos activos del visor, los normaliza como puntos temporales y los cruza con PostGIS:

- `ST_DWithin(f.geom::geography, n.geom::geography, distance_m)` para filtrar por distancia real en metros.
- `ST_Distance(f.geom::geography, n.geom::geography)` para devolver la distancia exacta.
- `LATERAL ... LIMIT 1` para asociar a cada foco el núcleo más cercano que cumple las condiciones.

### Resultado devuelto
La tool devuelve:

- `total_matched`, `returned`, `truncated` y filtros aplicados;
- lista `items` con foco, sensor, FRP, núcleo, habitantes y distancia;
- `map_layers: ["fires", "nucleos"]`;
- `map_geojson`, una `FeatureCollection` temporal con:
  - punto del foco activo;
  - punto representativo del núcleo;
  - línea de distancia entre ambos.

### Acción cliente añadida
Se incorpora la client tool **`showGeoJsonResults`** para que el frontend dibuje resultados calculados por tools server-side como capa temporal sobre Leaflet.

Campos principales:

- `geojson`: `FeatureCollection` de resultados.
- `title`: título breve de la capa temporal.
- `fit`: si debe encuadrar el mapa a los resultados.
- `clear_existing`: si debe borrar resultados temporales anteriores.

En el frontend, la acción pinta puntos y líneas con estilos distintos según `properties.kind` (`fire`, `population`, `distance`) y tooltips derivados de `properties.label`.

### Separación entre payload de mapa y observación al LLM
La primera versión devolvía `map_geojson` completo al LLM en la observación de la tool. En consultas reales con decenas de resultados, esto generaba payloads grandes y podía provocar errores de red en la segunda llamada al LLM.

La decisión final es:

- el GeoJSON completo viaja al frontend como `client_action` (`showGeoJsonResults`);
- el LLM recibe una observación compacta mediante `_compact_result_for_model`;
- la observación conserva `map_geojson_summary` con tipo y número de features;
- si hay muchos `items`, se recortan para el modelo y se añade `items_omitted_from_llm_observation`;
- si el backend encola acciones automáticas, el LLM ve `client_actions_queued`.

Esto mantiene la trazabilidad del cálculo sin convertir al LLM en transporte de geometrías.

### Relación con acciones automáticas del visor
Además de `showGeoJsonResults`, el orquestador ya puede derivar automáticamente:

- `setVisibleLayers({"names":["fires","nucleos"]})` para dejar visibles solo las capas usadas por `activeFiresNearPopulation`;
- `showGeoJsonResults(...)` cuando una server tool devuelve `map_geojson`.

El usuario puede pedir explícitamente "muestra únicamente las capas utilizadas y los resultados", y el sistema responde con el cálculo, la visibilidad de capas y la capa temporal de resultados.

### Límite mantenido: inundabilidad T10
La proximidad foco activo ↔ núcleo sí es ejecutable porque ambas geometrías existen: los focos como puntos y los núcleos como polígonos locales. En cambio, la consulta avisos hidrometeorológicos ↔ zona inundable T10 ↔ núcleos sigue limitada porque la capa T10 procede de un WMS externo de MITECO sin geometría vectorial local en PostGIS.

## Datos explícitos
- `activeFiresNearPopulation` calcula distancias reales en metros con PostGIS.
- La capa de núcleos IGN existe en `core.nucleos_poblacion_polygon`.
- Los focos activos se obtienen desde la fuente FIRMS viva del visor y se convierten en puntos temporales.
- `showGeoJsonResults` pinta resultados temporales GeoJSON en Leaflet.
- El orquestador compacta las observaciones antes de reinyectarlas al LLM para evitar payloads pesados.

## Datos inferidos
- La nota se clasifica en `08-llm-y-consulta-en-lenguaje-natural/` porque documenta el catálogo de tools y el contrato backend-LLM-frontend.
- Tipo `decisión`, ya que registra una elección de arquitectura: geometría al frontend, resumen al LLM.
- El mismo patrón puede reutilizarse para futuras tools espaciales que devuelvan `map_geojson`.

## Datos faltantes o ambiguos
- Confirmar autoría como elaboración propia.
- Decidir si la memoria del TFG explica el detalle de `map_geojson_summary` o solo el principio de compactación.
- Validar con capturas o caso de uso final el comportamiento visual de `showGeoJsonResults`.
