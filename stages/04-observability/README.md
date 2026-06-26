# Stage 04 — Observability (Rung 4): make the self-correction visible

> The pipeline already heals itself (rungs 1 and 3). This rung doesn't change that — it lets you
> *see* it, at a glance, without logging into anything.

_Ladder: rung 4 of 5 — you are here._

Runs the **same image** one more way: `python -m eo_ingest.report` in-cluster, rendering a daily
report with two sections that mirror the two levels of self-correction.

```
rung4-report  ──▶  daily report
  (one step)        ├─ ITEM level   : Argo run summary  ← workflow archive (pgSTAC Postgres)
                    └─ SYSTEM level  : gap heatmap ⬜→✅  ← the logbook (find_gaps)
```

## Run it

```bash
make demo STAGE=04         # render the report in-cluster; watch it Succeed
argo logs @latest -n eo    # see the rich heatmap in the pod logs
# the markdown is also captured as the workflow's `report` output parameter:
argo get @latest -n eo -o json | jq -r '.status.nodes[].outputs.parameters[0].value'
```

## Two levels, two sources

| Level | What it shows | Automatic or surfaced? | Source |
|-------|----------------|------------------------|--------|
| **Item** | a step failed and **retried** to success | **automatic** — Argo did it without anyone watching | Argo workflow **archive** |
| **System** | a day was **missing** and got **refilled** (⬜ → ✅) | **surfaced** — you have to *look* to know it happened | the **logbook** (`find_gaps`) |

The item level corrects itself silently; the system level needs this report to be visible. That's
the whole point of rung 4: a self-healing pipeline still needs a window onto *what* it healed.

## Verified live (2026-06-11)

`make demo STAGE=04` produced a report showing `synthetic-aurora-veil` at **0 gaps (all ✅)** after
its rung-3 repair, `synthetic-tidal-glass` still at **4 ⬜**, and **1 attempt failed then retried**
read from the durable archive (it survived workflow GC — that's why the archive exists).

Repair a collection (`make demo STAGE=03 ARGS="-p collection=synthetic-tidal-glass"`) and re-run this report: its ⬜ flip to ✅.

## Why no Prometheus / Grafana here (core profile)

The report is sourced entirely from the **Argo Workflows API** and the **STAC logbook** — systems
the pipeline already runs. The core profile stays small and dependency-light; the optional **prod**
profile adds Grafana + a titiler coverage map for a richer dashboard, running the *same*
workflows unchanged.

## End of the ladder

Rungs 0 → 4: what started as a fragile cron job is now an orchestrated, parallel, **self-correcting**
pipeline with a logbook and a window onto its own health — and the unit of work never changed.
```
0 cron → 1 retries+logbook → 2 fan-out → 3 gap-closing → 4 observability
```
