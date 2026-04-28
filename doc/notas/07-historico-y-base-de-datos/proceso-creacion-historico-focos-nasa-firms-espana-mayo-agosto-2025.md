---
id: TFG-20260427-proceso-creacion-historico-focos-nasa-firms-espana-mayo-agosto-2025
título: "Proceso de creación del histórico de focos NASA FIRMS para España (mayo-agosto 2025)"
tipo: decisión
tags:
  - tfg
  - firms
  - viirs
  - historico
  - postgis
  - ingest
  - espana
  - webgis
contexto: "Documentación del proceso realmente seguido para incorporar al visor del TFG un histórico diario persistente de focos NASA FIRMS para España entre el 1 de mayo de 2025 y el 31 de agosto de 2025."
fuente_existe: true
fuente_tipo: documentación
fuente_descripción: "Elaboración propia basada en la implementación real del pipeline histórico FIRMS en el repositorio, incluyendo descarga, importación, deduplicación, publicación y visualización en el visor."
fuente_url: "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{BBOX}/{DAY_RANGE}/{DATE}"
autor_o_entidad: "NASA FIRMS y elaboración propia"
fecha_fuente: "2026-04-27"
licencia_o_copyright: "desconocido"
condiciones_de_uso: "uso académico interno; pendiente de confirmar la atribución y las condiciones formales de reutilización de NASA FIRMS."
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar la cita institucional exacta de NASA FIRMS y Earthdata que se usará en la memoria."
  - "Confirmar si conviene documentar aparte una validación cuantitativa del histórico FIRMS frente a EFFIS/Copernicus."
  - "Confirmar si la siguiente iteración del histórico debe añadir agregados territoriales por CCAA o provincia además de la serie país."
---

# Proceso de creación del histórico de focos NASA FIRMS para España (mayo-agosto 2025)

## Contenido
Esta nota ya no describe solo un proceso previsto, sino el proceso que se ha terminado implementando en el repositorio para dejar operativo un histórico diario de focos NASA FIRMS en España para el periodo `2025-05-01` a `2025-08-31`. El resultado final no es una descarga puntual, sino un pipeline reproducible con separación `raw -> source -> core -> pub`, apoyado en `PostgreSQL + PostGIS`, ficheros brutos en disco y endpoints específicos para que el visor pueda consultar la serie temporal y los focos de una fecha concreta.

La solución se ha construido sobre los productos históricos `SP` de `VIIRS_NOAA20_SP` y `VIIRS_SNPP_SP`, manteniendo la decisión de trabajar con varias `bbox` específicas para España en lugar de usar el ámbito `world`. A partir de esa base se añadieron scripts de descarga por bloques cortos, importación a `source`, canonización deduplicada en `core`, publicación diaria país en `pub` y una capa histórica nueva en el frontend con timeline propia y consulta GeoJSON por fecha.

La decisión importante de fondo ha sido separar claramente este histórico `SP` de la consulta operativa en vivo `NRT` que ya existía en el visor. De ese modo, el proyecto conserva dos usos distintos de FIRMS: consulta casi en tiempo real para situación actual y persistencia histórica para análisis temporal y comparación retrospectiva.

## Flujo implementado
1. Se crearon las estructuras SQL `source`, `core` y `pub` del histórico FIRMS en `infra/postgres/initdb/009_firms_history_source.sql`, `010_firms_history_core.sql` y `011_firms_history_pub.sql`.
2. Se implementó `infra/ingest/download_firms_historical_sources.py` para descargar bloques `CSV` históricos `SP` de `VIIRS_NOAA20_SP` y `VIIRS_SNPP_SP`, repartidos entre `peninsula_baleares`, `canarias` y `ceuta_melilla`, guardando tanto el fichero bruto como un manifiesto JSON con hash, fechas, tamaño y recuento de filas.
3. Se implementó `infra/ingest/import_firms_historical_source.py` para cargar esos bloques en `source.firms_hotspot_download_file` y `source.firms_hotspot_observation`, normalizando campos, derivando `observed_at`, preservando la fila bruta en `raw_json` y marcando si cada observación cae realmente dentro del límite NUTS de España.
4. Se añadió `infra/ingest/refresh_firms_historical_core.sql` para reconstruir `core.firms_hotspot` desde `source`, deduplicando focos y manteniendo trazabilidad de cuántas descargas y observaciones originales alimentaron cada foco canónico.
5. Se implementó `infra/ingest/publish_firms_historical.py` para generar la serie diaria país en `pub.firms_hotspot_daily_stat`, distinguiendo cobertura completa de cobertura incompleta, conservando también los días con `0` focos cuando la descarga del día quedó realmente cerrada y publicando operativamente solo focos con confianza `nominal` o `alta`.
6. Se amplió `main.py` con nuevos endpoints de metadata, timeline, estadísticas diarias y `GeoJSON` por fecha, alineando además la capa histórica publicada con ese mismo criterio operativo de confianza `nominal`/`alta`.
7. Se amplió el frontend para activar una nueva capa histórica FIRMS, integrarla en la barra temporal histórica y consultar los focos diarios publicados desde PostGIS.

