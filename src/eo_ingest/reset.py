"""Reset the demo's data plane — clear the logbook and empty the asset bucket (T29).

Dev tooling behind ``make clean`` / ``make reset``: it removes what a demo *produced* (STAC
collections + their items, and the objects in the MinIO bucket) while leaving the cluster, the
bucket itself, and the Argo run-history archive in place — those are a ``make down`` concern.

Like :mod:`eo_ingest.seed`, this is NOT part of any rung's workflow and never touches
``ingest.py``; it just drives the same env-configured endpoints. Deleting a collection deletes
its items too (pgSTAC cascades the delete), and the next ``make demo`` / ``make seed`` recreates
collections via ``ensure_collection`` — so dropping whole collections is the cheapest clean.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import urlparse

import httpx
from botocore.exceptions import ClientError
from rich.console import Console

from .config import Config, load_config

# Reuse the one S3-client factory — the same private helper the byte-frozen ingest.py already
# imports — so dev tooling and the unit of work resolve endpoint/credentials identically.
from .download import _s3_client

_TIMEOUT = 30.0
_console = Console()

# S3 DeleteObjects accepts at most this many keys per call.
_DELETE_BATCH = 1000

# reset() is destructive (it deletes every collection and empties the bucket), so by default it
# refuses any endpoint that isn't the local demo — a guard against an ambient cloud profile
# leaking a real STAC/S3 endpoint into host-run tooling and turning `make clean` into data loss.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _is_local(url: str | None) -> bool:
    return (urlparse(url or "").hostname or "") in _LOCAL_HOSTS


def list_collections(stac_url: str) -> list[str]:
    """Return the ids of every collection currently in the catalog."""
    base = stac_url.rstrip("/")
    resp = httpx.get(f"{base}/collections", timeout=_TIMEOUT)
    resp.raise_for_status()
    return [c["id"] for c in resp.json().get("collections", [])]


def delete_collection(stac_url: str, collection_id: str) -> None:
    """Delete one collection; pgSTAC cascades the delete to its items."""
    base = stac_url.rstrip("/")
    resp = httpx.delete(f"{base}/collections/{collection_id}", timeout=_TIMEOUT)
    resp.raise_for_status()


def clear_catalog(stac_url: str) -> list[str]:
    """Delete every collection (and, by cascade, every item); return the ids removed."""
    removed = list_collections(stac_url)
    for cid in removed:
        delete_collection(stac_url, cid)
    return removed


def empty_bucket(config: Config) -> int:
    """Delete all objects in the asset bucket (keeping the bucket); return the count removed.

    A missing bucket is treated as already-empty (0 removed) — a clean no-op, not an error.
    """
    s3 = _s3_client(config)
    bucket = config.s3_bucket
    paginator = s3.get_paginator("list_objects_v2")
    batch: list[dict] = []
    removed = 0

    def flush() -> None:
        nonlocal removed, batch
        if batch:
            s3.delete_objects(Bucket=bucket, Delete={"Objects": batch})
            removed += len(batch)
            batch = []

    try:
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                batch.append({"Key": obj["Key"]})
                if len(batch) == _DELETE_BATCH:
                    flush()
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchBucket", "404", "NotFound"):
            return removed
        raise
    flush()
    return removed


def reset(env: Mapping[str, str] | None = None) -> dict:
    """Clear the logbook and empty the asset bucket; return a summary. Requires ``STAC_URL``.

    An already-empty catalog or bucket is a clean no-op. The cluster, the bucket, and the Argo
    run-history archive are left untouched. Refuses a non-loopback STAC/S3 endpoint unless
    ``RESET_ALLOW_REMOTE`` is set — this is destructive, and an ambient cloud profile must never
    turn ``make clean`` into wiping a real catalog.
    """
    env = env if env is not None else os.environ
    config = load_config(env)
    if config.stac_url is None:
        raise ValueError(
            "reset requires STAC_URL to be set (there is no logbook to clear otherwise)"
        )

    allow_remote = (env.get("RESET_ALLOW_REMOTE") or "").strip().lower() in _TRUTHY
    targets_local = _is_local(config.stac_url) and _is_local(config.s3_endpoint_url)
    if not (allow_remote or targets_local):
        raise ValueError(
            f"reset refuses a non-local endpoint (STAC_URL={config.stac_url!r}, "
            f"S3_ENDPOINT_URL={config.s3_endpoint_url!r}) — it deletes every collection and "
            "empties the bucket. Set RESET_ALLOW_REMOTE=1 to override."
        )

    collections = clear_catalog(config.stac_url)
    objects = empty_bucket(config)

    _console.print(
        f"[green]✓[/] cleared logbook: {len(collections)} collection(s) "
        f"{collections or '—'} · emptied bucket [bold]{config.s3_bucket}[/]: "
        f"{objects} object(s)"
    )
    return {"collections": collections, "objects": objects}


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="eo_ingest.reset", description="Reset the demo data plane (clear logbook + bucket)."
    )
    parser.parse_args(argv)
    reset(env if env is not None else os.environ)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
