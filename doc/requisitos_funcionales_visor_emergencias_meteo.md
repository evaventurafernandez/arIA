# Requisitos funcionales del visor web de alertas y avisos de fenómenos meteorológicos y apoyo a la gestión de emergencias en España

## 1. Objeto del documento

El presente documento define los objetivos, alcance y requisitos funcionales de una plataforma web de visualización y análisis orientada a la monitorización de riesgos meteorológicos y de incendios en el ámbito de España.

La plataforma se concibe como un visor cartográfico operativo para apoyo a la gestión de emergencias, capaz de integrar información procedente de distintas fuentes oficiales y temáticas, cruzarla con capas de exposición y peligrosidad, y facilitar tanto la consulta experta como la operación por parte de usuarios sin conocimientos GIS mediante una interfaz conversacional basada en LLM.

---

## 2. Objetivo general del sistema

El sistema deberá proporcionar un visor web operativo para la monitorización, consulta y evaluación integrada de riesgos meteorológicos e incendios en España, permitiendo:

- visualizar eventos en curso e históricos;
- cruzar dichos eventos con capas temáticas de peligrosidad y exposición;
- generar indicadores y prioridades operativas;
- facilitar la interpretación de la información por parte de usuarios técnicos y no técnicos;
- servir de base para capacidades futuras de analítica avanzada y modelos de clasificación o predicción.

---

## 3. Objetivos específicos

Son objetivos específicos del sistema:

1. Integrar en una misma interfaz cartográfica los avisos meteorológicos adversos y los focos de incendio detectados por satélite.
2. Facilitar la interpretación del riesgo mediante la combinación de capas de contexto y exposición.
3. Apoyar la priorización operativa de eventos en función de su severidad, peligrosidad potencial y posible afección a población e infraestructuras.
4. Proporcionar visión temporal e histórica de los avisos y eventos para seguimiento y análisis.
5. Reducir la barrera de uso del sistema mediante un asistente en lenguaje natural que permita operar la plataforma sin conocimientos especializados en SIG.
6. Dejar preparada la base funcional y de datos para futuros modelos de apoyo a decisión, clasificación o predicción de peligrosidad.

---

## 4. Alcance funcional

El alcance funcional de la plataforma comprende:

- la adquisición y representación de datos procedentes de distintas APIs y servicios cartográficos;
- la visualización cartográfica interactiva de eventos y capas temáticas;
- el filtrado, consulta y análisis espacial básico de la información;
- la evaluación funcional del riesgo mediante reglas configurables;
- la consulta temporal e histórica de eventos;
- la generación de vistas operativas y resúmenes de situación;
- la interacción en lenguaje natural con el sistema mediante un asistente LLM.

Quedan fuera del alcance inicial, salvo evolución posterior:

- la sustitución del criterio técnico u operativo humano;
- la automatización de decisiones ejecutivas sobre emergencias;
- la predicción plenamente automatizada con efectos vinculantes;
- la gestión transaccional completa de incidentes o recursos de emergencia externos al visor.

---

## 5. Ámbito geográfico y temporal

### 5.1. Ámbito geográfico

El sistema tendrá como ámbito principal el territorio de España, con capacidad para representar:

- información a escala nacional;
- información por comunidad autónoma;
- información provincial o zonal;
- información local cuando la resolución de la fuente lo permita.

### 5.2. Ámbito temporal

El sistema deberá soportar:

- visualización en curso o cuasi-tiempo real;
- consulta retrospectiva de eventos históricos;
- comparación temporal de situaciones;
- reproducción temporal de la evolución de los eventos.

---

## 6. Fuentes de información previstas

### 6.1. Avisos meteorológicos AEMET

Fuente principal para avisos meteorológicos adversos en formato CAP.

Uso funcional previsto:

- representación de avisos vigentes;
- consulta de metadatos del aviso;
- explotación histórica de archivos disponibles;
- clasificación temática de avisos ligados a agua o inundación.

### 6.2. NASA FIRMS

Fuente principal para detección de focos activos de incendio o anomalías térmicas.

Uso funcional previsto:

- representación de hotspots detectados por satélite;
- filtrado temporal y por sensor;
- explotación del histórico;
- valoración del riesgo combinada con otras capas.

### 6.3. Capa de peligrosidad por inundación fluvial T=10

Servicio WMS de mapas de peligrosidad por inundación fluvial para período de retorno de 10 años, asociado a un escenario de probabilidad alta.

