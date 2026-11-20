#!/usr/bin/env python3
"""SUPER SKY FURY v1.2 -- the giant robot boss as a voxel model, sprite-stacked in parts.

The v1.0 boss was painted as one flat front view (tools/boss_art.py).  Here the same design (white / blue
armour, red eyes, chest gem, spiky crest) is rebuilt in 3D: every front-view part polygon of boss_art is
extruded into a solid with its own depth and edge rounding (domes, cylinders, plates), decals (visor, vents,
chevrons, the gem, eyes) are painted onto the front surface, and the crest blades fan out backwards.  The
model is split into three groups that the game draws as separate sprite groups:

  body   legs, pelvis, torso with the chest gem, shoulder pads   (front view, symmetric: left half + h-flip)
  head   helmet, visor, eyes and the crest                        (yaw 0, +-18, +-36: the head tracks you)
  arm    upper arm, forearm, cuff, fist / cannon                  (poses: down, cannon aimed at you, spread)

Each frame is rendered with tools/voxstack.render (z-buffered slice stacking, lambert from the upper left,
inner seams from depth steps, BOSS_PAL ramps) and cut into 16x16 cells relative to the chest gem, which
stays the anchor of the weak-point hit boxes.
"""
import math, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boss_art
import voxstack as vs
from PIL import Image, ImageDraw

AX, GEM = boss_art.AX, boss_art.GEM
MX = 40                    # canvas margin (spread arms reach past the art's edges)
CW, CH = boss_art.W + 2 * MX, boss_art.H + 8
MATS = [None]                 # one material per part ("ramp|part"): seams are drawn where parts meet
SEAMG = [-1]
MATG = [None]                 # group of each material (body / head / arm)
_CUR_GROUP = ["body"]
NOSEAM = ("knuckle", "padb", "vent", "pvent", "chev", "bootb", "face")
def mat_id(matn, key):
    nm = f"{matn}|{key}|{_CUR_GROUP[0]}"
    if nm not in MATS:
        MATS.append(nm)
        SEAMG.append(-1 if key in NOSEAM else (1 if key in ("spike", "spikeb") else len(MATS)))
        MATG.append(_CUR_GROUP[0])
    return MATS.index(nm)
BASE_RAMPS = {"white": [5, 6, 7, 8, 9], "blue": [10, 11, 12, 12], "dark": [2, 3, 4], "scorch": [2, 2, 3], "eye": 13, "gem": [14, 14, 14, 9],
         "ankle": 15, "glow": [13, 13, 9], "spike": [5, 6, 7, 8, 9], "red": [13]}
class _Ramps(dict):
    def __missing__(self, k): return BASE_RAMPS[k.split("|")[0]]
RAMPS = _Ramps()
RAMP_OF = {tuple(boss_art.WHITE): "white", tuple(boss_art.BLUE): "blue", tuple(boss_art.DARK): "dark"}
LIGHT = (-0.55, 0.62, 0.56)       # model space: x right, y toward the viewer, z up (upper-left front light)
HEAD = ("spike", "spikeb", "helm", "visor", "face", "eye")
ARM = ("uparm", "forearm", "cuff", "fist", "knuckle", "muzzle", "glow")
DECAL = ("knuckle", "padb", "vent", "pvent", "chev", "bootb", "face", "visor", "eye", "gem", "collar", "ankle", "muzzle", "glow")
# part -> (centre depth, half thickness, edge rounding radius, style)
DEPTH = {"spike": (-4, 1.6, 1.0, "blade"), "spikeb": (-4, 1.8, 1.0, "blade"),
         "uparm": (-1, 5, 4, "cylx"), "forearm": (1, 7, 5, "cylx"), "cuff": (1, 8.5, 5, "cylx"), "fist": (2, 6.5, 5, "dome"),
         "pad": (3, 7, 6, "dome"), "abdomen": (0, 6, 4, "cylx"), "chest": (3, 9, 9, "dome"), "helm": (3, 8, 6, "dome"),
         "pelvis": (2, 7, 5, "dome"), "crotch": (0, 4, 2, "cylx"), "thigh": (1, 6, 5, "cylx"), "knee": (3, 7, 5, "dome"),
         "shin": (2, 7, 5, "cylx"), "boot": (3, 8, 5, "dome")}
PROTRUDE = {"gem": 2, "eye": 1, "glow": 1, "ankle": 1, "collar": 1, "visor": 1, "padb": 1, "chev": 0, "vent": 0}

