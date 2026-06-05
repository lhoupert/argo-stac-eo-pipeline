"""Local preview CLI for the synthetic world — not on the ingest critical path.

    python -m eo_ingest.synthetic.preview --list
    python -m eo_ingest.synthetic.preview --collection synthetic-aurora-veil --day 2026-03-14

Renders the deterministic assets to ``out/{data,thumbnail}.png`` and prints the STAC item JSON,
so you can eyeball a mission's footprint and false-color look without a cluster.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .generate import build_item, render_assets
from .world import iter_missions


def _list_missions() -> None:
    for m in iter_missions():
        lon_min, lat_min, lon_max, lat_max = m.region_bbox
        print(
            f"{m.collection_id}  (code {m.code}, {m.platform}/{m.instrument})  "
            f"bbox=[{lon_min}, {lat_min}, {lon_max}, {lat_max}]"
        )


def _preview(collection: str, day: date, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    data_png, thumb_png = render_assets(collection, day)
    data_path = out / "data.png"
    thumb_path = out / "thumbnail.png"
    data_path.write_bytes(data_png)
    thumb_path.write_bytes(thumb_png)

    item = build_item(
        collection, day, data_href=str(data_path), thumbnail_href=str(thumb_path)
    )
    print(json.dumps(item, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eo_ingest.synthetic.preview")
    parser.add_argument("--list", action="store_true", help="list missions and exit")
    parser.add_argument("--collection", help="synthetic collection id")
    parser.add_argument("--day", type=date.fromisoformat, help="observation day (YYYY-MM-DD)")
    parser.add_argument("--out", type=Path, default=Path("out"), help="output dir (default: out)")
    args = parser.parse_args(argv)

    if args.list:
        _list_missions()
        return 0

    if not args.collection or not args.day:
        parser.error("--collection and --day are required (or use --list)")

    _preview(args.collection, args.day, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
