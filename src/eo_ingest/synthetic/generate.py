"""Deterministic, pure generation for the synthetic world.

Everything here is a pure function of ``(collection, day)`` — no filesystem, network, or clock.
Determinism is load-bearing: recorded screencasts and the seeded catalog must reproduce
byte-for-byte. See SYNTHETIC_WORLD_SPEC.md.
"""

from __future__ import annotations

import hashlib
import io
import math
import random
from datetime import date

from PIL import Image

from .world import Mission, get_mission

# Polygons are inset from their grid cell so adjacent footprints read as discrete tiles.
_INSET_FRACTION = 0.08

# Raster sizing. The field is smooth value noise shaped into the mission's texture, computed with
# integer arithmetic only (no float anywhere) so PNG bytes are identical across architectures —
# see SYNTHETIC_WORLD_SPEC.md. Lattice cells must divide _SIZE.
_SIZE = 256
_COARSE_CELL = 64  # broad shapes
_FINE_CELL = 16  # detail octave
_WARP_CELL = 64  # low-frequency displacement that makes channels flow organically
_CHANNEL_PERIOD = 56  # horizontal band spacing (must be even)
_CELL_GRID = 5  # Worley feature points per axis (5x5 jittered grid)


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


def build_item(
    collection: str,
    day: date,
    *,
    data_href: str,
    thumbnail_href: str,
) -> dict:
    """A contract-valid STAC item dict for ``(collection, day)``.

    The caller owns I/O: it uploads the assets and passes their final hrefs in. This stays a
    pure function so seeding and screencasts reproduce byte-for-byte — note there is no
    ``created`` stamp. Geometry comes from :func:`footprint`; ``bbox`` is derived from its ring.
    """
    mission = get_mission(collection)
    geometry = footprint(mission, day)
    ring = geometry["coordinates"][0]
    lons = [pt[0] for pt in ring]
    lats = [pt[1] for pt in ring]
    bbox = [min(lons), min(lats), max(lons), max(lats)]

    return {
        "type": "Feature",
        "stac_version": "1.0.0",
        "stac_extensions": [],
        "id": f"MOI-{mission.code}_{day:%Y%m%d}",
        "collection": mission.collection_id,
        "geometry": geometry,
        "bbox": bbox,
        "properties": {
            "datetime": f"{day.isoformat()}T10:30:00Z",
            "mission": mission.collection_id,
            "platform": mission.platform,
            "instruments": [mission.instrument],
            "gsd": 20,
            "synthetic": True,
        },
        "links": [],
        "assets": {
            "data": {
                "href": data_href,
                "type": "image/png",
                "roles": ["data"],
            },
            "thumbnail": {
                "href": thumbnail_href,
                "type": "image/png",
                "roles": ["thumbnail"],
            },
        },
    }


# Generated imagery, not real observations — declared explicitly so the catalog never implies
# otherwise. The 'synthetic-' collection-id prefix is the other half of that signal.
_DATA_LICENSE = "CC-BY-4.0"


