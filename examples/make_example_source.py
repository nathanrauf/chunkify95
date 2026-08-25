#!/usr/bin/env python3
"""Generates an original, unencumbered example icon (a simple gear) purely to
demonstrate chunkify95.py in this repo without bundling anyone's trademarked
logo. Run this, then run chunkify95.py on its output, to reproduce README.md's
before/after."""
import math
import os

from PIL import Image, ImageDraw

S = 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

cx, cy = S // 2, S // 2
outer_r = 190
inner_r = 130
hub_r = 70
teeth = 8

pts = []
for i in range(teeth * 2):
    angle = (2 * math.pi / (teeth * 2)) * i
    r = outer_r if i % 2 == 0 else inner_r
    pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))

d.polygon(pts, fill=(90, 140, 90, 255))
d.ellipse([cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r], fill=(240, 240, 235, 255))
d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=(90, 140, 90, 255))

img.save(os.path.join(os.path.dirname(__file__), "gear-source.png"))
print("wrote gear-source.png")
