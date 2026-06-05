# argo-stac-eo-pipeline

> Companion repo for the FOSS4G Europe 2026 talk *"From Cron Job to Self-Healing Pipeline."*

A clone-and-run reference that walks the **maturity ladder** for Earth-observation data
ingestion — from a fragile cron job to a self-correcting pipeline — one independently
runnable stage at a time. The unit-of-work ingest function never changes across rungs;
only the orchestration around it grows.

See [`claude_docs/SPEC.md`](./claude_docs/SPEC.md) for the design and [`claude_docs/tasks/`](./claude_docs/tasks/) for the build plan.

## Status

🚧 Early construction (Phase 0 — the shared core). Not yet runnable end-to-end.

## Dev quickstart

```bash
uv sync                      # install deps into .venv
uv run ruff check .          # lint
uv run pytest tests/unit     # fast offline tests
```

## License

Apache-2.0 — see [`LICENSE`](./LICENSE).
