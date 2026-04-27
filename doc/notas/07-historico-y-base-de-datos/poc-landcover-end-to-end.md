---
id: TFG-20260420-poc-landcover-end-to-end
título: "PoC landcover end-to-end"
tipo: referencia
tags:
  - tfg
  - landcover
  - corine
  - postgis
  - ingest
  - arquitectura-datos
contexto: "Nota de referencia interna para documentar la prueba de concepto completa de ingestión, normalización y publicación del dataset landcover dentro de la arquitectura de datos del TFG."
fuente_existe: true
fuente_tipo: documentación
fuente_descripción: "Documento interno del repositorio: doc/arquitectura/poc_landcover_end_to_end.md"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "pendiente de confirmar"
licencia_o_copyright: "desconocido"
condiciones_de_uso: "uso interno académico; pendiente de confirmar"
grado_de_confianza: medio
pendientes_de_verificar:
  - "Confirmar autoría del documento interno"
  - "Confirmar fecha del documento fuente"
  - "Confirmar condiciones de uso internas si se reutiliza fuera del repo"
---

# PoC landcover end-to-end

## Contenido
La nota recoge la implementación completa de la prueba de concepto del pipeline `raw -> staging -> source -> core -> pub` para el dataset `landcover_corine_2018_filtered`. El flujo parte de un `FileGDB` empaquetado en ZIP, lo conserva como dato bruto en filesystem, lo carga masivamente a PostgreSQL/PostGIS, consolida una capa `source` cercana al origen, construye un nivel `core` canónico con geometrías `MultiPolygon` válidas y termina en una capa `pub` preparada para explotación y equivalente funcional al `landcover.geojson` histórico.

El documento fija las decisiones arquitectónicas principales: `PostgreSQL + PostGIS` como store maestro, uso de Docker para la infraestructura, separación entre ingestión y explotación, uso de `staging` para la carga masiva, y distinción clara entre `source` como capa trazable cercana al origen, `core` como modelo homogéneo canónico y `pub` como derivado materializado de publicación.

En el nivel operativo, la nota deja documentados los objetos principales y el pipeline de reconstrucción:

- `staging.landcover_clc18_es_raw`
- `staging.landcover_clc18_es_canarias_raw`
- `source.landcover_clc18_es`
- `source.landcover_clc18_es_canarias`
- `source.landcover_corine_polygon`
- `core.landcover_class`
- `core.landcover_polygon`
- `pub.landcover_filtered`

También se registran los pasos técnicos de la PoC:

1. carga completa a `source` desde `CLC2018_GDB.zip`,
2. reconstrucción de `core` desde `source`,
3. reconstrucción de `pub` desde `core`,
4. validación funcional comparada con el `GeoJSON` histórico.

Los resultados validados que conviene reutilizar en el TFG son:

- `source`: `151615` features totales,
- `core`: `151615` features, `0 invalid_geom`, `0 non_multipolygon`, `0 wrong_srid`,
- `pub`: `9` features agregadas por clase, equivalentes funcionalmente al `data/landcover.geojson`.

La nota es útil como referencia de arquitectura de datos, justificación metodológica de la PoC y base para describir la transición desde ficheros geoespaciales a un pipeline persistido y explotable en base de datos.

## Datos explícitos
- Existe un documento fuente interno en `doc/arquitectura/poc_landcover_end_to_end.md`.
- El documento describe la PoC completa del dataset `landcover`.
- La arquitectura implementada se organiza en `raw`, `staging`, `source`, `core` y `pub`.
- El store maestro elegido es `PostgreSQL + PostGIS`.
- El artefacto bruto tratado es `CLC2018_GDB.zip`.
- `core` canoniza geometrías a `MultiPolygon` en `EPSG:4326`.
- `pub.landcover_filtered` es una vista materializada.
- La validación registrada indica `151615` features en `source` y `core`, y `9` features en `pub`.

## Datos inferidos
- La nota encaja principalmente en `07-historico-y-base-de-datos/` por tratar sobre arquitectura de datos, pipeline y persistencia.
- El documento fuente parece ser una elaboración interna del proyecto, aunque la autoría explícita no aparece.
- La nota funciona mejor como `referencia` que como `idea` o `decisión`, porque resume un estado implementado y reusable.

## Datos faltantes o ambiguos
- Autoría explícita del documento fuente.
- Fecha exacta del documento fuente.
- Licencia o condiciones formales de reutilización del documento interno.
