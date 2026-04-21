---
id: TFG-20260421-priorizacion-operativa-viirs-frente-a-modis
título: "Priorización operativa de VIIRS frente a MODIS en NASA FIRMS"
tipo: decisión
tags:
  - tfg
  - incendios
  - firms
  - viirs
  - modis
  - decision-operativa
contexto: "Decisión técnica del TFG para justificar por qué MeteoVisor España debe usar VIIRS como fuente principal de focos activos en NASA FIRMS y dejar MODIS como apoyo histórico o de validación."
fuente_existe: true
fuente_tipo: documentación
fuente_descripción: "Síntesis técnica basada en NASA FIRMS, NASA Earthdata, NOAA/NESDIS, NOAA OSPO y literatura científica sobre productos activos VIIRS y MODIS."
fuente_url: "https://www.earthdata.nasa.gov/data/tools/firms"
autor_o_entidad: "NASA FIRMS, NASA Earthdata, NOAA/NESDIS, NOAA OSPO y varios autores"
fecha_fuente: "pendiente de confirmar"
licencia_o_copyright: "desconocido"
condiciones_de_uso: "Revisar condiciones específicas de cada fuente y citar cada recurso técnico o artículo cuando se reutilice en la memoria."
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar si se quiere citar expresamente la fecha de consulta 2026-04-21 en la memoria para los recursos web."
  - "Revisar si la nota debe enlazar también con una futura nota de validación FIRMS frente a EFFIS."
  - "No usar Hawbaker et al. (2017) como comparativa directa VIIRS/MODIS hasta verificar esa referencia."
---

# Priorización operativa de VIIRS frente a MODIS en NASA FIRMS

## Contenido
Para el TFG, la fuente principal operativa de puntos calientes de NASA FIRMS debe ser **VIIRS** y no **MODIS**. La razón no es solo que VIIRS sea más reciente, sino que ofrece una resolución espacial mucho más fina, mejor respuesta sobre fuegos pequeños, mejor rendimiento nocturno y mejor ajuste para integrar focos con capas GIS y análisis de exposición.

A fecha **2026-04-21**, FIRMS distribuye productos NRT VIIRS desde **Suomi NPP, NOAA-20 y NOAA-21**, mientras que MODIS se apoya en **Terra y Aqua**. En la práctica del prototipo, esto refuerza el uso de VIIRS como base operativa porque permite reducir la probabilidad de omitir focos pequeños o tempranos y disminuye la dependencia de una sola plataforma.

Comparativa técnica clave:

| Característica | VIIRS (NOAA-21/NOAA-20/Suomi NPP) | MODIS (Terra/Aqua) |
|---|---|---|
| Resolución espacial | **375 m** (alta) | **1 km** (media) |
| Sensibilidad a focos pequeños | Muy alta | Limitada |
| Detección nocturna | Excelente para focos térmicos pequeños; requiere cautela con artefactos de plumas muy calientes | Correcta, pero con píxel más grueso |
| Frecuencia de revisita | Aproximadamente 12 h por satélite polar; el uso combinado de 3 productos NRT reduce huecos temporales | Aproximadamente 12 h por satélite polar; 2 plataformas |
| Número de satélites/plataformas en FIRMS NRT | 3 (`NOAA-21`, `NOAA-20`, `Suomi NPP`) | 2 (`Terra`, `Aqua`) |
| Latencia NRT en FIRMS global | `< 3 h` desde la observación satelital hasta la disponibilidad en FIRMS | `< 3 h` desde la observación satelital hasta la disponibilidad en FIRMS |
| Precisión de geolocalización | Alta: centro de píxel nominal de 375 m | Media: centro de píxel de 1 km, no necesariamente ubicación real del fuego |
| Nivel de falsos positivos | Bajo-medio; puede haber artefactos, especialmente en detecciones nocturnas asociadas a plumas supercalentadas | Medio; producto maduro, pero más condicionado por el tamaño de píxel y la mezcla de señales dentro del píxel |
| Madurez del producto | Alta, aunque con una serie temporal más reciente que MODIS | Muy alta; serie histórica larga y muy validada |
| Rol recomendado en MeteoVisor | Fuente principal operativa | Apoyo histórico, contraste y validación |

Matización importante: VIIRS no implica observación continua en sentido estricto. Sigue siendo una fuente polar NRT dependiente de pasos orbitales, aunque la combinación de tres plataformas mejora la cobertura temporal. También conviene distinguir entre disponibilidad del producto y envío de alertas: FIRMS indica disponibilidad NRT global inferior a 3 horas, mientras que las alertas por correo se describen en la FAQ con tiempos normalmente de 3 horas para MODIS y 4 horas para VIIRS.

Conclusión reutilizable para la memoria:

- **VIIRS** debe justificarse como fuente principal operativa en el visor.
- **MODIS** debe presentarse como complemento útil para continuidad histórica, contraste metodológico y validación.
- La superioridad práctica de VIIRS se fundamenta sobre todo en resolución, detección de focos pequeños, rendimiento nocturno y precisión espacial.

## Datos explícitos
- Se ha trabajado una comparativa técnica VIIRS frente a MODIS para NASA FIRMS.
- VIIRS usa resolución de 375 m y MODIS de 1 km en los productos activos NRT relevantes para el visor.
- La decisión buscada para el TFG es priorizar VIIRS como fuente principal operativa.
- En FIRMS están disponibles productos VIIRS de Suomi NPP, NOAA-20 y NOAA-21.
- MODIS queda orientado a apoyo histórico, contraste y validación.

## Datos inferidos
- Esta nota pertenece principalmente a `03-incendios-firms-effis/` porque afecta a la estrategia de ingestión y representación de focos activos.
- El criterio servirá tanto para justificar decisiones del backend como para redactar la memoria del TFG.
- Las valoraciones sobre falsos positivos y madurez son síntesis técnicas apoyadas en documentación oficial y literatura, no clasificaciones oficiales literales de FIRMS.

## Datos faltantes o ambiguos
- Confirmar si se quiere convertir esta decisión en requisito formal del proyecto o mantenerla como nota de justificación técnica.
- Confirmar la referencia bibliográfica exacta que se usará finalmente para justificar la comparación VIIRS/MODIS en la memoria.
- Verificar si se añadirá una nota aparte de validación empírica con casos reales del visor.
