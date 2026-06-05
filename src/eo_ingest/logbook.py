"""The STAC catalog as the pipeline's logbook (AD-2).

Born in the foundation with ``register()``; it grows ``find_gaps()`` at rung 3 (T18) — the
moment the logbook stops being a passive record and starts driving self-correction.

``register`` is an idempotent upsert against the stac-fastapi transactions extension: POST to
create, and on a create conflict fall back to PUT so re-running never duplicates an item.
"""

from __future__ import annotations

import httpx

from .config import Config

_TIMEOUT = 30.0


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
