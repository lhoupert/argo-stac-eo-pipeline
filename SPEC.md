# Spec: "From Cron Job to Self-Healing Pipeline" — Talk + Companion Repo

FOSS4G Europe 2026 · 30-minute talk + open-source companion project.
**Repo name:** `argo-stac-eo-pipeline`

---

## Objective

**Two coupled deliverables that tell one story.**

1. **The talk (30 min):** Teach the *maturity ladder* for EO data ingestion — how you climb from a fragile cron job to a system you can run unsupervised — and make concrete **what Argo Workflows buys you at each rung**. The primary takeaway is conceptual: the audience should be able to locate their own pipeline on the ladder and know the next rung to climb.

2. **The companion repo:** A clone-and-run reference that mirrors the talk as **progressive, independently runnable stages**. It exists so an attendee can go home, `git clone`, `make up`, and *walk the same ladder* on their laptop — no cloud account, no bill.

**Design principle — minimal by default, prod-like as the payoff.** The core stack is the lightest thing that demonstrates each rung (plain Kubernetes manifests, single-replica services, no Helm on the critical path). A separate **prod-like profile** layers in the production-grade components (eoAPI Helm chart, titiler, stac-browser, Grafana) and is shown as the *final* step — "here's where the ladder leads," not a prerequisite for walking it.

**Who it's for:** Intermediate practitioners — comfortable with Python and Docker, *not* assumed to know Argo or STAC. EO/geospatial engineers, data platform engineers, research-software engineers who run scheduled data pipelines.

