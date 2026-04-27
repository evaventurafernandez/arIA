---
id: TFG-20260427-copernicus-dataspace-s3-y-estructura-real-de-burnt-area-v4
título: "Copernicus Data Space S3 y estructura real del producto burnt area v4"
tipo: fuente
tags:
  - tfg
  - copernicus
  - cdse
  - s3
  - burnt-area
  - clms
  - documentación
contexto: "Fuente técnica relevante para justificar en el TFG cómo se descargan en local los datos diarios de burnt area y por qué el producto v4/cog debe tratarse como un prefijo S3 con varias bandas raster separadas."
fuente_existe: true
fuente_tipo: documentación
fuente_descripción: "Documentación oficial de Copernicus Data Space Ecosystem sobre acceso S3, complementada con la documentación oficial del producto burnt area v4 y con la inspección real del contenido del prefijo S3 durante la implementación."
fuente_url: "https://documentation.dataspace.copernicus.eu/APIs/S3.html"
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "pendiente de confirmar"
licencia_o_copyright: "desconocido"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar entidad autora exacta de la documentación oficial de CDSE."
  - "Confirmar fecha de actualización de las páginas usadas."
  - "Confirmar condiciones de reutilización de la documentación web en la memoria del TFG."
---

# Copernicus Data Space S3 y estructura real del producto burnt area v4

## Contenido
La documentación de `Copernicus Data Space Ecosystem` sobre acceso S3 fue clave para resolver la descarga local del producto `burnt area v4`. Su utilidad principal no estuvo solo en confirmar que el bucket `eodata` puede consultarse con `access key` y `secret key`, sino en sugerir la forma correcta de razonar sobre el contenido: en algunos productos el valor publicado en catálogo funciona mejor como prefijo S3 que como objeto final descargable.

Durante la implementación del pipeline se contrastó esa idea con el producto `burnt area v4` y se comprobó que, en la variante `v4/cog`, el campo `s3path` del catálogo diario no apunta a un único fichero TIFF. En la práctica, cada día se expone como un prefijo bajo el que cuelgan varios objetos raster. Para el día `2025-05-01`, por ejemplo, la inspección real del prefijo devolvió cuatro TIFF distintos:

- `c_gls_BA300-BF-NRT_202505010000_GLOBE_S3_V4.0.1.tiff`
- `c_gls_BA300-CP-NRT_202505010000_GLOBE_S3_V4.0.1.tiff`
- `c_gls_BA300-DOB-NRT_202505010000_GLOBE_S3_V4.0.1.tiff`
- `c_gls_BA300-LFP-NRT_202505010000_GLOBE_S3_V4.0.1.tiff`

Esa observación técnica encaja con la documentación temática del propio producto `burnt area v4`, donde se describen varias capas o bandas relevantes. En el pipeline del TFG se usaron principalmente:

- `BF`: fracción quemada;
- `DOB`: día del año de la quema;
- `CP`: capa auxiliar del producto;
- `LFP`: capa auxiliar del producto.

La consecuencia metodológica fue importante. No bastaba con intentar descargar el valor literal de `s3path`. Había que listar el contenido del prefijo, descargar a disco local todos los TIFF asociados al día y montar después un `VRT` con las bandas necesarias para el procesado. Esta decisión permitió una estrategia consistente con el objetivo del TFG de trabajar en local y no depender continuamente de un servicio remoto una vez hecha la descarga inicial.

La fuente también resulta útil para justificar por qué el pipeline final se separó en dos fases:

1. descarga local de objetos diarios desde `eodata` usando credenciales S3;
2. procesado raster completamente local sobre la copia en disco.

Desde el punto de vista de la memoria, esta referencia sirve para explicar por qué la implementación definitiva no usa el `s3path` como si fuera un archivo único, sino como entrada a una enumeración de objetos. También ayuda a respaldar técnicamente el uso de `boto3` para la descarga local y de `GDAL` para la construcción de un `VRT` diario a partir de los cuatro TIFF.

## URLs relevantes
- `https://documentation.dataspace.copernicus.eu/APIs/S3.html`
- `https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/clms/bio-geophysical-parameters/vegetation/burnt-area/ba_global_300m_daily_v4.html`
- `https://land.copernicus.eu/en/products/vegetation/burnt-area-v4-daily-300m`

## Utilidad concreta para el TFG
- Justifica el acceso S3 autenticado a datos CLMS.
- Explica por qué el producto diario `v4/cog` debe tratarse como un prefijo multi-fichero.
- Respalda la descarga local previa a la fase de explotación.
- Sirve de base para describir la construcción de un `VRT` diario antes del recorte a España y del teselado.

## Datos explícitos
- Existe una documentación oficial de CDSE para acceso S3.
- El bucket de trabajo es `eodata`.
- El producto `burnt area v4` documenta varias capas temáticas relevantes, entre ellas `BF` y `DOB`.
- En la inspección real del prefijo diario `v4/cog` aparecieron cuatro TIFF: `BF`, `CP`, `DOB` y `LFP`.
- El `s3path` del catálogo funcionó operativamente como prefijo S3, no como un único TIFF descargable.

## Datos inferidos
- La documentación oficial de CDSE y la inspección del prefijo son suficientes para justificar un downloader local específico para `burnt area v4`.
- El pipeline del TFG debe tratar la descarga y el procesado como fases separadas.
- Esta nota encaja mejor en `10-fuentes-y-referencias/` que en una carpeta de ideas o decisiones, porque su valor principal es de apoyo técnico externo.

## Datos faltantes o ambiguos
- Fecha exacta de publicación o última actualización de las páginas oficiales.
- Forma bibliográfica final más adecuada para citar CDSE y CLMS en la memoria.
- Licencia o condiciones de uso detalladas de la documentación web oficial.
