"""T20 — the shared-logic invariant guard.

The ladder's core promise (AD-2): there is ONE unit of work, used unchanged by every rung. This
guard fails CI if a stage ever vendors/shadows the package, points at a different image, or if
`ingest.py` drifts from its frozen rung-1 form. Tested both ways — clean repo passes, each kind of
deliberate violation is caught.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_shared_logic import (  # noqa: E402
    ONE_IMAGE,
    foreign_images,
    ingest_drift,
    vendored_modules,
    violations,
)


def test_the_real_repo_is_clean() -> None:
    assert violations(REPO_ROOT) == []


def _make_stage(root: Path, name: str) -> Path:
    d = root / "stages" / name / "workflows"
    d.mkdir(parents=True)
    return d


def test_vendored_python_module_in_a_stage_is_caught(tmp_path: Path) -> None:
    _make_stage(tmp_path, "01-x")
    (tmp_path / "stages" / "01-x" / "ingest.py").write_text("# a forbidden copy of the unit\n")
    found = vendored_modules(tmp_path)
    assert any(p.name == "ingest.py" for p in found)
    assert violations(tmp_path)  # surfaced as a violation


def test_foreign_image_reference_is_caught(tmp_path: Path) -> None:
    wf = _make_stage(tmp_path, "01-x") / "w.yaml"
    wf.write_text("spec:\n  template:\n    container:\n      image: patched-ingest:dev\n")
    bad = foreign_images(tmp_path)
    assert bad == [(wf, "patched-ingest:dev")]


def test_the_one_image_is_not_flagged(tmp_path: Path) -> None:
    wf = _make_stage(tmp_path, "01-x") / "w.yaml"
    wf.write_text(f"      image: {ONE_IMAGE}\n")
    assert foreign_images(tmp_path) == []


def test_ingest_drift_is_caught(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "eo_ingest"
    pkg.mkdir(parents=True)
    (pkg / "ingest.py").write_text("# tampered\n")
    assert ingest_drift(tmp_path) is not None
    assert any("ingest.py" in v for v in violations(tmp_path))
