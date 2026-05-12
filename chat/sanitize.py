"""Saneamiento de entradas del usuario antes de inyectarlas en el prompt.

Defensa en profundidad contra prompt injection y jailbreaks:
- Truncar a longitud maxima razonable (los modelos pequenos descarrilan
  con contextos largos llenos de ruido del usuario).
- Neutralizar patrones obvios que un atacante usa para suplantar al rol
  system: cabeceras tipo 'system:', frases 'ignore previous instructions',
  marcadores especiales del propio modelo (<|...|>, <thinking>...).
- Sustituir el match por '[SANITIZED]' para que sea visible en el log si
  hace falta diagnosticar.

NO es un firewall completo: el LLM sigue siendo la primera linea de
defensa (entrenamiento + system prompt). Esto solo tapa los patrones mas
groseros para que no entren en la cadena de mensajes textuales.
"""

from __future__ import annotations

import re


DEFAULT_MAX_USER_LENGTH = 4000

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    # Cabeceras de rol que un atacante usa para suplantar:
    re.compile(r"(?im)^\s*(?:system|assistant|tool)\s*:\s*$"),
    re.compile(r"(?im)^\s*<\|im_start\|>\s*(?:system|assistant|tool)"),
    # Marcadores Gemma / OpenAI internos:
    re.compile(r"<\|[^|>\s]{1,40}\|>"),
    re.compile(r"</?(?:thinking|channel|im_start|im_end)[^>]*>", re.IGNORECASE),
    # Frases de jailbreak conocidas (no exhaustivo):
    re.compile(r"(?i)ignore\s+(?:all\s+|the\s+)?(?:previous|prior|above)\s+(?:instructions?|rules?|prompts?|messages?)"),
    re.compile(r"(?i)disregard\s+(?:all\s+|the\s+)?(?:above|previous|prior|system|instructions?)"),
    re.compile(r"(?i)forget\s+(?:everything|all|previous|the\s+above)"),
    re.compile(r"(?i)you\s+are\s+now\s+(?:a\s+)?(?:different|new|dan|jailbroken)"),
]


def sanitize_user_content(
    text: str | None,
    *,
    max_length: int = DEFAULT_MAX_USER_LENGTH,
) -> str:
    """Devuelve el texto saneado y truncado a `max_length` caracteres.

    Vacios y None pasan a "". El truncado preserva inicio (es donde el
    usuario suele poner la consulta real). Se aplica primero la
    sustitucion y luego el truncado para que un payload largo cargado de
    marcadores no se 'oculte' por estar mas alla del corte.
    """
    if not text:
        return ""
    cleaned = text
    for pat in _INJECTION_PATTERNS:
        cleaned = pat.sub("[SANITIZED]", cleaned)
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned
