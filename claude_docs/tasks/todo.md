# TODO: `argo-stac-eo-pipeline`

Working checklist derived from [`plan.md`](./plan.md). Sizes: **S** (1–2 files), **M** (3–5),
**L** (split before starting). Check a box only when **all** acceptance criteria *and* verification
steps pass. **Never** weaken the contract layer (T15) without explicit human approval.

Architecture: **one STAC API = the logbook, written from rung 1** (AD-4). `ingest.py` is byte-frozen
and registers items gated on `STAC_URL`; `logbook.py` is born with `register` and grows `find_gaps`
at rung 3; rung 0 leaves `STAC_URL` unset (no cluster).

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · ★ = human-review checkpoint.

---

## Phase 0 — Foundation: the shared, unchanging core

### [ ] T1 — Project scaffold & tooling — **S/M**
- **Acceptance:** `pyproject.toml` (uv, Python 3.12) + `uv.lock`; deps declared (`boto3`, `pystac`, `pystac-client`, **`rich`**, **`pillow`**); `ruff` configured; `src/eo_ingest/__init__.py`; `tests/unit/` + `tests/integration/`; `.env.example`; README stub.
- **Verify:** `uv sync` · `uv run ruff check .` clean · `uv run pytest` collects 0 tests OK.
- **Deps:** None · **Files:** `pyproject.toml`, `uv.lock`, `src/eo_ingest/__init__.py`, `.env.example`, `README.md`.

### [x] T2 — Minimal CI (lint + unit) — **S**
- **Acceptance:** `.github/workflows/ci.yml` runs `ruff check` + `pytest tests/unit` on push/PR.
- **Verify:** push a branch → Actions green.
- **Deps:** T1 · **Files:** `.github/workflows/ci.yml`.

### [x] T3 — `config.py` (env-driven settings) — **S**
The seam (AD-1) that lets one image serve every rung.
- **Acceptance:** loads `STAC_URL` (**optional** — unset disables registration), S3 endpoint/creds, collection, `SOURCE_TYPE`, `FAIL_ONCE`, `INGEST_SLEEP`; sane defaults; missing-required → clear error.
- **Verify:** `pytest tests/unit/test_config.py` (TDD); covers `STAC_URL` set vs unset.
- **Deps:** T1 · **Files:** `src/eo_ingest/config.py`, `tests/unit/test_config.py`.

### [x] T4 — `stac_source.py` (resolve items for a window) — **S**
Two config backends (AD-4): `synthetic` (deterministic generator behind a seam, ladder default) + `earthsearch` (real). Thin branch, **not** a plugin registry.
- **Interface contract (stable):** `(collection, day)` → deterministic STAC item with a **real-coord polygon geometry** + `data` asset + `thumbnail` asset. **The themed world (names/geography/look) is specified by `SYNTHETIC_WORLD_SPEC.md`** (the *Meridian Observation Initiative* — Finnish Lapland + Wadden Sea); build and test against the interface, not the theme.
- **Acceptance:** synthetic mode returns deterministic items matching the contract (valid geometry, both assets); earthsearch mode queries the real API; **bounded** query; empty window → `[]`. Test against the **interface**, not the theme.
- **Verify:** `pytest tests/unit/test_stac_source.py` — synthetic determinism + contract shape + `respx`-mocked earthsearch.
- **Deps:** T3 · **Files:** `src/eo_ingest/stac_source.py`, `src/eo_ingest/synthetic/`, `tests/unit/test_stac_source.py`.

### [x] T5 — `download.py` (assets → S3, idempotent + checksummed) — **M**
- **Acceptance:** writes asset to bucket via boto3; synthetic mode also writes a tiny deterministic **PNG `thumbnail`** (`pillow`, mission/date encoded as color) so items render previews in stac-browser; **re-run is a no-op**; **truncated/checksum-mismatch → re-fetched, never silently accepted**.
- **Verify:** `pytest tests/unit/test_download.py` with `moto`; thumbnail is byte-deterministic; includes corrupt/partial adversarial cases.
- **Deps:** T3 · **Files:** `src/eo_ingest/download.py`, `tests/unit/test_download.py`.

