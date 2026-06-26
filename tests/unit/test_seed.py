"""T17 — seed the logbook with deliberate, per-collection gaps.

The seed reuses the frozen unit of work (`ingest_one`) over a date window, *skipping* planted days
so the catalog comes up with reproducible holes — the holes rung 3's `find_gaps` will detect and
close. Two missions over two distinct regions, each with its own gap pattern.

Logic lives in `eo_ingest.seed` so it's unit-testable with injected fakes (no cluster); the
`ingest`/`ensure-collection` work is mocked out here — we assert *which* days get ingested.
"""

from __future__ import annotations

from datetime import date, timedelta

from eo_ingest.config import Config
from eo_ingest.seed import (
    DEFAULT_START,
    DEFAULT_WINDOW,
    GAP_OFFSETS,
    present_offsets,
    seed,
)
from eo_ingest.synthetic.world import iter_missions

BOTH = [m.collection_id for m in iter_missions()]


def test_planted_gaps_are_per_collection_and_reproducible() -> None:
    assert set(GAP_OFFSETS) == set(BOTH), "every mission has a planted gap pattern"
    # The two collections must have *different* holes (separable demo).
    assert GAP_OFFSETS[BOTH[0]] != GAP_OFFSETS[BOTH[1]]
    # Pure/deterministic.
    assert present_offsets(BOTH[0], DEFAULT_WINDOW) == present_offsets(BOTH[0], DEFAULT_WINDOW)


def test_present_offsets_excludes_exactly_the_gaps() -> None:
    for cid in BOTH:
        present = set(present_offsets(cid, DEFAULT_WINDOW))
        gaps = set(GAP_OFFSETS[cid])
        assert present.isdisjoint(gaps), "a planted gap is never ingested"
        assert present | gaps == set(range(DEFAULT_WINDOW)), "present + gaps tile the window"
        assert list(present_offsets(cid, DEFAULT_WINDOW)) == sorted(present)


def test_seed_ingests_present_days_for_both_collections_skipping_gaps() -> None:
    ensured: list[str] = []
    ingested: list[tuple[str, date]] = []

    def fake_ensure(cfg: Config, collection: dict) -> str:
        ensured.append(collection["id"])
        return "created"

    def fake_ingest(cfg: Config, day: date) -> dict:
        ingested.append((cfg.collection, day))
        return {"ingested": 1}

    summary = seed(
        {"STAC_URL": "http://stac-api"},
        ingest_fn=fake_ingest,
        ensure_fn=fake_ensure,
    )

    # Both collections bootstrapped, over distinct regions.
    assert ensured == BOTH

    for cid in BOTH:
        days = sorted(d for c, d in ingested if c == cid)
        expected = [DEFAULT_START + timedelta(days=o) for o in present_offsets(cid, DEFAULT_WINDOW)]
        assert days == expected
        # The gap days are demonstrably absent.
        gap_days = {DEFAULT_START + timedelta(days=o) for o in GAP_OFFSETS[cid]}
        assert gap_days.isdisjoint(days)
        assert summary[cid]["present"] == len(expected)
        assert summary[cid]["gaps"] == sorted(GAP_OFFSETS[cid])


def test_seed_requires_a_catalog() -> None:
    # No STAC_URL -> seeding a logbook makes no sense; fail loudly.
    import pytest

    with pytest.raises(ValueError, match="STAC_URL"):
        seed({}, ingest_fn=lambda *a: None, ensure_fn=lambda *a: None)
