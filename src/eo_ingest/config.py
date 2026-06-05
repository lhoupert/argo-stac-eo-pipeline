"""Env-driven settings: the AD-1 seam that lets one image serve every rung.

Rung 0 runs zero-config (defaults target a local MinIO sink with no catalog); higher rungs
flip behaviour purely through env vars — notably ``STAC_URL``, whose presence enables
registration. ``load_config`` is a pure function of its ``env`` mapping so it is trivially
testable; malformed values raise a clear :class:`ConfigError` rather than failing deep in the
pipeline. See SPEC.md (AD-1) and ``.env.example``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

VALID_SOURCE_TYPES = ("synthetic", "earthsearch")

# Accepted spellings for boolean knobs (case-insensitive).
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class ConfigError(ValueError):
    """Raised when an environment value is present but invalid."""


@dataclass(frozen=True)
class Config:
    """Resolved settings for one ingest run."""

    stac_url: str | None  # None disables registration (rung 0 has no catalog)
    source_type: str  # one of VALID_SOURCE_TYPES
    collection: str
    s3_endpoint_url: str
    s3_bucket: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    fail_once: bool  # inject one transient failure then succeed (rung-1 retry demo)
    ingest_sleep: float  # per-item sleep (s) simulating IO cost for the fan-out demo

    @property
    def registration_enabled(self) -> bool:
        """Whether items should be registered into the STAC logbook."""
        return self.stac_url is not None


def _parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigError(f"{name} must be one of {sorted(_TRUE | _FALSE)}, got {raw!r}")


def _parse_sleep(name: str, raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number (seconds), got {raw!r}") from exc
    if value < 0:
        raise ConfigError(f"{name} must be >= 0, got {raw!r}")
    return value


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Resolve settings from ``env`` (defaults to ``os.environ``); raise ConfigError if invalid."""
    if env is None:
        env = os.environ

    source_type = env.get("SOURCE_TYPE", "synthetic")
    if source_type not in VALID_SOURCE_TYPES:
        raise ConfigError(
            f"SOURCE_TYPE must be one of {list(VALID_SOURCE_TYPES)}, got {source_type!r}"
        )

    return Config(
        stac_url=env.get("STAC_URL") or None,
        source_type=source_type,
        collection=env.get("COLLECTION", "synthetic-aurora-veil"),
        s3_endpoint_url=env.get("S3_ENDPOINT_URL", "http://localhost:9000"),
        s3_bucket=env.get("S3_BUCKET", "eo-assets"),
        aws_access_key_id=env.get("AWS_ACCESS_KEY_ID", "minioadmin"),
        aws_secret_access_key=env.get("AWS_SECRET_ACCESS_KEY", "minioadmin"),
        aws_region=env.get("AWS_REGION", "us-east-1"),
        fail_once=_parse_bool("FAIL_ONCE", env.get("FAIL_ONCE", "0")),
        ingest_sleep=_parse_sleep("INGEST_SLEEP", env.get("INGEST_SLEEP", "0")),
    )
