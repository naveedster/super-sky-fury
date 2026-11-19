"""Boss robot pixel art (front view, mirror-symmetric), Capcom-style shading.

Palette 7 (OBJ) layout, chase/cockpit views during the boss fight:
 1 outline   2-4 dark joints   5-9 white armour ramp   10-12 blue ramp
 13 eyes (animated)   14 chest gem (animated)   15 green ankle lights
"""
import numpy as np
from PIL import Image, ImageDraw

BOSS_PAL = ["#000000", "#0a0c1c", "#1e2234", "#363c54", "#58627e",
            "#5e6c8c", "#93a2c2", "#c4cee2", "#e9eef8", "#ffffff",
            "#0e2470", "#2652d0", "#5a98ff", "#ff2a1c", "#f01c18", "#3cff6a"]
W, H = 96, 128
AX = 48           # mirror axis
GEM = (48, 41)    # anchor: centre of the chest gem (also the hit point)
EYE_Y = 22        # eye row (sprite px)

WHITE = [5, 6, 7, 8, 9]
BLUE = [10, 11, 12]
DARK = [2, 3, 4]

def _parts(arm_up):
    """(name, polygon or ('circle', cx, cy, r), material ramp, base level, style) back to front, left half"""
    P = []
    def add(name, pts, ramp, base, style='flat'):
        P.append((name, pts, ramp, base, style))
    # crest spikes behind the helmet: white blades with a blue inner edge
    spikes = [((48, 0), (42, 12), (48, 12)),
              ((40, 0), (37, 13), (47, 10)),
              ((29, 3), (35, 15), (43, 9)),
              ((19, 9), (34, 19), (40, 11)),
              ((11, 19), (34, 24), (37, 15)),
              ((10, 32), (35, 29), (36, 21))]
    for i, (tip, b0, b1) in enumerate(spikes):
        t2 = (tip[0] + 2, tip[1] + 1) if i else (tip[0], tip[1])
        add(f'spike{i}', [tip, t2, b1, b0], WHITE, 3, 'blade')
        # blue edge along the lower/outer side of each blade (tip -> b0)
        mx, my = (b0[0] * 0.62 + b1[0] * 0.38), (b0[1] * 0.62 + b1[1] * 0.38)
        if i:
            add(f'spikeb{i}', [tip, b0, (mx, my)], BLUE, 1, 'flat')
    # arms (behind the shoulder pads)
    if not arm_up:
        add('uparm', [(16, 43), (26, 43), (26, 58), (15, 58)], DARK, 1, 'cyl')
        add('forearm', [(8, 55), (25, 55), (24, 75), (9, 75)], WHITE, 2, 'cyl')
        add('cuff', [(6, 63), (26, 63), (26, 72), (6, 72)], BLUE, 1, 'cyl')
        add('fist', [(9, 74), (23, 74), (24, 82), (21, 87), (11, 87), (8, 82)], WHITE, 2, 'dome')
        add('knuckle', [(10, 79), (22, 79), (22, 80), (10, 80)], WHITE, 1, 'flat')
    else:
        # arm raised to the side, forearm aimed at you: big round cuff = cannon muzzle
        add('uparm', [(14, 40), (27, 38), (27, 48), (14, 52)], DARK, 1, 'cyl')
        add('forearm', ('circle', 12, 46, 11.5), WHITE, 2, 'dome')
        add('cuff', ('circle', 12, 46, 8.5), BLUE, 1, 'dome')
        add('muzzle', ('circle', 12, 46, 5.0), DARK, 0, 'flat')
        add('glow', ('circle', 12, 46, 2.6), [13, 13, 9], 1, 'flat')
    # shoulder pads
    add('pad', [(4, 20), (15, 27), (31, 25), (37, 30), (35, 43), (18, 47), (9, 42), (7, 31)], WHITE, 2, 'dome')
    add('padb', [(8, 41), (17, 46), (35, 42), (35, 39), (17, 43), (9, 38)], BLUE, 1, 'flat')
    # torso
    add('abdomen', [(34, 47), (48, 47), (48, 64), (37, 64)], DARK, 1, 'cyl')
    add('chest', [(30, 29), (48, 29), (48, 52), (41, 54), (34, 49), (29, 38)], WHITE, 2, 'dome')
    add('vent', [(32, 43), (38, 41), (38, 43), (33, 45)], BLUE, 0, 'flat')
    add('gem', [(39, 35), (48, 35), (48, 48)], [14, 14, 9], 1, 'flat')
    add('collar', [(37, 26), (48, 26), (48, 32), (39, 31)], BLUE, 1, 'flat')
    # helmet + face
    add('helm', [(36, 13), (48, 9), (48, 23), (44, 21), (40, 19), (36, 23)], WHITE, 2, 'dome')
    add('visor', [(37, 20), (40, 19), (48, 24), (48, 31), (42, 30), (38, 25)], BLUE, 1, 'flat')
    add('face', [(44, 26), (48, 27), (48, 31), (45, 30)], DARK, 0, 'flat')
    add('eye', [(39, 20), (46, 23), (46, 25), (40, 22)], [13, 13, 13], 1, 'flat')
    # hips + legs
    add('pelvis', [(35, 61), (48, 61), (48, 72), (44, 74), (36, 70)], WHITE, 2, 'dome')
    add('pvent', [(44, 64), (48, 64), (48, 68), (44, 68)], BLUE, 1, 'flat')
    add('crotch', [(44, 70), (48, 70), (48, 98), (45, 98)], DARK, 0, 'flat')
    add('thigh', [(34, 68), (45, 71), (44, 90), (33, 88)], WHITE, 2, 'cyl')
    add('knee', [(32, 86), (45, 88), (45, 97), (33, 96)], WHITE, 2, 'dome')
    add('shin', [(30, 94), (46, 95), (46, 112), (29, 112)], WHITE, 2, 'cyl')
    add('chev', [(31, 101), (38, 107), (46, 101), (46, 105), (38, 111), (31, 105)], BLUE, 1, 'flat')
    add('boot', [(28, 110), (46, 110), (46, 121), (42, 126), (32, 126), (28, 121)], WHITE, 2, 'dome')
    add('bootb', [(28, 108), (46, 108), (46, 111), (28, 111)], BLUE, 1, 'flat')
    add('ankle', ('circle', 30.0, 113.0, 2.6), [15, 15, 9], 1, 'flat')
    return P

