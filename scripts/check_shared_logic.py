#!/usr/bin/env python
"""Shared-logic invariant guard (T20).

The ladder's central teaching claim (AD-2): there is ONE unit of work, and every rung uses it
*unchanged* — only the orchestration around it grows. This script makes that claim enforceable
instead of aspirational. It fails (exit 1) if any of these hold:

  1. a stage **vendors/shadows** the package — any `.py` under `stages/` (the logic must live only
     in `src/eo_ingest`, never be copied into a rung);
  2. a stage workflow references an **image other than the one image** (`eo-ingest:dev`);
  3. `src/eo_ingest/ingest.py` has **drifted** from its frozen rung-1 form (byte hash).

Run locally or in CI: `python scripts/check_shared_logic.py`. Pure helpers take a repo root so the
checks are unit-tested both clean and against deliberate violations.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

# The single ingester image every rung must reference.
ONE_IMAGE = "eo-ingest:dev"

# Frozen rung-1 form of the unit of work. ingest.py is byte-stable from rung 1 (AD-2); if it must
# ever change, that is a deliberate, human-approved act — update this hash in the same commit.
EXPECTED_INGEST_SHA256 = "9f0742af9dd3a6ae327cf05a18d5ffb4eea60ddd0f1a72eecd01c67c65c1fd15"

_IMAGE_RE = re.compile(r"^\s*image:\s*([^\s#]+)", re.MULTILINE)


def vendored_modules(repo_root: Path) -> list[Path]:
    """Python files living under `stages/` — there should be none; logic belongs in the package."""
    return sorted((repo_root / "stages").rglob("*.py"))


def foreign_images(repo_root: Path) -> list[tuple[Path, str]]:
    """(`file`, `image`) for every stage workflow image reference that isn't the one image."""
    out: list[tuple[Path, str]] = []
    stages = repo_root / "stages"
    for yaml in sorted([*stages.rglob("*.yaml"), *stages.rglob("*.yml")]):
        for image in _IMAGE_RE.findall(yaml.read_text()):
            if image.strip("'\"") != ONE_IMAGE:
                out.append((yaml, image.strip("'\"")))
    return out


def ingest_drift(repo_root: Path) -> str | None:
    """A message if `ingest.py` is missing or no longer matches its frozen hash, else None."""
    path = repo_root / "src" / "eo_ingest" / "ingest.py"
    if not path.is_file():
        return f"ingest.py not found at {path.relative_to(repo_root)} — the unit of work is missing"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != EXPECTED_INGEST_SHA256:
        return (
            f"ingest.py drifted from its frozen rung-1 form (AD-2): "
            f"expected {EXPECTED_INGEST_SHA256[:12]}, got {actual[:12]}. "
            f"The unit of work must not change; if deliberate and human-approved, "
            f"update EXPECTED_INGEST_SHA256."
        )
    return None


def violations(repo_root: Path) -> list[str]:
    """All invariant violations as human-readable lines (empty list ⇒ clean)."""
    out: list[str] = []
    for module in vendored_modules(repo_root):
        out.append(f"stage vendors a module (shadows the package): {module.relative_to(repo_root)}")
    for yaml, image in foreign_images(repo_root):
        out.append(f"stage references a foreign image {image!r} (must be {ONE_IMAGE!r}): "
                   f"{yaml.relative_to(repo_root)}")
    drift = ingest_drift(repo_root)
    if drift:
        out.append(drift)
    return out


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    found = violations(repo_root)
    if found:
        print("✖ shared-logic invariant VIOLATED:")
        for line in found:
            print(f"  - {line}")
        return 1
    print(f"✓ shared-logic invariant holds: one image ({ONE_IMAGE}), no vendored logic, "
          f"ingest.py frozen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
