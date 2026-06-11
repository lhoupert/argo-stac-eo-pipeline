# Screencast scripts (T28, part b — SCAFFOLD)

Five short clips (≤ 90 s each) for the deck, one per rung + a recap. Each is **scripted** so it
re-records identically: `python scripts/make_screencast_data.py <clip>` resets the cluster to the
clip's starting state, then you run the command block below while recording.

Recording tools (pick per clip):
- **Terminal** clips → [VHS](https://github.com/charmbracelet/vhs) tapes (deterministic) or
  `asciinema` → GIF via `agg`.
- **Browser** clips (stac-browser / Argo UI) → Playwright trace or a screen recorder, exported to
  GIF/APNG.

Keep clips **UI-parity with the minimal install** (core profile) so what the audience clones
matches what they watch.

---

## `rung1-retry` — fail once, retry, succeed (~30 s)

```bash
python scripts/make_screencast_data.py rung1-retry   # fresh cluster, fail-marker cleared
make demo STAGE=01                                   # watch ingest(0) ✖ → ingest(1) ✔
```
Capture: the Argo `--watch` table flipping the retried step to ✔.

## `rung2-fanout` — capped parallel backfill (~40 s)

```bash
python scripts/make_screencast_data.py rung2-fanout
make demo STAGE=02                                   # ~10 ingest pods at a time, 30 days
```
Capture: the burst of parallel pods (Argo UI is the strongest visual here).

## `rung3-gapclose` — the logbook repairs itself (~45 s)

```bash
python scripts/make_screencast_data.py rung3-gapclose   # seeds gaps
make demo STAGE=03                                       # find-gaps → fills only the gaps
make browse                                              # ⬜ → ✅ in the calendar
```
Capture: the heatmap / catalog before and after; the "only the gaps" fan-out.

## `rung4-report` — make it visible (~30 s)

```bash
python scripts/make_screencast_data.py rung4-report
make demo STAGE=04 && argo logs @latest -n eo            # the gap heatmap + retry summary
```

## `recap` — the ladder (~20 s)

Animate `ladder.svg` highlighting rung 0 → 4 in turn (use the `ladder-rung{0..4}.svg` family), then
the `make demo-real` one-liner. No cluster needed — pure diagram + one command.

---

## Honesty checklist (per the SPEC)

- [ ] clips are color-blind-safe (the heatmap + ladder already are; check any added overlays)
- [ ] each clip ≤ 90 s; GIF/APNG committed under `docs/slides/clips/`
- [ ] a clip regenerated from these scripts matches the committed one (CI can diff a frame)
