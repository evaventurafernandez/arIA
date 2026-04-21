---
id: TFG-20260421-fuentes-viirs-modis-firms
título: "Fuentes verificadas para comparativa VIIRS vs MODIS en FIRMS"
tipo: referencia
tags:
  - tfg
  - incendios
  - firms
  - viirs
  - modis
  - fuentes
  - referencias
contexto: "Nota bibliográfica para sostener en la memoria del TFG la priorización de VIIRS frente a MODIS en NASA FIRMS, separando fuentes oficiales, documentación técnica y referencias científicas."
fuente_existe: true
fuente_tipo: otro
fuente_descripción: "Conjunto de fuentes oficiales y artículos científicos verificados sobre productos activos VIIRS y MODIS en NASA FIRMS."
fuente_url: "https://firms.modaps.eosdis.nasa.gov/"
autor_o_entidad: "NASA FIRMS, NASA Earthdata, NOAA/NESDIS, NOAA OSPO y varios autores"
fecha_fuente: "pendiente de confirmar"
licencia_o_copyright: "desconocido"
condiciones_de_uso: "Revisar condiciones específicas de cada portal y publicación; citar cada recurso de forma individual en la memoria cuando proceda."
grado_de_confianza: medio
pendientes_de_verificar:
  - "Confirmar el formato bibliográfico final que se usará en la memoria para artículos y recursos web."
  - "Añadir fechas exactas de consulta si se quiere una trazabilidad bibliográfica más estricta."
  - "No citar Hawbaker et al. (2017) como comparativa directa VIIRS/MODIS hasta encontrar la referencia correcta o sustituirla."
---

# Fuentes verificadas para comparativa VIIRS vs MODIS en FIRMS

## Contenido
Estas son las fuentes que sí están verificadas y resultan útiles para sostener la comparativa VIIRS frente a MODIS dentro del TFG:

### Fuentes oficiales y documentación técnica

- **NASA FIRMS**  
  Portal general y acceso a productos activos, mapas, descargas y documentación.  
  URL: `https://firms.modaps.eosdis.nasa.gov/`

- **NASA Earthdata - FIRMS / Active Fire Data Attributes for MODIS and VIIRS**  
  Útil para justificar la diferencia entre el centro de píxel de **1 km** en MODIS y el centro de píxel nominal de **375 m** en VIIRS, así como atributos relevantes como `confidence`, `scan`, `track` y `satellite`.  
  URL: `https://www.earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs`

- **NASA Earthdata - VIIRS I-Band 375 m Active Fire Data**  
  Fuente clave para sostener que VIIRS ofrece mejor respuesta sobre fuegos pequeños, mejor cartografía de perímetros y mejor rendimiento nocturno que MODIS.  
  URL: `https://www.earthdata.nasa.gov/data/instruments/viirs/viirs-i-band-375-m-active-fire-data`

- **NASA Earthdata - FIRMS FAQ**  
  Útil para identificar qué plataformas VIIRS están activas en FIRMS, diferenciar productos NRT y matizar tiempos de disponibilidad y alertas.  
  URL: `https://www.earthdata.nasa.gov/data/tools/firms/faq`

- **NOAA/NESDIS - JPSS Satellite and Instruments**  
  Recurso oficial para describir VIIRS como sensor operativo dentro del programa JPSS y reforzar el contexto instrumental de NOAA-20 y NOAA-21.  
  URL: `https://www.nesdis.noaa.gov/our-satellites/currently-flying/joint-polar-satellite-system/jpss-satellite-and-instruments`

- **NOAA OSPO - Hazard Mapping System Fire and Smoke Product**  
  Aporta cautelas útiles sobre artefactos en detección nocturna y sobre la interpretación operativa de focos térmicos.  
  URL: `https://www.ospo.noaa.gov/Products/land/hms.html`

### Publicaciones científicas útiles

- **Schroeder et al. (2014) - The New VIIRS 375 m active fire detection data product: Algorithm description and initial assessment**  
  DOI: `https://doi.org/10.1016/j.rse.2013.12.008`  
  Aporta la base metodológica del algoritmo VIIRS 375 m y su evaluación inicial.

- **Giglio et al. (2016) - The Collection 6 MODIS active fire detection algorithm and fire products**  
  DOI: `https://doi.org/10.1016/j.rse.2016.02.054`  
  Es la referencia de base para describir MODIS como producto más maduro y con continuidad histórica.

- **Hawbaker et al. (2008) - Detection rates of the MODIS active fire product in the United States**  
  DOI: `https://doi.org/10.1016/j.rse.2007.12.008`  
  Resulta útil para justificar que MODIS puede perder incendios pequeños y que su sensibilidad depende del tamaño del fuego.

### Referencia que conviene no usar todavía como comparativa directa

- **Hawbaker et al. (2017) - Mapping burned areas using dense time-series of Landsat data**  
  DOI: `https://doi.org/10.1016/j.rse.2017.06.027`  
  La referencia localizada con ese año trata de cartografía de áreas quemadas con Landsat. Puede ser útil para validación de históricos de incendio, pero **no debe citarse como comparativa directa VIIRS/MODIS** salvo que se verifique otra referencia distinta.

Resumen reutilizable:

- Para defender la prioridad de **VIIRS** en el TFG, bastan FIRMS, Earthdata, NOAA/NESDIS, NOAA OSPO y Schroeder et al. (2014), complementados por Giglio et al. (2016) y Hawbaker et al. (2008).
- **MODIS** debe seguir citándose como producto maduro e históricamente valioso, pero no como estándar operativo preferente para el visor.
- Si se quiere mantener una cita de **Hawbaker et al. (2017)**, conviene reetiquetarla como fuente de validación de áreas quemadas o sustituirla por una referencia realmente comparativa entre VIIRS y MODIS.

## Datos explícitos
- Se han identificado fuentes oficiales de NASA y NOAA para sostener la comparativa VIIRS frente a MODIS.
- Se han verificado como útiles Schroeder et al. (2014), Giglio et al. (2016) y Hawbaker et al. (2008).
- La referencia Hawbaker et al. (2017) no encaja como comparativa directa VIIRS/MODIS con la información actualmente localizada.

## Datos inferidos
- Esta nota pertenece a `10-fuentes-y-referencias/` porque su función principal es bibliográfica y de trazabilidad.
- Parte de estas referencias se reutilizarán después en la memoria, en `doc/apuntes/fuentes_tfg.md` y en futuras notas temáticas sobre incendios.
- Puede ser útil desdoblar más adelante esta nota en una bibliografía específica de FIRMS y otra de validación/áreas quemadas si el bloque de incendios crece.

## Datos faltantes o ambiguos
- Fecha exacta de publicación o actualización de algunos recursos web oficiales, si se quiere recoger en la memoria.
- Referencia bibliográfica exacta, si existe, para una comparación directa VIIRS/MODIS atribuible a Hawbaker et al. en 2017.
- Estilo final de cita bibliográfica que se usará en el TFG.
