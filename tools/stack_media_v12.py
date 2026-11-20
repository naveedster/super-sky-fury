#!/usr/bin/env python3
"""v1.2 sprite-stacking media: shots/sprite_stack_v1_2.png, shots/boss_stack_v1_2.png and
shots/sprite_stack_turntable_v1_2.mp4.
  python3 tools/stack_media_v12.py SHOTS_DIR BEFORE_DIR AFTER_DIR BOSS11_DIR BOSS12_DIR
BEFORE/AFTER_DIR hold in-game PPMs named stage<k>.ppm (k = 0..3) from v1.1 / v1.2; BOSS*_DIR hold b<frame>.ppm."""
import os, struct, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import voxstack as vs, tumble_cfg as tc, boss_vox as bv, boss_art as ba

out, bdir, adir, b11, b12 = sys.argv[1:6]; os.makedirs(out, exist_ok=True)
root = os.path.dirname(here)
st = open(os.path.join(root, "assets/stages.bin"), "rb").read()
import re
STAGE_SZ = int(re.search(r"STAGE_SZ = (\d+)", open(os.path.join(root, "assets/stages.inc")).read()).group(1))
def cg(stage, base):
    o = stage * STAGE_SZ; out_ = []
    for i in range(16):
        v = struct.unpack("<H", st[o + 2 * (base + i):o + 2 * (base + i) + 2])[0]
        out_.append(((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31))
    return np.array(out_, np.uint8)
BG = np.array([28, 32, 56], np.uint8)
def rgb(idx, p, bg=BG):
    a = p[idx].copy(); a[idx == 0] = bg; return a
def up(a, k): return np.kron(a, np.ones((k, k, 1), np.uint8))
def label(img, text, y=2, x=4, col=(255, 230, 120)):
    im = Image.fromarray(img); ImageDraw.Draw(im).text((x, y), text, fill=col); return np.asarray(im)
def hcat(imgs, gap=4, bg=BG):
    h = max(i.shape[0] for i in imgs); cols = []
    for i in imgs:
        c = np.zeros((h, i.shape[1] + gap, 3), np.uint8); c[:] = bg; c[(h - i.shape[0]) // 2:(h - i.shape[0]) // 2 + i.shape[0], :i.shape[1]] = i; cols.append(c)
    return np.hstack(cols)
def vcat(imgs, gap=4, bg=BG):
    w = max(i.shape[1] for i in imgs); rows = []
    for i in imgs:
        r = np.zeros((i.shape[0] + gap, w, 3), np.uint8); r[:] = bg; r[:i.shape[0], :i.shape[1]] = i; rows.append(r)
    return np.vstack(rows)
def title(text, w, h=14):
    a = np.zeros((h, w, 3), np.uint8); a[:] = BG; return label(a, text)
def ppm(d, n): return np.asarray(Image.open(os.path.join(d, n)).convert("RGB"))

# ---------------------------------------------------------------- sprite_stack_v1_2.png
PROPS = vs.prop_models_v12()
STAGE_PROPS = [["carrier", "palms", "oilrig", "bunker"], ["pyramid", "rocks", "radar", "tank"],
               ["iceberg", "pines", "igloo", "turret"], ["carrier", "skyscraper", "oilrig", "bunker"]]
SC = {"carrier": 1.15, "skyscraper": 1.05, "pyramid": 1.25, "iceberg": 1.3, "palms": 1.3}
NAMES = ["OCEAN", "DESERT", "ARCTIC", "NIGHT"]
def prop(t, yaw, size=32): return vs.render(PROPS[t], vs.PROP12_RAMPS, "chase", yaw=yaw, pitch_cam=30, size=size, scale=SC.get(t, 1.4), oy=size / 2 - 3, dither=True, flat_top=0.18)
rows = []
for s in range(4):
    p6 = cg(s, 224); tiles = []
    for t in STAGE_PROPS[s]:
        tiles += [up(rgb(prop(t, y), p6), 2) for y in (0, 45, 90, 135)]
    rows.append(vcat([title(f"{NAMES[s]}: " + ", ".join(STAGE_PROPS[s]) + " (16 streamed yaws each, stage palette)", 1100), hcat(tiles, 2)]))
props_img = vcat(rows)
TM = vs.tumble_models(); trows = []
BPAL = np.array([tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in ba.BOSS_PAL], np.uint8)
def tpal(name):
    k = tc.TUMBLE[name][0]
    return BPAL if k == "boss" else cg(0, {"frame": 176, "jet": 128, "hud": 160}[k])
for name in tc.TUMBLE:
    fr = tc.tumble_frames(TM, name)
    p = tpal(name)
    trows.append(hcat([up(rgb(f, p), 3) for f in fr], 2))
tum_img = vcat([title("TUMBLING OBJECTS: debris x2, missile, enemy missile, capsules P/M/S, crest shard (8 frames each)", 900)] + [hcat(trows[:4], 12), hcat(trows[4:], 12)])
bef = [ppm(bdir, f"stage{k}.ppm") for k in range(4)]; aft = [ppm(adir, f"stage{k}.ppm") for k in range(4)]
ingame = vcat([title("BEFORE (v1.1): the same stage moments - towers / fuel tanks / AA bunkers everywhere, one palette", 1100), hcat(bef, 4),
               title("AFTER (v1.2): per-stage voxel props (carriers, rigs, palms / pyramids, radar, tanks / icebergs, pines, igloos, turrets / lit towers), night palettes", 1100), hcat(aft, 4)])
sheet = vcat([label(np.full((18, 1100, 3), BG, np.uint8), "SUPER SKY FURY v1.2 - more sprite stacking", x=4, col=(255, 255, 255)), ingame, props_img, tum_img])
Image.fromarray(sheet).save(os.path.join(out, "sprite_stack_v1_2.png")); print("sprite_stack_v1_2.png", sheet.shape)

# ---------------------------------------------------------------- boss_stack_v1_2.png
fr, S = bv.build_all()
bp = np.array([tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in ba.BOSS_PAL], np.uint8)
def boss(img): return rgb(img, bp)
poses = [(0, ("down", "down")), (18, ("cannon", "down")), (-36, ("spread", "spread")), (36, ("down", "cannon"))]
after = [boss(bv.compose(fr, S, *a)) for a in poses]
dmg = dict(fr); dmg["body"] = fr["body_dmg"]
after.append(boss(bv.compose(dmg, S, 0, ("down", "down"))))
old = boss(np.pad(ba.render(False), ((40, 40), (56, 56))))
row1 = hcat([vcat([title("v1.1: flat 2D art", 220), up(old, 1)])] + [vcat([title(t, 220), a]) for t, a in zip(
    ["v1.2: voxel, head ahead", "head 18 right, L cannon", "head 36 left, spread", "head 36 right, R cannon", "damage: holes, scorch"], after)], 6)
parts = [vcat([title(k, 210), boss(fr[k])]) for k in ("body", "body_dmg", "head0", "head18", "head36", "arm_down", "arm_cannon", "arm_spread")]
row2 = vcat([title("parts (sprite-stacked offline, cut into 16x16 cells, deduped / mirrored; head, arms and body drawn as separate layers)", 1300), hcat(parts[:4], 6), hcat(parts[4:], 6)])
ig = vcat([title("in game - top v1.1, bottom v1.2 (same frames of the boss test run)", 1300),
           hcat([ppm(b11, f) for f in ("b1300.ppm", "b1700.ppm", "b2100.ppm", "b2500.ppm")], 4),
           hcat([ppm(b12, f) for f in ("b1300.ppm", "b1700.ppm", "b2100.ppm", "b2500.ppm")], 4)])
bimg = vcat([row1, row2, ig])
Image.fromarray(bimg).save(os.path.join(out, "boss_stack_v1_2.png")); print("boss_stack_v1_2.png", bimg.shape)

# ---------------------------------------------------------------- turntable mp4 (640x360, 30 fps, 12 s)
tmp = tempfile.mkdtemp(); W_, H_ = 640, 360; N = 360
p_stage = [cg(s, 224) for s in range(4)]
for i in range(N):
    a = i * 360 / N
    can = np.zeros((H_, W_, 3), np.uint8); can[:] = BG
    im = Image.fromarray(can); d = ImageDraw.Draw(im)
    d.text((8, 6), "SUPER SKY FURY v1.2 - sprite-stacked voxel models", fill=(255, 255, 255))
    can = np.asarray(im).copy()
    # boss: head sweeps, arms cycle poses
    k = (i // 45) % 4; hy = [0, 18, 36, 18, 0, -18, -36, -18][(i // 22) % 8]
    arms = [("down", "down"), ("cannon", "down"), ("spread", "spread"), ("down", "cannon")][k]
    bimg_ = bv.compose(fr if i < N // 2 else dmg, S, hy, arms)
    b = boss(bimg_)
    can[30:30 + S, 8:8 + S] = b
    # props: 4 stages x 4 models, all turning
    s = (i // 90) % 4
    for j, t in enumerate(STAGE_PROPS[s]):
        f = up(rgb(prop(t, a + j * 30), p_stage[s]), 2)
        x0 = 240 + (j % 2) * 96; y0 = 40 + (j // 2) * 96
        can[y0:y0 + 64, x0:x0 + 64] = f
    im = Image.fromarray(can); d = ImageDraw.Draw(im); d.text((240, 236), NAMES[s] + " props", fill=(255, 230, 120))
    can = np.asarray(im).copy()
    # tumble objects
    for j, name in enumerate(tc.TUMBLE):
        frs = tc.tumble_frames(TM, name) if i == 0 else TF[name]
        if i == 0:
            TF = globals().setdefault("TF", {}); TF[name] = frs
        p = tpal(name)
        f = up(rgb(frs[(i // 4 + j) % 8], p), 3)
        x0 = 440 + (j % 4) * 50; y0 = 50 + (j // 4) * 60
        can[y0:y0 + 48, x0:x0 + 48] = f
    Image.fromarray(can).save(f"{tmp}/f{i:04d}.png")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", f"{tmp}/f%04d.png", "-vf", "scale=1280:720:flags=neighbor",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", os.path.join(out, "sprite_stack_turntable_v1_2.mp4")], check=True)
print("turntable ok")
