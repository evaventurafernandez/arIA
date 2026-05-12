"""Tests del LocalPlaceResolver y la tool searchPlace."""

from __future__ import annotations

import pytest

from chat.tools.server.place_resolver import (
    LocalPlaceResolver,
    normalize_name,
    set_place_resolver,
)
from chat.tools.server.search_place import search_place


@pytest.fixture(autouse=True)
def _reset_resolver():
    set_place_resolver(None)
    yield
    set_place_resolver(None)


def test_normalize_strips_accents_and_lowercases():
    assert normalize_name("  Cataluña ") == "cataluna"
    assert normalize_name("Cádiz") == "cadiz"


@pytest.mark.asyncio
async def test_resolves_ccaa_exact_match():
    set_place_resolver(LocalPlaceResolver(use_db_fallback=False))
    res = await search_place(name="Galicia")
    assert res["found"] is True
    assert res["kind"] == "ccaa"
    assert res["name"] == "Galicia"
    assert len(res["bbox"]) == 4


@pytest.mark.asyncio
async def test_resolves_ccaa_with_accent_variant():
    set_place_resolver(LocalPlaceResolver(use_db_fallback=False))
    res = await search_place(name="Cataluña")  # con tilde
    assert res["found"] is True
    assert res["name"] in {"Cataluna", "Cataluña"}  # canonical sin tilde


@pytest.mark.asyncio
async def test_resolves_provincia():
    set_place_resolver(LocalPlaceResolver(use_db_fallback=False))
    res = await search_place(name="Cuenca")
    assert res["found"] is True
    assert res["kind"] in {"provincia", "ccaa"}


@pytest.mark.asyncio
async def test_unknown_place_returns_not_found():
    set_place_resolver(LocalPlaceResolver(use_db_fallback=False))
    res = await search_place(name="Lugar inventado")
    assert res["found"] is False
    assert "query" in res


@pytest.mark.asyncio
async def test_place_resolver_interface_accepts_custom_implementation():
    """Strategy: cualquier objeto que implemente .resolve(name) sirve."""

    class FakeResolver:
        async def resolve(self, name):
            return {"name": "Fake", "kind": "ccaa", "bbox": [0, 0, 1, 1], "source": "fake"}

    set_place_resolver(FakeResolver())
    res = await search_place(name="cualquier-cosa")
    assert res["found"] is True
    assert res["source"] == "fake"