def _raster(pts):
    im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
    if pts[0] == 'circle':
        _, cx, cy, r = pts
        yy, xx = np.mgrid[0:H, 0:W] + 0.5
        return ((xx - cx) ** 2 + (yy - cy) ** 2) <= r * r
    d.polygon([(x, y) for x, y in pts], fill=1, outline=1)
    m = np.array(im) > 0
    return m

def _shift(m, dy, dx):
    o = np.zeros_like(m)
    ys = slice(max(0, dy), H + min(0, dy)); yd = slice(max(0, -dy), H + min(0, -dy))
    xs = slice(max(0, dx), W + min(0, dx)); xd = slice(max(0, -dx), W + min(0, -dx))
    o[ys, xs] = m[yd, xd]
    return o

def render(arm_up=False):
    """full 96x128 index image (palette 7 indices), mirror-symmetric"""
    parts = _parts(arm_up)
    img = np.zeros((H, W), np.uint8)
    pid = np.zeros((H, W), np.int16)
    yy, xx = np.mgrid[0:H, 0:W]
    for k, (name, pts, ramp, base, style) in enumerate(parts, start=1):
        m = _raster(pts)
        m[:, AX:] = False
        m |= m[:, ::-1]                    # mirror (full image)
        if not m.any():
            continue
        # neighbours outside the part, toward the light (upper-left) and away from it
        lvl = np.full((H, W), base, int)
        out = ~m
        tl1 = _shift(out, 1, 1) | _shift(out, 1, 0) | _shift(out, 0, 1)      # pixel up/left is outside
        br1 = _shift(out, -1, -1) | _shift(out, -1, 0) | _shift(out, 0, -1)
        br2 = _shift(out, -2, -2) | _shift(out, -2, 0) | _shift(out, 0, -2)
        ys, xs = np.nonzero(m)
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        # left/right halves of the mirrored part are lit from the upper-left of each half's own side? No:
        # one light for the whole robot (upper left), so the right half is darker overall.
        if style == 'cyl':
            # per half: highlight band on the left third, shade on the right
            for side in (0, 1):
                sm = m & ((xx < AX) if side == 0 else (xx >= AX))
                if not sm.any():
                    continue
                sx = xx[sm]; a, b = sx.min(), sx.max() + 1
                u = (xx - a) / max(1, (b - a))
                lvl[sm & (u > 0.18) & (u < 0.38)] += 1
                lvl[sm & (u > 0.72)] -= 1
                lvl[sm & (u > 0.9)] -= 1
        elif style == 'dome':
            for side in (0, 1):
                sm = m & ((xx < AX) if side == 0 else (xx >= AX))
                if not sm.any():
                    continue
                sx = xx[sm]; sy = yy[sm]
                cx, cy = (sx.min() + sx.max() + 1) / 2, (sy.min() + sy.max() + 1) / 2
                rx, ry = max(2, (sx.max() + 1 - sx.min()) / 2), max(2, (sy.max() + 1 - sy.min()) / 2)
                nx = (xx + 0.5 - cx) / rx; ny = (yy + 0.5 - cy) / ry
                lit = -(nx * 0.55 + ny * 0.75)
                lvl[sm & (lit > 0.15)] += 1
                lvl[sm & (lit > 0.7)] += 1
                lvl[sm & (lit < -0.3)] -= 1
                lvl[sm & (lit < -0.8)] -= 1
        elif style == 'blade':
            lvl[m] += 1
        lvl[m & tl1] += 1
        lvl[m & br1] -= 1
        if style in ('dome', 'cyl', 'blade'):
            lvl[m & br2 & ~br1] -= 0
        # the robot's right half (screen right) a touch darker: one key light from the upper left
        lvl[m & (xx >= AX) & ~tl1] -= (1 if style in ('dome', 'cyl', 'blade') and len(ramp) > 3 else 0)
        lvl = np.clip(lvl, 0, len(ramp) - 1)
        col = np.array(ramp)[lvl]
        img[m] = col[m]
        grp = {'spike': 1, 'spikeb': 1, 'knuckle': 0, 'padb': 0, 'vent': 0, 'pvent': 0, 'chev': 0, 'bootb': 0}
        key = name.rstrip('0123456789')
        if key in ('spike', 'spikeb'):
            pid[m] = 1                      # whole crest = one group (no seams between its blades)
        elif key in ('knuckle', 'padb', 'vent', 'pvent', 'chev', 'bootb', 'face'):
            pid[m] = np.where(pid[m] > 0, pid[m], k)   # decals: inherit the part below (no seam)
        else:
            pid[m] = k
    # outlines: outer silhouette, and seams where a part meets a part drawn over it
    opaque = img > 0
    edge = opaque & (~_shift(opaque, 1, 0) | ~_shift(opaque, -1, 0) | ~_shift(opaque, 0, 1) | ~_shift(opaque, 0, -1))
    seam = np.zeros_like(opaque)
    for dy, dx in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        nb = np.zeros_like(pid); 
        nb[max(0, dy):H + min(0, dy), max(0, dx):W + min(0, dx)] = pid[max(0, -dy):H + min(0, -dy), max(0, -dx):W + min(0, -dx)]
        seam |= opaque & (nb > pid) & (nb > 0)
    out = img.copy()
    out[seam] = 1
    out[edge] = 1
    # keep the glowing bits bright (no outline eating 2-px eyes / lights)
    for c in (13, 15):
        out[(img == c) & seam] = c
    return out

