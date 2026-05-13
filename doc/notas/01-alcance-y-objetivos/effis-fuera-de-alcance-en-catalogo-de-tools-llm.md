---
id: TFG-20260512-effis-fuera-de-alcance-en-catalogo-de-tools-llm
título: "EFFIS fuera de alcance en el catálogo de tools del chat LLM"
tipo: alcance
tags:
  - tfg
  - llm
  - effis
  - copernicus
  - firms
  - alcance
  - tests
contexto: "Decisión de alcance que materializa en el chat LLM la retirada previa de EFFIS como fuente operativa de focos del visor MeteoVisor. Define cómo se refleja la restricción a la vez en prompt, esquema de tools, catálogo y tests."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia derivada del cierre del módulo de chat LLM y de la decisión previa de retirar EFFIS como fuente de focos"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-12"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría como elaboración propia del autor del TFG."
  - "Confirmar referencia exacta al commit 07a3148 en la memoria del TFG si se cita."
---

# EFFIS fuera de alcance en el catálogo de tools del chat LLM

## Contenido
EFFIS/Copernicus quedó fuera de alcance como fuente operativa de focos del visor (ver [[decision-retirar-focos-effis-y-priorizar-nasa-firms]]; commit `07a3148`). El módulo de chat LLM materializa esa restricción **a la vez en cuatro lugares** para evitar que se filtre por descuido:

1. **System prompt**: declara explícitamente que EFFIS no está disponible como fuente de focos en el chat. El modelo debe rechazar y redirigir a FIRMS si el usuario lo pide.
2. **Esquema JSON de la tool `toggleLayer`**: el enum del parámetro `name` excluye cualquier identificador `effis_*` relacionado con focos. Las capas EFFIS que sí permanecen en el visor (FWI, DC como contexto meteorológico) se nombran sin prefijo `effis_focos`.
3. **Catálogo de tools**: **no incluye** una tool `compareFirmsEffis` ni equivalente. Se descarta porque exigiría datos EFFIS de focos que no se ingieren.
4. **Tests de regresión**: tests automáticos verifican que ninguna respuesta del asistente, sobre un set de consultas que mencionan EFFIS, acaba invocando una tool con parámetros `effis_*` ni alucinando una tool inexistente.

La restricción se expresa de forma redundante por capas porque cada capa cubre un fallo distinto: el prompt cubre la generación libre, el enum cubre la validación de tool call, el catálogo cubre la elección de tool, y los tests cubren regresiones futuras al ampliar el prompt.

## Datos explícitos
- EFFIS está fuera de alcance como fuente de focos por decisión previa del proyecto (commit `07a3148`).
- El prompt declara EFFIS como no disponible.
- El enum de `toggleLayer.name` excluye `effis_*` relativos a focos.
- El catálogo no incluye `compareFirmsEffis`.
- Existen tests de regresión que verifican la no filtración.

## Datos inferidos
- La capa EFFIS de FWI/DC permanece accesible como contexto meteorológico, no como fuente de focos.
- La redundancia por capas es deliberada para resistir cambios futuros en el prompt o en el catálogo.

## Datos faltantes o ambiguos
- Lista exacta de consultas usadas como casos de regresión en los tests.
- Si la memoria del TFG citará el commit `07a3148` o solo describirá la decisión.
