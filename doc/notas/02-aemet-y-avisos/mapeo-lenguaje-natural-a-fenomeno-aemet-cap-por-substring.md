---
id: TFG-20260512-mapeo-lenguaje-natural-a-fenomeno-aemet-cap-por-substring
título: "Mapeo de lenguaje natural a fenómeno AEMET CAP por substring case-insensitive"
tipo: decisión
tags:
  - tfg
  - llm
  - aemet
  - avisos
  - cap
  - tool-calling
contexto: "Decisión de diseño de la tool `queryAlerts` del catálogo del chat LLM del visor MeteoVisor. Define cómo se traduce el término coloquial del usuario a un filtro sobre los avisos CAP de AEMET sin mantener un diccionario explícito."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada del cierre del módulo de chat LLM en MeteoVisor"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-12"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar si la memoria del TFG citará la especificación CAP-ES de AEMET para justificar la decisión."
---

# Mapeo de lenguaje natural a fenómeno AEMET CAP por substring case-insensitive

## Contenido
Los avisos meteorológicos de AEMET en formato CAP no exponen un código corto controlado para el fenómeno; el campo `event` viene como **texto descriptivo en lenguaje natural**, con variantes del estilo *"Aviso de vientos"*, *"Temperaturas máximas"*, *"Nevadas en cotas bajas"*, *"Tormentas con granizo"*.

La tool `queryAlerts` del chat LLM acepta un parámetro `phenomenon` y aplica un **filtro por substring case-insensitive** sobre `event`. Así:

- `phenomenon='viento'` captura cualquier aviso con la palabra "viento" en el evento, sin necesidad de mantener un diccionario explícito.
- `phenomenon='temperatura'` captura "Temperaturas máximas" y "Temperaturas mínimas".
- `phenomenon='nieve'` y `phenomenon='nevada'` se complementan según el término que use el modelo.

Razón de la decisión: mantener un diccionario explícito término coloquial → código sería frágil (AEMET cambia denominaciones entre episodios) y aumentaría la superficie de mantenimiento. La búsqueda por substring sobre el texto que AEMET ya emite delega la cobertura léxica a las propias denominaciones oficiales del organismo y permite que el modelo LLM aproveche su comprensión del lenguaje para elegir un substring razonable.

Encadena de forma natural con [[redireccion-variables-no-observadas-a-avisos-aemet]]: cuando una consulta sobre una variable no observada se redirige a aviso AEMET, el substring usado para `phenomenon` se obtiene del término que el usuario utilizó.

## Datos explícitos
- AEMET CAP usa texto descriptivo en `event`, no códigos cortos controlados.
- La tool `queryAlerts` admite `phenomenon` como string libre.
- El filtrado es substring sobre `event` con normalización case-insensitive.

## Datos inferidos
- Mantener un diccionario término → código sería frágil y costoso.
- El LLM elige el substring adecuado a partir del prompt sin necesidad de fine-tuning.
- Pueden aparecer falsos positivos si AEMET reutiliza la misma palabra en eventos no relacionados; el riesgo se considera asumible para el alcance del prototipo.

## Datos faltantes o ambiguos
- Tabla del catálogo real de denominaciones `event` observadas en el histórico de avisos persistido.
- Política sobre tildes y normalización Unicode (NFD/NFC) en el substring.
