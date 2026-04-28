---
id: TFG-20260428-proceso-creacion-historico-avisos-aemet-temperaturas-maximas
título: "Proceso de creación del histórico de avisos AEMET de temperaturas máximas"
tipo: decisión
tags:
  - tfg
  - aemet
  - avisos
  - temperaturas-maximas
  - historico
  - postgis
  - webgis
contexto: "Documentación del proceso implementado para incorporar al visor del TFG un histórico diario de avisos AEMET filtrado exclusivamente al fenómeno AT;Temperaturas máximas, con persistencia en PostgreSQL/PostGIS y publicación en GeoJSON/MVT."
fuente_existe: true
fuente_tipo: documentación
fuente_descripción: "Elaboración propia basada en la implementación real del pipeline histórico AEMET del repositorio, incluyendo descarga del archivo CAP, importación filtrada, canonización, publicación diaria y visualización en el visor."
fuente_url: "https://opendata.aemet.es/opendata/api/avisos_cap/archivo/fechaini/{date_from}/fechafin/{date_to}"
autor_o_entidad: "Agencia Estatal de Meteorología (AEMET) y elaboración propia"
fecha_fuente: "2026-04-28"
licencia_o_copyright: "© AEMET / condiciones de reutilización indicadas en la nota legal; implementación propia del repositorio"
condiciones_de_uso: "Requiere citar a AEMET como fuente y no desnaturalizar el sentido de la información; uso académico interno de la implementación del TFG."
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar la fórmula definitiva de atribución a AEMET que se mostrará en la memoria y, si procede, en el visor."
  - "Confirmar con una ejecución completa los recuentos finales del periodo 2025-05-01 a 2025-08-31."
  - "Decidir si se documentará aparte una validación de días sin avisos frente a la cobertura de descargas del archivo CAP."
---

# Proceso de creación del histórico de avisos AEMET de temperaturas máximas

## Contenido
Esta nota documenta el proceso implementado para convertir el archivo histórico de avisos CAP de AEMET en una capa temporal diaria del visor centrada solo en calor extremo, es decir, en el fenómeno `AT;Temperaturas máximas`. El objetivo no es conservar todos los fenómenos meteorológicos de AEMET, sino aislar los avisos de temperaturas máximas para poder compararlos temporalmente con capas de incendio, áreas quemadas, usos del suelo y exposición territorial dentro del TFG.

El pipeline sigue la arquitectura `raw -> source -> core -> pub`. En `raw` se guardan los ficheros `tar` originales descargados desde AEMET y un manifiesto JSON por bloque. En `source` se almacena el CAP ya parseado, pero todavía cercano al origen. En `core` se deduplican y normalizan los avisos de temperaturas máximas. En `pub` se genera una publicación diaria optimizada para timeline, estadísticas país, GeoJSON y teselas vectoriales MVT.

La decisión de filtrado principal se aplica durante la importación: solo se aceptan bloques CAP en español (`language` con prefijo `es`) cuyo `eventCode` tenga código `AT`. Después, el refresco de `core` restringe la publicación canónica a `phenomenon_code = 'AT'`, `language = 'es-ES'`, geometría válida y zona AEMET con `area_code`.

## Flujo implementado
1. Se crearon las estructuras `source`, `core` y `pub` en `infra/postgres/initdb/012_aemet_warnings_source.sql`, `013_aemet_warnings_core.sql` y `014_aemet_warnings_pub.sql`.
2. Se implementó `infra/ingest/download_aemet_warnings_historical_sources.py` para descargar el archivo histórico CAP desde AEMET por rangos de fecha/hora de elaboración, usando `AEMET_API_KEY`, bloques pequeños y reintentos.
3. La descarga guarda cada bloque como `tar` bruto en `data-store/files/raw/aemet/avisos_cap/archive`, junto a un manifiesto JSON con ruta relativa, `sha256`, tamaño, rango de elaboración solicitado, fecha de descarga y metadatos de respuesta de AEMET.
4. Se añadió un `lookback` de elaboración antes del primer día válido para capturar avisos que fueron emitidos antes del inicio del periodo, pero que seguían vigentes dentro del rango de análisis.
5. Se implementó `infra/ingest/import_aemet_warnings_source.py` para leer los manifiestos, verificar hash, recorrer archivos `tar`/`gzip` anidados, parsear XML CAP 1.2 y extraer solo los registros de `AT;Temperaturas máximas`.
6. La importación extrae fechas CAP (`sent`, `effective`, `onset`, `expires`), nivel Meteoalerta, umbral de temperatura, probabilidad, zona, código de área, descripción, instrucciones y polígono de la zona. Además preserva el bloque original relevante en `raw_json`.
7. Los polígonos CAP, publicados como pares `lat,lon`, se convierten a geometría WKT `lon lat` en EPSG:4326 para PostGIS.
8. El refresco `infra/ingest/refresh_aemet_warnings_core.sql` reconstruye `core.aemet_max_temperature_warning`, deduplica por `cap_identifier + language + area_code`, conserva la versión más reciente y reproyecta geometría a EPSG:3857 para teselas MVT.
9. En `core` se calcula `level_rank` (`Verde=0`, `Amarillo=1`, `Naranja=2`, `Rojo=3`) y `is_warning`, que solo es verdadero para niveles adversos (`Amarillo`, `Naranja`, `Rojo`).
10. La vista materializada `pub.aemet_max_temperature_daily_feature` expande cada aviso a los días locales de validez en `Europe/Madrid` y deja una feature por `día + zona + fenómeno`, escogiendo primero el nivel más alto y después la emisión más reciente.
11. El script `infra/ingest/publish_aemet_warnings.py` genera `pub.aemet_max_temperature_daily_stat`, una serie diaria país con cobertura, recuentos por nivel, número de zonas avisadas y temperatura máxima publicada.
12. `main.py` expone la capa mediante metadata, timeline, estadísticas diarias, GeoJSON por fecha y teselas MVT.
13. El frontend añade la capa "Histórico AEMET calor", la integra en la timeline histórica compartida y renderiza la geometría con `Leaflet.VectorGrid`, usando por defecto `warnings_only=true`.

