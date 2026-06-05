"""Synthetic-world generator behind a clean, extractable seam.

Pure generation only: STAC item dicts and asset *bytes*, deterministic in `(collection, day)`.
No S3, no STAC server, no network, no clock. See SYNTHETIC_WORLD_SPEC.md.

The public API (iter_missions / render_assets / build_item) is assembled in SW5.
"""
