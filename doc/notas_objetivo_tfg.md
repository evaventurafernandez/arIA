# Notas para discutir el objetivo y alcance del TFG

La idea del TFG es desarrollar un visor web GIS para apoyar la lectura de Avisos de Fenómenos Meteorológicos Adversos y focos de incendio en España. El visor debe reunir información que normalmente se consulta por separado: AEMET, NASA FIRMS, EFFIS/Copernicus, CORINE Land Cover, núcleos de población, carreteras IGN, espacios protegidos y capas de peligrosidad.

Además del mapa, interesa incluir una capa de consulta en lenguaje natural con LLM. La idea no sería que el LLM decida, sino que ayude a preguntar al visor cosas como: "muéstrame los avisos peligrosos cerca de núcleos de población" o "compara los focos FIRMS con Copernicus".

## Objetivo propuesto

Desarrollar un prototipo de visor cartográfico web que integre Avisos de Fenómenos Meteorológicos Adversos, focos de incendio y capas geográficas de exposición y peligrosidad, para facilitar la consulta, filtrado y análisis espacial básico de situaciones de riesgo en España.

Como objetivo complementario, el TFG puede preparar una interfaz LLM para operar el visor mediante lenguaje natural: activar capas, filtrar avisos, consultar focos, pedir resúmenes y explicar qué datos se han usado.

## Alcance actual del prototipo

El prototipo ya cuenta con un mapa Leaflet, una API FastAPI y varias capas GIS integradas. Ahora mismo permite:

- consultar avisos AEMET activos en formato CAP;
- representar avisos como polígonos cuando incluyen geometría;
- consultar focos NASA FIRMS recientes y filtrarlos con el límite de España;
- clasificar focos por FRP;
- activar capas WMS de inundabilidad T=100, FWI, sequía DC y CORINE;
- usar una capa CORINE local filtrada para usos forestales y agrícolas;
- mostrar focos EFFIS/Copernicus vectorizados desde teselas WMTS;
- usar leyenda dinámica, filtros, listado lateral y línea temporal de avisos;
- activar capas relacionadas al seleccionar avisos de agua o focos de incendio.

## Ajustes según las anotaciones del profesor

El alcance debería quedar algo más orientado a datos GIS concretos:

- CORINE: trabajar con GeoPackage vectorial, filtrando clases relevantes y simplificando geometría para reducir peso. La idea apuntada es quedarse con unas 9 clases útiles en vez de cargar todo el conjunto.
- Avisos peligrosos: definir condiciones claras para considerar un aviso como relevante, por nivel, fenómeno, zona afectada o cruce con otras capas.
- Núcleos de población: incorporarlos al visor y ajustar su visibilidad según escala o zoom, combinándolos con usos del suelo.
- Carreteras IGN: añadir una capa de red viaria, al menos distinguiendo carreteras principales si la fuente lo permite.
- Espacios protegidos: incorporar parques naturales, espacios protegidos o capas de biodiversidad para valorar afección ambiental.
- Histórico AEMET: estudiar cómo recopilar avisos históricos desde la API o archivos disponibles, guardando fecha de inicio, fecha de fin, fenómeno, zona y evolución del aviso.
- Focos de incendio: contrastar NASA FIRMS con EFFIS/Copernicus para ver diferencias, coincidencias y limitaciones de cada fuente.
- Base de datos: guardar datos actuales e históricos para poder consultar evolución, no depender solo de la memoria de la aplicación.
- LLM: incluirlo como forma de consulta del visor, conectado a datos y operaciones GIS reales, no como respuesta libre sin trazabilidad.

## Lo que ya se puede considerar cumplido

- Integración inicial de avisos AEMET y focos NASA FIRMS.
- Visualización cartográfica básica de España.
- Filtros por nivel y tipo de aviso.
- Listado lateral sincronizado con el mapa.
- Línea temporal para avisos activos y próximos.
- Capas WMS de inundabilidad, FWI, sequía y CORINE.
- CORINE local filtrado para usos forestales y agrícolas.
- Límite territorial de España en GeoJSON para filtrar FIRMS.
- Capa local EFFIS/Copernicus derivada de WMTS.
- Panel resumen con número de avisos, focos y FRP máximo.
- Scripts auxiliares para generar capas locales.

