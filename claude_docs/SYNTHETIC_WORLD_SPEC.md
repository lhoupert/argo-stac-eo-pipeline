# Spec: The Meridian Observation Initiative — Synthetic-World Companion

Companion spec to [`SPEC.md`](./SPEC.md) · `argo-stac-eo-pipeline` · FOSS4G Europe 2026.
**Status:** drafted 2026-06-05. **Parent contract:** frozen by `SPEC.md` — this spec conforms to it, never redefines it.

> The parent spec deferred the *themed fictional world* (names, geography, look) that the in-repo
> generator (`src/eo_ingest/synthetic/`) renders, while freezing the **interface contract**:
> `(collection, day)` → a deterministic STAC item with a **real-coordinate polygon**, a `data`
> asset, and a `thumbnail` asset. This spec supplies the world; any world meeting the contract
> would do, this is the one we ship.

---

## Objective

Give the deterministic ladder a small, **offline, byte-reproducible, license-free** world that:

- renders on the stac-browser OSM basemap as satellite-style tiles over real, recognisable land —
  credible enough to teach ingestion, **proudly synthetic** so no STAC-literate attendee mistakes
  it for Copernicus;
- sets up the recap's **`fake → real` beat** (flip `SOURCE_TYPE=earthsearch` for real Sentinel-2);
- shows **two missions over two separable EU regions**, so per-collection fan-out (rung 2) and
  gap-closing (rung 3) read clearly on the map.

**Non-goals:** not a radiometric simulator; not a custom basemap (we ride real OSM); does not model
acquisition cadence (the generator is *total* — "gaps" are an orchestration/seed concern, and the
demo uses daily cadence for clarity per the parent spec).

---

## The world

Two missions of the (fictional) **Meridian Observation Initiative (MOI)** — an invented, near-future,
open-data EO consortium. The MOI name, missions, and palettes are original and IP-safe; the
mandatory `synthetic-` collection prefix keeps the data unmistakably not-real. *Aurora-Veil* watches
the auroral north (Finnish Lapland); *Tidal-Glass* watches Europe's great tidal flats (the Wadden
Sea). That's the whole story — it exists to make the catalog memorable and the fake→real flip land.

| Mission | Collection id | Region (real, EU) | Platform / instrument | False-color palette (4-stop ramp) |
|---|---|---|---|---|
| **Aurora-Veil** | `synthetic-aurora-veil` | **Finnish Lapland** | `moi-veil-1` / `mvi` | `#0B0F3B → #145C5C → #2FBF71 → #C9A0FF` (auroral) |
| **Tidal-Glass** | `synthetic-tidal-glass` | **Wadden Sea** (NL/DE) | `moi-glass-1` / `mgi` | `#04243B → #1E6F8E → #5FC9E8 → #F2FBFF` (tidal shallows) |

Item id pattern: `MOI-<CODE>_<YYYYMMDD>` (e.g. `MOI-AV_20260314`). The palettes differ in both hue
and lightness so the two missions are tellable apart even in grayscale.

### Geography

Region bounding boxes `[lon_min, lat_min, lon_max, lat_max]` (EPSG:4326), both inside EU member
states and far apart on the map (arctic north vs. southern North Sea coast):

| Mission | Region bbox | Tiling grid |
|---|---|---|
| Aurora-Veil | `[24.0, 67.5, 29.0, 69.5]` | 4 × 4 |
| Tidal-Glass | `[5.0, 53.2, 9.2, 54.2]` | 4 × 4 |

Each `(collection, day)` produces **one** scene whose footprint is a single grid cell inside the
bbox, chosen deterministically by day — so backfilling a range **fills the region tile-by-tile**
(the visual that makes fan-out and gap-closing legible).

---

## Assets & determinism

Each scene carries two PNG assets from one seeded noise field:

- **`data`** — 256×256 **grayscale** PNG (`image/png`, roles `["data"]`): the raw synthetic band.
- **`thumbnail`** — 256×256 **RGB** PNG (`image/png`, roles `["thumbnail"]`): the same field through
  the mission's false-color LUT. This is the tile preview in stac-browser.

> Honest simplification (state it in the README, like the cadence note): real assets would be COG
> GeoTIFFs; we use PNG to stay dependency-light (`pillow` only). The orchestration lessons are
> identical.

**Determinism is load-bearing** (recorded screencasts must not drift):

- One seed: `seed = int.from_bytes(sha256(f"{collection}|{day.isoformat()}").digest()[:8], "big")`.
  All randomness flows from `random.Random(seed)` — never the global RNG, the clock, or `os.urandom`.
- The generator is a **pure function of `(collection, day)`** → byte-identical `data`, `thumbnail`,
  and item JSON across processes and architectures. PNGs carry no `tIME`/`tEXt` chunks; `pillow` is
  pinned. **No I/O in generation** — callers (`download.py`) own writing to S3.
- Per-item properties are deterministic too: `datetime = <day>T10:30:00Z`, `mission`, `platform`,
  `instruments`, `gsd: 20` (fictional). No `created` field (a wall-clock value would break byte-stability).

**Footprint algorithm:**