def _dt(m, cap=24, axis=None):
    """chamfer-ish distance to the outside of mask m (in px, capped); axis='x' measures horizontally only"""
    d = np.zeros(m.shape, float); cur = m.copy()
    for i in range(cap):
        if not cur.any(): break
        d[cur] += 1
        n = cur.copy()
        if axis != "z": n[:, 1:] &= cur[:, :-1]; n[:, :-1] &= cur[:, 1:]
        if axis != "x": n[1:] &= cur[:-1]; n[:-1] &= cur[1:]
        cur = n
    return d

def _mask(pts):
    im = Image.new("L", (CW, CH), 0); d = ImageDraw.Draw(im)
    if pts[0] == "circle":
        _, cx, cy, r = pts
        yy, xx = np.mgrid[0:CH, 0:CW] + 0.5
        return ((xx - cx - MX) ** 2 + (yy - cy) ** 2) <= r * r
    d.polygon([(x + MX, y) for x, y in pts], fill=1, outline=1)
    return np.array(im) > 0

def spread_arm():
    """arm thrown out sideways (beam / shard attacks): left half, art coordinates"""
    B = boss_art
    return [("uparm", [(6, 37), (27, 37), (27, 48), (6, 50)], B.DARK, 1, "cyl"),
            ("forearm", [(-20, 34), (10, 35), (10, 50), (-20, 51)], B.WHITE, 2, "cyl"),
            ("cuff", [(-10, 33), (-2, 33), (-2, 52), (-10, 52)], B.BLUE, 1, "cyl"),
            ("fist", [(-31, 36), (-19, 34), (-17, 42), (-19, 51), (-31, 49), (-33, 42)], B.WHITE, 2, "dome"),
            ("knuckle", [(-30, 40), (-29, 40), (-29, 46), (-30, 46)], B.WHITE, 1, "flat")]

def parts(pose):
    """boss_art's part list with the arm swapped for the pose: 'down', 'cannon' (raised, aimed), 'spread'"""
    P = boss_art._parts(pose == "cannon")
    if pose == "spread":
        P = [p for p in P if p[0] not in ARM]
        P = spread_arm() + P
    return P

DMG_SPOTS = [(14, 31, 4.0), (60, 37, 3.5), (37, 84, 3.0), (58, 104, 3.0)]

def _damage(mat, front, ZD):
    """battle damage (below 1/3 health): blast holes in the armour with scorched rims, asymmetric"""
    sc = mat_id("dark", "scorch"); hole = mat_id("dark", "hole")
    yy, xx = np.mgrid[0:CH, 0:CW]
    for ax_, ay_, r in DMG_SPOTS:
        cx, cy = ax_ + MX, ay_
        d = np.hypot(xx - cx, (yy - cy) * 1.1)
        for z, x in zip(*np.nonzero((d <= r + 2.5) & (front > -99))):
            f = front[z, x]
            if d[z, x] <= r:
                mat[z, max(0, f - 3):f + 1, x] = 0          # dent
                mat[z, max(0, f - 4), x] = hole
            else:
                mat[z, max(0, f - 1):f + 1, x] = sc          # scorched rim
        # soot streak running down from the hole
        for z, x in zip(*np.nonzero((np.abs(xx - cx) <= r * 0.5) & (yy > cy + r) & (yy < cy + r + 5) & (front > -99))):
            if (x + z) % 3: mat[z, front[z, x], x] = sc

