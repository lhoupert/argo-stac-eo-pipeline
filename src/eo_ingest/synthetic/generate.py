"""Deterministic, pure generation for the synthetic world.

Everything here is a pure function of ``(collection, day)`` — no filesystem, network, or clock.
Determinism is load-bearing: recorded screencasts and the seeded catalog must reproduce
byte-for-byte. See SYNTHETIC_WORLD_SPEC.md.
"""

from __future__ import annotations

import hashlib
import io
import random
from datetime import date

from PIL import Image

from .world import Mission, get_mission

# Polygons are inset from their grid cell so adjacent footprints read as discrete tiles.
_INSET_FRACTION = 0.08

# Raster sizing. The coarse field is block-replicated up to _SIZE with integer arithmetic only
# (no float resize) so PNG bytes are identical across architectures — see SYNTHETIC_WORLD_SPEC.md.
_SIZE = 256
_COARSE = 32
_BLOCK = _SIZE // _COARSE


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


def _noise_field(seed_value: int) -> list[int]:
    """A coarse seeded grid block-replicated to a flat _SIZE×_SIZE list of 0..255 values."""
    rng = random.Random(seed_value)
    coarse = [rng.randint(0, 255) for _ in range(_COARSE * _COARSE)]
    field = [0] * (_SIZE * _SIZE)
    for y in range(_SIZE):
        row_base = (y // _BLOCK) * _COARSE
        out_base = y * _SIZE
        for x in range(_SIZE):
            field[out_base + x] = coarse[row_base + x // _BLOCK]
    return field


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False, compress_level=6)  # no metadata chunks
    return buf.getvalue()


def render_assets(collection: str, day: date) -> tuple[bytes, bytes]:
    """Render the deterministic ``data`` (grayscale) and ``thumbnail`` (false-color) PNG bytes.

    Pure and byte-stable: same ``(collection, day)`` → identical bytes on any architecture.
    """
    mission = get_mission(collection)
    field = _noise_field(seed(collection, day))

    data_img = Image.new("L", (_SIZE, _SIZE))
    data_img.putdata(field)

    lut = _build_lut(mission.palette)
    thumb_img = Image.new("RGB", (_SIZE, _SIZE))
    thumb_img.putdata([lut[v] for v in field])

    return _png_bytes(data_img), _png_bytes(thumb_img)
