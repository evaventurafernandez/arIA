---
name: notas-tfg
description: Usa este skill cuando el usuario quiera crear una nota para su TFG, registrar una fuente, guardar una idea o reflexión, documentar una cita, recurso o referencia, organizar notas de investigación en ficheros Markdown, verificar si faltan datos de fuente, autoría o licencia, o convertir texto libre en una nota estructurada reutilizable para el Trabajo de Fin de Grado. No lo uses para redactar capítulos completos del TFG, para generar bibliografía formal en un estilo académico concreto salvo petición expresa dentro de la nota, ni para gestión documental genérica ajena al TFG.
---

# Skill: Notas de investigación para TFG

Este skill sirve para transformar información dispersa en notas Markdown reutilizables, una por fichero, con trazabilidad mínima de fuente, autoría, licencia y grado de confianza.

## Cuándo usarlo

Actívalo cuando el usuario pida algo como:

- crear una nota para su TFG;
- registrar una fuente o referencia;
- guardar una idea, reflexión, cita o recurso;
- convertir texto libre en una nota estructurada;
- organizar notas de investigación en ficheros Markdown;
- revisar si faltan datos de fuente, autoría, fecha o licencia.

## Cuándo no usarlo

No lo uses para:

- redactar capítulos completos del TFG;
- generar bibliografía formal en APA, IEEE u otro estilo, salvo que el usuario lo pida expresamente dentro de la nota;
- gestionar documentación genérica que no pertenezca al TFG.

## Objetivo operativo

Para cada nota:

1. Analiza la información recibida.
2. Construye una nota estructurada.
3. Distingue entre datos explícitos, datos inferidos y datos faltantes.
4. Marca claramente lo inferido y pide confirmación.
5. Pregunta solo lo estrictamente faltante o ambiguo.
6. Guarda una nota por fichero Markdown.
7. Usa nombres de fichero estables a partir del título normalizado.
8. Registra fuente, licencia o copyright cuando existan.
9. No inventes ningún dato no sustentado.

## Reglas obligatorias

- No inventes referencias, URLs, autores, fechas ni licencias.
- Si un dato puede inferirse razonablemente, márcalo como `inferido` y pide confirmación.
- Si un dato no puede inferirse, pregúntalo.
- Si la nota parece ser contenido propio del usuario y no hay fuente externa, registra `elaboración propia` en `fuente_descripción` y pide confirmación.
- Si la licencia o el copyright no están claros, usa `desconocido` o `pendiente de confirmar`.
- No hagas preguntas redundantes.
- Si la información ya basta para construir la nota, construye primero el borrador y luego pide solo las confirmaciones mínimas.
- Si el usuario no pide guardar todavía, ofrece la nota estructurada lista para guardar.
- Si el usuario pide persistencia, crea el fichero directamente en el árbol de notas.

## Campos mínimos de cada nota

Toda nota debe incluir estos campos, aunque algunos queden como `pendiente de confirmar`, `desconocido` o lista vacía:

- `id`
- `título`
- `tipo`
- `contenido`
- `contexto`
- `fuente_existe`
- `fuente_tipo`
- `fuente_descripción`
- `fuente_url`
- `autor_o_entidad`
- `fecha_fuente`
- `licencia_o_copyright`
- `condiciones_de_uso`
- `grado_de_confianza`
- `pendientes_de_verificar`
- `tags`

## Tipos recomendados de nota

Usa uno de estos valores salvo que el usuario pida otro:

- `idea`
- `reflexión`
- `fuente`
- `cita`
- `recurso`
- `referencia`
- `reunión`
- `alcance`
- `tarea`
- `decisión`

## Flujo de trabajo

### 1. Analizar entrada

Extrae, como mínimo:

- tema principal;
- posible título;
- tipo de nota;
- contenido literal o resumible;
- contexto dentro del TFG;
- existencia de fuente externa;
- metadatos de autoría, fecha, URL y licencia;
- clasificación temática probable.

### 2. Clasificar los datos

Separa la información en tres grupos:

- `explícitos`: aparece de forma directa en la petición o material aportado;
- `inferidos`: se deduce con bastante probabilidad del contexto;
- `faltantes`: no aparece y no debe inventarse.

