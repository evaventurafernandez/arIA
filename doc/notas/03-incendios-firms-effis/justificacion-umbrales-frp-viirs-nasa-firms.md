---
id: TFG-20260428-justificacion-umbrales-frp-viirs-nasa-firms
título: "Justificación de umbrales FRP en focos VIIRS de NASA FIRMS"
tipo: decisión
tags:
  - tfg
  - firms
  - viirs
  - frp
  - incendios
contexto: "Criterio metodológico para la simbología de focos NASA FIRMS en el visor GIS del TFG."
fuente_existe: true
fuente_tipo: documentación y artículos científicos
fuente_descripción: "Documentación NASA FIRMS/Earthdata, NASA ARSET/SVS, Copernicus CAMS/GFAS, NOAA/NESDIS HMS y literatura científica sobre FRP y clasificación empírica de intensidad."
fuente_url: "https://www.earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs"
autor_o_entidad: "NASA Earthdata/FIRMS; NASA Applied Sciences; Copernicus CAMS; NOAA/NESDIS; Wooster et al.; Schroeder et al.; Bezerra et al."
fecha_fuente: "2026-04-28"
licencia_o_copyright: "desconocido"
condiciones_de_uso: "uso académico con cita; verificar condiciones específicas de cada fuente antes de reproducción literal"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar el estilo bibliográfico definitivo del TFG."
  - "Revisar si el tutor prefiere denominar las clases como intensidad baja/media/alta/muy alta o como categorías visuales FRP."
---

# Justificación de umbrales FRP en focos VIIRS de NASA FIRMS

## Contenido

El parámetro Fire Radiative Power (FRP) incluido en los focos activos de NASA FIRMS se ha utilizado en este trabajo como variable principal para simbolizar la intensidad radiativa de las detecciones VIIRS. En la documentación oficial de NASA Earthdata/FIRMS, el campo `FRP` se define como la potencia radiativa integrada del píxel de fuego y se expresa en megavatios (MW). Físicamente, el FRP representa la tasa instantánea a la que el área detectada emite energía térmica radiativa. Esta magnitud es especialmente útil en teledetección de incendios porque la radiancia térmica observada desde satélite permite caracterizar fuegos subpíxel que ocupan solo una parte del píxel nominal de detección.

La base científica del uso de FRP como indicador de intensidad procede de trabajos como Wooster et al. (2005), que relacionan la energía radiativa del fuego con el consumo de biomasa y muestran una relación significativa entre FRP y tasa de combustión. En la misma línea, sistemas operativos como el Global Fire Assimilation System (GFAS) de Copernicus Atmosphere Monitoring Service usan observaciones satelitales de FRP para estimar intensidad relativa y emisiones procedentes de incendios de vegetación y biomasa. NOAA/NESDIS también describe el FRP como un atributo operativo de los píxeles de fuego relacionado con la tasa de consumo de biomasa y útil para identificar los segmentos más activos o intensos dentro de un perímetro de incendio, aunque advierte que los valores absolutos dependen del combustible, la meteorología y las condiciones de observación.

Por tanto, en este visor el FRP se interpreta como un indicador de intensidad radiativa del foco activo, no como una medida directa de peligrosidad. La peligrosidad de un incendio depende de factores que no quedan resumidos en un único valor FRP, como continuidad y carga de combustible, humedad, viento, pendiente, accesibilidad, exposición de población e infraestructuras, comportamiento esperado del frente, capacidad de extinción y evolución temporal. Un foco con FRP alto indica mayor emisión radiativa en el instante de observación satelital, pero no equivale necesariamente a mayor riesgo operativo o daño potencial. De forma inversa, focos con FRP moderado pueden ser peligrosos si se sitúan en condiciones meteorológicas extremas, cerca de población o en combustibles muy continuos.

La documentación oficial consultada no establece umbrales universales de peligrosidad basados en FRP para VIIRS. NASA FIRMS documenta el significado y unidades del atributo, así como las clases de confianza de detección, pero no publica una escala normativa de gravedad. Copernicus CAMS/GFAS y NOAA utilizan FRP en modelización, seguimiento e interpretación operativa, pero lo hacen como magnitud física o indicador relativo, no como escala universal de riesgo. En consecuencia, los rangos adoptados en el prototipo deben entenderse como una clasificación orientativa basada en literatura científica, documentación institucional y usos habituales de análisis visual de incendios, no como umbrales oficiales de NASA, Copernicus, NOAA ni de protección civil.

