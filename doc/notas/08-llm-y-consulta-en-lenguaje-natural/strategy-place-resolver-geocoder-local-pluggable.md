---
id: TFG-20260512-strategy-place-resolver-geocoder-local-pluggable
título: "Strategy PlaceResolver: geocoder local pluggable para el chat LLM"
tipo: decisión
tags:
  - tfg
  - llm
  - geocoder
  - arquitectura
  - strategy
  - searchPlace
contexto: "Decisión de arquitectura del módulo de chat LLM del visor MeteoVisor sobre cómo resolver el nombre de un lugar a coordenadas/bbox dentro de la tool `searchPlace`, con un punto de extensión preparado para reemplazar la implementación sin tocar la tool ni el orquestador."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada del cierre del módulo de chat LLM en MeteoVisor"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-12"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar nombres definitivos del patrón en la memoria (`PlaceResolver`, `LocalPlaceResolver`, `NominatimPlaceResolver`)."
---

# Strategy PlaceResolver: geocoder local pluggable para el chat LLM

## Contenido
La tool `searchPlace` del catálogo del chat LLM se apoya en un punto de extensión `PlaceResolver` implementado con patrón **Strategy**. La intención es que el geocoder de la tool se pueda reemplazar sin tocar la tool ni el orquestador del chat.

### Implementación actual: `LocalPlaceResolver`

- Fichero estático con las **19 comunidades autónomas** de España y **~50 provincias**, con su bbox aproximado y centroide. Cubre los ámbitos administrativos típicos en una consulta del visor (*"Galicia"*, *"Cáceres"*, *"Cataluña"*).
- **Fallback a `core.nucleos_poblacion_polygon`** por consulta `ILIKE` cuando el término no encaja en CCAA ni provincia. Cubre municipios y núcleos menores.
- Sin dependencia de servicios externos. Latencia despreciable.

### Implementación futura: `NominatimPlaceResolver`

Si en el futuro se necesita cobertura ampliada (puntos de interés, lugares fuera del set administrativo), basta con implementar un `NominatimPlaceResolver` contra el servicio Nominatim de OpenStreetMap. **No requiere tocar la tool `searchPlace` ni el orquestador**: la selección se hace con la variable de entorno `PLACE_RESOLVER=local|nominatim` resuelta al construir el contenedor de tools.

### Justificación de la decisión

Decisión **consciente** de no integrar Nominatim ahora:
- El alcance del visor es España y los ámbitos administrativos (CCAA, provincia, municipio). El set local cubre el 95 % de las consultas previsibles del prototipo.
- Evita una dependencia externa con políticas de uso, rate limits y latencia variable.
- Reduce la superficie de fallos en demos offline.

A cambio, se acepta que ciertas consultas con topónimos no administrativos (parques naturales por nombre, comarcas históricas, hidrónimos) pueden no resolver. El asistente devuelve un mensaje de "no encontrado" en ese caso, que el usuario puede solventar dando un bbox o una CCAA.

Relacionado con [[ideas-operaciones-llm-local-en-visor-meteovisor]] (catálogo de tools, Nivel 1).

## Datos explícitos
- El patrón aplicado es Strategy.
- La implementación actual usa un fichero estático con 19 CCAA y ~50 provincias.
- Fallback a `core.nucleos_poblacion_polygon` por `ILIKE`.
- Selección de implementación por `PLACE_RESOLVER=local|nominatim`.
- Sin dependencia externa en la implementación actual.

## Datos inferidos
- El patrón Strategy aquí también facilita testear `searchPlace` sin red, mockeando el resolver.
- Una migración a Nominatim no requiere cambios en el catálogo de tools ni en el system prompt.

## Datos faltantes o ambiguos
- Política sobre acentos, mayúsculas y variantes oficiales/coloquiales en el matching `ILIKE`.
- Cobertura medida sobre un set real de consultas del prototipo.
