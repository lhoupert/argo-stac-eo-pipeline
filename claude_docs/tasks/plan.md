# Implementation Plan: `argo-stac-eo-pipeline`

Companion repo for the FOSS4G Europe 2026 talk *"From Cron Job to Self-Healing Pipeline."*
Source of truth: [`SPEC.md`](../SPEC.md). This plan operationalizes it into vertically-sliced,
verifiable tasks following `/ai-engineering` and `/planning-and-task-breakdown` principles.

---

## Overview

We are building a **teaching artifact**: a clone-and-run reference that walks the *maturity
ladder* for EO data ingestion (rung 0 → 4 + a prod profile). The central teaching device is that
**the unit-of-work ingest function never changes across rungs — only the orchestration around it
grows**. Everything here serves that claim being *literally true and demonstrable*, and the
clone-and-run budget on an "average laptop" (4-core/16 GB).

The natural vertical slices are **the rungs themselves** — each is a complete, independently
runnable path. We build a thin foundation (the shared package + the one ingester image), then
climb the ladder one rung at a time, with hard human checkpoints at the two highest-stakes rungs
(rung 1 = the core demo; rung 3 = the heart + the honesty claim).

---

## Architecture Decisions

Resolved as a senior architect would, following `/ai-engineering` (architecture-first, simplicity,
honesty) with the talk's context in mind. **AD-4 reflects the maintainer's explicit choice: one
STAC API, used as the logbook, visible from rung 1.**

### AD-4 (keystone, maintainer's call) — ONE STAC API = the logbook, written from rung 1
For a STAC-literate FOSS4G audience, a browsable catalog is the clearest possible signal of "what
the pipeline did." So:
- **`ingest` writes each item to the STAC logbook from rung 1** → the catalog reflects the
  pipeline's work at every rung, **browsable live in stac-browser (now included in the *core*
  profile** for visual appeal; also `pystac-client`/curl).
- **The synthetic in-process source stays the data origin** for the deterministic ladder
  (`stac_source` generates items for `(collection, day)`); `SOURCE_TYPE=earthsearch` switches to
  real Earth Search for the proof. The *one* local STAC API is the **logbook**, not the source —
  this keeps it to a single STAC concept, as chosen.
- **The rung-3 reveal is reframed (and strengthened):** rungs 1–2 fill the catalog as a passive
  record; **rung 3 makes it active** — `find_gaps` queries the logbook to drive self-correction.
  The "aha" is *"your logbook tells you what to ingest next,"* not *"a STAC API exists."*
- **Cost accepted:** pgSTAC sits on stage-1's critical path. This is small now that core uses
  **bare `stac-fastapi-pgstac`** ("installs in seconds," SPEC.md "Why bare manifests in core"), not the heavy eoAPI chart.
  T15 re-measures the cold/warm budget with pgSTAC included; if it threatens the <15 min cold
  target, that is surfaced at Checkpoint C, not hidden.

> **Reconciled with SPEC.md:** AD-4 is now the spec's position too. SPEC.md (the 2026-06-05
> architecture pass) puts the STAC catalog on the critical path from rung 1 and states `logbook.py`
> exists from the foundation with `register()` and **grows `find_gaps` at rung 3**. The "package
> grows" teaching claim holds; its locus moved. Plan and spec agree — no pending SPEC.md edit.

### AD-1 — Config is the seam that lets one image serve every rung
`config.py` is env-driven (`STAC_URL`, S3 endpoint/creds, collection, `SOURCE_TYPE`, knobs). The
*same* ingester image runs at every rung; only env/config differs (rung 0 → no `STAC_URL`, local
sink; rungs 1+ → in-cluster DNS like `http://stac-api`, `http://minio:9000`). "Same code,
different rung" is honest because the difference is configuration, not code. **Pattern:**
12-factor config / dependency-injection at the boundary.

