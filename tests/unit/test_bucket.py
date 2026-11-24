"""The demo bucket bootstrap: created once, readable by anyone, CORS open, safe to re-run."""

import json

import boto3
from moto import mock_aws

from eo_ingest.bucket import ensure_public_bucket
from eo_ingest.config import load_config

BUCKET = "eo-assets"
ENV = {"S3_BUCKET": BUCKET, "S3_ENDPOINT_URL": ""}  # let moto intercept the default endpoint


@mock_aws
def test_bucket_is_public_read_with_cors_and_rerunnable():
    config = load_config(ENV)
    ensure_public_bucket(config)
    ensure_public_bucket(config)  # second run must not fail on the existing bucket

    s3 = boto3.client("s3", region_name="us-east-1")
    assert [b["Name"] for b in s3.list_buckets()["Buckets"]] == [BUCKET]

    (stmt,) = json.loads(s3.get_bucket_policy(Bucket=BUCKET)["Policy"])["Statement"]
    assert stmt["Effect"] == "Allow"
    assert stmt["Action"] == ["s3:GetObject"]
    assert stmt["Resource"] == [f"arn:aws:s3:::{BUCKET}/*"]

    (rule,) = s3.get_bucket_cors(Bucket=BUCKET)["CORSRules"]
    assert rule["AllowedOrigins"] == ["*"]
    assert "GET" in rule["AllowedMethods"]
