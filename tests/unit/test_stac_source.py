"""T4: resolve STAC items for a window — synthetic (default) + earthsearch backends.

Tests target the *interface contract* (deterministic items with real-coord polygon + data +
thumbnail assets; bounded query; empty window -> []), not the themed world.
"""

from datetime import date

import pystac
import pytest

from eo_ingest.config import load_config
from eo_ingest.stac_source import EARTH_SEARCH_URL, resolve_items
from eo_ingest.synthetic.world import get_mission

START = date(2026, 3, 1)
END = date(2026, 3, 8)  # half-open => 7 days


def _synthetic_cfg(**over):
    env = {"SOURCE_TYPE": "synthetic", "COLLECTION": "synthetic-aurora-veil", **over}
    return load_config(env)


# --- synthetic backend (the ladder default) -------------------------------------------------


def test_synthetic_returns_one_item_per_day_in_half_open_window() -> None:
    items = resolve_items(_synthetic_cfg(), START, END)
    assert len(items) == 7
    datetimes = sorted(it["properties"]["datetime"][:10] for it in items)
    assert datetimes[0] == "2026-03-01"
    assert datetimes[-1] == "2026-03-07"  # END (03-08) is excluded


def test_synthetic_items_satisfy_the_contract() -> None:
    mission = get_mission("synthetic-aurora-veil")
    b_lon_min, b_lat_min, b_lon_max, b_lat_max = mission.region_bbox
    for raw in resolve_items(_synthetic_cfg(), START, END):
        item = pystac.Item.from_dict(raw)  # valid STAC item
        assert set(raw["assets"]) == {"data", "thumbnail"}
        # real-coord polygon geometry inside the mission's region
        assert raw["geometry"]["type"] == "Polygon"
        for lon, lat in raw["geometry"]["coordinates"][0]:
            assert b_lon_min <= lon <= b_lon_max
            assert b_lat_min <= lat <= b_lat_max
        assert item.collection_id == "synthetic-aurora-veil"


def test_synthetic_asset_hrefs_are_deterministic_s3_keys() -> None:
    cfg = _synthetic_cfg(S3_BUCKET="eo-assets")
    items = resolve_items(cfg, date(2026, 3, 14), date(2026, 3, 15))
    assets = items[0]["assets"]
    assert assets["data"]["href"] == "s3://eo-assets/synthetic-aurora-veil/2026/03/14/data.png"
    assert assets["thumbnail"]["href"] == (
        "s3://eo-assets/synthetic-aurora-veil/2026/03/14/thumbnail.png"
    )


def test_synthetic_is_deterministic() -> None:
    first = resolve_items(_synthetic_cfg(), START, END)
    second = resolve_items(_synthetic_cfg(), START, END)
    assert first == second


def test_empty_window_returns_empty_list() -> None:
    assert resolve_items(_synthetic_cfg(), START, START) == []


def test_window_is_capped_by_max_items() -> None:
    items = resolve_items(_synthetic_cfg(), date(2026, 1, 1), date(2026, 12, 31), max_items=5)
    assert len(items) == 5


# --- earthsearch backend (thin real branch, mocked at the client boundary) -------------------


class _FakeSearch:
    def __init__(self, items):
        self._items = items

    def items(self):
        return iter(self._items)


class _FakeClient:
    last_url = None
    last_search = None

    @classmethod
    def open(cls, url, **kwargs):
        cls.last_url = url
        return cls()

    def search(self, **kwargs):
        type(self).last_search = kwargs
        item = pystac.Item.from_dict(
            {
                "type": "Feature",
                "stac_version": "1.0.0",
                "id": "S2_real_1",
                "collection": "sentinel-2-l2a",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[5, 53], [6, 53], [6, 54], [5, 53]]],
                },
                "bbox": [5, 53, 6, 54],
                "properties": {"datetime": "2026-03-02T10:00:00Z"},
                "links": [],
                "assets": {},
            }
        )
        return _FakeSearch([item])


def _patch_client(monkeypatch, fake=_FakeClient):
    import eo_ingest.stac_source as mod

    monkeypatch.setattr(mod, "Client", fake)


def test_earthsearch_queries_the_real_api_bounded(monkeypatch) -> None:
    _patch_client(monkeypatch)
    cfg = load_config({"SOURCE_TYPE": "earthsearch", "COLLECTION": "sentinel-2-l2a"})
    items = resolve_items(cfg, START, END, bbox=[5, 53, 6, 54], max_items=10)

    assert _FakeClient.last_url == EARTH_SEARCH_URL
    assert _FakeClient.last_search["collections"] == ["sentinel-2-l2a"]
    assert _FakeClient.last_search["bbox"] == [5, 53, 6, 54]
    assert _FakeClient.last_search["max_items"] == 10  # bounded
    assert "2026-03-01" in _FakeClient.last_search["datetime"]
    assert items[0]["id"] == "S2_real_1"


def test_earthsearch_empty_result_returns_empty_list(monkeypatch) -> None:
    class _Empty(_FakeClient):
        def search(self, **kwargs):
            return _FakeSearch([])

    _patch_client(monkeypatch, _Empty)
    cfg = load_config({"SOURCE_TYPE": "earthsearch", "COLLECTION": "sentinel-2-l2a"})
    assert resolve_items(cfg, START, END, bbox=[5, 53, 6, 54]) == []


def test_earthsearch_requires_a_bbox(monkeypatch) -> None:
    _patch_client(monkeypatch)
    cfg = load_config({"SOURCE_TYPE": "earthsearch", "COLLECTION": "sentinel-2-l2a"})
    with pytest.raises(ValueError, match="bbox"):
        resolve_items(cfg, START, END)


def test_earthsearch_falls_back_to_configured_bbox(monkeypatch) -> None:
    # The frozen ingest calls resolve_items WITHOUT a bbox, so config.bbox (env BBOX) must drive it.
    _patch_client(monkeypatch)
    cfg = load_config(
        {"SOURCE_TYPE": "earthsearch", "COLLECTION": "sentinel-2-l2a", "BBOX": "5,53,6,54"}
    )
    items = resolve_items(cfg, START, END)  # no explicit bbox
    assert _FakeClient.last_search["bbox"] == [5.0, 53.0, 6.0, 54.0]
    assert items[0]["id"] == "S2_real_1"


def test_earthsearch_trims_item_to_the_configured_asset(monkeypatch) -> None:
    class _Multi(_FakeClient):
        def search(self, **kwargs):
            type(self).last_search = kwargs
            item = pystac.Item.from_dict(
                {
                    "type": "Feature", "stac_version": "1.0.0", "id": "S2_multi",
                    "collection": "sentinel-2-l2a",
                    "geometry": {"type": "Polygon",
                                 "coordinates": [[[5, 53], [6, 53], [6, 54], [5, 53]]]},
                    "bbox": [5, 53, 6, 54], "properties": {"datetime": "2026-03-02T10:00:00Z"},
                    "links": [],
                    "assets": {
                        "thumbnail": {"href": "https://x/t.jpg"},
                        "red": {"href": "https://x/r.tif"},
                        "nir": {"href": "https://x/n.tif"},
                    },
                }
            )
            return _FakeSearch([item])

    _patch_client(monkeypatch, _Multi)
    cfg = load_config(
        {"SOURCE_TYPE": "earthsearch", "COLLECTION": "sentinel-2-l2a", "BBOX": "5,53,6,54"}
    )
    items = resolve_items(cfg, START, END)  # ASSET defaults to "thumbnail"
    assert list(items[0]["assets"]) == ["thumbnail"]  # the other ~bands trimmed away
