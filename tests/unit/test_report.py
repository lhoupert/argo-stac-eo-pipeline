"""T21 — the rung-4 daily report: self-correction at a glance.

Two levels, two sources, both injectable so the module is testable without a cluster:
  * SYSTEM level — per-collection gap heatmaps from the logbook (⬜ → ✅ as gaps refill);
  * ITEM level   — recent workflow runs from the Argo Workflows API (failed attempts that retried).

The heatmap glyphs (✅/⬜) are shape-distinct, so the report is color-blind-safe by construction.
"""

from __future__ import annotations

from datetime import date

import httpx
import respx

from eo_ingest.report import (
    Run,
    build_markdown,
    fetch_runs,
    gap_heatmap,
    summarize_runs,
)

START = date(2026, 3, 1)
END = date(2026, 3, 14)
ARGO = "https://argo-server:2746"
NS = "eo"


def _present(*day_nums: int) -> set[date]:
    return {date(2026, 3, d) for d in day_nums}


# --- gap heatmap (pure, the heart of the rung) ---------------------------------------------------
def test_heatmap_marks_present_and_missing_days() -> None:
    present = _present(*[d for d in range(1, 15) if d not in (4, 5, 10)])
    md = gap_heatmap("synthetic-aurora-veil", START, END, present)
    assert "synthetic-aurora-veil" in md
    assert "3 gap" in md  # 3 missing days in the summary line
    assert md.count("✅") == 11
    assert md.count("⬜") == 3


def test_fully_backfilled_heatmap_is_all_present() -> None:
    md = gap_heatmap("synthetic-aurora-veil", START, END, _present(*range(1, 15)))
    assert "0 gap" in md
    assert md.count("⬜") == 0
    assert md.count("✅") == 14


def test_heatmap_is_deterministic() -> None:
    p = _present(1, 2, 3)
    assert gap_heatmap("c", START, END, p) == gap_heatmap("c", START, END, p)


# --- workflow summary (item-level self-correction) -----------------------------------------------
def test_summary_counts_phases_and_retried_attempts() -> None:
    summary = summarize_runs(
        [
            Run("rung1-a", "Succeeded", retried_attempts=1),
            Run("rung2-b", "Succeeded", retried_attempts=0),
            Run("rung1-c", "Failed", retried_attempts=0),
        ]
    )
    assert summary["total"] == 3
    assert summary["succeeded"] == 2
    assert summary["failed"] == 1
    assert summary["retried_attempts"] == 1  # the one failed-then-recovered attempt


def _wf(name: str, phase: str, failed_pods: int = 0) -> dict:
    nodes = {f"{name}-p{i}": {"type": "Pod", "phase": "Failed"} for i in range(failed_pods)}
    nodes[f"{name}-ok"] = {"type": "Pod", "phase": "Succeeded"}
    return {"metadata": {"name": name}, "status": {"phase": phase, "nodes": nodes}}


@respx.mock
def test_fetch_runs_uses_the_archive_when_available() -> None:
    archive = respx.get(f"{ARGO}/api/v1/archived-workflows").mock(
        return_value=httpx.Response(200, json={"items": [_wf("a", "Succeeded", failed_pods=1)]})
    )
    runs = fetch_runs(ARGO, NS)
    assert archive.called
    assert [r.name for r in runs] == ["a"]
    assert runs[0].retried_attempts == 1  # one Failed pod => one retried attempt


@respx.mock
def test_fetch_runs_enriches_archived_runs_that_lack_nodes() -> None:
    # The archived LIST strips node trees, so a run with no nodes must be re-fetched by uid to
    # recover the failed-then-retried attempts.
    stub = {"metadata": {"name": "a", "uid": "u1"}, "status": {"phase": "Succeeded"}}  # no nodes
    respx.get(f"{ARGO}/api/v1/archived-workflows").mock(
        return_value=httpx.Response(200, json={"items": [stub]})
    )
    full = respx.get(f"{ARGO}/api/v1/archived-workflows/u1").mock(
        return_value=httpx.Response(200, json=_wf("a", "Succeeded", failed_pods=2))
    )
    runs = fetch_runs(ARGO, NS)
    assert full.called  # had to enrich
    assert runs[0].retried_attempts == 2


@respx.mock
def test_fetch_runs_degrades_to_live_when_archive_unavailable() -> None:
    # Archive not configured yet (404/empty) -> fall back to the live workflows endpoint.
    respx.get(f"{ARGO}/api/v1/archived-workflows").mock(return_value=httpx.Response(404))
    live = respx.get(f"{ARGO}/api/v1/workflows/{NS}").mock(
        return_value=httpx.Response(200, json={"items": [_wf("b", "Succeeded")]})
    )
    runs = fetch_runs(ARGO, NS)
    assert live.called
    assert [r.name for r in runs] == ["b"]


@respx.mock
def test_fetch_runs_returns_empty_when_both_sources_fail() -> None:
    respx.get(f"{ARGO}/api/v1/archived-workflows").mock(return_value=httpx.Response(500))
    respx.get(f"{ARGO}/api/v1/workflows/{NS}").mock(side_effect=httpx.ConnectError("down"))
    assert fetch_runs(ARGO, NS) == []  # report degrades, never crashes


# --- markdown assembly ---------------------------------------------------------------------------
def test_build_markdown_includes_both_levels() -> None:
    heatmaps = [gap_heatmap("c1", START, END, _present(*range(1, 15)))]
    summary = {"total": 2, "succeeded": 2, "failed": 0, "retried_attempts": 1}
    md = build_markdown(heatmaps, summary, generated_at="2026-06-11T00:00:00Z")
    assert "self-correction" in md.lower()
    assert "c1" in md               # system level present
    assert "retried" in md.lower()  # item level present
    assert "2026-06-11" in md       # stamped
