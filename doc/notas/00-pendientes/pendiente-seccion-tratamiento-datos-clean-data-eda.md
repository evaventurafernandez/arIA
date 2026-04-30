---
id: TFG-20260428-pendiente-seccion-tratamiento-datos-clean-data-eda
título: "Pendiente: añadir al TFG una sección de tratamiento de datos, clean data y EDA"
tipo: pendiente
tags:
  - tfg
  - pendiente
  - estructura-memoria
  - tratamiento-de-datos
  - clean-data
  - eda
  - bibliografia
contexto: "Recordatorio de que la memoria del TFG debe incluir un apartado específico sobre tratamiento de datos, limpieza (clean data) y análisis exploratorio (EDA), en línea con lo que recoge el manual 'GIS AI Manual' de Jo Wilkin. Sirve también como punto de partida bibliográfico para no apoyarse únicamente en una guía docente y citar trabajos reconocidos."
fuente_existe: true
fuente_tipo: documentación
fuente_descripción: "Capítulo de la guía docente 'GIS AI Manual' dedicado a Exploratory Data Analysis. Es un material orientado a la docencia de GIS+IA que sintetiza pasos de inspección, limpieza y exploración aplicables a datos espaciales."
fuente_url: "https://jo-wilkin.github.io/gis-ai-manual/exploratory-data-analysis.html"
autor_o_entidad: "Jo Wilkin (GIS AI Manual)"
fecha_fuente: "pendiente de confirmar"
licencia_o_copyright: "desconocido"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: medio
pendientes_de_verificar:
  - "Decidir el lugar exacto del apartado en la memoria: capítulo propio, sección dentro de Metodología o anexo metodológico."
  - "Confirmar la fecha de consulta y el autor exacto del 'GIS AI Manual' antes de citarlo formalmente."
  - "Elegir cuáles de las referencias bibliográficas listadas se usan en la memoria final y revisar la última edición disponible de cada una."
  - "Comprobar si conviene añadir una referencia específica sobre calidad de datos espaciales (ISO 19157) según el nivel de profundidad que se quiera dar."
---

# Pendiente: añadir al TFG una sección de tratamiento de datos, clean data y EDA

## Contenido
La memoria del TFG debe incluir un apartado dedicado al tratamiento de datos, la limpieza (clean data) y el análisis exploratorio de datos (EDA). Hasta ahora la documentación del proyecto se ha centrado en describir las fuentes (AEMET, NASA FIRMS, EFFIS/Copernicus, CORINE, IGN, MITECO) y en los procesos de ingesta y publicación, pero falta una sección que explique de forma estructurada qué se hace con esos datos antes de visualizarlos: cómo se inspeccionan, cómo se filtran, cómo se normalizan, qué decisiones de limpieza se toman y qué exploración previa justifica los criterios usados (umbrales FRP, filtros de `confidence`, simplificación de geometrías, recorte por límite nacional, etc.).

El artículo de referencia que ha disparado la nota es el capítulo de EDA del *GIS AI Manual* de Jo Wilkin, que describe un flujo razonablemente típico para datos espaciales: revisión inicial, perfilado de variables, detección y tratamiento de valores atípicos y nulos, y exploración descriptiva antes de pasar a modelado o visualización. Es una buena guía de partida porque se sitúa explícitamente en contexto GIS, pero es un material docente; conviene apoyarse en referencias bibliográficas más reconocidas para sostener el apartado en una memoria de TFG.

La sección debería conectar este marco genérico con lo que ya se hace realmente en el repositorio (filtrado FIRMS por `confidence in {n, h}`, criterio VIIRS frente a MODIS, recorte espacial con el GeoJSON `spain_nuts_2024_01m`, simplificación de CORINE con `tolerance=0.005`, vectorización por píxel de las teselas WMTS de EFFIS, decisiones de simbología por FRP, etc.), de forma que la parte teórica no quede desconectada del prototipo.

## Datos explícitos
- Falta en la memoria un apartado específico de tratamiento de datos, limpieza y EDA.
- El disparador de esta nota es: https://jo-wilkin.github.io/gis-ai-manual/exploratory-data-analysis.html
- Esa fuente es útil como guía operativa, pero al ser material docente conviene reforzarla con bibliografía académica y técnica reconocida.
- La sección debe enlazar con los procesos ya documentados del proyecto (ingesta FIRMS, vectorización EFFIS, pipeline CORINE, núcleos IGN, límite GISCO).

## Propuesta de ubicación en la memoria
- Opción A: capítulo propio, p. ej. "Tratamiento y exploración de datos", entre "Fuentes de datos" y "Arquitectura del visor".
- Opción B: sección dentro del capítulo de Metodología, con subapartados de inspección, limpieza, normalización y EDA.
- Opción C: anexo metodológico, si se prefiere mantener el cuerpo de la memoria centrado en el visor y dejar el detalle del flujo de datos como material de soporte.

Recomendación inicial: opción A o B. El TFG trabaja con varias fuentes heterogéneas y las decisiones de limpieza condicionan directamente lo que se muestra en el visor, por lo que el apartado tiene entidad propia y no debería quedar relegado a anexo.