```
cell_index = seed % (grid_cols * grid_rows)
(col, row) = divmod(cell_index, grid_cols)
polygon    = the (col,row) cell rectangle, inset ~8%, as a closed 5-vertex ring (always inside the bbox)
```

---

## Interface-contract conformance (inherited from `SPEC.md`)

| Contract requirement (parent) | How this world meets it |
|---|---|
| Input `(collection, day)` | `collection ∈ {synthetic-aurora-veil, synthetic-tidal-glass}`, `day: date` |
| **Deterministic** STAC item | pure function of `(collection, day)`; see *Determinism* |
| **Polygon at real coordinates** | grid-cell rectangle inside a real region bbox (Lapland / Wadden Sea) |
| **`data`** asset | 256×256 grayscale PNG, `image/png`, roles `["data"]` |
| **`thumbnail`** asset | 256×256 false-color PNG, `image/png`, roles `["thumbnail"]` |
| `SOURCE_TYPE` real switch unaffected | this is only the `synthetic` backend; `earthsearch` is untouched |

---

## Commands

```bash
# Preview one scene: writes data.png + thumbnail.png to ./out/, prints the STAC item JSON
uv run python -m eo_ingest.synthetic.preview --collection synthetic-aurora-veil --day 2026-03-14

# Determinism + contract gate (offline, fast)
uv run pytest tests/unit/test_synthetic_world.py
```

---

## Project structure (the seam)

Pure generation behind the parent's extractable seam; persistence is the caller's job.

```
src/eo_ingest/synthetic/
├── __init__.py   # public API (the only surface stac_source.py / download.py import)
├── world.py      # the two Mission records as data: id, code, region bbox, grid, palette, platform, instrument
├── generate.py   # seed → footprint polygon + grayscale `data` PNG + false-color `thumbnail` PNG + STAC item dict
└── preview.py    # `python -m eo_ingest.synthetic.preview` dev CLI (non-critical-path)
```

**Public API** (stable):

```python
def iter_missions() -> list[Mission]: ...                    # for seed_stac.py / --list
def render_assets(collection: str, day: date) -> tuple[bytes, bytes]: ...   # (data_png, thumbnail_png)
def build_item(collection: str, day: date, *, data_href: str, thumbnail_href: str) -> dict: ...
```

`synthetic/` imports nothing from Argo, the STAC server, or boto3 — it produces data; `download.py`
writes it and `logbook.py` registers it.

---

## Code style

Python 3.12, `ruff`-formatted, full type hints, small **pure** functions; **no side effects in
generation** (no fs/network/clock). Missions are declarative `dataclass` records in `world.py` —
one generator code path, no per-mission branching. Only added dep here is `pillow`.

---

## Testing strategy

All offline, in `tests/unit` (consistent with the parent's boundaries):

- **Determinism (load-bearing):** `render_assets` / `build_item` byte-identical across calls; the
  PNG sha256 for a fixed `(collection, day)` is pinned. A break is a real failure, not a snapshot to bless.
- **Contract conformance (mirrors the parent's acceptance boundary — don't weaken without approval):**
  output validates as a STAC Item (`pystac`); has exactly `data` + `thumbnail` assets with correct
  roles/type; polygon is a closed ring **inside** the bbox; `datetime` equals the day; id matches
  `MOI-<CODE>_<YYYYMMDD>`; collection carries the `synthetic-` prefix.
- **Registry invariants:** the two missions have unique codes, `synthetic-`-prefixed ids, valid and
  non-overlapping bboxes.
- **Adversarial / boundaries:** leap day, year boundaries, far-past/future days all produce a valid
  scene (generator is total); the two collections on the same day yield different footprints/thumbnails.

---

## Licensing & provenance

- Generated synthetic data → **`CC0-1.0`** (stated in each collection's STAC `license`); generator
  code → Apache-2.0 (repo).
- MOI, the mission names, and palettes are original and IP-safe — no real agency/satellite/trademark,
  no protected fictional names. The `synthetic-` prefix makes the data unmistakably not Sentinel.

---

## Boundaries

**Always:** keep the generator pure, total, deterministic, byte-stable; keep the `synthetic-` prefix;
real coordinates inside the declared bboxes; satisfy the frozen contract exactly; missions stay
declarative in `world.py`.
**Ask first:** changing a region bbox/palette (invalidates the seed *and* recorded clips); adding a
dep beyond `pillow`; changing the asset format or item-id convention; adding a third mission.
**Never:** change the interface contract here (parent-`SPEC.md`'s call); use real/trademarked names;
introduce clock/network/unseeded randomness into generation; imply the data is real; require a
custom basemap; weaken the determinism or contract-conformance tests without approval.

---

## Open Questions

1. **Demo temporal window** (owned by `scripts/seed_stac.py`, not the generator). Recommend one
   ~30-day synthetic month aligned to the rung-2 fan-out tuning. Confirm the month.
2. **`data` as a real COG later?** Recommend **no** for the demo — PNG keeps the seam light.

---

*Living document; companion to `SPEC.md`, whose frozen interface contract it inherits and may not
change. Generator implementation: `src/eo_ingest/synthetic/` (parent tasks T4/T5; seed at T17).*
