# chunkify95

Recreates a modern app icon in a rough Windows-98-era style: pixel-analyze
the source down to a chunky low-color grid, then layer on a hand-rolled 3D
bevel and hard drop shadow, the two things that actually make an icon read
as "Win98" and that a pixelation pass alone won't give you.

| Source | Result | Source | Result |
|---|---|---|---|
| ![gear source](examples/gear-source.png) | ![gear win98](examples/gear-win98.png) | ![Firefox source](examples/firefox-source.png) | ![Firefox win98](examples/firefox-win98.png) |
| ![Chromium source](examples/chromium-source.png) | ![Chromium win98](examples/chromium-win98.png) | ![Steam source](examples/steam-source.png) | ![Steam win98](examples/steam-win98.png) |
| ![Code - OSS source](examples/code-oss-source.png) | ![Code - OSS win98](examples/code-oss-win98.png) | | |

The gear is the original demo asset. The rest come from the
[Papirus icon theme](https://github.com/PapirusDevelopmentTeam/papirus-icon-theme)
(GPL-3.0), specifically its icons for Firefox, Chromium, Steam, and Code -
OSS, the open-source upstream projects, not Google's Chrome or Microsoft's
Visual Studio Code builds. See "Why these and not the real corporate logos"
below for why that distinction matters.

Built to plug the icon gap in [chicago95-plus](https://github.com/nathanrauf/chicago95-plus)
(a Chicago95-on-Cinnamon companion pack). Chicago95's icon theme covers a
lot, but not everything you actually have installed, and this is the tool
for whatever's left over.

## Usage

```sh
python3 chunkify95.py --input icon.png --output-dir out/
```

Produces `icon-master.png` (512×512) plus `icon-16.png` .. `icon-256.png`
(the standard icon-theme sizes) in `out/`.

Options:

```
--pixel-grid N   downsample grid before upscaling back up (default: 24)
--colors N       palette size (default: 16)
--no-bevel       skip the 3D bevel pass
--no-shadow      skip the drop shadow
--sizes 16,32,48 comma-separated output sizes
```

## How it works

1. **Pixel-analyze**: the source is pasted onto a square canvas, downsampled
   to an `N×N` grid with box (area-average) filtering, so each output cell
   is the *dominant* color of its source region rather than a single sampled
   pixel, then quantized to a limited palette (`Image.quantize`, median-cut).
   The alpha channel is thresholded separately so transparency stays crisp
   instead of picking up quantization noise.
2. **Upscale with nearest-neighbor** back to full size, keeping hard pixel
   edges instead of blur.
3. **Bevel**: a lighter copy of the icon's silhouette is offset up-left and
   a darker copy down-right, both composited behind the pixelated icon,
   approximating the light-top/dark-bottom 3D edge every real Win9x icon has,
   without actually tracing per-pixel normals.
4. **Drop shadow**: a blurred, offset black copy of the silhouette, behind
   everything.

## What it's good at

Simple, high-contrast, single-subject icons: logos, glyphs, app marks. I
tested it against VS Code's and Thunderbird's real icons during development
(not included here, see below) and got genuinely recognizable, distinctly
Win98-flavored results even at 16px.

## What it's not good at

This is a heuristic re-stylization, not true style transfer, and I'd rather
say that up front than let you find out from a muddy result. It will
struggle with:

- **Photographic or gradient-heavy icons**: median-cut quantization on a
  smooth gradient produces visible banding rather than a clean palette; the
  block-averaging can also muddy fine detail into an indistinct blob.
- **Icons that are already mostly white/near-transparent**: the alpha
  threshold in the pixelation pass can clip soft edges more aggressively
  than intended.
- **Very detailed/busy icons**: anything with lots of small internal detail
  will lose most of it at low `--pixel-grid` values; raising the grid size
  helps but starts to look less authentically chunky.

If a result looks muddy, try a smaller `--pixel-grid` (more aggressive,
often *more* legible) or fewer `--colors`.

## Why these and not the real corporate logos

A company's actual logo file is their trademarked artwork, current and
actively enforced. Fine to run this tool against your own desktop's real
icons locally. Not fine to redistribute transformed copies of Google's
Chrome icon or Microsoft's VS Code icon in this repo.

Papirus's icons are a different case: original artwork drawn by the Papirus
project, released under their own GPL-3.0 license, and (where one exists)
drawn for the open-source upstream project rather than the corporate build:
Chromium instead of Chrome, Code - OSS instead of VS Code. Firefox and Steam
don't have that same open/corporate split, so those two are Papirus's own
GPL-licensed renditions of the real apps.

`examples/gear-source.png` is the one fully original placeholder, generated
by `make_example_source.py`. The rasterized Papirus SVGs came from:

```sh
rsvg-convert -w 512 -h 512 /usr/share/icons/Papirus/64x64/apps/firefox.svg -o firefox-source.png
rsvg-convert -w 512 -h 512 /usr/share/icons/Papirus/64x64/apps/chromium.svg -o chromium-source.png
rsvg-convert -w 512 -h 512 /usr/share/icons/Papirus/64x64/apps/steam.svg -o steam-source.png
rsvg-convert -w 512 -h 512 /usr/share/icons/Papirus/64x64/apps/code-oss.svg -o code-oss-source.png
```
