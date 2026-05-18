---
id: TFG-20260512-tools-no-implementables-por-limite-de-datos-chat-llm
título: "Tools no implementables por límite de datos: declaradas en el prompt para rechazo controlado"
tipo: alcance
tags:
  - tfg
  - llm
  - alcance
  - burnt-area
  - copernicus
  - inundaciones
  - miteco
contexto: "Decisión de alcance del módulo de chat LLM del visor MeteoVisor sobre tools del documento original que no son implementables con los datos efectivamente persistidos en la plataforma. Define cómo se gestiona ese hueco sin dejar que el modelo invente respuestas y distingue esos límites de operaciones de proximidad ya resueltas con geometría local."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada del cierre del módulo de chat LLM en MeteoVisor"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-18"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar si en la memoria estas tools se presentan como 'no implementables ahora' o como 'fuera de alcance del TFG'."
---

# Tools no implementables por límite de datos: declaradas en el prompt para rechazo controlado

## Contenido
El documento de partida del TFG enumeraba un catálogo amplio de tools del chat LLM. Durante el cierre del módulo, dos de esas tools se han identificado como **no implementables con los datos efectivamente persistidos** en la plataforma. La decisión es **declararlas explícitamente como no disponibles en el system prompt** para que el modelo las rechace de forma controlada en lugar de improvisar respuestas inventadas.

### `burntAreaIntersectPopulation`

Objetivo previsto: cruzar áreas quemadas con núcleos de población para reportar exposición. **No implementable** porque el producto Burnt Area v4 de Copernicus persistido en el visor solo conserva agregados a **escala país**, no las geometrías vectoriales de los polígonos quemados. Sin geometría, no hay cruce espacial posible con `core.nucleos_poblacion_polygon`. Ver [[proceso-ingesta-burnt-area-v4-espana-mayo-agosto-2025]] y [[copernicus-dataspace-s3-y-estructura-real-de-burnt-area-v4]].

### `crossAlertsFloodT10`

Objetivo previsto: cruzar avisos hidrometeorológicos vigentes con zonas inundables de período de retorno T=10 años cerca de núcleos. **No implementable** porque la capa de inundabilidad T=10 se consume del **WMS externo de MITECO**, sin geometría vectorial local persistida en PostGIS. La intersección espacial solo sería posible si se descargara y persistiera la capa, fuera del alcance del prototipo actual.

### Contraste: proximidad foco activo ↔ núcleo sí implementada

La limitación anterior no afecta a todas las operaciones de distancia. La consulta "núcleos de menos de 5.000 habitantes a menos de 2 km de un foco activo" sí es ejecutable porque:

- los focos activos FIRMS pueden representarse como puntos temporales WGS84;
- los núcleos del IGN existen localmente en `core.nucleos_poblacion_polygon`;
- PostGIS puede aplicar `ST_DWithin` y `ST_Distance` sobre `geography`.

Esa operación queda implementada como `activeFiresNearPopulation` y documentada en [[distancia-focos-activos-nucleos-y-resultados-geojson]].

### Patrón general

El asistente está instruido para responder a estas peticiones con un mensaje del tipo *"Esta operación no es ejecutable con los datos actualmente disponibles en MeteoVisor porque ..."* y, cuando exista, ofrecer una **alternativa cercana** (por ejemplo, listar avisos hidrometeorológicos vigentes sin el cruce con T=10, o reportar el área quemada agregada de Burnt Area sin desglose por núcleo).

Relacionado con [[ideas-operaciones-llm-local-en-visor-meteovisor]] (Nivel 3 del catálogo, cruces espaciales explicables).

## Datos explícitos
- Burnt Area v4 persistido en la plataforma solo conserva agregados a escala país.
- La capa T=10 se sirve vía WMS externo de MITECO, sin persistencia vectorial local.
- Las dos tools se declaran como no disponibles en el system prompt del chat.
- El asistente debe rechazar y, cuando proceda, sugerir una alternativa cercana.
- `activeFiresNearPopulation` sí es implementable porque no depende de la capa T10 ni de geometría externa no persistida.

## Datos inferidos
- Declarar la limitación en el prompt rinde mejor que omitir las tools, porque permite respuestas explicativas en lugar de "no entendí".
- Si en el futuro se persiste la geometría Burnt Area o la T=10 MITECO, basta con retirar la declaración del prompt y publicar la tool sin tocar el resto del orquestador.

## Datos faltantes o ambiguos
- Texto exacto del mensaje de rechazo en cada caso, para reutilizarlo en la memoria como evidencia.
- Lista cerrada de alternativas cercanas que el asistente puede ofrecer en cada rechazo.
