#!/usr/bin/env python3
"""v1.1 sprite stacking previews: before/after sheet + a turntable mp4 of the voxel models.
  python3 tools/sprite_stack_preview.py SHOTS_DIR [ingame_before.ppm ingame_after.ppm]
Runs tools/gen_assets.py into a scratch dir to get the models, ramps and the game palette."""
import os, runpy, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw

out_dir = sys.argv[1]; os.makedirs(out_dir, exist_ok=True)
here = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
argv = sys.argv; sys.argv = [os.path.join(here, "gen_assets.py"), tmp]
cwd = os.getcwd(); os.chdir(os.path.dirname(here))
G = runpy.run_path(os.path.join(here, "gen_assets.py"), run_name="ga")
os.chdir(cwd); sys.argv = argv
vs = G["vs"]; CG = G["CGRAM"]
def pal(n): return np.array([CG[128 + 16 * n + i] for i in range(16)], np.uint8)
PJ, PE, PO = pal(0), pal(3), pal(6)
SKY = np.array([110, 162, 228], np.uint8)
def rgb(idx, p, bg=SKY):
    a = p[idx]; a[idx == 0] = bg; return a
def up(a, k): return np.kron(a, np.ones((k, k, 1), np.uint8))
def pad_to(a, h, w, bg=SKY):
    o = np.zeros((h, w, 3), np.uint8); o[:] = bg; o[(h - a.shape[0]) // 2:(h - a.shape[0]) // 2 + a.shape[0], (w - a.shape[1]) // 2:(w - a.shape[1]) // 2 + a.shape[1]] = a; return o
def strip(imgs, h, gap=4):
    cols = [pad_to(i, h, i.shape[1] + gap) for i in imgs]; return np.hstack(cols)

# ---------------------------------------------------------------- before / after sheet
K = 3
before = [rgb(G["render_jet_poly"]("chase", r, 64, 1.9, pitch_deg=38), PJ) for r in (0, 22, 44)]
before += [rgb(G["render_enemy_poly"]("chase", 0, y, 32, 1.02), PE) for y in (180, 0)]
before += [rgb(G["render_bomber_poly"](32, 0.98), PE)]
after_j = [rgb(f, PJ) for f in G["jet_frames"]]
after_e = [rgb(f, PE) for f in G["EN_YAWS"]]
after_p = [rgb(G["PROP_NEAR"][t][d], PO) for t in (0, 2, 3) for d in (0, 2, 4, 6)]
after_b = [rgb(G["render_bomber"](32, 0.98), PE)]
rows = [("BEFORE (v1.1 polygon renders): jet 3 banks, enemy toward/away, bomber", strip(before, 64)),
        ("AFTER: voxel sprite-stacked jet, 5 banks x level / climb / dive (one streamed 64x64 VRAM slot)", strip(after_j[:5], 64)),
        ("", strip(after_j[5:10], 64)), ("", strip(after_j[10:], 64)),
        ("AFTER: enemy fighter, 16 yaws (9 unique + h-flip), streamed 32x32 slots; bomber", strip(after_e + after_b, 32)),
        ("AFTER: ground props on the Mode 7 plane (tower / fuel tanks / AA bunker), 16 yaws each", strip(after_p, 32))]
W = max(r[1].shape[1] for r in rows) * K + 40
blocks = []
for title, a in rows:
    a = up(a, K); h = a.shape[0] + (26 if title else 6)
    b = Image.new("RGB", (W, h), (16, 20, 32)); b.paste(Image.fromarray(a), (20, h - a.shape[0] - 3))
    if title: ImageDraw.Draw(b).text((20, 6), title, fill=(255, 230, 120))
    blocks.append(np.array(b))
if len(argv) > 3:
    ga = np.array(Image.open(argv[2]).convert("RGB")); gb = np.array(Image.open(argv[3]).convert("RGB"))
    pair = np.hstack([up(ga, 2), np.zeros((ga.shape[0] * 2, 16, 3), np.uint8), up(gb, 2)])
    b = Image.new("RGB", (W, pair.shape[0] + 30), (16, 20, 32)); b.paste(Image.fromarray(pair), (20, 26))
    d = ImageDraw.Draw(b); d.text((20, 6), "IN GAME, same frame: before", fill=(255, 230, 120))
    d.text((20 + pair.shape[1] // 2 + 8, 6), "after (sprite-stacked jet, enemies, ground props)", fill=(255, 230, 120))
    blocks.append(np.array(b))
Wm = max(b.shape[1] for b in blocks)
sheet = np.vstack([np.pad(b, ((0, 0), (0, Wm - b.shape[1]), (0, 0))) for b in blocks])
Image.fromarray(sheet).save(os.path.join(out_dir, "sprite_stack_before_after.png"))

# ---------------------------------------------------------------- turntable mp4
fr_dir = tempfile.mkdtemp()
VJ, VE, VB = G["VOX_JET"], G["VOX_EN"], G["VOX_BOMB"]
P = G["PROPS12"]
N = 360
for i in range(N):
    yaw = i * 360.0 / 120          # 3 turns
    k16 = round(yaw / 22.5) * 22.5  # what the game shows: the nearest of 16 yaws
    roll = 40 * np.sin(i / N * 2 * np.pi * 2)
    j = rgb(vs.render(VJ, G["JET_RAMPS"], "chase", roll=roll, yaw=yaw, pitch_cam=38, size=64, scale=1.9, oy=-2), PJ)
    e = rgb(vs.render(VE, G["EN_RAMPS"], "chase", yaw=k16, size=32, scale=1.02), PE)
    b = rgb(vs.render(VB, G["EN_RAMPS"], "chase", yaw=k16, pitch_cam=52, size=32, scale=0.98), PE)
    ps = [rgb(G["render_prop"](t, k16, 32, 1.4, 30), PO) for t in ("carrier", "oilrig", "bunker")]   # (v1.2 models)
    top = pad_to(j, 72, 96); bot = strip([e, b] + ps, 40)
    img = np.vstack([pad_to(top, 72, bot.shape[1]), bot])
    img = up(img, 5)
    im = Image.fromarray(img); d = ImageDraw.Draw(im)
    d.text((8, 6), "SUPER SKY FURY v1.1 - voxel models, sprite-stacked (SNES OBJ palettes)", fill=(255, 255, 255))
    d.text((8, 22), f"jet: yaw {yaw % 360:5.1f}  bank {roll:+5.1f}   others: game's 16-yaw frames", fill=(255, 240, 160))
    im = im.resize((im.width // 2 * 2, im.height // 2 * 2))
    im.save(os.path.join(fr_dir, f"f{i:04d}.png"))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", os.path.join(fr_dir, "f%04d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", os.path.join(out_dir, "sprite_stack_turntable.mp4")], check=True)
print("wrote", os.path.join(out_dir, "sprite_stack_before_after.png"), os.path.join(out_dir, "sprite_stack_turntable.mp4"))
