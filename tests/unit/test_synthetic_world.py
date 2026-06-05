"""SW1: the synthetic world registry — Mission records and their invariants."""

import pytest

from eo_ingest.synthetic.world import Mission, get_mission, iter_missions


def test_world_has_two_missions() -> None:
    missions = iter_missions()
    assert len(missions) == 2
    assert all(isinstance(m, Mission) for m in missions)


def test_collection_ids_carry_synthetic_prefix() -> None:
    for m in iter_missions():
        assert m.collection_id.startswith("synthetic-")


def test_mission_codes_are_unique_two_letter_uppercase() -> None:
    codes = [m.code for m in iter_missions()]
    assert len(set(codes)) == len(codes)
    assert all(len(c) == 2 and c.isupper() for c in codes)


def test_each_palette_has_four_stops() -> None:
    for m in iter_missions():
        assert len(m.palette) == 4


def test_each_mission_declares_a_known_texture() -> None:
    # The texture drives the directional structure in the raster (ribbons vs channels).
    for m in iter_missions():
        assert m.texture in {"ribbons", "channels"}


def test_textures_are_distinct_per_mission() -> None:
    textures = [m.texture for m in iter_missions()]
    assert len(set(textures)) == len(textures)


def test_region_bboxes_are_valid() -> None:
    for m in iter_missions():
        lon_min, lat_min, lon_max, lat_max = m.region_bbox
        assert -180 <= lon_min < lon_max <= 180
        assert -90 <= lat_min < lat_max <= 90


def test_region_bboxes_do_not_overlap() -> None:
    a, b = iter_missions()
    a_lon_min, a_lat_min, a_lon_max, a_lat_max = a.region_bbox
    b_lon_min, b_lat_min, b_lon_max, b_lat_max = b.region_bbox
    disjoint = (
        a_lon_max <= b_lon_min
        or b_lon_max <= a_lon_min
        or a_lat_max <= b_lat_min
        or b_lat_max <= a_lat_min
    )
    assert disjoint


def test_get_mission_looks_up_by_collection_id() -> None:
    assert get_mission("synthetic-aurora-veil").code == "AV"
    assert get_mission("synthetic-tidal-glass").code == "TG"


def test_get_mission_raises_for_unknown_id() -> None:
    with pytest.raises(KeyError):
        get_mission("synthetic-nonexistent")