### 3. Proponer borrador de nota

Genera una nota completa con:

- valores explícitos ya fijados;
- valores inferidos marcados explícitamente como inferidos en el apartado de verificación;
- valores faltantes marcados como `pendiente de confirmar`, `desconocido`, cadena vacía o lista vacía según corresponda.

### 4. Confirmar inferencias

Antes de consolidar la nota o guardarla, confirma solo las inferencias relevantes. Ejemplos:

- título propuesto;
- tipo de nota;
- clasificación temática;
- si se trata de elaboración propia;
- autoría probable;
- fecha aproximada;
- licencia probable o ausencia de licencia clara.

### 5. Preguntar solo lo faltante o ambiguo

Haz el mínimo número de preguntas. Prioriza:

- datos necesarios para no perder trazabilidad;
- datos que cambian la clasificación o el nombre del fichero;
- datos que afectan al uso permitido del material.

Evita preguntar por campos que ya estén suficientemente resueltos.

### 6. Persistir la nota

Si el usuario quiere guardar la nota:

- guarda una nota por fichero;
- usa formato Markdown;
- coloca el fichero en un subdirectorio temático si es razonable;
- si no está clara la clasificación, usa `00-pendientes/`.

## Convenciones de persistencia

### Árbol de notas

Usa como raíz preferente una carpeta de notas del proyecto, por ejemplo:

```text
doc/notas/
```

Si el repositorio ya usa otra raíz de notas, respétala.

### Nombre de fichero

Genera el nombre a partir del título normalizado:

- minúsculas;
- sin tildes ni caracteres especiales;
- espacios convertidos en guiones;
- sin dobles guiones;
- estable en el tiempo;
- suficientemente descriptivo.

Ejemplos:

- `comparativa-firms-effis.md`
- `criterios-aviso-peligroso.md`
- `idea-consulta-llm-con-trazabilidad.md`

### Clasificación temática sugerida para este TFG

Basada en un TFG sobre visor GIS web, avisos meteorológicos, focos de incendio, capas de exposición y apoyo con LLM:

- `00-pendientes/`
- `01-alcance-y-objetivos/`
- `02-aemet-y-avisos/`
- `03-incendios-firms-effis/`
- `04-capas-gis-y-exposicion/`
- `05-corine-y-usos-del-suelo/`
- `06-poblacion-carreteras-y-espacios-protegidos/`
- `07-historico-y-base-de-datos/`
- `08-llm-y-consulta-en-lenguaje-natural/`
- `09-validacion-y-casos-de-uso/`
- `10-fuentes-y-referencias/`
- `99-ideas-sueltas/`

Reglas:

- Si la nota trata de varias áreas y una predomina, clasifícala por el tema principal.
- Si no hay tema claro, usa `00-pendientes/`.
- Si es una nota puramente bibliográfica o de recurso externo, prioriza `10-fuentes-y-referencias/`.
- Si es una idea breve todavía inmadura, prioriza `99-ideas-sueltas/`.

## Formato de salida esperado

Cuando el usuario pida una nota, responde en este orden:

1. `Clasificación de datos`
2. `Confirmaciones necesarias`
3. `Preguntas mínimas pendientes` solo si hacen falta
4. `Ruta propuesta`
5. `Nota en Markdown`

Si el usuario ya ha dado información suficiente, puedes omitir preguntas y dejar solo confirmaciones breves.

## Plantilla de nota en Markdown

Usa esta plantilla base:

```markdown
---
id: TFG-AAAAMMDD-slug
título: "Título de la nota"
tipo: idea
tags:
  - tfg
  - pendiente
contexto: "Relación de esta nota con el TFG."
fuente_existe: true
fuente_tipo: web
fuente_descripción: "Descripción breve de la fuente o 'elaboración propia'."
fuente_url: "https://..."
autor_o_entidad: "Nombre del autor, entidad o 'pendiente de confirmar'"
fecha_fuente: "AAAA-MM-DD"
licencia_o_copyright: "desconocido"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: medio
pendientes_de_verificar:
  - "Confirmar autoría"
  - "Confirmar licencia"
---

# Título de la nota

## Contenido
Texto principal de la nota.

## Datos explícitos
- Dato 1
- Dato 2

## Datos inferidos
- Dato inferido 1
- Dato inferido 2

## Datos faltantes o ambiguos
- Dato pendiente 1
- Dato pendiente 2
```