Uso funcional previsto:

- cruce espacial con avisos asociados a lluvia, tormenta, deshielo, DANA y fenómenos análogos;
- valoración de riesgo de inundación;
- apoyo a la priorización operativa.

### 6.4. Capas EFFIS / Copernicus

Capas WMS actualizadas con periodicidad diaria para valorar el peligro de propagación de incendios y la sequía.

Uso funcional previsto:

- valoración del contexto meteorológico de propagación del fuego;
- cruce espacial con hotspots;
- apoyo a la priorización operativa.

### 6.5. Usos del suelo

Capas temáticas de uso/cobertura del suelo para clasificar el entorno potencialmente afectado.

Uso funcional previsto:

- identificación de usos forestales;
- identificación de usos agrícolas o de cultivo;
- discriminación de entornos menos críticos.

### 6.6. Núcleos de población

Capas de asentamientos, poblaciones o entidades de población.

Uso funcional previsto:

- evaluación de exposición humana;
- apoyo a priorización;
- resúmenes territoriales.

### 6.7. Red viaria

Capas de carreteras y, cuando sea posible, jerarquización de la red principal y secundaria.

Uso funcional previsto:

- valoración de afección a la movilidad y accesibilidad;
- apoyo a priorización;
- análisis de impacto potencial.

---

## 7. Principios funcionales de diseño

La solución deberá construirse conforme a los siguientes principios funcionales:

1. **Interpretabilidad**: el usuario debe poder comprender qué está viendo y por qué un evento se considera más relevante que otro.
2. **Trazabilidad**: toda visualización o resultado deberá poder asociarse a su fuente y momento temporal.
3. **Operatividad**: el visor debe facilitar la detección rápida de situaciones relevantes.
4. **Configurabilidad**: las reglas de priorización y clasificación deberán poder ajustarse.
5. **Escalabilidad funcional**: el sistema debe poder crecer con nuevas capas, reglas y fuentes.
6. **Accesibilidad de uso**: el sistema debe poder ser utilizado por perfiles no expertos gracias al asistente LLM.
7. **Separación entre dato y recomendación**: el sistema apoya, pero no sustituye, la decisión técnica.

---

## 8. Perfiles de usuario previstos

Se contemplan, al menos, los siguientes perfiles funcionales:

### 8.1. Usuario consultor general

Perfil que necesita visualizar información, entender la situación general y realizar consultas sencillas.

### 8.2. Usuario analista / operador

Perfil con necesidad de utilizar filtros avanzados, cruces espaciales, histórico, exportaciones y priorización operativa.

### 8.3. Usuario supervisor / administrador funcional

Perfil con capacidad para:

- configurar reglas de negocio;
- revisar clasificaciones;
- validar resultados;
- administrar catálogos y parámetros del asistente LLM.

---

## 9. Casos de uso principales

1. Consultar los avisos meteorológicos activos de una zona concreta.
2. Identificar avisos de lluvia o tormenta con afección potencial a zonas inundables.
3. Consultar hotspots de incendio recientes y valorar su peligrosidad de propagación.
4. Identificar eventos cercanos a núcleos de población o carreteras.
5. Generar un resumen ejecutivo de situación por territorio.
6. Revisar la evolución temporal de un episodio.
7. Consultar el histórico de avisos o focos en una zona concreta.
8. Preguntar al sistema en lenguaje natural qué eventos presentan mayor prioridad.
9. Pedir al sistema que configure automáticamente una vista temática sin usar herramientas GIS manuales.
10. Exportar el resultado de un análisis o consulta.

---

## 10. Requisitos funcionales generales del visor

### RF-01. Visualización cartográfica básica
El sistema deberá mostrar un mapa interactivo de España con navegación estándar: zoom, desplazamiento, ajuste a extensión, escala y cambio de mapa base.

### RF-02. Gestión de capas
El sistema deberá permitir activar, desactivar, reordenar y ajustar la transparencia de las capas disponibles.

### RF-03. Leyenda dinámica
El sistema deberá mostrar una leyenda dinámica para cada capa activa, incluyendo simbología, niveles de severidad, categorías de riesgo y fuente de procedencia.

### RF-04. Panel de fuentes
El sistema deberá disponer de un panel donde se identifique claramente cada fuente de información, su fecha/hora de actualización y su cobertura territorial.