## Problemas encontrados y cómo se resolvieron
- El recorte por `bbox` era necesario para no descargar el ámbito `world`, pero una `bbox` no garantiza por sí sola que todos los puntos descargados pertenezcan realmente a España. La resolución fue mantener tres `bbox` operativas y añadir en la importación un filtro geométrico contra `data/boundaries/spain_nuts_2024_01m.geojson`, persistiendo el resultado en `in_spain_nuts`.
- Las `bbox` elegidas no son totalmente independientes. `ceuta_melilla` puede solaparse con `peninsula_baleares`, y además los reintentos o recargas del mismo bloque podían volver a introducir observaciones repetidas. La resolución fue tratar `source` como capa cercana al origen y deduplicar después en `core` con la clave `firms_source + latitude + longitude + acq_date + acq_time + satellite`, guardando además `bbox_regions`, `source_download_count` y `source_observation_count` para no perder trazabilidad.
- Un día sin filas en un CSV no significa automáticamente “no hubo focos”. También podía significar que faltaba alguna combinación de fuente y región y, por tanto, que el día estaba incompleto. La resolución fue modelar la cobertura diaria en `pub.firms_hotspot_daily_stat` con `coverage_expected_unit_count = 6`, `coverage_unit_count` y `coverage_complete`, de forma que el visor y la analítica distingan entre día vacío válido y día todavía no cubierto del todo.
- Los CSV de FIRMS no son cómodos para explotación directa si se dejan tal cual. Había que normalizar `confidence`, `daynight`, `acq_time`, derivar `observed_at` e incluso inferir `instrument` cuando no viniera explícito. La resolución fue normalizar esos campos durante la importación y persistir tanto los valores derivados como la fila original en JSON para conservar capacidad de auditoría.
- Las detecciones con confianza `low` seguían siendo útiles para trazabilidad y auditoría, pero al publicarlas en la capa histórica operativa introducían ruido visual y dejaban el histórico desalineado respecto a la consulta `NRT`, que ya priorizaba `nominal` y `alta`. La resolución fue conservar `low` en `source` y `core`, pero excluirlo de `pub.firms_hotspot_daily_stat` y del `GeoJSON` servido al frontend histórico, de modo que la publicación visible y sus recuentos operativos trabajen solo con `nominal`/`alta`.
- El histórico necesitaba poder rehacerse sin dejar residuos ni exigir limpieza manual. La resolución fue guardar cada descarga con hash y manifiesto, usar `upsert` en `source.firms_hotspot_download_file`, borrar antes las observaciones asociadas a un bloque cuando se reimporta y reconstruir `core` de forma explícita desde `source`.
- La descarga contra FIRMS debía ser robusta en entornos locales donde pueden influir proxy o configuración del sistema. La resolución fue incorporar una secuencia de reintentos alternando `trust_env` en `httpx`, además de leer `FIRMS_MAP_KEY` desde `.env` o desde variables de entorno en vez de dejarla embebida en scripts versionados.
- El histórico nuevo no podía mezclarse de forma confusa con los focos `NRT` ya visibles en el visor. La resolución fue publicarlo como capa separada, con `dataset_type = 'SP'`, endpoints propios y controles de timeline específicos en la interfaz.

## Cambios añadidos y por qué
- Se añadieron `infra/ingest/download_firms_historical_sources.py`, `infra/ingest/import_firms_historical_source.py`, `infra/ingest/refresh_firms_historical_core.sql` y `infra/ingest/publish_firms_historical.py` porque una ejecución manual no dejaba trazabilidad suficiente ni era cómoda de repetir para todo el periodo.
- Se añadieron `infra/postgres/initdb/009_firms_history_source.sql`, `010_firms_history_core.sql` y `011_firms_history_pub.sql` porque el histórico necesitaba un modelo persistente diferenciado: `source` para proximidad al dato original, `core` para deduplicación canónica y `pub` para explotación diaria en el visor.
- Se añadió almacenamiento bruto en `data-store/files/raw/nasa/firms/historical/...` con manifiestos JSON porque hacía falta conservar evidencia reproducible de lo descargado, poder verificar hashes y distinguir entre ausencia de focos y ausencia de cobertura.
- Se añadieron en `main.py` los endpoints `/api/layers/firms-history`, `/api/firms/history/timeline`, `/api/firms/history/stats/daily` y `/api/firms/history/features` porque el frontend necesitaba una API estable y publicada, no acceso directo a tablas ni consultas ad hoc.
- Se añadieron `FIRMS_HISTORICAL_DEFAULT_DATE_FROM` y `FIRMS_HISTORICAL_DEFAULT_DATE_TO` en configuración porque el visor histórico necesitaba un rango temporal por defecto desacoplado del código duro y fácil de reajustar.
- Se amplió el frontend en `frontend/app.js`, `frontend/index.html` y `frontend/style.css` para incluir una capa “Histórico NASA FIRMS”, una timeline histórica compartida y caché de consultas por fecha, porque el objetivo ya no era solo almacenar datos sino poder recorrer el periodo día a día desde la interfaz.
- Se actualizó la documentación operativa en `README.md`, `infra/ingest/README.md` e `infra/postgres/README.md` porque el pipeline dejó de ser una idea interna y pasó a formar parte real del flujo reproducible del proyecto.