## Lo que queda por cerrar

- Añadir núcleos de población al visor, no solo generar el GeoJSON.
- Añadir carreteras IGN o decidir una fuente equivalente.
- Añadir espacios protegidos o biodiversidad como capa de exposición ambiental.
- Refinar CORINE: clases finales, simplificación y escala de visualización.
- Definir reglas de "aviso peligroso" y prioridad visual.
- Hacer cruces espaciales reales: intersección con inundabilidad, proximidad a población, carreteras y espacios protegidos.
- Crear una base de datos para histórico de avisos y focos.
- Preparar consultas históricas: preguntas, evolución y progreso de aviso.
- Conectar el LLM a acciones concretas del visor y a consultas sobre datos cargados.

## Papel del LLM

El LLM debería plantearse como una interfaz de ayuda para usuarios no expertos en GIS. Puede traducir preguntas normales a operaciones del visor: activar capas, aplicar filtros, buscar zonas, comparar fuentes o generar un resumen.

Para el TFG, el alcance razonable sería un LLM básico y controlado. Por ejemplo:

- interpretar consultas sobre avisos, focos y capas;
- activar una vista temática;
- devolver un resumen con los datos usados;
- indicar si no hay datos suficientes;
- dejar trazabilidad de la pregunta, filtros y capas consultadas.

No conviene presentarlo como un modelo predictivo ni como un sistema que toma decisiones. Su valor estaría en facilitar el uso del visor y explicar resultados.

## Alcance recomendado para defender

Yo defendería el TFG como un visor GIS operativo con apoyo LLM básico. El núcleo sería la integración de fuentes, la visualización cartográfica, el análisis espacial simple y la preparación de histórico.

El alcance mínimo defendible sería:

- avisos AEMET activos y, si es viable, histórico inicial;
- focos NASA FIRMS y contraste con EFFIS/Copernicus;
- CORINE filtrado y simplificado;
- núcleos de población;
- carreteras IGN;
- espacios protegidos o biodiversidad;
- capas de inundabilidad, FWI y sequía;
- reglas simples para destacar avisos o focos relevantes;
- base de datos para guardar histórico básico;
- LLM como consulta guiada sobre capas, filtros y resúmenes.

Dejaría fuera la predicción automática, la toma de decisiones de emergencia y un LLM avanzado que razone sin estar conectado a datos del visor.

## Dudas para hablar con el profesor

- Si el histórico AEMET debe cubrir muchos años o basta con preparar una primera base.
- Qué fuente concreta usar para carreteras y espacios protegidos.
- Qué clases de CORINE son necesarias para el caso de uso.
- Qué condiciones definen un aviso peligroso.
- Qué se espera del LLM: prototipo visible, diseño funcional o integración mínima.
- Cómo validar el resultado: episodios reales, comparación FIRMS-Copernicus o revisión de zonas concretas.

## Actualización 2026-04-22 sobre landcover interactivo

Se ha refinado bastante la línea de `landcover` respecto a lo que se planteaba al principio. La visualización filtrada local del proyecto sigue teniendo sentido para publicación propia, pero la consulta puntual vinculada a la capa visible del `IGN` ha terminado evolucionando hacia `GetFeatureInfo`, porque era la única forma de hacer coincidir de verdad lo que el usuario ve con lo que el visor devuelve al pinchar.

Además, esa línea se ha conectado ya con los focos `NASA FIRMS`: las cards del sidebar pueden mostrar el tipo de uso del suelo en el que cae cada foco y el mapa puede resaltar el polígono asociado. El detalle y la historia de este cambio quedan documentados en:

- `doc/notas/05-corine-y-usos-del-suelo/evolucion-consulta-puntual-landcover-de-core-a-getfeatureinfo-ign.md`
- `doc/notas/03-incendios-firms-effis/contextualizacion-de-focos-nasa-firms-con-usos-del-suelo.md`
