"""Tool explainTerm: definicion + contexto operativo de un termino del glosario.

No accede a datos; consulta un fichero estatico `chat/data/glossary.json`.
Sirve para preguntas tipo "que es FRP" o "que significa FWI".
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from chat.tools import server_tool


GLOSSARY_PATH = Path(__file__).resolve().parents[2] / "data" / "glossary.json"


@lru_cache(maxsize=1)
def _load_glossary() -> dict[str, dict[str, Any]]:
    with GLOSSARY_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _normalize(term: str) -> str:
    return (term or "").strip().upper().replace(" ", "")


SCHEMA = {
    "type": "object",
    "properties": {
        "term": {
            "type": "string",
            "description": (
                "Termino a definir. Soporta abreviaturas (FRP, FWI, DC, T10, CAP, "
                "VIIRS, FIRMS, AEMET, CORINE) y 'Burnt Area v4'."
            ),
        },
    },
    "required": ["term"],
    "additionalProperties": False,
}


@server_tool(
    name="explainTerm",
    description=(
        "Devuelve la definicion y el contexto operativo de un termino del "
        "glosario del visor (FRP, FWI, DC, T10, CAP, VIIRS, FIRMS, Burnt Area "
        "v4, CORINE, AEMET). Util para preguntas '¿que es X?' o '¿que significa Y?'."
    ),
    parameters=SCHEMA,
)
async def explain_term(*, term: str) -> dict[str, Any]:
    glossary = _load_glossary()
    needle = _normalize(term)

    # Match directo por clave (FRP, FWI...) o por alias normalizado.
    for key, entry in glossary.items():
        if _normalize(key) == needle:
            return {"found": True, "term": key, **entry}

    # Match por subcadena en long_name o name (mas tolerante).
    for key, entry in glossary.items():
        candidates = [entry.get("name", ""), entry.get("long_name", ""), key]
        for cand in candidates:
            if cand and needle in _normalize(cand):
                return {"found": True, "term": key, **entry}

    return {
        "found": False,
        "term": term,
        "available_terms": list(glossary.keys()),
        "message": f"El termino '{term}' no esta en el glosario del visor.",
    }