### [x] T6 — `logbook.py` — `register()` — **S/M**
Born in the foundation (AD-2); `find_gaps` is added later at T18.
- **Acceptance:** idempotent upsert of a STAC item into the catalog (stac-fastapi transactions); item includes `data` + **`thumbnail` asset roles** so stac-browser shows a preview; re-register → no duplicate.
- **Verify:** `pytest tests/unit/test_logbook_register.py` with `respx`-mocked stac-fastapi.
- **Deps:** T4 · **Files:** `src/eo_ingest/logbook.py`, `tests/unit/test_logbook_register.py`.

### [x] T7 — `ingest.py` (the frozen unit of work) — **M**
Resolve → download → S3 → `register` (**gated on `STAC_URL`**). **Byte-stable from here (AD-2).**
- **Acceptance:** `python -m eo_ingest.ingest` ingests one unit against mocked source + moto S3 + mocked STAC; emits a **`rich` summary line** (item id, region, bytes, registered?); with `STAC_URL` unset, registration is skipped; `FAIL_ONCE=1` fails once then succeeds; re-run ingests nothing new.
- **Verify:** `pytest tests/unit/test_ingest.py` · `python -m eo_ingest.ingest` standalone (both `STAC_URL` set and unset).
- **Deps:** T4, T5, T6 · **Files:** `src/eo_ingest/ingest.py`, `src/eo_ingest/__main__.py`, `tests/unit/test_ingest.py`.

> ### ★ Checkpoint A
> - [x] `uv sync` · `ruff` clean · all unit+adversarial tests green · `python -m eo_ingest.ingest` runs standalone with **and** without `STAC_URL` · ≥85% coverage · CI green.
> - Verified 2026-06-05: 80 tests green, 97% coverage, CI green on amd64 (run 27034423212). Cross-arch determinism now pinned on decoded content (CP-SW-B). Standalone run proven under moto/respx; real-MinIO standalone awaits rung 0 (T9).

---

## Phase 1 — Rung 0 (NO Kubernetes) + the one image

### [x] T8 — Ingester Dockerfile (multi-arch, digest-pinned) — **S**
- **Acceptance:** `docker build` succeeds; `docker run eo-ingest:dev python -m eo_ingest.ingest` runs; buildable amd64 **and** arm64; base pinned by `sha256`.
- **Verify:** `docker buildx build` (both platforms) · `docker run … --help`.
- **Deps:** T7 · **Files:** `Dockerfile`, `.dockerignore`.

### [x] T9 — `stages/00-cron/` (the fragile baseline + walking skeleton) — **S**
`STAC_URL` unset → asset → S3 only; sink = local MinIO via plain `docker run`; no kind/kubectl (AD-3).
- **Acceptance:** `crontab` line + `run.sh` execute `python -m eo_ingest.ingest` with **no cluster, no catalog**; README explains "nowhere to look at 3am" + the 0→1 delta (laptop crontab → Argo *and you gain a logbook*).
- **Verify:** run `run.sh` on host → asset in local MinIO; confirm `kubectl`/`kind` never invoked.
- **Deps:** T8 · **Files:** `stages/00-cron/{crontab,run.sh,README.md}`.

> ### ★ Checkpoint B
> - [x] Rung 0 runs end-to-end with **zero Kubernetes** (free-tier-Codespace compatible).
> - Verified 2026-06-05: `stages/00-cron/run.sh` builds the image, starts local MinIO, runs the ingester (`STAC_URL` unset → `registered=disabled`); both assets land in MinIO; no `kubectl`/`kind` invoked. Left for human review per the ★ gate.

---

## Phase 2 — Local cluster + Rung 1 (Argo retries + the logbook appears)

### [x] T10 — kind + MinIO (core) — **M**
- **Acceptance:** `kind create` + apply → MinIO reachable in-cluster (`http://minio:9000`); bucket bootstrapped; digest-pinned.
- **Verify:** `kubectl get pods` ready · boto/mc smoke from a pod.
- **Deps:** T1 · **Files:** `deploy/kind-cluster.yaml`, `deploy/core/minio/*.yaml`.

