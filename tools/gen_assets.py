#!/usr/bin/env python3
"""Generates every graphic/table for SNES FLY. All art is procedural (no assets copied)."""
import math, os, random, struct, sys
import numpy as np
from PIL import Image, ImageDraw

OUT = sys.argv[1] if len(sys.argv) > 1 else "assets"
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(1234)
random.seed(1234)

def hexrgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def bgr555(c):
    r, g, b = c; return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)

# ----------------------------------------------------------------- palette
CGRAM = [(0, 0, 0)] * 256
def setpal(start, cols):
    for i, c in enumerate(cols): CGRAM[start + i] = hexrgb(c) if isinstance(c, str) else c

# ground colours: see tools/terrain.py (Mode 7 uses CGRAM 1..27, 32..47, 112..127 directly)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain

# BG palette 3 (48-63) cockpit/dash, 4 (64-79) yellow text, 5 (80-95) green digits
DASH = ["#000000", "#16181c", "#24272d", "#34383f", "#474c55", "#5e646e", "#7c838e", "#f07818",
        "#a84a0c", "#0e2a12", "#1f6a2a", "#3ee05a", "#c8ffd0", "#d82020", "#e8e8e0", "#ffc020"]
setpal(48, DASH)
setpal(64, ["#000000", "#ffd838", "#1e1400", "#b08a10", "#fff6c0", "#f09018"] + ["#000000"] * 10)
setpal(80, ["#000000", "#5cff6c", "#041a08", "#2a9a3a", "#d4ffd8", "#22b83a"] + ["#000000"] * 10)
setpal(96, ["#000000", "#ff4a38", "#200300", "#b01c10", "#ffd0a0", "#c82010"] + ["#000000"] * 10)   # BG pal 6: red text / warnings
# OBJ palettes (128..255)
JET = ["#000000", "#0c1014", "#283040", "#3c4658", "#566278", "#74849c", "#9cacc4", "#ccd8e8",
       "#f07a1a", "#ffb848", "#162e58", "#3c7cc8", "#c0ecff", "#ffffff", "#fff0a0", "#d83418"]
setpal(128, JET)
CLOUD = ["#000000", "#ffffff", "#eef6ff", "#d4e4f4", "#b4cae2", "#94aed0", "#f8fcff", "#ff6a10",
         "#ffa020", "#fff060", "#ffffff", "#c8dcf0", "#000000", "#000000", "#000000", "#000000"]
setpal(144, CLOUD)
HUD = ["#000000", "#50ff60", "#2a9a3a", "#0c3a14", "#3a78d8", "#8a5a2a", "#ffffff", "#c0ffc8",
       "#1c1c20", "#ff9020", "#000000", "#000000", "#000000", "#000000", "#000000", "#000000"]
setpal(160, HUD)
FRAME = ["#000000", "#16181c", "#24272d", "#34383f", "#474c55", "#5e646e", "#f07818", "#a84a0c",
         "#4a0c0c", "#9a1a16", "#d83a2a", "#ff8a6c", "#98a0aa", "#dce2ea", "#ffe070", "#1c3050"]   # 8-15: enemy jets
setpal(176, FRAME)
setpal(192, ["#000000"] + ["#000000"] * 15)     # shadow palette (half-transparent black via color math)
setpal(208, ["#000000"] + ["#ffffff"] * 15)     # translucent white (overhead contrails)
# enemy type palettes (chase/cockpit only; overhead keeps palette 3 because colour math blends 4-7 there)
setpal(224, FRAME[:8] + ["#2a3416", "#566c2c", "#80984a", "#b4c884", "#9aa0a8", "#e0d4a0", "#ffe070", "#12283a"])  # olive camo + ocean props (v1.2: recoloured per stage)
setpal(240, FRAME[:8] + ["#121a34", "#26386a", "#4060a8", "#7c9ce4", "#5a6274", "#a8b0c0", "#ffd040", "#401010"])  # navy

# ----------------------------------------------------------------- periodic noise
def pnoise(size, period, seed):
    r = np.random.default_rng(seed).random((period, period))
    xs = np.arange(size) * period / size
    i0 = np.floor(xs).astype(int); f = xs - i0; f = f * f * (3 - 2 * f)
    i1 = (i0 + 1) % period; i0 %= period
    a = r[np.ix_(i0, i0)]; b = r[np.ix_(i0, i1)]; c = r[np.ix_(i1, i0)]; d = r[np.ix_(i1, i1)]
    fy = f[:, None]; fx = f[None, :]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy
def fbm(size, base, octaves, seed):
    tot = np.zeros((size, size)); amp = 1; s = 0
    for o in range(octaves):
        tot += amp * pnoise(size, base * 2 ** o, seed + o); s += amp; amp *= 0.5
    return tot / s

# ----------------------------------------------------------------- terrain
G = terrain.build(CGRAM, OUT)
# v1.1: a second, land-heavy map (desert / arctic stages): big landmasses around inland seas and canyons
_CG2 = list(CGRAM)
terrain.build(_CG2, OUT, rng_seed=4321, suffix="B", nseed=500, islands=[
    (130, 130, 92), (390, 130, 84), (130, 390, 86), (392, 392, 96), (256, 256, 44), (256, 40, 34), (40, 256, 30),
    (470, 256, 36), (256, 470, 32), (200, 200, 30), (320, 330, 28), (60, 60, 26), (470, 60, 22)])

# ----------------------------------------------------------------- tile helpers
def to4bpp(t):  # t 8x8 indices 0..15
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            v = int(t[y][x]); bit = 7 - x
            out[y * 2] |= (v & 1) << bit; out[y * 2 + 1] |= ((v >> 1) & 1) << bit
            out[16 + y * 2] |= ((v >> 2) & 1) << bit; out[16 + y * 2 + 1] |= ((v >> 3) & 1) << bit
    return bytes(out)

# ----------------------------------------------------------------- tiny 3D jet renderer
# ----------------------------------------------------------------- shaded 3D sprite renderer (graphics v1)
# Polygons carry a material; each face is lit (lambert, light from above-front-left) and the material
# ramp picks the palette index, so banking frames shade themselves.
LIGHT = np.array([-0.25, -0.30, 0.92]); LIGHT = LIGHT / np.linalg.norm(LIGHT)
def render_shaded(polys, ramps, view, roll_deg, yaw_deg, size, scale, pitch_deg=50, ss=4, oy=0, outline=1,
                  decals=()):
    W = size * ss; img = Image.new("P", (W, W), 0); dr = ImageDraw.Draw(img)
    ph = math.radians(roll_deg); al = math.radians(pitch_deg); yw = math.radians(yaw_deg)
    cam = np.array([0, 0, 1.0]) if view == "top" else np.array([0, math.cos(al), math.sin(al)])
    out_polys = []
    for pts, mat in polys:
        w3 = []
        for x, y, z in pts:
            xr = x * math.cos(ph) + z * math.sin(ph); zr = -x * math.sin(ph) + z * math.cos(ph)
            xr, yr = xr * math.cos(yw) - y * math.sin(yw), xr * math.sin(yw) + y * math.cos(yw)
            w3.append((xr, yr, zr))
        P3 = np.array(w3)
        n = np.zeros(3)
        for i in range(len(P3)):
            a_, b_ = P3[i], P3[(i + 1) % len(P3)]
            n += np.array([(a_[1] - b_[1]) * (a_[2] + b_[2]), (a_[2] - b_[2]) * (a_[0] + b_[0]), (a_[0] - b_[0]) * (a_[1] + b_[1])])
        nn = np.linalg.norm(n); n = n / nn if nn > 1e-9 else np.array([0, 0, 1.0])
        if n @ cam < 0: n = -n
        lam = 0.18 + 0.82 * max(0.0, float(n @ LIGHT))
        if view == "top": lam = 0.42 + 0.58 * max(0.0, float(abs(n @ LIGHT)))   # seen from above: keep banked frames readable
        tp = []
        for xr, yr, zr in w3:
            if view == "top": sx, sy, dep = xr, yr, zr
            else: sx = xr; sy = -zr * math.cos(al) + yr * math.sin(al); dep = yr * math.cos(al) + zr * math.sin(al)
            tp.append((sx, sy, dep))
        r_ = ramps[mat]
        c = r_[min(len(r_) - 1, max(0, int(lam ** 1.5 * len(r_))))] if isinstance(r_, (list, tuple)) else r_
        out_polys.append((sum(p[2] for p in tp) / len(tp), tp, c))
    out_polys.sort(key=lambda p: p[0])
    for _, tp, c in out_polys:
        dr.polygon([((p[0] * scale + size / 2) * ss, (p[1] * scale + size / 2 + oy) * ss) for p in tp], fill=c)
    a = np.array(img)
    out = np.zeros((size, size), np.uint8)
    for y in range(size):
        for x in range(size):
            blk = a[y * ss:(y + 1) * ss, x * ss:(x + 1) * ss].reshape(-1)
            nz = blk[blk > 0]
            if len(nz) * 2 >= len(blk) or (len(nz) >= 5 and len(nz) * 3 > len(blk)):
                out[y, x] = np.bincount(nz).argmax()
    if outline:
        o = out.copy()
        for y in range(size):
            for x in range(size):
                if out[y, x] == 0:
                    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                        yy_, xx_ = y + dy, x + dx
                        if 0 <= yy_ < size and 0 <= xx_ < size and out[yy_, xx_] not in (0, outline):
                            o[y, x] = outline; break
        out = o
    return out

def jet_polys():
    P = []
    def sym(pts, m):
        P.append((pts, m)); P.append(([(-x, y, z) for x, y, z in pts][::-1], m))
    sym([(0, -16, 1.6), (2.2, -11, 1.8), (3.2, -5, 2.0), (3.6, 8, 2.0), (3.0, 15, 1.6), (0, 15, 2.3)], "body")
    sym([(0, -16, 1.7), (1.0, -12, 2.0), (1.2, 12, 2.4), (0, 13, 2.5)], "spine")
    sym([(0, -16, 1.6), (1.1, -14.6, 1.7), (0.5, -13.6, 1.9), (0, -14, 1.9)], "radome")
    sym([(3.0, -2, 0.8), (14.5, 8, 0.6), (14.5, 10.8, 0.6), (3.6, 9.5, 0.8)], "wing")
    sym([(3.0, -2, 0.85), (14.5, 8, 0.65), (13.8, 8.5, 0.65), (3.0, -0.6, 0.85)], "edge")
    sym([(6.0, 6.4, 0.75), (13.6, 10.0, 0.62), (13.6, 10.7, 0.62), (6.2, 8.6, 0.75)], "flap")
    sym([(13.2, 8.2, 0.7), (14.8, 8.0, 0.7), (14.8, 11.0, 0.7), (13.4, 10.6, 0.7)], "tip")
    sym([(3.4, 10, 0.9), (9.5, 14, 0.8), (9.5, 15.8, 0.8), (3.2, 14.5, 0.9)], "wing")
    sym([(3.3, -6, 1.6), (4.3, -4, 1.4), (4.3, 1, 1.4), (3.4, 1, 1.6)], "dark")
    sym([(3.0, 6.5, 1.9), (3.1, 13.5, 1.9), (5.2, 14.5, 7.0), (4.8, 10.5, 7.0)], "fin")
    sym([(4.8, 10.5, 7.0), (5.2, 14.5, 7.0), (5.05, 13.8, 6.1), (4.65, 10.3, 6.2)], "tip")
    sym([(3.7, 9.6, 3.6), (4.25, 12.6, 4.6), (4.3, 13.6, 4.3), (3.75, 10.6, 3.3)], "stripe")
    sym([(0.3, 14.2, 1.3), (2.7, 14.2, 1.3), (2.7, 17.0, 1.3), (0.3, 17.0, 1.3)], "dark")
    sym([(0.7, 16.6, 1.35), (2.3, 16.6, 1.35), (2.3, 17.1, 1.35), (0.7, 17.1, 1.35)], "glow")
    # roundels on the wings
    for cx, cy in ((9.2, 6.4), (-9.2, 6.4)):
        P.append(([(cx + math.cos(a) * 1.55, cy + math.sin(a) * 1.25, 0.9) for a in np.linspace(0, 2 * math.pi, 9)[:-1]], "rnd_o"))
        P.append(([(cx + math.cos(a) * 0.7, cy + math.sin(a) * 0.6, 0.95) for a in np.linspace(0, 2 * math.pi, 7)[:-1]], "rnd_i"))
    P.append(([(0, -11, 2.4), (1.4, -8, 2.6), (1.4, -3.5, 2.6), (0, -1.5, 2.5), (-1.4, -3.5, 2.6), (-1.4, -8, 2.6)], "canopy"))
    P.append(([(0, -10.5, 2.7), (0.8, -8, 2.8), (0.6, -5, 2.8), (0, -6, 2.8)], "glint"))
    return P
# JET palette: 2-7 blue-grey ramp, 8/9 orange, 10-12 canopy, 13 white, 14 pale yellow, 15 red
JET_RAMPS = {"body": [2, 3, 4, 5, 6], "spine": [3, 4, 5, 6, 7], "wing": [2, 3, 4, 5, 6, 6], "edge": [4, 5, 6, 7],
             "flap": [2, 3, 3, 4, 5], "tip": [15, 8, 8], "fin": [2, 3, 4, 5, 6], "dark": 1, "glow": 9,
             "stripe": [15, 15, 8], "rnd_o": [10, 11, 11], "rnd_i": 13, "radome": [2, 3, 3, 4],
             "canopy": [10, 10, 11, 11], "glint": [11, 12, 12, 13]}
def render_jet(view, roll_deg, size, scale, pitch_deg=50, ss=4):
    return render_shaded(jet_polys(), JET_RAMPS, view, roll_deg, 0, size, scale, pitch_deg, ss,
                         oy=0 if view == "top" else -2)

def circle_blob(size, circles, seed=0, shade=True):
    """fluffy cloud: union of circles; light from top-left"""
    a = np.zeros((size, size), np.uint8)
    yy_, xx_ = np.mgrid[0:size, 0:size] + 0.5
    inside = np.zeros((size, size), bool); lum = np.full((size, size), -9.0)
    for cx, cy, r in circles:
        d = np.sqrt((xx_ - cx) ** 2 + (yy_ - cy) ** 2)
        m = d < r; inside |= m
        l = ((cx - xx_) * 0.7 + (cy - yy_) * 0.9) / r   # >0 toward top-left of each puff
        lum = np.where(m, np.maximum(lum, l), lum)
    a[inside] = 1
    a[inside & (lum < 0.05)] = 2
    a[inside & (lum < -0.35)] = 3
    a[inside & (lum < -0.65)] = 4
    # bottom edge outline
    edge = inside & ~np.roll(inside, -1, 0)
    a[edge] = 5
    return a

def make_cloud(size, n, seed):
    r = random.Random(seed); circ = []
    cx0 = size / 2
    for i in range(n):
        t = i / max(1, n - 1)
        x = size * (0.22 + 0.56 * t) + r.uniform(-2, 2)
        rad = size * r.uniform(0.15, 0.22) * (1.25 - abs(t - 0.5))
        y = size * 0.62 - rad * 0.6 + r.uniform(-2, 2)
        circ.append((x, y, rad))
    circ.append((cx0 + r.uniform(-4, 4), size * 0.40, size * 0.24))
    circ.append((cx0 + size * 0.15, size * 0.48, size * 0.18))
    return circle_blob(size, circ, seed)

# ----------------------------------------------------------------- OBJ sheet packer
class Sheet:
    """OBJ sheet (16 x 32 tiles). put() queues a graphic; pack() places them biggest first so the
    16x16 pieces never fragment the 32x32 / 64x64 grid."""
    def __init__(self):
        self.a = np.zeros((256, 128), np.uint8); self.used = np.zeros((32, 16), bool); self.syms = {}; self.sizes = {}
        self.queue = []
    def put(self, name, g):
        self.queue.append((name, np.asarray(g, np.uint8)))
    def pack(self):
        for name, g in sorted(self.queue, key=lambda q: -q[1].size):
            self.place(name, g)
        self.queue = []
        free = int((~self.used).sum())
        return free
    def place(self, name, g):
        h_, w_ = g.shape; th, tw = h_ // 8, w_ // 8
        for ty in range(0, 32 - th + 1, th):
            for tx in range(0, 16 - tw + 1, tw):
                if not self.used[ty:ty + th, tx:tx + tw].any():
                    self.used[ty:ty + th, tx:tx + tw] = True
                    self.a[ty * 8:ty * 8 + h_, tx * 8:tx * 8 + w_] = g
                    self.syms[name] = ty * 16 + tx; self.sizes[name] = (th, tw); return
        raise RuntimeError("sheet full " + name)
    def free(self, names):
        for name in names:
            t = self.syms.pop(name); th, tw = self.sizes.pop(name); ty, tx = divmod(t, 16)
            self.used[ty:ty + th, tx:tx + tw] = False
            self.a[ty * 8:ty * 8 + th * 8, tx * 8:tx * 8 + tw * 8] = 0
    def bin(self):
        out = bytearray()
        for ty in range(32):
            for tx in range(16):
                out += to4bpp(self.a[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8])
        return bytes(out)

