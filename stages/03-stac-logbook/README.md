# Stage 03 — STAC logbook (Rung 3): the catalog repairs itself

> Until this rung, I had to tell the pipeline what to do. Here the **logbook** does:
> it knows what should exist, finds what's missing, and fills exactly that — nothing more.

_Ladder: rung 3 of 5 — you are here._

Rung 2 backfilled a window you named by hand. Rung 3 asks the catalog `find_gaps` — *which days in
this window have no item?* — and fans `ingest` out over **only those days**. Same frozen unit of
work, same env-driven image; the only new idea is **who decides**.

```
ensure-collection ─▶ find-gaps ─▶ close-gaps  (fan-out ingest, one pod per MISSING day)
                     │                         withParam = the gap list
                     └─ prints e.g. ["2026-03-04","2026-03-05","2026-03-10"]
                        (an empty list ⇒ the workflow fills nothing — a clean no-op)
```

## Run it

```bash
make up                 # if not already running
make seed               # plant two collections with deliberate gaps (rung 3 needs holes to close)
make demo STAGE=03      # repair synthetic-aurora-veil: detect its gaps, fill exactly them
make browse             # the calendar fills in

# per-collection: repair the other mission
argo submit -n eo --watch stages/03-stac-logbook/workflows/repair.yaml \
  -p collection=synthetic-tidal-glass
```

## What it proves (verified live 2026-06-10)

Seeded `synthetic-aurora-veil` had gaps at **03-04, 03-05, 03-10**. One `make demo STAGE=03`:

- **`find-gaps` detected exactly those three** and printed them as JSON;
- **`close-gaps` fanned out three ingest pods**, one per gap day — and no others;
- afterwards `find_gaps` over the window returns **`[]`** — the holes are gone;
- **re-running is a clean no-op**: `find-gaps` prints `[]`, Argo fans out over nothing, **zero
  ingest pods**, workflow still `Succeeded`;
- **per-collection**: `synthetic-tidal-glass` kept *its* gaps — repairing one mission never touches
  the other.

## Two-level self-correction

This is the second of two independent repair loops the ladder gives you for free:

| Level | Failure | Who fixes it | Rung |
|-------|---------|--------------|------|
| Item  | a single run fails transiently | Argo retries the step | 1 |
| System | a whole day never landed | the logbook detects + refills it | 3 |

## What did *not* change

`src/eo_ingest/ingest.py` is **byte-identical** to its rung-1 form (AD-2) — enforced next by T20.
`find_gaps` grew in `logbook.py` (the logbook is *meant* to grow); `list_gaps` is a thin CLI that
turns its answer into JSON for Argo's `withParam`. The unit of work never learned what a "gap" is.

## The 3 → 4 delta (next rung)

The pipeline now self-corrects, but you still have to *look* to know it's working. Rung 4
(`stages/04-observability/`) produces a daily report — a gap heatmap that shows ⬜ flipping to ✅ —
so the self-healing is visible at a glance.