### [x] T11 — STAC infra + stac-browser (core) — **M**
On the rung-1 path now (AD-4). The browser is what makes the demo *visual*.
- **Acceptance:** bare `stac-fastapi-pgstac` + pgSTAC Postgres + Service reachable in-cluster (`http://stac-api`); pgSTAC migrated; **stac-browser** Deployment+Service pointed at the API; digest-pinned plain manifests.
- **Verify:** `curl http://stac-api/collections` → 200 · port-forward stac-browser → collections render in the UI.
- **Deps:** T10 · **Files:** `deploy/core/stac/*.yaml`, `deploy/core/stac/browser.yaml`.
- **★ FU-1 (follow-up, tracked 2026-06-05):** `radiantearth/stac-browser` is **amd64-only** (no arm64 manifest, all tags incl. v4). Decision: *accept host emulation* on arm64 for now (works on Apple Silicon via Docker Desktop; native on amd64 CI). SPEC classifies this as a multi-arch release-blocker, so before release **build/vendor a multi-arch stac-browser image** and pin our own digest (fold into T23 multi-arch CI). The STAC API itself is multi-arch.

### [x] T12 — Argo Workflows minimal install (core) — **M**
- **Acceptance:** Argo UI reachable via port-forward; hello workflow completes; workflow SA RBAC **least-privilege** (not cluster-admin); auth mode documented.
- **Verify:** `argo submit --watch` · UI loads · `kubectl auth can-i` confirms scoped RBAC.
- **Deps:** T10 · **Files:** `deploy/core/argo/*.yaml`, `rbac.yaml`, README note.
- Verified 2026-06-06 on kind `eo-ladder`: vendored namespace-install v3.7.4 (namespaced controller+server, images digest-pinned); `hello.yaml` reached **Succeeded** as the least-privilege `argo-workflow` SA; `kubectl auth can-i` confirmed only `workflowtaskresults` (wildcard/secrets/pods **denied**); `argo-server` (`--auth-mode=server`) returned HTTP 200 + `/api/v1/info` with no token over a port-forward.

### [ ] T13 — Makefile (`up/seed/demo/down/ui/browse`, PROFILE=core|prod) — **M**
- **Acceptance:** `make up` → kind + MinIO + STAC + stac-browser + Argo + buckets; `make ui` port-forwards Argo; `make browse` port-forwards stac-browser; `make demo STAGE=01` submits; `make down` cleans up.
- **Verify:** full `make up` → `make down` cycle leaves no dangling cluster; `make browse` opens the catalog UI.
- **Deps:** T10, T11, T12 · **Files:** `Makefile`.

### [ ] T14 — `stages/01-argo-retries/` — **M**
- **Acceptance:** CronWorkflow runs the **same image**; retries on `FAIL_ONCE` then succeeds; UI+logs show it; **asset lands in MinIO AND item appears in the STAC API**; README states the 0→1 delta.
- **Verify:** `make demo STAGE=01` → observe retry in UI → asset in MinIO → `make browse` shows the item appear in stac-browser.
- **Deps:** T8, T13 · **Files:** `stages/01-argo-retries/workflows/*.yaml`, `README.md`.

### [ ] T15 — Acceptance/contract smoke + cold/warm budget — **M**  ⚠️ CONTRACT LAYER
- **Acceptance:** timed `make up && make demo STAGE=01` reaches working rung-1 **with pgSTAC on the path** within **<15 min cold / <5 min warm**; elapsed recorded; README states it with CI-runner specs separately.
- **Verify:** run smoke locally (timed) · CI records time. **Never weakened/skipped/`xfail`'d without explicit human approval.**
- **Deps:** T14 · **Files:** `tests/integration/test_smoke_stage01.py`, README timing section.

> ### ★ Checkpoint C (CRITICAL — HUMAN REVIEW REQUIRED)
> - [ ] Fresh clone → `make up` → rung 1 working, retries visible, **items in the STAC API**, within cold/warm budget.
> - [ ] If pgSTAC pushes past budget: **decide here** (optimize vs. relax the claim) — do not silently absorb it.
> - [ ] **Stop and review with the human** — the talk's central demo + the Success-Criteria contract.

---

## Phase 3 — Rung 2 (fan-out backfill)

### [ ] T16 — `stages/02-fanout/` — **M**
- **Acceptance:** fan-out (`withItems`/`withParam`) parallelizes backfill; **parallelism capped** (politeness); `INGEST_SLEEP≈2s` × ~30 items, cap ≈10 → visible ~4–6× collapse; **measured** numbers in README + re-derived in CI; many items appear in the catalog at once.
- **Verify:** run backfill sequential vs fan-out → compare wall-clock → matches README.
- **Deps:** T14 · **Files:** `stages/02-fanout/workflows/*.yaml`, `README.md`.

