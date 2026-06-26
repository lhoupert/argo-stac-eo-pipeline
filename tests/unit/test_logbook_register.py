"""T6: logbook.register() — idempotent upsert of a STAC item into the catalog.

stac-fastapi transactions: POST creates an item, PUT updates it. Re-registering the same id must
not create a duplicate — a create conflict (409) falls back to an update.
"""

import json
from datetime import date

import httpx
import pytest
import respx

from eo_ingest.config import load_config
from eo_ingest.logbook import register
from eo_ingest.synthetic import build_item

STAC_URL = "http://stac-api"
COLLECTION = "synthetic-aurora-veil"


def _cfg(stac_url=STAC_URL):
    return load_config({"STAC_URL": stac_url, "COLLECTION": COLLECTION})


def _item():
    return build_item(
        COLLECTION,
        date(2026, 3, 14),
        data_href="s3://eo-assets/a/data.png",
        thumbnail_href="s3://eo-assets/a/thumbnail.png",
    )


_ITEMS_URL = f"{STAC_URL}/collections/{COLLECTION}/items"
_ITEM_URL = f"{_ITEMS_URL}/MOI-AV_20260314"


@respx.mock
def test_register_creates_the_item() -> None:
    route = respx.post(_ITEMS_URL).mock(return_value=httpx.Response(201))
    assert register(_cfg(), _item()) == "created"
    assert route.called


@respx.mock
def test_registered_item_carries_data_and_thumbnail_roles() -> None:
    # The catalog needs both asset roles for stac-browser to render a preview.
    route = respx.post(_ITEMS_URL).mock(return_value=httpx.Response(201))
    register(_cfg(), _item())
    sent = json.loads(route.calls.last.request.content)
    assert sent["assets"]["data"]["roles"] == ["data"]
    assert sent["assets"]["thumbnail"]["roles"] == ["thumbnail"]


@respx.mock
def test_reregister_updates_instead_of_duplicating() -> None:
    respx.post(_ITEMS_URL).mock(return_value=httpx.Response(409))  # already exists
    put = respx.put(_ITEM_URL).mock(return_value=httpx.Response(200))
    assert register(_cfg(), _item()) == "updated"
    assert put.called


@respx.mock
def test_server_error_propagates() -> None:
    respx.post(_ITEMS_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        register(_cfg(), _item())


def test_register_without_stac_url_is_a_clear_error() -> None:
    cfg = load_config({"COLLECTION": COLLECTION})  # STAC_URL unset
    with pytest.raises(ValueError, match="STAC_URL"):
        register(cfg, _item())