### RF-05. Búsqueda y localización
El sistema deberá permitir buscar localizaciones, municipios, provincias o coordenadas y centrar el mapa en el resultado.

### RF-06. Selección por área
El sistema deberá permitir seleccionar una zona en el mapa y obtener el resumen de avisos, focos y capas de riesgo que intersectan con ella.

### RF-07. Consulta multicriterio
El sistema deberá permitir consultas combinadas sobre capas, fenómenos, niveles, fechas y territorios.

---

## 11. Requisitos funcionales sobre avisos meteorológicos AEMET

### RF-08. Ingesta de avisos meteorológicos vigentes
El sistema deberá consumir y representar los avisos CAP vigentes de AEMET para el ámbito geográfico seleccionado.

### RF-09. Representación geográfica de avisos
El sistema deberá representar cada aviso meteorológico sobre el mapa mediante su geometría asociada o, en su defecto, mediante la zona de aviso correspondiente.

### RF-10. Ficha de detalle del aviso
Al seleccionar un aviso, el sistema deberá mostrar al menos:

- identificador del aviso;
- fenómeno;
- nivel o severidad;
- probabilidad;
- ámbito geográfico;
- fecha/hora de inicio;
- fecha/hora de fin;
- estado del aviso;
- descripción o titular;
- fuente.

### RF-11. Filtrado de avisos
El sistema deberá permitir filtrar avisos por:

- comunidad autónoma;
- provincia o zona;
- tipo de fenómeno;
- nivel de severidad;
- estado;
- rango temporal.

### RF-12. Histórico de avisos
El sistema deberá permitir consultar avisos históricos procedentes de los archivos disponibles de la API o repositorio de almacenamiento que alimente la plataforma.

### RF-13. Comparación temporal de avisos
El sistema deberá permitir comparar la evolución de avisos meteorológicos en el tiempo, mostrando:

- aparición;
- actualización;
- intensificación;
- desactivación;
- cambios espaciales.

### RF-14. Línea temporal de avisos
El sistema deberá incluir una línea temporal o selector temporal para reproducir la evolución de los avisos históricos sobre el mapa.

### RF-15. Clasificación temática de avisos por riesgo de inundación
El sistema deberá identificar automáticamente los avisos asociados a fenómenos de agua o inundación a partir de reglas configurables basadas en palabras clave, categorías, parámetros y metadatos del aviso.

### RF-16. Gestión de vocabulario funcional para fenómenos de agua
El sistema deberá permitir mantener un vocabulario configurable de términos relacionados con inundación o fenómenos hidrometeorológicos, incluyendo, entre otros: lluvia, precipitación, tormenta, costero, nieve derretida, deshielo, vaguada y DANA.

---

## 12. Requisitos funcionales sobre riesgo de inundación

### RF-17. Cruce de avisos con capa de peligrosidad fluvial T10
Cuando un aviso meteorológico sea clasificado como relacionado con inundación o agua, el sistema deberá cruzarlo espacialmente con la capa de peligrosidad fluvial T=10 años.

### RF-18. Indicador de exposición a inundación
El sistema deberá generar un indicador funcional de exposición o coincidencia entre:

- zona del aviso meteorológico;
- peligrosidad fluvial;
- núcleos de población;
- red viaria.

### RF-19. Priorización visual de avisos por impacto potencial
El sistema deberá destacar visualmente aquellos avisos de agua o inundación cuya intersección espacial afecte a zonas inundables, población o carreteras relevantes.

### RF-20. Ficha de evaluación de riesgo por inundación
Para cada aviso asociado a inundación, el sistema deberá mostrar una ficha resumen con:

- superficie afectada;
- grado de solape con zonas inundables;
- núcleos de población potencialmente expuestos;
- tramos viarios potencialmente afectados;
- nivel de prioridad calculado.

---

## 13. Requisitos funcionales sobre focos de incendio NASA FIRMS

### RF-21. Ingesta de focos activos
El sistema deberá consumir y representar los focos activos o hotspots proporcionados por NASA FIRMS para el ámbito de España o la extensión visible del mapa.

### RF-22. Ficha de detalle del foco
Al seleccionar un hotspot, el sistema deberá mostrar al menos:

- sensor u origen;
- fecha/hora de detección;
- latitud y longitud;
- confianza o atributo equivalente;
- potencia radiativa o atributos disponibles;
- fuente.