> ### ★ Checkpoint D
> - [ ] Deterministic, polite ~4–6× speedup; numbers recorded in the stage README.

---

## Phase 4 — Rung 3 (the logbook becomes active — the heart)

### [ ] T17 — `scripts/seed_stac.py` (`make seed`) — **M**
Seed the **logbook** with deliberate holes (AD-4). Uses the `synthetic/` seam; themed world per the separate spec.
- **Acceptance:** seeds **two** deterministic collections into the logbook **over two distinct, visually separable regions** **with intentional gaps**; items carry thumbnails; explicit data license; gaps reproducible and **per collection**. (Specific themed regions come from the world spec; here: just two, separable.)
- **Verify:** `make seed` → `make browse` → two missions visible over distinct regions, planted gaps present.
- **Deps:** T11 · **Files:** `scripts/seed_stac.py`, seed data + license note.

### [ ] T18 — `find_gaps` (grow `logbook.py`) — **M**
The package grows here; **`ingest.py` untouched (AD-2).**
- **Acceptance (adversarial):** null top-level `datetime` → `start_datetime` fallback, never crashes; **neither** datetime → skipped with a warning; duplicate ids / re-run → idempotent; `find_gaps` boundaries (empty + fully-backfilled → `[]`); `max_items` bound exercised.
- **Verify:** `pytest tests/unit/test_find_gaps.py` (all adversarial cases present, not just guards).
- **Deps:** T6 · **Files:** `src/eo_ingest/logbook.py`, `tests/unit/test_find_gaps.py`.

### [ ] T19 — `stages/03-stac-logbook/` — **M**
- **Acceptance:** workflow does `find_gaps` → fan-out **unchanged** `ingest` over only the missing days; gaps close; **re-run ingests nothing new**; per-collection.
- **Verify:** integration on kind: seed gaps → run stage → gaps closed → re-run is a no-op.
- **Deps:** T17, T18 · **Files:** `stages/03-stac-logbook/workflows/*.yaml`, `README.md`.

### [ ] T20 — Shared-logic invariant CI check — **S**
- **Acceptance:** CI check asserts **no stage vendors/patches/shadows** `src/eo_ingest`; every stage references the one image; **fails** on a deliberate violation.
- **Verify:** run check (passes) → temporarily copy a module into a stage → check fails → revert.
- **Deps:** T19 · **Files:** `scripts/check_shared_logic.py`, CI wiring.

> ### ★ Checkpoint E (the heart — HUMAN REVIEW)
> - [ ] Rung 3 closes gaps; re-run is a no-op; per-collection.
> - [ ] **`ingest.py` is byte-identical to its rung-1 form**, enforced by T20.
> - [ ] **Review with the human** — the central teaching claim.

---

## Phase 5 — Rung 4 (observability)

### [ ] T21 — Daily report (core) — **M**
- **Acceptance:** plain `report()` writes stdout + markdown, sourced from the **Argo Workflows API** (no Prometheus); markdown includes a **gap heatmap** (✅/⬜ calendar grid per collection, color-blind-safe) and `rich` stdout; Argo **workflow archive** on the existing pgSTAC Postgres (one DB, two schemas), degrading to "last N live"; **documented sink seam, no plugin interface**; conveys two-level self-correction.
- **Verify:** run a gap-closing demo → `report()` heatmap shows ⬜ flipping to ✅ as gaps close.
- **Deps:** T19 · **Files:** `src/eo_ingest/report.py`, archive config in `deploy/core/`.

### [ ] T22 — `stages/04-observability/` — **S/M**
- **Acceptance:** stage runs the report in-cluster, produces the markdown artifact; README distinguishes item-level (auto) vs system-level (surfaced).
- **Verify:** `make demo STAGE=04` → artifact present, gaps shown closing.
- **Deps:** T21 · **Files:** `stages/04-observability/workflows/*.yaml`, `README.md`.

> ### ★ Checkpoint F
> - [ ] Full ladder 0→4 runs in core; daily report renders and shows gaps closing.

---

## Phase 6 — Polish, prod profile, real data, durability *(parallelizable after CP-F)*

