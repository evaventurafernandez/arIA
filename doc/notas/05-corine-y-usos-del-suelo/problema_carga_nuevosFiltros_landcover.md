---
id: TFG-20260421-problema-carga-nuevos-filtros-landcover
título: "Problema al ampliar el filtro CORINE con 111, 112 y 121"
tipo: referencia
tags:
  - tfg
  - corine
  - landcover
  - ingest
  - postgis
  - filtros
contexto: "Incidencia técnica al ampliar el subconjunto de clases CORINE que se cargan en el pipeline actual de landcover del visor GIS del TFG."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia a partir del error observado durante la ingesta y de la revisión del código y SQL del proyecto"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-04-21"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría de la nota"
---

# Problema al ampliar el filtro CORINE con 111, 112 y 121

## Contenido
Se quiso ampliar el subconjunto `landcover` cargado desde CORINE para incluir tres clases nuevas: `111` (tejido urbano continuo), `112` (tejido urbano discontinuo) y `121` (zonas industriales o comerciales). El objetivo era que estas clases quedaran incorporadas al mismo pipeline actual `source -> core -> pub`.

El primer intento falló al ejecutar `import_landcover_source.py`. La causa no estaba en GDAL ni en el `FileGDB`, sino en una desalineación del contrato interno del pipeline: el filtro funcional se había ampliado, pero las restricciones `CHECK` de `staging/source` y el catálogo semántico de `core` seguían admitiendo solo el conjunto anterior de códigos.

En una decisión posterior de modelado, una vez resuelta la incidencia de carga, se dejó de publicar `111` y `112` como clases separadas y se pasaron a agrupar bajo un nuevo código canónico `1001` con la etiqueta `Tejido urbano`. El nivel `source` mantiene los códigos originales de CORINE, pero `core`, `pub` y las publicaciones `MVT` ya trabajan con ese agrupamiento canónico.

## Problema detectado
Al lanzar la carga con el filtro ampliado apareció este error:

```text
ERROR: Transaction not established
May be caused by: Terminating translation prematurely after failed translation from sql statement.
May be caused by: COPY statement failed.
ERROR: new row for relation "landcover_clc18_es_raw" violates check constraint "landcover_clc18_es_raw_code_18_check"
DETAIL: Failing row contains (..., 111, ...).
```

La fila rechazada ya mostraba el primer indicador clave: el código `111` llegaba correctamente desde el origen, pero la tabla `staging.landcover_clc18_es_raw` todavía no lo aceptaba.

## Causa localizada
La revisión del flujo dejó localizados tres puntos que debían evolucionar juntos:

- `infra/ingest/import_landcover_source.py` construía el filtro funcional `CODE_FILTER`.
- `infra/postgres/initdb/002_landcover_source.sql` imponía `CHECK (code_18 IN (...))` en `staging` y `source`.
- `infra/postgres/initdb/003_landcover_core.sql` definía el catálogo `core.landcover_class` y restringía tanto `class_code` como `theme`.

El problema real era, por tanto, de coherencia interna: añadir códigos nuevos en el filtro sin ampliar también las restricciones y el catálogo hacía que la carga abortara en `staging`, y aunque `staging` hubiera aceptado esas filas, la reconstrucción de `core` también habría fallado al no existir todavía esas clases en `core.landcover_class`.

## Solución aplicada
La corrección quedó documentada y aplicada en cuatro frentes:

- se amplió `CODE_FILTER` para incluir `111`, `112` y `121`;
- se actualizaron las `CHECK` de `staging` y `source` para aceptar el subconjunto actual completo;
- se amplió `core.landcover_class` para aceptar los temas artificiales y, en el estado actual, para publicar `1001` como clase canónica urbana;
- y se añadió el tema `artificial` al contrato de `core`, porque las nuevas clases ya no pertenecen a los temas forestales, de matorral o agrícolas.

El subconjunto actual queda así:

```python
CODE_FILTER = ("111", "112", "121", "211", "242", "311", "312", "313", "321", "322", "323", "324")
```

Clases incorporadas o redefinidas en el catálogo canónico:

- `1001`: `Tejido urbano` (`#e6004d`, `artificial`), como agrupación de `111` y `112`
- `121`: `Zonas industriales o comerciales` (`#cc4df2`, `artificial`)

## Ajuste posterior de modelado
Aunque la ampliación inicial se planteó para publicar `111` y `112` por separado, el criterio final del pipeline cambió para simplificar la lectura urbana en el visor:

- `source` conserva `111` y `112` como códigos de origen;
- `refresh_landcover_core.sql` los mapea al código canónico `1001`;
- `core.landcover_polygon` conserva una fila por feature, pero ya con `class_code = '1001'` y `class_label = 'Tejido urbano'`;
- `pub.landcover_filtered`, `pub.landcover_mvt_source` y `pub.landcover_mvt_class_source` publican esa clase urbana ya agrupada.

El objetivo de este ajuste es mantener la trazabilidad del origen sin obligar al visor a distinguir dos subclases urbanas que, en este caso de uso, se prefieren como una única categoría temática.

## Proceso documentado
Para repetir la corrección en una base ya existente, el orden operativo recomendado es este:

1. Actualizar el código y los scripts SQL del proyecto.
2. Reaplicar `002_landcover_source.sql` para ampliar las restricciones de `staging/source`.
3. Reaplicar `003_landcover_core.sql` para ampliar el catálogo y las restricciones de `core`.
4. Volver a ejecutar la importación `source`.
5. Reconstruir `core`, aplicando el mapeo canónico `111|112 -> 1001`.
6. Refrescar `pub.landcover_filtered`.
7. Refrescar `pub.landcover_mvt_source` y `pub.landcover_mvt_class_source`.
8. Verificar recuentos y clases publicadas.

Comandos de referencia:

```bash
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/002_landcover_source.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/003_landcover_core.sql
docker compose run --rm gdal python3 /work/infra/ingest/import_landcover_source.py
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_landcover_core.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_landcover_pub.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_landcover_mvt.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/verify_landcover_source.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/verify_landcover_core.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/verify_landcover_pub.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/verify_landcover_mvt.sql
```

La lección técnica es que, en este pipeline, cambiar el subconjunto de `CODE_18` no consiste solo en tocar el filtro de importación: hay que mantener sincronizados el contrato de `source`, el catálogo semántico de `core`, el mapeo canónico aplicado en la reconstrucción y las publicaciones derivadas.

## Datos explícitos
- Se quiso añadir `111`, `112` y `121` al filtro de `landcover`.
- La carga falló con la restricción `landcover_clc18_es_raw_code_18_check`.
- El error apareció durante la importación a `staging`.
- El contrato SQL del proyecto seguía aceptando solo el subconjunto anterior de códigos.
- La solución requiere actualizar tanto el filtro como las restricciones, el catálogo de clases y el mapeo canónico de `core`.
- El estado final publicado agrupa `111` y `112` bajo `1001` con la etiqueta `Tejido urbano`.

## Datos inferidos
- El objetivo funcional era ampliar la cobertura urbana e industrial del subconjunto CORINE usado en el visor.
- Sin ampliar `core.landcover_class`, la reconstrucción de `core` habría fallado aunque `staging` hubiese aceptado los nuevos códigos.
- La agrupación `111|112 -> 1001` responde más a una decisión de modelado del visor que a la nomenclatura oficial de CORINE.
- Esta incidencia es relevante para el TFG porque documenta una dependencia estructural entre ingesta, normalización y publicación.

## Datos faltantes o ambiguos
- Confirmación de autoría de la nota.
