"""T3: env-driven settings — the AD-1 seam that lets one image serve every rung."""

import pytest

from eo_ingest.config import Config, ConfigError, load_config


def test_defaults_are_the_local_profile_with_registration_disabled() -> None:
    # Empty env => rung-0 works zero-config: local MinIO sink, no catalog.
    cfg = load_config({})
    assert isinstance(cfg, Config)
    assert cfg.stac_url is None
    assert cfg.registration_enabled is False
    assert cfg.source_type == "synthetic"
    assert cfg.collection == "synthetic-aurora-veil"
    assert cfg.s3_endpoint_url == "http://localhost:9000"
    assert cfg.s3_bucket == "eo-assets"
    assert cfg.aws_region == "us-east-1"
    assert cfg.fail_once is False
    assert cfg.ingest_sleep == 0.0


def test_stac_url_set_enables_registration() -> None:
    cfg = load_config({"STAC_URL": "http://stac-api"})
    assert cfg.stac_url == "http://stac-api"
    assert cfg.registration_enabled is True


def test_empty_stac_url_disables_registration() -> None:
    # An empty string is the documented "off" state, same as unset.
    cfg = load_config({"STAC_URL": ""})
    assert cfg.stac_url is None
    assert cfg.registration_enabled is False


def test_reads_provided_env_values() -> None:
    cfg = load_config(
        {
            "SOURCE_TYPE": "earthsearch",
            "COLLECTION": "sentinel-2-l2a",
            "S3_ENDPOINT_URL": "http://minio:9000",
            "S3_BUCKET": "custom-bucket",
            "AWS_ACCESS_KEY_ID": "key",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "AWS_REGION": "eu-central-1",
        }
    )
    assert cfg.source_type == "earthsearch"
    assert cfg.collection == "sentinel-2-l2a"
    assert cfg.s3_endpoint_url == "http://minio:9000"
    assert cfg.s3_bucket == "custom-bucket"
    assert cfg.aws_access_key_id == "key"
    assert cfg.aws_secret_access_key == "secret"
    assert cfg.aws_region == "eu-central-1"


def test_unknown_source_type_raises_clear_error() -> None:
    with pytest.raises(ConfigError) as exc:
        load_config({"SOURCE_TYPE": "bogus"})
    msg = str(exc.value)
    assert "SOURCE_TYPE" in msg
    assert "synthetic" in msg and "earthsearch" in msg  # lists valid options


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0", False), ("1", True), ("true", True), ("False", False), ("yes", True), ("no", False)],
)
def test_fail_once_parses_common_boolean_spellings(value: str, expected: bool) -> None:
    assert load_config({"FAIL_ONCE": value}).fail_once is expected


def test_invalid_fail_once_raises_clear_error() -> None:
    with pytest.raises(ConfigError) as exc:
        load_config({"FAIL_ONCE": "maybe"})
    assert "FAIL_ONCE" in str(exc.value)


def test_ingest_sleep_parses_as_float() -> None:
    assert load_config({"INGEST_SLEEP": "2"}).ingest_sleep == 2.0
    assert load_config({"INGEST_SLEEP": "0.5"}).ingest_sleep == 0.5


def test_invalid_ingest_sleep_raises_clear_error() -> None:
    with pytest.raises(ConfigError) as exc:
        load_config({"INGEST_SLEEP": "soon"})
    assert "INGEST_SLEEP" in str(exc.value)


def test_negative_ingest_sleep_raises_clear_error() -> None:
    with pytest.raises(ConfigError) as exc:
        load_config({"INGEST_SLEEP": "-1"})
    assert "INGEST_SLEEP" in str(exc.value)


def test_load_config_defaults_to_os_environ(monkeypatch) -> None:
    monkeypatch.setenv("COLLECTION", "synthetic-tidal-glass")
    monkeypatch.delenv("STAC_URL", raising=False)
    cfg = load_config()
    assert cfg.collection == "synthetic-tidal-glass"


def test_bbox_parsed_from_env() -> None:
    cfg = load_config({"BBOX": "5.0,53.2,5.1,53.3"})
    assert cfg.bbox == (5.0, 53.2, 5.1, 53.3)


def test_bbox_unset_is_none_and_asset_defaults_to_thumbnail() -> None:
    cfg = load_config({})
    assert cfg.bbox is None
    assert cfg.asset == "thumbnail"


def test_bbox_malformed_is_a_clear_error() -> None:
    import pytest as _pytest

    from eo_ingest.config import ConfigError
    with _pytest.raises(ConfigError, match="BBOX"):
        load_config({"BBOX": "5.0,53.2,5.1"})  # only 3 numbers
