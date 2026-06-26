"""SW5: the public API surface and the preview CLI."""

import subprocess
import sys
from pathlib import Path

import eo_ingest.synthetic as synthetic
from eo_ingest.synthetic.preview import main


def test_public_api_exposes_the_generation_callables() -> None:
    # These are the only import surface the rest of eo_ingest should use.
    assert callable(synthetic.iter_missions)
    assert callable(synthetic.render_assets)
    assert callable(synthetic.build_item)
    assert callable(synthetic.build_collection)
    assert set(synthetic.__all__) == {
        "iter_missions",
        "render_assets",
        "build_item",
        "build_collection",
    }


def test_cli_list_lists_both_missions(capsys) -> None:
    assert main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "synthetic-aurora-veil" in out
    assert "synthetic-tidal-glass" in out


def test_cli_writes_both_pngs_and_prints_item_json(tmp_path: Path, capsys) -> None:
    out_dir = tmp_path / "out"
    rc = main(
        ["--collection", "synthetic-aurora-veil", "--day", "2026-03-14", "--out", str(out_dir)]
    )
    assert rc == 0

    data_png = out_dir / "data.png"
    thumb_png = out_dir / "thumbnail.png"
    assert data_png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert thumb_png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    # stdout carries the item JSON.
    assert '"MOI-AV_20260314"' in capsys.readouterr().out


def test_cli_requires_collection_and_day_without_list() -> None:
    # argparse error() exits non-zero rather than silently doing nothing.
    with __import__("pytest").raises(SystemExit) as exc:
        main([])
    assert exc.value.code != 0


def test_python_m_entrypoint_smoke(tmp_path: Path) -> None:
    # Proves the `python -m eo_ingest.synthetic.preview` wiring actually runs and exits 0.
    result = subprocess.run(
        [
            sys.executable, "-m", "eo_ingest.synthetic.preview",
            "--collection", "synthetic-tidal-glass",
            "--day", "2026-03-14",
            "--out", str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert (tmp_path / "out" / "data.png").exists()