def build_collection(collection: str) -> dict:
    """A contract-valid STAC Collection doc for a mission.

    Pure data derived from the :class:`Mission` record: the spatial extent *is* the mission's
    real-world region. Rung 1 must create this before registering items, since items live under
    ``/collections/{id}/items``. Like :func:`build_item`, this is a pure function so seeding and
    screencasts reproduce byte-for-byte.
    """
    mission = get_mission(collection)
    lon_min, lat_min, lon_max, lat_max = mission.region_bbox
    return {
        "type": "Collection",
        "stac_version": "1.0.0",
        "stac_extensions": [],
        "id": mission.collection_id,
        "title": f"MOI {mission.code} (synthetic)",
        "description": (
            f"Synthetic Meridian Observation Initiative mission {mission.collection_id} "
            f"({mission.platform}/{mission.instrument}). Generated imagery — not real "
            f"observations; the 'synthetic-' id prefix marks it as such."
        ),
        "license": _DATA_LICENSE,
        "extent": {
            "spatial": {"bbox": [[lon_min, lat_min, lon_max, lat_max]]},
            "temporal": {"interval": [["2026-01-01T00:00:00Z", None]]},
        },
        "links": [],
    }


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    h = value.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _build_lut(palette: tuple[str, str, str, str]) -> list[tuple[int, int, int]]:
    """A 256-entry RGB lookup table interpolating the 4-stop ramp with integer math only."""
    stops = [_hex_to_rgb(c) for c in palette]
    segments = len(stops) - 1
    lut: list[tuple[int, int, int]] = []
    for v in range(256):
        pos = v * segments
        seg = min(pos // 256, segments - 1)
        local = pos - seg * 256  # 0..255 within the segment
        lo, hi = stops[seg], stops[seg + 1]
        lut.append(tuple(lo[c] + (hi[c] - lo[c]) * local // 256 for c in range(3)))  # type: ignore[misc]
    return lut


def _smooth_weight(f: int, span: int) -> int:
    """Integer smoothstep: eases a 0..span ramp into an S-curve, returning 0..span."""
    return (3 * f * f * span - 2 * f * f * f) // (span * span)


def _value_octave(rng: random.Random, cell: int) -> list[int]:
    """Smooth value noise: a seeded lattice bilinearly interpolated with integer smoothstep.

    Unlike white noise, neighbouring pixels are correlated, so the field reads as coherent
    blobs (clouds/terrain) rather than static.
    """
    g = _SIZE // cell + 1
    lattice = [[rng.randint(0, 255) for _ in range(g)] for _ in range(g)]
    field = [0] * (_SIZE * _SIZE)
    cell2 = cell * cell
    for y in range(_SIZE):
        cy, fy = divmod(y, cell)
        wy = _smooth_weight(fy, cell)
        row = lattice[cy]
        row_next = lattice[cy + 1]
        out_base = y * _SIZE
        for x in range(_SIZE):
            cx, fx = divmod(x, cell)
            wx = _smooth_weight(fx, cell)
            top = row[cx] * (cell - wx) + row[cx + 1] * wx
            bot = row_next[cx] * (cell - wx) + row_next[cx + 1] * wx
            field[out_base + x] = (top * (cell - wy) + bot * wy) // cell2
    return field


def _triangle(t: int, period: int) -> int:
    """A 0..255 triangle wave of the given (even) period; total over any integer ``t``."""
    p = t % period
    half = period // 2
    return p * 255 // half if p <= half else (period - p) * 255 // half


def _cellular_field(rng: random.Random, base: list[int]) -> list[int]:
    """Worley (cellular) noise: distance to the nearest of a jittered grid of feature points.

    Centres come out dark and rims bright, giving irregular rounded oval blobs — auroral
    coronae. Distances use ``math.isqrt`` (exact integer) so bytes stay stable across arches.
    """
    g = _CELL_GRID
    span = _SIZE // g
    points = [
        (gx * _SIZE // g + rng.randint(0, span - 1), gy * _SIZE // g + rng.randint(0, span - 1))
        for gy in range(g)
        for gx in range(g)
    ]
    field = [0] * (_SIZE * _SIZE)
    for y in range(_SIZE):
        out_base = y * _SIZE
        for x in range(_SIZE):
            nearest = min((x - px) ** 2 + (y - py) ** 2 for px, py in points)
            blob = min(255, math.isqrt(nearest) * 255 // span)
            field[out_base + x] = (3 * blob + 2 * base[out_base + x]) // 5
    return field


def _channel_field(rng: random.Random, base: list[int]) -> list[int]:
    """Horizontal bands (``y``) displaced by a low-frequency octave, flowing as tidal channels."""
    warp = _value_octave(rng, _WARP_CELL)
    field = [0] * (_SIZE * _SIZE)
    for y in range(_SIZE):
        out_base = y * _SIZE
        for x in range(_SIZE):
            i = out_base + x
            band = _triangle(y + (warp[i] - 128) // 2, _CHANNEL_PERIOD)
            field[i] = (3 * band + 2 * base[i]) // 5  # 60% structure, 40% base texture
    return field


def _themed_field(mission: Mission, seed_value: int) -> list[int]:
    """A flat _SIZE×_SIZE field: smooth base noise shaped into the mission's texture.

    Two octaves of value noise give an organic base, then the mission's ``texture`` imposes
    structure: ``cells`` (Worley blobs) or ``channels`` (horizontal bands). Integer-only
    throughout to stay byte-stable across architectures.
    """
    rng = random.Random(seed_value)
    coarse = _value_octave(rng, _COARSE_CELL)
    fine = _value_octave(rng, _FINE_CELL)
    base = [(3 * coarse[i] + fine[i]) // 4 for i in range(_SIZE * _SIZE)]

    if mission.texture == "cells":
        return _cellular_field(rng, base)
    return _channel_field(rng, base)


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False, compress_level=6)  # no metadata chunks
    return buf.getvalue()


def render_assets(collection: str, day: date) -> tuple[bytes, bytes]:
    """Render the deterministic ``data`` (grayscale) and ``thumbnail`` (false-color) PNG bytes.

    Pure and byte-stable: same ``(collection, day)`` → identical bytes on any architecture.
    """
    mission = get_mission(collection)
    field = _themed_field(mission, seed(collection, day))

    data_img = Image.new("L", (_SIZE, _SIZE))
    data_img.putdata(field)

    lut = _build_lut(mission.palette)
    thumb_img = Image.new("RGB", (_SIZE, _SIZE))
    thumb_img.putdata([lut[v] for v in field])

    return _png_bytes(data_img), _png_bytes(thumb_img)
