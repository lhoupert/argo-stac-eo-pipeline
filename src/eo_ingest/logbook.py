"""The STAC catalog as the pipeline's logbook (AD-2).

Born in the foundation with ``register()``; it grows ``find_gaps()`` at rung 3 (T18) — the
moment the logbook stops being a passive record and starts driving self-correction.

``register`` is an idempotent upsert against the stac-fastapi transactions extension: POST to
create, and on a create conflict fall back to PUT so re-running never duplicates an item.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx

from .config import Config

_TIMEOUT = 30.0
_logger = logging.getLogger(__name__)


def ensure_collection(config: Config, collection: dict) -> str:
    """Idempotently upsert a STAC ``collection`` doc; return ``"created"`` or ``"updated"``.

    Rung 1 must guarantee the collection exists before :func:`register` POSTs items under it.
    Same upsert shape as :func:`register`, against the collections endpoint: POST to create, and
    on a create conflict fall back to PUT so re-running never errors.
    """
    if config.stac_url is None:
        raise ValueError("ensure_collection requires STAC_URL to be set")

    base = config.stac_url.rstrip("/")
    collections_url = f"{base}/collections"

    created = httpx.post(collections_url, json=collection, timeout=_TIMEOUT)
    if created.status_code != httpx.codes.CONFLICT:
        created.raise_for_status()
        return "created"

    updated = httpx.put(f"{collections_url}/{collection['id']}", json=collection, timeout=_TIMEOUT)
    updated.raise_for_status()
    return "updated"


def register(config: Config, item: dict) -> str:
    """Upsert ``item`` into the catalog; return ``"created"`` or ``"updated"``.

    Idempotent: a second registration of the same id updates in place rather than duplicating.
    Requires ``STAC_URL`` to be set (the caller, ``ingest``, gates this on registration).
    """
    if config.stac_url is None:
        raise ValueError("register requires STAC_URL to be set")

    base = config.stac_url.rstrip("/")
    collection = item["collection"]
    items_url = f"{base}/collections/{collection}/items"

    created = httpx.post(items_url, json=item, timeout=_TIMEOUT)
    if created.status_code != httpx.codes.CONFLICT:
        created.raise_for_status()
        return "created"

    # Already present — update in place so the upsert stays idempotent.
    updated = httpx.put(f"{items_url}/{item['id']}", json=item, timeout=_TIMEOUT)
    updated.raise_for_status()
    return "updated"


def _item_day(feature: dict) -> date | None:
    """The observation day of an item, or None if it carries no usable timestamp.

    Prefer the top-level ``datetime``; a STAC item is allowed to set it null and instead carry a
    ``start_datetime``/``end_datetime`` range, so fall back to ``start_datetime``. An item with
    neither is undatable — the caller skips it rather than crash.
    """
    props = feature.get("properties") or {}
    stamp = props.get("datetime") or props.get("start_datetime")
    if not stamp:
        return None
    return date.fromisoformat(stamp[:10])


def find_gaps(
    config: Config,
    collection: str,
    start: date,
    end: date,
    *,
    max_items: int = 1000,
) -> list[date]:
    """Days in the inclusive ``[start, end]`` window that have NO item in ``collection``.

    The logbook turning active (AD-2): rung 3 fans out ``ingest`` over exactly these days. Queries
    the catalog once, bounded by ``max_items`` (a deliberate ceiling — set it ≥ the window size).
    Robust to real-world catalog data: items with a null ``datetime`` fall back to
    ``start_datetime``; items with neither are skipped with a warning; duplicate ids / same-day
    items collapse (presence is a set), so the result is idempotent.
    """
    if config.stac_url is None:
        raise ValueError("find_gaps requires STAC_URL to be set")

    base = config.stac_url.rstrip("/")
    params = {
        "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
        "limit": max_items,
    }
    resp = httpx.get(f"{base}/collections/{collection}/items", params=params, timeout=_TIMEOUT)
    resp.raise_for_status()

    present: set[date] = set()
    for feature in resp.json().get("features", []):
        day = _item_day(feature)
        if day is None:
            _logger.warning(
                "skipping undatable item %r (no datetime/start_datetime)", feature.get("id")
            )
            continue
        present.add(day)

    window = ((end - start).days + 1)
    expected = (start + timedelta(days=i) for i in range(window))
    return sorted(day for day in expected if day not in present)
