---
id: TFG-20260427-proceso-ingesta-burnt-area-v4-espana-mayo-agosto-2025
título: "Proceso de ingesta de burnt area v4 para España (mayo-agosto 2025)"
tipo: decisión
tags:
  - tfg
  - burnt-area
  - copernicus
  - clms
  - postgis
  - ingest
  - histórico
  - españa
contexto: "Documentación del proceso completo seguido para incorporar al visor del TFG una capa temporal diaria de áreas quemadas de Copernicus CLMS para España entre el 1 de mayo de 2025 y el 31 de agosto de 2025."
fuente_existe: true
fuente_tipo: documentación
fuente_descripción: "Elaboración propia basada en la ejecución real del pipeline en el repositorio, contrastada con documentación oficial de Copernicus Data Space Ecosystem y CLMS."
fuente_url: "https://documentation.dataspace.copernicus.eu/APIs/S3.html"
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "pendiente de confirmar"
licencia_o_copyright: "desconocido"
condiciones_de_uso: "uso académico interno; pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría formal de la nota."
  - "Confirmar cómo citar de forma estable la documentación oficial de CDSE y CLMS en la memoria."
  - "Confirmar si conviene añadir después una estadística territorial por CCAA o provincia además de la serie país."
---

# Proceso de ingesta de burnt area v4 para España (mayo-agosto 2025)

## Contenido
Esta nota documenta el proceso completo seguido para dejar operativa en el visor una capa temporal diaria de `burnt area` de Copernicus CLMS, centrada en España y acotada al periodo comprendido entre `2025-05-01` y `2025-08-31`. El resultado final no fue solo una carga puntual de datos, sino un pipeline reproducible y orientado a trabajo local: catálogo, base de datos, descarga a disco, recorte a España, teselado raster y publicación de estadísticas diarias.

La situación de partida era más limitada de lo que parecía. En `data/copernicus/data_burnt_areas` solo estaban los catálogos `cog.csv` y `nc.csv` de las variantes diarias y mensuales, pero no los rasters reales. A partir de esa carpeta se confirmó que, para el intervalo de estudio, `v4/cog` disponía de cobertura diaria completa y que la variante adecuada para el objetivo del TFG era `v4`, `COG` y modo principal `daily`, dejando la versión acumulada como ampliación posterior.

El primer bloque de trabajo consistió en adaptar el proyecto para que no dependiera de `all.zip`. Se amplió el backend para leer el catálogo directamente desde la carpeta extraída `data/copernicus/data_burnt_areas`, se preparó la metadata de la capa temporal y se dejaron operativos los endpoints de timeline, estadísticas diarias y teselas. En paralelo, se añadieron estructuras `source`, `core` y `pub` en PostgreSQL/PostGIS para `burnt area`, además de scripts de importación y consolidación equivalentes al patrón ya usado en `landcover`.

Una vez cargado el catálogo en base, se consolidó una fila por día, versión y formato. El catálogo quedó con `2720` filas en `source.burnt_area_catalog_item`, `2720` filas en `core.burnt_area_daily_file`, y se verificó que el rango `2025-05-01` a `2025-08-31` contenía exactamente `123` días para `v4/cog`. Esta parte dejó resuelto el control de disponibilidad, pero todavía no existía la capa visible porque faltaban los rásteres diarios reales.

El siguiente bloque fue la descarga local. Primero se comprobó que el acceso anónimo al endpoint de `eodata.dataspace.copernicus.eu` devolvía `403`, por lo que era necesario usar credenciales S3 de Copernicus Data Space Ecosystem. Después de configurar las claves en `.env`, se validó un detalle técnico importante: en `v4/cog` el `s3path` del catálogo no apunta directamente a un fichero TIFF único, sino a un prefijo S3. Al listar ese prefijo se comprobó que cada día publica realmente cuatro TIFF separados:

- `BF`
- `CP`
- `DOB`
- `LFP`

Ese descubrimiento cambió el diseño del pipeline. En vez de intentar descargar un único COG diario, se implementó un downloader local para traer a disco esos cuatro TIFF por día y guardarlos en `data/copernicus/burnt_area/raw/...`. Después se montó un `VRT` diario local para tratarlos como un stack raster de trabajo. Esta decisión permitió cumplir el criterio de “trabajar en local” y dejar la dependencia de S3 limitada a la primera descarga.

Con la descarga local resuelta, se implementó el procesado raster diario. El flujo quedó así:

1. descargar los TIFF de bandas del día en local;
2. construir un `VRT` diario con `BF`, `CP`, `DOB` y `LFP`;
3. recortar el dataset a España con la geometría de `data/boundaries/spain_nuts_2024_01m.geojson`;
4. generar un `COG` diario recortado a España;
5. calcular la estadística diaria usando `BF` y `DOB`;
6. generar un raster visual RGBA;
7. teselar ese raster solo si hay píxeles quemados;
8. escribir un manifiesto diario con rutas, métricas y estado;
9. publicar esos manifiestos en `core` y `pub`.

La lógica temática adoptada para el modo diario fue `DOB == día seleccionado`, es decir, la capa muestra solo los píxeles quemados ese día concreto, no el acumulado hasta esa fecha. La estadística de área se calculó ponderando la fracción quemada `BF` por el área real del píxel, en vez de contar píxeles binarios sin más. La variante acumulada quedó preparada en el script, pero no se conectó como modo principal del visor.

Durante la implementación aparecieron varias incidencias relevantes que conviene conservar para la memoria del TFG:

- La carpeta inicial contenía solo catálogos, no rasters.
- El importador de catálogo truncaba `source` por defecto, pero eso dejó de ser viable en cuanto `core` pasó a tener claves foráneas hacia `source`; se cambió a un patrón de `upsert` seguro por defecto.
- Apareció un problema de tipado en `psycopg` con el `bbox` nulo durante la importación, que se corrigió tipando mejor la rama SQL.
- El `s3path` de `v4/cog` resultó ser un prefijo S3, no un objeto final descargable.
- Una prueba en paralelo de descarga y procesado falló porque el `VRT` se estaba construyendo antes de que estuvieran todas las bandas disponibles en disco.
- Al añadir variables nuevas de CDSE al `.env`, `main.py` tuvo que ampliarse para aceptar esos campos sin romper la carga de `Settings`.

El resultado final quedó completamente operativo para el intervalo de estudio. Tras descargar, procesar y publicar el periodo completo, la serie diaria quedó con estos valores globales:

- `123` días publicados en `core` y `pub`;
- `116` días con teselas visibles (`tiles_generated = true`);
- `248383.15 ha` como suma de área quemada diaria del periodo;
- `32305.51 ha` como máximo diario, el `2025-08-16`;
- `5125` teselas PNG generadas;
- `123` recortes `COG` de España;
- `123` manifiestos diarios;
- `615` artefactos en `raw` contando TIFF descargados y `VRT` diarios.

Los picos más altos del periodo quedaron concentrados en agosto, especialmente en la segunda quincena. Los días con mayor superficie quemada diaria publicados en la serie país fueron:

1. `2025-08-16`: `32305.51 ha`
2. `2025-08-14`: `23972.81 ha`
3. `2025-08-18`: `23609.52 ha`
4. `2025-08-13`: `19607.04 ha`
5. `2025-08-19`: `19449.90 ha`

Desde el punto de vista del TFG, esta iteración deja varias decisiones de arquitectura ya maduras. La primera es que el histórico diario de áreas quemadas funciona mejor como pipeline híbrido: base de datos para catálogo, control de publicación y estadísticas; filesystem local para ráster bruto, `VRT`, recortes `COG` y teselas PNG. La segunda es que el formato `v4/cog` es suficientemente rico para soportar una visualización diaria creíble, siempre que se trate correctamente la estructura multi-banda real del producto. La tercera es que el criterio “local first” es viable: una vez descargados los TIFF diarios, el resto del flujo puede ejecutarse completamente en local sin depender de servicios remotos.

## Componentes implicados
- `main.py`
- `docker-compose.yml`
- `infra/postgres/initdb/006_burnt_area_source.sql`
- `infra/postgres/initdb/007_burnt_area_core.sql`
- `infra/postgres/initdb/008_burnt_area_pub.sql`
- `infra/ingest/import_burnt_area_catalog.py`
- `infra/ingest/refresh_burnt_area_core.sql`
- `infra/ingest/download_burnt_area_daily_sources.py`
- `infra/ingest/process_burnt_area_daily.py`
- `infra/ingest/publish_burnt_area_manifests.py`
- `data/boundaries/spain_nuts_2024_01m.geojson`

## Resultado operativo para el visor
- Timeline diaria propia para `burnt area`.
- Capa raster por fecha servida localmente.
- Serie diaria de estadísticas país en `pub.burnt_area_daily_stat`.
- Periodo `2025-05-01` a `2025-08-31` totalmente publicado.
- Días sin quemas visibles tratados como válidos, no como error.

## Relación con otras notas
- Esta nota complementa la línea de arquitectura de datos ya documentada en `poc-landcover-end-to-end.md`, pero aplicada a un caso raster temporal en vez de a un caso vectorial de usos del suelo.
- También se apoya en una nota de fuente técnica específica sobre CDSE S3 y la estructura real del producto `burnt area v4`.

## Datos explícitos
- La carpeta inicial `data/copernicus/data_burnt_areas` contenía catálogos CSV y no rásteres diarios.
- Se confirmó el uso de `v4`, `COG` y visualización principal `daily`.
- Se cargaron `2720` filas en `source.burnt_area_catalog_item`.
- Se consolidaron `2720` filas en `core.burnt_area_daily_file`.
- El rango `2025-05-01` a `2025-08-31` contiene `123` días para `v4/cog`.
- Se comprobó que el acceso anónimo a `eodata.dataspace.copernicus.eu` no era suficiente.
- Cada día de `v4/cog` se resolvió como un prefijo S3 con cuatro TIFF: `BF`, `CP`, `DOB` y `LFP`.
- Se descargó el periodo completo a disco local y después se procesó íntegramente desde copia local.
- El resultado final fue `123` días publicados, `116` con teselas visibles y `248383.15 ha` acumuladas en la serie diaria país.

## Datos inferidos
- Esta solución es suficientemente sólida como base metodológica para el capítulo de histórico raster del TFG.
- La separación entre filesystem local y PostGIS reduce complejidad frente a cargar el raster global bruto directamente en base.
- El patrón aplicado a `burnt area` puede reutilizarse en otros productos temporales raster si se mantiene la misma filosofía de catálogo, publicación y derivados.
- La nota encaja principalmente en `07-historico-y-base-de-datos/` porque documenta arquitectura de datos, pipeline, persistencia y explotación temporal.

## Datos faltantes o ambiguos
- Confirmar la forma exacta de citar institucionalmente la documentación de CDSE y CLMS en la memoria.
- Confirmar si conviene documentar por separado la variante acumulada cuando se active en el visor.
- Falta decidir si el siguiente paso del pipeline debe ser la estadística por CCAA, provincia o municipio.