def pad(g, size):
    out = np.zeros((size, size), np.uint8); h_, w_ = g.shape
    out[(size - h_) // 2:(size - h_) // 2 + h_, (size - w_) // 2:(size - w_) // 2 + w_] = g; return out

clouds_big = [make_cloud(64, 5, 11), make_cloud(64, 4, 23)]
clouds_small = [make_cloud(32, 3, 5), make_cloud(32, 3, 8)]
def dot(size, px, c=1):
    g = np.zeros((32, 32), np.uint8); g[0:px, 0:px] = c
    if px >= 3: g[0, 0] = g[0, px - 1] = g[px - 1, 0] = g[px - 1, px - 1] = 0
    return g
def flame(size, h_, frame, view):
    g = np.zeros((32, 32), np.uint8)
    for side in ((-1, 1) if view == "chase" else (0,)):
        cx = 16 + side * 4
        L = h_ + (2 if frame else 0)
        for y in range(L):
            w = max(0.6, 2.4 * (1 - y / L))
            for x in range(32):
                d = abs(x + 0.5 - cx)
                if d < w + 0.6:
                    g[y, x] = 9 if d < w * 0.4 and y < L * 0.5 else (8 if d < w * 0.8 else 7)
    return g

# ----------------------------------------------------------------- enemies, explosions, debris, bullets
# Enemy jets use OBJ palette 3 (cockpit frame greys + new reds in slots 8-15); explosions use the
# player-jet palette 0 (white/yellow/orange/red + greys for smoke). Both stay clear of palettes 4-7,
# which colour math half-blends in the overhead view.
# Enemy jets: palette 3 (red), 6 (olive camo) or 7 (navy/yellow) by type. Indices 1-5 greys,
# 8-11 paint ramp, 12/13 light metal, 14 glow, 15 canopy.
def enemy_polys():
    P = []
    def sym(pts, m):
        P.append((pts, m)); P.append(([(-x, y, z) for x, y, z in pts][::-1], m))
    sym([(0, -15, 1.6), (1.8, -11, 1.9), (2.6, -4, 2.0), (2.8, 9, 2.0), (2.2, 14, 1.7), (0, 14, 2.2)], "body")
    sym([(0, -15, 1.7), (0.8, -11, 2.1), (1.0, 11, 2.4), (0, 12, 2.5)], "spine")
    sym([(2.4, -5, 0.9), (13.5, 9.5, 0.7), (12.5, 11.5, 0.7), (2.8, 10.5, 0.9)], "wing")
    sym([(2.4, -5, 0.95), (13.5, 9.5, 0.75), (12.6, 10.2, 0.75), (2.4, -3.4, 0.95)], "edge")
    sym([(5.0, 7.5, 0.82), (11.0, 10.3, 0.74), (10.6, 11.1, 0.74), (5.0, 10.0, 0.82)], "metal")
    sym([(12.2, 9.4, 0.8), (13.8, 9.3, 0.8), (13.0, 11.6, 0.8), (12.0, 11.4, 0.8)], "tip")
    sym([(1.8, -10.5, 1.4), (5.6, -7.5, 1.3), (5.6, -6.6, 1.3), (1.9, -7.4, 1.4)], "wing")
    sym([(1.6, 6.5, 1.9), (1.8, 13.5, 1.9), (3.6, 14.6, 7.2), (3.2, 10.6, 7.2)], "fin")
    sym([(3.2, 10.6, 7.2), (3.6, 14.6, 7.2), (3.5, 13.8, 6.0), (3.1, 10.4, 6.1)], "tip")
    sym([(0.4, 13.4, 1.4), (2.2, 13.4, 1.4), (2.2, 15.6, 1.4), (0.4, 15.6, 1.4)], "dark")
    sym([(0.7, 15.2, 1.45), (1.9, 15.2, 1.45), (1.9, 15.8, 1.45), (0.7, 15.8, 1.45)], "glow")
    P.append(([(0, -10.5, 2.4), (1.3, -7.5, 2.6), (1.3, -3.5, 2.6), (0, -1.8, 2.5), (-1.3, -3.5, 2.6), (-1.3, -7.5, 2.6)], "canopy"))
    P.append(([(0, -10, 2.7), (0.7, -7.6, 2.8), (0.5, -5, 2.8), (0, -6, 2.8)], "glint"))
    return P
EN_RAMPS = {"body": [3, 4, 5, 12, 13], "spine": [4, 5, 12, 13, 13], "wing": [8, 9, 9, 10, 11], "edge": [9, 10, 11, 11],
            "metal": [3, 4, 5, 12], "tip": [8, 13, 13], "fin": [8, 9, 10, 11], "dark": 1, "glow": 14,
            "canopy": [15, 15, 2], "glint": [2, 5, 13]}
def render_enemy(view, roll_deg, yaw_deg, size, scale, pitch_deg=38, ss=4, outline=True):
    return render_shaded(enemy_polys(), EN_RAMPS, view, roll_deg, yaw_deg, size, scale, pitch_deg, ss,
                         outline=1 if outline else 0)

# ----------------------------------------------------------------- v1.1 sprite stacking (tools/voxstack.py)
# The plan-form polygons above are voxelized into solid models; every frame is a sprite-stacked render.
import voxstack as vs
import tumble_cfg
TUMBLE_MODELS = vs.tumble_models()
TUMBLE_FR = {k: tumble_cfg.tumble_frames(TUMBLE_MODELS, k) for k in tumble_cfg.TUMBLE}   # v1.2: 8 frames each
# v1.5 DKC-style glossy lighting (key light + Blinn-Phong specular streak + warm back rim; voxstack.render)
GLOSS_JET = dict(spec=1.4, shine=40, rim=1.1, hi=13, hi_t=0.5, rimc=14, rim_t=0.42, diff=0.9,
                 matte=('dark', 'glow', 'canopy', 'glint', 'rnd_i', 'stripe', 'tip', 'rnd_o'))
GLOSS_EN = dict(GLOSS_JET, matte=('dark', 'glow', 'canopy', 'glint', 'tip'))
GLOSS_PROP = dict(spec=1.2, shine=30, rim=0.0, hi="top", hi_t=0.5,
                  only=('hull', 'deck', 'steel', 'dish', 'metal', 'gun', 'pad', 'glass', 'ice', 'wallp'))
VOX_JET = vs.voxelize(jet_polys(), 0.4, fill={"body": 0.9, "spine": 0.9, "canopy": 2.25, "radome": 0.9})
VOX_EN = vs.voxelize(enemy_polys(), 0.4, fill={"body": 0.9, "spine": 0.9, "canopy": 2.2})
render_jet_poly = render_jet; render_enemy_poly = render_enemy
def render_jet(view, roll_deg, size, scale, pitch_deg=50, ss=4, nose=0.0):
    return vs.render(VOX_JET, JET_RAMPS, view, roll=roll_deg, pitch_cam=pitch_deg, size=size, scale=scale,
                     oy=0 if view == "top" else -2, nose_pitch=nose, gloss=GLOSS_JET)
def render_enemy(view, roll_deg, yaw_deg, size, scale, pitch_deg=38, ss=4, outline=True):
    return vs.render(VOX_EN, EN_RAMPS, view, roll=roll_deg, yaw=yaw_deg, pitch_cam=pitch_deg, size=size, scale=scale,
                     outline=1 if outline else 0, dither=size > 16, gloss=GLOSS_EN if size > 16 else {})

def tiny(rows, size=16):
    """hand-drawn tiny sprite, centred in a size x size cell. rows: strings of palette digits/hex."""
    g = np.zeros((size, size), np.uint8); h_ = len(rows); w_ = len(rows[0])
    y0 = (size - h_) // 2; x0 = (size - w_) // 2
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != '.': g[y0 + y, x0 + x] = int(ch, 16)
    return g

def _blobfield(size, radius, seed, nblobs=7, spread=(0.3, 0.75), rad=(0.35, 0.6)):
    r = np.random.default_rng(seed)
    yy_, xx_ = np.mgrid[0:size, 0:size] + 0.5
    c = size / 2
    blobs = [(c, c, radius)]
    for i in range(nblobs):
        a_ = r.uniform(0, 2 * math.pi); d = r.uniform(*spread) * radius
        blobs.append((c + math.cos(a_) * d, c + math.sin(a_) * d, radius * r.uniform(*rad)))
    heat = np.full((size, size), -1.0); lit = np.full((size, size), -9.0)
    for bx, by, br in blobs:
        dd = np.sqrt((xx_ - bx) ** 2 + (yy_ - by) ** 2) / br
        lit = np.where(1 - dd > heat, ((bx - xx_) * 0.7 + (by - yy_) * 0.8) / br, lit)
        heat = np.maximum(heat, 1 - dd)
    heat = np.where(heat > 0, heat + r.normal(0, 0.05, heat.shape), heat)
    return heat, lit, r

def fireball(size, radius, seed, smoke=0.0, core=1.0):
    # palette 0: 13 white, 14 pale yellow, 9 light orange, 8 orange, 15 red, 2-6 greys for smoke
    heat, lit, r = _blobfield(size, radius, seed)
    v = heat * (0.8 + 0.2 * core) + np.clip(lit, -1, 1) * 0.12
    g = np.zeros((size, size), np.uint8)
    for th, col in [(0.0, 15), (0.12, 8), (0.30, 9), (0.48, 14), (0.66, 13)]:
        g[(heat > 0) & (v > th * (2 - core))] = col
    if smoke > 0:
        sm = (heat > 0) & (heat < smoke)
        g[sm] = np.where(lit[sm] > 0.2, 5, np.where(lit[sm] > -0.3, 4, 3))
        g[sm & (r.random(sm.shape) < 0.12)] = 15            # embers in the smoke
    # dark rim on the lower right for weight
    rim = (heat > 0) & (heat < 0.06) & (lit < -0.2) & (g != 0)
    g[rim] = 2 if smoke > 0 else 15
    return g

def flash_star(size=16):
    g = np.zeros((size, size), np.uint8); c = size / 2
    yy_, xx_ = np.mgrid[0:size, 0:size] + 0.5
    d = np.sqrt((xx_ - c) ** 2 + (yy_ - c) ** 2)
    ang = np.arctan2(yy_ - c, xx_ - c)
    star = d < 2.6 + 4.6 * np.abs(np.cos(ang * 2)) ** 6
    g[star] = 8; g[star & (d < 4.5)] = 9; g[d < 3.6] = 14; g[d < 2.3] = 13
    return g

def smoke_puff(size, radius, seed, embers=False, light=False):
    heat, lit, r = _blobfield(size, radius, seed, nblobs=6, spread=(0.0, 0.6), rad=(0.45, 0.7))
    g = np.zeros((size, size), np.uint8)
    base = [2, 3, 4, 5, 6] if light else [2, 3, 4, 5]
    m = heat > 0
    s = np.clip(lit * 0.5 + 0.5 + heat * 0.3, 0, 0.999)
    g[m] = np.array(base)[(s[m] * len(base)).astype(int)]
    if embers:
        e = m & (heat > 0.35) & (r.random(m.shape) < 0.25)
        g[e] = np.where(r.random(e.sum()) < 0.5, 8, 15)
    return g

def puff_small():
    return tiny(["..676..",
                 ".67D76.",
                 "67DDD76",
                 "7DDDD76",
                 "67DD765",
                 ".66765.",
                 "..555.."], 16)

def shard(seed, size=16):
    r = random.Random(seed); img = Image.new("P", (size * 4, size * 4), 0); d = ImageDraw.Draw(img)
    pts = [(size * 2 + math.cos(a_) * rr * 4, size * 2 + math.sin(a_) * rr * 4)
           for a_, rr in ((0.3, 5.5), (1.6, 3.0), (2.4, 4.5), (3.6, 2.5), (4.5, 5.0), (5.6, 2.2))]
    pts = [(x + r.uniform(-3, 3), y + r.uniform(-3, 3)) for x, y in pts]
    d.polygon(pts, fill=4)
    d.line(pts[:3], fill=13 - 12 + 12, width=4)
    a = np.array(img)[::4, ::4].copy()
    a[a == 13] = 12
    o = a.copy()
    for y in range(size):
        for x in range(size):
            if a[y, x] == 0 and any(0 <= y + dy < size and 0 <= x + dx < size and a[y + dy, x + dx]
                                    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0))):
                o[y, x] = 1
    o[(a == 4) & (np.add.outer(np.arange(size), np.arange(size)) % 5 == 0)] = 9    # red paint flecks
    return o

def bullet(near):
    """tracer: white-hot head, yellow body, orange tail"""
    g = np.zeros((16, 16), np.uint8)
    if near:
        g[2:4, 7:9] = 13; g[4:7, 7:9] = 14; g[7:10, 7:9] = 9; g[10:13, 7:9] = 8; g[13, 7:9] = 15
        g[3:6, 6] = 9; g[3:6, 9] = 9
    else:
        g[5:7, 7:9] = 13; g[7:9, 7:9] = 14; g[9:11, 7:9] = 8
    return g

def missile_spr():
    return tiny(["...1111...",
                 "..1DDDD1..",
                 ".16DDDDD61",
                 "1D6DDDD6D1",
                 ".1DD99DD1.",
                 "..1E88E1..",
                 "...1F81...",
                 "....F8....",
                 "....8F...."], 16) 

def ebullet(near):
    if near:
        return tiny(["...FFFF...",
                     "..F7777F..",
                     ".F78EE87F.",
                     "F78EDDE87F",
                     "F7EDDDDE7F",
                     "F7EDDDDE7F",
                     "F78EDDE87F",
                     ".F78EE87F.",
                     "..F7777F..",
                     "...FFFF..."], 16)
    return tiny([".FF.",
                 "F7EF",
                 "FE7F",
                 ".FF."], 16)

def emissile():
    return tiny([".....1.....",
                 "....8E8....",
                 "...8E5E8...",
                 "..8E666E8..",
                 ".1E66F66E1.",
                 "155E6DFE551",
                 ".1E66F66E1.",
                 "..8E666E8..",
                 "...8E5E8...",
                 "....8E8....",
                 ".....1....."], 16)

def enemy_frames_persp(include_away=True, include_bank=True):
    f = {}
    f["EL_TOW"] = render_enemy("chase", 0, 180, 32, 1.02)
    if include_away: f["EL_AWAY"] = render_enemy("chase", 0, 0, 32, 1.02)
    f["EM"] = render_enemy("chase", 0, 180, 16, 0.50)
    if include_bank: f["EM_BANK"] = render_enemy("chase", 35, 180, 16, 0.50)
    f["ES"] = render_enemy("chase", 0, 180, 16, 0.36, outline=False)
    f["EXS"] = tiny(["...D...", "9AABAA9", ".8CDC8.", "..1.1.."])
    f["EXXS"] = tiny(["ADDA", ".99."])
    return f

import boom17, boom18
BOOM18 = boom18.boom_seq(24); SMOKE18 = boom18.smoke_seq(12); FLAME18 = boom18.flame_seq(16); BFLAME18 = boom18.bflame_seq(16)
FX_HOME_A, FX_HOME_B, FX_HOME_C = 3, 13, 2
OLD_BOOM = bool(os.environ.get('OLD_BOOM'))
def fx_frames(two_big=True, two_debris=True, extra=True):
    f = {}
    if OLD_BOOM:
        f["X32A"] = fireball(32, 10.5, 3, core=1.15)
        if two_big: f["X32B"] = fireball(32, 14.0, 9, smoke=0.22, core=0.9)
    else:                                     # v1.7: glossy ray-traced billows, shockwave ring, debris (tools/boom17.py)
        f["X32A"] = BOOM18[FX_HOME_A]          # v1.8: the sheet holds the streamed sequences' home frames
        if two_big: f["X32B"] = BOOM18[FX_HOME_B]
    f["X16A"] = flash_star(16)
    f["X16B"] = smoke_puff(16, 6.2, 4, light=True) if OLD_BOOM else boom17.smoke16(4)
    if extra:
        f["X16C"] = smoke_puff(16, 6.6, 12, embers=True) if OLD_BOOM else SMOKE18[FX_HOME_C]
        if extra != "nopuff": f["PUFF"] = puff_small()
    f["DEB0"] = TUMBLE_FR["DEB0"][0]          # v1.2: sprite-stacked, streamed tumbling frames (frame 0 here)
    if two_debris: f["DEB1"] = TUMBLE_FR["DEB1"][0]
    f["BUL0"] = bullet(True); f["BUL1"] = bullet(False)
    f["MSL"] = TUMBLE_FR["MSL"][0]
    f["EBUL0"] = ebullet(True); f["EBUL1"] = ebullet(False); f["EMSL"] = TUMBLE_FR["EMSL"][0]
    return f

# ----------------------------------------------------------------- v1.1 art: bomber, sky fortress, power-ups, hit spark, popup font
def bomber_polys(span=15.0, eng=(5.0, 10.0), length=16.0, chord=1.0):
    P = []
    def sym(pts, m):
        P.append((pts, m)); P.append(([(-x, y, z) for x, y, z in pts][::-1], m))
    L = length
    sym([(0, -L, 1.8), (2.2, -L + 4, 2.2), (2.8, -2, 2.3), (2.6, L - 4, 2.0), (1.4, L, 1.8), (0, L, 2.3)], "body")
    sym([(0, -L, 1.9), (1.0, -L + 4, 2.5), (1.0, L - 3, 2.6), (0, L - 2, 2.7)], "spine")
    c = chord
    sym([(2.6, -3.0 * c, 1.2), (span, -1.0 * c, 1.0), (span, 2.6 * c, 1.0), (2.6, 4.0 * c, 1.2)], "wing")
    sym([(2.6, -3.0 * c, 1.25), (span, -1.0 * c, 1.05), (span, -0.2 * c, 1.05), (2.6, -2.2 * c, 1.25)], "edge")
    for ex in eng:
        sym([(ex - 1.2, -6.0, 1.0), (ex + 1.2, -6.0, 1.0), (ex + 1.2, 2.0, 1.0), (ex - 1.2, 2.0, 1.0)], "metal")
        sym([(ex - 0.9, -6.6, 1.05), (ex + 0.9, -6.6, 1.05), (ex + 0.9, -5.4, 1.05), (ex - 0.9, -5.4, 1.05)], "dark")
        sym([(ex - 0.5, 1.6, 1.1), (ex + 0.5, 1.6, 1.1), (ex + 0.5, 2.6, 1.1), (ex - 0.5, 2.6, 1.1)], "glow")
    sym([(1.4, L - 4, 1.9), (6.5, L - 2.5, 1.7), (6.5, L - 0.8, 1.7), (1.4, L - 0.6, 1.9)], "wing")
    sym([(4.8, L - 4.0, 1.8), (5.2, L - 0.8, 1.8), (5.4, L - 0.6, 6.4), (5.0, L - 3.2, 6.2)], "fin")
    P.append(([(0, -L + 1.5, 2.5), (1.3, -L + 3.8, 2.8), (1.3, -L + 6.5, 2.8), (0, -L + 7.5, 2.7), (-1.3, -L + 6.5, 2.8), (-1.3, -L + 3.8, 2.8)], "canopy"))
    P.append(([(0, -L + 2.0, 2.9), (0.6, -L + 3.8, 3.0), (0.4, -L + 5.0, 3.0), (0, -L + 4.4, 3.0)], "glint"))
    return P

def render_bomber_poly(size, scale, **kw):
    return render_shaded(bomber_polys(chord=1.4, **kw), EN_RAMPS, "chase", 0, 180, size, scale, 52, 4, outline=1)
BOMB_FILL = {"body": 1.1, "spine": 1.1, "canopy": 2.3, "metal": 0.3}
VOX_BOMB = vs.voxelize(bomber_polys(chord=1.4), 0.4, fill=BOMB_FILL)
def render_bomber(size, scale, **kw):
    return vs.render(VOX_BOMB, EN_RAMPS, "chase", yaw=180, pitch_cam=52, size=size, scale=scale, dither=size > 16,
                     gloss=GLOSS_EN if size > 16 else {})

def fortress_cells():
    """the mid-boss: a 96x32 six-engine sky fortress, cut into a centre cell and a left-wing cell
    (the right wing is the left one h-flipped)"""
    vf = vs.voxelize(bomber_polys(span=44.0, eng=(6.5, 17.0, 30.0), length=15.0, chord=2.2), 0.4, fill=BOMB_FILL)
    big = vs.render(vf, EN_RAMPS, "chase", yaw=180, pitch_cam=56, size=96, scale=1.04, gloss=GLOSS_EN)
    ys = np.nonzero(big.any(axis=1))[0]; cy = (ys.min() + ys.max() + 1) // 2
    y0 = max(0, min(96 - 32, cy - 16)); band = big[y0:y0 + 32]
    left = band[:, 0:32].copy(); centre = band[:, 32:64].copy()
    return centre, left

def capsule(letter, body):
    """16x16 power-up capsule, HUD palette 2: 8 = dark outline, 6 = white, 7 = highlight"""
    g = np.zeros((16, 16), np.uint8)
    yy_, xx_ = np.mgrid[0:16, 0:16] + 0.5
    d = np.maximum(np.abs(xx_ - 8) - 3.0, 0) ** 2 + (yy_ - 8) ** 2
    g[d < 6.6 ** 2] = 8
    g[d < 5.4 ** 2] = body
    g[(d < 5.4 ** 2) & (yy_ < 4.6)] = 7 if body != 9 else 14 - 8
    F = {"P": ["111.", "1..1", "111.", "1...", "1..."], "M": ["1...1", "11.11", "1.1.1", "1...1", "1...1"],
         "S": [".111", "1...", ".11.", "...1", "111."]}[letter]
    w = len(F[0]); x0 = 8 - w // 2 - (0 if w % 2 else 0); y0 = 5
    for y, r in enumerate(F):
        for x, ch in enumerate(r):
            if ch == '1':
                g[y0 + y, x0 + x] = 6
                if g[y0 + y + 1, x0 + x] not in (6,): g[y0 + y + 1, x0 + x] = 8
    return g

