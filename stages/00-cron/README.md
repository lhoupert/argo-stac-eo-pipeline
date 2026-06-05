# Stage 00 — Cron (Rung 0): the honestly-fragile baseline

> The starting point everyone recognises: a script on a laptop, run by `cron`.

This rung runs the **one image** (the frozen unit of work) on a schedule against a **local
MinIO**, with **no Kubernetes and no catalog**. It is deliberately fragile — its job is to make
the problems *visible* so the later rungs have something to fix.

## What it does

```
cron ──▶ run.sh ──▶ docker run eo-ingest  ──▶  MinIO (object storage)
                    (STAC_URL unset)            └─ the asset, and nothing else
```

- `run.sh` builds/uses `eo-ingest:dev`, starts a local MinIO, and runs
  `python -m eo_ingest.ingest` with **`STAC_URL` unset** — so the item's assets land in object
  storage and registration is skipped.
- `crontab` is the one line that would schedule it at 03:00 daily.

## Run it

```bash
./stages/00-cron/run.sh                 # ingest the default day
./stages/00-cron/run.sh 2026-03-15      # or a specific day
```

You'll see the asset in MinIO (console at http://localhost:9001, user/pass `minioadmin`).

## Why this is fragile (the point of the rung)

- **Nowhere to look at 3am.** If the run fails, there is no logbook, no UI, no retry — the only
  trace is a line in `/tmp/eo-rung0.log`, if you remembered to redirect it. You learn the data is
  missing when a downstream user complains.
- **No record of what *should* exist.** Object storage holds what succeeded; nothing knows what
  was supposed to be there, so a gap is invisible.
- **No retries.** A transient network blip just loses the day.
- **Tied to one machine.** The laptop sleeps, the job doesn't run.

## The 0 → 1 delta (what the next rung buys you)

Rung 1 runs **the same image, unchanged** under **Argo Workflows** — and crucially the ingest
starts **registering each item into a STAC API (the logbook)**. So you gain two things at once:
orchestration (retries, history, a UI) *and* a catalog you can actually look at. "Nowhere to look
at 3am" becomes "open the logbook."

## No Kubernetes here (AD-3)

This rung never invokes `kind` or `kubectl` — it is plain `docker run`, so it works on a free-tier
Codespace. The cluster appears at rung 1.
