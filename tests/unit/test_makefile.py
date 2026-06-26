"""Contract tests for the top-level Makefile (T13).

The Makefile is orchestration glue over `kind`/`kubectl`/`argo`, so its end-to-end behaviour
(`make up` -> cluster -> `make down`) is verified by a human running the real cycle. What we *can*
pin here, offline and without a cluster, is the Makefile's **decision logic**:

  * every target the plan promises actually exists;
  * `demo` refuses to run without a STAGE (no silent no-op);
  * the not-yet-built `prod` profile is guarded, not silently treated as `core`.

These guards run before any `docker`/`kind`/`kubectl` call, so the tests touch nothing external.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"

# The targets T13 promises (plus the helpers they lean on; `slides` joined in the T28 redesign —
# it bakes in `--theme-set`, so nobody renders the deck without the custom theme by accident).
PROMISED_TARGETS = [
    "help", "check", "up", "down", "ui", "browse", "status",
    "seed", "demo", "clean", "reset", "build", "slides",
]

requires_make = pytest.mark.skipif(shutil.which("make") is None, reason="`make` not on PATH")


def _make(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_makefile_exists() -> None:
    assert MAKEFILE.is_file(), "T13 requires a top-level Makefile"


@requires_make
@pytest.mark.parametrize("target", PROMISED_TARGETS)
def test_target_is_defined(target: str) -> None:
    # `-n` is a dry run: it expands and prints recipes but executes nothing, so no cluster is
    # touched. An undefined target makes `make` fail with "No rule to make target".
    result = _make("-n", target, "STAGE=01", "PROFILE=core")
    assert "No rule to make target" not in result.stderr, (
        f"target `{target}` is not defined:\n{result.stderr}"
    )
    assert result.returncode == 0, f"`make -n {target}` failed:\n{result.stderr}"


@requires_make
def test_demo_requires_stage() -> None:
    # No STAGE -> must fail loudly rather than silently submitting nothing.
    result = _make("demo")
    assert result.returncode != 0
    assert "STAGE" in (result.stdout + result.stderr)


@requires_make
def test_reset_runs_clean_then_seed() -> None:
    # `reset` is a convenience wrapper — it must drive both `clean` and `seed`, not reimplement.
    result = _make("-n", "reset")
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert "make clean" in out and "make seed" in out


@requires_make
def test_prod_profile_is_guarded() -> None:
    # The prod profile (T25) does not exist yet; `up` must refuse it, not silently run core.
    result = _make("up", "PROFILE=prod")
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "prod" in combined