## Componentes implicados
- `main.py`
- `.env.example`
- `frontend/app.js`
- `frontend/index.html`
- `frontend/style.css`
- `infra/ingest/download_firms_historical_sources.py`
- `infra/ingest/import_firms_historical_source.py`
- `infra/ingest/refresh_firms_historical_core.sql`
- `infra/ingest/publish_firms_historical.py`
- `infra/postgres/initdb/009_firms_history_source.sql`
- `infra/postgres/initdb/010_firms_history_core.sql`
- `infra/postgres/initdb/011_firms_history_pub.sql`
- `infra/ingest/README.md`
- `infra/postgres/README.md`
- `README.md`
- `data/boundaries/spain_nuts_2024_01m.geojson`

## Resultado operativo para el visor
- El visor dispone de una capa separada de histórico FIRMS distinta de la consulta `NRT`.
- La metadata de la capa histórica se expone en `/api/layers/firms-history`.
- La timeline diaria publicada se expone en `/api/firms/history/timeline`.
- La serie diaria país con cobertura y estadísticas se expone en `/api/firms/history/stats/daily`.
- Los focos de una fecha concreta se sirven como `GeoJSON` desde `/api/firms/history/features`.
- La capa histórica publicada y sus estadísticas operativas excluyen focos con confianza `low`; esos registros permanecen en niveles internos para trazabilidad, pero no se representan ni se contabilizan en la publicación usada por el visor.
- La publicación mantiene días con `0` focos cuando la cobertura del día es completa, evitando interpretar como “sin incendios” un día que en realidad está incompleto.
- El almacenamiento maestro del histórico queda en PostGIS, mientras que los CSV originales y sus manifiestos se conservan en filesystem para trazabilidad y reproceso.

## Relación con otras notas
- Esta nota complementa [proceso-ingesta-burnt-area-v4-espana-mayo-agosto-2025.md](./proceso-ingesta-burnt-area-v4-espana-mayo-agosto-2025.md), pero aplicada a un histórico vectorial de focos activos en vez de a un producto raster diario.
- También se apoya en [priorizacion-operativa-viirs-frente-a-modis.md](../03-incendios-firms-effis/priorizacion-operativa-viirs-frente-a-modis.md), porque el histórico sigue priorizando `VIIRS` frente a `MODIS`.
- Encaja además con el estado actual del visor, donde `main.py` mantiene la consulta operativa `NRT` y ahora añade en paralelo una capa histórica persistente `SP`.

## Datos explícitos
- El histórico objetivo queda acotado al periodo `2025-05-01` a `2025-08-31`.
- Las fuentes históricas implementadas son `VIIRS_NOAA20_SP` y `VIIRS_SNPP_SP`.
- La descarga se particiona en tres regiones: `peninsula_baleares`, `canarias` y `ceuta_melilla`.
- El pipeline persistido se organiza en `raw -> source -> core -> pub`.
- `source` se divide en `source.firms_hotspot_download_file` y `source.firms_hotspot_observation`.
- `core` se materializa en `core.firms_hotspot`.
- `pub` se materializa en `pub.firms_hotspot_daily_stat` y en la vista `pub.firms_hotspot_daily_catalog`.
- La deduplicación canónica se apoya en la unicidad de `firms_source`, `latitude`, `longitude`, `acq_date`, `acq_time` y `satellite`.
- La publicación diaria país usa una cobertura esperada de `6` unidades, equivalente a `2` fuentes por `3` regiones.
- La publicación histórica operativa expone solo focos con confianza `nominal` o `alta`; las detecciones `low` se preservan en `source`/`core`, pero se excluyen de la capa y de la estadística diaria publicada.
- El backend publica endpoints específicos para metadata, timeline, estadísticas diarias y focos por fecha.

## Datos inferidos
- La arquitectura del histórico FIRMS ya está madura como base metodológica para el capítulo de persistencia temporal vectorial del TFG.
- La separación entre dato bruto en filesystem y modelo publicado en PostGIS reduce riesgo de pérdida de trazabilidad y facilita reprocesos.
- El patrón `source -> core -> pub` reutiliza de forma coherente la arquitectura ya aplicada en `landcover` y `burnt area`, lo que simplifica justificarla en la memoria.
- La decisión de modelar cobertura diaria explícita evita uno de los errores interpretativos más delicados en series temporales de focos: confundir “día sin observaciones publicadas” con “día completamente cubierto y sin focos”.

## Datos faltantes o ambiguos
- Falta confirmar cómo citar formalmente NASA FIRMS y Earthdata en la memoria del TFG.
- Falta decidir si la siguiente ampliación del histórico debe añadir agregados territoriales además de la serie país.
- Falta decidir si conviene documentar en otra nota una validación comparativa sistemática entre histórico FIRMS y productos EFFIS/Copernicus.
