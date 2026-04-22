---
id: TFG-20260421-atributos-fuego-activo-firms-modis-viirs
título: "Atributos de fuego activo FIRMS para MODIS y VIIRS"
tipo: referencia
tags:
  - tfg
  - firms
  - modis
  - viirs
  - incendios
  - atributos
contexto: "Fuente externa útil para documentar el significado de los campos de NASA FIRMS y justificar el mapeo de atributos en la ingesta, normalización y visualización de focos de incendio en el visor GIS del TFG."
fuente_existe: true
fuente_tipo: documentación
fuente_descripción: "Página oficial de NASA Earthdata con la tabla de atributos de los datos NRT de fuego activo de MODIS y VIIRS distribuidos por FIRMS."
fuente_url: "https://www.earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs"
autor_o_entidad: "NASA Earthdata"
fecha_fuente: "pendiente de confirmar"
licencia_o_copyright: "desconocido"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar la fecha específica de publicación o última actualización de esta página."
  - "Confirmar si la entidad autora debe citarse como NASA Earthdata, FIRMS o ESDIS."
  - "Confirmar licencia o condiciones de reutilización específicas de la página."
---

# Atributos de fuego activo FIRMS para MODIS y VIIRS

## Contenido
La página oficial de NASA Earthdata resume los campos que aparecen en los datos de fuego activo en tiempo casi real (`NRT`) distribuidos por FIRMS para dos familias de producto: MODIS y VIIRS 375 m. La utilidad principal de esta fuente para el TFG es que permite interpretar con precisión qué representa cada columna de los CSV o servicios web y evita tratar estos campos como si fueran coordenadas o intensidades exactas sin contexto instrumental.

Para MODIS, la tabla indica que `latitude` y `longitude` representan el centro del píxel de fuego de 1 km, no necesariamente la localización exacta del fuego dentro del píxel. También aclara el papel de `scan` y `track` como tamaño real del píxel en las direcciones de barrido, `acq_date` y `acq_time` como fecha y hora UTC de adquisición, `satellite` como identificador de Aqua o Terra, `confidence` como una estimación porcentual entre 0 y 100 con clases baja, nominal y alta, `version` como colección y modo de procesado, `bright_t31` y `brightness` como temperaturas de brillo, `FRP` como potencia radiativa del fuego en megavatios y `type` como clasificación inferida del foco, disponible solo en el producto estándar `MCD14ML`.

Para VIIRS 375 m, la tabla mantiene varios campos equivalentes, pero introduce matices importantes: el píxel nominal es de 375 m, `bright_ti4` y `bright_ti5` corresponden a temperaturas de brillo de los canales I-4 e I-5, `confidence` se expresa en niveles cualitativos (`low`, `nominal`, `high`) y la propia documentación explica que los valores bajos diurnos suelen asociarse a `sun glint`. Además, la página advierte que ciertos falsos positivos nocturnos vinculados a la anomalía magnética del Atlántico Sur han sido eliminados del NRT distribuido por FIRMS. También señala que la estimación de `FRP` en VIIRS está condicionada por la saturación frecuente del canal I4 y que la caracterización subpíxel es más viable en fuegos pequeños o de menor intensidad, usando un enfoque híbrido con datos de 375 y 750 m.

Como nota de contexto para el TFG, esta fuente es especialmente útil para definir un esquema de datos común entre sensores y para documentar en memoria o anexos qué significan realmente campos como `confidence`, `FRP`, `scan/track`, `brightness` y `daynight`. También ayuda a justificar por qué conviene mantener separados los atributos instrumentales, temporales y de clasificación inferida al integrar FIRMS con otras fuentes como EFFIS o capas de exposición.

## Datos explícitos
- La fuente aportada es una página oficial de NASA Earthdata sobre atributos de datos de fuego activo para MODIS y VIIRS.
- La página describe campos de los datos `NRT` distribuidos por FIRMS.
- MODIS usa un píxel de fuego de 1 km y VIIRS usa un píxel nominal de 375 m.
- En MODIS, `confidence` se expresa en 0-100% y en VIIRS se expresa como `low`, `nominal` o `high`.
- `FRP` representa la potencia radiativa del fuego y `daynight` distingue entre detecciones diurnas y nocturnas.
- El atributo `type` solo está disponible para `MCD14ML`.

## Datos inferidos
- La nota encaja mejor como `referencia` externa reutilizable que como idea o decisión interna.
- Esta documentación es adecuada para respaldar el mapeo de columnas FIRMS a un modelo de datos propio del TFG.
- La entidad publicadora aparente es NASA Earthdata, aunque conviene verificar si la cita formal debe atribuirse a FIRMS o al programa ESDIS.

## Datos faltantes o ambiguos
- Fecha exacta de publicación o actualización específica de la página.
- Autoría editorial exacta de la página.
- Licencia o condiciones de uso concretas aplicables a esta documentación web.