### [ ] T23 — CI (full) — **M**
- **Acceptance:** expands T2 with `argo lint`, multi-arch digest-pinned build + **image scan**, timed kind smoke, shared-logic invariant, **devcontainer build**, Marp **HTML+PDF** render, **scheduled drift run**.
- **Verify:** PR → all jobs green; scheduled workflow registered.
- **Deps:** T15, T20, T24, T28 · **Files:** `.github/workflows/ci.yml`.

### [ ] T24 — `.devcontainer` — **M**
- **Acceptance:** uv/kubectl/kind/argo + docker-in-docker; "reopen in container" works; CI-built; README documents Codespaces with honest sizing (rung 0 on free tier).
- **Verify:** build the devcontainer image → run rung 0 inside.
- **Deps:** T9 · **Files:** `.devcontainer/{devcontainer.json,Dockerfile}`, README section.

### [ ] T25 — Prod profile — **L (split before starting)**
- **Acceptance:** `deploy/prod/`: `eoapi-k8s` Helm, titiler-pgstac (coverage map), optional Grafana (Prometheus → error-rate dashboard); `make up PROFILE=prod` runs the **same workflows unchanged**; license audit notes Grafana AGPL. *(stac-browser already in core.)*
- **Verify:** `make up PROFILE=prod` → run a stage unchanged → open dashboard / coverage map.
- **Deps:** CP-F · **Files:** `deploy/prod/{eoapi,minio,grafana}/*`, README appendix. *Split: (a) eoAPI+MinIO Helm; (b) titiler+Grafana.*

### [ ] T26 — `examples/real-sentinel2/` — **M**
- **Acceptance:** `SOURCE_TYPE=earthsearch` ingests real `sentinel-2-l2a` (single band, tiny bbox); Copernicus attribution/terms; `make demo-real`.
- **Verify:** `make demo-real BBOX=… DATETIME=…` → real item in MinIO + catalog.
- **Deps:** T7 · **Files:** `examples/real-sentinel2/*`, Makefile target.

### [ ] T27 — README + OSS hygiene + SPEC sync — **M**
- **Acceptance:** full README (ladder narrated, quickstart, cold/warm timings, footprint core-vs-prod, "average laptop" 4-core/16 GB, runner specs separate, **troubleshooting**, Windows/WSL2, QR target); `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, labelled `good first issue`s, governance statement, Discussions pointer; **SPEC.md sync** — verify it still matches the built ladder (AD-4 / STAC-from-rung-1 already incorporated).
- **Verify:** every README-related Success-Criteria box in SPEC.md checked; SPEC.md still matches the ladder.
- **Deps:** CP-F · **Files:** `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SPEC.md`, `docs/`.

### [ ] T28 — Slides + screencasts — **L (split before starting)**
- **Acceptance:** `docs/slides/talk.md` (Marp **HTML primary** + PDF fallback in CI); `screencast-scripts.md`; `make_screencast_data.py`; scripted recording (VHS/asciinema + Playwright); **5 clips** (rungs 1–4 + recap) GIF/APNG ≤90s; `FAIL_ONCE` retry clip; **one reusable color-blind-safe ladder SVG with a "you are here" highlight**, embedded in every stage README + the deck; **UI parity** with the minimal install.
- **Verify:** render deck (HTML+PDF) · regenerate one clip → matches the repo.
- **Deps:** CP-F · **Files:** `docs/slides/talk.md`, `docs/slides/screencast-scripts.md`, `scripts/make_screencast_data.py`. *Split: (a) deck + diagrams; (b) clip tooling + recordings.*

> ### ★ Checkpoint G (Complete)
> - [ ] Every Success-Criteria checkbox in SPEC.md met.
> - [ ] CI green incl. scheduled drift run; deck renders; clips regenerate and match the repo.
> - [ ] Ready for the talk.

---

## Definition of Done (every task)
- [ ] Acceptance criteria met **and** verification commands pass.
- [ ] `ruff` + `pytest tests/unit` green before commit (SPEC.md Boundaries→Always).
- [ ] Every changed line traces to the task (no scope creep — `/ai-engineering` #4).
- [ ] Commit message explains *why*, not just *what*.
- [ ] No secrets committed; `.env.example` updated if config changed.