## Reglas para rellenar campos

### `id`

Genera un identificador estable con este patrón preferente:

```text
TFG-AAAAMMDD-slug
```

Si no hay fecha fiable de la fuente, usa la fecha de creación de la nota.

### `título`

Debe ser breve, informativo y utilizable como base del nombre de fichero.

### `tipo`

Elige el tipo más cercano al contenido real. Si dudas entre dos, propón uno como inferido y pide confirmación.

### `contenido`

Debe recoger la idea, cita, resumen o dato útil de forma reutilizable. No reescribas como capítulo académico.

### `contexto`

Explica por qué esta nota importa para el TFG. Relaciónala con temas como:

- visor GIS web;
- avisos AEMET;
- focos NASA FIRMS;
- contraste con EFFIS/Copernicus;
- CORINE y usos del suelo;
- población, carreteras o espacios protegidos;
- histórico y base de datos;
- interfaz LLM y trazabilidad.

### `fuente_existe`

- `true` si hay fuente externa identificable;
- `false` si parece contenido propio sin fuente externa.

### `fuente_tipo`

Valores recomendados:

- `web`
- `artículo`
- `documentación`
- `libro`
- `dataset`
- `mapa`
- `normativa`
- `reunión`
- `elaboración propia`
- `otro`

### `fuente_descripción`

Describe la fuente. Si no existe fuente externa, usa:

```text
elaboración propia
```

y pide confirmación.

### `fuente_url`

Incluye URL solo si existe y ha sido aportada o verificada. No la inventes.

### `autor_o_entidad`

Usa el nombre del autor o entidad si aparece. Si no está claro, `pendiente de confirmar`.

### `fecha_fuente`

Usa formato `AAAA-MM-DD` si se conoce con precisión. Si solo hay año o mes, no inventes el resto; usa el dato parcial dentro del contenido y deja este campo como `pendiente de confirmar` si hace falta.

### `licencia_o_copyright`

Valores frecuentes:

- `desconocido`
- `pendiente de confirmar`
- texto literal de la licencia si aparece

### `condiciones_de_uso`

Resume restricciones útiles para el TFG, por ejemplo:

- `uso académico con cita`
- `requiere atribución`
- `no redistribuir`
- `pendiente de confirmar`

No inventes condiciones.

### `grado_de_confianza`

Usa:

- `alto`
- `medio`
- `bajo`

Criterio orientativo:

- `alto`: datos principales explícitos y trazables;
- `medio`: mezcla de datos explícitos e inferidos;
- `bajo`: faltan datos clave o la procedencia es débil.

### `pendientes_de_verificar`

Lista corta y concreta. Incluye solo lo realmente pendiente.

### `tags`

Incluye `tfg` y entre 2 y 6 etiquetas útiles y estables.

## Ejemplos de notas

### Ejemplo 1: idea propia

```markdown
---
id: TFG-20260415-consulta-llm-con-trazabilidad
título: "Consulta LLM con trazabilidad de capas y filtros"
tipo: idea
tags:
  - tfg
  - llm
  - trazabilidad
  - visor-gis
contexto: "Idea para el componente de consulta en lenguaje natural del visor web GIS del TFG."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-04-15"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: medio
pendientes_de_verificar:
  - "Confirmar que es elaboración propia"
  - "Confirmar autoría"
---

# Consulta LLM con trazabilidad de capas y filtros

## Contenido
El LLM no debe responder de forma libre, sino actuar como interfaz para activar capas, aplicar filtros y devolver resúmenes explicando qué datos se han usado.

## Datos explícitos
- El TFG incluye un visor GIS web.
- Se quiere una consulta en lenguaje natural con trazabilidad.

## Datos inferidos
- La nota pertenece al área de LLM y consulta.
- El contenido es una idea propia del trabajo.

## Datos faltantes o ambiguos
- Confirmación de autoría.
- Condiciones de uso internas de la nota.
```

### Ejemplo 2: fuente externa

