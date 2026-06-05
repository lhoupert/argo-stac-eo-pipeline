"""Smoke test: the package is installed and importable in the project venv."""

import eo_ingest


def test_package_exposes_version() -> None:
    assert eo_ingest.__version__ == "0.1.0"