### RF-23. Filtrado de focos de incendio
El sistema deberá permitir filtrar los focos por:

- fecha/hora;
- sensor;
- confianza;
- intensidad disponible;
- ventana temporal.

### RF-24. Histórico de focos
El sistema deberá permitir visualizar focos recientes y focos históricos en rangos temporales configurables.

---

## 14. Requisitos funcionales sobre riesgo de incendio

### RF-25. Cruce con capas de peligro de propagación
El sistema deberá cruzar espacialmente cada hotspot con las capas de peligro de propagación y sequía disponibles procedentes de EFFIS u otras fuentes equivalentes.

### RF-26. Cruce con usos del suelo
El sistema deberá cruzar cada hotspot con la capa de usos del suelo y clasificar la peligrosidad del entorno, al menos distinguiendo:

- forestal;
- cultivo;
- otros usos.

### RF-27. Indicador de propagación potencial
El sistema deberá calcular un indicador funcional de propagación potencial del incendio a partir de la combinación de:

- hotspot;
- peligro meteorológico de propagación;
- sequía;
- uso del suelo.

### RF-28. Priorización visual de incendios
El sistema deberá destacar visualmente aquellos hotspots con mayor peligrosidad potencial en función del entorno y de los índices disponibles.

### RF-29. Ficha de evaluación de riesgo por incendio
Para cada foco, el sistema deberá mostrar una ficha resumen con:

- nivel de peligro meteorológico de propagación;
- nivel de sequía;
- tipo de uso del suelo afectado;
- proximidad a núcleos de población;
- proximidad a carreteras;
- nivel de prioridad calculado.

---

## 15. Requisitos funcionales sobre capas de exposición y contexto

### RF-30. Capa de núcleos de población
El sistema deberá incorporar una capa de núcleos de población y permitir su consulta individual.

### RF-31. Capa de red viaria
El sistema deberá incorporar una capa de carreteras y permitir distinguir, al menos, la red principal de la secundaria si la fuente lo permite.

### RF-32. Evaluación de proximidad a elementos vulnerables
El sistema deberá calcular la proximidad o intersección de avisos y hotspots con:

- núcleos de población;
- carreteras;
- otras infraestructuras críticas que se incorporen en el futuro.

### RF-33. Resumen territorial de exposición
El sistema deberá mostrar resúmenes territoriales agregados por comunidad, provincia o municipio sobre:

- avisos activos;
- focos activos;
- población potencialmente expuesta;
- carreteras potencialmente afectadas.

---

## 16. Requisitos funcionales de priorización operativa

### RF-34. Sistema de priorización operativa
El sistema deberá generar una prioridad operativa para cada evento o aviso, basada en reglas configurables.

### RF-35. Reglas configurables
El sistema deberá permitir parametrizar reglas de negocio sin necesidad de cambiar el código, incluyendo pesos o umbrales para:

- severidad del aviso;
- tipo de fenómeno;
- solape con capas de riesgo;
- proximidad a población;
- proximidad a carreteras;
- peligro de propagación;
- uso del suelo;
- recurrencia histórica;
- combinación de factores.

### RF-36. Explicabilidad del resultado
El sistema deberá mostrar de forma comprensible por qué un aviso o foco ha sido clasificado con una prioridad determinada.

### RF-37. Panel resumen de situación
El visor deberá disponer de un panel ejecutivo con indicadores de situación, al menos:

- número de avisos activos por nivel;
- número de focos activos;
- eventos priorizados;
- territorios con mayor concentración de riesgo.

### RF-38. Alertas visuales operativas
El sistema deberá resaltar en el panel y en el mapa los eventos cuya prioridad supere un umbral definido.

---

## 17. Requisitos funcionales temporales e históricos

### RF-39. Persistencia de series temporales
El sistema deberá almacenar la información histórica necesaria para reconstruir la evolución temporal de avisos y focos.

### RF-40. Comparación temporal
El sistema deberá permitir comparar períodos distintos para evaluar evolución, concentración o agravamiento de la situación.

### RF-41. Reproducción temporal
El sistema deberá permitir reproducir la evolución de eventos mediante una línea temporal o mecanismo equivalente.

### RF-42. Consulta histórica territorial
El sistema deberá permitir consultar el histórico de una zona geográfica concreta, incluyendo avisos, focos y su comportamiento en el tiempo.

---

