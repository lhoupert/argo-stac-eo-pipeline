"""The synthetic world as data: the Meridian Observation Initiative's two missions.

This module is *pure data* — declarative ``Mission`` records plus lookups. Adding a mission is a
data edit here, not new code elsewhere (one generator code path serves all missions).
See SYNTHETIC_WORLD_SPEC.md.
"""

from __future__ import annotations

from dataclasses import dataclass

# (lon_min, lat_min, lon_max, lat_max) in EPSG:4326.
BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class Mission:
    """One MOI mission = one STAC collection observed over one real region."""

    collection_id: str  # must carry the "synthetic-" prefix (the not-real marker)
    code: str  # 2-letter id used in item ids, e.g. "AV"
    region_bbox: BBox  # real-world bounds the footprints fall inside
    grid: tuple[int, int]  # (cols, rows) footprint tiling
    palette: tuple[str, str, str, str]  # 4-stop false-color ramp (hex)
    texture: str  # directional structure: "ribbons" (diagonal) or "channels" (horizontal)
    platform: str  # e.g. "moi-veil-1"
    instrument: str  # e.g. "mvi"


_MISSIONS: tuple[Mission, ...] = (
    Mission(
        collection_id="synthetic-aurora-veil",
        code="AV",
        region_bbox=(24.0, 67.5, 29.0, 69.5),  # Finnish Lapland
        grid=(4, 4),
        palette=("#0B0F3B", "#145C5C", "#2FBF71", "#C9A0FF"),  # auroral
        texture="ribbons",  # diagonal auroral ribbons
        platform="moi-veil-1",
        instrument="mvi",
    ),
    Mission(
        collection_id="synthetic-tidal-glass",
        code="TG",
        region_bbox=(5.0, 53.2, 9.2, 54.2),  # Wadden Sea (NL/DE)
        grid=(4, 4),
        palette=("#04243B", "#1E6F8E", "#5FC9E8", "#F2FBFF"),  # tidal shallows
        texture="channels",  # horizontal tidal channels
        platform="moi-glass-1",
        instrument="mgi",
    ),
)


def iter_missions() -> list[Mission]:
    """Return all missions in the world, in declaration order."""
    return list(_MISSIONS)


def get_mission(collection_id: str) -> Mission:
    """Look up a mission by its collection id; raise ``KeyError`` for an unknown id."""
    for mission in _MISSIONS:
        if mission.collection_id == collection_id:
            return mission
    known = ", ".join(m.collection_id for m in _MISSIONS)
    raise KeyError(f"unknown synthetic collection {collection_id!r}; known: {known}")