La clasificación aplicada para los focos VIIRS de NASA FIRMS es: intensidad baja para valores de FRP inferiores a 10 MW; intensidad media para `10 <= FRP < 50 MW`; intensidad alta para `50 <= FRP <= 200 MW`; e intensidad muy alta para valores superiores a 200 MW. Esta división separa detecciones débiles o de pequeña extensión radiativa, focos intermedios, píxeles con emisión radiativa elevada y focos excepcionalmente intensos dentro del contexto de una visualización cartográfica nacional. Los cortes de 10, 50 y 200 MW son coherentes con el uso del FRP como variable continua de comparación relativa: NASA SVS emplea FRP de VIIRS para representar visualmente intensidades globales; NOAA indica que valores más altos pueden señalar las zonas más intensas de un conjunto de píxeles; y Bezerra et al. (2026) usan una partición empírica equivalente para distinguir clases baja, moderada, alta y extrema en detecciones VIIRS, insistiendo en que no representa regímenes físicos universales.

Debe señalarse, además, que VIIRS 375 m ofrece mayor sensibilidad espacial que productos MODIS de resolución más gruesa y permite detectar focos de menor tamaño o menor temperatura, pero la recuperación de FRP no está exenta de incertidumbre. NASA Earthdata indica que la saturación frecuente del canal VIIRS I4 en el infrarrojo medio obliga a aplicar pruebas adicionales y que las recuperaciones sistemáticas de FRP combinan información de 375 m y 750 m. También pueden afectar al valor observado la posición del foco dentro del píxel, el ángulo de visión, nubes o humo espeso, la cubierta forestal, la topografía, la fase de combustión, el momento de paso del satélite y la posible presencia de fuentes térmicas no forestales. Por ello, en el TFG los rangos FRP se usan exclusivamente para simbología e interpretación exploratoria, y cualquier conclusión sobre peligrosidad debe apoyarse en capas adicionales de peligro meteorológico, combustible, exposición y contexto territorial.

## Referencias integrables en bibliografía

NASA Earthdata/FIRMS. Active Fire Data Attributes for MODIS and VIIRS. https://www.earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs

NASA Earthdata. VIIRS I-Band 375 m Active Fire Data. https://www.earthdata.nasa.gov/data/instruments/viirs/viirs-i-band-375-m-active-fire-data

NASA Scientific Visualization Studio. Active Fires As Observed by VIIRS, 2024-Present. https://svs.gsfc.nasa.gov/5113/

NASA Applied Remote Sensing Training Program (ARSET). Satellite Observations and Tools for Fire Risk, Detection, and Analysis. https://appliedsciences.nasa.gov/get-involved/training/english/arset-satellite-observations-and-tools-fire-risk-detection-and

Copernicus Atmosphere Monitoring Service. CAMS global biomass burning emissions based on fire radiative power (GFAS). https://www.copernicus.eu/en/access-data/copernicus-services-catalogue/cams-global-biomass-burning-emissions-based-fire

NOAA/NESDIS Office of Satellite and Product Operations. Hazard Mapping System Fire and Smoke Product. https://www.ospo.noaa.gov/products/land/hms.html

Wooster, M. J., Roberts, G., Perry, G. L. W. y Kaufman, Y. J. (2005). Retrieval of biomass combustion rates and totals from fire radiative power observations: FRP derivation and calibration relationships between biomass consumption and fire radiative energy release. Journal of Geophysical Research: Atmospheres, 110(D24), D24311. https://doi.org/10.1029/2005JD006318

Schroeder, W., Oliva, P., Giglio, L. y Csiszar, I. A. (2014). The New VIIRS 375 m active fire detection data product: Algorithm description and initial assessment. Remote Sensing of Environment, 143, 85-96. https://doi.org/10.1016/j.rse.2013.12.008

Bezerra, K. F. da S. et al. (2026). Wildfires in the Southern Amazon: Insights into Pyro-Convective Cloud Development from Two Case Studies in August 2021. Atmosphere, 17(2), 173. https://doi.org/10.3390/atmos17020173

## Datos explícitos

- Se cambia la simbología del campo `FRP` de NASA FIRMS en el visor.
- La clasificación adoptada es: bajo `< 10 MW`, medio `10-50 MW`, alto `50-200 MW` y muy alto `> 200 MW`.
- La clasificación es orientativa y no representa umbrales oficiales de peligrosidad.

## Datos inferidos

- Esta nota se vincula al apartado metodológico del TFG y a la justificación de la simbología del visor.
- La categoría principal es una decisión metodológica de visualización, no una fuente bibliográfica aislada.

## Datos faltantes o ambiguos

- Estilo bibliográfico definitivo exigido por el TFG.
- Denominación final preferida para la leyenda: "intensidad" o "intensidad radiativa".
