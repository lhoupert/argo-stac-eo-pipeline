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
        "eaa429c029b5973dcf4056198db3642f9a96f9f49eab212d08535763e4b48d22",
        "56cea346a478d8a3ad1ae4d1218cc567ab897220fb94cb1c11820bb89ad62281",
    ),
    "synthetic-tidal-glass": (
        "5d7144bf85a36fff430166720b6f9c63f17081ccc394fde9f3c43731e13a7174",
        "a6d0307ede65cfae6af9db3906b34a76854bc16c9fe1fa78e387e4fc16b0a66d",
    ),
}


def test_render_matches_golden_hashes() -> None:
    import hashlib

    for collection, (data_sha, thumb_sha) in _GOLDEN.items():
        data_png, thumb_png = render_assets(collection, date(2026, 3, 14))
        assert hashlib.sha256(data_png).hexdigest() == data_sha
        assert hashlib.sha256(thumb_png).hexdigest() == thumb_sha
