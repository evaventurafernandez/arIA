---
id: TFG-20260422-evolucion-consulta-puntual-landcover-de-core-a-getfeatureinfo-ign
título: "Evolución de la consulta puntual de landcover desde core a GetFeatureInfo del IGN"
tipo: decisión
tags:
  - tfg
  - landcover
  - corine
  - wms
  - getfeatureinfo
  - ign
  - fastapi
  - leaflet
contexto: "Trazabilidad de la evolución del subsistema de consulta puntual de usos del suelo del TFG, desde una primera propuesta apoyada en core.landcover_polygon hasta la adopción de GetFeatureInfo sobre la capa visible del IGN."
fuente_existe: true
fuente_tipo: web
fuente_descripción: "Servicio WMS INSPIRE de ocupación del suelo del IGN utilizado como base visual y como fuente de GetFeatureInfo en las pruebas del prototipo."
fuente_url: "https://servicios.idee.es/wms-inspire/ocupacion-suelo"
autor_o_entidad: "Instituto Geográfico Nacional (IGN)"
fecha_fuente: "pendiente de confirmar"
licencia_o_copyright: "desconocido"
condiciones_de_uso: "uso académico de consulta y validación; pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría de la nota."
  - "Confirmar condiciones de uso exactas del servicio WMS del IGN para documentarlas formalmente en la memoria."
---

# Evolución de la consulta puntual de landcover desde core a GetFeatureInfo del IGN

## Contenido
Esta nota deja constancia de un cambio importante de enfoque dentro del TFG. La primera implementación de consulta puntual de `landcover` se apoyó en `core.landcover_polygon`, porque era la capa canónica del pipeline propio, tenía geometría vectorial limpia y era razonable para una consulta espacial rápida por punto.

Sin embargo, durante la validación visual se vio que el usuario no estaba comparando el resultado contra `core`, sino contra la capa realmente visible en pantalla: `corine_wms`, servida por el `IGN` desde `LC.LandCoverSurfaces`. En ese momento apareció el problema clave: la fuente consultada y la fuente visualizada no eran la misma, y eso generaba discrepancias perceptibles en el popup y en el polígono resaltado.

La solución final fue cambiar el origen de metadatos y geometría del clic puntual: dejar de consultar `core.landcover_polygon` para este caso concreto y pasar a usar `GetFeatureInfo` del mismo `WMS` que el usuario está viendo. Esta decisión no sustituye la arquitectura local de `landcover` ya construida en `raw/staging/source/core/pub`, pero sí redefine cuál debe ser la fuente de verdad para la interacción puntual cuando la capa activa es el `WMS` oficial del `IGN`.

La evolución no terminó ahí. Una vez integrado el proxy a `GetFeatureInfo`, aparecieron problemas de robustez en la propia interacción del frontend: la consulta puntual no dependía ya solo de pedir bien `bbox`, `width`, `height`, `i`, `j` y `crs`, sino también de que el ciclo de vida del popup no interfiriera con la petición en curso ni con el estado interno de `Leaflet`. Por eso esta nota debe recoger también los ajustes posteriores sobre cancelación, reapertura de popup y cierre controlado al desactivar `corine_wms`.

## Situación de partida
- El proyecto ya tenía documentado y operativo un pipeline propio de `landcover` en base de datos.
- La visualización filtrada local seguía una arquitectura propia basada en `PostGIS`, publicaciones `pub` y `vector tiles`.
- Para la consulta puntual, la primera opción elegida fue `core.landcover_polygon` porque ofrecía geometría canónica, atributos normalizados y control completo desde backend.
- Antes de implementarla se revisó que esa tabla fuera la más adecuada para un punto-en-polígono y que su uso encajara con la estructura e índices del pipeline.

## Problema detectado
- La capa visible para la inspección interactiva era `corine_wms`, no la capa local de `core`.
- A simple vista, el resultado devuelto por `core` podía no coincidir con lo pintado por el `WMS`, especialmente al variar el zoom.
- El desfase no era solo geométrico: el propio servicio visible del `IGN` cambia la fuente temática según escala.
- En consecuencia, un mismo punto podía parecer coherente a zoom medio y dejar de parecerlo a zoom alto si se seguía consultando `core`.

