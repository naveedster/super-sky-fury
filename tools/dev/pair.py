#!/usr/bin/env python3
"""pair.py before_dir after_dir out.png [names...] : side-by-side old|new contact sheet (2x)"""
import sys, os
from PIL import Image, ImageDraw
b, a, out = sys.argv[1:4]
names = sys.argv[4:] or sorted(f[:-4] for f in os.listdir(a) if f.endswith('.ppm'))
rows = []
for n in names:
    ib = Image.open(f"{b}/{n}.ppm").convert("RGB").resize((256, 224)); ia = Image.open(f"{a}/{n}.ppm").convert("RGB").resize((256, 224))
    r = Image.new("RGB", (256 * 2 + 6, 224), (0, 0, 0)); r.paste(ib, (0, 0)); r.paste(ia, (262, 0)); rows.append((n, r))
W = 518; img = Image.new("RGB", (W * 2 + 10, ((len(rows) + 1) // 2) * 240), (16, 16, 16))
d = ImageDraw.Draw(img)
for i, (n, r) in enumerate(rows):
    x = (i % 2) * (W + 10); y = (i // 2) * 240
    img.paste(r, (x, y + 14)); d.text((x + 2, y + 1), f"{n}: before | after", fill=(255, 255, 255))
img.save(out)