```markdown
---
id: TFG-20260415-comparativa-firms-y-effis
título: "Comparativa preliminar entre NASA FIRMS y EFFIS/Copernicus"
tipo: fuente
tags:
  - tfg
  - incendios
  - firms
  - effis
  - copernicus
contexto: "Nota para el análisis comparado de fuentes de focos de incendio en el visor del TFG."
fuente_existe: true
fuente_tipo: web
fuente_descripción: "Recurso web sobre focos de incendio y productos de observación"
fuente_url: "https://ejemplo.org/recurso"
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "pendiente de confirmar"
licencia_o_copyright: "desconocido"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: bajo
pendientes_de_verificar:
  - "Confirmar autor o entidad"
  - "Confirmar fecha de publicación"
  - "Confirmar licencia o copyright"
---

# Comparativa preliminar entre NASA FIRMS y EFFIS/Copernicus

## Contenido
La fuente parece útil para describir diferencias de cobertura, actualización o interpretación entre FIRMS y EFFIS/Copernicus, pero faltan metadatos para poder reutilizarla con seguridad en el TFG.

## Datos explícitos
- Existe una URL aportada por el usuario.
- La nota se relaciona con focos de incendio.

## Datos inferidos
- La fuente puede servir para la parte comparativa del TFG.
- Probablemente deba clasificarse en incendios o referencias.

## Datos faltantes o ambiguos
- Autoría.
- Fecha.
- Licencia.
```

### Ejemplo 3: criterio de alcance

```markdown
---
id: TFG-20260415-criterios-aviso-peligroso
título: "Criterios para considerar un aviso como peligroso"
tipo: decisión
tags:
  - tfg
  - aemet
  - avisos
  - criterios
  - alcance
contexto: "Tema central para destacar avisos relevantes dentro del visor GIS del TFG."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-04-15"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: medio
pendientes_de_verificar:
  - "Confirmar que esta nota refleja un criterio propio y no una fuente externa"
---

# Criterios para considerar un aviso como peligroso

## Contenido
Conviene definir reglas claras basadas en nivel, fenómeno, zona afectada o cruce con otras capas para decidir cuándo resaltar un aviso en el visor.

## Datos explícitos
- El TFG necesita reglas de aviso peligroso.

## Datos inferidos
- Esta nota pertenece a alcance y avisos AEMET.
- Es una nota de decisión o trabajo interno.

## Datos faltantes o ambiguos
- Autoría confirmada.
- Regla exacta que se adoptará.
```

## Ejemplo breve de interacción de confirmación

```text
Usuario: Guarda una nota sobre usar el LLM solo como interfaz de consulta del visor, no como sistema de decisión.

Asistente:
Datos explícitos:
- El LLM debe actuar como interfaz de consulta.
- No debe presentarse como sistema de decisión.

Datos inferidos:
- Tipo de nota: idea.
- Clasificación: 08-llm-y-consulta-en-lenguaje-natural/.
- Fuente: elaboración propia.

Necesito confirmar solo esto:
1. ¿La tratamos como elaboración propia?
2. ¿Te vale este título: "LLM como interfaz de consulta, no de decisión"?
3. ¿La guardo en `doc/notas/08-llm-y-consulta-en-lenguaje-natural/`?
```

## Criterio de calidad antes de guardar

Antes de persistir una nota, verifica:

- que el título sea útil y estable;
- que el fichero vaya a una sola ubicación;
- que no se haya inventado ningún dato;
- que los datos inferidos estén marcados y pendientes de confirmación;
- que las preguntas pendientes sean mínimas;
- que fuente, autoría y licencia estén registradas aunque sea como desconocidas o pendientes.

## Propuesta opcional de estructura de carpetas

```text
doc/notas/
├── 00-pendientes/
├── 01-alcance-y-objetivos/
├── 02-aemet-y-avisos/
├── 03-incendios-firms-effis/
├── 04-capas-gis-y-exposicion/
├── 05-corine-y-usos-del-suelo/
├── 06-poblacion-carreteras-y-espacios-protegidos/
├── 07-historico-y-base-de-datos/
├── 08-llm-y-consulta-en-lenguaje-natural/
├── 09-validacion-y-casos-de-uso/
├── 10-fuentes-y-referencias/
└── 99-ideas-sueltas/
```
