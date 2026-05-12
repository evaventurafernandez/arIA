---
id: TFG-20260512-decision-retirar-focos-effis-y-priorizar-nasa-firms
título: "Decisión de retirar los focos EFFIS y priorizar NASA FIRMS"
tipo: decisión
tags:
  - tfg
  - incendios
  - firms
  - effis
  - copernicus
  - alcance
contexto: "Nota de trazabilidad sobre la comparación realizada entre la capa de focos activos EFFIS/Copernicus y NASA FIRMS, y la decisión de mantener solo FIRMS como fuente operativa de focos en el visor."
fuente_existe: false
fuente_tipo: elaboración propia
fuente_descripción: "elaboración propia basada en la evolución real del prototipo MeteoVisor"
fuente_url: ""
autor_o_entidad: "pendiente de confirmar"
fecha_fuente: "2026-05-12"
licencia_o_copyright: "pendiente de confirmar"
condiciones_de_uso: "pendiente de confirmar"
grado_de_confianza: alto
pendientes_de_verificar:
  - "Confirmar autoría de la nota."
  - "Confirmar si esta decisión se citará en la memoria como decisión de alcance o como limitación técnica."
---

# Decisión de retirar los focos EFFIS y priorizar NASA FIRMS

## Contenido
Durante el desarrollo del visor se exploró la capa de focos activos de EFFIS/Copernicus como posible capa de contexto y comparación frente a los focos de NASA FIRMS. La prueba permitió contrastar ambas fuentes y comprobar que, para el prototipo, la capa EFFIS disponible no aportaba una base operativa equivalente a FIRMS.

El motivo principal es técnico y metodológico: la integración de EFFIS se apoyaba en teselas `WMTS/WMS` rasterizadas y en una vectorización local por píxeles. Ese flujo generaba un `GeoJSON` útil para comparación visual, pero no conservaba atributos originales equivalentes a los de FIRMS, como `FRP`, hora de adquisición, sensor o confianza de detección. Por tanto, podía inducir a interpretar como dato vectorial nativo lo que en realidad era una derivación visual.

La decisión final es retirar la capa operativa de focos EFFIS/Copernicus, eliminar su carga diaria, endpoints, script de vectorización y artefactos locales, y mantener `NASA FIRMS` como única fuente visible de focos activos. EFFIS/Copernicus permanece en el visor para lo que sí aporta valor diferencial: contexto meteorológico de peligro de incendio mediante `FWI` y sequía `DC`.

## Datos explícitos
- La capa de focos EFFIS/Copernicus se usó inicialmente como contexto y comparación con NASA FIRMS.
- Se quiere conservar el rastro de la comparativa realizada.
- Se retiran las llamadas, interacciones, conversiones y cargas diarias asociadas a los focos EFFIS/Copernicus.
- La fuente operativa de focos activos que permanece en el visor es NASA FIRMS.
- Las capas EFFIS de `FWI` y `DC` no forman parte de esta retirada.

## Datos inferidos
- La retirada responde a una decisión de alcance y calidad de dato, no a que EFFIS carezca de valor como fuente general.
- Para la memoria del TFG conviene presentar EFFIS como fuente evaluada para focos, descartada como capa visible, y conservada como contexto meteorológico.
- El argumento central es evitar mezclar detecciones FIRMS con puntos derivados de imagen sin atributos equivalentes.

## Datos faltantes o ambiguos
- Falta confirmar la redacción exacta que se usará en la memoria final.
- Falta decidir si se incluirá una captura o tabla breve de la comparativa inicial como evidencia adicional.