### AD-2 — `ingest.py` is byte-frozen from rung 1; the package *grows* `find_gaps` at rung 3
The spec's central claim (SPEC.md:23) — *"the unit-of-work function is untouched; the package
grows"* — honored literally:
- `ingest.py` is written **once** and is **byte-identical from rung 1 onward**. It does:
  resolve item (`stac_source`) → download asset → S3 (`download`) → **register item → STAC
  (`logbook.register`), gated on `STAC_URL`**. The registration call is present from rung 1;
  rung 0 simply leaves `STAC_URL` unset, so the *code* is frozen while the *config* varies (AD-1).
- `logbook.py` exists in the **foundation** with `register(item)` (idempotent upsert). At **rung 3**
  it **grows `find_gaps(...)`** — the new capability.
- The rung-3 **workflow** composes: `find_gaps` → fan-out the *unchanged* `ingest` over only the
  missing days. Orchestration grows; `ingest` does not. The growth is visible as a new
  `find-gaps` node in the Argo graph and as new code in `logbook.py`.

Enforced by the **shared-logic invariant** CI check (T20).

### AD-3 — Rung 0 is K8s-free via the same config seam
Rung 0 (SPEC.md "Rung 0 is deliberately *not* Kubernetes") runs the identical pipeline with **`STAC_URL` unset** → asset → S3 only, no
catalog; sink = **local MinIO via plain `docker run`** (Docker is required; kind is not). This is
thematically perfect: the fragile baseline has *no logbook, no UI, nowhere to look at 3am* — and
the 0→1 delta now includes "you gain a catalog." Identical code, deterministic, offline,
free-tier-Codespace friendly. Rung 0 doubles as the **walking skeleton** validating the data flow
before any cluster exists.

### Cross-cutting principles (from `/ai-engineering`)
- **TDD at the business-logic boundary** — unit + adversarial tests written *with* each module in
  `src/eo_ingest`; freely editable.
- **The acceptance/contract layer is sacred** — the smoke test + cold/warm budget (T15) encode
  what the demo *promises*. Per SPEC.md Boundaries→Never, **never** weakened, skipped, or `xfail`'d
  without explicit human approval.
- **One image, digest-pinned, multi-arch** (amd64+arm64); stages hold orchestration only.
- **Core = plain manifests; prod = Helm profile** — no prod-only component on the rung 1–4
  critical path.
- **CI grows with the code** — a thin lint+unit CI lands at Phase 0, not at the end.

### Visual design (cross-cutting — the demo must *look* like real EO)
The repo is a conference artifact; what's on screen matters. These small choices make the synthetic
demo visually compelling without faking realism (approved by the maintainer):
- **A themed fictional world (in-repo, behind a seam) — *design deferred to its own spec*.** The
  synthetic generator lives in **`src/eo_ingest/synthetic/`** — a clean, extractable sub-package
  (rule-of-three; not a separate repo, to protect the offline clone-and-run promise). **The themed
  world (names, geography, look) is specified by the companion spec `SYNTHETIC_WORLD_SPEC.md`
  (now written — the *Meridian Observation Initiative*).** This plan only fixes the **interface
  contract** so the ladder isn't blocked: for a `(collection, day)` the synthetic backend yields a *deterministic* STAC item with
  a **polygon geometry at real-world coordinates**, a `data` asset, and a `thumbnail` asset. Any
  world that satisfies that contract drops in. The fake-world → real-Sentinel-2 contrast in the
  recap is the payoff (T4).
- **Visible thumbnails.** Each item carries a tiny deterministic **PNG `thumbnail` asset** (encodes
  mission/date as color) so the catalog renders *pictures* (T5/T6). Needs a light image dep
  (`pillow`).
- **Two distinct regions = two missions.** The two pseudo-missions sit over **two visually
  separable** regions (distinct real coordinates) so per-collection fan-out and gap-closing are
  legible on the map (T17). The specific themed regions come from the world spec; the plan only
  requires *two, separable*.
- **Gap heatmap.** The rung-4 report renders a **calendar grid (✅/⬜ per collection)**, not prose —
  re-renders in the README, no Grafana needed (T21).
