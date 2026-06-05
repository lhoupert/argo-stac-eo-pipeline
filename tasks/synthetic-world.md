# Plan: Synthetic-World Sub-Package (`src/eo_ingest/synthetic/`)

Detailed breakdown of the `synthetic/` seam. Source of truth: [`SYNTHETIC_WORLD_SPEC.md`](../SYNTHETIC_WORLD_SPEC.md).
This expands the `synthetic/` portion of main-plan [`plan.md`](./plan.md) **T4** (and feeds **T5** download,
**T17** seed). It has **no dependency on `config.py` (T3) or the cluster** — build it right after **T1** (scaffold).

---

## Scope boundary (what this does and does not touch)

- **Builds only `src/eo_ingest/synthetic/`** — *pure generation*: STAC item dicts + asset **bytes**.
- **Does NOT** write to S3 (that's T5 `download.py`) or call the STAC API (T6 `logbook.py`). No Argo, no boto3, no network, no clock.
- **Resolves the seam ambiguity** flagged in review (#2): `build_item(...)` takes asset **hrefs as parameters** — the caller (download → register) owns I/O and decides S3 keys. The per-day "what to ingest" unit is just `(collection, day)`, produced by `stac_source` (T4).

**Consumer contract** (how the rest of `eo_ingest` uses this):
```
stac_source (T4):  enumerate (collection, day) for a window
download   (T5):   render_assets(collection, day) -> (data_png, thumb_png); upload; get S3 hrefs
logbook    (T6):   build_item(collection, day, data_href=…, thumbnail_href=…) -> register()
seed       (T17):  iter_missions() + build_item(...) to plant the catalog (with gaps)
```

---

## Dependency graph

```
T1 scaffold ── SW1 world.py ─┬─ SW2 geometry ──┐
   (main plan)               ├─ SW3 raster ★   ┼─ SW4 build_item ── SW5 __init__ API + preview CLI
                             └─────────────────┘
```
`SW3 (raster)` is the **risk task** — it carries the byte-determinism guarantee. Build it cross-arch-stable from the first commit (see Risks).

---

## Tasks (TDD: RED → GREEN → commit)

### SW1 — `world.py`: Mission records + registry — **S**
The world bible *as data* — one code path for both missions.
- **Acceptance:** a frozen `Mission` dataclass (`collection_id`, `code`, `region_bbox`, `grid` cols×rows, `palette` = 4 hex stops, `platform`, `instrument`) and a registry of the **two** missions (Aurora-Veil/Finnish Lapland `[24.0,67.5,29.0,69.5]`; Tidal-Glass/Wadden Sea `[5.0,53.2,9.2,54.2]`); `iter_missions()` + lookup-by-collection-id with a clear error on unknown id.
- **Verify (`test_synthetic_world.py`):** unique 2-letter codes; every id carries the `synthetic-` prefix; bboxes valid (`lon∈[-180,180]`, `lat∈[-90,90]`, `min<max`) and **non-overlapping**; each palette has exactly 4 stops; unknown collection → error.
- **Deps:** T1.

### SW2 — `geometry.py` (or a `generate.py` fn): deterministic footprint — **S**
- **Acceptance:** `seed(collection, day)` = `sha256("{collection}|{day.isoformat()}")[:8]` → int; `footprint(mission, day)` → a closed 5-vertex GeoJSON polygon for grid cell `seed % (cols*rows)`, inset ~8%, **always inside** the region bbox.
- **Verify (`test_synthetic_geometry.py`):** deterministic (same input → identical ring); ring closed + valid; lies inside the bbox; leap day / year-boundary / far-future days all yield a valid ring (generator is *total*).
- **Deps:** SW1.

### SW3 — `raster.py`: deterministic `data` + `thumbnail` PNGs — **M** ★ RISK
- **Acceptance:** `render_assets(collection, day)` → `(data_png_bytes, thumbnail_png_bytes)`: a seeded field rendered to a **256×256 grayscale** PNG (`data`) and the same field through the mission's **4-stop false-color LUT** to a **256×256 RGB** PNG (`thumbnail`). **Cross-arch byte-stable** (see Risks): integer-only field + integer LUT, **no float resize**, PNGs stripped of `tIME`/`tEXt` chunks.
- **Verify (`test_synthetic_raster.py`):** byte-identical across repeated calls; **pinned sha256** for a fixed `(collection, day)`; PNGs decode as `L` (data) and `RGB` (thumb), both 256×256; purity (no fs/network — guarded); two collections on the same day → different bytes.
- **Deps:** SW1.

### SW4 — `build_item`: contract-valid STAC item — **M**
- **Acceptance:** `build_item(collection, day, *, data_href, thumbnail_href)` → a STAC Item dict: `id = MOI-<CODE>_<YYYYMMDD>`, `collection`, geometry+bbox from SW2, `properties` (`datetime = <day>T10:30:00Z`, `mission`, `platform`, `instruments`, `gsd:20`; **no `created`**), and exactly two assets `data`/`thumbnail` (`image/png`, correct `roles`, given hrefs).
- **Verify (`test_synthetic_item.py`) — contract conformance, mirrors the parent acceptance boundary:** validates via `pystac.Item.from_dict`; exactly `data`+`thumbnail` assets with roles/type; id matches the pattern; `datetime` equals the requested day; collection carries `synthetic-`; geometry inside the bbox.
- **Deps:** SW2.

### SW5 — `__init__.py` public API + `preview.py` CLI — **S**
- **Acceptance:** `__init__` exposes `iter_missions`, `render_assets`, `build_item` (the only import surface). `preview.py` (`python -m eo_ingest.synthetic.preview`): `--collection/--day` writes `out/{data,thumbnail}.png` and prints the item JSON; `--list` prints missions/regions. Non-critical-path.
- **Verify (`test_synthetic_api.py`):** the three callables import from `eo_ingest.synthetic`; CLI smoke in a tmp dir writes both PNGs and exits 0; `--list` lists both missions.
- **Deps:** SW1–SW4.

---

## Checkpoints

- **★ CP-SW-A (after SW1):** registry invariants green (codes/prefixes/bboxes), `iter_missions()` returns both missions.
- **★ CP-SW-B (after SW3) — the load-bearing one:** determinism proven — `render_assets` byte-identical, **pinned hashes hold**, no float math in the path. This is what guarantees recorded screencasts don't drift; treat a break as a real failure, not a snapshot to re-bless.
- **★ CP-SW-C (after SW5):** public API stable; **≥85% coverage of `synthetic/`**; `ruff` + `pytest tests/unit` green. Ready for T4/T5/T17 to consume.

---

## Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **PNG bytes differ across amd64/arm64** (breaks pinned hashes + clips) | **High** | Integer-only noise field + integer LUT; **no Pillow float resize** (use per-pixel values or nearest/integer replication); strip PNG metadata; pin `pillow`. Run the determinism test on **both arches** in CI (main-plan T23). Decide the exact field-generation method in SW3 before coding. |
| Item fails STAC validation on an edge the demo will hit | Med | SW4 validates with `pystac`; adversarial dates (leap/boundary) covered in SW2/SW4. |
| Scope creep into N-mission taxonomy / lore | Low | Spec is already trimmed to two missions; `world.py` stays declarative — add a third mission only when actually needed (rule-of-three). |

---

## Checklist

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · ★ = checkpoint.

- [ ] **SW1** — `world.py` Mission dataclass + 2-mission registry + `iter_missions()`/lookup · `test_synthetic_world.py`
- [ ] ★ **CP-SW-A** — registry invariants green
- [ ] **SW2** — `seed()` + `footprint()` deterministic polygon · `test_synthetic_geometry.py`
- [ ] **SW3** — `render_assets()` byte-stable `data`+`thumbnail` PNGs (cross-arch) · `test_synthetic_raster.py`
- [ ] ★ **CP-SW-B** — determinism proven (pinned hashes, no float path)
- [ ] **SW4** — `build_item()` contract-valid STAC item · `test_synthetic_item.py`
- [ ] **SW5** — `__init__` public API + `preview` CLI · `test_synthetic_api.py`
- [ ] ★ **CP-SW-C** — API stable, ≥85% coverage, lint+unit green; ready for T4/T5/T17

### Definition of done (every SW task)
- [ ] Failing test written first (RED), minimal code to pass (GREEN).
- [ ] `uv run ruff check .` + `uv run pytest tests/unit` green before commit.
- [ ] Generation stays **pure** (no fs/network/clock); only added dep is `pillow`.
- [ ] Commit message explains *why*; every changed line traces to the task.

---

*Derived from `SYNTHETIC_WORLD_SPEC.md`; slots into `plan.md` T4. Prerequisite: main-plan T1 (scaffold).
Build order: SW1 → SW2/SW3 → SW4 → SW5. Update this file if the seam or contract changes, before implementing.*
