# Walk the ladder — a guided tour (rungs 0 → 4)

This is the long-form companion to the README's quickstart: a **step-by-step walk up the whole
maturity ladder** on your laptop. Each rung is one command, and for each we say **what you'll
see**, **how to verify it**, and **the lesson** — the one idea that rung adds.

The teaching device runs through everything: **the unit of work never changes.**
`src/eo_ingest/ingest.py` is byte-frozen from rung 1; every rung runs the *same* image, and only
the orchestration around it grows. When code seems to "appear" at rung 3, it's the *logbook*
(`logbook.py`) growing `find_gaps` — never the ingester.

![The maturity ladder](https://raw.githubusercontent.com/lhoupert/foss4g2026-talk/main/public/ladder.svg)

> **New here?** Do the [Prerequisites](../README.md#prerequisites) first, then come back. The
> short version: install Docker + `uv` + `kind` + `kubectl` + `argo` (or use the dev container),
> then run `make check` to confirm you're ready.

**Time & size.** Rung 0 runs on anything (2-core / 4 GB). Rungs 1–4 want **4-core / 8 GB+** —
they spin up a real (tiny) Kubernetes cluster. A fresh `make up` reaches a working rung 1 in
**< 15 min cold / < 5 min warm**.

---

## Rung 0 — the cron baseline (no Kubernetes)

The starting point everyone recognises: a script on a laptop, run by `cron`. No cluster, no
catalog — deliberately fragile, so the later rungs have something to fix.

```bash
./stages/00-cron/run.sh              # ingest the default day
./stages/00-cron/run.sh 2026-03-15   # …or a specific day
```

**What you'll see.** The script builds/uses the `eo-ingest:dev` image, starts a local MinIO, and
runs the ingester with `STAC_URL` **unset** — so the asset lands in object storage and
registration is skipped.

**How to verify.** Open the MinIO console at <http://localhost:9001> (user/pass
`minioadmin`/`minioadmin`) — the asset is there, and *nothing else*.

**The lesson.** There's **nowhere to look at 3 am**: no logbook, no UI, no retry. A transient blip
silently loses the day; object storage holds what *succeeded* but nothing records what *should*
exist. That's the problem rung 1 solves. → details: [`stages/00-cron/`](../stages/00-cron/README.md)

---

## Bring up the cluster (once)

Everything from rung 1 on runs on a local `kind` cluster. One command brings up the whole core
stack — MinIO, pgSTAC (the logbook's Postgres), the STAC API, stac-browser, and Argo:

```bash
make check    # optional but recommended: confirms Docker is running + the CLIs are installed
make up       # kind + MinIO + pgSTAC + STAC API + stac-browser + Argo  (one cluster)
```

> **⏳ Be patient on the first run — it is not hung.** A cold `make up` pulls several container
> images and then runs the **pgSTAC database migration on first boot** (the startup probe allows
> it ~5 minutes). The terminal can sit quietly on `waiting for pgstac rollout` for a while — that's
> expected. Subsequent runs are warm and fast.

When it finishes you'll see `core stack is up. Next: …`. Check it any time with:

```bash
make status   # pod readiness + the demo URLs at a glance
```

**Open the Argo UI now and leave it running** — you'll watch every rung execute in it, so it helps
to have it open *before* you submit anything. `make ui` (like `make browse` and `make demo`) holds
its terminal with a port-forward, so keep a couple of tabs open and run the `make demo` commands in
a **second** terminal:

```bash
make ui       # opens the Argo UI (plain HTTP, no login); leave it running
```

---

## Rung 1 — retries + a logbook

The crontab line moves into the cluster. Nothing about *the work* changes; you gain two things at
once — **retries** and a **catalog you can finally look at**. With the Argo UI already open,
submit the rung from your second terminal and watch it run:

```bash
make demo STAGE=01   # 2nd terminal — submit rung 1 and watch it appear + run in the Argo UI
```

**What you'll see.** A new workflow shows up in the Argo UI, and its ingest node goes
`ingest(0) ✖ → ingest(1) ✔` — it fails once (`FAIL_ONCE` injects a transient failure), Argo
reschedules it in a fresh pod, and the retry succeeds. (`make demo` also streams the same
fail→retry→succeed in your terminal via `--watch`.) That fail-then-succeed *is* the rung.

**How to verify the result.** Once the workflow is `Succeeded`, look at the logbook:

```bash
make browse   # opens stac-browser → the ingested item now appears in the catalog
```

`make browse` also port-forwards the STAC API on `:8081` while it runs, so from another terminal:

```bash
curl -s http://localhost:8081/collections/synthetic-aurora-veil/items | jq '.features[].id'
# → the ingested item id (e.g. "MOI-AV_20260314")
```

> **🖼 Heads-up — previews are blank in stac-browser.** The item, its geometry, and its metadata
> are correct, but the thumbnail tile is empty. That's a known follow-up (FU-2): the asset hrefs
> are `s3://…` URIs, which a browser can't fetch directly. The map footprint and item records are
> the real signal here, not the preview image.

**The lesson.** "Nowhere to look at 3 am" becomes "open the logbook, and the retry already handled
the blip." Same image, same ingest code — the retry lives in the Argo spec, not the
code. → details: [`stages/01-argo-retries/`](../stages/01-argo-retries/README.md)

---

## Rung 2 — fan-out backfill (go fast, politely)

Rung 1 ingested one day. Backfilling a month that way is 30 sequential runs. Rung 2 keeps the exact
same `ingest` and fans it out across the window with Argo's `withItems`, capped so "fast" never
means "rude."

```bash
make demo STAGE=02   # 2nd terminal — backfill 30 days; watch ~10 ingest pods run at a time
make browse          # afterwards — the whole month appears in the logbook at once
```

**What you'll see.** Up to `parallelism: 10` ingest pods in flight at once (each carries
`INGEST_SLEEP=2s` to stand in for real IO cost), and the catalog filling from empty to **30 items**
(`MOI-AV_20260301 … 20260330`) in one go. For this rung the terminal `--watch` reads best — a big
fan-out is where the Argo UI graph collapses nodes into "N hidden," so the live count is clearer in
the terminal.

**How to verify (the measured speedup is the point).** Compare the fan-out against the *same*
workflow pinned to one-at-a-time:

```bash
sed 's/parallelism: 10/parallelism: 1/' stages/02-fanout/workflows/backfill.yaml \
  | argo submit -n eo --wait -                                       # sequential baseline
argo submit -n eo --wait stages/02-fanout/workflows/backfill.yaml    # fan-out
```

Measured here: **~311 s sequential vs ~50 s fan-out ≈ 6.2×**. (Not 10× — per-pod startup on one
node erodes the cap; the cap is a *politeness ceiling*, not a throughput guarantee.)

**The lesson.** Parallelism is a property of the *orchestration*, not the code — `ingest.py` has
no batching logic. → details: [`stages/02-fanout/`](../stages/02-fanout/README.md)

---

## Rung 3 — the logbook repairs itself (the heart of the talk)

Until now *you* told the pipeline what to do. Here the **logbook** does: it knows what should
exist, finds what's missing (`find_gaps`), and fills exactly that — nothing more. Rung 3 needs
some holes to close, so seed them first:

```bash
make seed            # plant two collections with deliberate, reproducible gaps
make demo STAGE=03   # 2nd terminal — detect synthetic-aurora-veil's gaps and fill exactly them
make browse          # afterwards — the calendar fills in
```

**What you'll see.** A `find-gaps` step prints the missing days as JSON
(e.g. `["2026-03-04","2026-03-05","2026-03-10"]`), then `close-gaps` fans out **one ingest pod per
missing day — and no others**.

**How to verify.** After the repair, the gap query returns empty, and a re-run is a clean no-op:

```bash
make demo STAGE=03   # run it again → find-gaps prints [], zero ingest pods, still Succeeded
```

Repairs are **per collection** — fix the other mission independently, and note it never touches the
first:

```bash
argo submit -n eo --watch stages/03-stac-logbook/workflows/repair.yaml \
  -p collection=synthetic-tidal-glass
```

**The lesson — two levels of self-correction, both for free:**

| Level | Failure | Who fixes it | Rung |
|-------|---------|--------------|------|
| Item | a single run fails transiently | Argo retries the step | 1 |
| System | a whole day never landed | the logbook detects + refills it | 3 |

`find_gaps` grew in `logbook.py` (the logbook is *meant* to grow); the unit of work never learned
what a "gap" is. → details: [`stages/03-stac-logbook/`](../stages/03-stac-logbook/README.md)

---

## Rung 4 — make the self-correction visible

The pipeline already heals itself. Rung 4 doesn't change that — it lets you *see* it, at a glance,
by running the same image one more way: a daily report.

```bash
make demo STAGE=04         # render the report in-cluster; watch it Succeed
argo logs @latest -n eo    # see the rich gap heatmap in the pod logs
# the markdown is also captured as the workflow's `report` output parameter:
argo get @latest -n eo -o json | jq -r '.status.nodes[].outputs.parameters[0].value'
```

**What you'll see.** A report with two sections mirroring the two repair loops: an **item-level**
Argo run summary (read from the durable workflow *archive* — "1 attempt failed then retried") and a
**system-level** gap heatmap with ⬜ flipping to ✅. Repair a collection at rung 3 and re-run this:
its ⬜ flip to ✅.

**The lesson.** A self-healing pipeline still needs a window onto *what* it healed — the item level
corrects itself silently; the system level needs this report to be visible. (No Prometheus/Grafana
in core: the report is sourced from systems the pipeline already runs — the Argo API and the
logbook.) → details: [`stages/04-observability/`](../stages/04-observability/README.md)

---

## Re-running cleanly — `make clean` / `make reset`

To walk a rung again from a clean slate **without** rebuilding the cluster:

```bash
make clean   # delete the demo's Argo workflows + clear the logbook + empty the asset bucket
make reset    # the above, then re-seed the planted gaps (handy before re-doing rung 3)
```

`make clean` keeps the cluster (and the Argo run-history archive) — it's seconds, not the ~2-minute
`down`/`up` recreate. For a **fully pristine** cluster (fresh archive, fresh images-as-loaded),
use `make down` then `make up`.

---

## Rung 5 — where the ladder leads (optional)

Rung 5 isn't a folder — it's the *same workflows* on a production-grade stack (eoAPI, titiler,
Grafana) via `make up PROFILE=prod`. It's the "here's where this goes" payoff, **not** a
prerequisite for walking the ladder. The prod profile is still being built (tracked as T25), so
today `PROFILE=prod` fails loudly rather than pretending to be core.

---

## Tear down

```bash
make down    # delete the kind cluster (idempotent)
```

---

## Observe the cluster (and when something looks wrong)

`make status` and `make check` are the two fastest "what's going on?" probes. To look closer, run
these wherever you brought the cluster up — your host, or the dev container — against the
`kind-eo-ladder` context:

```bash
make status                         # pods + the demo URLs at a glance
kubectl -n eo get pods              # raw pod status (Running / Completed / Error)
kubectl -n eo get all              # pods, services, deployments together
kubectl -n eo logs deploy/stac-api  # a component's logs (swap in pgstac, minio, …)
kubectl -n eo describe pod <name>   # why a pod is Pending / CrashLooping
kubectl -n eo get events --sort-by=.lastTimestamp   # recent cluster events

argo list -n eo                     # every workflow run + its status
argo get  -n eo @latest             # the step tree of the last run (the ✖→✔ retry view)
argo logs -n eo @latest             # that run's pod logs
```

The two web UIs need a port-forward, which the Makefile wraps: `make ui` (Argo Workflows,
http://localhost:2746) and `make browse` (STAC API + stac-browser). In a dev container, run these
in the editor-attached terminal so the port is forwarded to your host browser.

The README's [Troubleshooting table](../README.md#troubleshooting) covers the usual suspects —
stale in-cluster image (`make rebuild`), an ambient `S3_*` env leaking into a host script, blank
previews (FU-2), slow first `make up`, and the Windows/WSL2 note.