- **One reusable ladder.** A single **color-blind-safe ladder SVG** with a "you are here" highlight,
  embedded in every stage README + the deck (T28) — the spec's recurring visual, drawn once.
- **Polished terminal.** `rich`-formatted CLI output (progress bar, colored logs, summary table)
  makes the VHS terminal clips pop (T5/T7/T21). Adds `rich` (approved; boring + standard).

New deps introduced for visuals: **`rich`** (CLI) and **`pillow`** (thumbnails) — both light,
both noted here per the spec's ask-first-on-deps boundary.

---

## Dependency Graph

```
T1 scaffold ─┬─ T2 CI(min)
             └─ T3 config ─┬─ T4 stac_source ─┐
                           ├─ T5 download ─────┼─ T7 ingest.py (FROZEN) ─ T8 image ─ T9 rung0 (no cluster/STAC)
                           └─ T6 logbook.register ┘                          │
                                                                             │   T10 kind+MinIO ─┐
                                                                             │   T11 STAC infra ─┼─ T13 Makefile ─ T14 rung1 ─ T15 smoke+budget ★CP-C
                                                                             │   T12 Argo ───────┘
                                                                             │
                                                                             ├─ T16 rung2 fan-out ★CP-D
                                                                             │
                                                                             │   T17 seed(logbook+gaps) ┐
                                                                             ├─ T18 find_gaps (grow logbook.py) ┼─ T19 rung3 ─ T20 invariant ★CP-E
                                                                             │
                                                                             ├─ T21 daily-report ─ T22 rung4 ★CP-F
                                                                             │
                              (parallelizable polish after CP-F:) T23 CI(full) T24 devcontainer T25 prod T26 real-S2 T27 README/OSS T28 slides
```

Bottom-up along this graph; the cluster + pgSTAC bring-up (now on the rung-1 path) is front-loaded
so it fails fast at Checkpoint C.

---

## Task List

### Phase 0 — Foundation: the shared, unchanging core
Goal: `python -m eo_ingest.ingest` runs standalone (mocked/local I/O), fully tested. This *is*
rung 0's substance.

- [ ] **T1 — Project scaffold & tooling.** `pyproject.toml` (uv, py3.12), `ruff`, `src/eo_ingest/__init__.py`, `tests/{unit,integration}/`, `.env.example`, README stub.
- [ ] **T2 — Minimal CI (lint + unit).** Thin `ci.yml` running `ruff` + `pytest tests/unit`. *Quality gate from commit 1.*
- [ ] **T3 — `config.py`.** Env-driven settings: `STAC_URL` (optional → gates registration), S3 endpoint/creds, collection, `SOURCE_TYPE`, `FAIL_ONCE`, `INGEST_SLEEP`. TDD.
- [ ] **T4 — `stac_source.py` + `synthetic/` seam.** Resolve items for a window; two config backends: `synthetic` (deterministic generator in **`src/eo_ingest/synthetic/`** behind a fixed interface — `(collection, day)` → STAC item w/ real-coord polygon + `data` + `thumbnail` assets; **themed world per `SYNTHETIC_WORLD_SPEC.md`** — MOI, Lapland + Wadden Sea) + `earthsearch` (real). Bounded query. TDD against the *interface*, not the theme.
- [ ] **T5 — `download.py`.** Fetch/generate assets → S3 via boto3, **idempotent + checksummed**; synthetic mode also writes a tiny deterministic **PNG `thumbnail`** (`pillow`). TDD with `moto` + adversarial (truncated/corrupt → re-fetch).
- [ ] **T6 — `logbook.py` (`register`).** Idempotent upsert of a STAC item into the catalog (stac-fastapi transactions). TDD with `respx`. *`find_gaps` is added later at T18.*
- [ ] **T7 — `ingest.py` (the frozen unit of work).** Resolve → download → S3 → `register` (gated on `STAC_URL`); `rich` summary line. Runnable as `python -m eo_ingest.ingest`; `FAIL_ONCE` injects one transient error. **Byte-stable from here (AD-2).**

