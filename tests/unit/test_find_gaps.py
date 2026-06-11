"""T18 — logbook.find_gaps(): which days in a window are missing from the catalog.

This is the logbook turning active: it answers "what *should* be here but isn't?" so rung 3 can
fan out ingest over only the gaps. The tests are deliberately adversarial — null datetimes,
missing datetimes, duplicates, and the empty / fully-backfilled boundaries — because find_gaps
runs against real catalog data, not the tidy items we write.
"""

from __future__ import annotations

import logging
from datetime import date

import httpx
import respx

from eo_ingest.config import load_config
from eo_ingest.logbook import find_gaps

STAC_URL = "http://stac-api"
COLLECTION = "synthetic-aurora-veil"
ITEMS_URL = f"{STAC_URL}/collections/{COLLECTION}/items"

START = date(2026, 3, 1)
END = date(2026, 3, 7)  # a 7-day inclusive window: 03-01 .. 03-07


def _cfg():
    return load_config({"STAC_URL": STAC_URL, "COLLECTION": COLLECTION})


def _feature(item_id: str, *, datetime_=..., start_datetime=None):
    """A minimal item. `datetime_=...` means 'omit'; pass None to send an explicit null."""
    props: dict = {}
    if datetime_ is not ...:
        props["datetime"] = datetime_
    if start_datetime is not None:
        props["start_datetime"] = start_datetime
    return {"id": item_id, "type": "Feature", "properties": props}


def _mock_items(features: list[dict]) -> respx.Route:
    return respx.get(ITEMS_URL).mock(
        return_value=httpx.Response(200, json={"type": "FeatureCollection", "features": features})
    )


def _all_days() -> list[date]:
    return [date(2026, 3, d) for d in range(1, 8)]


@respx.mock
def test_empty_catalog_every_day_is_a_gap() -> None:
    _mock_items([])
    assert find_gaps(_cfg(), COLLECTION, START, END) == _all_days()


@respx.mock
def test_fully_backfilled_no_gaps() -> None:
    feats = [_feature(f"d{d}", datetime_=f"2026-03-0{d}T10:00:00Z") for d in range(1, 8)]
    _mock_items(feats)
    assert find_gaps(_cfg(), COLLECTION, START, END) == []


@respx.mock
def test_reports_exactly_the_missing_days() -> None:
    present = {1, 2, 5, 7}
    feats = [_feature(f"d{d}", datetime_=f"2026-03-0{d}T10:00:00Z") for d in present]
    _mock_items(feats)
    assert find_gaps(_cfg(), COLLECTION, START, END) == [date(2026, 3, d) for d in (3, 4, 6)]


@respx.mock
def test_null_datetime_falls_back_to_start_datetime() -> None:
    # A null top-level datetime must not crash and must not be treated as "missing":
    # fall back to start_datetime so the day still counts as present.
    feats = [_feature(f"d{d}", datetime_=f"2026-03-0{d}T10:00:00Z") for d in (1, 2, 3, 4, 5, 6)]
    feats.append(_feature("d7", datetime_=None, start_datetime="2026-03-07T09:00:00Z"))
    _mock_items(feats)
    assert find_gaps(_cfg(), COLLECTION, START, END) == []


@respx.mock
def test_neither_datetime_is_skipped_with_a_warning(caplog) -> None:
    feats = [_feature(f"d{d}", datetime_=f"2026-03-0{d}T10:00:00Z") for d in (1, 2, 3, 4, 5, 6)]
    feats.append(_feature("bad7", datetime_=None))  # neither datetime nor start_datetime
    _mock_items(feats)
    with caplog.at_level(logging.WARNING):
        gaps = find_gaps(_cfg(), COLLECTION, START, END)
    # The undatable item is ignored (so its day stays a gap) and a warning names it — no crash.
    assert gaps == [date(2026, 3, 7)]
    assert any("bad7" in r.message for r in caplog.records)


@respx.mock
def test_duplicate_and_same_day_items_are_idempotent() -> None:
    feats = [
        _feature("a", datetime_="2026-03-01T10:00:00Z"),
        _feature("a", datetime_="2026-03-01T10:00:00Z"),  # exact duplicate id
        _feature("b", datetime_="2026-03-01T23:00:00Z"),  # same day, different item
    ]
    _mock_items(feats)
    # Only 03-01 is covered; the rest of the window are gaps — duplicates don't change that.
    assert find_gaps(_cfg(), COLLECTION, START, END) == [date(2026, 3, d) for d in range(2, 8)]


@respx.mock
def test_query_is_bounded_by_max_items() -> None:
    route = _mock_items([])
    find_gaps(_cfg(), COLLECTION, START, END, max_items=25)
    request = route.calls.last.request
    assert request.url.params["limit"] == "25"


@respx.mock
def test_malformed_datetime_is_skipped_with_a_warning(caplog) -> None:
    # A present-but-unparseable datetime is "untidy real data": skip it with a warning, never
    # crash the whole scan (the function advertises robustness to real catalog data).
    feats = [_feature(f"d{d}", datetime_=f"2026-03-0{d}T10:00:00Z") for d in (1, 2, 3, 4, 5, 6)]
    feats.append(_feature("bad7", datetime_="not-a-real-date"))
    _mock_items(feats)
    with caplog.at_level(logging.WARNING):
        gaps = find_gaps(_cfg(), COLLECTION, START, END)
    assert gaps == [date(2026, 3, 7)]  # the undatable item's day stays a gap
    assert any("bad7" in r.message for r in caplog.records)


@respx.mock
def test_hitting_the_max_items_ceiling_warns_about_truncation(caplog) -> None:
    # If the page is full, results may be truncated -> present days under-counted -> false gaps.
    # Warn loudly rather than silently report days that actually exist as missing.
    feats = [_feature(f"d{d}", datetime_=f"2026-03-0{d}T10:00:00Z") for d in (1, 2, 3)]
    _mock_items(feats)
    with caplog.at_level(logging.WARNING):
        find_gaps(_cfg(), COLLECTION, START, END, max_items=3)
    assert any("max_items" in r.message or "truncat" in r.message.lower() for r in caplog.records)


@respx.mock
def test_single_day_window() -> None:
    _mock_items([])
    assert find_gaps(_cfg(), COLLECTION, START, START) == [START]


def test_find_gaps_without_stac_url_is_a_clear_error() -> None:
    import pytest

    cfg = load_config({"COLLECTION": COLLECTION})  # STAC_URL unset
    with pytest.raises(ValueError, match="STAC_URL"):
        find_gaps(cfg, COLLECTION, START, END)
