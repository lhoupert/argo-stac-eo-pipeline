# argo-stac-eo-pipeline

> Companion repo for the FOSS4G Europe 2026 talk *"From Cron Job to Self-Healing Pipeline."*

A clone-and-run reference that walks the **maturity ladder** for Earth-observation data
ingestion — from a fragile cron job to a self-correcting pipeline — one independently
runnable stage at a time. The unit-of-work ingest function never changes across rungs;
only the orchestration around it grows.

See [`claude_docs/SPEC.md`](./claude_docs/SPEC.md) for the design and [`claude_docs/tasks/`](./claude_docs/tasks/) for the build plan.

## The ladder

Folder number == rung number. Each rung is independently runnable and adds **one** idea — the
ingest function is identical throughout; only the orchestration grows.

| Rung | Stage | What's new | The lesson |
|------|-------|-----------|------------|
| **0** | `00-cron` | a laptop `crontab` → `docker run` (no Kubernetes) | fragile: nowhere to look at 3 am |
| **1** | `01-argo-retries` | the same image under Argo + a STAC **logbook** | retries turn a lost day into a recovered one; you can finally *look* |
| **2** | `02-fanout` | capped parallel backfill (`withItems`) | go fast **politely** — measured ~6× here |
| **3** | `03-stac-logbook` | the logbook drives repair (`find_gaps`) | the system detects its own gaps and refills them |
| **4** | `04-observability` | a daily report (Argo API + gap heatmap) | make the self-healing **visible** |

> rung 5 isn't a folder — it's `make up PROFILE=prod` (eoAPI / titiler / Grafana), "where the
> ladder leads."

**Two levels of self-correction** fall out for free: an *item* that fails is **retried** (rung 1),
and a *day* that's missing is **detected and refilled** (rung 3).

## Status

✅ **Rungs 0–4 run end-to-end** on a local `kind` cluster. Polish & release work (full CI, prod
profile, real-data example, slides) is in progress — see [`claude_docs/tasks/todo.md`](./claude_docs/tasks/todo.md).

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

### Dev container / Codespaces

A [`.devcontainer`](./.devcontainer/) ships everything to run the ladder — `uv`, `kind`,
`kubectl`, `argo`, and Docker-in-Docker — pinned to the versions the cluster runs. "Reopen in
Container" (VS Code) or open the repo in a GitHub Codespace and you get a maintainer-equivalent
environment.

**Honest sizing** (the cluster rungs are not free-tier-sized):

| Environment | What runs |
|-------------|-----------|
| Free Codespace / 2-core, 4 GB | **Rung 0 only** (`./stages/00-cron/run.sh` — plain `docker run`, no Kubernetes) |
| 4-core, 8 GB+ | The **full ladder** (`make up` → rungs 1–4): kind + MinIO + pgSTAC + STAC API + Argo |

Rung 0 exists precisely so the entry point works on the smallest tier; the cluster appears at
rung 1, where you need the bigger machine.

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

## Footprint — core vs. prod

The **core** profile is the lightest thing that demonstrates each rung; the **prod** profile
(`make up PROFILE=prod`) swaps in the production-grade stack, running the *same* workflows unchanged.

| | Core (default) | Prod (`PROFILE=prod`) |
|--|----------------|------------------------|
| STAC API | bare `stac-fastapi-pgstac` + one Postgres pod | eoAPI (`eoapi-k8s` Helm) |
| Tiles / coverage | — | titiler-pgstac |
| Dashboards | the rung-4 markdown report | + Grafana (AGPL) |
| Install | plain digest-pinned manifests | Helm |
| Target machine | **4-core / 16 GB "average laptop"** (rung 0 runs on a 2-core free tier) | more |

CI-runner timings are measured separately from laptop numbers (see the cold/warm budget above).

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `make demo` runs the **old** code | the in-cluster image is stale — `make rebuild` (force build + `kind load`) |
| `NoSuchBucket` / wrong endpoint from a host script | an ambient `S3_BUCKET` / `S3_ENDPOINT_URL` in your shell leaked in — the `make` targets pin their own env; if running a script directly, unset those or set them explicitly |
| stac-browser shows items but **blank previews** | thumbnail hrefs are `s3://…`, which a browser can't fetch (tracked follow-up); the item metadata is correct |
| `make up` slow on first run | one-time image pulls; subsequent runs are warm |
| pgSTAC pod slow to become Ready | first boot runs the pgSTAC migration (the startup probe allows ~5 min) |
| `make demo STAGE=NN` says "no stage matching" | that rung isn't built yet, or you mistyped the number (folder `NN-name`) |

### Windows / WSL2

Run everything inside **WSL2** (Ubuntu) with Docker Desktop's WSL2 backend — `kind` needs a Linux
Docker daemon. Clone the repo *inside* the WSL2 filesystem (`~/…`, not `/mnt/c/…`) for sane file
performance, then follow the Linux quickstart. The dev container / Codespace avoids this entirely.

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) and our [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md).
Questions and "where's my pipeline on the ladder?" chats go in
[Discussions](https://github.com/lhoupert/argo-stac-eo-pipeline/discussions).

## License & attribution

Code is Apache-2.0 — see [`LICENSE`](./LICENSE). The synthetic imagery is generated (not real
observations), licensed CC-BY-4.0. The optional real-data example uses **Sentinel-2** via
[Earth Search](https://earth-search.aws.element84.com/v1); Copernicus Sentinel data are free and
open under the [Copernicus terms](https://sentinels.copernicus.eu/web/sentinel/terms-conditions) —
attribute "contains modified Copernicus Sentinel data [year]".
