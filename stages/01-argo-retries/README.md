# Stage 01 — Argo retries (Rung 1): the same job, now resilient and recorded

> The crontab line moves into the cluster. Nothing about *the work* changes — the orchestration
> around it grows, and you gain two things at once.

_Ladder: rung 1 of 5 — you are here._

This rung runs the **exact same image** as rung 0 (`eo-ingest:dev`, the frozen unit of work),
but under **Argo Workflows**. Two changes, both purely orchestration:

1. **Retries.** The ingest step has a `retryStrategy`. The transient failure that *silently lost a
   day* at rung 0 (`FAIL_ONCE`) now fails once and **succeeds on the retry** — Argo reschedules it
   in a fresh pod, and the S3 fail-marker survives so the second attempt proceeds.
2. **A logbook.** `STAC_URL` is now set, so each item is **registered into the STAC API**. You can
   finally *look* at what landed.

```
CronWorkflow (0 3 * * *) ─▶ ensure-collection ─▶ ingest ──▶ MinIO (assets)
   the same image                                 │ retry    └─▶ STAC API (the logbook)
   the same env-driven config (AD-1)              └─ FAIL_ONCE: fail once, then succeed
```

## Run it

```bash
make up                 # cluster + MinIO + STAC + stac-browser + Argo  (once)
make demo STAGE=01      # submit the Workflow and watch the retry happen live
make browse             # open stac-browser → the item appears in the logbook
make ui                 # open the Argo UI → see the failed-then-retried step
```

`make demo STAGE=01` submits [`workflows/ingest.yaml`](./workflows/ingest.yaml) (a `Workflow`,
so it runs immediately and `--watch` follows it). You'll see the ingest step go
`ingest(0) ✖ → ingest(1) ✔` — the fail-then-succeed that is the whole point of the rung.

### Verify what landed

```bash
# the item is in the logbook (collection auto-created by the ensure-collection step):
curl -s http://localhost:8081/collections/synthetic-aurora-veil/items | jq '.features[].id'
# the assets are in MinIO: synthetic-aurora-veil/2026/03/14/{data,thumbnail}.png
```

## The scheduled form (the literal 0 → 1 delta)

Rung 0 *was* a crontab line — `0 3 * * *  run.sh`. Rung 1 is the **same schedule**, now in Argo:
[`cronworkflow.yaml`](./cronworkflow.yaml).

```bash
kubectl apply -f stages/01-argo-retries/cronworkflow.yaml   # schedule it daily at 03:00
argo cron list -n eo                                        # confirm it's registered
argo submit -n eo --from cronwf/rung1-ingest --watch        # trigger one run on demand
```

"Nowhere to look at 3am" becomes "open the logbook, and the retry already handled the blip."

## What did *not* change

`src/eo_ingest/ingest.py` is **byte-identical** to its rung-0 form (AD-2). The retry lives in the
Argo spec, not the code; registration was always there, gated on `STAC_URL` (unset at rung 0, set
here). The collection is created *around* `ingest` by a separate `ensure-collection` step
(`python -m eo_ingest.ensure_collection`) — the unit of work never learned about collections.

## The 1 → 2 delta (next rung)

Rung 1 still ingests **one day at a time**. Rung 2 (`stages/02-fanout/`) keeps this same workflow
but **fans out** over a date range to backfill many days in parallel — politely capped.