> **★ Checkpoint A:** `uv sync`, lint clean, all unit+adversarial tests green, `python -m eo_ingest.ingest` runs standalone (with and without `STAC_URL`), ≥85% coverage, CI green.

### Phase 1 — Rung 0 (NO Kubernetes) + the one image
- [ ] **T8 — Ingester Dockerfile.** Multi-arch (amd64+arm64), digest-pinned base. The single image reused by every stage.
- [ ] **T9 — `stages/00-cron/`.** Host `crontab` + `run.sh` + README ("no catalog, no UI, nowhere to look"). `STAC_URL` unset → asset → S3 only; sink = local MinIO via plain `docker run`. **No kind/kubectl.** The walking skeleton (AD-3).

> **★ Checkpoint B:** rung 0 runs end-to-end with **zero Kubernetes** (free-tier-Codespace compatible).

### Phase 2 — Local cluster + Rung 1 (Argo retries + the logbook appears)
- [ ] **T10 — kind + MinIO (core).** `kind-cluster.yaml` + `deploy/core/minio/`, digest-pinned, bucket bootstrap.
- [ ] **T11 — STAC infra + stac-browser (core).** `deploy/core/stac/`: bare `stac-fastapi-pgstac` + pgSTAC Postgres + Service **+ stac-browser** (lightweight static app pointed at the API), digest-pinned plain manifests. *On the rung-1 path now (AD-4); the browser is what makes the demo visual.*
- [ ] **T12 — Argo Workflows minimal install (core).** `deploy/core/argo/` (~v3.6.x pinned), **UI exposed**, **least-privilege RBAC**, auth mode documented.
- [ ] **T13 — Makefile.** `up / seed / demo / down / ui / browse`, `PROFILE=core|prod` (`browse` port-forwards stac-browser).
- [ ] **T14 — `stages/01-argo-retries/`.** Argo CronWorkflow wrapping the **same image**; retries; **writes asset→S3 + item→STAC** (items now visible in the catalog). README states the 0→1 delta (laptop crontab → Argo; *and you gain a logbook*).
- [ ] **T15 — Acceptance/contract smoke + cold/warm budget.** Timed `make up && make demo STAGE=01` reaches working rung-1 **with pgSTAC on the path**; records elapsed; documented. **Contract layer — never weakened without approval.**

> **★ Checkpoint C (CRITICAL — HUMAN REVIEW):** fresh clone → `make up` → rung 1 working, retries
> visible, items appear in the STAC API, **within the cold (<15 min)/warm (<5 min) budget**. If
> pgSTAC pushes past budget, decide here (optimize vs. relax the claim). The talk's central demo.

### Phase 3 — Rung 2 (fan-out backfill)
- [ ] **T16 — `stages/02-fanout/`.** Fan-out (`withItems`/`withParam`), **parallelism cap** (politeness), `INGEST_SLEEP≈2s` × ~30 items, cap ≈10. README records **measured** numbers; CI re-derives.

> **★ Checkpoint D:** deterministic, polite ~4–6× speedup; many items appear in the catalog at once.

### Phase 4 — Rung 3 (the logbook becomes active — the heart)
- [ ] **T17 — `scripts/seed_stac.py` (`make seed`).** Seed the **logbook** with **two** collections **over two distinct EU regions** (visually separable on the map) **with intentional gaps**; thumbnails; explicit data license; per-collection.
- [ ] **T18 — `find_gaps` (grow `logbook.py`).** Add `find_gaps(...)` (with `_item_date` fallback). TDD + **adversarial**: null `datetime`→fallback; neither→skip+warn; duplicate ids→idempotent; boundaries (empty + fully-backfilled → `[]`); `max_items` bound exercised. **`ingest.py` untouched.**
- [ ] **T19 — `stages/03-stac-logbook/`.** Workflow: `find_gaps` → fan-out *unchanged* `ingest` over only the missing days. Gaps close; re-run is a no-op; per-collection. README: the catalog goes passive→active.
- [ ] **T20 — Shared-logic invariant CI check.** No stage vendors/patches/shadows `src/eo_ingest`; one image referenced everywhere. Prove it catches a deliberate violation.

