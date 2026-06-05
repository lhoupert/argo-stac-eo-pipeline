"""Deterministic, pure generation for the synthetic world.

Everything here is a pure function of ``(collection, day)`` — no filesystem, network, or clock.
Determinism is load-bearing: recorded screencasts and the seeded catalog must reproduce
byte-for-byte. See SYNTHETIC_WORLD_SPEC.md.
"""

from __future__ import annotations

import hashlib
from datetime import date

from .world import Mission

# Polygons are inset from their grid cell so adjacent footprints read as discrete tiles.
_INSET_FRACTION = 0.08


def seed(collection: str, day: date) -> int:
    """Stable 64-bit seed for a ``(collection, day)`` pair (no wall-clock, no global RNG)."""
    digest = hashlib.sha256(f"{collection}|{day.isoformat()}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def footprint(mission: Mission, day: date) -> dict:
    """A deterministic GeoJSON polygon: one grid cell of the mission's region for this day.

    The cell is chosen by the seed, so backfilling a date range fills the region tile-by-tile.
    The ring is always inside ``mission.region_bbox``.
    """
    cols, rows = mission.grid
    cell_index = seed(mission.collection_id, day) % (cols * rows)
    row, col = divmod(cell_index, cols)

    lon_min, lat_min, lon_max, lat_max = mission.region_bbox
    cell_w = (lon_max - lon_min) / cols
    cell_h = (lat_max - lat_min) / rows
    inset = _INSET_FRACTION * min(cell_w, cell_h)

    x0 = lon_min + col * cell_w + inset
    y0 = lat_min + row * cell_h + inset
    x1 = lon_min + (col + 1) * cell_w - inset
    y1 = lat_min + (row + 1) * cell_h - inset

    ring = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
    return {"type": "Polygon", "coordinates": [ring]}
