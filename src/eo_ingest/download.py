"""Put an item's assets into the S3 sink — idempotent and checksum-guarded.

For the synthetic backend the asset *bytes* are regenerated deterministically (the item's hrefs
are the destination S3 keys, set by ``stac_source``). Each object is stored with its sha256 in
metadata; a re-run that finds a byte-identical object skips it, while a truncated or corrupt
object is re-uploaded rather than silently accepted. Earth Search asset fetching lands in T26.
"""

from __future__ import annotations

import hashlib
import os
from datetime import date
from urllib.parse import urlparse

import boto3
import httpx
from botocore.exceptions import ClientError

from .config import Config
from .synthetic import render_assets

_PNG = "image/png"
_FETCH_TIMEOUT = 120.0


def _s3_client(config: Config):
    return boto3.client(
        "s3",
        endpoint_url=config.s3_endpoint_url or None,
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
        region_name=config.aws_region,
    )


def _split_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    return parsed.netloc, parsed.path.lstrip("/")


def _is_current(s3, bucket: str, key: str, data: bytes, sha: str) -> bool:
    """True iff an object already stored at ``key`` is byte-identical (right length + checksum)."""
    try:
        head = s3.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise
    return head.get("ContentLength") == len(data) and head["Metadata"].get("sha256") == sha


def _put_if_needed(s3, uri: str, data: bytes, content_type: str = _PNG) -> str:
    """Upload ``data`` to the S3 ``uri`` unless an identical object is already there."""
    bucket, key = _split_s3_uri(uri)
    sha = hashlib.sha256(data).hexdigest()
    if _is_current(s3, bucket, key, data, sha):
        return "skipped"
    s3.put_object(
        Bucket=bucket, Key=key, Body=data, ContentType=content_type, Metadata={"sha256": sha}
    )
    return "uploaded"


def _fetch_remote(url: str) -> bytes:
    """Fetch an asset's bytes from its (real) remote href."""
    resp = httpx.get(url, follow_redirects=True, timeout=_FETCH_TIMEOUT)
    resp.raise_for_status()
    return resp.content


def _download_synthetic(config: Config, item: dict) -> dict[str, str]:
    day = date.fromisoformat(item["properties"]["datetime"][:10])
    data_bytes, thumb_bytes = render_assets(item["collection"], day)
    s3 = _s3_client(config)
    return {
        "data": _put_if_needed(s3, item["assets"]["data"]["href"], data_bytes),
        "thumbnail": _put_if_needed(s3, item["assets"]["thumbnail"]["href"], thumb_bytes),
    }


def _download_earthsearch(config: Config, item: dict) -> dict[str, str]:
    """Fetch each (trimmed) real asset from its remote href into the S3 sink, idempotently.

    The remote href is the *source*; we rewrite the item's asset href to the ``s3://`` *sink* in
    place, so the item registered in the logbook (and the byte accounting in ``ingest``) points at
    our copy, not the upstream URL. ``stac_source`` already trimmed the item to one asset.
    """
    s3 = _s3_client(config)
    day = date.fromisoformat(item["properties"]["datetime"][:10])
    actions: dict[str, str] = {}
    for name, asset in item["assets"].items():
        data = _fetch_remote(asset["href"])
        ext = os.path.splitext(urlparse(asset["href"]).path)[1]
        sink = f"s3://{config.s3_bucket}/{item['collection']}/{day:%Y/%m/%d}/{name}{ext}"
        actions[name] = _put_if_needed(
            s3, sink, data, content_type=asset.get("type") or "application/octet-stream"
        )
        asset["href"] = sink  # source -> sink, so register/_asset_bytes use our copy
    return actions


def download_item(config: Config, item: dict) -> dict[str, str]:
    """Ensure the item's asset(s) are in S3; return a per-asset ``"uploaded"``/``"skipped"`` action.

    Synthetic: regenerate ``data`` + ``thumbnail`` bytes deterministically. Earthsearch: fetch the
    one trimmed real asset from its remote href and rewrite the href to the S3 sink.
    """
    if config.source_type == "synthetic":
        return _download_synthetic(config, item)
    return _download_earthsearch(config, item)
