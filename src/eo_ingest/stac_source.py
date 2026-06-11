"""Resolve the STAC items to ingest for a date window.

Two backends, switched by ``config.source_type`` (AD-4) — a thin branch, not a plugin registry:

* ``synthetic`` — the ladder default: deterministic, offline items from the in-repo generator
  (``synthetic/``), one per day in the window. Asset hrefs are the deterministic S3 keys the
  downloader (T5) will write to, so the item is self-consistent before any I/O happens.
* ``earthsearch`` — query the real Earth Search STAC API (bounded) for genuine Sentinel-2 items.

Both return plain STAC item dicts, so the rest of the pipeline is backend-agnostic.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

from pystac_client import Client

from .config import Config
from .synthetic import build_item

# Public Earth Search v1 endpoint (the real-data backend; the local STAC_URL is a *sink*, not this).
EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1"

_DEFAULT_MAX_ITEMS = 100


def _daterange(start: date, end: date) -> Iterator[date]:
    """Days in the half-open window ``[start, end)``."""
    day = start
    while day < end:
        yield day
        day += timedelta(days=1)


def _asset_key(collection: str, day: date, name: str) -> str:
    """Deterministic S3 object key for an asset — shared contract with the downloader (T5)."""
    return f"{collection}/{day:%Y/%m/%d}/{name}"


def _resolve_synthetic(config: Config, start: date, end: date, max_items: int) -> list[dict]:
    bucket = config.s3_bucket
    items: list[dict] = []
    for day in _daterange(start, end):
        if len(items) >= max_items:
            break
        data_href = f"s3://{bucket}/{_asset_key(config.collection, day, 'data.png')}"
        thumb_href = f"s3://{bucket}/{_asset_key(config.collection, day, 'thumbnail.png')}"
        items.append(
            build_item(config.collection, day, data_href=data_href, thumbnail_href=thumb_href)
        )
    return items


def _resolve_earthsearch(
    config: Config, start: date, end: date, bbox: list[float] | None, max_items: int
) -> list[dict]:
    # The frozen ingest calls resolve_items without a bbox, so fall back to the configured one
    # (env BBOX); either way the query stays bounded.
    if bbox is None and config.bbox is not None:
        bbox = list(config.bbox)
    if bbox is None:
        raise ValueError("earthsearch source needs a bbox (pass one or set BBOX) to stay bounded")
    client = Client.open(EARTH_SEARCH_URL)
    search = client.search(
        collections=[config.collection],
        bbox=bbox,
        datetime=f"{start.isoformat()}/{end.isoformat()}",
        max_items=max_items,
    )
    items = [item.to_dict() for item in search.items()]
    # Real S2 items carry ~17 assets; the frozen ingest downloads and sums *every* asset it sees, so
    # trim each item to the single configured asset (default the small thumbnail) to keep the
    # example light and self-consistent.
    for item in items:
        assets = item.get("assets", {})
        item["assets"] = {config.asset: assets[config.asset]} if config.asset in assets else {}
    return items


def resolve_items(
    config: Config,
    start: date,
    end: date,
    *,
    bbox: list[float] | None = None,
    max_items: int = _DEFAULT_MAX_ITEMS,
) -> list[dict]:
    """Return the STAC items to ingest for the half-open window ``[start, end)`` (bounded).

    ``bbox`` is required for the ``earthsearch`` backend and ignored by ``synthetic`` (which uses
    each mission's own region). An empty window — or a query with no results — returns ``[]``.
    """
    if config.source_type == "earthsearch":
        return _resolve_earthsearch(config, start, end, bbox, max_items)
    return _resolve_synthetic(config, start, end, max_items)
