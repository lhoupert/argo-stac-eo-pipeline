"""Create the demo asset bucket: public read and wildcard CORS, so stac-browser shows thumbnails.

Idempotent, so the bootstrap Job and rung 0 can run it on every start. Demo only: never point it
at a real bucket. Run as `python -m eo_ingest.bucket` with the usual S3 environment.
"""

import json
import time
from collections.abc import Mapping

from botocore.exceptions import ClientError, EndpointConnectionError

from .config import Config, load_config
from .download import _s3_client

_CORS_RULE = {"AllowedOrigins": ["*"], "AllowedMethods": ["GET", "HEAD"], "AllowedHeaders": ["*"]}


def ensure_public_bucket(config: Config) -> None:
    s3 = _s3_client(config)
    bucket = config.s3_bucket
    try:
        s3.create_bucket(Bucket=bucket)
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            raise
    s3.put_bucket_policy(
        Bucket=bucket,
        Policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{bucket}/*"],
                    }
                ],
            }
        ),
    )
    s3.put_bucket_cors(Bucket=bucket, CORSConfiguration={"CORSRules": [_CORS_RULE]})


def main(env: Mapping[str, str] | None = None) -> int:
    config = load_config(env)
    for attempt in range(30):
        try:
            ensure_public_bucket(config)
            break
        except EndpointConnectionError:
            if attempt == 29:
                raise
            time.sleep(2)  # the object store is still starting
    print(f"bucket {config.s3_bucket}: public read + CORS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