## 18. Requisitos funcionales de exportación y explotación

### RF-43. Exportación de resultados
El sistema deberá permitir exportar consultas, listados o fichas en formatos reutilizables, al menos CSV y PDF.

### RF-44. Exportación de vista operativa
El sistema deberá permitir exportar una vista cartográfica activa con sus capas, filtros y elementos destacados.

### RF-45. Generación de resúmenes
El sistema deberá permitir generar resúmenes de situación por territorio, fenómeno o período temporal.

---

## 19. Requisitos funcionales del asistente LLM / interfaz conversacional

### 19.1. Objetivo funcional del asistente

El sistema deberá incorporar un asistente basado en modelos de lenguaje natural que permita a usuarios no expertos consultar, filtrar, interpretar y explotar la información del visor mediante instrucciones en lenguaje natural, reduciendo la necesidad de conocimientos GIS y facilitando la toma de decisiones.

### RF-46. Interfaz conversacional integrada
El sistema deberá disponer de una interfaz conversacional integrada en la web desde la que el usuario pueda realizar consultas o instrucciones en lenguaje natural.

### RF-47. Comprensión de lenguaje natural orientada a operaciones GIS
El asistente deberá interpretar consultas del usuario y traducirlas a operaciones funcionales sobre el visor, incluyendo al menos:

- activación y desactivación de capas;
- zoom a un territorio;
- filtrado por fecha, fenómeno, severidad o fuente;
- búsqueda de eventos;
- cruce de capas;
- consulta de proximidad;
- consulta de prioridad o riesgo.

### RF-48. Traducción de lenguaje natural a acciones del visor
El sistema deberá transformar la intención del usuario en acciones ejecutables sobre la plataforma.

### RF-49. Generación automática de vistas temáticas
El asistente deberá poder construir automáticamente vistas de trabajo combinando capas, filtros y extensión geográfica según la consulta del usuario.

### RF-50. Explicación comprensible de resultados
El asistente deberá devolver respuestas comprensibles, en lenguaje no técnico, explicando:

- qué datos ha utilizado;
- qué criterios ha aplicado;
- qué resultados ha encontrado;
- qué limitaciones existen.

### RF-51. Respuesta híbrida texto + mapa
El sistema deberá responder a las consultas del usuario mediante una combinación de:

- texto explicativo;
- cambios en el mapa;
- resaltado de elementos;
- apertura de fichas o paneles;
- indicadores o listados.

### RF-52. Consulta resumida de situación
El asistente deberá poder ofrecer resúmenes ejecutivos de situación.

### RF-53. Consultas guiadas para usuarios no expertos
El sistema deberá ofrecer ejemplos de preguntas o sugerencias guiadas para facilitar el uso del asistente a perfiles no técnicos.

### RF-54. Interpretación de sinónimos y lenguaje no técnico
El asistente deberá reconocer expresiones no técnicas o equivalentes funcionales.

### RF-55. Gestión de ambigüedad
Cuando la petición del usuario sea ambigua, el asistente deberá:

- pedir aclaración;
- proponer opciones;
- o ejecutar una interpretación razonable explicando la decisión tomada.

### RF-56. Explicación del razonamiento funcional
El asistente deberá poder indicar qué operación ha realizado sobre el visor en términos comprensibles.

### RF-57. Consulta sobre eventos concretos
El asistente deberá permitir preguntas sobre un elemento específico del mapa o una ficha.

### RF-58. Generación de listados y resúmenes exportables
El asistente deberá poder generar, a petición del usuario, listados o resúmenes exportables de los resultados obtenidos.

### RF-59. Soporte a consultas temporales
El asistente deberá entender consultas temporales relativas y absolutas.

### RF-60. Soporte a histórico conversacional e histórico de eventos
El asistente deberá permitir explotar el histórico mediante preguntas comparativas o evolutivas.

### RF-61. Soporte a priorización operativa
El asistente deberá responder preguntas operativas sobre qué eventos presentan mayor prioridad o combinación de riesgo y exposición.

### RF-62. Recomendación de vistas y análisis
El asistente deberá sugerir de forma proactiva capas o análisis relevantes según el contexto.

### RF-63. Limitación a capacidades autorizadas
El asistente deberá operar únicamente sobre las capas, acciones y datos autorizados por la plataforma.

### RF-64. Trazabilidad de la respuesta del LLM
El sistema deberá registrar para cada respuesta del asistente:

