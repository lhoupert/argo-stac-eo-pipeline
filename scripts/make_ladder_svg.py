#!/usr/bin/env python
"""Generate the reusable, color-blind-safe ladder diagram (T28, part a).

Emits `docs/slides/ladder.svg` (neutral) and `ladder-rung0.svg … ladder-rung4.svg` (each with a
"you are here" highlight on one rung). One template, reused in the deck and every stage README.

Color-blind-safe by construction: rung fill uses the Okabe–Ito palette AND every rung carries its
number + name (shape/text redundancy), and the highlight is a gold outline + ★ + label, not colour
alone. Run: `python scripts/make_ladder_svg.py`.
"""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "slides"

# Okabe–Ito (color-blind-safe), one per rung.
RUNGS = [
    ("0", "cron", "#0072B2"),
    ("1", "retries + logbook", "#56B4E9"),
    ("2", "fan-out", "#009E73"),
    ("3", "self-repair", "#E69F00"),
    ("4", "observability", "#D55E00"),
]

_STEP_W, _STEP_H, _DX, _DY, _PAD = 230, 64, 250, 78, 40
_W = _PAD * 2 + _DX * (len(RUNGS) - 1) + _STEP_W
_H = _PAD * 2 + _DY * (len(RUNGS) - 1) + _STEP_H


def _svg(highlight: int | None) -> str:
    rows: list[str] = []
    # bottom rung first so the staircase rises left->right, top-right is rung 4.
    for i, (num, name, fill) in enumerate(RUNGS):
        x = _PAD + _DX * i
        y = _PAD + _DY * (len(RUNGS) - 1 - i)
        active = i == highlight
        stroke = "#F5C200" if active else "#333333"
        sw = 5 if active else 2
        rows.append(
            f'<g><rect x="{x}" y="{y}" width="{_STEP_W}" height="{_STEP_H}" rx="10" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
            f'<text x="{x + 16}" y="{y + 41}" font-family="sans-serif" font-size="26" '
            f'font-weight="700" fill="#ffffff">{num}</text>'
            f'<text x="{x + 48}" y="{y + 41}" font-family="sans-serif" font-size="20" '
            f'fill="#ffffff">{name}</text>'
        )
        if active:
            rows.append(
                f'<text x="{x + _STEP_W - 14}" y="{y - 8}" text-anchor="end" '
                f'font-family="sans-serif" font-size="18" font-weight="700" fill="#B8860B">'
                f'★ you are here</text>'
            )
        rows.append("</g>")
    body = "\n  ".join(rows)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_W} {_H}" '
        f'role="img" aria-label="EO ingestion maturity ladder, rungs 0 to 4">\n'
        f'  <title>Maturity ladder (rungs 0–4)</title>\n  {body}\n</svg>\n'
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ladder.svg").write_text(_svg(None))
    for i in range(len(RUNGS)):
        (OUT / f"ladder-rung{i}.svg").write_text(_svg(i))
    print(f"wrote ladder.svg + {len(RUNGS)} highlighted variants to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