> **★ Checkpoint E (the heart — HUMAN REVIEW):** rung 3 closes gaps, re-run is a no-op,
> per-collection; **`ingest.py` is byte-identical to rung 1**, enforced by T20. The central claim.

### Phase 5 — Rung 4 (observability)
- [ ] **T21 — Daily report (core).** Plain `report()` (stdout + markdown) from the **Argo Workflows API** (no Prometheus); includes a **gap heatmap** (✅/⬜ calendar grid per collection, color-blind-safe) + `rich` stdout; Argo **workflow archive** on the existing pgSTAC Postgres (one DB, two schemas), degrading to "last N live"; documented sink **seam**, no plugin interface.
- [ ] **T22 — `stages/04-observability/`.** Daily-report workflow + README (item-level auto vs system-level surfaced). Demonstrates gaps closing in the report.

> **★ Checkpoint F:** full ladder 0→4 runs in core; report renders; gaps close.

### Phase 6 — Polish, prod profile, real data, durability *(parallelizable)*
- [ ] **T23 — CI (full).** `argo lint`, multi-arch digest-pinned build + **scan**, timed kind smoke, shared-logic invariant, **devcontainer build**, Marp **HTML+PDF**, **scheduled drift run**.
- [ ] **T24 — `.devcontainer`.** uv/kubectl/kind/argo + docker-in-docker; CI-built; README documents Codespaces with **honest** sizing (rung 0 on free tier).
- [ ] **T25 — Prod profile** *(L — split).* `deploy/prod/`: `eoapi-k8s` Helm, titiler-pgstac (coverage map), optional Grafana (Prometheus → error-rate dashboard). `make up PROFILE=prod` runs the **same workflows unchanged**. *(stac-browser is already in core; prod just gets the eoAPI-bundled one.)* License audit (Grafana AGPL).
- [ ] **T26 — `examples/real-sentinel2/`.** Real `sentinel-2-l2a` via Earth Search (`SOURCE_TYPE=earthsearch`, single band, tiny bbox). Copernicus attribution. `make demo-real`.
- [ ] **T27 — README + OSS hygiene + SPEC sync.** Full README (ladder, quickstart, timings, footprint, "average laptop" defined, runner specs, **troubleshooting**, Windows/WSL2, QR); `CONTRIBUTING`, `CODE_OF_CONDUCT`, `good first issue`s, governance. **SPEC.md sync** — verify SPEC.md still matches the built ladder (AD-4 / STAC-from-rung-1 already incorporated).
- [ ] **T28 — Slides + screencasts** *(L — split).* `docs/slides/talk.md` (Marp **HTML primary** + PDF fallback), `screencast-scripts.md`, `make_screencast_data.py`, scripted recording (VHS/asciinema + Playwright), **5 clips** (rungs 1–4 + recap) GIF/APNG ≤90s, `FAIL_ONCE` retry clip, **one reusable color-blind-safe ladder SVG with a "you are here" highlight** (embedded in every stage README + deck), **UI parity**.

> **★ Checkpoint G (Complete):** every Success-Criteria checkbox in SPEC.md met; CI green (incl.
> scheduled drift); deck renders; clips regenerate and match the repo. Ready for the talk.

---

## Parallelization

- **Strictly sequential:** T1→T3→{T4,T5,T6}→T7; T7→T8→T9; {T10,T11,T12}→T13→T14→T15;
  T17→T18→T19. Cluster/pgSTAC bring-up and the shared package cannot be parallelized.
- **Safe to parallelize once inputs exist:** T4/T5/T6 (all depend only on T3); the three core
  infra installs T10/T11/T12 (independent manifests); Phase 6 (T23–T28) after CP-F.
- **Contract-first:** the image CLI surface (`python -m eo_ingest.ingest`) is fixed at T7 before
  stages T14/T16/T19/T22 parallelize.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| pgSTAC on the rung-1 path blows the <15 min cold budget | **High** (new, from AD-4) | Bare manifests (seconds to install); digest-pin; T15 measures it; decision gate at CP-C. |