## Proceso seguido
1. Se revisó la documentación de carga de `landcover` para identificar con claridad qué representaba cada stage (`raw`, `staging`, `source`, `core`, `pub`) y cuál era la capa más robusta para una primera consulta puntual.
2. Se comprobó que `core.landcover_polygon` era la opción lógica para una primera versión del endpoint, porque era la capa canónica del modelo propio y estaba preparada para consulta espacial rápida.
3. Se implementó una primera consulta puntual contra `core` y se conectó al frontend para mostrar popup y resaltar el polígono resultante.
4. Durante la prueba visual, se observó que el polígono y la clase devueltos no siempre coincidían con lo que el usuario veía realmente en el `WMS`.
5. Se validó el comportamiento del `GetFeatureInfo` del `IGN` con dos puntos de prueba y dos escalas distintas:
   - en `(39.67825, -3.67887)`, a escala alta devolvía `SIOSE 2014` con código `312`, mientras que a escala media devolvía `CORINE 2018` también con `312`;
   - en `(39.66900, -3.67304)`, a escala alta devolvía `SIOSE 2014` con código `340` (`Combinación de vegetación`) y a escala media devolvía `CORINE 2018` con código `312` (`Bosques de coníferas`).
6. Esa validación confirmó que `GetFeatureInfo` sí devolvía geometría, no solo atributos, y que además la respuesta dependía de la escala efectiva de consulta.
7. A partir de ahí, se sustituyó el servicio puntual propio por un proxy backend a `GetFeatureInfo`, enviando desde el frontend el estado real del mapa: `bbox`, `width`, `height`, `i`, `j` y `crs`.
8. Tras ese cambio apareció un segundo problema: la geometría devuelta por el servicio llegaba en `EPSG:3857`, lo que hacía que el resaltado no se dibujara correctamente sobre Leaflet si se trataba como GeoJSON lon/lat. Se corrigió reproyectando a `EPSG:4326` en backend y dejando además una salvaguarda en frontend.
9. Finalmente, se añadió el cálculo de `surface_ha` a partir del polígono cuando el servicio no la aporta explícitamente, proyectando la geometría a `EPSG:3035` antes de medir el área.
10. En las pruebas reales del visor apareció un tercer problema: la gestión del popup y de la cancelación podía interferir con la propia consulta puntual. En una variante del flujo, la apertura del popup de “Consultando uso del suelo...” llegaba a abortar la petición recién creada; en otra, el cierre del popup podía dejar referencias inconsistentes y provocar el error `Cannot use 'in' operator to search for '_leaflet_id' in null`.
11. Para corregirlo, se simplificó el ciclo de vida del popup en frontend. El cierre explícito del popup pasó a concentrarse en `closeCorineMapPopup()`, que ahora trabaja con una referencia local segura antes de invocar `map.closePopup(...)`, y `openCorineMapPopup()` pasó a reutilizar ese cierre sin abortar la consulta recién lanzada.
12. También se eliminó el cierre automático del popup por eventos genéricos de interfaz (`click` y `change`) y se dejó como comportamiento principal que la limpieza completa de popup y selección ocurra cuando se desactiva la capa `corine_wms`.
13. Como ajuste de eficiencia complementario, el proxy backend redujo `FEATURE_COUNT` a `1`, porque en la práctica el visor solo consume la primera feature devuelta por `GetFeatureInfo`.

## Decisión adoptada
- La consulta puntual asociada a `corine_wms` debe resolverse con `GetFeatureInfo` del propio `IGN`.
- La capa local basada en `core/pub` y `vector tiles` se mantiene como solución válida para visualización filtrada y publicación propia.
- La respuesta puntual debe asumirse como dependiente de la escala del mapa o, en contextos no interactivos, de una escala fijada explícitamente por la aplicación.
- El popup y el resaltado asociados a esa consulta deben seguir un ciclo de vida acotado a la propia capa `corine_wms`, evitando cierres globales de interfaz que introduzcan estados inconsistentes.

## Justificación del cambio
- El usuario compara el resultado con la capa visible, no con una capa interna del pipeline.
- Consultar una fuente distinta de la que se ve en pantalla introduce una disonancia que perjudica la credibilidad del visor.
- `GetFeatureInfo` permite recuperar atributos y geometría del mismo servicio cartográfico que se está usando como referencia visual.
- Mantener `core` para la publicación propia y `GetFeatureInfo` para la inspección puntual separa mejor dos necesidades distintas del TFG:
  - publicación interna optimizada;
  - consulta contextual coherente con la cartografía oficial visible.

## Consecuencias prácticas
- El endpoint puntual pasa a depender de la disponibilidad y latencia del `WMS` externo del `IGN`.
- La respuesta ya no es una verdad única independiente del zoom, sino una respuesta cartográfica ligada a la escala consultada.
- El backend necesita conocer el contexto de la vista actual para reproducir correctamente la consulta del usuario.
- El cálculo de superficie debe completarse localmente cuando el servicio no aporta `superficie_ha`.
- La robustez del servicio por clic no depende solo del `GetFeatureInfo`, sino también de cómo el frontend coordina popup, cancelación de peticiones y limpieza de selección.
- Un cierre demasiado agresivo del popup puede romper la interacción aunque la respuesta del `IGN` sea correcta.

