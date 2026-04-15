---
id: TFG-20260415-glosario-terminos-gis-y-arquitectura-de-mapas
título: "Glosario de términos GIS y arquitectura de mapas"
tipo: referencia
tags:
  - tfg
  - glosario
  - gis
  - arquitectura-de-mapas
  - geoserver
  - postgis
contexto: "Glosario técnico reutilizable para el TFG, útil para definir conceptos de infraestructura geoespacial, estándares OGC, formatos de datos y decisiones de arquitectura relacionadas con publicación, consulta y rendimiento de capas cartográficas."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-04-15"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar que el glosario es de elaboración propia."
  - "Confirmar si esta nota debe permanecer en capas GIS y exposición o duplicarse como apoyo transversal."
  - "Decidir qué términos pasarán al texto final del TFG y cuáles quedarán como nota interna."
---

# Glosario de términos GIS y arquitectura de mapas

## Contenido
Glosario base de conceptos y componentes relacionados con sistemas de información geográfica y arquitectura de publicación de mapas. Reúne software, estándares, formatos y nociones operativas que pueden servir como referencia interna durante el desarrollo y como material reutilizable para definir términos en el TFG.

### 1. Software y componentes
- **GeoServer**: Servidor geoespacial open source para publicar datos mediante estándares OGC.
- **GeoWebCache**: Sistema de cacheo de teselas para mejorar el rendimiento.
- **PostGIS**: Extensión espacial de PostgreSQL para almacenar y consultar geometrías.
- **GDAL**: Librería para procesar datos geoespaciales raster y vectoriales.
- **ogr2ogr**: Herramienta de GDAL para conversión y transformación de datos vectoriales.
- **gdal_translate**: Herramienta para conversión y procesamiento de datos raster.
- **gdaladdo**: Generación de pirámides de resolución (overviews).
- **GeoPackage**: Formato portable basado en SQLite para datos geoespaciales.
- **Nginx**: Servidor web y proxy inverso para cacheo, compresión y seguridad.

### 2. Estándares y formatos
- **OGC**: Organización que define estándares geoespaciales.
- **WMS**: Servicio de mapas como imágenes.
- **WMTS**: Servicio de mapas basado en teselas.
- **OGC API Features**: API REST para acceso a entidades geográficas.
- **OGC API Tiles**: API REST para acceso a teselas.
- **Shapefile**: Formato vectorial clásico.
- **GeoJSON**: Formato JSON para datos geoespaciales.
- **Vector tiles**: Teselas con datos vectoriales.
- **Raster**: Datos en forma de píxeles.
- **Tile**: Fragmento de mapa.

### 3. Conceptos GIS
- **Feature (Entidad)**: Objeto geográfico.
- **Layer (Capa)**: Conjunto de datos homogéneos.
- **Geometría**: Forma espacial (punto, línea, polígono).
- **Atributos**: Información asociada a la geometría.
- **CRS**: Sistema de referencia de coordenadas.
- **EPSG**: Código estándar de CRS.
- **WGS84**: Sistema de coordenadas global.
- **BBOX**: Caja delimitadora.
- **Subsetting**: Filtrado espacial.
- **Reproyección**: Cambio de sistema de coordenadas.
- **Índice espacial**: Estructura para acelerar consultas.
- **GiST**: Tipo de índice en PostGIS.
- **Generalización**: Reducción de detalle según zoom.
- **Simplificación**: Reducción de vértices.
- **Pirámides**: Versiones de menor resolución.
- **Cache de teselas**: Almacenamiento de tiles generados.
- **Seeding**: Precálculo de teselas.
- **Cache-Control**: Control de caché HTTP.
- **ETag**: Identificador de versión.
- **Last-Modified**: Fecha de modificación.

### 4. Aplicación al proyecto
- Usar BBOX para limitar datos.
- Cachear tiles mediante GeoWebCache o WMTS.
- Usar PostGIS para consultas eficientes.
- Simplificar geometrías según nivel de zoom.
- Aplicar caché HTTP para mejorar el rendimiento.

## Datos explícitos
- El usuario aporta un glosario de términos GIS y arquitectura de mapas.
- El glosario incluye software, estándares, formatos y conceptos GIS.
- También incluye una sección de aplicación práctica al proyecto.
- El usuario quiere conservarlo por si decide incluirlo en el TFG.

## Datos inferidos
- La nota puede servir como base para una sección de definiciones o marco técnico.
- El contenido parece pensado como material propio de trabajo y no como transcripción de una fuente externa concreta.
- La clasificación temática más cercana es la de capas GIS y exposición por su relación con arquitectura cartográfica y servicios geoespaciales.

## Datos faltantes o ambiguos
- Si alguna definición procede de documentación externa concreta.
- Qué términos se incluirán finalmente en el TFG.
- Si conviene dividir este glosario en varias notas temáticas más pequeñas.