## Comandos de reproducción
El flujo operativo documentado para el periodo del TFG es:

```bash
docker compose up -d postgres
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/012_aemet_warnings_source.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/013_aemet_warnings_core.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /docker-entrypoint-initdb.d/014_aemet_warnings_pub.sql
venv\Scripts\python.exe infra/ingest/download_aemet_warnings_historical_sources.py --date-from 2025-05-01 --date-to 2025-08-31 --elaboration-lookback-days 3 --block-days 2 --sleep-seconds 3 --max-retries 8
venv\Scripts\python.exe infra/ingest/import_aemet_warnings_source.py --date-from 2025-05-01 --date-to 2025-08-31 --elaboration-lookback-days 3
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_aemet_warnings_core.sql
docker compose exec -T postgres psql -U meteovisor -d meteovisor -f /infra/ingest/refresh_aemet_warnings_pub.sql
venv\Scripts\python.exe infra/ingest/publish_aemet_warnings.py --date-from 2025-05-01 --date-to 2025-08-31
```

## Problemas encontrados y cómo se resolvieron
- El endpoint histórico de AEMET trabaja por rango de elaboración, no directamente por día de validez del aviso. La solución fue descargar desde varios días antes del inicio del periodo con `--elaboration-lookback-days`, de forma que no se pierdan avisos emitidos antes del primer día pero activos durante él.
- Los paquetes descargados pueden contener archivos comprimidos o empaquetados de forma anidada. La importación se resolvió con un iterador recursivo capaz de abrir `tar`, `gzip` y XML CAP hasta encontrar los mensajes finales.
- El archivo CAP contiene múltiples idiomas y fenómenos. La solución fue filtrar localmente por idioma español y por `eventCode` de fenómeno `AT`, evitando que el histórico de calor quede contaminado por lluvia, tormentas, viento u otros avisos.
- Los avisos pueden aparecer varias veces por solapes entre bloques descargados o por nuevas versiones de un mismo CAP. La resolución fue conservar los registros próximos al origen en `source` y deduplicar en `core` por `cap_identifier`, `language` y `area_code`, escogiendo la versión más reciente.
- El formato CAP representa los polígonos como coordenadas `lat,lon`, mientras que PostGIS espera geometrías WKT en orden `lon lat`. La importación convierte explícitamente el orden y cierra el anillo del polígono cuando es necesario.
- Un aviso puede abarcar más de un día local. La publicación diaria usa `generate_series` entre `onset_at` y `expires_at` en la zona horaria `Europe/Madrid`, para que la timeline del visor funcione por día civil español.
- Para una misma zona y día pueden existir varias versiones o niveles. La vista diaria ordena por `level_rank` descendente y por `sent_at` más reciente, de modo que la feature publicada representa el estado más severo y actualizado para ese día.
- El nivel `Verde` es útil para trazabilidad, pero no debe mostrarse como aviso adverso en el visor. La solución fue conservarlo en base de datos y estadísticas internas, pero consumir por defecto `warnings_only=true` en GeoJSON/MVT y contar como avisos visibles solo `Amarillo`, `Naranja` y `Rojo`.

## Componentes implicados
- `.env.example`
- `infra/ingest/download_aemet_warnings_historical_sources.py`
- `infra/ingest/import_aemet_warnings_source.py`
- `infra/ingest/refresh_aemet_warnings_core.sql`
- `infra/ingest/refresh_aemet_warnings_pub.sql`
- `infra/ingest/publish_aemet_warnings.py`
- `infra/postgres/initdb/012_aemet_warnings_source.sql`
- `infra/postgres/initdb/013_aemet_warnings_core.sql`
- `infra/postgres/initdb/014_aemet_warnings_pub.sql`
- `infra/ingest/README.md`
- `main.py`
- `frontend/app.js`
- `frontend/index.html`
- `frontend/style.css`

