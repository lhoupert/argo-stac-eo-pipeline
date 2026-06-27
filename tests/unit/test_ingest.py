"""T7: the frozen unit of work — resolve -> download -> register (gated on STAC_URL).

This is the byte-stable core (AD-2). Tests exercise it against the real synthetic source, moto S3,
and a respx-mocked STAC API: full ingest, registration gating, FAIL_ONCE retry, and re-run no-op.
"""

from datetime import date

import boto3
import httpx
import pytest
import respx
from botocore.exceptions import ClientError
from moto import mock_aws

from eo_ingest.config import load_config
from eo_ingest.ingest import (
    TransientIngestError,
    _maybe_fail_once,
    _rewrite_hrefs,
    ingest_one,
    main,
)

BUCKET = "eo-assets"
DAY = date(2026, 3, 14)
COLLECTION = "synthetic-aurora-veil"
STAC_URL = "http://stac-api"
ITEMS_URL = f"{STAC_URL}/collections/{COLLECTION}/items"


def _base_env(**over):
    env = {
        "COLLECTION": COLLECTION,
        "S3_BUCKET": BUCKET,
        "S3_ENDPOINT_URL": "",  # let moto intercept
    }
    env.update(over)
    return env


def _make_bucket():
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)


@mock_aws
@respx.mock
def test_ingest_one_resolves_downloads_and_registers(capsys) -> None:
    _make_bucket()
    post = respx.post(ITEMS_URL).mock(return_value=httpx.Response(201))
    cfg = load_config(_base_env(STAC_URL=STAC_URL))

    result = ingest_one(cfg, DAY)

    assert result["item_id"] == "MOI-AV_20260314"
    assert result["register_action"] == "created"
    assert result["bytes"] > 0
    assert post.called
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.head_object(Bucket=BUCKET, Key="synthetic-aurora-veil/2026/03/14/data.png")
    # The rich summary line names the item.
    assert "MOI-AV_20260314" in capsys.readouterr().out


@mock_aws
def test_registration_skipped_when_stac_url_unset() -> None:
    _make_bucket()
    cfg = load_config(_base_env())  # STAC_URL unset
    result = ingest_one(cfg, DAY)

    assert result["registered"] is False
    assert result["register_action"] is None
    # asset still written to S3
    boto3.client("s3", region_name="us-east-1").head_object(
        Bucket=BUCKET, Key="synthetic-aurora-veil/2026/03/14/thumbnail.png"
    )


@mock_aws
def test_fail_once_fails_then_succeeds_on_retry() -> None:
    _make_bucket()
    cfg = load_config(_base_env(FAIL_ONCE="1"))  # STAC unset to isolate the failure mechanism

    with pytest.raises(TransientIngestError):
        ingest_one(cfg, DAY)  # first attempt

    result = ingest_one(cfg, DAY)  # Argo-style retry
    assert result["ingested"] == 1


@mock_aws
def test_rerun_ingests_nothing_new() -> None:
    _make_bucket()
    cfg = load_config(_base_env())

    ingest_one(cfg, DAY)
    result = ingest_one(cfg, DAY)
    assert result["actions"] == {"data": "skipped", "thumbnail": "skipped"}


def test_fail_once_propagates_unexpected_s3_error() -> None:
    # The FAIL_ONCE marker probe distinguishes "first attempt" from "retry" by a 404 on the marker.
    # Any *other* head_object error (e.g. AccessDenied) must propagate, not be mistaken for the
    # first attempt — otherwise a real S3 outage would masquerade as the injected transient failure.
    class _RaisingHead:
        def head_object(self, **_kwargs):
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "HeadObject")

    cfg = load_config(_base_env(FAIL_ONCE="1"))
    with pytest.raises(ClientError):
        _maybe_fail_once(cfg, _RaisingHead(), BUCKET, "MOI-AV_20260314")


@mock_aws
@respx.mock
def test_ingest_one_with_asset_base_url_posts_http_href() -> None:
    import json

    _make_bucket()
    route = respx.post(ITEMS_URL).mock(return_value=httpx.Response(201))
    cfg = load_config(_base_env(STAC_URL=STAC_URL, ASSET_BASE_URL="http://localhost:9100/eo-assets"))
    ingest_one(cfg, DAY)
    posted = json.loads(route.calls.last.request.content)
    for name, asset in posted["assets"].items():
        assert asset["href"].startswith("http://localhost:9100/eo-assets/"), (
            f"asset {name!r}: expected HTTP href, got {asset['href']!r}"
        )


def test_rewrite_hrefs_no_op_when_base_url_unset() -> None:
    cfg = load_config(_base_env())
    href = "s3://eo-assets/col/2026/03/14/thumbnail.png"
    item = {"assets": {"thumbnail": {"href": href}}}
    result = _rewrite_hrefs(cfg, item)
    assert result["assets"]["thumbnail"]["href"] == href


def test_rewrite_hrefs_passes_through_non_matching_href() -> None:
    cfg = load_config(_base_env(ASSET_BASE_URL="http://localhost:9100/eo-assets"))
    href = "https://external.example.com/asset.tif"
    item = {"assets": {"external": {"href": href}}}
    result = _rewrite_hrefs(cfg, item)
    assert result["assets"]["external"]["href"] == href


@mock_aws
def test_main_runs_standalone_without_stac_url(monkeypatch) -> None:
    _make_bucket()
    monkeypatch.setenv("COLLECTION", COLLECTION)
    monkeypatch.setenv("S3_BUCKET", BUCKET)
    monkeypatch.setenv("S3_ENDPOINT_URL", "")
    monkeypatch.delenv("STAC_URL", raising=False)

    assert main(["--day", "2026-03-14"]) == 0