- consulta del usuario;
- intención interpretada;
- capas y filtros aplicados;
- datos consultados;
- resultado devuelto.

### RF-65. Validación de resultados críticos
En respuestas que impliquen priorización o clasificación de riesgo, el sistema deberá mostrar que el resultado proviene de reglas, datos geoespaciales y criterios configurados, y no sólo de generación libre del modelo.

### RF-66. Modo explicativo o formativo
El asistente deberá poder operar en modo explicativo para enseñar al usuario qué está viendo en el mapa y cómo interpretar las capas.

### RF-67. Ayuda contextual
El sistema deberá permitir que el usuario pregunte directamente por términos, indicadores, capas o conceptos.

### RF-68. Acceso conversacional a cuadros de mando
El asistente deberá poder responder preguntas agregadas sobre los indicadores del panel.

---

## 20. Requisitos funcionales de control, fiabilidad y gobierno del LLM

### RF-69. Respuestas basadas en datos de la plataforma
El asistente deberá fundamentar sus respuestas en los datos realmente cargados en la plataforma y no en conocimiento genérico no verificado.

### RF-70. Indicación de incertidumbre
Cuando el sistema no disponga de datos suficientes o exista ambigüedad, el asistente deberá indicarlo expresamente.

### RF-71. No sustitución del criterio operativo
El asistente deberá presentarse como herramienta de apoyo a la interpretación y operación del visor, no como sustituto de la decisión técnica u operativa.

### RF-72. Validación humana de configuraciones sensibles
Las reglas de priorización, clasificación y etiquetado utilizadas por el asistente deberán ser configurables y revisables por personal autorizado.

### RF-73. Registro de interacciones
El sistema deberá permitir auditar las interacciones relevantes con el asistente cuando afecten a análisis operativos o generación de resultados exportables.

---

## 21. Requisitos funcionales para analítica avanzada y evolución futura

### RF-74. Preparación para analítica avanzada
El sistema deberá permitir explotar el histórico para análisis estadístico y entrenamiento futuro de modelos de clasificación o predicción.

### RF-75. Etiquetado funcional para entrenamiento
El sistema deberá permitir registrar o generar etiquetas funcionales del tipo:

- peligroso / no peligroso;
- prioridad alta / media / baja;
- afectación a población;
- afectación a carreteras;
- coincidencia con zonas de riesgo.

### RF-76. Revisión humana del etiquetado
El sistema deberá permitir que un usuario autorizado revise o corrija la clasificación de eventos para mejorar la calidad del histórico.

### RF-77. Integración futura de modelos analíticos
La arquitectura funcional deberá permitir incorporar en fases posteriores modelos que apoyen la clasificación, recomendación o predicción de peligrosidad.

---

## 22. Requisitos funcionales transversales

### RF-78. Trazabilidad de la fuente
Todo dato visualizado deberá conservar referencia a:

- fuente;
- fecha/hora de obtención;
- fecha/hora del dato;
- versión o identificador cuando exista.

### RF-79. Indicación de frescura del dato
El sistema deberá informar si una capa está actualizada, retrasada o no disponible.

### RF-80. Gestión de indisponibilidad de fuentes
Si una fuente externa no está disponible, el visor deberá mantener visible la última versión válida disponible e informar claramente de ello.

### RF-81. Sincronización temporal entre capas
El sistema deberá permitir consultar simultáneamente capas con distinta frecuencia de actualización, dejando visible la fecha/hora real de cada una.

### RF-82. Configurabilidad funcional
El sistema deberá permitir incorporar nuevas capas, nuevas reglas y nuevas fuentes sin rediseñar el comportamiento funcional global del visor.

---

## 23. Fases de implantación recomendadas

## 23.1. Fase 1 — MVP del visor operativo

Objetivo: disponer de una plataforma GIS funcional, sólida y trazable.

### Incluye:

- visor cartográfico base;
- gestión de capas y leyendas;
- ingesta de avisos AEMET actuales;
- ingesta de hotspots NASA actuales;
- capas FWI/DC de EFFIS, inundabilidad, usos del suelo, población y carreteras;
- fichas de detalle;
- filtros básicos;
- cruces espaciales básicos;
- panel resumen de situación;
- reglas iniciales de priorización;
- persistencia de datos históricos básicos;
- preparación técnica del asistente LLM mediante APIs internas y catálogo funcional de operaciones.

