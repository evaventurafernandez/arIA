# Catálogo del dataset `landcover_corine_2018_filtered`

## 1. Identificación

- `dataset_id`: `landcover_corine_2018_filtered`
- `dataset_type`: `capa_tematica_estatica`
- `source_system`: `copernicus_corine_2018`
- `origin_format`: `FileGDB`
- `update_frequency`: `muy baja` / `manual por nueva edición`

## 2. Descripción funcional

Este dataset representa el subconjunto CORINE 2018 usado por MeteoVisor para capas temáticas estáticas de uso del suelo. El producto lógico de la PoC agrupa solo las clases forestales y agrícolas de interés para el visor.

La salida funcional actual equivalente es `data/landcover.geojson`.

## 3. Origen y capas de entrada

- Artefacto bruto actual para la PoC de ingesta: `data-store/files/CLC2018_GDB.zip`
- Dataset vectorial contenido en el ZIP: `CLC2018_ES.gdb`
- Fichero de origen histórico en el repo: `data/CLC2018_ES.gpkg`
- Capas de entrada:
  - `CLC18_ES`
  - `CLC18_ES_Canarias`
- Filtro funcional actual: `CODE_18`

## 4. Subconjunto temático

Clases incluidas en la PoC:

- `211`
- `242`
- `311`
- `312`
- `313`
- `321`
- `322`
- `323`
- `324`

## 5. Organización `raw`

Ruta canónica propuesta para el artefacto bruto principal de la PoC:

```text
./data-store/files/CLC2018_GDB.zip
```

Ruta lógica interna consumida por GDAL:

```text
/vsizip/.../CLC2018_GDB.zip/CLC2018_ES.gdb
```

Criterio operativo:

- el ZIP bruto se conserva por copia,
- no se considera un producto transformado,
- el `raw` solo conserva el origen y metadatos mínimos de trazabilidad,
- no es necesario descomprimir el artefacto para la Fase 3.

Metadatos mínimos del artefacto:

- hash de contenido,
- tamaño,
- timestamp de incorporación,
- formato,
- capas disponibles,
- versión lógica del dataset.

## 6. Validación mínima

Antes de pasar a la siguiente fase, la documentación de este dataset debe dejar claro que:

- el fichero bruto existe en la ruta acordada,
- las capas esperadas están presentes,
- el filtro funcional se limita a `CODE_18`,
- el producto actual de referencia es equivalente a `data/landcover.geojson`.

## 7. Pendiente de cerrar

- Atribución/licencia exacta del origen si se necesita fuera del ámbito interno del repo.
- URL o identificador formal de descarga del paquete fuente si se desea registrar en el catálogo extendido.
