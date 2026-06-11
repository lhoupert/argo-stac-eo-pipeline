# argo-stac-eo-pipeline

> Companion repo for the FOSS4G Europe 2026 talk *"From Cron Job to Self-Healing Pipeline."*

A clone-and-run reference that walks the **maturity ladder** for Earth-observation data
ingestion — from a fragile cron job to a self-correcting pipeline — one independently
runnable stage at a time. The unit-of-work ingest function never changes across rungs;
only the orchestration around it grows.

See [`claude_docs/SPEC.md`](./claude_docs/SPEC.md) for the design and [`claude_docs/tasks/`](./claude_docs/tasks/) for the build plan.

## Status

🚧 Under construction (Phase 2). **Rungs 0–1 run end-to-end**; higher rungs (fan-out, the
self-healing logbook, observability) are in progress — see [`claude_docs/tasks/todo.md`](./claude_docs/tasks/todo.md).

## Dev quickstart

```bash
uv sync                      # install deps into .venv
uv run ruff check .          # lint
uv run pytest tests/unit     # fast offline tests
```

## Run the ladder (rungs 0–1)

```bash
make up                 # kind + MinIO + pgSTAC + STAC API + stac-browser + Argo  (one cluster)
make demo STAGE=01      # rung 1: the same image under Argo — watch it fail once, retry, succeed
make browse            # open stac-browser → the ingested item appears in the logbook
make ui                 # open the Argo UI → see the retried step
make down               # delete the cluster
```

Rung 0 (no Kubernetes) is `./stages/00-cron/run.sh`. Each rung has its own README.

### Cold/warm budget (rung 1) — the Success-Criteria contract

A fresh clone must reach a working rung 1, **with pgSTAC on the path**, within **< 15 min cold /
< 5 min warm**. Enforced by [`tests/integration/test_smoke_stage01.py`](./tests/integration/test_smoke_stage01.py)
(`make down → up → demo STAGE=01`, timed; opt-in via `RUN_CLUSTER_SMOKE=1` as it recreates the
cluster).

| Measured | `make up` | `make demo STAGE=01` | total |
|----------|-----------|----------------------|-------|
| 2026-06-10 | 113 s | 41 s | **153 s** |

**Caveat — be honest about "cold":** this is a cold *cluster* (fresh `kind`) but a **warm image
cache** (the MinIO / pgSTAC / stac-api / Argo images were already pulled). A truly pristine machine
also pays the one-time image pulls. Specs: **Apple M5, 10-core (4P+6E), 32 GB**. These are laptop
numbers, *not* a CI SLA — the **CI-runner budget is measured separately** in the kind-smoke job
(T23, pending).

## License

Apache-2.0 — see [`LICENSE`](./LICENSE).