def pieces16(img):
    """left half (cols 0-2) cut into 16x16 cells: {(col,row): array}; empty cells omitted"""
    cells = {}
    for r in range(H // 16):
        for c in range(AX // 16):
            t = img[r * 16:r * 16 + 16, c * 16:c * 16 + 16]
            if t.any():
                cells[(c, r)] = t.copy()
    return cells

def beam_orb(big):
    g = np.zeros((16, 16), np.uint8)
    yy, xx = np.mgrid[0:16, 0:16] + 0.5
    d = np.sqrt((xx - 8) ** 2 + (yy - 8) ** 2)
    if big:
        g[d < 7.5] = 14; g[d < 5.5] = 13; g[d < 3.5] = 9; g[(d < 7.5) & (d >= 6.8)] = 1
    else:
        g[d < 4.5] = 14; g[d < 2.8] = 9
    return g

def shard_spr():
    rows = ["......1.........",
            ".....1C1........",
            ".....1C91.......",
            "....1CC91.......",
            "....1CC991......",
            "...1BCC991......",
            "...1BCCC991.....",
            "..1BBCCCC91.....",
            "..1BBBCCC991....",
            "...1BBBCC91.....",
            "....1BBC91......",
            ".....1BC1.......",
            "......11........",
            "................",
            "................",
            "................"]
    m = {'.': 0, '1': 1, '9': 9, 'B': 11, 'C': 12}
    return np.array([[m[ch] for ch in r] for r in rows], np.uint8)

def flame16(frame):
    """thruster flame pointing down (palette 1 = cloud palette: 7/8/9 orange..yellow, 1 white)"""
    g = np.zeros((16, 16), np.uint8)
    L = 13 + (2 if frame else 0)
    for y in range(min(16, L)):
        w = max(0.6, 3.6 * (1 - y / L))
        for x in range(16):
            dd = abs(x + 0.5 - 8)
            if dd < w + 0.6:
                g[y, x] = 1 if (dd < w * 0.35 and y < L * 0.35) else (9 if dd < w * 0.6 else (8 if dd < w * 0.9 else 7))
    return g

def to_rgb(img, pal=BOSS_PAL, bg=(24, 28, 52)):
    lut = np.array([bg] + [tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in pal[1:]], np.uint8)
    return lut[img]

if __name__ == '__main__':
    a = render(False); b = render(True)
    big = np.concatenate([to_rgb(a), np.zeros((H, 8, 3), np.uint8), to_rgb(b)], 1)
    Image.fromarray(big).resize((big.shape[1] * 4, big.shape[0] * 4), Image.NEAREST).save('/tmp/boss_art.png')
    print('cells', len(pieces16(a)), 'variant', sum(1 for k, v in pieces16(b).items() if k not in pieces16(a) or (pieces16(a)[k] != v).any()))
