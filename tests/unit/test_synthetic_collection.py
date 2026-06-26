"""build_collection — a contract-valid STAC Collection doc for a synthetic mission.

Rung 1 registers items into ``/collections/{id}/items``, which requires the collection to exist
first. The collection's spatial extent is the mission's real-world region; its synthetic nature is
explicit (license + the ``synthetic-`` id prefix).
"""

from __future__ import annotations

import pytest

from eo_ingest.synthetic import build_collection
from eo_ingest.synthetic.world import get_mission, iter_missions


@pytest.mark.parametrize("mission", iter_missions(), ids=lambda m: m.collection_id)
def test_collection_shape_is_contract_valid(mission) -> None:
    coll = build_collection(mission.collection_id)
    assert coll["type"] == "Collection"
    assert coll["id"] == mission.collection_id
    assert coll["stac_version"]
    assert coll["description"]
    assert coll["license"], "synthetic data still needs an explicit license"
    assert isinstance(coll["links"], list)


@pytest.mark.parametrize("mission", iter_missions(), ids=lambda m: m.collection_id)
def test_spatial_extent_is_the_mission_region(mission) -> None:
    coll = build_collection(mission.collection_id)
    bbox = coll["extent"]["spatial"]["bbox"]
    assert bbox == [list(mission.region_bbox)]
    # Temporal extent is a single open-ended interval [start, end].
    interval = coll["extent"]["temporal"]["interval"]
    assert len(interval) == 1 and len(interval[0]) == 2


def test_is_pure_deterministic() -> None:
    cid = iter_missions()[0].collection_id
    assert build_collection(cid) == build_collection(cid)


def test_unknown_collection_raises() -> None:
    with pytest.raises(KeyError):
        build_collection("not-a-real-mission")
    # sanity: the helper we lean on is the same lookup build_item uses
    assert get_mission(iter_missions()[0].collection_id)
