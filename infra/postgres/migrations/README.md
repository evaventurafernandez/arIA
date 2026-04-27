# Migraciones

Este directorio queda reservado para migraciones SQL versionadas de la estructura de base de datos.

Criterio de uso propuesto:

- scripts numerados o identificados de forma estable,
- una migración por cambio estructural,
- ejecución controlada desde Docker o por un proceso de administración reproducible,
- sin depender de shell específico de plataforma,
- la ingesta operativa de `landcover` se documenta en `infra/ingest/`.
