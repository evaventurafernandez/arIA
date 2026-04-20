# Ingesta `landcover`

Fases 4b y 5 de la PoC: carga completa eficiente desde un `FileGDB` empaquetado en ZIP a PostGIS usando GDAL desde Python con flujo `ZIP -> GDB extraido -> staging -> source`, y normalizacion posterior desde `source` a `core`.

## Piezas

- `import_landcover_source.py`: descomprime el `FileGDB` a una ruta canónica, hace la carga bulk a `staging` con `osgeo.gdal` y consolida `source` con SQL.
- `docker-compose.yml`: añade el servicio `gdal` con una imagen oficial de GDAL con bindings de Python.
- `infra/postgres/initdb/002_landcover_source.sql`: crea `ingest.ingest_file`, las tablas `staging`, las tablas `source` y la vista unificada.
- `infra/postgres/initdb/003_landcover_core.sql`: crea el catalogo semantico de clases y la tabla canonica `core.landcover_polygon`.
- `infra/postgres/initdb/004_landcover_pub.sql`: crea `pub.landcover_filtered` como vista materializada derivada para explotacion.
- `refresh_landcover_core.sql`: reconstruye `core` desde `source` reparando y canonizando geometria.
- `refresh_landcover_pub.sql`: refresca `pub` desde `core` reproduciendo la simplificacion y el dissolve del flujo historico.

## Origen actual de la fase

La subfase 4b usa por defecto este artefacto bruto:

```text
./data-store/files/CLC2018_GDB.zip
```

Durante la carga eficiente, el proceso lo descomprime una vez a esta ruta canónica:

```text
./data-store/files/raw/copernicus/corine/landcover_corine_2018_filtered/2018/CLC2018_ES.gdb
```

Si el `FileGDB` ya existe extraido y el ZIP no ha cambiado, el proceso reutiliza esa extracción.

## Ejecución

1. Arrancar PostgreSQL/PostGIS:

   ```bash
   docker compose up -d postgres
   ```

2. Si la base ya existía antes de añadir el SQL de esta fase, aplicar el bootstrap actualizado:

   ```bash
   docker compose exec postgres psql -U ${POSTGRES_USER:-meteovisor} -d ${POSTGRES_DB:-meteovisor} -f /docker-entrypoint-initdb.d/002_landcover_source.sql
   docker compose exec postgres psql -U ${POSTGRES_USER:-meteovisor} -d ${POSTGRES_DB:-meteovisor} -f /docker-entrypoint-initdb.d/003_landcover_core.sql
   docker compose exec postgres psql -U ${POSTGRES_USER:-meteovisor} -d ${POSTGRES_DB:-meteovisor} -f /docker-entrypoint-initdb.d/004_landcover_pub.sql
   ```

3. Ejecutar la importación completa eficiente:

   ```bash
   docker compose run --rm gdal python3 /work/infra/ingest/import_landcover_source.py
   ```

4. Validación rápida opcional con muestra pequeña:

   ```bash
   docker compose run --rm -e MAX_FEATURES_PER_LAYER=100 gdal python3 /work/infra/ingest/import_landcover_source.py
   ```

5. Verificar el resultado:

   ```bash
   docker compose exec postgres psql -U ${POSTGRES_USER:-meteovisor} -d ${POSTGRES_DB:-meteovisor} -c "\dt source.*"
   docker compose exec postgres psql -U ${POSTGRES_USER:-meteovisor} -d ${POSTGRES_DB:-meteovisor} -c "SELECT source_layer, count(*) FROM source.landcover_corine_polygon GROUP BY 1 ORDER BY 1;"
   ```

6. Reconstruir `core` desde `source`:

   ```bash
   docker compose exec -T postgres psql -U ${POSTGRES_USER:-meteovisor} -d ${POSTGRES_DB:-meteovisor} < infra/ingest/refresh_landcover_core.sql
   ```

7. Verificar `core`:

   ```bash
   docker compose exec -T postgres psql -U ${POSTGRES_USER:-meteovisor} -d ${POSTGRES_DB:-meteovisor} < infra/ingest/verify_landcover_core.sql
   ```

8. Reconstruir `pub` desde `core`:

   ```bash
   docker compose exec -T postgres psql -U ${POSTGRES_USER:-meteovisor} -d ${POSTGRES_DB:-meteovisor} < infra/ingest/refresh_landcover_pub.sql
   ```

9. Verificar `pub`:

   ```bash
   docker compose exec -T postgres psql -U ${POSTGRES_USER:-meteovisor} -d ${POSTGRES_DB:-meteovisor} < infra/ingest/verify_landcover_pub.sql
   ```

## Variables útiles

- `RAW_ZIP`: ZIP de entrada. Por defecto `./data-store/files/CLC2018_GDB.zip`.
- `EXTRACTED_GDB_DIR`: ruta canónica del `FileGDB` descomprimido.
- `WHERE_CLAUSE`: filtro funcional por `CODE_18`.
- `MAX_FEATURES_PER_LAYER`: límite de features por capa para validación rápida. `0` significa sin límite.
- `TRUNCATE_STAGING`: limpia `staging` antes de recargar. Por defecto `1`.
- `TRUNCATE_SOURCE`: limpia `source` antes de recargar. Por defecto `1`.
- `OGR_ORGANIZE_POLYGONS`: estrategia de GDAL para polígonos complejos. Por defecto `SKIP`.

## Notas

- El filtrado funcional se hace antes de persistir en PostGIS.
- La carga masiva entra primero en `staging` y solo después se consolida a `source`.
- `core` no hace `dissolve`; conserva una fila por geometria de `source` y normaliza solo la semantica y la geometria canonica.
- `pub.landcover_filtered` es una vista materializada y no una vista simple porque el dissolve y la simplificacion deben ejecutarse en batch, no por peticion.
- `pub.landcover_filtered` reproduce el flujo historico: simplificacion por feature con tolerancia `0.005`, dissolve por clase y payload minimo con `feature_id`, `class_code`, `class_label`, `class_color`, `theme` y `geom`.
- La ejecución es portable: el mismo comando `docker compose run` sirve en Linux y en Windows con Docker Desktop.
- La importación usa GDAL desde Python, sin wrappers de shell como pieza principal.
- La carga bulk usa el driver PostgreSQL de GDAL con `PG_USE_COPY=YES`.
- El valor por defecto `OGR_ORGANIZE_POLYGONS=SKIP` prioriza rendimiento en la carga completa. Eso puede aumentar el numero de geometrías inválidas en `source`; la reparación se reserva para `core`.
- En `source`, `source_fid` es un identificador técnico generado en PostGIS y `source_objectid` conserva el `OBJECTID` original del `FileGDB`.
- Cada carga crea su registro en `ingest.ingest_file` con `status`, hash, ruta y metadatos de trazabilidad.
- `source` puede conservar geometrías no canónicas, incluyendo `MultiSurface` o geometrías inválidas; la canonización y reparación se reservan para `core`.
- En `core`, las geometrías `MultiSurface` se linealizan con `ST_CurveToLine`, las geometrías no canónicas se reparan con `ST_Buffer(geom, 0)` y el resultado se canoniza a `MultiPolygon` en `EPSG:4326`.
