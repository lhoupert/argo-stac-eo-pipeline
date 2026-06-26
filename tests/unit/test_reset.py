"""T29: reset.py — clear the logbook + empty the asset bucket (the `make clean` data plane).

Clearing drops whole collections (pgSTAC cascades item deletion) and removes every object from
the bucket while keeping the bucket itself. An already-empty catalog or bucket is a clean no-op,
and a missing STAC_URL is a clear error (you can't clear a logbook that isn't configured).
"""

import boto3
import httpx
import pytest
import respx
from moto import mock_aws

from eo_ingest.config import load_config
from eo_ingest.reset import clear_catalog, empty_bucket, reset

STAC_URL = "http://stac-api"
BUCKET = "eo-assets"
_COLLECTIONS_URL = f"{STAC_URL}/collections"


def _env(stac_url: str = STAC_URL, bucket: str = BUCKET) -> dict:
    return {
        "STAC_URL": stac_url,
        "S3_BUCKET": bucket,
        "S3_ENDPOINT_URL": "",  # let moto intercept the default AWS endpoint
    }


def _client():
    return boto3.client("s3", region_name="us-east-1")


def _seed_objects(s3, *keys: str) -> None:
    s3.create_bucket(Bucket=BUCKET)
    for key in keys:
        s3.put_object(Bucket=BUCKET, Key=key, Body=b"x")


# --- catalog -------------------------------------------------------------------------------------


@respx.mock
def test_clear_catalog_deletes_every_collection() -> None:
    respx.get(_COLLECTIONS_URL).mock(
        return_value=httpx.Response(200, json={"collections": [{"id": "c1"}, {"id": "c2"}]})
    )
    d1 = respx.delete(f"{_COLLECTIONS_URL}/c1").mock(return_value=httpx.Response(200))
    d2 = respx.delete(f"{_COLLECTIONS_URL}/c2").mock(return_value=httpx.Response(200))

    assert clear_catalog(STAC_URL) == ["c1", "c2"]
    assert d1.called and d2.called


@respx.mock
def test_clear_catalog_empty_is_a_noop() -> None:
    respx.get(_COLLECTIONS_URL).mock(
        return_value=httpx.Response(200, json={"collections": []})
    )
    assert clear_catalog(STAC_URL) == []


@respx.mock
def test_clear_catalog_propagates_server_error() -> None:
    respx.get(_COLLECTIONS_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        clear_catalog(STAC_URL)


# --- bucket --------------------------------------------------------------------------------------


@mock_aws
def test_empty_bucket_removes_objects_but_keeps_the_bucket() -> None:
    s3 = _client()
    _seed_objects(s3, "a/data.png", "a/thumbnail.png", "b/data.png")

    assert empty_bucket(load_config(_env())) == 3
    # bucket still exists, now empty
    assert "Contents" not in s3.list_objects_v2(Bucket=BUCKET)


@mock_aws
def test_empty_bucket_already_empty_is_a_noop() -> None:
    _client().create_bucket(Bucket=BUCKET)
    assert empty_bucket(load_config(_env())) == 0


@mock_aws
def test_empty_bucket_missing_bucket_is_a_noop() -> None:
    # No bucket at all → clean is a no-op, not a NoSuchBucket crash.
    assert empty_bucket(load_config(_env())) == 0


@mock_aws
def test_empty_bucket_batches_large_deletes(monkeypatch: pytest.MonkeyPatch) -> None:
    import eo_ingest.reset as reset_mod

    monkeypatch.setattr(reset_mod, "_DELETE_BATCH", 2)  # force multiple delete_objects batches
    s3 = _client()
    _seed_objects(s3, "a", "b", "c", "d", "e")

    assert empty_bucket(load_config(_env())) == 5
    assert "Contents" not in s3.list_objects_v2(Bucket=BUCKET)


# --- reset (both) --------------------------------------------------------------------------------


@mock_aws
@respx.mock
def test_reset_clears_catalog_and_bucket() -> None:
    # The mocked endpoints aren't loopback, so this also exercises the RESET_ALLOW_REMOTE override.
    s3 = _client()
    _seed_objects(s3, "synthetic-aurora-veil/2026/03/01/data.png")
    respx.get(_COLLECTIONS_URL).mock(
        return_value=httpx.Response(200, json={"collections": [{"id": "synthetic-aurora-veil"}]})
    )
    respx.delete(f"{_COLLECTIONS_URL}/synthetic-aurora-veil").mock(
        return_value=httpx.Response(200)
    )

    summary = reset({**_env(), "RESET_ALLOW_REMOTE": "1"})

    assert summary == {"collections": ["synthetic-aurora-veil"], "objects": 1}
    assert "Contents" not in s3.list_objects_v2(Bucket=BUCKET)


def test_reset_refuses_a_non_local_endpoint() -> None:
    # Destructive + an ambient cloud profile could leak a real endpoint: refuse unless overridden.
    with pytest.raises(ValueError, match="non-local"):
        reset({"STAC_URL": "http://stac.example.com:8081", "S3_BUCKET": BUCKET})


def test_reset_without_stac_url_is_a_clear_error() -> None:
    with pytest.raises(ValueError, match="STAC_URL"):
        reset({"S3_BUCKET": BUCKET})  # STAC_URL unset
