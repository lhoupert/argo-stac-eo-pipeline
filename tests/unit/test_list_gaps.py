"""T19 — the `eo_ingest.list_gaps` CLI: emit a collection's missing days as JSON.

This is the seam between `find_gaps` (T18) and Argo's dynamic fan-out: the rung-3 workflow runs
this, captures stdout as a step result, and fans `ingest` out over the days it prints. stdout must
be *only* the JSON array (no rich, no log noise) so `withParam` can parse it.
"""

from __future__ import annotations

import json
from datetime import date

import httpx
import respx

from eo_ingest.list_gaps import main

STAC_URL = "http://stac-api"
COLLECTION = "synthetic-aurora-veil"
ITEMS_URL = f"{STAC_URL}/collections/{COLLECTION}/items"


def _mock(features: list[dict]) -> None:
    respx.get(ITEMS_URL).mock(
        return_value=httpx.Response(200, json={"type": "FeatureCollection", "features": features})
    )


def _env():
    return {"STAC_URL": STAC_URL, "COLLECTION": COLLECTION}


@respx.mock
def test_prints_missing_days_as_a_json_array(capsys) -> None:
    present = [
        {"id": f"d{d}", "properties": {"datetime": f"2026-03-0{d}T10:00:00Z"}}
        for d in (1, 2, 5)
    ]
    _mock(present)
    rc = main(["--start", "2026-03-01", "--end", "2026-03-05"], env=_env())
    out = capsys.readouterr().out.strip()

    assert rc == 0
    assert json.loads(out) == ["2026-03-03", "2026-03-04"]


@respx.mock
def test_no_gaps_prints_empty_array(capsys) -> None:
    present = [
        {"id": f"d{d}", "properties": {"datetime": f"2026-03-0{d}T10:00:00Z"}}
        for d in range(1, 6)
    ]
    _mock(present)
    rc = main(["--start", "2026-03-01", "--end", "2026-03-05"], env=_env())
    out = capsys.readouterr().out.strip()

    assert rc == 0
    # An empty array is what makes the rung-3 re-run a clean no-op (Argo fans out over nothing).
    assert json.loads(out) == []


@respx.mock
def test_stdout_is_only_the_json(capsys) -> None:
    _mock([])
    main(["--start", "2026-03-01", "--end", "2026-03-02"], env=_env())
    out = capsys.readouterr().out.strip()
    # Exactly one line, parseable as JSON — Argo withParam consumes the whole result.
    assert out.count("\n") == 0
    assert json.loads(out) == ["2026-03-01", "2026-03-02"]
    assert [date.fromisoformat(d) for d in json.loads(out)]  # all valid ISO dates