def hit_spark():
    """impact spark: thin 4-point white-hot star (palette 0: 13 white, 14 yellow, 9/8 orange)"""
    g = np.zeros((16, 16), np.uint8); c = 7.5
    for y in range(16):
        for x in range(16):
            dx, dy = abs(x - c), abs(y - c)
            ray = (dx < 0.9 and dy < 7.6) or (dy < 0.9 and dx < 7.6)
            diag = abs(dx - dy) < 0.8 and dx < 3.8
            if ray or diag:
                r_ = max(dx, dy)
                g[y, x] = 13 if r_ < 2.2 else (14 if r_ < 4.2 else (9 if r_ < 6 else 8))
            if dx * dx + dy * dy < 4.2: g[y, x] = 13
    return g

POPFONT = "0123456789+x"
POP_GLYPHS = {
    '0': ["1111", "1..1", "1..1", "1..1", "1..1", "1111"], '1': [".11.", "111.", ".11.", ".11.", ".11.", "1111"],
    '2': ["1111", "...1", "1111", "1...", "1...", "1111"], '3': ["1111", "...1", ".111", "...1", "...1", "1111"],
    '4': ["1..1", "1..1", "1111", "...1", "...1", "...1"], '5': ["1111", "1...", "1111", "...1", "...1", "1111"],
    '6': ["1111", "1...", "1111", "1..1", "1..1", "1111"], '7': ["1111", "...1", "..1.", ".1..", ".1..", ".1.."],
    '8': ["1111", "1..1", "1111", "1..1", "1..1", "1111"], '9': ["1111", "1..1", "1111", "...1", "...1", "1111"],
    '+': ["....", ".11.", "1111", "1111", ".11.", "...."], 'x': ["....", "1..1", ".11.", ".11.", "1..1", "...."]}
def pop_glyph(ch, col):
    """8x8 popup character: 4x6 bold glyph (colour col) with a 1 px dark outline (8), HUD palette 2"""
    g = np.zeros((8, 8), np.uint8)
    for y, r in enumerate(POP_GLYPHS[ch]):
        for x, c in enumerate(r):
            if c == '1':
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):
                        yy_, xx_ = y + 1 + dy, x + 2 + dx
                        if 0 <= yy_ < 8 and 0 <= xx_ < 8 and g[yy_, xx_] == 0: g[yy_, xx_] = 8
    for y, r in enumerate(POP_GLYPHS[ch]):
        for x, c in enumerate(r):
            if c == '1': g[y + 1, x + 2] = col
    return g
BOMB_N = render_bomber(32, 0.98); BOMB_F = render_bomber(16, 0.47)
FORT_C, FORT_W = fortress_cells()
def v11_frames():
    return {"BOMB_N": BOMB_N, "BOMB_F": BOMB_F, "FORT_C": FORT_C, "FORT_W": FORT_W,
            "PU_P": TUMBLE_FR["PU_P"][0], "PU_M": TUMBLE_FR["PU_M"][0], "PU_S": TUMBLE_FR["PU_S"][0], "HSPARK": hit_spark(),
            "POP0": np.zeros((16, 32), np.uint8), "POP1": np.zeros((16, 32), np.uint8)}

symbols = {}
def emit_sheet(view, sheet):
    free = sheet.pack(); print(f"sheet {view}: {free} tiles free")
    open(f"{OUT}/obj_{view}.bin", "wb").write(sheet.bin())
    for k, v in sheet.syms.items(): symbols[f"T_{view.upper()}_{k}"] = v
    Image.fromarray(np.array([CGRAM[128 + i] for i in range(16)], np.uint8)[sheet.a]).save(f"{OUT}/sheet_{view}.png")

# overhead sheet (pal: jet=0, cloud=1)
sh = Sheet()
for i, r in enumerate((0, 25, 50)): sh.put(f"JET{i}", render_jet("top", r, 32, 0.95))
for i, c in enumerate(clouds_big): sh.put(f"CLOUDB{i}", c)
for i, c in enumerate(clouds_small): sh.put(f"CLOUDS{i}", c)
sh.put("DOT", dot(32, 2)); sh.put("FLAME0", np.flipud(flame(32, 7, 0, "top"))); sh.put("FLAME1", np.flipud(flame(32, 7, 1, "top")))
for i, yaw in enumerate((0, 45, 90)): sh.put(f"TOP{i}", render_enemy("top", 0, yaw, 32, 0.78))
for k, g in fx_frames(extra="nopuff").items(): sh.put(k, pad(g, 32))
emit_sheet("over", sh)
jet_top0 = sh.a.copy()
# chase sheet
sh = Sheet()
# v1.1 sprite stacking: the chase jet is ONE 64x64 VRAM slot; its 15 frames (5 bank x level/climb/dive)
# live in ROM and the NMI streams the one in use (src/v11.s X_Stream)
# v1.8 smooth animation: 17 bank angles (-44..44 deg in 5.5 deg steps, no mirroring so the key light stays
# put) x 5 nose pitches (-14, -7, 0, 7, 14), then a full 360 deg barrel roll in 64 steps (5.6 deg): 149 frames,
# streamed one per vblank from banks $A0-$A9 (frame f: bank $A0 + f/16, offset (f & 15) * 2 KB)
JET_BANKS = [5.5 * k for k in range(-8, 9)]; JET_NOSE = (-14, -7, 0, 7, 14)
JET_NROLL = 64; JET_ROLL0 = len(JET_BANKS) * len(JET_NOSE)
jet_frames = [render_jet("chase", r, 64, 1.9, pitch_deg=38, nose=p) for p in JET_NOSE for r in JET_BANKS]
jet_frames += [render_jet("chase", a * 360.0 / JET_NROLL, 64, 1.9, pitch_deg=38) for a in range(JET_NROLL)]
sh.put("JETS", jet_frames[2 * len(JET_BANKS) + 8])
wingtips = []
for jg in jet_frames:
    ys, xs = np.nonzero(jg > 1)
    li = xs.argmin(); ri = xs.argmax()
    wingtips.append((int(xs[li]), int(ys[li]), int(xs[ri]), int(ys[ri])))
# streamed 32x32 slots: near enemies (9 unique yaws of 16, the rest h-flipped) and near ground props (16 yaws)
# v1.8: 64 yaws x 3 bank angles (-30 / 0 / +30 deg while turning), no mirroring: frame = bank * 64 + yaw64
EN_NYAW = 64; EN_BANKS = (-30, 0, 30)
EN_YAWS = [render_enemy("chase", b, u * 360.0 / EN_NYAW, 32, 1.02) for b in EN_BANKS for u in range(EN_NYAW)]
for k in range(6): sh.put(f"SLOT{k}", EN_YAWS[EN_NYAW + 32])
for u in range(5): sh.put(f"EMY{u}", render_enemy("chase", 0, u * 45.0, 16, 0.50))
# v1.2: per-stage ground props. Four slots per stage (0 open water / sand, 1 nature, 2 structure,
# 3 military = shootable); each stage maps its slots to voxel models (STAGE_PROPS). Near: 16 streamed
# yaw frames per model (ROM banks $90+), mid / far: 16x16 frames uploaded per stage at LoadView.
PROPS12 = vs.prop_models_v12()
PROP12_LIST = ["carrier", "palms", "oilrig", "bunker", "skyscraper", "pyramid", "rocks", "radar", "tank",
               "iceberg", "pines", "igloo", "turret"]
PROP12_SCALE = {"carrier": 1.15, "skyscraper": 1.05, "pyramid": 1.25, "iceberg": 1.3, "palms": 1.3}
STAGE_PROPS = [["carrier", "palms", "oilrig", "bunker"], ["pyramid", "rocks", "radar", "tank"],
               ["iceberg", "pines", "igloo", "turret"], ["carrier", "skyscraper", "oilrig", "bunker"]]
SLOT_WATER = [(0, 2), (0,)]          # per map: slots that stand on water (map B: sand / sea)
def render_prop(t, yaw, size, scale, pc, outline=1):
    return vs.render(PROPS12[t], vs.PROP12_RAMPS, "chase", yaw=yaw, pitch_cam=pc, size=size, scale=scale * PROP12_SCALE.get(t, 1.4) / 1.4,
                     oy=size / 2 - 3, dither=size > 16, flat_top=0.18, outline=outline, gloss=GLOSS_PROP if size > 16 else {})
PROP_NYAW = 32               # v1.8: 32 yaws (was 16)
PROP_NEAR = [[render_prop(t, d * 360.0 / PROP_NYAW, 32, 1.4, 30) for d in range(PROP_NYAW)] for t in PROP12_LIST]
PROP_MID = {t: (render_prop(t, 30, 16, 0.7, 22), render_prop(t, 30, 16, 0.36, 15, outline=0)) for t in PROP12_LIST}
for i, t in enumerate(STAGE_PROPS[0]):
    sh.put(f"PRM{i}", PROP_MID[t][0]); sh.put(f"PRF{i}", PROP_MID[t][1])
sh.put("CLOUDB0", clouds_big[0]); sh.put("CLOUDS0", clouds_small[0])   # v1.1: one shape each (h-flipped for variety)
# far clouds in the chase view: 16x16 half-size copies (1 sprite instead of 4)
for i, c in enumerate(clouds_small[:1]):
    b = np.asarray(c).reshape(16, 2, 16, 2)
    cov = (b > 0).sum(axis=(1, 3)) >= 2
    t = np.where(cov, b[:, 0, :, 0], 0)
    t = np.where(cov & (t == 0), b.max(axis=(1, 3)), t)
    sh.put(f"CLOUDT{i}", t.astype(np.uint8))
# chase view runs OBSEL 16x16/64x64: dots + flames are 16x16 (flame content shifted 8 px left)
for i, p in enumerate((1, 2, 3)): sh.put(f"DOT{i}", dot(32, p)[:16, :16])
sh.put("FLAME0", FLAME18[0]); sh.put("FLAME1", FLAME18[8])   # v1.8: FLAME0 streams 16 frames
for k, g in enemy_frames_persp(include_away=False, include_bank=False).items():
    if k != "EM": sh.put(k, g)            # (chase medium enemies are the 8-direction EMY frames)
for k, g in fx_frames().items(): sh.put(k, g)
for k, g in v11_frames().items(): sh.put(k, g)
# v1.5: the jet's ground shadow (left half of a 32 x 12 soft ellipse, h-flipped for the right half;
# palette 4 = black, 50% ordered dither so the ground shows through)
_jm = render_jet("top", 0, 32, 0.95) > 0              # planform silhouette, foreshortened 2:1 on the ground
_jm = _jm.reshape(16, 2, 32).any(1)
_sh = np.zeros((16, 16), np.uint8)
for y_ in range(16):
    for x_ in range(16):
        if _jm[y_, x_] and ((x_ + y_) & 1 or (y_ & 1 and x_ & 2)):
            _sh[y_, x_] = 1
