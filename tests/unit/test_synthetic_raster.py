"""SW3: deterministic data + thumbnail PNG assets (the load-bearing determinism property)."""

import builtins
import io
from datetime import date

from PIL import Image

from eo_ingest.synthetic.generate import render_assets


def _open(blob: bytes) -> Image.Image:
    return Image.open(io.BytesIO(blob))


def test_render_assets_returns_two_png_blobs() -> None:
    data_png, thumb_png = render_assets("synthetic-aurora-veil", date(2026, 3, 14))
    assert isinstance(data_png, bytes) and isinstance(thumb_png, bytes)
    assert _open(data_png).format == "PNG"
    assert _open(thumb_png).format == "PNG"


def test_data_is_grayscale_256_thumbnail_is_rgb_256() -> None:
    data_png, thumb_png = render_assets("synthetic-aurora-veil", date(2026, 3, 14))
    data_img, thumb_img = _open(data_png), _open(thumb_png)
    assert data_img.mode == "L" and data_img.size == (256, 256)
    assert thumb_img.mode == "RGB" and thumb_img.size == (256, 256)


def test_render_is_byte_identical_across_calls() -> None:
    a = render_assets("synthetic-tidal-glass", date(2026, 3, 14))
    b = render_assets("synthetic-tidal-glass", date(2026, 3, 14))
    assert a == b


def test_two_collections_same_day_differ() -> None:
    av = render_assets("synthetic-aurora-veil", date(2026, 3, 14))
    tg = render_assets("synthetic-tidal-glass", date(2026, 3, 14))
    assert av[0] != tg[0]  # data differs
    assert av[1] != tg[1]  # thumbnail differs


def _anisotropy(data_png: bytes) -> tuple[float, float]:
    """Mean abs neighbour difference along x (h) and along y (v) of the grayscale field."""
    img = _open(data_png)
    px = img.tobytes()  # one byte per pixel for mode "L"
    w, _ = img.size
    h_diff = sum(abs(px[i + 1] - px[i]) for i in range(len(px)) if (i + 1) % w)
    v_diff = sum(abs(px[i + w] - px[i]) for i in range(len(px) - w))
    n = len(px)
    return h_diff / n, v_diff / n


def test_channels_texture_is_horizontally_banded() -> None:
    # Tidal-Glass uses "channels": crossing bands vertically must vary more than along a row.
    h, v = _anisotropy(render_assets("synthetic-tidal-glass", date(2026, 3, 14))[0])
    assert v > 1.3 * h


def test_ribbons_texture_is_not_axis_banded() -> None:
    # Aurora-Veil uses diagonal "ribbons": no strong horizontal/vertical asymmetry.
    h, v = _anisotropy(render_assets("synthetic-aurora-veil", date(2026, 3, 14))[0])
    assert abs(v - h) / max(v, h) < 0.3


def test_render_assets_does_no_file_io(monkeypatch) -> None:
    def _no_open(*args, **kwargs):
        raise AssertionError("render_assets must not touch the filesystem")

    monkeypatch.setattr(builtins, "open", _no_open)
    render_assets("synthetic-aurora-veil", date(2026, 3, 14))  # must not raise


# Golden lock (CP-SW-B): pins the byte output for a fixed (collection, day). A change here means
# either an intended generator change (re-pin deliberately) or a cross-arch/Pillow regression that
# would silently drift recorded screencasts. Generated on arm64 / Pillow 12.2.0; CI re-checks on
# amd64 too. Do not re-bless without understanding why the bytes moved.
_GOLDEN = {
    "synthetic-aurora-veil": (
        "809f55d8d6f3e65fac8077f4341825e4c06090c0ba2bffd1723497675e35b0e8",
        "2429b22c3347d8f8f7b0f50174c9673788dda61f0d8fc319496af628427af8ef",
    ),
    "synthetic-tidal-glass": (
        "5d671bf75cb7a60bb7c040d00e1407d36f7806c749bbe8bf95bd3c3110fe0066",
        "ba02f529ce6ad3b5dc15ac267c81ecc52940af62f70dd1b03eaabad01835c97d",
    ),
}


def test_render_matches_golden_hashes() -> None:
    import hashlib

    for collection, (data_sha, thumb_sha) in _GOLDEN.items():
        data_png, thumb_png = render_assets(collection, date(2026, 3, 14))
        assert hashlib.sha256(data_png).hexdigest() == data_sha
        assert hashlib.sha256(thumb_png).hexdigest() == thumb_sha
