#!/usr/bin/env python3
"""Recreates a modern app icon in a rough Windows-98-era style: a chunky
low-color pixelation pass, then a hand-rolled 3D bevel and drop shadow layered
on top (the parts a pure pixelation pass can't give you, since real Win9x
icons weren't just "modern icon but blockier" -- they were beveled, high-
contrast, and usually had a hard drop shadow).

This is a heuristic re-stylization, not true style transfer -- it works
reasonably well on simple, high-contrast, single-subject icons (the common
case for app icons) and will look mediocre on busy/photographic ones. See
README.md for what it's actually good and bad at.

Usage:
  python3 chunkify95.py --input icon.png --output-dir out/
  python3 chunkify95.py --input icon.png --output-dir out/ --pixel-grid 20 --colors 12 --no-bevel
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFilter

SIZES = [16, 22, 24, 32, 48, 256]


def pixelate_and_quantize(img, grid, colors):
    """The "pixel analyze" pass: downsample to a small grid (area-averaging,
    so each output pixel is the dominant color of its source block, not just
    a sample), then quantize to a limited palette, then scale back up with
    nearest-neighbor to keep hard pixel edges instead of blur.
    """
    w, h = img.size
    size = max(w, h)

    # work on a square canvas so the grid is uniform regardless of aspect
    square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    square.paste(img, ((size - w) // 2, (size - h) // 2), img)

    alpha = square.split()[-1]

    small = square.convert("RGB").resize((grid, grid), Image.BOX)
    quantized = small.quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.NONE)
    quantized_rgb = quantized.convert("RGB")

    small_alpha = alpha.resize((grid, grid), Image.BOX).point(lambda p: 255 if p > 96 else 0)

    pixel_img = Image.new("RGBA", (grid, grid))
    pixel_img.paste(quantized_rgb, (0, 0))
    pixel_img.putalpha(small_alpha)

    return pixel_img.resize((size, size), Image.NEAREST)


def add_bevel(img, thickness=None):
    """A hard light-top-left/dark-bottom-right bevel traced along the alpha
    silhouette's edge -- the single most recognizable trait of Win9x icons.
    Approximated by compositing a slightly-offset lighter/darker copy of the
    silhouette behind the original, rather than true per-pixel edge tracing.
    """
    size = img.size[0]
    thickness = thickness or max(1, size // 64)

    alpha = img.split()[-1]
    silhouette = Image.new("RGBA", img.size, (0, 0, 0, 0))
    silhouette.paste((255, 255, 255, 255), (0, 0), alpha)

    highlight = Image.new("RGBA", img.size, (0, 0, 0, 0))
    highlight.paste((255, 255, 255, 200), (-thickness, -thickness), alpha)

    shadow_edge = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_edge.paste((40, 40, 40, 200), (thickness, thickness), alpha)

    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(shadow_edge)
    out.alpha_composite(highlight)
    out.alpha_composite(img)
    return out


def add_drop_shadow(img, offset=None, blur=None, opacity=140):
    size = img.size[0]
    offset = offset or max(2, size // 32)
    blur = blur if blur is not None else max(2, size // 48)

    alpha = img.split()[-1]
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, opacity), (0, 0), alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))

    canvas = Image.new("RGBA", img.size, (0, 0, 0, 0))
    canvas.alpha_composite(shadow, (offset, offset))
    canvas.alpha_composite(img)
    return canvas


def chunkify95(img, pixel_grid=24, colors=16, bevel=True, shadow=True):
    img = img.convert("RGBA")
    out = pixelate_and_quantize(img, pixel_grid, colors)
    if bevel:
        out = add_bevel(out)
    if shadow:
        out = add_drop_shadow(out)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--pixel-grid", type=int, default=24, help="downsample grid size before upscaling (default: 24)")
    p.add_argument("--colors", type=int, default=16, help="palette size (default: 16)")
    p.add_argument("--bevel", dest="bevel", action="store_true", default=True)
    p.add_argument("--no-bevel", dest="bevel", action="store_false")
    p.add_argument("--shadow", dest="shadow", action="store_true", default=True)
    p.add_argument("--no-shadow", dest="shadow", action="store_false")
    p.add_argument("--sizes", default=",".join(str(s) for s in SIZES))
    args = p.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    src = Image.open(args.input)

    master = chunkify95(src, args.pixel_grid, args.colors, args.bevel, args.shadow)
    master_size = 512
    master_out = master.resize((master_size, master_size), Image.LANCZOS) if master.size[0] != master_size else master
    master_out.save(os.path.join(args.output_dir, "icon-master.png"))

    for size in (int(s) for s in args.sizes.split(",")):
        master.resize((size, size), Image.LANCZOS).save(os.path.join(args.output_dir, f"icon-{size}.png"))

    print(f"wrote icon-master.png + {args.sizes} to {args.output_dir}")


if __name__ == "__main__":
    main()
