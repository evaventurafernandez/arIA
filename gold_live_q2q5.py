"""Snapshot del 'gold' manual en vivo para q2 y q5, SIN pasar por el LLM.

Ejecuta directamente las mismas operaciones que invocan las tools del chat:
  - q2: activeFiresNearPopulation(distance_m=2000, population_max=5000)
        -> fetch_spain_hotspots() (FIRMS en vivo) + ST_DWithin sobre nucleos.
  - q5 (parte viva): queryAlerts(phenomenon in {lluvia,tormenta,agua}, vigente)
        -> filtra alerts_cache (avisos AEMET vigentes cargados en vivo).

Cada ejecucion anade UNA linea con timestamp a un JSONL, para documentar el
valor de referencia y la deriva del dato vivo durante el barrido e2e.

Uso (desde la raiz del demo, con su venv):
    venv\\Scripts\\python.exe gold_live_q2q5.py
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# --- Cargar .env en os.environ ANTES de importar main ---
ENV = Path(__file__).parent / ".env"
for line in ENV.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip())

import main  # noqa: E402
from chat.tools import TOOLS  # noqa: E402
from psycopg_pool import ConnectionPool  # noqa: E402

OUT = Path(r"C:\Users\evave\Documents\meteovisor-test-llms\results\chat_e2e_live_20260604")
OUT.mkdir(parents=True, exist_ok=True)
GOLD_LOG = OUT / "_gold_live.jsonl"


async def snapshot() -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    # Pool PostGIS (replica del lifespan)
    if main.db_pool is None:
        main.db_pool = ConnectionPool(conninfo=main.postgres_conninfo(),
                                      min_size=1, max_size=4, open=False)
        main.db_pool.open()
    # Cache de avisos AEMET vigentes (replica del lifespan)
    main.alerts_cache = await main.fetch_aemet_alerts()

    # --- q2: focos activos cerca de nucleos < 5000 hab a < 2 km ---
    q2 = await TOOLS["activeFiresNearPopulation"].handler(
        distance_m=2000, population_max=5000, limit=200,
    )
    q2_summary = {
        "total_matched": q2.get("total_matched"),
        "active_fire_candidates": q2.get("active_fire_candidates"),
        "returned": q2.get("returned"),
        "items_top": [
            {"nucleo": it["nucleo_nombre"], "hab": it["nucleo_habitantes"],
             "dist_m": it["distance_m"], "frp": it["frp"]}
            for it in (q2.get("items") or [])[:10]
        ],
    }

    # --- q5 (parte viva): avisos vigentes por lluvia/tormenta/agua ---
    q5 = {}
    for ph in ("lluvia", "tormenta", "agua"):
        r = await TOOLS["queryAlerts"].handler(phenomenon=ph, status="vigente", limit=200)
        q5[ph] = {
            "total_matched": r.get("total_matched"),
            "by_level": r.get("summary_by_level"),
            "by_phenomenon": r.get("summary_by_phenomenon"),
        }

    rec = {"ts": ts, "n_alerts_cache": len(main.alerts_cache), "q2": q2_summary, "q5": q5}
    with GOLD_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


if __name__ == "__main__":
    rec = asyncio.run(snapshot())
    print(json.dumps(rec, ensure_ascii=False, indent=2))