## Contenidos que debería cubrir el apartado
- Definición y diferencia entre tratamiento de datos, calidad de datos, limpieza (clean data) y EDA.
- Flujo aplicado en el proyecto: descarga, validación de esquema, normalización, filtrado, simplificación, georreferenciación y exportación.
- Decisiones tomadas en cada fuente, con justificación bibliográfica:
  - AEMET CAP: parseo del XML, criterios para clasificar nivel/severidad, tratamiento de avisos sin polígono, manejo de duplicados por `identifier`.
  - NASA FIRMS: filtros por `confidence`, recorte por límite nacional, gestión de falsos positivos y elección de VIIRS frente a MODIS.
  - EFFIS/Copernicus: vectorización por píxel desde teselas WMTS y limitaciones de la pérdida de atributos respecto a un servicio vectorial nativo.
  - CORINE: filtrado por `CODE_18`, simplificación, disolución por clase y reproyección.
  - Núcleos IGN: filtro por habitantes positivos, descartando registros sin dato o con `0` habitantes porque en escenarios de emergencia su riesgo poblacional se considera nulo; simplificación de geometrías y umbrales por escala/zoom.
- Análisis exploratorio mínimo: distribuciones de FRP, conteos por nivel de aviso y por fenómeno, comparativa visual FIRMS vs EFFIS, cobertura temporal del histórico, etc.
- Buenas prácticas adoptadas: trazabilidad de fuentes, registro de fecha de descarga, separación entre datos brutos, intermedios y publicados (esquema `source` / `core` / `pub` que ya usa el proyecto en PostgreSQL).

## Bibliografía recomendada como respaldo del apartado
Estas referencias son más adecuadas que una guía docente para sostener el apartado en una memoria de TFG. Se priorizan obras canónicas y trabajos ampliamente citados, combinando EDA estadístico, *tidy data* y calidad de datos espaciales.

- Tukey, J. W. (1977). *Exploratory Data Analysis*. Addison-Wesley. Obra fundacional del concepto de EDA; referencia obligada al introducir el término.
- Behrens, J. T. (1997). Principles and procedures of exploratory data analysis. *Psychological Methods*, 2(2), 131-160. https://doi.org/10.1037/1082-989X.2.2.131. Síntesis académica de los principios de Tukey, útil como cita más manejable que la obra original.
- Wickham, H. (2014). Tidy data. *Journal of Statistical Software*, 59(10), 1-23. https://doi.org/10.18637/jss.v059.i10. Referencia canónica para justificar criterios de organización y limpieza de tablas.
- Wickham, H., Çetinkaya-Rundel, M., & Grolemund, G. (2023). *R for Data Science* (2.ª ed.). O'Reilly. Introduce el flujo importar-ordenar-transformar-visualizar-modelar; muy citado en TFGs aunque el proyecto sea Python.
- McKinney, W. (2022). *Python for Data Analysis* (3.ª ed.). O'Reilly. Referencia natural para el stack del proyecto (pandas/geopandas) en la parte de tratamiento y exploración.
- VanderPlas, J. (2016). *Python Data Science Handbook*. O'Reilly. Complemento útil para la parte de visualización y exploración con Python.
- Van den Broeck, J., Cucchiara, S., Chapelle, A., Mwangi, M., & Argeseanu Cunningham, S. (2005). Data cleaning: detecting, diagnosing, and editing data abnormalities. *PLoS Medicine*, 2(10), e267. https://doi.org/10.1371/journal.pmed.0020267. Marco metodológico clásico para justificar pasos de limpieza.
- Rahm, E., & Do, H. H. (2000). Data cleaning: Problems and current approaches. *IEEE Data Engineering Bulletin*, 23(4), 3-13. Tipología muy citada de errores y técnicas de limpieza.
- Chapman, A. D. (2005). *Principles of Data Quality*. Global Biodiversity Information Facility (GBIF). https://doi.org/10.15468/doc.jrgg-a190. Referencia específica de calidad de datos en contexto espacial; encaja bien con un visor GIS.
- ISO 19157:2013. *Geographic information — Data quality*. Estándar internacional para describir calidad de datos geográficos; útil si se quiere dar formalidad al apartado de calidad espacial.
- de Smith, M. J., Goodchild, M. F., & Longley, P. A. (2024). *Geospatial Analysis: A Comprehensive Guide* (6.ª ed.). https://www.spatialanalysisonline.com. Manual abierto muy citado en TFGs de GIS, útil para enmarcar el análisis espacial básico.

## Próximos pasos
1. Decidir ubicación del apartado en la estructura de la memoria.
2. Redactar un borrador siguiendo el guion de "Contenidos que debería cubrir el apartado".
3. Citar Wilkin como guía operativa, pero sostener el discurso con Tukey, Wickham (2014), McKinney y Chapman como mínimo.
4. Cruzar el texto con las notas existentes en `doc/notas/03-incendios-firms-effis/`, `doc/notas/05-corine-y-usos-del-suelo/` y `doc/notas/07-historico-y-base-de-datos/` para no duplicar y para apoyar afirmaciones con ejemplos reales del prototipo.
