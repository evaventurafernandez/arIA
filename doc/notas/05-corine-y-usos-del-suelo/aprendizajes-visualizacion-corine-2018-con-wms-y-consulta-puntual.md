---
id: TFG-20260421-aprendizajes-visualizacion-corine-2018-wms-consulta-puntual
título: "Aprendizajes sobre visualización de Corine Land Cover 2018 con WMS y consulta puntual"
tipo: reflexión
tags:
  - tfg
  - corine-2018
  - wms
  - gdb
  - firms
  - visor-gis
  - ensayo-y-error
contexto: "Reflexión técnica del TFG sobre el proceso de prueba y error seguido para visualizar Corine Land Cover 2018 en el visor GIS, pasando de intentar tratar la capa de forma más pesada a apoyarse en un WMS como base visual y en consultas puntuales de metadatos desde el GDB."
fuente_existe: true
fuente_tipo: web
fuente_descripción: "Referencia funcional externa del visualizador SIOSE del IGN, donde se visualiza la capa Corine Land Cover 2018 y se consultan los metadatos asociados de forma interactiva."
fuente_url: "https://visualizadores.ign.es/siose/"
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "pendiente de confirmar"
licencia_o_copyright: "desconocido"
condiciones_de_uso: "referencia funcional externa; pendiente de confirmar"
grado_de_confianza: medio
pendientes_de_verificar:
  - "Confirmar autoría de la nota."
  - "Confirmar la fuente WMS concreta de Corine Land Cover 2018 que se adoptará como base."
  - "Definir qué campos exactos del GDB se mostrarán al consultar una unidad de landcover."
  - "Precisar si la reclasificación visible será solo de presentación o también afectará al modelo de datos de salida."
---

# Aprendizajes sobre visualización de Corine Land Cover 2018 con WMS y consulta puntual

## Contenido
Durante las pruebas con `landcover`, una de las líneas exploradas consistía en tratar la capa de forma más directa para filtrarla, manipularla y servirla con mayor control desde el proyecto. En la práctica, ese enfoque resultó pesado: aumentaba el coste de carga, complicaba la visualización y desplazaba demasiado esfuerzo técnico hacia el tratamiento de una capa que ya existe resuelta visualmente como servicio de mapa.

El problema no era solo de tamaño de datos, sino de enfoque. Intentar reproducir por nuestra cuenta toda la lógica de visualización de `Corine Land Cover 2018` obligaba a gestionar renderizado, filtrado y respuesta temática de una capa extensa cuando lo que realmente necesitamos para el visor no es rehacer toda la cartografía base, sino consultarla bien y cruzarla con otros eventos puntuales, especialmente con focos de `NASA FIRMS`.

La solución que emerge de ese proceso de ensayo y error es apoyarse en la capa `WMS` de `Corine Land Cover 2018` como mapa base, igual que en el visualizador de referencia de `SIOSE`, y reservar el `GDB` para las consultas puntuales de metadatos y geometría. Así, la capa base aporta la riqueza visual y temática sin cargar el navegador con toda la geometría vectorial, mientras que el dato estructurado del `GDB` permite recuperar la información de la unidad seleccionada cuando el usuario haga clic en el mapa o cuando se quiera contextualizar un punto concreto de `NASA FIRMS`.

En este marco, la reclasificación de `landcover` deja de plantearse como una necesidad de generar y filtrar una copia completa de la capa para renderizado general. Pasa a entenderse más bien como una capa de interpretación y presentación sobre la consulta puntual: qué categoría mostrar, qué descripción ofrecer, qué metadatos devolver y cómo presentar la unidad territorial encontrada.

El comportamiento objetivo del visor debe acercarse al del visualizador `SIOSE` del `IGN`, con una particularidad importante: la capa que se quiere usar como base es precisamente `Corine Land Cover 2018`, y la interacción deseada es similar a la de ese visor, es decir, una visualización cartográfica ya resuelta y una consulta posterior de metadatos de la unidad sobre la que se pulsa.

## Problemas observados
- Tratar la capa de `landcover` de forma más directa para filtrado y visualización resultaba pesado.
- El coste técnico de manipular toda la capa no compensaba para el objetivo real del visor.
- La geometría completa no necesita viajar al cliente de forma continua si la necesidad principal es consulta puntual.
- El problema no era solo de datos, sino de intentar asumir en el proyecto una responsabilidad cartográfica ya resuelta por la capa `WMS`.

## Solución de trabajo que parece más razonable
- Usar `Corine Land Cover 2018` en `WMS` como mapa base visual.
- Utilizar el `GDB` como fuente para extraer metadatos y, cuando haga falta, la geometría de la unidad consultada.
- Lanzar consultas a partir de un clic del usuario o de las coordenadas concretas de un foco `NASA FIRMS`.
- Acercar la experiencia final al patrón del visor `SIOSE`: capa base rica en visualización y consulta interactiva de atributos.

## Consecuencias prácticas
- La capa base del visor no necesita reconstruirse desde cero en el frontend.
- El esfuerzo pasa del renderizado masivo a la consulta espacial puntual.
- Los focos `NASA FIRMS` se integran de forma natural porque ya aportan coordenadas concretas.
- La geometría del polígono puede recuperarse solo cuando sea útil para inspección o explicación.
- La reclasificación final puede resolverse sobre la información devuelta al usuario, sin forzar necesariamente un pipeline pesado de filtrado previo.

## Datos explícitos
- Se quiere añadir una nota sobre la reclasificación de los datos de `landcover` y sobre cómo mostrarlos.
- La capa `WMS` a la que se refiere esta línea es `Corine Land Cover 2018`.
- Se quiere usar esa misma capa como base visual.
- La motivación del `WMS` es que resulta más rico en visualización, contenido y carga.
- Se extraerá la información de los metadatos de `landcover` desde el `GDB`.
- No se pretende seguir filtrando ese fichero para servirlo como capa principal.
- Se recogerán metadatos, incluidos los polígonos, a partir de focos de `NASA FIRMS` o de cualquier punto seleccionado en el mapa.
- El comportamiento final deseado debe parecerse al visualizador `SIOSE`.
- En ese visor de referencia se está visualizando precisamente esa misma capa y los metadatos que se quieren mostrar.

## Datos inferidos
- Esta nota encaja mejor como `reflexión` que como `decisión`, porque recoge un proceso de prueba y error y los aprendizajes derivados.
- La nota pertenece principalmente a `05-corine-y-usos-del-suelo/`, aunque afecta también al diseño del visor y al cruce con focos de incendio.
- La consulta principal de `landcover` pasará previsiblemente a ser un proceso espacial tipo punto-en-polígono o selección de unidad sobre geometría.
- La estrategia prioriza experiencia de uso y acceso contextual al dato frente a filtrado y publicación vectorial completa en cliente.
- La referencia externa del visualizador `SIOSE` se usa como objetivo funcional y como ejemplo de cómo visualizar la misma capa con consulta de metadatos.

## Datos faltantes o ambiguos
- Servicio `WMS` exacto de `Corine Land Cover 2018` que se utilizará en producción.
- Conjunto final de campos o metadatos que se devolverán al seleccionar una unidad de `landcover`.
- Regla concreta de reclasificación o agrupación temática que se mostrará en la interfaz.
- Criterio exacto para decidir cuándo devolver solo atributos y cuándo devolver también geometría completa del polígono.
