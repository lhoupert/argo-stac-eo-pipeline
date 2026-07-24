"""SW2: deterministic footprint geometry."""

from datetime import date

from eo_ingest.synthetic.generate import footprint, seed
from eo_ingest.synthetic.world import get_mission, iter_missions

AV = get_mission("synthetic-aurora-veil")


def _ring(poly: dict) -> list[list[float]]:
    assert poly["type"] == "Polygon"
    rings = poly["coordinates"]
    assert len(rings) == 1
    return rings[0]


def test_seed_is_deterministic() -> None:
    d = date(2026, 3, 14)
    assert seed("synthetic-aurora-veil", d) == seed("synthetic-aurora-veil", d)


def test_seed_differs_by_collection_and_day() -> None:
    d = date(2026, 3, 14)
    assert seed("synthetic-aurora-veil", d) != seed("synthetic-tidal-glass", d)
    assert seed("synthetic-aurora-veil", d) != seed("synthetic-aurora-veil", date(2026, 3, 15))


def test_footprint_is_deterministic() -> None:
    d = date(2026, 3, 14)
    assert footprint(AV, d) == footprint(AV, d)


def test_footprint_ring_is_closed_pentagon() -> None:
    ring = _ring(footprint(AV, date(2026, 3, 14)))
    assert len(ring) == 5
    assert ring[0] == ring[-1]


def test_footprint_lies_inside_region_bbox() -> None:
    for m in iter_missions():
        b_lon_min, b_lat_min, b_lon_max, b_lat_max = m.region_bbox
        for lon, lat in _ring(footprint(m, date(2026, 3, 14))):
            assert b_lon_min <= lon <= b_lon_max
            assert b_lat_min <= lat <= b_lat_max


def test_footprint_is_total_over_edge_case_dates() -> None:
    edge_dates = [date(2024, 2, 29), date(2025, 12, 31), date(2026, 1, 1), date(2099, 1, 1)]
    for m in iter_missions():
        b_lon_min, b_lat_min, b_lon_max, b_lat_max = m.region_bbox
        for d in edge_dates:
            ring = _ring(footprint(m, d))
            assert len(ring) == 5 and ring[0] == ring[-1]
            for lon, lat in ring:
                assert b_lon_min <= lon <= b_lon_max
                assert b_lat_min <= lat <= b_lat_max


def test_footprint_varies_across_days() -> None:
    seen = {tuple(map(tuple, _ring(footprint(AV, date(2026, 3, d))))) for d in range(1, 32)}
    assert len(seen) > 1
