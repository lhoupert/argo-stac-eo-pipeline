"""SW4: build_item produces a contract-valid STAC item.

These tests mirror the acceptance boundary: they assert the *contract* (a pystac-valid
item with the right id, datetime, geometry and exactly two assets), not the theme.
"""

from datetime import date

import pystac

from eo_ingest.synthetic.generate import build_item, footprint
from eo_ingest.synthetic.world import get_mission, iter_missions

DAY = date(2026, 3, 14)
DATA_HREF = "s3://bucket/synthetic-aurora-veil/20260314/data.png"
THUMB_HREF = "s3://bucket/synthetic-aurora-veil/20260314/thumbnail.png"


def _item(collection: str = "synthetic-aurora-veil") -> dict:
    return build_item(
        collection, DAY, data_href=DATA_HREF, thumbnail_href=THUMB_HREF
    )


def test_item_validates_via_pystac() -> None:
    # pystac.Item.from_dict raises if the dict is not a valid STAC item.
    item = pystac.Item.from_dict(_item())
    assert item.id == "MOI-AV_20260314"


def test_item_id_matches_pattern() -> None:
    for m in iter_missions():
        item = build_item(
            m.collection_id, DAY, data_href=DATA_HREF, thumbnail_href=THUMB_HREF
        )
        assert item["id"] == f"MOI-{m.code}_20260314"


def test_item_collection_carries_synthetic_prefix() -> None:
    item = _item()
    assert item["collection"] == "synthetic-aurora-veil"
    assert item["collection"].startswith("synthetic-")


def test_item_datetime_equals_requested_day_at_1030z() -> None:
    item = _item()
    assert item["properties"]["datetime"] == "2026-03-14T10:30:00Z"


def test_item_has_no_created_property() -> None:
    # The item must be byte-reproducible — a wall-clock "created" stamp would break that.
    assert "created" not in _item()["properties"]


def test_item_carries_mission_metadata() -> None:
    m = get_mission("synthetic-aurora-veil")
    props = _item()["properties"]
    assert props["platform"] == m.platform
    assert props["instruments"] == [m.instrument]
    assert props["gsd"] == 20
    assert props["mission"] == m.collection_id


def test_item_has_exactly_data_and_thumbnail_assets() -> None:
    assets = _item()["assets"]
    assert set(assets) == {"data", "thumbnail"}

    assert assets["data"]["href"] == DATA_HREF
    assert assets["data"]["type"] == "image/png"
    assert assets["data"]["roles"] == ["data"]

    assert assets["thumbnail"]["href"] == THUMB_HREF
    assert assets["thumbnail"]["type"] == "image/png"
    assert assets["thumbnail"]["roles"] == ["thumbnail"]


def test_item_geometry_matches_footprint_and_lies_inside_bbox() -> None:
    for m in iter_missions():
        item = build_item(
            m.collection_id, DAY, data_href=DATA_HREF, thumbnail_href=THUMB_HREF
        )
        assert item["geometry"] == footprint(m, DAY)

        ring = item["geometry"]["coordinates"][0]
        lons = [pt[0] for pt in ring]
        lats = [pt[1] for pt in ring]
        # bbox is [min_lon, min_lat, max_lon, max_lat] derived from the ring.
        assert item["bbox"] == [min(lons), min(lats), max(lons), max(lats)]

        b_lon_min, b_lat_min, b_lon_max, b_lat_max = m.region_bbox
        assert b_lon_min <= item["bbox"][0] <= item["bbox"][2] <= b_lon_max
        assert b_lat_min <= item["bbox"][1] <= item["bbox"][3] <= b_lat_max


def test_item_is_deterministic() -> None:
    assert _item() == _item()