**What success looks like:**
- Talk: an audience member can draw the ladder from memory and name what Argo adds at retries → fan-out → logbook → observability.
- Repo: a fresh clone reaches a working **stage-1** demo **fast** (see the cold/warm budget below) on a laptop, and each later stage diffs cleanly against the previous one so the *delta* is the lesson.
- The **`ingest`-one-unit function never changes** across stages — only the *orchestration around it* grows, and the shared package gains *new* capabilities (rung 3 adds `logbook.py`). This precise wording matters: a careful viewer who sees a new module appear while you claim "identical code!" feels a seam. The honest, defensible claim — matched to the CI shared-logic invariant — is "the unit-of-work function is untouched; the package grows." (This is the repo's central teaching device.)

**Clone-and-run time budget (explicit, measured):**
- **"Average laptop" is defined**, not hand-waved: a **4-core / 16 GB** machine, stated for both core and prod profiles in the README. The budget below is for the *core* profile.
- **Stage-1, cold** (first run; images must be pulled): target **< 15 min**. Stage-1 = rung 1 = `stages/01-argo-retries` — the first *cluster-based* rung (rung 0 / `stages/00-cron` needs no cluster). It depends only on Argo + the ingester image + MinIO — the STAC API is **not** on its critical path.
- **Stage-1, warm** (images cached from a prior run): target **< 5 min**.
- **CI time ≠ laptop time.** CI's kind smoke test records elapsed time, but a GitHub runner is not "an average laptop." The README states the **runner specs** next to the laptop target and adds at least one **real-laptop anecdote**. A **Windows/WSL2** note sits alongside the Apple-Silicon one — FOSS4G has many Windows/QGIS users, not just macOS.

---

## The Talk

### Narrative spine: the maturity ladder

| Rung | State | What Argo buys you |
|---|---|---|
| 0 | Plain cron + Python script | (baseline — you are the only one watching) |
| 1 | Argo CronWorkflow | Retries, web UI showing the failed step, full logs — *for free*, script unchanged |
| 2 | Fan-out backfill | Parallelism (`withItems`/`withParam`); days that took a week run in minutes |
| 3 | STAC as logbook | Idempotency + **gap detection**; the catalog knows what's ingested and what's missing |
| 4 | Observability | Daily reports + metrics; systemic error periods surface for humans |
| 5 (optional) | Prod-like deployment | The same ladder on real components: eoAPI, titiler, stac-browser, Grafana |

**Two levels of self-correction (the closing payoff):**
- *Item level:* failed items are re-ingested automatically via STAC gap detection.
- *System level:* error-rate anomalies surface in daily reports for human intervention.

> **Note on "across missions":** the talk's hook frames EO ingestion as multi-mission. The local seed honours this with **two small synthetic collections** (two pseudo-missions), so gap detection and fan-out are shown operating *per collection*, not against a single stream.

### Time budget (≈26½ min content + ~3½ min live Q&A)

**Pacing principle (per audience review):** go *deep* on rungs 1–3 (retries, fan-out, logbook — the heart of the talk); treat rungs 4–5 as "and it keeps climbing"; reclaim real time for **live Q&A**. The positioning question ("why Argo, not Airflow?") is the most likely Q&A opener, so it gets its own short slot rather than being left to chance.

| Time | Section | Visual |
|---|---|---|
| 0:00–3:00 | **Hook & problem + two promises.** Analysis-ready EO starts *before* the algorithm; reliable ingestion across missions + multi-year backfill is the hard, unglamorous foundation. **Promise 1:** "You do **not** need to know Kubernetes to follow this talk — you need Docker to run the repo." **Promise 2:** disambiguate — this is **Argo *Workflows***, not Argo CD. | Title + "what could go wrong" + the two-promise slide |
| 3:00–5:00 | **Rung 0 — the *actual* cron job.** A plain `crontab` line running `python -m eo_ingest.ingest` on a laptop — no Kubernetes. What it *can't* tell you when it fails at 3am. This is the honestly-fragile baseline the talk is named after. | Code on slide (laptop crontab) |
| 5:00–10:00 | **Rung 1 — Argo CronWorkflow.** Same ingest function, now wrapped. Retries, UI, logs — "you're not the only one watching anymore." The 0→1 delta is *laptop crontab → Argo*. | **Clip: Argo UI, a failed step, the retry** |
| 10:00–15:00 | **Rung 2 — fan-out backfill.** Sequential backfill took days; fan-out (`withItems`/`withParam`) parallelizes it. | **Clip: the fan-out graph** |
| 15:00–21:00 | **Rung 3 — STAC as logbook (the heart).** Write ingested items back to STAC; query it to find gaps; ingest only what's missing. Idempotent + self-correcting at item level. | **Clip: gap query → targeted re-ingest** |
| 21:00–23:30 | **Rung 4 — observability (it keeps climbing).** Daily report + the two-level self-*correction* (item-level automatic vs. system-level surfaced-for-a-human). Coverage map / Grafana = prod profile, shown only if time allows. | **Clip: daily report → gaps closing** |
| 23:30–25:00 | **Why Argo, and how this differs.** One honest slide: the ladder is orchestrator-*agnostic*; Argo specifically buys K8s-native container-per-step, no separate scheduler DB, first-class fan-out. Related work named (cirrus-geo, stac-task/stactools, VEDA); our differentiator is *pedagogical* (the ladder + clone-and-run), not "a better framework." **openEO** standardizes *processing* APIs — complementary, this talk is about *ingestion orchestration*. | Positioning + related-work slide |
| 25:00–26:30 | **Recap + real-EO proof.** The ladder ("here's where you are; here's the next rung"), a 20-second "…and here it is on **real Sentinel-2** via Earth Search" moment, the prod path (`PROFILE=prod`), and the repo. | Ladder slide + Sentinel-2 still + QR code |
| 26:30–30:00 | **Live Q&A** (~3.5 min reclaimed). | — |

### Demo strategy
- **Pre-recorded screencasts**, embedded in slides — zero live-demo risk on conference wifi/projector. Record them *from the companion repo* so what's on screen is exactly what attendees will clone.
- Keep each clip ≤ 60–90s, captioned, no audio dependency.
- **Deck format (resolved):** the presented deck is **HTML (Marp HTML)** so the embedded clips actually play; a **PDF is rendered in CI as a static fallback** only. A PDF deck cannot play video, so it must never be the primary artifact.
- **Clip format (resolved):** clips are **animated GIF/APNG**, not mp4 — they play inline in the README, on GitHub, and in the HTML deck, and degrade to a clean still frame in the PDF fallback, with **no codec/audio dependency** (clips are already silent + ≤90s).
- **Reproducible clip generation (resolved):** pair `make_screencast_data.py` (seed state) with *scripted recording* so anyone can regenerate clips and they match the repo — **VHS or asciinema** for terminal clips, **Playwright** for Argo-UI clips. A **scheduled (cron) CI run** of the kind smoke test surfaces version drift to the maintainer before it bites an attendee six months out.
- **Deterministic failure injection:** the rung-1 retry clip needs a reproducible fail-then-succeed. Provide a documented knob — **`FAIL_ONCE=1`** (inject one transient error, then succeed) — so the retry clip is re-recordable.
- Have the repo open in a backup tab in case of live questions, but never depend on a live cluster.
- **UI parity:** the minimal Argo install must expose the same web UI shown in the screencasts. Pin the install manifest and verify the UI a cloner gets matches the recording (see Tech stack).

### Positioning, related work & framing (pre-empt the Q&A)

The "we built a pipeline" genre is crowded; naming the neighbours *raises* credibility and defuses the obvious questions before they land on stage.

- **vs. other orchestrators (Airflow / Prefect / Dagster).** The ladder is orchestrator-*agnostic*. What Argo *specifically* buys: Kubernetes-native, container-per-step, no separate scheduler database, first-class fan-out (`withItems`/`withParam`). Airflow is more common in data engineering — say so honestly.
- **vs. STAC-pipeline prior art (cirrus-geo, stac-task / stactools, VEDA ingestion, Element84 / Earth Search tooling).** These solve adjacent problems. Our differentiator is **pedagogical, not "a better framework"** — the maturity ladder + clone-and-run teaching device. State that plainly; the repo is a *teaching* artifact.
- **vs. openEO** (it's a *European* conference — Copernicus/openEO is in the room): openEO standardizes *processing* APIs; this is *ingestion orchestration*. Complementary, not competing — one line.
- **Ingestion vs. ARD (scientific credibility).** The hook is "analysis-ready EO starts *before* the algorithm," but the demo stops at *ingestion*. Name where ingestion ends and ARD begins (cloud masking, reprojection, COG validation, datacube generation) — and that the *orchestration* lessons apply equally to those steps. Pre-empts "you stopped before the hard part."
- **Decision-maker ROI (optional slide).** Some attendees are team leads choosing tooling. One "what this saves you" line — unattended runs, faster backfill, fewer 3am pages — gives them ammunition to justify adopting Argo internally.
- **CfP framing.** The abstract should lead with the **ladder + clone-and-run teaching device** (the genuinely novel part), not the stack, and confirm EO / cloud-native-geo track fit.

### Accessibility & inclusion (OSGeo/FOSS4G values this)

- **Don't encode meaning by colour alone** — the ladder and fan-out diagrams use a **colour-blind-safe palette** plus shape/label for rung and status.
- **Legible from the back row and on a 4:3 projector** — generous contrast and font sizes; code slides large enough to read. The `find_gaps` sample won't fit legibly at full size — show a **trimmed** version on the slide, full version in the repo.
- **Low jargon budget** for the GIS-not-DevOps slice — expand "fan-out", "idempotent", "CRD" on first use.
- Clips are **captioned** (already required) and silent (no audio dependency).

---

## Companion Repo

### Tech stack

The **core (default)** column is what `make up` installs — minimal, plain-manifest, single-replica. The **prod-like** column is what `make up PROFILE=prod` adds.

| Concern | Core (default) | Prod-like profile | Notes |
|---|---|---|---|
| Orchestrator | **Argo Workflows** minimal quick-start manifests (pinned, ~v3.6.x) | same | Kubernetes-native; the UI/retries are the point. UI must be exposed in the minimal install. |
| Local Kubernetes | **kind** (vanilla upstream K8s) | same | Vendor-neutral, prod-fidelity; single cluster for *everything* |
| STAC API + catalog | **bare `stac-fastapi-pgstac` + pgSTAC** (single Postgres pod, plain manifests) | **eoAPI** via `eoapi-k8s` Helm chart | Core keeps it light & fast; prod profile shows the real, batteries-included stack |
| Tiles / coverage map | — (skipped in core) | **titiler-pgstac** | Coverage map is a *nice-to-have* at rung 4; lives in the prod profile |
| STAC browser | — (skipped in core) | **stac-browser** | Prod profile only |
| Object store (S3) | **MinIO** single-container Deployment (plain manifest) | MinIO (Helm) | S3-compatible sink, fully local in both |
| Reporting / metrics | **daily-report Job querying the Argo Workflows API** (workflow statuses); **workflow archive enabled** on the existing Postgres for history | + **Prometheus scrape + Grafana** for the `/metrics` error-rate dashboard | See "Rung-4 data source" below — core needs no Prometheus; the error-rate *dashboard* is prod-only |
| Ingestion language | **Python 3.12** | same | The business logic that stays *unchanged* across stages |
| STAC client | **pystac-client**, **pystac** | same | Query source + write to logbook |
| S3 client | **boto3** | same | Talks to MinIO via in-cluster DNS; one boring, well-understood client |
| Packaging | **uv** | same | Fast, reproducible; `uv.lock` committed |
| Lint/format | **ruff** | same | Lint + format in one tool |
| Tests | **pytest** (+ **moto** for S3, responses/respx for STAC) | same | Unit fast & offline; integration against kind |
| Build | **Docker** (multi-arch: amd64 + arm64) | same | Single ingester image, reused by every stage. **Apple Silicon must work.** |
| Task runner | **Make** | same | Most universal; `make up/demo/down` |
| CI | **GitHub Actions** | same | Lint, test, `argo lint`, build+scan digest-pinned multi-arch image, kind smoke test (timed), build the **devcontainer image**, render Marp **HTML deck + PDF fallback**; a **scheduled** smoke run catches drift |

**Single-cluster design (no compose split):** Argo + STAC + MinIO all live in one kind cluster. Workflow pods reach services by in-cluster DNS (`http://stac-api`, `http://minio:9000`) — no host-networking gymnastics. Docker-compose is explicitly **not** used for the pipeline, because Argo requires a Kubernetes API.

**Why bare manifests in core (not Helm):** the eoAPI `eoapi-k8s` chart is the heaviest dependency and the one most exposed to chart/CRD/K8s-version drift over time — i.e. the thing most likely to break a clone-and-run six months out. The core demo therefore uses pinned plain-manifest `stac-fastapi-pgstac` + a single pgSTAC Postgres, which installs in seconds and has almost no moving parts. The full eoAPI chart is preserved as the **prod-like profile** so the audience still sees the production-grade stack — just not on the critical path to walking the ladder.

**Multi-arch:** every pinned image (Argo, stac-fastapi-pgstac, Postgres/pgSTAC, MinIO, titiler) must have amd64 **and** arm64 variants, and the ingester image is built multi-arch in CI. Apple Silicon is a first-class target; an arch gap is a classic "works on my laptop" trap and is treated as a release blocker.

### Progressive stages (each independently runnable)

```
stages/00-cron/          Plain host crontab + `python -m eo_ingest.ingest`. NO Kubernetes. The honestly-fragile baseline.
stages/01-argo-retries/  Same ingest function, Argo CronWorkflow. First rung that needs kind. Retries, UI, logs.
stages/02-fanout/        Argo fan-out (withItems/withParam) for parallel backfill.
stages/03-stac-logbook/  Write items to STAC; query gaps; ingest only missing. Idempotent.
stages/04-observability/ Daily report + Argo API; 2-level self-correction. Coverage map = prod profile.
```

**Folder number == rung number.** `stages/0N` is rung `N` (00 = rung 0 … 04 = rung 4); rung 5 (prod-like) is a deployment profile, not a folder. This keeps the talk's ladder and the repo's folders in lockstep — no off-by-one to translate.

**Rung 0 is deliberately *not* Kubernetes (resolved per review).** `stages/00-cron/` is a plain `crontab` entry invoking `python -m eo_ingest.ingest` directly on the host — no kind cluster, no manifests. This keeps the talk's title (*From Cron Job…*) honest: the audience sees the truly fragile thing (a laptop crontab with nowhere to look when it fails), and the **0→1 delta is genuinely "laptop crontab → Argo,"** not "K8s CronJob → CronWorkflow." It also means the very first rung has *zero* Kubernetes barrier — kind is first required at **stage 01**.

Each stage folder contains its own orchestration (stage 00: a documented `crontab` line + run script; stages 01+: `workflows/*.yaml`), a `README.md` ("what's new vs. previous rung"), and any stage-specific config. The **`src/eo_ingest`** package is shared and stable — stages add orchestration, not new business logic.

**The prod-like deployment is a profile, not a code stage (resolved).** It is the same workflows pointed at the eoAPI/titiler/stac-browser/Grafana stack via `make up PROFILE=prod`, plus a short appendix README — a deployment swap ("where the ladder leads"), not a sixth rung. This keeps the staged folders as the orchestration-delta rungs of the ladder.

### Project structure

```
.
├── SPEC.md                     # this file
├── README.md                   # the ladder, narrated; quickstart; cold/warm timings; footprint; QR target
├── LICENSE                     # Apache-2.0
├── CONTRIBUTING.md             # so attendees can adopt/extend
├── CODE_OF_CONDUCT.md
├── .devcontainer/              # toolchain (uv/kubectl/kind/argo + docker-in-docker); local "reopen in container" + optional Codespaces on-ramp
│   ├── devcontainer.json
│   └── Dockerfile
├── Makefile                    # up / demo / down / lint / test (PROFILE=core|prod)
├── pyproject.toml              # uv project
├── uv.lock
├── Dockerfile                  # the ingester image (one image, all stages, multi-arch)
│
├── src/eo_ingest/              # SHARED, STABLE business logic — ONE copy, no Argo import
│   ├── __init__.py
│   ├── stac_source.py          # query a STAC API for items in a date/bbox window
│   ├── logbook.py              # read/write the STAC catalog; gap detection
│   ├── download.py             # fetch assets -> MinIO/S3 (idempotent, checksummed)
│   ├── ingest.py               # orchestrate one unit of work (one day / one item)
│   └── config.py               # env-driven settings (endpoints, creds, collection)
│
├── stages/                     # folder NN == rung NN (00–04); rung 5 is the prod profile, not a folder
│   ├── 00-cron/                # host crontab + run script + README (NO K8s) — the rung-0 baseline
│   ├── 01-argo-retries/
│   ├── 02-fanout/
│   ├── 03-stac-logbook/
│   └── 04-observability/
│
├── deploy/                     # the single-cluster local stack
│   ├── kind-cluster.yaml
│   ├── core/                   # DEFAULT: plain manifests — Argo (minimal), bare stac-fastapi-pgstac+pgSTAC, MinIO
│   │   ├── argo/
│   │   ├── stac/               # stac-fastapi-pgstac Deployment + pgSTAC Postgres + Service
│   │   └── minio/              # MinIO Deployment + Service + bucket bootstrap
│   └── prod/                   # PROFILE=prod: eoapi-k8s Helm values, titiler, stac-browser, optional Grafana
│       ├── eoapi/
│       ├── minio/
│       └── grafana/            # optional
│
├── scripts/
│   ├── seed_stac.py            # seed TWO deterministic local collections WITH intentional gaps
│   └── make_screencast_data.py # reproducible state for recording clips
│
├── examples/
│   └── real-sentinel2/         # OPTIONAL: ingest real sentinel-2-l2a via Earth Search (single band, tiny bbox)
│
├── tests/
│   ├── unit/                   # offline: mocked STAC + moto S3
│   └── integration/            # against the live kind cluster (CI-gated)
│
├── docs/
│   ├── ladder.md               # the maturity table, expanded
│   ├── architecture.md         # the single-cluster diagram (core + prod profiles)
│   └── slides/                 # Marp markdown deck (HTML primary + PDF fallback rendered in CI)
│       ├── talk.md             # the deck, version-controlled + diffable
│       └── screencast-scripts.md
│
└── .github/workflows/ci.yml
```

### Commands

```bash
# Local stack lifecycle
make up                 # create kind cluster + install the CORE stack (Argo minimal, bare STAC, MinIO); bootstrap buckets
make up PROFILE=prod    # same cluster, but install the prod-like stack (eoAPI Helm, titiler, stac-browser, Grafana)
make seed               # seed local STAC with TWO deterministic collections (with gaps)
make demo STAGE=01      # submit the CronWorkflow/Workflow for a given stage (01 = rung 1, Argo retries)
make ui                 # port-forward the Argo UI (https://localhost:2746)
make down               # tear everything down

# Dev loop
uv sync                 # install deps from uv.lock
uv run ruff check .     # lint
uv run ruff format .    # format
uv run pytest tests/unit            # fast offline tests
uv run pytest tests/integration     # against running kind cluster
argo lint stages/**/workflows/*.yaml  # validate workflow manifests
docker build -t eo-ingest:dev .       # build the shared ingester image

# Optional real-data example
make demo-real BBOX=... DATETIME=...   # ingest real Sentinel-2 via Earth Search (single band, tiny bbox)
```

### Code style

Python 3.12, `ruff`-formatted, full type hints, small pure functions where logic is testable. Business logic is decoupled from Argo so it runs standalone (`python -m eo_ingest.ingest`) *and* inside a workflow pod — that decoupling is what lets the same code survive every rung.

> **Note on cadence (per review):** real Sentinel-2 / Landsat has *legitimate* gaps — revisit cycles, no acquisition, cloud masking — so production gap detection models **acquisition cadence**, not calendar days. The demo uses **daily cadence for clarity**, and the talk/slide names this simplification *before* a STAC-literate audience does. The function below is illustrative; it guards the real-world STAC edge cases but the query is intentionally bounded for the demo (no pagination loop).

```python
# src/eo_ingest/logbook.py
from datetime import date, datetime, timedelta
from pystac import Item
from pystac_client import Client

def _item_date(item: Item) -> date | None:
    """Best-effort acquisition date for a STAC item.

    Top-level `datetime` can legitimately be null when an item uses the
    `start_datetime`/`end_datetime` range form — both are valid STAC. Fall
    back to `start_datetime` and skip items we genuinely can't date.
    """
    dt = item.datetime or item.common_metadata.start_datetime
    return dt.date() if isinstance(dt, datetime) else None

def find_gaps(
    catalog: Client,
    collection: str,
    start: date,
    end: date,
) -> list[date]:
    """Return the days in [start, end] with no item in the logbook.

    The STAC catalog *is* the source of truth for what's been ingested.
    Gap detection here is: expected days minus present days — idempotent and
    self-correcting at the item level. NOTE: daily cadence is a teaching
    simplification (see cadence note above); the search is bounded for the
    demo (a production logbook would page through results).
    """
    present = {
        d
        for item in catalog.search(
            collections=[collection],
            datetime=f"{start.isoformat()}/{end.isoformat()}",
            max_items=10_000,  # bounded for the demo, not a production paginator
        ).items()
        if (d := _item_date(item)) is not None
    }
    expected = (start + timedelta(days=i) for i in range((end - start).days + 1))
    return [day for day in expected if day not in present]
```

### Testing strategy

Tests are organised by **boundary**, and the boundary determines who may change them. This matters in an AI-assisted workflow: unit tests are freely editable, but the acceptance layer is a contract — it encodes what the demo *promises* an attendee, and must not be weakened to make a build pass.

- **Unit (`tests/unit`)** — fast, offline, the default gate. Mock the source STAC (responses/respx) and S3 (moto). Cover the logic that *matters*: gap detection, idempotent download (re-running ingests nothing new), checksum/completeness validation, config parsing. Freely editable as logic evolves.
- **Adversarial (`tests/unit`, called out separately)** — inputs that actively try to break the EO assumptions, because a STAC-literate audience *will* hit them:
  - item with **null top-level `datetime`** but `start_datetime`/`end_datetime` set → dated via the fallback, **never crashes** (this is the edge case already hard-coded in `_item_date`; it must have a test, not just a guard);
  - item with **neither** datetime form → skipped with a warning, not a crash;
  - **duplicate item ids / re-run** → idempotent: no double-count in `find_gaps`, no duplicate object in MinIO;
  - **partial or corrupt download** (truncated asset / checksum mismatch) → re-fetched, never silently accepted as complete;
  - **`find_gaps` boundaries** → empty collection and a fully-backfilled range both return `[]`; the `max_items` bound is exercised so the demo limit is explicit, not accidental.
- **Integration (`tests/integration`)** — against the live kind cluster: submit a workflow, assert items land in MinIO and appear in the STAC catalog. CI-gated (slower). Assumptions in these tests get reviewed, not rubber-stamped.
- **Acceptance / contract (CI smoke test + checked Success Criteria)** — the executable expression of the **Success Criteria** and the cold/warm budget: a fresh `make up && make seed && make demo STAGE=01` reaches a working rung-1 demo within the timed budget, and the gap-closing demonstration actually closes gaps. **This layer is the contract** — per *Boundaries → Never*, it is not weakened, skipped, or `xfail`'d without explicit human approval. AI-generated changes may *extend* it but not relax it.
- **Manifest validation** — `argo lint` on every stage's YAML in CI.
- **Shared-logic invariant** — a CI check asserting that **no stage folder vendors, patches, or shadows `src/eo_ingest`**: the ingester image is built once and every stage's workflow references that same image/package. (This is the real "the code didn't change" guarantee — see Success Criteria.)
- **Coverage** — meaningful coverage of `src/eo_ingest` (target ≥ 85% on the package); orchestration YAML covered by the integration smoke test, not line coverage. Coverage is a floor, not the goal — the adversarial cases above matter more than the percentage.

### Backfill speedup demo (rung 2)

The "fan-out is faster than sequential" claim is demonstrated **against the local seed with a configurable injected per-item latency** (`INGEST_SLEEP ≈ 2s/item`, over a ~30-item window, fan-out parallelism cap ≈ 10 — see the resolved tuning below) that simulates real network/IO cost. Because the latency is IO-wait (sleeping pods yield CPU), the win shows even on a 4-core laptop. This keeps the before/after **reproducible and deterministic** while staying polite (no hammering a public API). The numbers are recorded in the stage-02 README and re-derived in CI. The real Earth Search example shows *genuine* latency but is **not** the benchmark — it is variable and rate-limited by design.

### Stage 5 scope — core vs. nice-to-have

Rung 4 is the most feature-dense and least-rehearsed slot, so its scope is tiered to degrade gracefully:
- **Core (must ship, runs in the default stack):** daily report (stdout + markdown artifact) and the gap-closing demonstration (gaps detected → re-ingested → report shows them closing). This is enough to land the two-level self-correction message.
- **Nice-to-have (prod profile; shown only if time/laptop allows):** the **error-rate dashboard** (Prometheus scraping Argo's `/metrics` → Grafana), titiler-pgstac coverage map, stac-browser.

#### Rung-4 data source (resolved — was the one open architectural ambiguity)

The previous draft said rung 4 "leans on Argo's built-in Prometheus metrics" in the *core* profile. That had a hidden dependency: Argo's metrics are only a `/metrics` endpoint — *something* must scrape and query it (Prometheus), which core deliberately does not run; and a report *over history* needs Argo's **workflow archive**, which the minimal quick-start install does not enable (live Workflow CRDs are GC'd). Resolution:

- **Core daily report reads the Argo Workflows API directly** (`/api/v1/workflows`, workflow statuses) — no Prometheus required. For history beyond live, not-yet-GC'd workflows, we **enable Argo's workflow archive backed by the Postgres we already run for pgSTAC** (one database, two schemas; no new component on the critical path). If a cloner skips the archive, the report degrades gracefully to "last N live workflows."
- **The Prometheus/Grafana error-rate *dashboard* moves to `PROFILE=prod`** — that's where a scraper exists. The two-level self-correction *message* is fully carried by the core daily report; the dashboard is the prod-profile flourish.

### Security & threat model

The repo asks potentially thousands of people to `kubectl apply` pinned manifests and port-forward the Argo UI — that is a trust act, and the demo should *teach* good hygiene, not bad.

- **Argo Server auth mode is stated explicitly.** The quick-start install commonly ships with auth effectively disabled; the port-forwarded UI must **not** become a teach-by-example unauthenticated control plane. One line in the README: "this is local-only; here's how you'd secure it in prod."
- **Workflow ServiceAccount RBAC is least-privilege**, documented — *never* `cluster-admin`. Copy-paste RBAC is how clusters get owned.
- **Supply chain:** pin images by **`sha256` digest** (not just moving tags), and **scan the ingester image in CI**. Asking people to apply your manifests means owning what's in them.

### Licensing & provenance

- **Pin by digest, not tag.** "Pinned ~v3.6.x" tags can move or be deleted — pin every image (Argo, stac-fastapi-pgstac, Postgres/pgSTAC, MinIO, titiler, the ingester) by `sha256` digest for true reproducibility.
- **Data licensing (this audience is sensitive to it).** The real Sentinel-2 example pulls Copernicus data — include the **Copernicus Sentinel attribution/terms**. Give the **synthetic seed an explicit license** so adopters know what they can redistribute.
- **Stack-wide license audit.** The prod profile bundles **Grafana (AGPLv3)** alongside Apache/BSD components; note any AGPL component explicitly so adopters who redistribute aren't surprised. Quick check across titiler, eoAPI, stac-browser, MinIO too.

### Adoption on-ramps & durability (turn "nice talk" into "starred repo")

- **Troubleshooting section in the README** — the things that actually save the <15 min promise: Docker not running, kind fails to start, port 2746 busy, arm64 image pull. This matters more than another feature.
- **Contributor on-ramps** — a few labelled **`good first issue`s** and a **Discussions** pointer.
- **Governance / bus factor** — a one-line maintenance statement: who owns the repo after the talk, and whether OSGeo/community stewardship is intended. Sets adopter expectations.
- **Bitrot defence** — the scheduled CI smoke run (see Demo strategy) is also the durability mechanism: drift surfaces to the maintainer before an attendee hits it six months out.

### Boundaries

**Always:**
- Keep `src/eo_ingest` runnable standalone (no Argo import in the business logic) — the "same script across rungs" promise depends on it.
- Keep **one copy** of `src/eo_ingest` and **one** ingester image, reused by every stage. Stages hold orchestration only.
- Make ingestion **idempotent** — re-running must not duplicate or corrupt (retries *will* re-run steps).
- Be **polite to source APIs** — cap fan-out parallelism (Argo `parallelism:`) and rate-limit; never hammer a public STAC API.
- Keep the **core** stack minimal (plain manifests, single-replica, fast); reserve Helm/heavy components for `PROFILE=prod`.
- Build images **multi-arch** (amd64 + arm64); Apple Silicon is a first-class target.
- Pin for reproducibility: container images **by `sha256` digest** (not just tags), Argo/eoAPI chart versions, and Python deps via `uv.lock`.
- Run `ruff` + `pytest tests/unit` before every commit.
- Each stage's README states **what's new vs. the previous rung**.

**Ask first:**
- Adding any dependency on a paid/cloud service to the *core* demo (must stay free + local).
- Bumping Argo or eoAPI chart major versions.
- Changing the staged structure or the shared-package boundary.
- Adding heavyweight deps that inflate the laptop footprint or blow the cold/warm time budget.
- Moving anything from the prod profile into the core critical path.

**Never:**
- Commit secrets/credentials or real API tokens (use K8s Secrets; provide `.env.example`).
- Hardcode a real S3 bucket or require a cloud account to run stages 1–5.
- Break the "each stage runs on its own" property.
- Make any stage 1–4 depend on the prod-only components (eoAPI Helm, titiler, stac-browser, Grafana).
- Remove, skip, `xfail`, or otherwise weaken tests without explicit approval — **especially** the acceptance/contract layer (Success Criteria + cold/warm budget). A failing acceptance test means the code or the budget is wrong, not the test.

---

## "Am I missing something?" — gaps worth folding in

Things the abstract doesn't yet name that strengthen both the talk and the repo:

1. **Idempotency is the linchpin.** Retries and re-runs only help if re-ingesting is a no-op. Make this an explicit slide *and* a tested property — it's the quiet prerequisite for everything above rung 1.
2. **Forward-fill vs. backfill are two different jobs.** The CronWorkflow handles "today"; backfill handles history. Saying this out loud clarifies why fan-out (rung 2) is separate from the cron (rung 1).
3. **Politeness / rate-limiting.** Uncapped fan-out can DoS a public STAC API or your own cluster. Show `parallelism:` and a rate limit — a credibility detail the audience will respect.
4. **Completeness, not just presence.** "Up to date *and complete*" means validating the downloaded asset (size/checksum), not just that a file exists. Worth one bullet + a test.
5. **Secrets in Argo.** Real ingestion needs creds (source auth, S3). Show the K8s Secret pattern even if the local demo uses MinIO's defaults — people will ask.
6. **Rung 4's core report reads the Argo API, not Prometheus.** The core daily-report Job queries the Argo Workflows API (workflow statuses), with the workflow archive enabled on the existing Postgres for history — no bespoke metrics system on the critical path. The Prometheus-scrape + Grafana error-rate *dashboard* is prod-profile-only (see "Rung-4 data source").
7. **The daily-report sink stays a plain function — *not* a plugin interface (P3, simplicity).** The demo only ever needs stdout + markdown, so `report()` is a single function with one clear seam (a `# wire your own sink here` comment + a README note on where Slack/email would attach). Don't build an interface/registry for a single-use sink until a second sink actually exists — that's premature abstraction, and it's code nobody owns. The extension *point* teaches adopters; the extension *machinery* is theirs to add.
8. **OSS adoption hygiene.** LICENSE (Apache-2.0 to match Argo/kind), CONTRIBUTING, CODE_OF_CONDUCT, a great README with the ladder + QR code, and a one-command quickstart. This is what turns "nice talk" into "starred repo."
9. **Reproducible screencast state.** A script that puts the cluster into a known state (with the right gaps, two collections) so clips are re-recordable and match the repo exactly.
10. **Teardown + footprint note.** `make down` and an honest "this needs ~X GB RAM / Docker resources" line in the README — separately for core vs. `PROFILE=prod`. Nothing kills adoption like a laptop melting silently.
11. **One image, many stages.** Building a single ingester image reused by every stage reinforces "the code didn't change" and keeps the repo small.
12. **Minimal core, prod-like as the destination.** Bare manifests on the critical path keep clone-and-run fast and durable; the eoAPI/titiler/stac-browser/Grafana stack is the *payoff* shown via `PROFILE=prod`, not a barrier to entry. This both protects the time budget and gives the talk a satisfying "and here's where it leads" close.
13. **Multi-arch / Apple Silicon.** A large share of the audience is on arm64. Every pinned image must be multi-arch; treat an arch gap as a release blocker.

---

## Success Criteria

- [ ] Fresh clone → working **stage-1** demo: **< 15 min cold**, **< 5 min warm** on a laptop (documented and measured; CI smoke test records the time).
- [ ] `make up` (core) installs only minimal, plain-manifest, single-replica components; no Helm on the stage-1 critical path.
- [ ] `make up PROFILE=prod` brings up the eoAPI/titiler/stac-browser(/Grafana) stack and the same workflows run unchanged against it.
- [ ] Each stage runs independently and its README names the delta from the prior rung.
- [ ] **One** `src/eo_ingest` and **one** ingester image: a CI check proves no stage vendors, patches, or shadows the business logic — orchestration changes, logic doesn't.
- [ ] Gap detection + idempotent re-ingest proven by unit tests; re-running a stage ingests nothing new.
- [ ] Fan-out backfill demonstrably faster than sequential against the local seed with injected `INGEST_SLEEP` (a documented, reproducible before/after).
- [ ] Seed produces **two** collections with intentional gaps; gap detection operates per collection.
- [ ] Stage 5 **core** produces a daily report (stdout + markdown) sourced from the **Argo Workflows API** (no Prometheus) and demonstrates gaps closing; the error-rate dashboard / coverage map work under `PROFILE=prod`.
- [ ] **Rung 0 (`stages/00-cron/`) runs with no Kubernetes** — a host crontab invoking `python -m eo_ingest.ingest`; kind is first required at stage 01. (Corollary: rung 0 runs in any Codespace, including the free tier.)
- [ ] **Folder number == rung number** across `stages/00`–`stages/04`; the talk's ladder and the repo folders agree with no off-by-one.
- [ ] A **`.devcontainer`** brings up the full toolchain (uv/kubectl/kind/argo + docker-in-docker), works via local "reopen in container", and is built in CI; the README documents the **optional Codespaces** path with honest machine-size guidance.
- [ ] All pinned images (and the ingester image) are pinned **by `sha256` digest** and available for amd64 **and** arm64; the ingester image is scanned in CI.
- [ ] Five clips (rungs 1–4 + recap) recorded *from the repo* as **animated GIF/APNG**, ≤ 90s each, regenerable via scripted recording (VHS/asciinema + Playwright); the Argo UI in the clips matches the minimal install; the retry clip uses the `FAIL_ONCE` knob.
- [ ] Talk delivers the ladder as the memorable takeaway; the **HTML deck** (clips play) + PDF fallback and screencast scripts live in `docs/slides`.
- [ ] README defines "average laptop" (4-core/16 GB), states CI-runner specs separately, and has a troubleshooting section; data licensing (Copernicus attribution + synthetic-seed license) is documented.
- [ ] CI green: ruff, unit tests, `argo lint`, multi-arch image build (digest-pinned) + image scan, timed kind smoke test, shared-logic invariant check, **scheduled** drift run.

---

## Open Questions

1. **Sentinel-2 footprint for the optional example** — full COG download is heavy. Restrict to a single overview/band, or a tiny bbox, to keep `examples/real-sentinel2/` laptop-friendly? (**Recommend: single band + tiny bbox** — adopted in the structure above.)
2. **Daily-report channel for the default demo** — stdout/markdown artifact only, with Slack/email as documented opt-ins? (**Adopted: a plain `report()` function** writing stdout + markdown, with a documented seam where adopters add a sink — *no* plugin interface until a second sink exists. See "Am I missing" #7.)
3. **Argo install flavor** — minimal "quick-start" manifests vs. full install. Minimal keeps `make up` fast and is now the core default; the full/prod path is documented under `PROFILE=prod`. **Caveat to verify:** the minimal manifests must still expose the same UI shown in the screencasts (UI parity is a release check).

**Resolved (initial spec):**
- Core STAC = **bare `stac-fastapi-pgstac` + pgSTAC** (plain manifests); full **eoAPI Helm** moves to the **prod-like profile**. This removes the heaviest/most-drift-prone dependency from the clone-and-run critical path.
- Slides = **Marp markdown** in `docs/slides/talk.md`.
- Repo name = **`argo-stac-eo-pipeline`**.
- Backfill speedup is benchmarked on the **local seed with injected latency**, not the real API.

**Resolved (this review pass):**
- **Rung 0 is real cron, not K8s** — `stages/00-cron/` is a host crontab running `python -m eo_ingest.ingest`; kind first appears at stage 01. (Was: stage 01 = K8s CronJob, which contradicted the talk title.)
- **Folders renumbered `00`–`04` so folder number == rung number** (was `01`–`05`, an off-by-one vs. the ladder once rung 0 became no-K8s). `stages/00-cron` = rung 0 … `stages/04-observability` = rung 4; rung 5 stays the `PROFILE=prod` deployment swap.
- **Rung-4 core report reads the Argo Workflows API**, with the workflow archive on the existing Postgres for history; the Prometheus/Grafana error-rate **dashboard** is prod-profile only. (Was: "Argo's built-in Prometheus metrics in core," which had a hidden scraper/archive dependency.)
- **Deck = HTML primary** (clips play) + **PDF fallback**; **clips = animated GIF/APNG** (not mp4), regenerable via VHS/asciinema + Playwright; retry clip uses a **`FAIL_ONCE`** knob.
- **Images pinned by `sha256` digest** + scanned in CI; **data licensing** (Copernicus attribution + synthetic-seed license) documented.
- **"Average laptop" defined** (4-core/16 GB); CI-runner specs stated separately; README gains a **troubleshooting** section and **Windows/WSL2** note.
- **Security posture stated:** Argo Server auth mode, least-privilege workflow RBAC.
- **Positioning is on-slide:** Argo vs. Airflow/Prefect/Dagster, related work (cirrus-geo, stac-task/stactools, VEDA), openEO complementarity, ingestion-vs-ARD boundary.
- **Prod-like = a `PROFILE=prod` profile, not a `stages/06-prod/` folder.** Stages stay the orchestration-delta rungs of the ladder (count = 5, matches the talk); prod is the *same* workflows on heavier backing services — a deployment swap, "where the ladder leads," not a new rung. Short appendix README. (Was Open Question 4.)
- **Backfill speedup tuning: `INGEST_SLEEP ≈ 2s`, ~30-item (one synthetic month) window, fan-out parallelism cap ≈ 10.** Sequential ≈ 60s; fan-out ≈ ~10–15s wall-clock (a visible ~4–6× collapse). The sleep simulates **network/IO wait** — IO-bound sleeping pods yield CPU, so the win shows even on a 4-core laptop (a real teaching point, stated on-slide). The clip shows fan-out filling live (~15s) and **cites** the sequential baseline rather than playing it in full. Exact measured numbers recorded in the stage-02 README; parallelism is a documented knob that doubles as the politeness cap. (Was Open Question 5.)
- **Devcontainer ships; Codespaces is an optional on-ramp, not the default.** A `.devcontainer` standardises the toolchain (uv/kubectl/kind/argo + docker-in-docker) and its biggest value is *local* ("reopen in container" kills the #1 "Docker/kind isn't set up right" failure). Codespaces is documented as "**best on the 4-core machine type**," with the free-tier (2-core/8 GB) fit *tested and stated honestly* rather than overpromised. Synergy with the rung-0 decision: because **rung 0 needs no Kubernetes, it runs in any Codespace** — a guaranteed first taste even on the smallest machine. "No paid cloud required" is preserved: the laptop path stays default and the free tier is genuinely free. (Was Open Question 6.)

**Resolved (ai-engineering pass):**
- **Testing organised by boundary** — unit (freely editable), **adversarial** (the EO edge cases a STAC-literate audience will hit: null `datetime`, no datetime, duplicate ids, partial/corrupt download, `find_gaps` boundaries), integration (assumptions reviewed), and an **acceptance/contract** layer (Success Criteria + cold/warm budget) that is *not* weakened without explicit approval. (P5.)
- **`obstore` alternative dropped** — `boto3` only; one boring, well-understood S3 client, no unrequested optionality. (P3.)
- **Daily-report sink stays a plain `report()` function**, not a plugin interface — a documented seam instead of premature abstraction; build the machinery only when a second sink exists. (P3.)

---

*This spec is a living document. Update it when scope or decisions change, before implementing. Phase 2 (Plan) and Phase 3 (Tasks) follow once you approve.*