## Funciones relevantes en la implementación
- `buildLandcoverPointQuery()` construye el contexto exacto que necesita `GetFeatureInfo` a partir del estado real del mapa o de un `zoom` de consulta fijado por la aplicación. Su papel es clave porque traduce la interacción del usuario a `bbox`, `width`, `height`, `i`, `j` y `crs`.
- `handleCorineWmsClick()` coordina el flujo completo del clic puntual: aborta una consulta previa si existe, crea un nuevo `AbortController`, lanza la petición al backend, interpreta la primera feature devuelta y actualiza tanto popup como geometría resaltada.
- `closeCorineMapPopup()` se volvió importante no por su complejidad, sino porque concentra una responsabilidad delicada: cerrar de forma segura el popup sin dejar una referencia inconsistente en memoria ni provocar errores internos en `Leaflet`.
- `clearCorinePointSelection()` agrupa la limpieza de popup y polígono resaltado. Su papel quedó mejor definido tras la corrección: debe ejecutarse sobre todo al desactivar `corine_wms`, no como reacción genérica a cualquier interacción de la interfaz.
- `fetch_landcover_features_by_point()` en backend mantiene el contrato con el `IGN` y normaliza la respuesta. Tras los últimos ajustes, además de pedir el `GetFeatureInfo` con el contexto adecuado, limita `FEATURE_COUNT` a `1` para evitar trabajo innecesario cuando el frontend solo consume la primera coincidencia.

## Relación con notas previas
- Esta nota corrige parcialmente la línea recogida en `aprendizajes-visualizacion-corine-2018-con-wms-y-consulta-puntual.md`, donde la hipótesis de trabajo todavía contemplaba usar el `GDB` como fuente de metadatos y geometría. Esa nota se conserva porque documenta un razonamiento intermedio útil, pero la implementación finalmente adoptada ya no usa `GDB` para esta interacción.
- Esta decisión tampoco invalida `decision-final-vector-tiles-para-landcover.md`: los `vector tiles` siguen siendo la solución elegida para la visualización filtrada local; simplemente se distingue mejor entre publicación propia y consulta puntual sobre la cartografía oficial visible.

## Datos explícitos
- Se implementó primero una consulta puntual contra `core.landcover_polygon`.
- El visor mostraba en pantalla la capa `corine_wms` del `IGN`.
- Se comprobó experimentalmente que `GetFeatureInfo` devuelve geometría y atributos.
- Se verificó que la respuesta de `GetFeatureInfo` cambia con la escala.
- Se sustituyó el endpoint puntual para que consultase `GetFeatureInfo` con el contexto real del mapa.
- Se corrigió un problema de CRS al recibir geometría en `EPSG:3857`.
- Se añadió cálculo de `surface_ha` cuando el servicio no la devuelve.
- Se detectó un fallo de robustez en el frontend relacionado con el ciclo de vida del popup y la cancelación de consultas.
- Se reprodujo un error de ejecución en el visor: `Cannot use 'in' operator to search for '_leaflet_id' in null`.
- Se corrigió el cierre del popup para hacerlo seguro y se eliminó el cierre automático por eventos genéricos de interfaz.
- Se dejó la limpieza del popup y de la selección asociada principalmente a la desactivación de `corine_wms`.
- El backend pasó a solicitar solo una coincidencia (`FEATURE_COUNT = 1`) en la consulta puntual.

## Datos inferidos
- El problema principal no era de índices ni de rendimiento puro, sino de coherencia entre fuente visual y fuente consultada.
- El valor metodológico para el TFG está en dejar separadas dos capas de verdad distintas: la canónica del proyecto y la oficial visible al usuario.
- La interfaz final gana credibilidad al priorizar consistencia visual aunque el servicio externo complique algo más el backend.
- En esta iteración, parte importante de la fiabilidad ya no dependía tanto del servicio externo como de acotar correctamente los efectos laterales del propio frontend.
- Para una interacción cartográfica creíble, no basta con consultar la fuente correcta: también hay que garantizar que popup, selección y estado de capa evolucionen de forma coherente.

## Datos faltantes o ambiguos
- Confirmación formal de las condiciones de uso del `WMS` del `IGN` para documentarlas con precisión en la memoria.
- Posible necesidad futura de registrar una estrategia de fallback si el servicio externo no responde.
