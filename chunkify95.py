#!/usr/bin/env python3
"""Recreates a modern app icon in a rough Windows-98-era style: a chunky
low-color pixelation pass with ordered dithering, a black outline traced
around the outer silhouette, then a hand-rolled 3D bevel and drop shadow
layered on top (the parts a pure pixelation pass can't give you: real
Win9x icons are flat-shaded and cel-outlined, closer to comic inking than a
pixelated photo filter, high-contrast, and usually have a hard drop
shadow).

This is a heuristic re-stylization, not true style transfer. It works
reasonably well on simple, high-contrast, single-subject icons (the common
case for app icons) and will look mediocre on busy/photographic ones. See
README.md for what it's actually good and bad at, and for why dithering is
ordered (Bayer) rather than the more obvious Floyd-Steinberg choice.

Usage:
  python3 chunkify95.py --input icon.png --output-dir out/
  python3 chunkify95.py --input icon.png --output-dir out/ --palette win95 --pixel-grid 32
"""
import argparse
import colorsys
import os

from PIL import Image, ImageDraw, ImageFilter

SIZES = [16, 22, 24, 32, 48, 256]

# The real Windows/VGA 16-color palette Win95/98 used for standard desktop
# icons (out of the 256 colors the OS technically supported). Available via
# --palette win95 for a stricter period-accurate look; costs real color
# richness on icons whose hues aren't close to any of these 16 (see
# README's "Dithering").
WIN95_PALETTE = [
    (0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0),
    (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
    (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0),
    (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
]

# The 4 achromatic win95 entries, and the other 12 grouped into dark/bright
# pairs per hue. Used by nearest_win95_color, since plain Euclidean RGB
# distance picks gray for most medium-saturation colors (gray sits centrally
# in RGB space, so it reads as "close" to nearly anything, regardless of
# hue), so matching has to treat hue and grayness as separate questions
# instead of one combined distance. See README's "Palettes".
WIN95_ACHROMATIC = [(0, 0, 0), (128, 128, 128), (192, 192, 192), (255, 255, 255)]
WIN95_HUE_FAMILIES = {
    "red": ((128, 0, 0), (255, 0, 0)),
    "yellow": ((128, 128, 0), (255, 255, 0)),
    "green": ((0, 128, 0), (0, 255, 0)),
    "cyan": ((0, 128, 128), (0, 255, 255)),
    "blue": ((0, 0, 128), (0, 0, 255)),
    "magenta": ((128, 0, 128), (255, 0, 255)),
}


def nearest_win95_color(r, g, b, t=0, sat_threshold=0.22):
    """Hue-aware nearest-color lookup for the fixed win95 palette: pixels
    below the saturation threshold match among black/gray/silver/white by
    brightness only; everything else matches to the closest hue family
    first, then picks that family's dark or bright variant by whichever is
    closer in brightness. Two separate decisions (hue, then lightness)
    instead of one combined RGB distance, which is what lets an actually
    purple pixel land on purple instead of gray.

    sat_threshold started at 0.15 and still let faint anti-aliasing pixels
    through: a pale green-white edge blend like (173, 195, 170), sat 0.13,
    has just enough saturation to read as "basically white" to a person but
    not enough to clear 0.15, so it fell into the achromatic branch and
    matched gray/silver by brightness, showing up as stray gray specks
    inside otherwise-white regions. 0.22 routes those through to their
    actual (faint) hue instead.

    t is the ordered-dither threshold offset (see ordered_dither), applied
    here to brightness only, after hue and saturation are computed from the
    true, unperturbed r/g/b. Earlier this added t to r/g/b uniformly before
    computing hue at all, which meant a strong enough perturbation could
    shift a pixel's hue across a family boundary entirely, a stray cyan
    speck showing up in an otherwise solid blue circle. Hue and grayness are
    stable, real properties of the source pixel; only the dark/bright
    brightness choice should be dithered, so only that step sees t. This is
    what let the default dither spread go up (see pixelate_and_quantize)
    without reintroducing wrong-hue-family noise.
    """
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    v = max(0.0, min(1.0, v + t / 255))
    if s < sat_threshold:
        return min(WIN95_ACHROMATIC, key=lambda c: abs(colorsys.rgb_to_hsv(*(x / 255 for x in c))[2] - v))

    def hue_distance(h1, h2):
        d = abs(h1 - h2)
        return min(d, 1 - d)

    family = min(
        WIN95_HUE_FAMILIES.values(),
        key=lambda pair: hue_distance(h, colorsys.rgb_to_hsv(*(x / 255 for x in pair[0]))[0]),
    )
    dark, bright = family
    dark_v = colorsys.rgb_to_hsv(*(x / 255 for x in dark))[2]
    bright_v = colorsys.rgb_to_hsv(*(x / 255 for x in bright))[2]
    return dark if abs(v - dark_v) < abs(v - bright_v) else bright

# 4x4 Bayer ordered-dither threshold matrix.
BAYER_4X4 = [
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
]


def build_adaptive_palette(img_rgb, colors):
    pal_img = img_rgb.quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.NONE)
    flat = pal_img.getpalette()[:colors * 3]
    return [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]


def _nearest_rgb(r, g, b, t, palette_colors):
    r2 = max(0, min(255, r + t))
    g2 = max(0, min(255, g + t))
    b2 = max(0, min(255, b + t))
    return min(palette_colors, key=lambda c: (c[0] - r2) ** 2 + (c[1] - g2) ** 2 + (c[2] - b2) ** 2)


def ordered_dither(img_rgb, palette_colors, spread=40, match_fn=None):
    """Ordered (Bayer 4x4) dithering: perturbs each pixel by a fixed,
    position-based threshold before nearest-palette-color lookup. Unlike
    error-diffusion dithering (Floyd-Steinberg), each pixel's decision is
    independent of its neighbors' error, so it produces a regular,
    deliberate-looking checkerboard exactly at color-transition zones
    instead of scattered noise across the whole image, much closer to how
    real Win9x icon art dithers shading by hand. spread=0 disables the
    perturbation entirely (plain nearest-color, no dither).

    match_fn(r, g, b, t) -> (r, g, b) overrides the default plain-Euclidean
    nearest-color lookup, receiving the *unperturbed* source pixel plus the
    raw dither threshold t separately rather than pre-perturbed RGB, so a
    hue-aware matcher can dither brightness without letting hue drift. Pass
    nearest_win95_color for palette="win95" (see its docstring). Left as
    plain Euclidean for the adaptive palette, where it's fine: an adaptive
    palette is built from the image's own colors, so nothing in it competes
    with gray for pixels that clearly aren't gray.

    PIL quirk found along the way: passing dither= directly to
    quantize(method=MEDIANCUT, ...) is silently ignored. Verified by
    diffing output with dither=NONE vs. dither=FLOYDSTEINBERG on the same
    call, byte-identical. Even worked around (dither only takes effect
    remapping onto an *already-built* palette), Floyd-Steinberg's cascading
    error was tried and rejected: on a fixed small palette it produces
    chaotic per-pixel noise rather than the sparse, deliberate dithering
    real icons have. This hand-rolled ordered dither replaced it entirely.
    """
    match_fn = match_fn or (lambda r, g, b, t: _nearest_rgb(r, g, b, t, palette_colors))
    w, h = img_rgb.size
    px = img_rgb.load()
    out = Image.new("RGB", (w, h))
    out_px = out.load()
    n = len(BAYER_4X4)
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            t = (BAYER_4X4[y % n][x % n] / (n * n) - 0.5) * spread
            out_px[x, y] = match_fn(r, g, b, t)
    return out


def pixelate_and_quantize(img, grid, colors, palette="adaptive", dither_spread=None):
    """The "pixel analyze" pass: downsample to a small grid (area-averaging,
    so each output pixel is the dominant color of its source block, not just
    a sample), then quantize with ordered dithering (see ordered_dither) at
    this low grid resolution, before the nearest-neighbor upscale, so the
    dither pattern itself comes out as chunky, clearly visible pixel
    squares instead of a fine-grained texture. Then scale back up with
    nearest-neighbor to keep hard pixel edges instead of blur.

    palette="adaptive" (default) builds a best-fit palette of `colors`
    colors for this specific image, keeping the source's actual hues
    recognizable. palette="win95" instead remaps onto the real fixed
    16-color Windows palette (WIN95_PALETTE), matched hue-first via
    nearest_win95_color rather than plain RGB distance (which routes most
    medium-saturation colors to gray regardless of actual hue: see that
    function's docstring).

    dither_spread=None picks a palette-appropriate default: 40 for
    adaptive, 100 for win95. win95 needs more: its hue-family matching only
    has two brightness levels (dark/bright) to dither between per hue, a
    coarser decision than an adaptive palette's finer-grained colors, so a
    flat-shaded region needs a stronger perturbation before the dither
    threshold actually pushes any pixels across that boundary. A spread
    this strong would cause real problems for plain-RGB matching (colors
    jumping to unrelated hues), but nearest_win95_color only ever dithers
    brightness, hue comes from the unperturbed pixel, so pushing spread
    this far is safe and just means denser, more visible checkering.
    """
    w, h = img.size
    size = max(w, h)

    # work on a square canvas so the grid is uniform regardless of aspect
    square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    square.paste(img, ((size - w) // 2, (size - h) // 2), img)

    alpha = square.split()[-1]

    small = square.convert("RGB").resize((grid, grid), Image.BOX)
    if palette == "win95":
        spread = dither_spread if dither_spread is not None else 100
        quantized_rgb = ordered_dither(small, WIN95_PALETTE, spread=spread, match_fn=nearest_win95_color)
    else:
        spread = dither_spread if dither_spread is not None else 40
        palette_colors = build_adaptive_palette(small, colors)
        quantized_rgb = ordered_dither(small, palette_colors, spread=spread)

    small_alpha = alpha.resize((grid, grid), Image.BOX).point(lambda p: 255 if p > 96 else 0)

    pixel_img = Image.new("RGBA", (grid, grid))
    pixel_img.paste(quantized_rgb, (0, 0))
    pixel_img.putalpha(small_alpha)

    return pixel_img.resize((size, size), Image.NEAREST)


def add_pixel_outline(img, grid, thickness=None, color=(20, 20, 20, 255)):
    """Traces a black outline around the outer silhouette only (the
    transparent-to-opaque boundary), not between every internal color
    cell. An early version of this outlined every color boundary, which
    over-inks flat-shaded regions into a stained-glass look real icons don't
    have. Reference icons only hard-outline the overall shape; internal
    color transitions are handled by dithering (see pixelate_and_quantize),
    not by lines.
    """
    size = img.size[0]
    block = size / grid
    thickness = thickness or max(1, round(size / 340))
    px = img.load()

    def cell_opaque(cx, cy):
        if cx < 0 or cy < 0 or cx >= grid or cy >= grid:
            return False
        sx = min(int((cx + 0.5) * block), size - 1)
        sy = min(int((cy + 0.5) * block), size - 1)
        return px[sx, sy][3] >= 10

    out = img.copy()
    draw = ImageDraw.Draw(out)
    for cy in range(grid):
        for cx in range(grid):
            if not cell_opaque(cx, cy):
                continue
            x0, y0 = cx * block, cy * block
            x1, y1 = (cx + 1) * block, (cy + 1) * block
            if not cell_opaque(cx + 1, cy):
                draw.line([(x1, y0), (x1, y1 + thickness)], fill=color, width=thickness)
            if not cell_opaque(cx, cy + 1):
                draw.line([(x0, y1), (x1 + thickness, y1)], fill=color, width=thickness)
            if not cell_opaque(cx - 1, cy):
                draw.line([(x0, y0), (x0, y1 + thickness)], fill=color, width=thickness)
            if not cell_opaque(cx, cy - 1):
                draw.line([(x0, y0), (x1 + thickness, y0)], fill=color, width=thickness)
    return out


def add_bevel(img, thickness=None):
    """A hard light-top-left/dark-bottom-right bevel traced along the alpha
    silhouette's edge, the single most recognizable trait of Win9x icons.
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


def chunkify95(img, pixel_grid=24, colors=12, bevel=True, shadow=True, outline=True, palette="adaptive", dither_spread=None):
    img = img.convert("RGBA")
    out = pixelate_and_quantize(img, pixel_grid, colors, palette, dither_spread)
    if outline:
        out = add_pixel_outline(out, pixel_grid)
    if bevel:
        out = add_bevel(out)
    if shadow:
        out = add_drop_shadow(out)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--pixel-grid", type=int, default=24,
                    help="downsample grid size before upscaling (default: 24). win95 palette benefits from a higher grid (try 32) to compensate for having only 16 colors")
    p.add_argument("--colors", type=int, default=12, help="adaptive palette size, ignored unless --palette adaptive (default: 12)")
    p.add_argument("--palette", choices=["adaptive", "win95"], default="adaptive",
                    help="adaptive (default): best-fit palette per image, keeps real color fidelity. win95: real fixed 16-color VGA palette, more period-accurate but loses hues with no close match.")
    p.add_argument("--dither-spread", type=int, default=None,
                    help="ordered-dither strength, 0 disables (default: 40 for adaptive, 100 for win95)")
    p.add_argument("--bevel", dest="bevel", action="store_true", default=True)
    p.add_argument("--no-bevel", dest="bevel", action="store_false")
    p.add_argument("--shadow", dest="shadow", action="store_true", default=True)
    p.add_argument("--no-shadow", dest="shadow", action="store_false")
    p.add_argument("--outline", dest="outline", action="store_true", default=True)
    p.add_argument("--no-outline", dest="outline", action="store_false")
    p.add_argument("--sizes", default=",".join(str(s) for s in SIZES))
    args = p.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    src = Image.open(args.input)

    master = chunkify95(src, args.pixel_grid, args.colors, args.bevel, args.shadow, args.outline, args.palette, args.dither_spread)
    master_size = 512
    master_out = master.resize((master_size, master_size), Image.LANCZOS) if master.size[0] != master_size else master
    master_out.save(os.path.join(args.output_dir, "icon-master.png"))

    for size in (int(s) for s in args.sizes.split(",")):
        master.resize((size, size), Image.LANCZOS).save(os.path.join(args.output_dir, f"icon-{size}.png"))

    print(f"wrote icon-master.png + {args.sizes} to {args.output_dir}")


if __name__ == "__main__":
    main()
