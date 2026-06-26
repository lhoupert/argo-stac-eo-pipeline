"""T5: assets -> S3, idempotent + checksummed (the demo's synthetic path).

A truncated or corrupt object must never be silently accepted — it is re-uploaded. Re-running a
clean ingest uploads nothing new. Earth Search asset fetching is deferred to T26.
"""

import hashlib
from datetime import date

import boto3
import httpx
import pytest
import respx
from botocore.exceptions import ClientError
from moto import mock_aws

from eo_ingest.config import load_config
from eo_ingest.download import _is_current, download_item
from eo_ingest.stac_source import resolve_items
from eo_ingest.synthetic import render_assets

BUCKET = "eo-assets"
DAY = date(2026, 3, 14)
DATA_KEY = "synthetic-aurora-veil/2026/03/14/data.png"
THUMB_KEY = "synthetic-aurora-veil/2026/03/14/thumbnail.png"


def _cfg():
    return load_config(
        {
            "SOURCE_TYPE": "synthetic",
            "COLLECTION": "synthetic-aurora-veil",
            "S3_BUCKET": BUCKET,
            "S3_ENDPOINT_URL": "",  # let moto intercept the default AWS endpoint
        }
    )


def _client():
    return boto3.client("s3", region_name="us-east-1")


def _item(cfg):
    return resolve_items(cfg, DAY, date(2026, 3, 15))[0]


def _get(s3, key) -> bytes:
    return s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()


@mock_aws
def test_uploads_both_assets_with_the_generated_bytes() -> None:
    cfg = _cfg()
    s3 = _client()
    s3.create_bucket(Bucket=BUCKET)

    result = download_item(cfg, _item(cfg))

    assert result == {"data": "uploaded", "thumbnail": "uploaded"}
    data_bytes, thumb_bytes = render_assets("synthetic-aurora-veil", DAY)
    assert _get(s3, DATA_KEY) == data_bytes
    assert _get(s3, THUMB_KEY) == thumb_bytes


@mock_aws
def test_rerun_is_a_noop() -> None:
    cfg = _cfg()
    s3 = _client()
    s3.create_bucket(Bucket=BUCKET)
    item = _item(cfg)

    assert download_item(cfg, item) == {"data": "uploaded", "thumbnail": "uploaded"}
    assert download_item(cfg, item) == {"data": "skipped", "thumbnail": "skipped"}


@mock_aws
def test_corrupt_object_is_replaced_not_accepted() -> None:
    cfg = _cfg()
    s3 = _client()
    s3.create_bucket(Bucket=BUCKET)
    # A pre-existing object with wrong content and no checksum metadata.
    s3.put_object(Bucket=BUCKET, Key=DATA_KEY, Body=b"corrupt-not-a-png")

    result = download_item(cfg, _item(cfg))

    assert result["data"] == "uploaded"  # detected as wrong, re-uploaded
    data_bytes, _ = render_assets("synthetic-aurora-veil", DAY)
    assert _get(s3, DATA_KEY) == data_bytes


@mock_aws
def test_truncated_object_is_replaced_even_with_matching_checksum_metadata() -> None:
    cfg = _cfg()
    s3 = _client()
    s3.create_bucket(Bucket=BUCKET)
    data_bytes, _ = render_assets("synthetic-aurora-veil", DAY)
    full_sha = hashlib.sha256(data_bytes).hexdigest()
    # Upload was truncated mid-flight but the (full) checksum got recorded anyway.
    s3.put_object(
        Bucket=BUCKET, Key=DATA_KEY, Body=data_bytes[:64], Metadata={"sha256": full_sha}
    )

    result = download_item(cfg, _item(cfg))

    assert result["data"] == "uploaded"  # length mismatch caught
    assert _get(s3, DATA_KEY) == data_bytes


class _RaisingHead:
    """A minimal S3 stand-in whose head_object raises a chosen ClientError code."""

    def __init__(self, code: str) -> None:
        self._code = code

    def head_object(self, **_kwargs):
        raise ClientError({"Error": {"Code": self._code}}, "HeadObject")


def test_unexpected_head_error_propagates_rather_than_reporting_absent() -> None:
    # A non-404 error (e.g. AccessDenied) must NOT be read as "object missing" — that would let a
    # checked-but-unreadable object be silently overwritten. It has to surface.
    s3 = _RaisingHead("AccessDenied")
    with pytest.raises(ClientError):
        _is_current(s3, BUCKET, DATA_KEY, b"some-bytes", "deadbeef")


@mock_aws
@respx.mock
def test_earthsearch_fetches_remote_asset_into_sink_and_rewrites_href() -> None:
    # T26: a real asset is fetched from its remote href, stored in MinIO, and the item's href is
    # rewritten to the s3:// sink so the catalog (and ingest's byte accounting) point at our copy.
    remote = "https://example.com/scenes/abc/thumbnail.jpg"
    payload = b"\xff\xd8\xff" + b"jpegbytes" * 10
    respx.get(remote).mock(return_value=httpx.Response(200, content=payload))

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)
    cfg = load_config(
        {
            "SOURCE_TYPE": "earthsearch",
            "COLLECTION": "sentinel-2-l2a",
            "S3_BUCKET": BUCKET,
            "S3_ENDPOINT_URL": "",  # let moto intercept the default AWS endpoint
        }
    )
    def fresh_item() -> dict:  # ingest re-resolves each run, so the href starts remote each time
        return {
            "collection": "sentinel-2-l2a",
            "properties": {"datetime": "2026-03-14T10:00:00Z"},
            "assets": {"thumbnail": {"href": remote, "type": "image/jpeg"}},
        }

    item = fresh_item()
    actions = download_item(cfg, item)

    assert actions == {"thumbnail": "uploaded"}
    sink = item["assets"]["thumbnail"]["href"]
    assert sink == f"s3://{BUCKET}/sentinel-2-l2a/2026/03/14/thumbnail.jpg"  # href rewritten
    bucket, key = sink[len("s3://"):].split("/", 1)
    assert s3.get_object(Bucket=bucket, Key=key)["Body"].read() == payload  # bytes landed
    # Re-run (fresh item, same bytes) is idempotent at the sink: byte-identical -> skipped.
    assert download_item(cfg, fresh_item()) == {"thumbnail": "skipped"}