def build(pose, group, dmg=False):
    """voxel model of one group (body / head / arm) for an arm pose. Origin = the chest gem."""
    _CUR_GROUP[0] = (group if group != "arm" else "arm_" + pose) + ("_dmg" if dmg else "")
    ZD = 48                                   # depth extent (y), centred
    mat = np.zeros((CH, ZD, CW), np.uint8)    # [z(row, down), y(depth), x]
    front = np.full((CH, CW), -99, int)       # front-most voxel depth index per pixel (for decals)
    yy, xx = np.mgrid[0:CH, 0:CW]
    for name, pts, ramp, base, style in parts(pose):
        key = name.rstrip("0123456789")
        g = "head" if key in HEAD else ("arm" if key in ARM else "body")
        if g != group: continue
        m = _mask(pts)
        if pose != "spread" or key not in ARM:
            if group != "arm":
                m[:, AX + MX:] = False; m |= m[:, ::-1]          # symmetric parts: mirror (whole model)
            else:
                m[:, AX + MX:] = False                           # arm: left one only
        else:
            m[:, AX + MX:] = False
        if not m.any(): continue
        matn = RAMP_OF.get(tuple(ramp), None)
        if key in ("spike",): matn = "spike"
        if key == "spikeb": matn = "blue"
        if key == "eye": matn = "eye"
        if key == "gem": matn = "gem"
        if key == "ankle": matn = "ankle"
        if key == "glow": matn = "glow"
        if key == "muzzle": matn = "dark"
        mid = mat_id(matn or "white", key)
        if key in DECAL and key not in ("muzzle", "glow") or (key in ("muzzle", "glow") and pose != "cannon"):
            # paint onto the front surface (+ optional protrusion); where nothing is below, a thin plate
            pr = PROTRUDE.get(key, 0)
            zc0, th0 = {"visor": (6, 2.5), "collar": (5, 2.5), "face": (6, 2)}.get(key, (3, 2))
            zs, xs = np.nonzero(m)
            for z, x in zip(zs, xs):
                f = front[z, x]
                if f == -99:
                    lo = int(ZD / 2 + zc0 - th0); hi = int(ZD / 2 + zc0 + th0)
                else:
                    lo = max(0, f - 1); hi = min(ZD - 1, f + pr)
                mat[z, lo:hi + 1, x] = mid
                front[z, x] = hi
            continue
        if pose == "cannon" and key in ("forearm", "cuff", "muzzle", "glow"):
            # the raised forearm points at you: a tube along the depth axis
            zc, L = {"forearm": (4, 12), "cuff": (5, 15), "muzzle": (5, 16), "glow": (5, 16)}[key]
            d = _dt(m, 6)
            for z, x in zip(*np.nonzero(m)):
                rnd = min(d[z, x], 3) / 3.0
                hi = int(round(ZD / 2 + zc + L * (0.75 + 0.25 * rnd))) if key in ("forearm", "cuff") else int(ZD / 2 + zc + L)
                lo = int(ZD / 2 + zc - 10)
                hi = min(ZD - 1, hi)
                mat[z, lo:hi + 1, x] = mid
                front[z, x] = max(front[z, x], hi)
            continue
        zc, th, R, st = DEPTH.get(key, (0, 3, 2, "dome"))
        if st == "blade":
            # crest blades fan backwards and thin out toward their tips
            hx, hy = AX + MX, 16
            dist = np.hypot(xx - hx, (yy - hy) * 1.2)
            zcen = zc - dist * 0.14
            thk = np.maximum(0.8, th * (1 - dist / 70))
            for z, x in zip(*np.nonzero(m)):
                lo = int(round(ZD / 2 + zcen[z, x] - thk[z, x])); hi = int(round(ZD / 2 + zcen[z, x] + thk[z, x]))
                mat[z, max(0, lo):min(ZD, hi + 1), x] = mid
                front[z, x] = max(front[z, x], min(ZD - 1, hi))
            continue
        if st == "cylx":
            d = _dt(m, 24, "x")
            if group == "arm" and pose == "spread" and key in ("uparm", "forearm", "cuff"):
                d = _dt(m, 24, "z")            # horizontal limbs round top-bottom
        else:
            d = _dt(m, 24)
        r = np.minimum(d, R) / R
        prof = np.sqrt(np.clip(1 - (1 - r) ** 2, 0, 1))
        if st == "dome":
            # a whole-part bulge on top of the edge rounding
            dd = np.minimum(d, 24) / max(1.0, d.max())
            prof = prof * (0.7 + 0.3 * np.sqrt(np.clip(dd, 0, 1)))
        for z, x in zip(*np.nonzero(m)):
            t = th * prof[z, x]
            lo = int(round(ZD / 2 + zc - t * 0.7)); hi = int(round(ZD / 2 + zc + t))
            lo = max(0, lo); hi = min(ZD - 1, hi)
            if hi < lo: hi = lo
            mat[z, lo:hi + 1, x] = mid
            front[z, x] = max(front[z, x], hi)
    if dmg: _damage(mat, front, ZD)
    m3 = mat[::-1, :, :]                      # z up (Vox wants mat[z, y, x]; y = toward the viewer here)
    origin = (-(GEM[0] + MX), -ZD / 2, -(CH - 1 - GEM[1]))
    return vs.Vox(MATS, m3, origin, 1.0)