sh.put("SHADOW", _sh)
emit_sheet("chase", sh)
chase_sheet = sh
# ---- v1.1 sprite-stack streaming data (ROM banks $8D / $8E, see src/v11.s X_Stream)
def tile_rows(g, tw):
    out = bytearray()
    for ty in range(g.shape[0] // 8):
        for tx in range(tw):
            out += to4bpp(g[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8])
    return bytes(out)
open(f"{OUT}/jetframes.bin", "wb").write(b"".join(tile_rows(j, 8) for j in jet_frames))
SS_PR_N = 64 * ((len(EN_YAWS) + 63) // 64)       # prop frames start on a bank boundary
SLOT_FRAMES = EN_YAWS + [np.zeros((32, 32), np.uint8)] * (SS_PR_N - len(EN_YAWS)) + [f for fr in PROP_NEAR for f in fr]
open(f"{OUT}/slotframes.bin", "wb").write(b"".join(tile_rows(f, 4) for f in SLOT_FRAMES))   # 64 frames per bank
# v1.8: medium-range enemies stream too: the same 64 yaws x 3 banks at 16x16 (128 B each, one bank)
EN_MED = [render_enemy("chase", b, u * 360.0 / EN_NYAW, 16, 0.50) for b in EN_BANKS for u in range(EN_NYAW)]
open(f"{OUT}/medframes.bin", "wb").write(b"".join(tile_rows(f, 2) for f in EN_MED))
# v1.8: explosion (24 x 32x32), dying smoke (12 x 16x16), afterburner (16 x 16x16) sequences
open(f"{OUT}/fxframes.bin", "wb").write(b"".join(tile_rows(f, 4) for f in BOOM18) + b"".join(tile_rows(f, 2) for f in SMOKE18)
                                        + b"".join(tile_rows(f, 2) for f in FLAME18) + b"".join(tile_rows(f, 2) for f in BFLAME18))
def place_bases(info, seed, mi, nbase=9, nwater=3):
    """ground props for one Mode 7 map, grouped in bases (so the game culls a whole base at once):
    the airfield, every town, open land, then open water (carriers / rigs, pyramids, icebergs).
    Prop types are stage slots (see STAGE_PROPS). -> [(cx, cy, [(ox, oy, slot, yaw16), ...])]; |offsets| < 64."""
    land = info["land"]; r_ = np.random.default_rng(seed); bases = []
    def onland(x, y): return bool(land[int(y) % 1024, int(x) % 1024])
    def openw(x, y):
        return not any(onland(x + dx, y + dy) for dx in (-22, 0, 22) for dy in (-22, 0, 22))
    def ok(x, y, t): return openw(x, y) if t in SLOT_WATER[mi] else onland(x, y)
    def far(x, y): return all(min(abs(x - a), 1024 - abs(x - a)) + min(abs(y - b), 1024 - abs(y - b)) > 150 for a, b, _ in bases)
    def base(cx, cy, layout, lim=nbase):
        if len(bases) >= lim or not far(cx, cy): return
        ps = [(ox, oy, t, int(r_.integers(16))) for ox, oy, t in layout if ok(cx + ox, cy + oy, t)]
        if len(ps) >= 2 or (ps and ps[0][2] in SLOT_WATER[mi]): bases.append((int(cx) % 1024, int(cy) % 1024, ps))
    st_ = 2 if mi else 1
    if info["airfield"]:
        y, x0, L = info["airfield"]; cx = (x0 + L / 2) * 8; cy = y * 8 + 8
        base(cx, cy, [(-L * 4 + 6, -22, st_), (L * 4 - 14, 26, 3), (L * 4 - 34, 28, 1), (-L * 4 - 18, 4, 3), (L * 4 + 18, 6, st_)])
    for ty, tx in info["towns"]:
        base(tx * 8, ty * 8, [(-30, -20, st_), (28, 22, 1), (10, -36, 3), (-34, 26, st_ if mi else 1)], nbase - nwater)
    tries = 0
    while len(bases) < nbase - nwater and tries < 3000:
        tries += 1; cx, cy = r_.integers(1024), r_.integers(1024)
        if onland(cx, cy): base(cx, cy, [(0, 0, 3), (-34, 18, 1), (30, -16, st_), (20, 30, 1)], nbase - nwater)
    tries = 0
    wl = [(0, 0, 0), (-44, 34, 2)] if mi == 0 else [(0, 0, 0), (-38, 26, 0)]
    while len(bases) < nbase and tries < 6000:
        tries += 1; cx, cy = r_.integers(1024), r_.integers(1024)
        if openw(cx, cy): base(cx, cy, wl)
    return bases
PROP_MAPS = [place_bases(terrain.INFO[""], 5, 0), place_bases(terrain.INFO["B"], 6, 1)]
print("ground prop bases:", [len(m) for m in PROP_MAPS], "props:", [sum(len(b[2]) for b in m) for m in PROP_MAPS])
with open(f"{OUT}/stack.inc", "w") as fo:
    fo.write("; generated by tools/gen_assets.py (v1.1 sprite stacking)\n")
    def _rows(j):
        r = [ty for ty in range(8) if j[ty * 8:ty * 8 + 8].any()] or [0]
        return min(r) | max(r) << 4
    fo.write("JetRows: .byte " + ",".join(str(_rows(j)) for j in jet_frames) + "   ; v1.8: first | last non-empty tile row << 4\n")
    fo.write(f"JS_N = {len(jet_frames)}\nJS_NB = {len(JET_BANKS)}\nJS_ROLL0 = {JET_ROLL0}\nJS_NROLL = {JET_NROLL}\n")
    fo.write(f"EN_NYAW = {EN_NYAW}\nSS_EN = 0\nSS_PR = {SS_PR_N}\nSS_NFR = {len(SLOT_FRAMES)}\nNBASE = {len(max(PROP_MAPS, key=len))}\n")
    fo.write("WingTips:  ; per jet frame: LX LY RX RY\n")
    for w in wingtips: fo.write("  .word " + ", ".join(str(v) for v in w) + "\n")
    k = 0; props = []
    for mi, m in enumerate(PROP_MAPS):
        m = m + [(0, 0, [])] * (len(max(PROP_MAPS, key=len)) - len(m))
        fo.write(f"BaseMap{mi}:  ; centre x, y, prop count, first prop offset (bytes)\n")
        for cx, cy, ps in m:
            fo.write(f"  .word {cx}, {cy}, {len(ps)}, {k * 8}\n"); k += len(ps); props += ps
    fo.write("PropOff:  ; dx, dy (from the base centre), type, yaw (16ths)\n")
    for ox, oy, t, yw in props: fo.write(f"  .word {ox & 0xFFFF}, {oy & 0xFFFF}, {t}, {yw}\n")
    fo.write(f"NPROP12 = {len(PROP12_LIST)}\nNPROPS = {len(props)}\n")
    fo.write("StageMod:  ; per stage, per slot: first near frame id (SS_PR + model * 32)\n")
    for sp in STAGE_PROPS: fo.write("  .word " + ", ".join(str(SS_PR_N + PROP12_LIST.index(t) * PROP_NYAW) for t in sp) + "\n")
# v1.2: prop offsets pre-rotated for all 256 headings (replaces four 8-bit multiplies per prop):
# per heading, per prop: dz = PMul(ox, S) - PMul(oy, C), dx = PMul(ox, C) + PMul(oy, S) as signed bytes
def _pmul(a, t): return (1 if a * t >= 0 else -1) * ((abs(a) * abs(t)) >> 8)
rot = bytearray()
sint_ = [max(-255, min(255, int(round(math.sin(i * 2 * math.pi / 256) * 256)))) for i in range(256)]
for h in range(256):
    S_ = sint_[h]; C_ = sint_[(h + 64) & 255]
    for ox, oy, t, yw in props:
        dz = _pmul(ox, S_) - _pmul(oy, C_); dx = _pmul(ox, C_) + _pmul(oy, S_)
        assert -128 <= dz < 128 and -128 <= dx < 128
        rot += bytes([dz & 255, dx & 255])
assert len(rot) // 2 <= 32768 and len(props) * 2 < 256
open(f"{OUT}/proprot.bin", "wb").write(bytes(rot))
open(f"{OUT}/propmid.bin", "wb").write(b"".join(tile_rows(PROP_MID[t][k], 2) for sp in STAGE_PROPS for k in (0, 1) for t in sp))

# cockpit sheet: pal2 HUD (green), clouds pal1, frame pal3
sh = Sheet()
sh.put("CLOUDB0", clouds_big[0]); sh.put("CLOUDS0", clouds_small[0])
g = np.zeros((32, 32), np.uint8)
im = Image.fromarray(g); d = ImageDraw.Draw(im)
d.ellipse((6, 6, 25, 25), outline=1); d.line((15, 0, 15, 4), fill=1); d.line((15, 27, 15, 31), fill=1)
d.line((0, 15, 4, 15), fill=1); d.line((27, 15, 31, 15), fill=1); d.rectangle((15, 15, 16, 16), fill=1)
sh.put("CROSS", np.array(im))
# cockpit runs OBSEL 16x16/32x32: the ladder pieces are 16x16 (rung row 7 = old row 15)
g = np.zeros((16, 16), np.uint8); g[7, 2:14] = 1; g[7:11, 13] = 1; sh.put("LADDER", g)   # left half rung
g = np.zeros((16, 16), np.uint8); g[7, 2::4] = 1; g[7, 3::4] = 1; sh.put("LADDERD", g)  # dashed rung (2 pieces per side)
# radar sweep: 4 base angles, flips give 16 directions
for i in range(5):
    g = np.zeros((32, 32), np.uint8); ang = math.radians(i * 22.5)
    for t in np.linspace(0, 15, 60):
        x = 16 + math.sin(ang) * t; y = 16 - math.cos(ang) * t
        g[min(31,int(y)), min(31,int(x))] = 7
        for tr in (1, 2):
            a2 = ang - math.radians(9 * tr); x2 = 16 + math.sin(a2) * t; y2 = 16 - math.cos(a2) * t
            yi, xi = min(31,int(y2)), min(31,int(x2))
            if g[yi, xi] == 0: g[yi, xi] = 1 if tr == 1 else 2
    sh.put(f"SWEEP{i}", g)
# attitude ball: bank 0/15/30 x pitch -1/0/+1
for bi, bank in enumerate((0, 15, 30)):
    for pi, pit in enumerate((-5, 0, 5)):
        g = np.zeros((32, 32), np.uint8)
        b = math.radians(bank)
        for y in range(32):
            for x in range(32):
                dx, dy = x + 0.5 - 16, y + 0.5 - 16
                if dx * dx + dy * dy <= 13.5 ** 2:
                    v = dy * math.cos(b) - dx * math.sin(b) + pit
                    g[y, x] = 4 if v < 0 else 5
                    if abs(v) < 0.8: g[y, x] = 6
                    if abs(dy) < 0.6 and abs(dx) < 7 and abs(dx) > 2: g[y, x] = 9
                    if abs(dx) < 0.6 and abs(dy) < 0.6: g[y, x] = 9
        sh.put(f"BALL{bi}{pi}", g)
# canopy pillar 32x32 strip (palette 3 frame)
g = np.zeros((16, 16), np.uint8); g[:, 0:10] = 3; g[:, 10:12] = 4; g[:, 0:2] = 1; g[:, 12] = 1
sh.put("PILLAR", g)   # 16x16 (12 sprites) so the enemy tracers / missile fit in the cockpit sheet
for k, g in enemy_frames_persp(include_away=False, include_bank=False).items(): sh.put(k, g)
for k, g in fx_frames(two_big=True, two_debris=False, extra=False).items(): sh.put(k, g)
for k, g in v11_frames().items():
    if k != "HSPARK": sh.put(k, g)        # (cockpit sheet is 4 tiles short: its spark is the X16A star)
emit_sheet("cock", sh)
cock_sheet = sh

# ----------------------------------------------------------------- boss sheets (v1.2: sprite-stacked parts)
# During the boss fight the chase / cockpit OBJ sheets swap clouds + enemy-plane frames for the boss
# robot's 16x16 pieces, beam orbs, shards, thrusters. Only the 512-byte sheet rows that differ are streamed to
# VRAM (NMI, during the WARNING). v1.2: the robot is a voxel model (tools/boss_vox.py) drawn as part groups:
# body (normal / battle-damaged), head + crest (5 yaws: it turns to track you), each arm (down / cannon /
# spread). boss_parts.inc holds one OAM list per part frame: (dy<<8)+dx, dx, dy, tile | attr << 8.
import copy
import boss_art, boss_vox, boss_rt
# v1.3: the robot is a pre-rendered 3D model (tools/boss_rt.py, glossy shading -> BOSS palette). The chase
# view uses scale 1.0; the cockpit (fewer free tiles: its instruments stay) a 0.8 render.
BV = {"chase": boss_rt.build_all(256, 1.0), "cock": boss_rt.build_all(256, 0.8)}
def _bv_full(fr, S, name, half):
    """part frame -> [(dx, dy, tile16, hflip)] covering the whole part (mirror-half frames get both halves)"""
    cs = boss_vox.cells(fr[name], S // 2, S // 2, mirror_half=half)
    cs = [c for c in cs if (c[2] > 0).sum() > 10]     # v1.3: no sprite for a few stray edge pixels
    out = [(dx, dy, t, 0) for dx, dy, t in cs]
    if half: out += [(-dx - 16, dy, t, 1) for dx, dy, t in cs]
    return out
def _bv_flip(lst): return [(-dx - 16, dy, t, 1 - f) for dx, dy, t, f in lst]
def _bv_parts(fr, S, scale):
    C = S // 2
    P = {"body": _bv_full(fr, S, "body", True)}
    _cl = fr["body"].copy(); _cl[:, C:] = _cl[:, :C][:, ::-1][:, :S - C]
    # battle damage: one blast per target, centred in the 16x16 cell that holds it (4 changed cells)
    cen = []
    for tx, ty in boss_rt.DMG_SCREEN:
        tx, ty = tx * scale, ty * scale
        for dx, dy, t, f in P["body"]:
            if dx <= tx < dx + 16 and dy <= ty < dy + 16: cen.append((C + dx + 7.5, C + dy + 7.5)); break
    dimg = boss_rt.damage_px(_cl, cen, 5.2)
    _bd = []
    for dx, dy, t, f in P["body"]:
        x0, y0 = C + dx, C + dy
        d = dimg[y0:y0 + 16, x0:x0 + 16]; c = _cl[y0:y0 + 16, x0:x0 + 16]
        _bd.append((dx, dy, d.copy(), 0) if (d != c).any() else (dx, dy, t, f))
    P["body_dmg"] = _bd
    P["head0"] = _bv_full(fr, S, "head0", True)
    y = boss_rt.HEAD_YAWS[1]
    P["head18"] = _bv_full(fr, S, f"head{y}", False); P["head-18"] = _bv_flip(P["head18"])
    for pz in boss_rt.POSES:
        P[f"armL_{pz}"] = _bv_full(fr, S, f"arm_{pz}", False); P[f"armR_{pz}"] = _bv_flip(P[f"armL_{pz}"])
    return P
BV_PARTS = {v: _bv_parts(*BV[v], {"chase": 1.0, "cock": 0.8}[v]) for v in BV}
# logical part ids (the game's tables): 0 body, 1 body damaged, 2..6 head yaw (far left .. far right), 7.. arms (pose * 2 + side)
BV_IDS = ["body", "body_dmg", "head-36", "head-18", "head0", "head18", "head36"] + \
         [f"arm{sd}_{pz}" for pz in boss_rt.POSES for sd in "LR"]
# v1.3 merged lists: body (+ damage) with both arms in a pose pair, drawn as one part when no arm recoils
BV_CMB = [("down", "down"), ("cannon", "down"), ("down", "cannon"), ("cannon", "cannon"), ("spread", "spread"), ("spread", "down"), ("down", "spread")]
for _l, _r in BV_CMB:
    for _b in ("body", "body_dmg"):
        BV_IDS.append(f"cmb_{_l}_{_r}_{_b}")
BV_VIEW_SUB = {"chase": {"head-36": "head-18", "head36": "head18"},
               "cock": {"head-36": "head0", "head-18": "head0", "head18": "head0", "head36": "head0", "body_dmg": "body",
                        "armL_spread": "armL_down", "armR_spread": "armR_down"}}
boss_out = {}
CMB_ROW = {}
def _ordered(view, n, ent):
    """entries in draw order + (first row dy, row index per entry)"""
    if (view, n) in CMB_ROW:
        y0 = CMB_ROW[(view, n)]; return ent, y0, [(e[1] - y0) // 16 for e in ent]
    se = sorted(ent, key=lambda e: (e[1], e[0])); y0 = se[0][1]
    return se, y0, [(e[1] - y0) // 16 for e in se]
def boss_sheet(view, field, drop):
    b = copy.deepcopy(field); b.free(drop)
    sub = BV_VIEW_SUB[view]
    used = [sub.get(n, n) for n in BV_IDS]
    BVP = dict(BV_PARTS[view])
    for n in BV_IDS:
        if n.startswith("cmb_"):
            _, l, r, bd = n.split("_", 3)
            parts = [sub.get(f"armL_{l}", f"armL_{l}"), sub.get(f"armR_{r}", f"armR_{r}"), sub.get(bd, bd)]
            BVP[n] = [("arm",) + e for p_ in parts[:2] for e in BVP[p_]] + [("body",) + e for e in BVP[parts[2]]]
    # (merged entries carry a kind tag; strip it for the cell dedup, keep it for the row order)
    KIND = {n: [e[0] for e in v] for n, v in BVP.items() if n.startswith("cmb_")}
    BVP = {n: ([e[1:] for e in v] if n.startswith("cmb_") else v) for n, v in BVP.items()}
    uniq = {}                                   # tile bytes -> sheet name (identical / mirrored cells shared)
    refs = {}
    for n in dict.fromkeys(used):
        for i, (dx, dy, t, f) in enumerate(BVP[n]):
            k = t.tobytes(); kf = np.ascontiguousarray(t[:, ::-1]).tobytes()
            if k in uniq: refs[(n, i)] = (uniq[k], 0)
            elif kf in uniq: refs[(n, i)] = (uniq[kf], 1)
            else:
                nm = f"BC{len(uniq)}"; uniq[k] = nm; b.put(nm, t); refs[(n, i)] = (nm, 0)
    b.put("BORB0", boss_art.beam_orb(True)); b.put("BORB1", boss_art.beam_orb(False))
    b.put("BSHARD", TUMBLE_FR["BSHARD"][0])
    b.put("BFLAME0", BFLAME18[0] if view == "chase" else boss_art.flame16(0)); b.put("BFLAME1", boss_art.flame16(1))
    print(f"boss sheet {view}: {len(uniq)} boss cells, room", int((~b.used).sum()), "tiles before packing")
    free = b.pack(); print(f"boss sheet {view}: {free} tiles free, {len(uniq)} boss cells")
    data = b.bin(); old = field.bin()
    open(f"{OUT}/obj_{view}_boss.bin", "wb").write(data)
    rows = [ty for ty in range(32) if data[ty * 512:(ty + 1) * 512] != old[ty * 512:(ty + 1) * 512]]
    for k, v in b.syms.items():
        if k.startswith("B") and not k.startswith("BC"): symbols[f"T_{view.upper()}_{k}"] = v
    lut = np.array([(255, 0, 255)] + [tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in boss_rt.PAL[1:]], np.uint8)
    Image.fromarray(lut[b.a]).save(f"{OUT}/sheet_{view}_boss.png")
    tabs_ = {}
    for n in dict.fromkeys(used):
        ent = []
        for i, (dx, dy, t, f) in enumerate(BVP[n]):
            nm, ff = refs[(n, i)]
            tile = b.syms[nm]; hf = f ^ ff
            attr = 0x0E | (tile >> 8 & 1) | (0x40 if hf else 0)
            ent.append((dx, dy, (tile & 0xFF) | attr << 8))
        if n in KIND:
            # rows of the body grid; in each row the arm cells come first (drawn over the body)
            bdy = [e for e, k in zip(ent, KIND[n]) if k == "body"]
            y0 = min(e[1] for e in bdy)
            ent = [e for _, e in sorted(((((e[1] - y0) // 16, 0 if k == "arm" else 1, e[1], e[0]), e) for e, k in zip(ent, KIND[n])), key=lambda t: t[0])]
            CMB_ROW[(view, n)] = y0
        tabs_[n] = ent
    boss_out[view] = (b, rows, used, tabs_)
CLOUDS_ALL = ["CLOUDB0", "CLOUDS0", "BOMB_N", "BOMB_F", "FORT_C", "FORT_W"]   # v1.1: no bombers during the boss
boss_sheet("chase", chase_sheet, CLOUDS_ALL + ["CLOUDT0", "EL_TOW", "ES", "EXS", "EXXS"] + [f"SLOT{k}" for k in range(6)]
           + [f"EMY{u}" for u in range(5)] + [f"PR{a}{i}" for a in "MF" for i in range(4) if f"PR{a}{i}" in chase_sheet.syms])
boss_sheet("cock", cock_sheet, CLOUDS_ALL + ["EL_TOW", "EM", "ES", "EXS", "EXXS"])
# ---- v1.6: the Stage 1 boss (Naveed's dad, tools/dad/dad_art.py). Chase view only. His sheet is the robot's
# chase boss sheet with the robot's cells swapped for his (orbs / shard / flames stay on the same tiles), so
# the boss code is shared: separate part ids (dad, dad_dmg), palette (DadPal) and sheet (obj_chase_dad.bin).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "dad"))
import dad_art
DAD_PX, DAD_GL = dad_art.build()
def _dad_dmg(px):
    """below 1/3 health: soot on the cheek, forehead and jersey, a cracked right lens"""
    q = px.copy(); H, W = q.shape; gx, gy = DAD_GL
    r = np.random.default_rng(16)
    for cx, cy, rad in ((gx + 24, gy + 18, 5), (gx - 20, gy - 26, 4), (gx + 34, gy + 66, 7), (gx - 36, gy + 72, 6)):
        for y in range(cy - rad, cy + rad + 1):
            for x in range(cx - rad, cx + rad + 1):
                if 0 <= y < H and 0 <= x < W and q[y, x] > 1 and (x - cx) ** 2 + (y - cy) ** 2 <= rad * rad and r.random() < 0.75:
                    q[y, x] = 1 if r.random() < 0.35 else (9 if q[y, x] in (7, 8, 10, 11, 12) else 2)
    for k in range(8):                                   # crack across the right lens
        x, y = gx + 8 + k, gy - 4 + (k * 5) // 4
        if q[y, x] > 1: q[y, x] = 12
    return q
def _dad_cells(px):
    out = []; H, W = px.shape; gx, gy = DAD_GL
    for y in range(0, H, 16):
        for x in range(0, W, 16):
            c = np.zeros((16, 16), np.uint8); blk = px[y:y + 16, x:x + 16]; c[:blk.shape[0], :blk.shape[1]] = blk
            if (c > 0).sum() > 6: out.append((x - gx, y - gy, c, 0))
    return out
# v1.8: head / chest split (the chest breathes under the head), blink + talking mouth tile patches
DAD_SPLIT = 112 - DAD_GL[1]                             # cell rows from y = 112 down are the chest
_DAD_PUP = ((48.5, 54.0), (73.0, 54.0))                 # pupils (output px)
_DAD_MOUTH = (61.0, 82.0)
def _dad_eyes(px, st):
    """st 0 open, 1 half shut, 2 shut (lids: skin, lash line)"""
    q = px.copy()
    if st == 0: return q
    for cx, cy in _DAD_PUP:
        for y in range(int(cy) - 4, int(cy) + 4):
            for x in range(int(cx) - 6, int(cx) + 7):
                e = ((x + 0.5 - cx) / 5.6) ** 2 + ((y + 0.5 - cy) / 3.0) ** 2
                if e >= 1 or q[y, x] in (0, 1, 11, 14): continue
                if st == 2:
                    if abs(y + 0.5 - (cy + 0.9)) < 0.6: q[y, x] = 15          # lash line
                    elif y + 0.5 < cy + 0.9: q[y, x] = 7 if y + 0.5 < cy - 1.2 else 6
                    else: q[y, x] = 6 if y + 0.5 < cy + 2.2 else q[y, x]
                else:
                    if y + 0.5 < cy - 0.3: q[y, x] = 6
                    elif abs(y + 0.5 - (cy - 0.3)) < 0.8: q[y, x] = 15
    return q
def _dad_mouth(px, lv):
    """lv 0 closed .. 3 wide: the lower lip and beard drop, a dark mouth opens (teeth at 2+), lower lip lit"""
    q = px.copy()
    if lv == 0: return q
    mx, my = _DAD_MOUTH; w = 3.6 + lv * 1.1; H = (0, 2, 3, 5)[lv]
    for x in range(int(mx - 10), int(mx + 11)):
        dxa = abs(x + 0.5 - mx)
        f = max(0.0, 1 - (dxa / (w + 3.5)) ** 2)
        k = int(round(H * f))
        if k <= 0: continue
        for y in range(95, int(my) - 1 + k, -1):                         # drop the jaw (cell row ends at 95)
            q[y, x] = px[y - k, x]
        for y in range(int(my), int(my) + k):
            if dxa <= w:
                if lv >= 2 and y == int(my) and dxa < w * 0.6: q[y, x] = 11        # upper teeth
                else: q[y, x] = 1 if dxa < w - 1 and y > int(my) - 1 else 15
        if dxa <= w - 0.5 and q[int(my) + k, x] > 1: q[int(my) + k, x] = 7        # lower lip
    return q
def _dad_parts(px, sfx):
    cells = _dad_cells(px)
    return {"dad" + sfx: [c for c in cells if c[1] < DAD_SPLIT], "dadb" + sfx: [c for c in cells if c[1] >= DAD_SPLIT]}
DAD_PARTS = {}
DAD_PARTS.update(_dad_parts(DAD_PX, "")); DAD_PARTS.update(_dad_parts(_dad_dmg(DAD_PX), "_dmg"))
DAD_PARTS = {k: DAD_PARTS[k] for k in ("dad", "dad_dmg", "dadb", "dadb_dmg")}
_b, _rows, _used, _tabs = boss_out["chase"]
_d = copy.deepcopy(_b)
_d.free([k for k in list(_d.syms) if k.startswith("BC")])
_uq = {}
for _n, _lst in DAD_PARTS.items():
    _ent = []
    for dx, dy, t, f in _lst:
        k = t.tobytes(); kf = np.ascontiguousarray(t[:, ::-1]).tobytes()
        if k in _uq: nm, ff = _uq[k], 0
        elif kf in _uq: nm, ff = _uq[kf], 1
        else: nm = f"DC{len(_uq)}"; _uq[k] = nm; _d.place(nm, t); ff = 0
        tile = _d.syms[nm]; attr = 0x0E | (tile >> 8 & 1) | (0x40 if ff else 0)
        _ent.append((dx, dy, (tile & 0xFF) | attr << 8))
    _tabs[_n] = _ent
# v1.8 patch groups: every tile whose 16x16 cell changes in some eye / mouth state, the cell data per state
def _dad_group(fn, nst):
    out = {}
    for sfx in ("", "_dmg"):
        b0 = DAD_PX if not sfx else _dad_dmg(DAD_PX)
        ents = {(dx, dy): w for n in ("dad" + sfx, "dadb" + sfx) for dx, dy, w in _tabs[n]}
        vs = [fn(DAD_PX, st) if not sfx else _dad_dmg(fn(DAD_PX, st)) for st in range(nst)]
        gx, gy = DAD_GL
        for cy in range(0, b0.shape[0], 16):
            for cx in range(0, b0.shape[1], 16):
                blk = [v[cy:cy + 16, cx:cx + 16] for v in vs]
                if all(np.array_equal(blk[0], bk) for bk in blk[1:]) and np.array_equal(blk[0], b0[cy:cy + 16, cx:cx + 16]): continue
                w = ents[(cx - gx, cy - gy)]
                tile = (w & 0xFF) | ((w >> 8) & 1) << 8; ff = (w >> 8) & 0x40
                data = [np.ascontiguousarray(bk[:, ::-1]) if ff else bk for bk in blk]
                if tile in out: assert all(np.array_equal(a, b) for a, b in zip(out[tile], data)), "shared patch tile"
                out[tile] = data
    # a patched tile must not be drawn anywhere else
    uses = {}
    for n in DAD_PARTS:
        for dx, dy, w in _tabs[n]: uses.setdefault((w & 0xFF) | ((w >> 8) & 1) << 8, set()).add((n.replace("_dmg", ""), dx, dy))
    for t in out: assert len({u[1:] for u in uses[t]}) == 1, f"dad patch tile {t} is shared"
    return sorted(out.items())
DAD_EYE = _dad_group(_dad_eyes, 3); DAD_MOUTH = _dad_group(_dad_mouth, 4)
print("dad patches: eye tiles", [t for t, _ in DAD_EYE], "mouth tiles", [t for t, _ in DAD_MOUTH])
with open(f"{OUT}/dadpatch.bin", "wb") as fo:
    for grp, nst in ((DAD_EYE, 3), (DAD_MOUTH, 4)):
        for st in range(nst):
            for t, data in grp: fo.write(tile_rows(data[st], 2))
import wave as _wave
_w = _wave.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "music", "dad_voice.wav"))
_vx = np.frombuffer(_w.readframes(_w.getnframes()), np.int16).astype(np.float32) / 32768; _vsr = _w.getframerate()
_hop = _vsr / 60.0; _env = []
for i in range(int(len(_vx) / _hop) + 1):
    seg = _vx[int(i * _hop):int((i + 1) * _hop)]
    _env.append(float(np.sqrt((seg ** 2).mean())) if len(seg) else 0.0)
_env = np.array(_env); _env /= max(1e-6, np.percentile(_env, 95))
_lv = []; _sm = 0.0
for e in _env:                                          # fast open, slower close; 0..3
    _sm = e if e > _sm else _sm * 0.72 + e * 0.28
    _lv.append(0 if _sm < 0.18 else 1 if _sm < 0.42 else 2 if _sm < 0.7 else 3)
DAD_TALK = [0, 0] + _lv + [0]                 # (2 frames for the APU to start the sample)
_dd = _d.bin(); _old = chase_sheet.bin()
open(f"{OUT}/obj_chase_dad.bin", "wb").write(_dd)
_rows_d = [ty for ty in range(32) if _dd[ty * 512:(ty + 1) * 512] != _old[ty * 512:(ty + 1) * 512]]
_rows = sorted(set(_rows) | set(_rows_d))
boss_out["chase"] = (_b, _rows, _used + ["dad", "dad_dmg", "dadb", "dadb_dmg"], _tabs)
_cb, _crows, _cused, _ctabs = boss_out["cock"]
boss_out["cock"] = (_cb, _crows, _cused + ["body", "body", "body", "body"], _ctabs)
BV_IDS += ["dad", "dad_dmg", "dadb", "dadb_dmg"]
print(f"dad sheet: {len(_uq)} cells, {int((~_d.used).sum())} tiles free, {len(DAD_PARTS['dad'])} sprites; rows {len(_rows)}")
dad_art.preview(DAD_PX, f"{OUT}/dad_boss.png", 2)
with open(f"{OUT}/boss.inc", "w") as fo:
    fo.write("; generated by tools/gen_assets.py (boss v1.2)\n")
    fr_ = BV["chase"][0]
    fo.write(f"BOSS_EYE_DY = {fr_['_eye_dy']}\n")
    fo.write(f"DP_EYE_N = {len(DAD_EYE)}\nDP_MOUTH_N = {len(DAD_MOUTH)}\nDP_TALK_N = {len(DAD_TALK)}\n")
    fo.write("DpEyeTile: .word " + ", ".join(str(t) for t, _ in DAD_EYE) + "\n")
    fo.write("DpMouthTile: .word " + ", ".join(str(t) for t, _ in DAD_MOUTH) + "\n")
    fo.write("DadTalk: .byte " + ", ".join(str(v) for v in DAD_TALK) + "\n")
    for view in ("chase", "cock"):
        f2 = BV[view][0]
        fo.write(f"BOSS_FOOT_X_{view.upper()} = {f2['_foot'][0]}\nBOSS_FOOT_Y_{view.upper()} = {f2['_foot'][1]}\n")
        fo.write(f"BOSS_MUZ_X_{view.upper()} = {f2['_muzzle']['cannon'][0]}\nBOSS_MUZ_Y_{view.upper()} = {f2['_muzzle']['cannon'][1]}\n")
    for view in ("chase", "cock"):
        b, rows, used, tabs_ = boss_out[view]
        fo.write(f"BossRows_{view}: .byte " + ",".join(str(r) for r in rows) + f"\nBOSS_NROWS_{view.upper()} = {len(rows)}\n")
    def bgr(h): r, g, b_ = (int(h[i:i + 2], 16) for i in (1, 3, 5)); return (r >> 3) | ((g >> 3) << 5) | ((b_ >> 3) << 10)
    # v1.3 blue energy orbit tables: spin ring (16 angles, 96 x 20 px ellipse, 14 px below the gem) and the
    # beam charge swirl (16 radius levels x 32 angles); entries are sprite offsets (top-left) from the gem
    fo.write("SpinTab: .word " + ", ".join(f"${(round(96 * math.cos(2 * math.pi * i / 16)) - 8) & 0xFFFF:04X}, ${(round(20 * math.sin(2 * math.pi * i / 16)) + 6) & 0xFFFF:04X}" for i in range(16)) + "\n")
    fo.write(".pushseg\n.segment \"BANK1\"\nSwirlTab:\n")    # v1.5: out of bank 0 (read with long addressing)
    for lv in range(16):
        r = (64 - 4 * lv) * 1.5 + 5
        fo.write("  .word " + ", ".join(f"${(round(r * math.cos(2 * math.pi * j / 32)) - 8) & 0xFFFF:04X}, ${(round(r * math.sin(2 * math.pi * j / 32)) - 8) & 0xFFFF:04X}" for j in range(32)) + "\n")
    fo.write(".popseg\n")
    fo.write("BossPal: .word " + ",".join(f"${bgr(h):04X}" for h in boss_rt.PAL) + "\n")
    fo.write("DadPal: .word " + ",".join(f"${v:04X}" for v in dad_art.DAD_PAL) + "\n")
    fo.write("NavyPal: .word " + ",".join(f"${bgr('#%02x%02x%02x' % c):04X}" for c in CGRAM[240:256]) + "\n")
with open(f"{OUT}/boss_parts.inc", "w") as fo:
    fo.write("; generated by tools/gen_assets.py: boss part OAM lists (boss v1.2, tools/boss_vox.py)\n")
    fo.write(f"BP_NIDS = {len(BV_IDS)}\nBP_DAD = {BV_IDS.index('dad')}\n")
    xs, ys = [], []
    for view in ("chase", "cock"):
        b, rows, used, tabs_ = boss_out[view]
        fo.write(f"BPIdx_{view}:   ; per part id (16 bytes): BPData offset, entries, fast sx range, first row dy, 16 * rows, BPRows offset, 0\n")
        M = 3   # animation offsets (bob, recoil) stay inside this margin
        for n in used:
            e = tabs_[n]
            x0 = -min(dx for dx, dy, w in e) + M; x1 = 256 - max(dx + 16 for dx, dy, w in e) - M
            _, dy0, rk = _ordered(view, n, e); nr = max(rk) + 1
            fo.write(f"  .word BPL_{view}_{n.replace('-', 'm')}-BPData, {len(e)}, " + ", ".join(f"${v & 0xFFFF:04X}" for v in (x0, x1, dy0)) +
                     f", {16 * nr}, BPR_{view}_{n.replace('-', 'm')}-BPRows, 0\n")
    fo.write("BPData:   ; (dy<<8)+dx, dx, dy, tile | attr<<8 (priority bits baked in per view), rows top to bottom\n")
    for view in ("chase", "cock"):
        b, rows, used, tabs_ = boss_out[view]
        pri = {"chase": 0x30, "cock": 0x10}[view]
        for n, ent in tabs_.items():
            fo.write(f"BPL_{view}_{n.replace('-', 'm')}:\n")
            for dx, dy, w in _ordered(view, n, ent)[0]:
                xs += [dx, dx + 16]; ys += [dy, dy + 16]
                fo.write(f"  .word ${(dy * 256 + dx) & 0xFFFF:04X}, ${dx & 0xFFFF:04X}, ${dy & 0xFFFF:04X}, ${w | pri << 8:04X}\n")
    fo.write("BPRows:   ; per part: byte offset of each 16 px row's first entry (+ end)\n")
    for view in ("chase", "cock"):
        b, rows, used, tabs_ = boss_out[view]
        for n, ent in tabs_.items():
            se, dy0, rk = _ordered(view, n, ent); nr = max(rk) + 1
            assert rk == sorted(rk) and min(rk) >= 0, n
            offs = [8 * next(i for i, r_ in enumerate(rk + [10 ** 6]) if r_ >= k) for k in range(nr)] + [8 * len(se)]
            fo.write(f"BPR_{view}_{n.replace('-', 'm')}: .word " + ", ".join(str(o) for o in offs) + "\n")
    fo.write(f"BOSS_FAST_X0 = {-min(xs) + M}\nBOSS_FAST_X1 = {256 - max(xs) - M}\nBOSS_FAST_Y0 = {-min(ys) + M}\nBOSS_FAST_Y1 = {224 - max(ys) - M}\n")
    fo.write(f"BOSS_MAXN = {max(sum(len(boss_out['chase'][3][n]) for n in grp) for grp in [['body', 'head18', 'armL_spread', 'armR_spread'], ['body_dmg', 'head18', 'armL_spread', 'armR_spread'], ['body', 'head0', 'armL_cannon', 'armR_cannon']])}\n")
    print("boss parts: x", min(xs), max(xs), "y", min(ys), max(ys))

# ----------------------------------------------------------------- v1.2 tumbling objects (streamed 16x16 frames)
# Debris chunks, missiles, power-up capsules and the boss's crest shards are small voxel models; 8 frames each
# (tumble / roll / spin) live in ROM and the NMI streams the current one over the object's sheet tiles.
TUMBLE_NAMES = list(tumble_cfg.TUMBLE)
tb = bytearray()
for k in TUMBLE_NAMES:
    for g in TUMBLE_FR[k]:
        tb += to4bpp(g[:8, :8]) + to4bpp(g[:8, 8:]) + to4bpp(g[8:, :8]) + to4bpp(g[8:, 8:])
open(f"{OUT}/tumble.bin", "wb").write(tb)
def _tt(view, names, off=0):
    return [(symbols[f"T_{view.upper()}_{n}"] + off, TUMBLE_NAMES.index(n)) for n in names if f"T_{view.upper()}_{n}" in symbols]
_tch = _tt("chase", ["DEB0", "DEB1", "MSL", "EMSL", "PU_P", "PU_M", "PU_S"])
_tco = _tt("cock", ["DEB0", "MSL", "EMSL", "PU_P", "PU_M", "PU_S"])
_tov = _tt("over", ["DEB0", "DEB1"], 17)          # (overhead: 32x32 frames with the 16x16 art in the middle)
with open(f"{OUT}/tumble.inc", "w") as fo:
    fo.write("; generated by tools/gen_assets.py: v1.2 tumbling frame targets (sheet tile, frame set)\n")
    for nm, lst in (("TbChase", _tch), ("TbChaseB", _tch + _tt("chase", ["BSHARD"])), ("TbCock", _tco),
                    ("TbCockB", _tco + _tt("cock", ["BSHARD"])), ("TbOver", _tov)):
        fo.write(f"{nm}: .word {len(lst)}" + "".join(f", {t}, {i}" for t, i in lst) + "\n")
print("tumble:", len(TUMBLE_NAMES), "sets,", len(tb), "bytes")

# ----------------------------------------------------------------- BG2 tiles: font + cockpit art
FONT_CHARS = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-:/.!>,"
FONT = {
' ':"00000000000000000000000000000000000",
'0':"01110100011001110101110011000101110",'1':"00100011000010000100001000010001110",
'2':"01110100010000100110010001000011111",'3':"11110000010000101110000010000111110",
'4':"00010001100101010010111110001000010",'5':"11111100001111000001000011000101110",
'6':"00110010001000011110100011000101110",'7':"11111000010001000100010000100001000",
'8':"01110100011000101110100011000101110",'9':"01110100011000101111000010001001100",
'A':"01110100011000111111100011000110001",'B':"11110100011000111110100011000111110",
'C':"01110100011000010000100001000101110",'D':"11100100101000110001100011001011100",
'E':"11111100001000011110100001000011111",'F':"11111100001000011110100001000010000",
'G':"01110100011000010111100011000101111",'H':"10001100011000111111100011000110001",
'I':"01110001000010000100001000010001110",'J':"00111000100001000010000101001001100",
'K':"10001100101010011000101001001010001",'L':"10000100001000010000100001000011111",
'M':"10001110111010110101100011000110001",'N':"10001100011100110101100111000110001",
'O':"01110100011000110001100011000101110",'P':"11110100011000111110100001000010000",
'Q':"01110100011000110001101011001001101",'R':"11110100011000111110101001001010001",
'S':"01111100001000001110000010000111110",'T':"11111001000010000100001000010000100",
'U':"10001100011000110001100011000101110",'V':"10001100011000110001100010101000100",
'W':"10001100011000110101101011010101010",'X':"10001100010101000100010101000110001",
'Y':"10001100010101000100001000010000100",'Z':"11111000010001000100010001000011111",
'-':"00000000000000011111000000000000000",':':"00000011000110000000011000110000000",
'/':"00001000010001000100010001000010000",'.':"00000000000000000000000000110001100",
'!':"00100001000010000100001000000000100",',':"0000000000000000000000000001100011001100",'>':"01000001000001000001000100010001000",
}
def glyph(ch):
    """5x7 glyph, Capcom-style: pale top rows (4), main colour (1), warm lower rows (5), dark outline (2)"""
    bits = FONT[ch]; g = np.zeros((9, 9), bool)
    for y in range(len(bits) // 5):          # 7 rows (v1.7: 8 for the comma's descender)
        for x in range(5):
            if bits[y * 5 + x] == '1': g[y + 1, x + 2] = True
    t = np.zeros((9, 9), np.uint8)
    for y in range(9):
        for x in range(9):
            if not g[y, x] and any(0 <= y + dy < 9 and 0 <= x + dx < 9 and g[y + dy, x + dx]
                                   for dy in (-1, 0, 1) for dx in (-1, 0, 1)): t[y, x] = 2
    for y in range(9):
        for x in range(9):
            if g[y, x]: t[y, x] = 4 if y <= 2 else (1 if y <= 5 else 5)
    # drop shadow: one more dark pixel down-right
    for y in range(8, 0, -1):
        for x in range(8, 0, -1):
            if t[y, x] == 0 and g[y - 1, x - 1]: t[y, x] = 2
    return t[1:9, 1:9]
bg_tiles = [np.zeros((8, 8), np.uint8)]
for ch in FONT_CHARS[1:]: bg_tiles.append(glyph(ch))
FONT_BASE = 0  # font char i -> tile i (space=0 blank)
def ftile(ch): return FONT_CHARS.index(ch)

tile_index = {}
def add_tile(t):
    """dedupe with h/v flips; returns (index, hflip, vflip)"""
    t = np.asarray(t, np.uint8)
    for hf in (0, 1):
        for vf in (0, 1):
            v = t[:, ::-1] if hf else t
            v = v[::-1, :] if vf else v
            k = v.tobytes()
            if k in tile_index: return tile_index[k], hf, vf
    tile_index[t.tobytes()] = len(bg_tiles); bg_tiles.append(t.copy()); return len(bg_tiles) - 1, 0, 0
for i, t in enumerate(bg_tiles): tile_index[t.tobytes()] = i

def mapword(tile, pal, hf=0, vf=0, prio=1):
    return tile | (pal << 10) | (prio << 13) | (hf << 14) | (vf << 15)

# text map (overhead/chase): rows 25-26
textmap = [0] * 1024
def puttext(m, row, col, s, pal=4):
    for i, ch in enumerate(s): m[row * 32 + col + i] = mapword(ftile(ch), pal)
L1 = "SCORE 000000"
L2 = "Y:GUN X:CHARGE A:MSL LL/RR:ROLL"   # v1.4: charge shot, barrel roll
puttext(textmap, 25, 1, L1)
puttext(textmap, 26, (32 - len(L2)) // 2, L2)
symbols["SCORE_ADDR_TEXT"] = 0x5C00 + 25 * 32 + 7
symbols["HUD_ADDR_TEXT"] = 0x5C00 + 25 * 32 + 15     # "SH" + 8 bar tiles + " " + jet icon + lives (13 tiles)

# cockpit art: 256x224 image using DASH palette indices (0 transparent)   (graphics v1 rework)
yy2, xx2 = np.mgrid[0:224, 0:256] + 0.5
B4 = np.tile(np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0 + 1 / 32, (56, 64))
arch = np.zeros((224, 256), np.uint8)
e = ((xx2 - 128) / 190) ** 2 + ((yy2 - 150) / 150) ** 2
top = yy2 < 64
# canopy frame: metal with a lit inner rim, rivets and warning-light housings
fr = top & (e > 1.0)
arch[fr] = 3
arch[fr & (e > 1.06)] = 2
arch[fr & (e > 1.06) & (e < 1.075)] = 4
arch[fr & (e > 1.14)] = 1
arch[fr & (e > 1.14) & (B4 > 0.75)] = 2
arch[top & (e > 0.985) & (e <= 1.0)] = 1
arch[top & (e > 1.0) & (e < 1.018)] = 6
arch[top & (e >= 1.018) & (e < 1.03)] = 5
for k in range(-9, 10):
    ang = k * 0.105; rx = 128 + math.sin(ang) * 190 * 1.045; ry = 150 - math.cos(ang) * 150 * 1.045
    if ry < 62:
        ix, iy = int(rx), int(ry)
        if 0 <= ix < 255 and iy >= 0: arch[iy, ix] = 6; arch[iy + 1, ix + 1] = 1 if arch[iy + 1, ix + 1] else 0
for cx in (40, 88, 168, 216):
    m = (abs(xx2 - cx) < 11) & (e > 1.085) & (e < 1.13) & top
    arch[m] = 8
    arch[m & (e > 1.093) & (e < 1.122) & (abs(xx2 - cx) < 9.5)] = 7
    arch[m & (e > 1.093) & (e < 1.104) & (abs(xx2 - cx) < 8)] = 15
ck = arch
D0 = 152
# glare shield lip + panel face with a gentle top-lit gradient (tile-periodic dither)
ck[D0:, :] = 3
for i, c in enumerate((6, 5, 4, 4, 3, 2, 1)): ck[D0 + i, :] = c
ck[D0 + 1, ::4] = 5
ck[D0 + 7, :] = 8; ck[D0 + 8, :] = 7; ck[D0 + 9, :] = 1
face = (yy2 >= D0 + 10)
ck[face & (yy2 < D0 + 14) & (B4 > 0.5)] = 4
ck[face & (yy2 >= D0 + 62) & (B4 > 0.55)] = 2
ck[yy2 >= D0 + 68] = 2
def rect(x0, y0, x1, y1, c): ck[y0:y1, x0:x1] = c
def bevel(x0, y0, x1, y1, w=2):
    rect(x0 - w, y0 - w, x1 + w, y1 + w, 4); rect(x0 - w, y0 - w, x1 + w, y0 - w + 1, 6); rect(x0 - w, y0 - w, x0 - w + 1, y1 + w, 5)
    rect(x0 - w, y1 + w - 1, x1 + w, y1 + w, 1); rect(x1 + w - 1, y0 - w, x1 + w, y1 + w, 1)
    rect(x0, y0, x1, y1, 1)
def screw(x, y):
    rect(x, y, x + 2, y + 2, 5); ck[y, x] = 6; ck[y + 1, x + 1] = 1; ck[y + 2, x + 1:x + 3] = 2
def circ(cx, cy, r, c, ring=None):
    m = (xx2 - cx) ** 2 + (yy2 - cy) ** 2 <= r * r; ck[m] = c
    if ring is not None:
        m2 = m & ((xx2 - cx) ** 2 + (yy2 - cy) ** 2 > (r - 1.2) ** 2); ck[m2] = ring
def lit_ring(cx, cy, r0, r1):
    d = np.sqrt((xx2 - cx) ** 2 + (yy2 - cy) ** 2); m = (d <= r1) & (d > r0)
    l = ((cx - xx2) * 0.6 + (cy - yy2) * 0.8) / np.maximum(d, 0.1)
    ck[m] = 4; ck[m & (l > 0.35)] = 5; ck[m & (l > 0.75)] = 6; ck[m & (l < -0.35)] = 2; ck[m & (l < -0.75)] = 1
def ticks(cx, cy, r, n, c, a0=0, a1=2 * math.pi, L=2):
    for i in range(n):
        a = a0 + (a1 - a0) * i / max(1, n - (0 if a1 - a0 >= 2 * math.pi - 1e-6 else 1))
        for t in range(L):
            x = int(cx + math.sin(a) * (r - t)); y = int(cy - math.cos(a) * (r - t)); ck[y, x] = c
# sub-panel seams + screws
for x in (66, 190):
    rect(x, D0 + 10, x + 1, 224, 1); rect(x + 1, D0 + 10, x + 2, 224, 4)
for x, y in ((2, D0 + 12), (60, D0 + 12), (70, D0 + 12), (184, D0 + 12), (194, D0 + 12), (252, D0 + 12),
             (70, D0 + 64), (184, D0 + 64)):
    screw(x, y)
# left radar screen
bevel(9, D0 + 13, 59, D0 + 61); rect(10, D0 + 14, 58, D0 + 60, 9)
circ(34, D0 + 37, 22, 9, 10); circ(34, D0 + 37, 15, 9, 10); circ(34, D0 + 37, 8, 9, 10)
rect(33, D0 + 15, 35, D0 + 59, 10); rect(12, D0 + 36, 56, D0 + 38, 10)
ticks(34, D0 + 37, 22, 24, 11, L=2)
for x in range(10, 58, 2): ck[D0 + 14, x] = 10
# small dials with ticks and coloured arcs
for cx in (84, 172):
    for cy, kind in ((D0 + 25, 0), (D0 + 49, 1)):
        lit_ring(cx, cy, 8.0, 10.5); circ(cx, cy, 8, 1)
        ticks(cx, cy, 7.6, 9, 14, -2.3, 2.3, L=2)
        for a in np.linspace(1.2, 2.3, 6):
            ck[int(cy - math.cos(a) * 7.5), int(cx + math.sin(a) * 7.5)] = 13
        if kind == 0: rect(cx, cy - 6, cx + 1, cy + 1, 15)
        else:
            for t in range(6): ck[cy, cx - t] = 15
        ck[cy, cx] = 6
# centre attitude housing (the ball sprite sits inside)
lit_ring(128, D0 + 30, 18.5, 23.5); circ(128, D0 + 30, 18.5, 1)
for a in (0.785, 2.356, 3.927, 5.498): screw(int(128 + math.sin(a) * 21) - 1, int(D0 + 30 - math.cos(a) * 21) - 1)
ticks(128, D0 + 30, 18.2, 12, 6, L=1)
# centre console / stick base
rect(116, D0 + 56, 140, 224, 1); rect(117, D0 + 57, 139, 224, 2); rect(117, D0 + 57, 139, D0 + 58, 4)
rect(124, D0 + 60, 132, 224, 3); rect(124, D0 + 60, 125, 224, 5); rect(131, D0 + 60, 132, 224, 1)
rect(121, D0 + 64, 135, D0 + 67, 4); rect(121, D0 + 64, 135, D0 + 65, 6)
# right digital panel (ALT / SPD digits are BG2 text on top)
bevel(197, D0 + 13, 247, D0 + 61); rect(198, D0 + 14, 246, D0 + 60, 9)
for y in range(D0 + 14, D0 + 60, 2): rect(198, y, 246, y + 1, 9)
rect(198, D0 + 14, 246, D0 + 15, 10)
# annunciator buttons: lit caps with a shadow
for i, x in enumerate(range(90, 112, 6)):
    c = (13, 7, 13, 7)[i]; rect(x, D0 + 61, x + 5, D0 + 66, 1); rect(x, D0 + 61, x + 4, D0 + 65, c); ck[D0 + 61, x] = 14
for i, x in enumerate(range(145, 167, 6)):
    c = (7, 15, 7, 15)[i]; rect(x, D0 + 61, x + 5, D0 + 66, 1); rect(x, D0 + 61, x + 4, D0 + 65, c); ck[D0 + 61, x] = 14
for x in (74, 180):
    rect(x, D0 + 64, x + 5, D0 + 70, 1); rect(x, D0 + 64, x + 4, D0 + 69, 14); rect(x, D0 + 68, x + 4, D0 + 69, 6)
# build cockpit tilemap (pal 3 = colors 48..)
cockmap = [0] * 1024
for ty in range(28):
    for tx in range(32):
        t = ck[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]
        if not t.any(): continue
        idx, hf, vf = add_tile(t)
        cockmap[ty * 32 + tx] = mapword(idx, 3, hf, vf)
puttext(cockmap, 8 + 19, 1, "ALT", 5) if False else None
# digit fields in the right panel: row 21: "ALT" ; row 23: "SPD"
def puttext_green(row, col, s): puttext(cockmap, row, col, s, 5)
puttext_green(21, 25, "ALT"); puttext_green(24, 25, "SPD")
puttext_green(22, 25, "00000"); puttext_green(25, 25, "000")
puttext(cockmap, 1, 10, "SCORE 000000", 4)
symbols["SCORE_ADDR_COCK"] = 0x5C00 + 1 * 32 + 16
symbols["HUD_ADDR_COCK"] = 0x5C00 + 2 * 32 + 9
# yellow hint on the cockpit text row (bottom)
puttext(cockmap, 27, 2, "SELECT:VIEW  B:BOOST  START:PAUSE", 4) if False else None
symbols["COCK_ALT_ADDR"] = 0x5C00 + 22 * 32 + 25
symbols["COCK_SPD_ADDR"] = 0x5C00 + 25 * 32 + 25
symbols["TEXT_ROW_ADDR"] = 0x5C00 + 26 * 32
# shield bar segments (colour 1 bright, 3 mid, 2 dark edge) + a jet icon for lives
def bar_tile(fill):
    """framed, bevelled shield segment: 2 dark frame, 4 highlight, 1 main, 5 lower, 3 recessed"""
    t = np.zeros((8, 8), np.uint8)
    t[0, :] = 2; t[7, :] = 2; t[:, 7] = 2
    t[1:7, 0:7] = 3; t[1, 0:7] = 2; t[2:7, 0] = 2          # recessed empty slot
    if fill >= 1:
        w = 3 if fill == 1 else 6
        t[2:6, 1:1 + w] = 1; t[2, 1:1 + w] = 4; t[5, 1:1 + w] = 5; t[6, 1:1 + w] = 2
    return t
symbols["T_BAR0"] = len(bg_tiles); bg_tiles.append(bar_tile(0))
symbols["T_BAR1"] = len(bg_tiles); bg_tiles.append(bar_tile(1))
symbols["T_BAR2"] = len(bg_tiles); bg_tiles.append(bar_tile(2))
icon = np.zeros((8, 8), np.uint8)
for y, r in enumerate(["...1....", "...1....", "..111...", ".11111..", "1111111.", "...1....", "..111...", "........"]):
    for x, ch in enumerate(r):
        if ch == '1': icon[y, x] = 1
icon2 = icon.copy()
for y in range(8):
    for x in range(8):
        if icon[y, x] == 0 and ((y > 0 and icon[y - 1, x]) or (x > 0 and icon[y, x - 1])): icon2[y, x] = 2
symbols["T_LIFE"] = len(bg_tiles); bg_tiles.append(icon2)
# double-size font for GAME OVER (each glyph -> 2x2 tiles), drawn in colour 1 with a dark outline (2)
BIG = {}
for ch in "GAMEOVRWNI":
    bits = FONT[ch]; g = np.zeros((16, 16), np.uint8)
    for y in range(7):
        for x in range(5):
            if bits[y * 5 + x] == '1': g[1 + y * 2:3 + y * 2, 3 + x * 2:5 + x * 2] = 1   # centred: mirror-dedupe
    o = g.copy()
    for y in range(16):
        for x in range(16):
            if g[y, x] == 0 and any(0 <= y + dy < 16 and 0 <= x + dx < 16 and g[y + dy, x + dx] == 1
                                    for dy in (-1, 0, 1) for dx in (-1, 0, 1)): o[y, x] = 2
    o[(g == 1) & (np.arange(16)[:, None] >= 9)] = 3      # lower half darker (shading)
    words = []
    for ty in range(2):
        for tx in range(2):
            idx, hf, vf = add_tile(o[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8].copy())
            words.append(idx | (hf << 14) | (vf << 15))
    BIG[ch] = words
with open(f"{OUT}/bigfont.inc", "w") as fo:
    fo.write("; 2x2-tile glyphs (BG2 map words without palette): TL, TR, BL, BR\n")
    for ch, w in BIG.items(): fo.write(f"BIG_{ch}: .word " + ",".join(f"${x:04X}" for x in w) + "\n")
print("bg2 tiles:", len(bg_tiles))
# HUD / warning / game-over strings: .byte length, font tiles
TEXTS = {"TX_WARN_F": "MISSILE! BREAK L/R", "TX_WARN_B": "MISSILE BEHIND! B:BOOST",
         "TX_PRESS": "PRESS START FOR TITLE", "TX_FINAL": "FINAL SCORE", "TX_PAUSED": "PAUSED",
         "TX_BEAM": "BEAM! CLIMB OR DIVE", "TX_WARNING": "!! WARNING !!", "TX_MISSION": "MISSION COMPLETE",
         "TX_BONUS": "BONUS", "TX_BOSS": "BOSS", "TX_APPROACH": "HUGE ENEMY APPROACHING",
         "TX_AIM": "MATCH HEIGHT - SHOOT GEM/EYES", "TX_FORT": "FORTRESS",
         "TX_ST1": "STAGE 1", "TX_ST2": "STAGE 2", "TX_ST3": "STAGE 3", "TX_ST4": "STAGE 4",
         "TX_SN1": "OCEAN STRIKE", "TX_SN2": "DESERT STORM", "TX_SN3": "ARCTIC FRONT", "TX_SN4": "NIGHT RAID",
         "TX_FORTW": "SKY FORTRESS APPROACHING", "TX_PUP_P": "SPREAD GUN!", "TX_PUP_M": "RAPID MISSILES!",
         "TX_PUP_S": "SHIELD REPAIRED!", "TX_PUP_P2": "SPREAD GUN LV2!", "TX_PUP_P3": "MAX POWER! LV3",
         "TX_CHARGE": "CHARGE READY!",
         "TX_TAUNT": "NAVEED, I WILL DESTROY YOU!", "TX_DADWIN": "DAD DEFEATED!",
         "TX_DADAPP": "DAD APPROACHING", "TX_DADAIM": "MATCH HEIGHT - SHOOT HIS GLASSES",
         "TX_CHECK": "CHECKPOINT!", "TX_SAND": "SANDSTORM! FIGHT THE WIND", "TX_BLIZ": "BLIZZARD! FIGHT THE WIND",
         "TX_FLAK": "FLAK BARRAGE! KEEP MOVING", "TX_CONVOY": "BOMBER CONVOY! MEDALS X2",
         "TX_MEDMAX": "MEDALS MAXED! 5000 EACH", "TX_MEDLOST": "MEDAL CHAIN LOST",
         "TX_CONT": "START:CONTINUE  SELECT:TITLE"}
with open(f"{OUT}/texts.inc", "w") as fo:
    for k, v in TEXTS.items():
        fo.write(f"{k}: .byte {len(v)}," + ",".join(str(ftile(ch)) for ch in v) + "\n")
assert len(bg_tiles) <= 256, len(bg_tiles)   # BG3 band map lives at VRAM $5000
symbols["FONT_0"] = ftile('0')
open(f"{OUT}/bg2tiles.bin", "wb").write(b"".join(to4bpp(t) for t in bg_tiles))
open(f"{OUT}/map_text.bin", "wb").write(b"".join(struct.pack("<H", w) for w in textmap))
open(f"{OUT}/map_cock.bin", "wb").write(b"".join(struct.pack("<H", w) for w in cockmap))
# ----------------------------------------------------------------- BG3 horizon band (graphics v1)
# Mode 1 BG3 (2bpp, palette 7 = CGRAM 28-31) above the horizon in the chase and cockpit views: distant
# islands and a cumulus bank, 512 px wide, scrolled with the heading (1024 px per turn).
setpal(28, ["#000000", "#7c9cc4", "#b2cae4", "#f4f8fc"])
BW, BH = 512, 24
band = np.zeros((BH, BW), np.uint8)
br = np.random.default_rng(404)
yyb, xxb = np.mgrid[0:BH, 0:BW] + 0.5
# distant islands: low ridges on the horizon line
ridge = np.full(BW, -1.0)
for cx, w_, hgt in ((40, 70, 11), (150, 40, 6), (230, 90, 15), (330, 30, 5), (400, 80, 10), (480, 36, 6)):
    for x in range(BW):
        dx = min(abs(x - cx), BW - abs(x - cx)) / w_
        if dx < 1: ridge[x] = max(ridge[x], hgt * (1 - dx * dx) ** 0.7 * (1 + 0.18 * math.sin(x * 0.21 + cx)))
for x in range(BW):
    if ridge[x] > 0.5:
        top = BH - 1 - ridge[x]
        band[int(math.ceil(top)):, x] = 1
        # lit western slopes
        if ridge[(x - 1) % BW] < ridge[x] - 0.15: band[int(math.ceil(top)):int(math.ceil(top)) + 3, x] = 2
# cumulus bank: puffs sitting on a flat base just above the horizon
for cx in list(range(10, BW, 46)):
    cx += int(br.integers(-12, 12)); base = BH - 3 - int(br.integers(0, 3))
    for k in range(int(br.integers(3, 6))):
        px = cx + br.uniform(-16, 16); r = br.uniform(3.5, 7.5); py = base - r * br.uniform(0.3, 0.9)
        dx = np.minimum(abs(xxb - px), BW - abs(xxb - px)); d = np.sqrt(dx ** 2 + (yyb - py) ** 2)
        m = (d < r) & (yyb < base)
        lit = ((px - xxb) * 0.5 + (py - yyb) * 0.9) / r
        band[m & (lit > -0.25)] = 3
        band[m & (lit <= -0.25)] = np.where(band[m & (lit <= -0.25)] == 3, 3, 2)
# BG3 tiles: dedupe with flips; tile numbers start at $300 (VRAM word $5800 with BG3 chars at $4000)
def to2bpp(t):
    out = bytearray(16)
    for y in range(8):
        for x in range(8):
            v = int(t[y][x]); out[y * 2] |= (v & 1) << (7 - x); out[y * 2 + 1] |= ((v >> 1) & 1) << (7 - x)
    return bytes(out)
b3tiles = [np.zeros((8, 8), np.uint8)]; b3idx = {b3tiles[0].tobytes(): 0}
b3map = [0] * (64 * 32)      # empty = BG3 tile 0 (= BG2 tile 0 bytes, blank)
BAND_ROW0 = 5
for ty in range(BH // 8):
    for tx in range(BW // 8):
        t = band[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]; hit = None
        for hf in (0, 1):
            for vf in (0, 1):
                v = t[:, ::-1] if hf else t
                v = v[::-1, :] if vf else v
                if v.tobytes() in b3idx and hit is None: hit = (b3idx[v.tobytes()], hf, vf)
        if hit is None:
            b3idx[t.tobytes()] = len(b3tiles); b3tiles.append(t.copy()); hit = (len(b3tiles) - 1, 0, 0)
        n, hf, vf = hit
        mx = tx % 32 + (tx // 32) * 32 * 32 + (BAND_ROW0 + ty) * 32 if False else None
        # 64x32 map = two 32x32 screens side by side
        scr, cx_ = divmod(tx, 32)
        b3map[scr * 1024 + (BAND_ROW0 + ty) * 32 + cx_] = (0x300 + n) | (7 << 10) | (hf << 14) | (vf << 15)
print("bg3 band tiles:", len(b3tiles))
assert len(b3tiles) <= 128
open(f"{OUT}/bg3tiles.bin", "wb").write(b"".join(to2bpp(t) for t in b3tiles))
# only the band rows are uploaded (the rest of VRAM is cleared at boot): screen 0 rows 5-7, screen 1 rows 5-7
rows_ = b3map[BAND_ROW0 * 32:(BAND_ROW0 + 3) * 32] + b3map[1024 + BAND_ROW0 * 32:1024 + (BAND_ROW0 + 3) * 32]
open(f"{OUT}/map_bg3.bin", "wb").write(b"".join(struct.pack("<H", w) for w in rows_))
symbols["BG3_ROWS_VRAM0"] = 0x5000 + BAND_ROW0 * 32; symbols["BG3_ROWS_VRAM1"] = 0x5400 + BAND_ROW0 * 32
Image.fromarray(np.array([CGRAM[28 + i] if i else (90, 140, 220) for i in range(4)], np.uint8)[band]).resize((BW * 2, BH * 2), Image.NEAREST).save(f"{OUT}/preview_band.png")
# v1.5: a distinct horizon band per stage (ocean islands + cumulus as above, desert mesas, arctic ice
# peaks, night-city skyline with lit windows); uploaded with the stage palette (src/v11.s X_ViewLoad)
def band_tiles(bd):
    tl = [np.zeros((8, 8), np.uint8)]; ix = {tl[0].tobytes(): 0}; mp = [0] * (64 * 32)
    for ty in range(BH // 8):
        for tx in range(BW // 8):
            t = bd[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]; hit = None
            for hf in (0, 1):
                for vf in (0, 1):
                    v = t[:, ::-1] if hf else t
                    v = v[::-1, :] if vf else v
                    if v.tobytes() in ix and hit is None: hit = (ix[v.tobytes()], hf, vf)
            if hit is None:
                ix[t.tobytes()] = len(tl); tl.append(t.copy()); hit = (len(tl) - 1, 0, 0)
            n, hf, vf = hit; scr, cx_ = divmod(tx, 32)
            mp[scr * 1024 + (BAND_ROW0 + ty) * 32 + cx_] = (0x300 + n) | (7 << 10) | (hf << 14) | (vf << 15)
    rows = mp[BAND_ROW0 * 32:(BAND_ROW0 + 3) * 32] + mp[1024 + BAND_ROW0 * 32:1024 + (BAND_ROW0 + 3) * 32]
    return tl, rows
def band_desert():
    bd = np.zeros((BH, BW), np.uint8); r = np.random.default_rng(77)
    h = np.zeros(BW)
    for xx in range(BW):                                          # low rolling dunes on the horizon
        h[xx] = 2.2 + 1.6 * math.sin(xx * 2 * math.pi / 128) + 0.9 * math.sin(xx * 2 * math.pi / 37 + 1.3)
    cap = np.zeros(BW, bool)
    x = 6
    while x < BW - 10:                                            # buttes / mesas: caprock + talus slopes
        w_ = int(r.integers(10, 40)); hg = float(r.integers(7, 19)); sl = r.uniform(0.5, 1.6)
        for xx in range(x - 8, x + w_ + 8):
            if not 0 <= xx < BW: continue
            d = max(0, x - xx, xx - (x + w_))                      # outside the cap: talus falls off
            v = hg - d * sl * (1 + 0.3 * math.sin(xx * 1.7)) if d else hg
            if v > h[xx]: h[xx] = v; cap[xx] = d == 0
        x += w_ + int(r.integers(14, 60))
    for xx in range(BW):
        top = int(round(BH - h[xx]))
        if top >= BH: continue
        bd[top:, xx] = 1
        rising = h[(xx + 1) % BW] <= h[xx] + 0.01 and h[(xx - 1) % BW] < h[xx] - 0.3
        west = h[(xx - 2) % BW] < h[xx] - 0.5
        if west or (cap[xx] and not cap[(xx + 4) % BW]): bd[top:, xx] = 2          # sunlit west slopes
        if cap[xx]:
            bd[top, xx] = 3
            if top + 1 < BH and bd[top + 1, xx] == 1: bd[top + 1, xx] = 2   # caprock lip
    return bd
def band_arctic():
    bd = np.zeros((BH, BW), np.uint8); r = np.random.default_rng(91)
    h = np.zeros(BW)
    for k in range(26):
        cx = r.uniform(0, BW); w_ = r.uniform(10, 42); hg = r.uniform(5, 21)
        for xx in range(BW):
            dx = min(abs(xx - cx), BW - abs(xx - cx)) / w_
            if dx < 1: h[xx] = max(h[xx], hg * (1 - dx) ** 1.15)
    hs = h
    for xx in range(BW):
        if hs[xx] < 1: continue
        top = int(BH - hs[xx]); bd[top:, xx] = 1
        if hs[(xx - 1) % BW] < hs[xx] - 0.05: bd[top:, xx] = 2          # sunlit west faces
        snow = int(1.5 + hs[xx] * 0.32)
        bd[top:min(BH, top + snow), xx] = 3
    return bd
def band_city():
    bd = np.zeros((BH, BW), np.uint8); r = np.random.default_rng(5)
    x = 0
    while x < BW:
        w_ = int(r.choice([8, 8, 16, 16, 24])); h_ = int(r.choice([6, 9, 11, 14, 17, 20, 22]))
        top = BH - h_
        bd[top:, x:x + w_] = 1
        bd[top, x:x + w_] = 2
        pat = int(r.integers(0, 3))
        for yy in range(top + 2, BH - 1, 3):                      # window rows on an 8 px grid (dedupes)
            for xx in range(x + 1, min(BW, x + w_) - 1, 2):
                if (pat == 0 and (xx // 2 + yy // 3) % 3) or (pat == 1 and xx % 4 == 1) or (pat == 2 and (yy // 3) % 2):
                    bd[yy, xx] = 3
        if h_ >= 17 and r.random() < 0.6: bd[max(0, top - 4):top, x + w_ // 2] = 2   # antenna
        x += w_
    return bd
BANDS = [band, band_desert(), band_arctic(), band_city()]
band_bin = bytearray(); bandmap_bin = bytearray()
for k, bd in enumerate(BANDS):
    tl, rows = band_tiles(bd)
    print(f"band {k}: {len(tl)} tiles")
    assert len(tl) <= 128, (k, len(tl))
    band_bin += b"".join(to2bpp(t) for t in tl).ljust(2048, b"\0")
    bandmap_bin += b"".join(struct.pack("<H", w) for w in rows)
open(f"{OUT}/bands.bin", "wb").write(band_bin); open(f"{OUT}/bandmaps.bin", "wb").write(bandmap_bin)

open(f"{OUT}/palette.bin", "wb").write(b"".join(struct.pack("<H", bgr555(c)) for c in CGRAM))
# text for pause
symbols["FONT_P"] = ftile('P')
for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    symbols[f"FONT_{ch}"] = ftile(ch)
symbols["FONT_SP"] = 0; symbols["FONT_COLON"] = ftile(':'); symbols["FONT_EXCL"] = ftile('!')
symbols["FONT_SLASH"] = ftile('/'); symbols["FONT_GT"] = ftile('>'); symbols["FONT_DASH"] = ftile('-')

# ----------------------------------------------------------------- perspective tables
HOR, F, D0P, KC = 64, 160.0, 4.0, 64.0
def entries(nlines):
    js = []
    for j in range(min(32, nlines)): js.append((j, 1))
    j = 32
    while j < nlines: js.append((j + 0.5, 2)); j += 2
    return js
CH_LINES, CK_LINES = 136, 88
ents = entries(CH_LINES)
NE = len(ents); NE_CK = len(entries(CK_LINES))
NLEV = 64
def cam_h(L): return 26.0 + L * 1.25
pers = bytearray()
for L in range(NLEV):
    hh = cam_h(L); sa = []
    for jm, cnt in ents:
        sa.append(min(32767, int(round(hh / (jm + D0P) * 256))))   # z/F in 8.8
    pers += struct.pack(f"<{NE}H", *sa)
open(f"{OUT}/persp.bin", "wb").write(bytes(pers))
symbols.update(NE_CH=NE, NE_CK=NE_CK, NE_CH2=NE - 32, NE_CK2=NE_CK - 32, PERSP_LEVEL_BYTES=NE * 2, HOR=HOR, FOCAL=int(F))
sint = [max(-255, min(255, int(round(math.sin(i * 2 * math.pi / 256) * 256)))) for i in range(256)]
open(f"{OUT}/sin.bin", "wb").write(struct.pack("<256h", *sint))
# camera height table (for cloud projection) in px
OVS = [0x90 + (L * 7) // 4 for L in range(NLEV)]
open(f"{OUT}/overs.bin", "wb").write(bytes(OVS))
open(f"{OUT}/overinv.bin", "wb").write(bytes(min(255, int(round(65536 / v - 256))) for v in OVS))
open(f"{OUT}/camh.bin", "wb").write(bytes(int(cam_h(L)) for L in range(NLEV)))

# ----------------------------------------------------------------- static HDMA tables
def hdma_count_split(n, payload, out):
    while n > 0:
        c = min(n, 127); out.append(c); out += payload; n -= c
sky = []
SKY_STOPS = [(0.0, "#1838a0"), (0.35, "#3266cc"), (0.70, "#6ea2e4"), (0.90, "#b4d6f2"), (1.0, "#e8f0f0")]
for y in range(64):
    t = y / 63
    for (t0, c0), (t1, c1) in zip(SKY_STOPS, SKY_STOPS[1:]):
        if t0 <= t <= t1:
            a_, b_ = hexrgb(c0), hexrgb(c1); f_ = (t - t0) / (t1 - t0)
            c = tuple(int(a_[i] + (b_[i] - a_[i]) * f_) for i in range(3)); break
    sky.append(bgr555(c))
def cgram_table(sky_lines, rest):  # rest: list of (count, color)
    out = bytearray()
    if sky_lines:
        out.append(0x80 | sky_lines)
        for v in sky[64 - sky_lines:]: out += bytes([0, 0, v & 255, v >> 8])
    for cnt, col in rest:
        hdma_count_split(cnt, bytes([0, 0, col & 255, col >> 8]), out)
    out.append(0); return bytes(out)
STRIP = bgr555(hexrgb("#101828")); DASHBG = bgr555(hexrgb("#0e2a12"))   # = digit screen colour
WATER = bgr555(hexrgb("#1d4ea6"))
tabs = {}
tabs["cg_chase"] = cgram_table(64, [(136, WATER), (1, STRIP)])
tabs["cg_cock"] = cgram_table(64, [(88, WATER), (1, DASHBG)])
tabs["cg_over"] = cgram_table(0, [(200, WATER), (1, STRIP)])
def mode_table(segs):
    out = bytearray()
    for cnt, m in segs: hdma_count_split(cnt, bytes([m]), out)
    out.append(0); return bytes(out)
tabs["md_chase"] = mode_table([(64, 1), (136, 7), (1, 1)])
tabs["md_cock"] = mode_table([(64, 1), (88, 7), (1, 1)])
tabs["md_over"] = mode_table([(200, 7), (1, 1)])
tabs["tm_chase"] = mode_table([(64, 0x16), (136, 0x13), (1, 0x02)])
tabs["tm_cock"] = mode_table([(64, 0x16), (88, 0x13), (1, 0x12)])
tabs["tm_over"] = mode_table([(200, 0x13), (1, 0x02)])
haze = bytearray(); haze.append(64); haze += bytes([0x20, 0xE0])
lines = 56; haze.append(0x80 | lines)
for i in range(lines):
    v = (1 - i / lines) ** 2.2 * 15
    r = int(v * 0.75); gb = int(v)
    haze += bytes([0x20 | r, 0xC0 | gb])
haze.append(1); haze += bytes([0x20, 0xE0]); haze.append(0)
haze = bytes([0x20, 0xC0])  # placeholder removed below
hz = bytearray(); hz.append(64); hz += bytes([0x20, 0xC0]); lines = 64; hz.append(0x80 | lines)
for i in range(lines):
    v = (1 - i / lines) ** 1.7 * 17
    hz += bytes([0x20 | min(31, int(v * 0.8)), 0xC0 | min(31, int(v))])
hz.append(1); hz += bytes([0x20, 0xC0]); hz.append(0)
tabs["haze"] = bytes(hz)

# ----------------------------------------------------------------- v1.1 stages: palettes, sky + haze tables
# Each stage = full CGRAM image (ground recolour by terrain colour name, BG3 band, clouds) + sky gradient
# (chase/cockpit CGRAM HDMA tables) + horizon haze (COLDATA HDMA). Map A = the archipelago, map B = land-heavy.
GN = {n: s_ for (n, _), s_ in zip(terrain.GROUND, terrain.SLOTS)}
STAGES = [
  dict(name="OCEAN STRIKE", map=0, water="#1d4ea6", ground={}, band=None, cloud=(1.0, 1.0, 1.0),
       sky=[(0.0, "#1c3490"), (0.38, "#3c68c4"), (0.66, "#8a9cd4"), (0.84, "#e4aea8"), (0.95, "#ffcc94"), (1.0, "#fff0c8")],
       haze=(1.0, 0.86, 0.80, 18), anim="dawn"),
  dict(name="DESERT STORM", map=1, water="#cfa062", ground=dict(
       deep3="#c08e52", deep="#cfa062", deep2="#dcb072", swell="#e6c084", crest="#f0d29c", fleck="#f8e4bc", white="#fff2d8",
       shal1="#c09058", shal2="#b07e4c", shal3="#9c6c42", shal4="#86593a", foam="#6e4830",
       sand1="#c8643e", sand2="#ac5032", sand3="#8e3e28", wet="#723020",
       g1="#e09656", g2="#cc8046", g3="#b86c3a", g4="#9e5830", g5="#844626",
       f1="#a0603a", f2="#88502e", f3="#704026", f4="#58301c", f5="#402214",
       r1="#ecdcbc", r2="#c8b28c", r3="#947e62", r4="#645442",
       road1="#c0ae92", road2="#786a56", roof1="#d89868", roof2="#a86a44", roof3="#f2e2c8", roof4="#e4b070",
       dark="#3c2a1a", plaza="#e2d2b0"),
       band=["#000000", "#8a4e4a", "#d08066", "#ffd0a0"], cloud=(1.0, 0.8, 0.68),
       sky=[(0.0, "#1a2462"), (0.30, "#44438e"), (0.56, "#a85c84"), (0.76, "#ec8a56"), (0.90, "#ffb85c"), (1.0, "#fff0b0")],
       haze=(1.0, 0.62, 0.45, 22), anim="heat", pal6=["#5a3a1e", "#8a6034", "#c09050", "#ecc890", "#7a4a32", "#b0785a", "#ffe070", "#2a2018"]),
  dict(name="ARCTIC FRONT", map=1, water="#143658", ground=dict(
       deep3="#0e2a46", deep="#143658", deep2="#1a4268", swell="#2a5a82", crest="#6c9ec2", fleck="#cce6f6", white="#ffffff",
       shal1="#3c7ca2", shal2="#5c9ec2", shal3="#8ec6de", shal4="#bae2f0", foam="#f0f8fc",
       sand1="#f4f8fc", sand2="#dce8f2", sand3="#bacadc", wet="#9cb2c6",
       g1="#ffffff", g2="#eef4fa", g3="#d8e4f0", g4="#bccee0", g5="#a0b6cc",
       f1="#5c7c76", f2="#486860", f3="#36544e", f4="#26403c", f5="#182c2a",
       r1="#cad2da", r2="#9ca6b2", r3="#6e7886", r4="#4a525e",
       wheat1="#e8eef4", wheat2="#c8d4e0", soil1="#8c98a6", soil2="#6c7886", crop1="#dce6ee", crop2="#c2d0dc",
       road1="#8c949e", road2="#4c545e", roof3="#ffffff", dark="#1a2430", plaza="#d8e0e8"),
       band=["#000000", "#8ea8c4", "#cadaea", "#ffffff"], cloud=(0.94, 0.97, 1.0),
       sky=[(0.0, "#0a1636"), (0.36, "#1c3664"), (0.62, "#4a6c9c"), (0.84, "#9cb6d6"), (1.0, "#eef6fc")],
       haze=(0.9, 1.0, 1.0, 22), anim="aurora", pal6=["#14301e", "#2a5a3a", "#4e8a5e", "#9ccaa8", "#8eb8d4", "#f0f8ff", "#ffe070", "#1a3a5a"]),
  dict(name="NIGHT RAID", map=0, water="#040c1e", ground=dict(
       deep3="#020814", deep="#040c1e", deep2="#061428", swell="#0a1c36", crest="#1c3664", fleck="#4c70a6", white="#a4bce4",
       shal1="#08183a", shal2="#0c2246", shal3="#123052", shal4="#1c405e", foam="#3c5c7c",
       sand1="#2c2c3a", sand2="#22222e", sand3="#1a1a26", wet="#14141e",
       g1="#162818", g2="#122214", g3="#0e1c10", g4="#0a160c", g5="#061008",
       f1="#0e1e12", f2="#0a180e", f3="#08140a", f4="#060e06", f5="#040a04",
       r1="#3c3c48", r2="#2e2e3a", r3="#22222c", r4="#181820",
       wheat1="#201e16", wheat2="#1a1810", soil1="#16120e", soil2="#120e0a", crop1="#162216", crop2="#121c12",
       road1="#ffb444", road2="#a8661e", roof1="#ffe274", roof2="#c48434", roof3="#fff8d4", roof4="#ffa444",
       dark="#080808", plaza="#86643e", tarmac="#12161a", tarm2="#ff3a30"),
       band=["#000000", "#0a1026", "#202e5c", "#ffcf5a"], cloud=(0.36, 0.42, 0.58),
       sky=[(0.0, "#000004"), (0.48, "#040a20"), (0.78, "#0e1c46"), (0.92, "#2e2a5c"), (1.0, "#6a4258")],
       haze=(0.2, 0.5, 0.5, 9), anim="neon", pal6=["#0c1208", "#18220e", "#263418", "#3a4a28", "#2c3038", "#464c58", "#ffe070", "#0a1428"],
       night=True),
]
def sky_words(stops):
    out = []
    for y in range(64):
        t = y / 63
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                a_, b_ = hexrgb(c0), hexrgb(c1); f_ = (t - t0) / (t1 - t0)
                c = tuple(int(a_[i] + (b_[i] - a_[i]) * f_) for i in range(3)); break
        out.append(bgr555(c))
    return out
def cg_tab(sw, sky_lines, rest):
    out = bytearray(); out.append(0x80 | sky_lines)
    for v in sw[64 - sky_lines:]: out += bytes([0, 0, v & 255, v >> 8])
    for cnt, col in rest: hdma_count_split(cnt, bytes([0, 0, col & 255, col >> 8]), out)
    out.append(0); return bytes(out)
def haze_tab(rk, gk, bk, amp):
    hz = bytearray(); hz.append(64); hz += bytes([0x20, 0xC0]); hz.append(0x80 | 64)
    for i in range(64):
        v = (1 - i / 64) ** 1.7 * amp
        hz += bytes([0x20 | min(31, int(v * rk)), 0xC0 | min(31, int(v * gk))])
    hz.append(1); hz += bytes([0x20, 0xC0]); hz.append(0); return bytes(hz)
SKYTAB_SZ = 0x180; HAZE_SZ = 0xA0; OVER_SZ = 0x10
stage_bin = bytearray()
for st in STAGES:
    cg = list(CGRAM)
    for n, c in st["ground"].items(): cg[GN[n]] = hexrgb(c)
    if st["band"]:
        for i, c in enumerate(st["band"]): cg[28 + i] = hexrgb(c)
    for i in range(1, 16):
        r_, g_, b_ = CGRAM[144 + i]; k = st["cloud"]; cg[144 + i] = (int(r_ * k[0]), int(g_ * k[1]), int(b_ * k[2]))
    for i, c in enumerate(st.get("pal6", [])): cg[232 + i] = hexrgb(c)
    if st.get("night"):      # v1.2: sprites darken at night (moonlit blue); lamps, flames, windows stay lit
        keep = {128: (8, 9, 13, 14, 15), 176: (6, 7, 14), 224: (6, 7, 14) + tuple(range(8, 14)), 240: (14, 15)}
        for base_, kp in keep.items():
            for i in range(1, 16):
                if i in kp: continue
                r_, g_, b_ = cg[base_ + i]; cg[base_ + i] = (int(r_ * 0.55), int(g_ * 0.62), int(min(255, b_ * 0.8 + 6)))
    pal = b"".join(struct.pack("<H", bgr555(c)) for c in cg)
    sw = sky_words(st["sky"])
    wt = bgr555(hexrgb(st["water"]))
    t1 = cg_tab(sw, 64, [(136, wt), (1, STRIP)]); t2 = cg_tab(sw, 64, [(88, wt), (1, DASHBG)])
    t3 = bytearray(); hdma_count_split(200, bytes([0, 0, wt & 255, wt >> 8]), t3)
    hdma_count_split(1, bytes([0, 0, STRIP & 255, STRIP >> 8]), t3); t3.append(0)
    assert len(t3) <= OVER_SZ
    hz = haze_tab(*st["haze"][:3], st["haze"][3])
    assert len(t1) <= SKYTAB_SZ and len(t2) <= SKYTAB_SZ and len(hz) <= HAZE_SZ
    stage_bin += pal + t1.ljust(SKYTAB_SZ, b"\0") + t2.ljust(SKYTAB_SZ, b"\0") + hz.ljust(HAZE_SZ, b"\0") + bytes(t3).ljust(OVER_SZ, b"\0")
    # preview of the recoloured map
    mp = open(f"{OUT}/m7map{'B' if st['map'] else ''}.bin", "rb").read(); tl = open(f"{OUT}/m7tiles{'B' if st['map'] else ''}.bin", "rb").read()
    idx = np.frombuffer(tl, np.uint8).reshape(256, 8, 8)[np.frombuffer(mp, np.uint8)].reshape(128, 128, 8, 8).swapaxes(1, 2).reshape(1024, 1024)
    Image.fromarray(np.array(cg, np.uint8)[idx][::2, ::2]).save(f"{OUT}/preview_stage{STAGES.index(st)}.png")
STAGE_SZ = 512 + 2 * SKYTAB_SZ + HAZE_SZ + OVER_SZ
# v1.4: water shimmer. Per stage 8 phases of the wave-stroke and surf colours (the NMI writes one phase
# every 8 frames): crests / flecks / whitecaps sparkle in a travelling wave, the surf line breathes.
SHIM = ["swell", "crest", "fleck", "white", "foam", "shal4", "roof1", "roof4", "tarm2"]   # v1.5: + neon slots
SHIM_AMP = [1.0, 0.0, 1.0, 0.7]            # desert dunes stay still
def _lerp(a, b, f): return tuple(int(round(a[i] + (b[i] - a[i]) * f)) for i in range(3))
shim_bin = bytearray()
for si, st in enumerate(STAGES):
    cg = list(CGRAM)
    for n, c in st["ground"].items(): cg[GN[n]] = hexrgb(c)
    col = {n: cg[GN[n]] for n in SHIM[:6] + ["deep2", "shal3"]}
    A = SHIM_AMP[si]
    for ph in range(8):
        w = [0.5 + 0.5 * math.sin(2 * math.pi * (ph / 8 + k / 4)) for k in range(4)]
        out = [_lerp(col["swell"], col["crest"], 0.45 * A * w[0]),
               _lerp(col["crest"], col["fleck"], 0.55 * A * w[1]) if w[1] > 0.5 else _lerp(col["crest"], col["swell"], 0.6 * A * (1 - w[1])),
               _lerp(col["fleck"], col["white"], A * w[2]) if w[2] > 0.5 else _lerp(col["fleck"], col["crest"], 0.8 * A * (1 - w[2])),
               _lerp(col["white"], col["crest"], 0.75 * A * (1 - w[3])),
               _lerp(col["foam"], col["shal4"], 0.55 * A * (0.5 + 0.5 * math.sin(2 * math.pi * ph / 8))),
               _lerp(col["shal4"], col["foam"], 0.4 * A * (0.5 - 0.5 * math.sin(2 * math.pi * ph / 8)))]
        if st.get("night"):      # v1.5: night-city neon palette cycling (signs, rooftops, runway lights)
            NE = [hexrgb(c) for c in ("#ff4ad0", "#ff9a3a", "#ffe86a", "#5af0ff", "#4a8cff", "#c45aff")]
            f8 = ph * len(NE) / 8; i0 = int(f8) % len(NE)
            out += [_lerp(NE[i0], NE[(i0 + 1) % len(NE)], f8 - int(f8)),
                    NE[(i0 + 3) % len(NE)],
                    hexrgb("#ff3a30") if ph % 4 < 2 else hexrgb("#601410")]
        else:
            out += [cg[GN["roof1"]], cg[GN["roof4"]], cg[GN["tarm2"]]]
        for c in out: shim_bin += struct.pack("<H", bgr555(c))
open(f"{OUT}/shim.bin", "wb").write(shim_bin)
# v1.5: animated sky. 16 phases of the chase view's CGRAM sky table per stage (the NMI points HDMA ch 6 at
# the next one every 4 frames: zero CPU). Smooth float gradients, error-diffused line to line (more apparent
# colours than 5-bit steps), plus a per-stage effect: dawn sun glow, desert heat waver, arctic aurora
# curtains, night-city neon glow pulsing on the horizon.
SKYPH_N = 16; SKYPH_SZ = 0x120
def sky_float(stops):
    out = []
    for y in range(64):
        t = y / 63
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                a_, b_ = hexrgb(c0), hexrgb(c1); f_ = (t - t0) / (t1 - t0); f_ = f_ * f_ * (3 - 2 * f_)
                out.append(np.array([a_[i] + (b_[i] - a_[i]) * f_ for i in range(3)], float)); break
    return np.array(out)
def sky_fx(kind, ph):
    a = 2 * math.pi * ph / SKYPH_N; d = np.zeros((64, 3))
    for y in range(64):
        t = y / 63
        if kind == "dawn":       # sun glow on the horizon, breathing
            g = math.exp(-((1 - t) / 0.10) ** 2) * (0.75 + 0.25 * math.sin(a))
            d[y] = np.array([60, 34, 6]) * g
        elif kind == "heat":     # heat waver: bright bands rising through the low sky
            if t > 0.70:
                w = math.sin(t * 46 - a * 2) * ((t - 0.70) / 0.30)
                d[y] = np.array([22, 12, 2]) * w
        elif kind == "aurora":   # curtains of green / teal with magenta tips, drifting
            if 0.06 < t < 0.74:
                e = math.sin(math.pi * (t - 0.06) / 0.68) ** 1.5
                k = (0.5 + 0.5 * math.sin(t * 19 + a)) * (0.55 + 0.45 * math.sin(t * 7.3 - a * 2 + 1.1))
                g = e * k
                tip = max(0.0, 1 - t / 0.26)
                d[y] = np.array([70 * tip + 10, 150 * (1 - 0.6 * tip), 70 + 40 * tip]) * g
        elif kind == "neon":     # city glow: magenta <-> amber on the horizon
            g = math.exp(-((1 - t) / 0.16) ** 2)
            m = 0.5 + 0.5 * math.sin(a)
            d[y] = (np.array([110, 20, 90]) * m + np.array([110, 60, 10]) * (1 - m)) * g * 0.8
    return d
def sky_words_ed(f):
    out = []; err = np.zeros(3)
    for y in range(64):
        v = np.clip(f[y] + err, 0, 255)
        q = np.clip(np.round(v / 8.225), 0, 31)       # 5 bit
        err = (v - q * 8.225) * 0.9
        out.append(int(q[0]) | (int(q[1]) << 5) | (int(q[2]) << 10))
    return out
skyph_bin = bytearray()
for st in STAGES:
    wt = bgr555(hexrgb(st["water"]))
    base = sky_float(st["sky"])
    for ph in range(SKYPH_N):
        t1 = cg_tab(sky_words_ed(base + sky_fx(st.get("anim"), ph)), 64, [(136, wt), (1, STRIP)])
        assert len(t1) <= SKYPH_SZ, len(t1)
        skyph_bin += t1.ljust(SKYPH_SZ, b"\0")
open(f"{OUT}/skyph.bin", "wb").write(skyph_bin)
# v1.5: sun glare. Per stage 4 levels of the COLDATA (ch 7) table, sky lines included: level 0 = the plain
# horizon haze; facing the low sun (dawn / sunset stages) the horizon blooms warm, above and below it.
GL_SZ = 0x110
def glare_tab(rk, gk, bk, amp, lvl, warm):
    hz = bytearray(); hz.append(0x80 | 64)
    for y in range(64):          # sky (BG2/BG3 + backdrop take the fixed colour in the chase view)
        g = lvl / 3 * math.exp(-((63 - y) / 14.0) ** 2) * 15 if lvl else 0
        r_ = int(g * warm[0]); gb = int(g * warm[1])
        hz += bytes([0x20 | min(31, r_), 0xC0 | min(31, gb)])
    hz.append(0x80 | 64)
    for i in range(64):
        v = (1 - i / 64) ** 1.7 * amp
        g = lvl / 3 * math.exp(-(i / 18.0) ** 2) * 12 if lvl else 0
        hz += bytes([0x20 | min(31, int(v * rk + g * warm[0])), 0xC0 | min(31, int(v * gk + g * warm[1]))])
    hz.append(1); hz += bytes([0x20, 0xC0]); hz.append(0)
    assert len(hz) <= GL_SZ
    return bytes(hz).ljust(GL_SZ, b"\0")
glare_bin = bytearray()
for st in STAGES:
    warm = (1.0, 0.62) if st.get("anim") == "dawn" else (1.0, 0.50)
    for lvl in range(4): glare_bin += glare_tab(*st["haze"][:3], st["haze"][3], lvl, warm)
open(f"{OUT}/glare.bin", "wb").write(glare_bin)
# v1.7: sandstorm (stage 2) / blizzard (stage 3) haze, 4 levels each (the same format as the glare tables;
# COLDATA is additive: red, then green = blue). Other stages get the plain haze (unused).
STORM_COL = {1: (15, 8), 2: (12, 13)}
def storm_tab(rk, gk, bk, amp, lvl, col):
    hz = bytearray(); hz.append(0x80 | 64)
    f = lvl / 3
    for y in range(64):
        k = f * (0.45 + 0.55 * y / 63)
        hz += bytes([0x20 | min(31, int(col[0] * k)), 0xC0 | min(31, int(col[1] * k))])
    hz.append(0x80 | 64)
    for i in range(64):
        v = (1 - i / 64) ** 1.7 * amp
        k = f * (1.0 - 0.3 * i / 63)
        hz += bytes([0x20 | min(31, int(v * rk + col[0] * k)), 0xC0 | min(31, int(v * gk + col[1] * k))])
    k = f * 0.7                  # the rest of the ground down to the HUD (line 200): held
    hz.append(72); hz += bytes([0x20 | min(31, int(col[0] * k)), 0xC0 | min(31, int(col[1] * k))])
    hz.append(1); hz += bytes([0x20, 0xC0]); hz.append(0)
    assert len(hz) <= GL_SZ
    return bytes(hz).ljust(GL_SZ, b"\0")
storm_bin = bytearray()
for si, st in enumerate(STAGES):
    for lvl in range(4): storm_bin += storm_tab(*st["haze"][:3], st["haze"][3], lvl, STORM_COL.get(si, (0, 0)))
open(f"{OUT}/storm.bin", "wb").write(storm_bin)
with open(f"{OUT}/v14.inc", "w") as fo:
    fo.write("; generated by tools/gen_assets.py (v1.4)\n")
    _ch = open(f"{OUT}/camh.bin", "rb").read()
    _sy = []
    for h_ in _ch:                    # v1.5 jet shadow: screen top y per altitude level (see v14.s X15_Shadow)
        z_ = h_ + 40 - 17; _sy.append(min(255, 64 + (h_ * ((40960 + z_ // 2) // z_) >> 8) - 8))
    fo.write("ShadowY: .byte " + ",".join(str(v) for v in _sy) + "\n")
    fo.write(f"NSHIM = {len(SHIM)}\nSKYPH_N = {SKYPH_N}\nSKYPH_SZ = {SKYPH_SZ}\nGL_SZ = {GL_SZ}\n")
    for i, n in enumerate(SHIM): fo.write(f"SHIM_I{i} = {GN[n]}\n")
open(f"{OUT}/stages.bin", "wb").write(stage_bin)
with open(f"{OUT}/stages.inc", "w") as fo:
    fo.write(f"NSTAGES = {len(STAGES)}\nSTAGE_SZ = {STAGE_SZ}\nSKYTAB_SZ = {SKYTAB_SZ}\nHAZE_SZ = {HAZE_SZ}\nOVER_SZ = {OVER_SZ}\n")
    fo.write("StageMap: .word " + ",".join(str(st["map"]) for st in STAGES) + "\n")
with open(f"{OUT}/tables.inc", "w") as fo:
    for k, v in tabs.items():
        fo.write(f"{k}:\n")
        for i in range(0, len(v), 16): fo.write("  .byte " + ",".join(f"${b:02x}" for b in v[i:i + 16]) + "\n")
# clouds in world: x,y (px), height(px above sea), shape(0/1), small(0/1)
cl = []
r = random.Random(77)
for i in range(16):
    cl.append((r.randrange(0, 1024), r.randrange(0, 1024), r.choice((14, 30, 46, 62, 80, 100)), r.randrange(2), 1 if r.random() < 0.35 else 0))
cl[0] = (470, 600, 20, 0, 0); cl[1] = (560, 520, 60, 1, 0); cl[2] = (430, 470, 96, 0, 1)
cl[3] = (540, 680, 70, 1, 1); cl[4] = (590, 610, 40, 0, 0); cl[5] = (420, 690, 50, 1, 0)
with open(f"{OUT}/clouds.inc", "w") as fo:
    fo.write(f"NUM_CLOUDS = {len(cl)}\ncloud_x:\n  .word " + ",".join(str(c[0]) for c in cl) + "\n")
    fo.write("cloud_y:\n  .word " + ",".join(str(c[1]) for c in cl) + "\n")
    fo.write("cloud_h:\n  .word " + ",".join(str(c[2]) for c in cl) + "\n")
    fo.write("cloud_shape:\n  .word " + ",".join(str(c[3] + 2 * c[4]) for c in cl) + "\n")
# logical sprite frames -> per-view (tile | kind << 12); kind 0 = 16x16, 1 = 32x32 large (cockpit),
# 2 = 32x32 drawn as four 16x16 (chase), 3 = 32x32 small (overhead)
FRAMES = ["EL_TOW", "EL_AWAY", "EM", "EM_BANK", "ES", "EXS", "EXXS", "X32A", "X32B", "X16A", "X16B",
          "DEB0", "DEB1", "BUL0", "BUL1", "MSL", "TOP0", "TOP1", "TOP2", "EBUL0", "EBUL1", "EMSL", "X16C", "PUFF",
          "BORB0", "BORB1", "BSHARD",
          "BOMB_N", "BOMB_F", "FORT_C", "FORT_W", "PU_P", "PU_M", "PU_S", "HSPARK",
          "EMY0", "EMY1", "EMY2", "EMY3", "EMY4", "SLOT0", "SLOT1", "SLOT2", "SLOT3", "SLOT4", "SLOT5",
          "PRM0", "PRM1", "PRM2", "PRM3", "PRF0", "PRF1", "PRF2", "PRF3", "EM"]
BIG32 = ("EL_TOW", "EL_AWAY", "X32A", "X32B", "BOMB_N", "FORT_C", "FORT_W", "SLOT0", "SLOT1", "SLOT2", "SLOT3", "SLOT4", "SLOT5")
_V11S = {f"EMY{u}": "EM" for u in range(5)}; _V11S.update({f"SLOT{k}": "EL_TOW" for k in range(6)})
_V11S.update({f"PR{a}{i}": "EXXS" for a in "MF" for i in range(4)})
SUBST = {"cock": {"HSPARK": "X16A", "X16C": "X16B", "PUFF": "EXXS", "EL_AWAY": "EL_TOW", "EM_BANK": "EM", "DEB1": "DEB0", "TOP0": "EM", "TOP1": "EM", "TOP2": "EM"},
         "chase": {"TOP0": "EMY4", "TOP1": "EMY4", "TOP2": "EMY4", "EM": "EMY4", "EL_AWAY": "EL_TOW", "EM_BANK": "EMY2"},
         "over": {"BOMB_N": "TOP0", "BOMB_F": "TOP0", "FORT_C": "TOP0", "FORT_W": "TOP0", "PU_P": "X16A", "PU_M": "X16A",
                  "PU_S": "X16A", "HSPARK": "X16A", "BORB0": "EBUL0", "BORB1": "EBUL1", "BSHARD": "EBUL1", "PUFF": "X16B", "EL_TOW": "TOP0", "EL_AWAY": "TOP0", "EM": "TOP0", "EM_BANK": "TOP0", "ES": "TOP0", "EXS": "TOP0", "EXXS": "TOP0"}}
SUBST["cock"].update(_V11S); SUBST["over"].update({k: "TOP0" for k in _V11S})
with open(f"{OUT}/frames.inc", "w") as fo:
    fo.write(f"NFRAMES = {len(FRAMES)}\nFrameTab:\n")
    for view in ("chase", "over", "cock"):
        words = []
        for f in FRAMES:
            n = SUBST[view].get(f, f)
            t = symbols[f"T_{view.upper()}_{n}"]
            kind = 3 if view == "over" else ((2 if view == "chase" else 1) if n in BIG32 else 0)
            words.append(t | (kind << 12))
        fo.write("  .word " + ",".join(f"${w:04x}" for w in words) + f"   ; {view}\n")
    for i, f in enumerate(FRAMES[:-1]):
        fo.write(f"F_{f} = {i}\n")
for v in ("CHASE", "COCK"):
    symbols[f"T_{v}_CLOUDB1"] = symbols[f"T_{v}_CLOUDB0"]; symbols[f"T_{v}_CLOUDS1"] = symbols[f"T_{v}_CLOUDS0"]
pf = bytearray()
for ch in POPFONT: pf += to4bpp(pop_glyph(ch, 6))
for ch in POPFONT: pf += to4bpp(pop_glyph(ch, 9))     # orange set (combo multiplier)
open(f"{OUT}/popfont.bin", "wb").write(pf)
with open(f"{OUT}/symbols.inc", "w") as fo:
    for k, v in symbols.items(): fo.write(f"{k} = {v}\n")
print("ok; symbols:", len(symbols))

# ----------------------------------------------------------------- sprite preview (dev only)
if os.environ.get("PREVIEW"):
    def col(g, base): return np.array([CGRAM[base + i] if i else (40, 40, 60) for i in range(16)], np.uint8)[g]
    tiles_ = []
    for r in (0, 22, 44): tiles_.append(col(render_jet("chase", r, 64, 1.9, pitch_deg=38), 128))
    for base in (176, 224, 240):
        for args in ((0, 180, 32, 1.02), (0, 0, 32, 1.02), (35, 180, 16, 0.5), (0, 180, 16, 0.5)):
            tiles_.append(col(render_enemy("chase", *args), base))
    for k, g in fx_frames().items(): tiles_.append(col(g, 128 if not k.startswith("DEB") else 176))
    for r in (0, 25, 50): tiles_.append(col(render_jet("top", r, 32, 0.95), 128))
    W = 64 * 8; x = y = 0; rowh = 0; canvas = np.full((300, W, 3), 20, np.uint8)
    for t in tiles_:
        h_, w_ = t.shape[:2]
        if x + w_ > W: x = 0; y += rowh + 4; rowh = 0
        canvas[y:y + h_, x:x + w_] = t; x += w_ + 4; rowh = max(rowh, h_)
    Image.fromarray(canvas[:y + rowh]).resize((W * 3, (y + rowh) * 3), Image.NEAREST).save(f"{OUT}/preview_sprites.png")
