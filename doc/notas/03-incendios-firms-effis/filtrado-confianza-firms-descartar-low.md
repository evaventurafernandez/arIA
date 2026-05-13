---
id: TFG-20260512-filtrado-confianza-firms-descartar-low
título: "Filtrado de confianza en FIRMS: descartar 'low' en la ingesta"
tipo: decisión
tags:
  - tfg
  - firms
  - viirs
  - calidad-de-dato
  - ingesta
  - llm
contexto: "Decisión de calidad de dato aplicada en la ingesta del histórico FIRMS del visor MeteoVisor y reflejada en el glosario operativo que sirve la tool `explainTerm` del chat LLM."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada del cierre del módulo de chat LLM y del proceso de ingesta del histórico FIRMS"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-12"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar la cita formal de la documentación FIRMS sobre el flag de confianza VIIRS antes de incluirla en la memoria."
---

# Filtrado de confianza en FIRMS: descartar 'low' en la ingesta

## Contenido
La ingesta del histórico NASA FIRMS persistida en `core.firms_history` aplica un filtro de calidad: se **descartan las detecciones con `confidence = 'l'` (baja)**. Solo se conservan las detecciones de confianza **nominal** (`'n'`) y **alta** (`'h'`) para VIIRS.

Motivo: la confianza baja en VIIRS concentra una proporción elevada de falsos positivos —reflejos solares sobre superficies brillantes, gas flares industriales y otros artefactos térmicos no asociados a fuego de vegetación—. Mantener detecciones de confianza baja contamina el histórico, distorsiona el clustering DBSCAN (ver [[umbrales-por-defecto-tools-llm-meteovisor]]) y degrada la utilidad de la tool `firmsHotspotAnalysis`.

El filtro se documenta explícitamente en el **glosario operativo** que sirve `explainTerm` del chat LLM, en las entradas para `FRP`, `VIIRS` y `FIRMS`. Cuando un usuario pregunta por el significado de esos términos, la respuesta del asistente incluye qué se ha filtrado y por qué, garantizando trazabilidad del dato.

Relacionado con [[priorizacion-operativa-viirs-frente-a-modis]], [[justificacion-umbrales-frp-viirs-nasa-firms]], [[atributos-fuego-activo-firms-modis-viirs]] y [[proceso-creacion-historico-focos-nasa-firms-espana-mayo-agosto-2025]].

## Datos explícitos
- La ingesta del histórico FIRMS descarta `confidence='l'`.
- Solo se conservan `confidence='n'` (nominal) y `confidence='h'` (alta).
- El filtro está documentado en el glosario operativo accesible por la tool `explainTerm`.

## Datos inferidos
- El filtro mejora la calidad agregada del histórico al precio de perder cobertura marginal en eventos genuinos de baja intensidad.
- El filtro debe ser explícito en la memoria del TFG para que un revisor pueda reproducir cifras.

## Datos faltantes o ambiguos
- Cuantificar el porcentaje de detecciones descartadas como `low` sobre el total VIIRS del verano 2025 para reportarlo en la memoria.
- Referencia bibliográfica exacta del producto VIIRS 375 m que documenta la semántica del campo `confidence`.
