"""logbook.ensure_collection() + the bootstrap CLI that the rung-1 workflow runs first.

Mirrors register()'s idempotent upsert (POST to create, PUT on 409 conflict) but against the
collections endpoint. The CLI (``python -m eo_ingest.ensure_collection``) wires the synthetic
collection doc to the upsert so a workflow can guarantee the collection exists before ingesting.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from eo_ingest.config import load_config
from eo_ingest.ensure_collection import main
from eo_ingest.logbook import ensure_collection
from eo_ingest.synthetic import build_collection

STAC_URL = "http://stac-api"
COLLECTION = "synthetic-aurora-veil"

_COLLECTIONS_URL = f"{STAC_URL}/collections"
_COLLECTION_URL = f"{_COLLECTIONS_URL}/{COLLECTION}"


def _cfg(**over):
    env = {"STAC_URL": STAC_URL, "COLLECTION": COLLECTION, **over}
    return load_config(env)


@respx.mock
def test_ensure_creates_the_collection() -> None:
    route = respx.post(_COLLECTIONS_URL).mock(return_value=httpx.Response(201))
    assert ensure_collection(_cfg(), build_collection(COLLECTION)) == "created"
    assert route.called


@respx.mock
def test_ensure_updates_when_already_present() -> None:
    respx.post(_COLLECTIONS_URL).mock(return_value=httpx.Response(409))  # conflict
    put = respx.put(_COLLECTION_URL).mock(return_value=httpx.Response(200))
    assert ensure_collection(_cfg(), build_collection(COLLECTION)) == "updated"
    assert put.called


@respx.mock
def test_ensure_server_error_propagates() -> None:
    respx.post(_COLLECTIONS_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        ensure_collection(_cfg(), build_collection(COLLECTION))


def test_ensure_without_stac_url_is_a_clear_error() -> None:
    cfg = load_config({"COLLECTION": COLLECTION})  # STAC_URL unset
    with pytest.raises(ValueError, match="STAC_URL"):
        ensure_collection(cfg, build_collection(COLLECTION))


@respx.mock
def test_cli_bootstraps_the_configured_collection() -> None:
    route = respx.post(_COLLECTIONS_URL).mock(return_value=httpx.Response(201))
    rc = main(env={"STAC_URL": STAC_URL, "COLLECTION": COLLECTION, "SOURCE_TYPE": "synthetic"})
    assert rc == 0
    assert route.called


@respx.mock
def test_cli_skips_for_non_synthetic_source() -> None:
    # Real catalogs (earthsearch) own their collections; bootstrap is a synthetic-only convenience.
    route = respx.post(_COLLECTIONS_URL).mock(return_value=httpx.Response(201))
    rc = main(env={"STAC_URL": STAC_URL, "SOURCE_TYPE": "earthsearch"})
    assert rc == 0
    assert not route.called
