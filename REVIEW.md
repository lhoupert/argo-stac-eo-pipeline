# Review: SPEC.md from a FOSS4G Europe attendee's seat

**Reviewer persona.** A European geospatial practitioner sitting in the audience — somewhere between a Sentinel/Copernicus data wrangler, a PostGIS/QGIS person, and a research-software engineer. STAC- and COG-literate, comfortable with Python and Docker, but **not** an Argo or Kubernetes expert (couldn't reliably tell Argo CD from Argo Workflows). My "cluster" is Docker Desktop on a MacBook or WSL2.

**Scope.** Review of `SPEC.md` ("From Cron Job to Self-Healing Pipeline", companion repo `argo-stac-eo-pipeline`) as of 2026-06-02. This is feedback only; `SPEC.md` is unchanged.

---

## What lands well (protect these)

- **The maturity ladder is the star.** "Locate your pipeline on the ladder, know the next rung" (table ~L36–43) is exactly the practical, take-it-home framing FOSS4G rewards. I'd remember rungs 0→4 from memory. This is the spec's biggest asset.
- **Clone-and-run, no cloud bill, measured cold/warm budget** (~L25–28). The thing that turns a nice talk into a starred repo. The discipline of documenting *and* CI-measuring the budget is rare and right.
- **Minimal-core vs. prod-like-profile discipline** (~L16, L76–99). Keeping Helm/eoAPI off the critical path while still showing the production stack as the payoff is mature design.
- **Prod-profile ecosystem fit** — eoAPI, titiler-pgstac, stac-browser, pgSTAC (~L78–86). Precisely the cloud-native-geo stack this crowd knows; instant credibility.
- **Pre-recorded screencasts** (~L64–68). FOSS4G venue wifi *will* betray a live demo. Recording from the actual repo is the right call.
- **Multi-arch / Apple-Silicon-as-release-blocker** (~L100–101), **idempotency-as-a-tested-property** (~L257, L285), and **OSS hygiene** (Apache-2.0 / CoC / CONTRIBUTING, ~L292). All signals of someone who has shipped before.

---

## Concerns, prioritized

Each: **observation → why it matters to *this* audience → concrete suggestion.**

### 1. The unspoken Kubernetes barrier — this audience is more GIS than DevOps
The spec assumes "Python + Docker" (~L18), but stage 2+ assumes kind + kubectl + a working mental model of pods/services/in-cluster DNS. A large slice of FOSS4G is QGIS/PostGIS/web-mapping people for whom a *local Kubernetes cluster* is the scary part, not the EO.
→ **Suggestion:** (a) a slide-one promise — "you do **not** need to know Kubernetes to follow this talk; you need Docker to run the repo." (b) Add a **GitHub Codespaces / devcontainer path** so attendees without a working local Docker can still walk the ladder. That one button widens the adoption funnel more than anything else here. (It's worth an Open Question if it tensions with the "no cloud account" purity — Codespaces free tier is a reasonable middle ground.)

### 2. "Why Argo and not Airflow / Prefect / Dagster?" — this *is* the Q&A
The spec sells Argo but never positions it against the field. Someone will ask within 30 seconds of Q&A; Airflow is far more common in data engineering.
→ **Suggestion:** One honest slide — the ladder is orchestrator-agnostic; what Argo specifically buys is Kubernetes-native, container-per-step, no separate scheduler DB, first-class fan-out (`withItems`/`withParam`). Also **disambiguate "Argo"** (Workflows, not CD) on slide one.

### 3. The gap-detection model is too clean for real EO
"Expected days minus present days" (~L211–231) assumes one-item-per-day cadence. Real Sentinel-2 / Landsat has *legitimate* gaps — revisit cycles, no acquisition, cloud masking. A STAC-literate attendee catches this instantly and risks reading the demo as a toy.
→ **Suggestion:** Keep the synthetic seed for teaching, but add one sentence/slide: "real gap detection models acquisition cadence, not calendar days — we use daily cadence here for clarity." Names the simplification before the audience does.

### 4. The lone code sample is fragile — and it's the only code in the spec
`item.datetime.date()` (~L224) breaks on STAC items that use `start_datetime`/`end_datetime` with a null top-level `datetime` (valid STAC). Pulling every item to diff dates (~L223–229) also ignores pagination/scale. Because it's the *only* code in the spec, it carries outsized weight.
→ **Suggestion:** Harden it (guard null `datetime`, fall back to `start_datetime`; note the query is bounded for the demo) or caveat it explicitly as illustrative.

### 5. "Same code, unchanged across rungs" slightly oversells at rung 3
Rung 3 introduces `logbook.py` + gap detection (~L113, L131–137) — genuinely *new* business logic, even though it lives in the shared package. If the demo says "see, identical code!" while a new module appears, a careful viewer feels the seam. The CI "shared-logic invariant" (~L239) checks stages don't vendor/shadow the package, but the package itself grows.
→ **Suggestion:** Tighten the spoken claim to "the *ingest-one-unit* function never changes; the package grows new capabilities" so wording matches the invariant.

### 6. 30 min / 5 rungs / 5 screencasts / 1 min Q&A is over-packed
~5 min per rung including a clip is tight, and "29:00–30:00 Q&A pointer / buffer" (~L62) reads as *no live Q&A*. You already tier rung 4 to degrade gracefully (~L246–250) — good instinct.
→ **Suggestion:** Go *deep* on rungs 1–3 (retries, fan-out, logbook — the heart), treat 4–5 as "and it keeps climbing," and reclaim ~4–5 min for live Q&A.

### 7. Elevate the real Sentinel-2 example out of the appendix
`examples/real-sentinel2` is currently optional/footnote (~L162, L198–199), but it's the thing that answers "does this work on *real* EO?" For this audience that question is decisive.
→ **Suggestion:** A 20-second "…and here it is on real Sentinel-2 via Earth Search" moment in the recap converts skeptics. Don't bury it.

### 8. Don't present a CI timing as a laptop timing
A GitHub runner's kind smoke-test time (~L28, L303) ≠ "average laptop." And the spec only calls out Apple Silicon — FOSS4G has many Windows/QGIS users.
→ **Suggestion:** State the measurement environment (runner specs) in the README, add one real-laptop anecdote, and a **Windows/WSL2** note alongside the Apple Silicon one.

### 9. openEO-shaped hole at a *European* conference
This is FOSS4G **Europe**; openEO / Copernicus is in the room. Not naming it invites "why not openEO?"
→ **Suggestion:** One line — openEO standardizes *processing* APIs; this is about *ingestion orchestration* — complementary, not competing.

### 10. "Self-healing" is a strong word — keep the honesty visible
You correctly split item-level (automatic) from system-level (surfaces for a human) self-correction (~L45–48).
→ **Suggestion:** Keep that distinction *on the slide*, or skeptics read "self-healing" as overclaim.

---

## Further suggestions

A second pass surfacing issues the 10 concerns above don't cover — ranked by how much they'd bite a real attendee or maintainer.

### High value

**A. The rung-0 baseline contradicts itself — the honest "naive" starting point is lost.**
The talk's rung 0 is "Plain cron + Python script" (~L38), but the repo's `stages/01-cron/` is already a **Kubernetes CronJob** (~L106). So even the baseline requires a kind cluster — the audience never sees the truly fragile thing the talk is named after ("*From* Cron Job…"), and the rung 0→1 delta shrinks to "CronJob → CronWorkflow" instead of "my laptop's crontab → Argo."
→ **Suggestion:** Either make stage 01 an actual host `cron` / plain `python -m eo_ingest.ingest` (no K8s), or rename the narrative so the baseline is honestly a K8s CronJob. Talk and repo currently disagree.

**B. The CI-rendered PDF deck can't play the screencasts.**
The demo strategy is embedded screencasts (~L64–68), but the deck is rendered to **PDF** in CI (~L95) — PDF can't play video, so the demos ship as dead frames.
→ **Suggestion:** Decide explicitly — **HTML deck** (Marp HTML) for live presenting + PDF as a static fallback. Strongly consider **animated GIF/APNG** over mp4 for clips: GIFs play in the README, on GitHub, and in HTML, and degrade to a still in PDF — no codec/audio dependency (clips are already silent + ≤90s, ~L66).

**C. Rung 4's "error-rate view from Argo's built-in metrics" may not work in the *core* profile.**
Core deliberately has no Grafana/Prometheus (~L86, L249), but Argo's metrics are just a `/metrics` endpoint — *something* must scrape and query them. A daily report *over history* also needs Argo's **workflow archive** (Postgres-backed), which the minimal quick-start install typically doesn't enable (live Workflow CRDs get GC'd). So rung-4 core has a hidden dependency.
→ **Suggestion:** Spell out the report's data source in core — most likely the daily-report Job queries the **Argo API / workflow statuses** directly (not Prometheus), and you either enable the archive or accept "last N live workflows." This is the one architectural ambiguity worth resolving before Phase 2.

### Concrete, cheap wins

**D. Deterministic failure injection for the retry clip.**
Rung 1's screencast shows "a failed step, the retry" (~L57) — that needs a reproducible fail-then-succeed.
→ **Suggestion:** Add a documented knob (e.g. `FAIL_ONCE=1` / inject a transient error) so the retry clip is re-recordable, alongside `make_screencast_data.py` (~L159).

**E. Make clip *generation* reproducible and bitrot-proof.**
→ **Suggestion:** Pair the seed-state script with scripted recording — **VHS or asciinema** for terminal clips, **Playwright** for Argo-UI clips — so anyone can regenerate them and they match the repo. Add a **scheduled (cron) CI run** of the kind smoke test so version drift surfaces to *you* before it surfaces to an attendee six months out (serves the "durable clone-and-run" goal, ~L99).

**F. Pin by digest, and name the data license.**
→ **Suggestion:** "Pinned ~v3.6.x" tags (~L80) can move or be deleted — pin images by **`sha256` digest** for true reproducibility, and scan the ingester image in CI. The real Sentinel-2 example (~L162) pulls Copernicus data: add the **Copernicus Sentinel attribution/terms**, and give the synthetic seed an explicit license. This audience is sensitive to data licensing.

**G. Define "average laptop," add troubleshooting + contributor on-ramps.**
→ **Suggestion:** The time budget hinges on "average laptop" (~L26) but it's never defined — give a reference spec (e.g. 4-core / 16 GB) for core *and* prod. Add a **README troubleshooting section** (Docker not running, kind fails, port 2746 busy, arm64 pull) — that's what actually saves the <15 min promise. To hit "starred repo" (~L292), add explicit on-ramps: a few labeled `good first issue`s and a Discussions pointer.

---

## Additional review angles

The sections above apply two lenses — *attendee in the seat* and *repo maintainer / durability*. These are further lenses the spec hasn't been examined through.

### Prior-art / novelty (highest impact)

The spec never positions the project against existing STAC-pipeline tooling, and the space is crowded: **cirrus-geo** (an established open-source STAC-based pipeline framework), **stac-task / stactools**, the **VEDA** ingestion stack, and Element84/Earth Search tooling all solve adjacent problems. A program-committee reviewer *or* an audience member will ask "isn't this just cirrus? why not stac-task?" — and nothing currently answers it.
→ **Suggestion:** Add a "related work / how this differs" note to the spec and one slide to the talk. The honest differentiator is likely *pedagogical* (the ladder + clone-and-run teaching device), not "a better pipeline framework" — say that plainly. Naming the prior art *raises* credibility; ignoring it invites the question on stage.

### Security / threat-model

The repo asks potentially thousands of people to `kubectl apply` pinned manifests and **port-forward the Argo UI** — whose quick-start install commonly ships with auth effectively disabled. The spec's only security note is "don't commit secrets" (~L273, L289); it doesn't cover what it hands attendees.
→ **Suggestions:**
- State the Argo Server **auth mode** explicitly and ensure the port-forwarded UI isn't a teach-by-example of an unauthenticated control plane. A one-line "this is local-only; here's how you'd secure it in prod" turns a risk into a teaching moment.
- Document the **workflow ServiceAccount RBAC** — least-privilege, not `cluster-admin` — since copy-paste RBAC is how clusters get owned.
- Pair with **F** above (digest pinning + image scanning): asking people to `apply` your manifests is a trust/supply-chain act; pin by digest and say what's in the image.

### Accessibility & inclusion

OSGeo/FOSS4G actively values this, and the spec's a11y coverage stops at captioned clips (~L66).
→ **Suggestions:** color-blind-safe palette for the ladder and fan-out diagrams (don't encode rung/status by color alone); contrast and font sizes legible from the back row and on a 4:3 projector; code slides large enough to read (the `find_gaps` sample won't fit legibly at full size — show a trimmed version); and keep the jargon budget low for the GIS-not-DevOps slice (expand "fan-out", "idempotent", "CRD" on first use).

### The rest (lower priority, still worth a line each)

- **CfP / program-committee fit.** Distinct from the attendee lens: *will it get accepted and fill a room?* The "we built a pipeline" genre is crowded — lead the abstract with the **ladder + clone-and-run teaching device** (the genuinely novel part), not the stack. Confirm track fit (EO / cloud-native-geo) and check overlap with other submissions.
- **Scientific credibility — ingestion vs. ARD.** The hook is "analysis-ready EO starts *before* the algorithm" (~L55), but the demo stops at *ingestion*. EO scientists may counter "you stopped before the hard part: cloud masking, reprojection, COG validation, datacube/ARD generation." Pre-empt by naming where ingestion ends and ARD begins — and that the *orchestration* lessons apply equally to the ARD steps.
- **License-compatibility audit.** The prod profile bundles **Grafana (AGPLv3)** alongside Apache/BSD components (~L86, L155). A quick stack-wide license check (titiler, eoAPI, stac-browser, MinIO's licensing history) avoids surprising adopters who redistribute. Note any AGPL component explicitly.
- **Instructional design / cognitive load.** Five rungs + a prod profile in ~27 min is a lot to retain. Ensure **one crisp "aha" per rung** and a single recurring visual (the ladder) that every section returns to — spaced repetition of one diagram beats five dense ones. (Reinforces concern #6.)
- **Governance / bus factor.** Who owns the repo after the talk? A one-line maintenance statement (and whether OSGeo/community stewardship is intended) sets adopter expectations and protects the "starred repo" goal.
- **Decision-maker ROI.** Some attendees are team leads choosing tooling. One slide of "what this saves you" (unattended runs, faster backfill, fewer 3am pages) gives them ammo to justify adopting Argo internally.

---

## Net assessment

A strong, unusually disciplined spec — clearly written by someone who has given talks and shipped repos. The concerns are about **audience calibration** (it's secretly a data-engineering talk for a partly-GIS crowd) and a few **EO-realism seams** that this specific, STAC-literate audience *will* notice. None are structural; all are addressable with a few slides and a handful of spec sentences.