def render(vox, yaw=0.0, pitch=6.0, size=208, keep=None):
    vox.mats = MATS
    km = None if keep is None else [i for i, g in enumerate(MATG) if g == keep]
    out = vs.render(vox, RAMPS, "chase", yaw=yaw, pitch_cam=-pitch, size=size, scale=1.0, ss=3, outline=1,
                    light=LIGHT, seam=0, keep_lit=(13, 14, 15), ambient=0.20, gamma=1.8, flat_top=0.04, dither=True,
                    dither_amp=0.3, seam_groups=SEAMG, keep_mats=km)
    return out          # gem at (size/2, size/2)

def cells(img, cx, cy, mirror_half=False, best=True):
    """cut img (gem at cx, cy) into 16x16 cells; returns [(dx, dy, tile16)].  mirror_half: only x < cx
    (grid aligned to the axis), the right half is the h-flip."""
    ys, xs = np.nonzero(img)
    if not len(ys): return []
    y0 = ys.min(); y1 = ys.max() + 1
    if mirror_half:
        x1 = cx; x0 = xs.min()
        offs_x = [0]
    else:
        x0 = xs.min(); x1 = xs.max() + 1
        offs_x = range(16) if best else [0]
    bestc = None
    for ox in offs_x:
        for oy in (range(16) if best else [0]):
            cs = []
            gx0 = (x1 - 16 * math.ceil((x1 - x0) / 16)) if mirror_half else x0 - ox
            for gy in range(y0 - oy, y1, 16):
                for gx in range(gx0, x1, 16):
                    t = np.zeros((16, 16), np.uint8)
                    sy0, sx0 = max(0, gy), max(0, gx)
                    sy1, sx1 = min(img.shape[0], gy + 16), min(x1 if mirror_half else img.shape[1], gx + 16)
                    if sy1 <= sy0 or sx1 <= sx0: continue
                    t[sy0 - gy:sy1 - gy, sx0 - gx:sx1 - gx] = img[sy0:sy1, sx0:sx1]
                    if t.any(): cs.append((gx - cx, gy - cy, t))
            if bestc is None or len(cs) < len(bestc): bestc = cs
    return bestc

POSES = ("down", "cannon", "spread")
HEAD_YAWS = (0, 18, 36)

def build_all():
    """-> dict of rendered frames (palette-index images, gem at (S/2, S/2))"""
    S = 208
    fr = {}
    body = build("down", "body")
    head = build("down", "head")
    arms = {p: build(p, "arm") for p in POSES}
    fr["body"] = render(body)
    fr["body_dmg"] = render(build("down", "body", dmg=True))
    NECK = (0.0, 0.0, 14.0)
    for y in HEAD_YAWS:
        # the head turns about the neck; the body in front of it (shoulder pads) still hides the crest
        sc = vs.Scene([(body, 0, NECK), (head, -y, NECK)], MATS)
        fr[f"head{y}"] = render(sc, keep="head")
    for p in POSES:
        # each arm pose in front of / behind the body and head as the model says
        sc = vs.Scene([(body, 0, NECK), (head, 0, NECK), (arms[p], 0, NECK)], MATS)
        fr[f"arm_{p}"] = render(sc, keep="arm_" + p)
    return fr, S

def compose(fr, S, head=0, arms=("down", "down")):
    """full robot image for previews: body, then arms behind? (game: head over body, arms over body)"""
    img = np.zeros((S, S), np.uint8)
    b = fr["body"].copy(); h = b[:, :S // 2]; b[:, S // 2:] = h[:, ::-1][:, :S - S // 2]
    img = b
    for side, p in enumerate(arms):
        a = fr[f"arm_{p}"]
        if side: a = a[:, ::-1]
        img = np.where(a > 0, a, img)
    hy = abs(head); hf = fr[f"head{hy}"]
    if hy == 0:
        hf = hf.copy(); hf[:, S // 2:] = hf[:, :S // 2][:, ::-1]
    if head < 0: hf = hf[:, ::-1]
    img = np.where(hf > 0, hf, img)
    return img

if __name__ == "__main__":
    fr, S = build_all()
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/bv"
    os.makedirs(out, exist_ok=True)
    tiles = []
    for args in ((0, ("down", "down")), (18, ("cannon", "down")), (-36, ("spread", "spread")), (36, ("down", "cannon"))):
        tiles.append(boss_art.to_rgb(compose(fr, S, *args)))
    tiles.append(boss_art.to_rgb(np.pad(boss_art.render(False), ((40, 40), (56, 56)))))
    big = np.concatenate(tiles, 1)
    Image.fromarray(big).resize((big.shape[1] * 3, big.shape[0] * 3), Image.NEAREST).save(f"{out}/boss_vox.png")
    print("saved")
