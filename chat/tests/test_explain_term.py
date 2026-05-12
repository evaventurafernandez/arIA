"""Tests de la tool explainTerm contra el glosario estatico."""

from __future__ import annotations

import pytest

from chat.tools.server.explain_term import explain_term


@pytest.mark.asyncio
async def test_explains_frp_with_meteovisor_context():
    res = await explain_term(term="FRP")
    assert res["found"] is True
    assert res["term"] == "FRP"
    assert "Fire Radiative Power" in res["long_name"]
    assert "MW" in res["unit"]
    assert "MeteoVisor" in res["context_meteovisor"] or "visor" in res["context_meteovisor"]


@pytest.mark.asyncio
async def test_normalization_is_case_insensitive_and_trims():
    res = await explain_term(term="  fwi  ")
    assert res["found"] is True
    assert res["term"] == "FWI"


@pytest.mark.asyncio
async def test_substring_match_falls_back_to_long_name():
    """'fire weather index' debe matchear FWI por long_name."""
    res = await explain_term(term="fire weather index")
    assert res["found"] is True
    assert res["term"] == "FWI"


@pytest.mark.asyncio
async def test_unknown_term_returns_available_list():
    res = await explain_term(term="NoExiste")
    assert res["found"] is False
    assert "available_terms" in res
    assert "FRP" in res["available_terms"]
