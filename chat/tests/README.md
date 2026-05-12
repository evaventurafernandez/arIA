# Suite de tests del chat LLM

Toda la suite es `pytest` puro. No requiere conexión real con el LLM
(las interacciones con el endpoint OpenAI-compatible se mockean con
`respx`), ni con un PostGIS real (las queries SQL se mockean a través
de un pool falso). La suite se ejecuta en pocos segundos.

## Cómo correrla

Desde el worktree, con el venv del proyecto principal:

```powershell
cd C:\Users\evave\Documents\meteovisor-demo\.claude\worktrees\chat-llm
C:\Users\evave\Documents\meteovisor-demo\venv\Scripts\python.exe -m pytest -v
```

Esperado: **172 passed** (Fase 6).

Para correr solo una fase concreta:

```powershell
# Solo tests del orquestador
python -m pytest chat/tests/test_orchestrator_loop.py chat/tests/test_orchestrator_client_actions.py

# Solo tools server-side
python -m pytest chat/tests/test_query_*.py chat/tests/test_landcover_at_point.py chat/tests/test_fires_near_population.py chat/tests/test_firms_hotspot_analysis.py

# Solo endurecimiento Fase 6
python -m pytest chat/tests/test_rate_limit.py chat/tests/test_prompt_injection.py chat/tests/test_input_sanitization.py chat/tests/test_health_endpoint.py chat/tests/test_tool_catalog_safety.py
```

## Estructura

| Archivo | Cubre | Fase |
|---|---|---|
| `conftest.py` | Fixtures: `api_client` (ASGI in-memory), `respx_llm`, `llm_config` (autouse) | F0 |
| `test_llm_client.py` | Wrapper httpx → /v1/chat/completions, auth opcional, errores HTTP/red | F0 |
| `test_router_basic.py` | Contrato HTTP del endpoint /api/chat (200/400/502/503, preserva session_id) | F0/F1 |
| `test_tool_registry.py` | Decoradores `@server_tool` / `@client_tool`, lookup, rechazo de duplicados | F1/F2 |
| `test_hermes_fallback.py` | Parser `<tool_call>...</tool_call>` y parser de los 4 bloques de respuesta | F1 |
| `test_orchestrator_loop.py` | Loop think→tool→observe→respond, max iteraciones, errores controlados | F1 |
| `test_orchestrator_client_actions.py` | Client tools no se ejecutan, se acumulan en `client_actions[]`, mezcla con server tools | F2 |
| `test_tool_validation.py` | JSON Schema rechaza args inválidos, enums, additionalProperties | F1/F2 |
| `test_client_tool_schemas.py` | Schemas concretos: flyTo / toggleLayer / setFilter / getFeatureDetail | F2 |
| `test_query_alerts.py` | Filtros por fenómeno, nivel, estado, ventana temporal sobre `alerts_cache` | F1 |
| `test_query_fires.py` | Filtros sobre `fetch_spain_hotspots` mockeado: sensor, bbox, FRP, confianza | F1 |
| `test_query_burnt_area.py` | Agregación total/peak/items sobre `query_burnt_area_stats_rows` mockeado | F1 |
| `test_landcover_at_point.py` | Bbox lat/lon (WMS 1.3.0+EPSG:4326), claves correctas del normalizador IGN | F3 |
| `test_fires_near_population.py` | SQL con `hotspot_id` (PK real), filtro grueso geom + fino geography | F3 |
| `test_firms_hotspot_analysis.py` | SQL con `hotspot_id`, fallback si PostGIS no expone `ST_ClusterDBSCAN` | F3 |
| `test_search_place_local.py` | `LocalPlaceResolver` (CCAA/provincias estáticas, fallback nucleos PostGIS) y la interfaz Strategy | F3 |
| `test_summarize_situation.py` | Composición concurrente alerts+fires(+burnt_area), errores aislados por componente | F3 |
| `test_explain_term.py` | Glosario estático, normalización case/acentos, match por long_name | F3 |
| `test_e2e_alerts_query.py` | E2E con LLM mockeado: queryAlerts → 4 bloques | F1 |
| `test_e2e_client_action.py` | E2E: la respuesta incluye `client_actions[]` con flyTo | F2 |
| `test_effis_rejection.py` | `compareFirmsEffis` NO está en el registro; `toggleLayer.name` excluye EFFIS | F3 |
| `test_edge_cases.py` | Casos de borde Sección 6 del documento (capas no disponibles, predicción, etc.) | F3 |
| `test_streaming_endpoint.py` | `/api/chat/stream`: tool_call_start/done, client_action, final_block, done | F4 |
| `test_streaming_error.py` | Errores LLM 5xx y de red emiten evento `error` controlado | F4 |
| `test_log_structure.py` | Estructura JSON del log, ISO 8601, redacción de sk-/Bearer | F5 |
| `test_log_integration.py` | `/api/chat` y `/api/chat/stream` emiten una línea por interacción | F5 |
| `test_input_sanitization.py` | `sanitize_user_content`: trunca, neutraliza patrones de jailbreak | F6 |
| `test_prompt_injection.py` | E2E: el contenido del usuario llega sanitizado al LLM (verifica wire payload) | F6 |
| `test_rate_limit.py` | Rate limit por IP devuelve 429 al superar el umbral | F6 |
| `test_health_endpoint.py` | `/api/chat/health` reporta ok/configurado/latencia/error | F6 |
| `test_tool_catalog_safety.py` | Ninguna tool expone API keys / paths / patrones de secretos | F6 |