## Modelo de datos resultante
- `source.aemet_warning_download_file`: registra cada descarga bruta del archivo CAP con rango solicitado, ruta, hash, tamaño, recuento de miembros y metadatos de respuesta.
- `source.aemet_warning_cap_record`: conserva registros CAP filtrados a temperaturas máximas, con campos CAP relevantes, zona AEMET, geometría EPSG:4326, umbral térmico y JSON original.
- `core.aemet_max_temperature_warning`: guarda avisos deduplicados y normalizados, con jerarquía de nivel, bandera `is_warning`, geometría válida en EPSG:4326 y versión EPSG:3857.
- `pub.aemet_max_temperature_daily_feature`: publica una feature diaria por zona/fenómeno para GeoJSON y MVT.
- `pub.aemet_max_temperature_daily_stat`: publica la serie diaria país para timeline y resúmenes del visor.
- `pub.aemet_max_temperature_daily_catalog`: vista ligera sobre la estadística diaria publicada.

## Resultado operativo para el visor
- La capa histórica se identifica como `aemet_max_temperature_warnings`.
- La metadata se expone en `/api/layers/aemet-max-temperature`.
- La timeline diaria se expone en `/api/aemet/max-temperature/timeline`.
- La serie diaria país se expone en `/api/aemet/max-temperature/stats/daily`.
- Las geometrías de una fecha concreta se pueden consultar en `/api/aemet/max-temperature/features?date=YYYY-MM-DD`.
- Las teselas vectoriales se sirven desde `/api/aemet/max-temperature/tiles/{date}/{z}/{x}/{y}.mvt`.
- La capa MVT usa el nombre interno `aemet_max_temp`.
- El frontend activa la capa con el control "Histórico AEMET calor" y la sincroniza con la timeline histórica compartida junto con FIRMS y burnt area.
- El resumen de timeline muestra cuántas zonas tienen aviso adverso y, si existe, el máximo umbral de temperatura publicado para la fecha.

## Relación con otras notas
- Esta nota complementa `doc/notas/10-fuentes-y-referencias/cita-obligatoria-aemet-datos-reutilizados.md`, que recoge la necesidad de atribuir correctamente la información de AEMET.
- Sigue el mismo patrón metodológico que `doc/notas/07-historico-y-base-de-datos/proceso-creacion-historico-focos-nasa-firms-espana-mayo-agosto-2025.md`, pero aplicado a avisos meteorológicos CAP y no a focos satelitales.
- Encaja con el bloque temporal del visor junto a burnt area y FIRMS, porque permite comparar avisos de calor, focos de incendio y superficies quemadas dentro de una misma ventana diaria.

## Datos explícitos
- El histórico se limita al fenómeno `AT;Temperaturas máximas`.
- El endpoint de descarga usado es el archivo CAP de AEMET por rango de elaboración.
- La clave de acceso se lee desde `AEMET_API_KEY`.
- El periodo documentado por defecto para el TFG es `2025-05-01` a `2025-08-31`.
- El almacenamiento bruto se organiza en `data-store/files/raw/aemet/avisos_cap/archive`.
- La arquitectura de persistencia es `raw -> source -> core -> pub`.
- La importación conserva `raw_json` y metadatos de trazabilidad.
- `source` conserva registros CAP ya filtrados por temperaturas máximas.
- `core` deduplica y normaliza a `core.aemet_max_temperature_warning`.
- `pub` genera una capa diaria y una tabla de estadísticas país.
- El visor consume por defecto solo niveles adversos mediante `warnings_only=true`.
- Los niveles adversos publicados son `Amarillo`, `Naranja` y `Rojo`; `Verde` se conserva como trazabilidad.

## Datos inferidos
- La capa histórica de temperaturas máximas sirve como proxy operativo de episodios de calor potencialmente relevantes para análisis de riesgo en el visor.
- La separación entre descarga bruta, source, core y pub facilita reproducibilidad, auditoría y reproceso sin depender de consultas manuales.
- La decisión de publicar MVT además de GeoJSON busca mantener rendimiento cuando haya muchas zonas de aviso o navegación a escalas amplias.
- La timeline diaria permite comparar visualmente la evolución temporal de avisos AEMET con otras capas históricas del TFG.

## Datos faltantes o ambiguos
- Falta confirmar los recuentos finales tras una ejecución completa del pipeline para todo el periodo.
- Falta decidir si el análisis académico usará todos los niveles conservados o solo los niveles adversos publicados en el visor.
- Falta cerrar el texto exacto de atribución a AEMET en memoria, interfaz y documentación.
- Falta documentar, si se considera necesario, una verificación externa de que los días sin avisos publicados no se deben a huecos de descarga.
