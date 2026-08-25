#!/usr/bin/env python3
"""Basic smoke tests -- run with: python3 tests/test_smoke.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image

import chunkify95


def make_test_source(path, size=256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.ellipse([size * 0.1, size * 0.1, size * 0.9, size * 0.9], fill=(200, 50, 50, 255))
    img.save(path)


def test_basic_pipeline():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.png")
        make_test_source(src)
        img = Image.open(src)
        out = chunkify95.chunkify95(img)
        assert out.mode == "RGBA"
        assert out.width == out.height
        # a fully-opaque red circle input should still have visible alpha=0
        # corners after pixelation (it doesn't fill the square)
        assert out.getpixel((0, 0))[3] == 0
    print("test_basic_pipeline: OK")


def test_output_sizes():
    with tempfile.TemporaryDirectory() as tmp_in, tempfile.TemporaryDirectory() as tmp_out:
        src = os.path.join(tmp_in, "src.png")
        make_test_source(src)
        img = Image.open(src)
        result = chunkify95.chunkify95(img)
        for size in [16, 32, 48]:
            resized = result.resize((size, size), Image.LANCZOS)
            path = os.path.join(tmp_out, f"icon-{size}.png")
            resized.save(path)
            assert os.path.exists(path)
            reloaded = Image.open(path)
            assert reloaded.size == (size, size)
    print("test_output_sizes: OK")


def test_no_bevel_no_shadow_still_runs():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.png")
        make_test_source(src)
        img = Image.open(src)
        out = chunkify95.chunkify95(img, bevel=False, shadow=False)
        assert out.mode == "RGBA"
    print("test_no_bevel_no_shadow_still_runs: OK")


if __name__ == "__main__":
    test_basic_pipeline()
    test_output_sizes()
    test_no_bevel_no_shadow_still_runs()
    print("\nAll smoke tests passed.")
