"""T15 — the rung-1 acceptance smoke + cold/warm budget.  ⚠️ CONTRACT LAYER.

This is the talk's central Success-Criteria contract made executable: a fresh clone must reach a
working rung 1 — with **pgSTAC on the path** (the item is queryable in the logbook) — inside a
bounded time. The budget assertion below MUST NOT be weakened, skipped, or xfail'd without
explicit human approval (see SPEC Boundaries / todo.md T15).

What it does, timed end-to-end:
    make down        # clean slate -> the `up` that follows is COLD (fresh cluster)
    make up          # kind + MinIO + pgSTAC + stac-api + stac-browser + Argo + bucket
    make demo STAGE=01   # submit the rung-1 Workflow and watch it (fail-once -> retry -> succeed)
then proves the item is registered in the STAC API and asserts the total wall-clock is within
budget.

SAFETY: `make down` deletes the kind cluster, so this is **opt-in** — it runs only when
RUN_CLUSTER_SMOKE=1, never on a bare `pytest tests/`. Gating execution is a guardrail against
accidental cluster destruction; it does not relax the contract (the budget assertion is
unconditional once the test runs). CI's kind-smoke job (T23) sets the env var.

Budgets (SPEC): cold < 15 min, warm < 5 min. The test enforces the COLD ceiling — the hard line
the demo must never cross. The warm figure is reported for the README, not separately asserted.
The CI-runner specs are recorded separately in the README; numbers from a laptop are not a CI SLA.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NS = "eo"
COLLECTION = "synthetic-aurora-veil"
EXPECTED_ITEM = "MOI-AV_20260314"

COLD_BUDGET_S = 15 * 60  # the contract ceiling — DO NOT weaken without human approval
WARM_BUDGET_S = 5 * 60   # reported, not asserted (the test always runs cold via `make down`)

_TOOLS = ("make", "docker", "kind", "kubectl", "argo")

requires_optin = pytest.mark.skipif(
    os.environ.get("RUN_CLUSTER_SMOKE") != "1"
    or not all(shutil.which(t) for t in _TOOLS),
    reason=(
        "opt-in destructive cluster smoke: set RUN_CLUSTER_SMOKE=1 (and have "
        f"{'/'.join(_TOOLS)} on PATH). Recreates the kind cluster."
    ),
)


def _make(*args: str, timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", *args], cwd=REPO_ROOT, text=True, capture_output=True, timeout=timeout
    )


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def _port_forward(service: str, remote: int) -> Iterator[str]:
    """Yield a localhost base URL forwarding to ``svc/<service>:<remote>``; clean up on exit."""
    local = _free_port()
    proc = subprocess.Popen(
        ["kubectl", "-n", NS, "port-forward", f"svc/{service}", f"{local}:{remote}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://localhost:{local}"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                httpx.get(f"{base}/", timeout=2)
                break
            except httpx.HTTPError:
                time.sleep(0.5)
        yield base
    finally:
        proc.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=10)


def _item_ids(base: str) -> list[str]:
    """Items in the collection, retrying briefly while the API settles after rollout."""
    url = f"{base}/collections/{COLLECTION}/items"
    deadline = time.monotonic() + 30
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=5)
            resp.raise_for_status()
            return [f["id"] for f in resp.json()["features"]]
        except httpx.HTTPError as exc:  # API may briefly 5xx right after rollout
            last = exc
            time.sleep(1)
    raise AssertionError(f"could not query {url}: {last}")


@requires_optin
def test_stage01_cold_smoke_within_budget() -> None:
    # Clean slate so the `make up` below is genuinely cold (fresh cluster, fresh ephemeral storage).
    _make("down", timeout=300)

    t0 = time.monotonic()
    up = _make("up", timeout=COLD_BUDGET_S)
    up_s = time.monotonic() - t0
    assert up.returncode == 0, f"`make up` failed:\n{up.stderr[-3000:]}"

    t1 = time.monotonic()
    # `argo submit --watch` exits non-zero if the workflow ends Failed, so a 0 here already proves
    # ensure-collection + ingest (fail-once -> retry -> success) all passed.
    demo = _make("demo", "STAGE=01", timeout=COLD_BUDGET_S)
    demo_s = time.monotonic() - t1
    if demo.returncode != 0:
        raise AssertionError(f"`make demo STAGE=01` failed:\n{(demo.stdout + demo.stderr)[-3000:]}")

    total_s = up_s + demo_s

    # pgSTAC on the path: the item is actually queryable in the logbook (not just workflow exit 0).
    with _port_forward("stac-api", 80) as stac_base:
        ids = _item_ids(stac_base)
    assert EXPECTED_ITEM in ids, f"{EXPECTED_ITEM!r} not registered in the logbook; got {ids}"

    print(
        f"\n[smoke] COLD rung-1: make up={up_s:.0f}s + demo={demo_s:.0f}s = {total_s:.0f}s "
        f"(cold budget {COLD_BUDGET_S}s; warm target {WARM_BUDGET_S}s)"
    )

    # THE CONTRACT. Do not weaken without explicit human approval (SPEC Boundaries / todo.md T15).
    assert total_s < COLD_BUDGET_S, (
        f"cold rung-1 took {total_s:.0f}s, over the {COLD_BUDGET_S}s budget — "
        f"decide (optimize vs. relax the claim) at Checkpoint C, do not silently absorb"
    )