| `ingest.py` quietly drifts, breaking the central claim | **High** | AD-2 + shared-logic invariant (T20) in CI; registration call frozen + config-gated, not rung-specific. |
| Multi-arch gap (breaks on Apple Silicon) | **High** | Release blocker; multi-arch build in CI (T23); verify arm64+amd64 on every pinned image. |
| K8s barrier for a GIS-not-DevOps audience | **Med** | Front-loaded fail-fast at CP-C; `.devcontainer` (T24); rung 0 needs no cluster. |
| Argo quick-start ships auth-disabled | **Med** | T12 documents auth mode + least-privilege RBAC; README hardening note. |
| Non-deterministic clips | **Med** | `INGEST_SLEEP` + `FAIL_ONCE`; `make_screencast_data.py`; scripted recording (T28). |
| Prod profile (T25) is L-sized | **Low/Med** | Off critical path; split; degrade gracefully. |

---

## Resolved Decisions (architect's calls + maintainer input)

1. **AD-4 (maintainer's choice, now reconciled):** one STAC API as the **logbook**, written from
   rung 1 — chosen for inspectability. Reorders the build (pgSTAC → stage-1 path;
   `logbook.register` → foundation; `find_gaps` → rung 3). **SPEC.md already reflects this** (the
   2026-06-05 architecture pass), so plan and spec agree.
2. **AD-1/AD-2/AD-3** follow from AD-4 above.
3. **`INGEST_SLEEP` numbers:** spec defaults as *knobs*; **measure on the reference laptop, record
   actuals**; CI re-derives (ai-eng #6).
4. **Codespaces:** promise only **rung 0 on the free tier (verified)**; rungs 1–4 want 4-core/local.
5. **REVIEW.md:** stays untracked; T27 *offers* to archive under `docs/decisions/`, default out.
6. **stac-browser in core (maintainer's choice):** **yes** — included in the *core* profile (T11)
   so the catalog is *visually* browsable from rung 1, not just `curl`-able. Lightweight static
   app; small cost; directly serves the "make the demo visually appealing" goal. SPEC.md moves
   stac-browser core-ward in T27.
7. **Synthetic data = themed fictional world, in-repo behind the `synthetic/` seam (maintainer's
   choice):** the generator stays in-repo (not a separate companion project) to protect the
   offline clone-and-run promise, but is isolated in `src/eo_ingest/synthetic/` so it's extractable
   later. **The themed world's design now lives in `SYNTHETIC_WORLD_SPEC.md`** — this plan
   commits only to the **interface contract** (`(collection, day)` → deterministic item w/
   real-coord polygon + `data` + `thumbnail`), so T4/T17 build against the interface and the
   themed world (Finnish Lapland + Wadden Sea) drops in on top. *The world spec feeds the
   final look of T4/T17/the clips (T28), but does not block building the ladder.*

## Open Questions (non-blocking)

- Whether `register` derives metadata from the source item or the stored asset (T6) —
  implementation detail settled in-task. *(Synthetic-asset format is now fixed by
  `SYNTHETIC_WORLD_SPEC.md`: `data` = 256×256 grayscale PNG, `thumbnail` = false-color PNG.)*

---

## Verification of this plan (pre-implementation gate)

- [x] Every task has acceptance criteria + a verification step (in `todo.md`).
- [x] Dependencies identified and ordered bottom-up (graph above), reflecting AD-4's reordering.
- [x] No task exceeds ~5 files except T25/T28, flagged **L — split**.
- [x] Checkpoints between every phase; **hard human gates at CP-C and CP-E**.
- [ ] **Human has reviewed and approved this plan** ← *we are here.*

---

*Derived from `SPEC.md`; inherits its living-document status. AD-4 is reconciled — SPEC.md already
reflects it (the 2026-06-05 architecture pass). Update this plan when scope changes, before
implementing.*