## Decisiones de diseño relevantes para los tests

- **No usamos cassettes grabadas**: la suite no contacta con vLLM/Gemma real,
  todas las respuestas del LLM se construyen a mano en el test. Eso hace los
  tests rápidos, deterministas y sin necesidad de red. Si en el futuro
  queremos validar contra el modelo real, una opción es añadir respx
  cassettes (`with respx.mock(cassette_path=...)`).

- **Llamada al LLM en streaming**: en producción, `/api/chat/stream` usa
  `chat_completion` (no streaming) internamente — vLLM con Gemma tiene un
  bug conocido al emitir token-a-token los `tool_call.arguments` con números
  negativos (`[--9.03` con doble guion). El usuario percibe streaming porque
  los eventos SSE salen a medida que el orquestador avanza por las
  iteraciones. Los tests reflejan esto: mockean el endpoint no-streaming.

- **PostGIS**: los tests que tocan SQL usan `FakePool/FakeCursor` que
  simulan la respuesta sin conectar a la BD. Lo que sí verificamos es que
  el SQL referencia las columnas correctas (p. ej. `fh.hotspot_id`, no
  `fh.id`) inspeccionando el módulo. Estos tests se llaman
  `test_sql_uses_hotspot_id_not_id` en `test_fires_near_population.py` y
  `test_firms_hotspot_analysis.py`.

- **Rate limit**: la fixture `tight_rate_limit` baja temporalmente el límite
  a `2/minute` y resetea el storage interno de slowapi con
  `limiter.reset()` entre tests. Es necesario porque slowapi mantiene un
  contador in-memory entre llamadas.

## Cuándo añadir tests al cerrar nuevas tools

Cada vez que se añada una tool nueva (server o cliente):

1. **Schema test**: validar args correctos y rechazar args incorrectos. Para
   server tools, añadir uno en `test_tool_validation.py` o crear archivo
   propio. Para client tools, ampliar `test_client_tool_schemas.py`.
2. **Handler test**: si es server-side, mockear el pool o el helper de
   `main.py` que la tool reutiliza, y verificar la forma del resultado.
3. **Safety check**: el test `test_no_forbidden_patterns_in_any_tool_description_or_schema`
   se ejecutará automáticamente sobre la nueva tool — asegurarse de que
   ni description ni parameters mencionan secretos.