### No incluye como capacidad visible principal:

- asistente LLM operativo completo;
- explotación conversacional compleja del histórico;
- modelos de predicción.

## 23.2. Fase 2 — Asistente LLM operativo básico

Objetivo: permitir operar la plataforma sin conocimientos GIS en tareas frecuentes.

### Incluye:

- interfaz conversacional integrada;
- consultas en lenguaje natural;
- activación/desactivación de capas por lenguaje natural;
- filtros y búsquedas guiadas;
- zoom y configuración automática de vistas temáticas;
- resúmenes ejecutivos;
- explicación de capas, conceptos y resultados;
- soporte a preguntas operativas sencillas;
- trazabilidad de respuestas del asistente.

## 23.3. Fase 3 — Asistente LLM analítico avanzado y explotación histórica

Objetivo: convertir el asistente en una capa de apoyo analítico y operacional avanzada.

### Incluye:

- consultas multicriterio complejas;
- comparación temporal avanzada;
- explotación conversacional del histórico;
- sugerencias proactivas;
- apoyo a priorización operativa explicable;
- generación avanzada de informes y resúmenes;
- soporte al etiquetado de datos;
- base funcional para modelos predictivos o clasificadores futuros.

---

## 24. Valoración de implantación del asistente LLM

Se considera que la inclusión del asistente LLM aporta un valor muy alto al proyecto, pero su introducción debe hacerse de forma escalonada.

### Valor principal del LLM

- reduce la barrera de uso para usuarios no expertos en SIG;
- facilita la explotación de la plataforma por perfiles operativos;
- mejora la interpretabilidad del sistema;
- permite generar vistas y consultas complejas sin formación técnica específica;
- puede convertirse en una capa transversal de acceso a la información y de apoyo a decisión.

### Motivo para no situarlo como núcleo del MVP

El asistente sólo resultará fiable si previamente existe una base robusta en:

- catálogo de capas y metadatos;
- operaciones GIS encapsuladas;
- reglas de negocio bien definidas;
- trazabilidad de fuentes;
- resultados verificables.

Por ello, se recomienda:

- **preparar la arquitectura del LLM en Fase 1**,
- **implantar el LLM operativo básico en Fase 2**,
- **implantar la capa analítica avanzada en Fase 3**.

---

## 25. Recomendación final de alcance para un pliego o memoria funcional

A efectos de definición funcional, se recomienda expresar el alcance del proyecto del siguiente modo:

> El sistema proporcionará un visor web de apoyo a la gestión de emergencias en España, integrando avisos meteorológicos, focos activos de incendio y capas temáticas complementarias para la evaluación del riesgo. La plataforma permitirá visualizar, filtrar, cruzar y priorizar eventos, consultar su evolución temporal y generar resúmenes operativos. Adicionalmente, el sistema evolucionará mediante la incorporación progresiva de un asistente basado en modelos de lenguaje natural que permitirá operar el visor sin conocimientos especializados en SIG.

---

## 26. Anexo: resumen ejecutivo de implantación por bloques

### Bloque A. Visualización y operación GIS
- cartografía base;
- capas;
- filtros;
- fichas;
- leyendas;
- consultas.

### Bloque B. Riesgo de inundación
- detección de avisos hidrometeorológicos;
- cruce con T10;
- cruce con población y carreteras;
- prioridad de inundación.

### Bloque C. Riesgo de incendio
- hotspots NASA;
- cruce con FWI/sequía;
- cruce con usos del suelo;
- cruce con población y carreteras;
- prioridad de incendio.

### Bloque D. Temporalidad e histórico
- almacenamiento histórico;
- línea temporal;
- comparación de períodos;
- explotación histórica.

### Bloque E. Asistente LLM
- Fase 1: preparación técnica;
- Fase 2: operación conversacional básica;
- Fase 3: análisis conversacional avanzado.

---

## 27. Conclusión

La plataforma propuesta no debe entenderse como un mero visor cartográfico, sino como una herramienta integral de apoyo a la comprensión y priorización de eventos con relevancia para la gestión de emergencias.

Su valor diferencial reside en la combinación de:

- integración de fuentes heterogéneas;
- análisis espacial orientado al riesgo;
- explotación temporal e histórica;
- explicabilidad del resultado;
- y una futura capa de interacción en lenguaje natural que democratice el acceso funcional al sistema.
