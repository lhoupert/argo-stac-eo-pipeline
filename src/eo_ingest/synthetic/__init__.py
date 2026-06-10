"""Synthetic-world generator behind a clean, extractable seam.

Pure generation only: STAC item dicts and asset *bytes*, deterministic in `(collection, day)`.
No S3, no STAC server, no network, no clock. See SYNTHETIC_WORLD_SPEC.md.

`iter_missions`, `render_assets` and `build_item` are the *only* import surface the rest of
`eo_ingest` should use.
"""

from .generate import build_collection, build_item, render_assets
from .world import iter_missions

__all__ = ["iter_missions", "render_assets", "build_item", "build_collection"]
