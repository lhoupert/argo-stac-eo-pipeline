# Contributing

Thanks for your interest! This is the companion repo for the FOSS4G Europe 2026 talk
*"From Cron Job to Self-Healing Pipeline."* It's a **teaching** repo — a maturity ladder for
Earth-observation ingestion — so contributions that make the ladder clearer, more reproducible, or
more honest are especially welcome.

By participating you agree to our [Code of Conduct](./CODE_OF_CONDUCT.md).

## Getting set up

```bash
uv sync                      # install deps into .venv (needs uv + Python 3.12)
uv run ruff check .          # lint
uv run pytest tests/unit     # fast offline tests (no cluster needed)
```

To run the cluster rungs you also need Docker, `kind`, `kubectl`, and `argo` — or just open the
repo in the [dev container / Codespace](./README.md#dev-container--codespaces), which ships them
pinned. To validate that container from a terminal (no editor), see
[`.devcontainer/README.md`](./.devcontainer/README.md).

## The one rule that matters most

**The unit of work never changes.** `src/eo_ingest/ingest.py` is byte-frozen from rung 1 (AD-2):
every rung runs the *same* image; only the orchestration around it grows, and the shared package
gains *new* capabilities (e.g. `logbook.py` grows `find_gaps` at rung 3). This is the repo's central
teaching device, and it is **enforced in CI** by `scripts/check_shared_logic.py`, which fails if:

- any stage vendors/shadows a module under `stages/`,
- any stage workflow references an image other than `eo-ingest:dev`,
- `ingest.py` drifts from its frozen hash.

If you have a genuine, human-approved reason to change `ingest.py`, update `EXPECTED_INGEST_SHA256`
in the same PR and say why.

## Repo shape

```
src/eo_ingest/     the shared, stable package (the unit of work + capabilities it grows)
stages/NN-name/    folder NN == rung N — orchestration only (workflows + README), no business logic
deploy/core/       plain, digest-pinned manifests for the local cluster
scripts/           dev/CI helpers (seed, shared-logic guard)
tests/unit/        fast, offline (mocked S3/STAC/Argo)
tests/integration/ cluster smokes (opt-in; recreate the cluster)
```

## Testing & quality bar

- **Unit tests** must stay green and ≥85% coverage (`uv run pytest tests/unit --cov=eo_ingest`).
- New logic comes with tests (TDD encouraged — see the adversarial `test_find_gaps.py` for the bar).
- **The contract layer** — `tests/integration/test_smoke_stage01.py` (cold/warm budget) — is **never
  weakened, skipped, or `xfail`'d without explicit human approval.** Extend it, don't relax it.
- Run `uv run python scripts/check_shared_logic.py` before pushing a stage change.

## Commits & PRs

- Conventional-ish prefixes: `build(TNN): …`, `fix(TNN): …`, `docs: …`.
- Explain **why**, not just what.
- One logical change per PR; keep the diff traceable to a task.

## Good first issues

Look for the [`good first issue`](https://github.com/lhoupert/argo-stac-eo-pipeline/labels/good%20first%20issue)
label. Good starting points: a stage README clarification, a troubleshooting entry, or a new
synthetic mission (it's pure data in `synthetic/world.py`).

## Questions

Open a [GitHub Discussion](https://github.com/lhoupert/argo-stac-eo-pipeline/discussions) rather than
an issue for questions, ideas, or "where does my pipeline sit on the ladder?" conversations.

## Governance

This repo is maintained by the talk's author. It's a teaching artifact, not a production framework,
so the roadmap follows the talk and its lessons. Decisions are made in the open via Issues and
Discussions; substantial changes to the ladder's structure are discussed before merge.
