#!/usr/bin/env python3
"""SUPER SKY FURY v1.1 -- voxel models + offline sprite-stack renderer.

Every flying object (player jet, enemy fighter, bomber, sky fortress) and the ground props are built as
small voxel models (the plan-form polygons of the v1.0 models are voxelized into thick plates and the
fuselages are filled into real volumes).  render() slices the model into horizontal layers and stacks them
(each voxel is splatted in back-to-front depth order with a z-buffer), so a frame can be produced for any
yaw, bank (roll) and pitch.  Shading: smooth normals from the blurred occupancy field, lambert from the
game's light direction, a top-face highlight per slice, ordered dither between ramp steps, then a 1px dark
outline.  The result is quantized straight to the 15-colour SNES OBJ palette ramps used by the game.

  python3 tools/voxstack.py preview out_dir     # turntable PNG strips + an mp4 of the models rotating
"""
import math, os, sys
import numpy as np

LIGHT = np.array([-0.25, -0.30, 0.92]); LIGHT = LIGHT / np.linalg.norm(LIGHT)
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0 - 0.5

class Vox:
    """voxel grid: mat[z, y, x] = material id (0 empty); origin + res map indices to model units."""
    def __init__(self, mats, mat, origin, res):
        self.mats = mats; self.mat = mat; self.origin = np.asarray(origin, float); self.res = res
        occ = (mat > 0).astype(float)
        # smooth occupancy -> normals (gradient points out of the solid)
        k = occ.copy()
        for ax in range(3):
            k = (np.roll(k, 1, ax) + k + np.roll(k, -1, ax)) / 3.0
        gz, gy, gx = np.gradient(k)
        zi, yi, xi = np.nonzero(mat)
        # keep only voxels that touch air (the hidden core never shows)
        p = np.pad(occ, 1)
        air = np.zeros(len(zi), bool)
        for dz, dy, dx in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            air |= p[zi + 1 + dz, yi + 1 + dy, xi + 1 + dx] == 0
        zi, yi, xi = zi[air], yi[air], xi[air]
        n = -np.stack([gx[zi, yi, xi], gy[zi, yi, xi], gz[zi, yi, xi]], 1)
        nl = np.linalg.norm(n, axis=1, keepdims=True); n = np.where(nl > 1e-6, n / np.maximum(nl, 1e-6), [0, 0, 1.0])
        self.p = np.stack([xi, yi, zi], 1) * res + self.origin      # model coords (x right, y back, z up)
        self.n = n
        self.m = mat[zi, yi, xi]
        self.top = p[zi + 2, yi + 1, xi + 1] == 0                 # nothing above: top face of a slice
        self.layer = zi

def voxelize(polys, res=0.4, fill=None, plate=0.5):
    """polys: [(pts3, material)].  Each polygon becomes a plate `plate` units thick; materials in `fill`
    (name -> z of the keel line) are also filled down to their mirror below the keel (solid fuselages)."""
    fill = fill or {}
    names = [None]
    for _, m in polys:
        if m not in names: names.append(m)
    allp = np.array([p for pts, _ in polys for p in pts], float)
    lo = allp.min(0) - 1.5; hi = allp.max(0) + 1.5
    lo[2] = min(lo[2], -2.0)
    shape = np.ceil((hi - lo) / res).astype(int) + 1
    mat = np.zeros((shape[2], shape[1], shape[0]), np.uint8)
    for pts, m in polys:
        P = np.array(pts, float); mid = names.index(m)
        for i in range(1, len(P) - 1):
            a, b, c = P[0], P[i], P[i + 1]
            L = max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b))
            n = int(L / (res * 0.35)) + 2
            u, v = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n))
            ok = u + v <= 1
            s = a + np.outer(u[ok], b - a) + np.outer(v[ok], c - a)
            if m in fill:
                keel = fill[m]
                z0 = np.minimum(s[:, 2], 2 * keel - s[:, 2]); z1 = np.maximum(s[:, 2], 2 * keel - s[:, 2])
                over = m in ("spine", "canopy", "glint")
                for dz in np.arange(0, (z1 - z0).max() + 1e-6, res * 0.7):
                    ok = z0 + dz <= z1
                    q = np.stack([s[ok, 0], s[ok, 1], z0[ok] + dz], 1)
                    ix = np.round((q - lo) / res).astype(int)
                    cur = mat[ix[:, 2], ix[:, 1], ix[:, 0]]
                    w = (cur == 0) | over
                    mat[ix[w, 2], ix[w, 1], ix[w, 0]] = mid
            th = np.arange(-plate / 2, plate / 2 + 1e-6, res * 0.7) if m not in fill else [0.0]
            for t in th:
                q = s + np.array([0, 0, t])
                ix = np.round((q - lo) / res).astype(int)
                mat[ix[:, 2], ix[:, 1], ix[:, 0]] = mid
    return Vox(names, mat, lo, res)

def render(vox, ramps, view, roll=0.0, yaw=0.0, pitch_cam=38.0, size=32, scale=1.0, ss=4, outline=1, oy=0.0,
           nose_pitch=0.0, dither=True, flat_top=0.10, out_lam=False, light=None, seam=0.0, ox=0.0, keep_lit=(),
           ambient=0.16, gamma=1.5, tumble=None, seam_groups=None, dither_amp=0.55, keep_mats=None):
    """sprite-stack render to a size x size palette-index image.
    v1.2: light (model-space direction), seam (depth step in model units that draws an inner outline, so the
    parts of a model read like hand-drawn panels), ox/oy (pixel offset of the model origin from the centre),
    keep_lit (materials the seams never darken: eyes, lights), tumble (extra (axis, deg) rotation applied first)."""
    L_ = LIGHT if light is None else np.asarray(light, float) / np.linalg.norm(light)
    ph = math.radians(roll); yw = math.radians(yaw); al = math.radians(pitch_cam); npch = math.radians(nose_pitch)
    def xf(v):
        x, y, z = v[:, 0], v[:, 1], v[:, 2]
        if tumble is not None:
            for ax_, deg_ in tumble:
                t_ = math.radians(deg_); c_, s_ = math.cos(t_), math.sin(t_)
                if ax_ == "x": y, z = y * c_ - z * s_, y * s_ + z * c_
                elif ax_ == "y": x, z = x * c_ + z * s_, -x * s_ + z * c_
                else: x, y = x * c_ - y * s_, x * s_ + y * c_
        # nose pitch (nose = -y; positive = nose up), then roll about the long axis, then yaw
        y, z = y * math.cos(npch) + z * math.sin(npch), z * math.cos(npch) - y * math.sin(npch)
        x, z = x * math.cos(ph) + z * math.sin(ph), -x * math.sin(ph) + z * math.cos(ph)
        x, y = x * math.cos(yw) - y * math.sin(yw), x * math.sin(yw) + y * math.cos(yw)
        return np.stack([x, y, z], 1)
    P = xf(vox.p); N = xf(vox.n)
    if view == "top":
        sx, sy, dep = P[:, 0], P[:, 1], P[:, 2]; cam = np.array([0, 0, 1.0])
    else:
        sx = P[:, 0]; sy = -P[:, 2] * math.cos(al) + P[:, 1] * math.sin(al)
        dep = P[:, 1] * math.cos(al) + P[:, 2] * math.sin(al); cam = np.array([0, math.sin(al), math.cos(al)])
    lam = ambient + (1 - ambient) * np.clip(N @ L_, 0, 1)
    if view == "top": lam = 0.40 + 0.60 * np.abs(N @ L_)
    lam = lam + flat_top * vox.top                               # stacked-slice highlight on each layer's top
    lam = np.clip(lam, 0, 1)
    W = size * ss
    cx = (sx * scale + size / 2 + ox) * ss; cy = (sy * scale + size / 2 + oy) * ss
    r = max(1, int(round(vox.res * scale * ss * 1.25)))
    offs = [(dx, dy) for dy in range(r) for dx in range(r)]
    X = np.concatenate([np.floor(cx - r / 2 + dx).astype(int) for dx, dy in offs])
    Y = np.concatenate([np.floor(cy - r / 2 + dy).astype(int) for dx, dy in offs])
    D = np.tile(dep, len(offs)); M = np.tile(vox.m, len(offs)); Lm = np.tile(lam, len(offs))
    ok = (X >= 0) & (X < W) & (Y >= 0) & (Y < W)
    X, Y, D, M, Lm = X[ok], Y[ok], D[ok], M[ok], Lm[ok]
    pix = Y * W + X
    o = np.lexsort((D, pix))                                      # per pixel: nearest (largest depth) last
    pix, M, Lm, D = pix[o], M[o], Lm[o], D[o]
    last = np.r_[pix[1:] != pix[:-1], True]
    mbuf = np.zeros(W * W, np.int32); lbuf = np.zeros(W * W); dbuf = np.full(W * W, -1e9)
    mbuf[pix[last]] = M[last]; lbuf[pix[last]] = Lm[last]; dbuf[pix[last]] = D[last]
    dbuf = dbuf.reshape(size, ss, size, ss).transpose(0, 2, 1, 3).reshape(size, size, ss * ss)
    mbuf = mbuf.reshape(size, ss, size, ss).transpose(0, 2, 1, 3).reshape(size, size, ss * ss)
    lbuf = lbuf.reshape(size, ss, size, ss).transpose(0, 2, 1, 3).reshape(size, size, ss * ss)
    cov = (mbuf > 0).sum(2)
    out = np.zeros((size, size), np.uint8); lout = np.zeros((size, size))
    nm = len(vox.mats)
    cnt = np.stack([(mbuf == k).sum(2) for k in range(nm)], 2); cnt[:, :, 0] = 0
    dom = cnt.argmax(2)
    lsum = (lbuf * (mbuf > 0)).sum(2) / np.maximum(cov, 1)
    dmax = dbuf.max(2)
    keep = (cov * 2 >= ss * ss) | ((cov >= 5) & (cov * 3 > ss * ss))
    for yy in range(size):
        for xx in range(size):
            if not keep[yy, xx]: continue
            mname = vox.mats[dom[yy, xx]]; rp = ramps[mname]
            l = lsum[yy, xx]; lout[yy, xx] = l
            if isinstance(rp, (list, tuple)):
                f = l ** gamma * len(rp) + (BAYER[yy % 4, xx % 4] * dither_amp if dither else 0)
                out[yy, xx] = rp[min(len(rp) - 1, max(0, int(f)))]
            else:
                out[yy, xx] = rp
    if seam_groups is not None and outline:
        # part seams: where two parts meet, the farther one gets a dark line (hand-drawn panel look)
        sg = np.asarray(seam_groups)[dom]
        dm = np.where(out > 0, dmax, -1e9)
        sm = np.zeros_like(out, bool)
        for dy_, dx_ in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            q = np.full_like(dm, -1e9); qg = np.full_like(sg, -1)
            ys_ = slice(max(0, -dy_), size - max(0, dy_)); yd_ = slice(max(0, dy_), size - max(0, -dy_))
            xs_ = slice(max(0, -dx_), size - max(0, dx_)); xd_ = slice(max(0, dx_), size - max(0, -dx_))
            q[ys_, xs_] = dm[yd_, xd_]; qg[ys_, xs_] = sg[yd_, xd_]
            sm |= (out > 0) & (sg >= 0) & (qg >= 0) & (qg != sg) & (q > dm + 0.5)
        lit = np.isin(out, list(keep_lit)) if keep_lit else np.zeros_like(sm)
        out[sm & ~lit] = outline
    if seam and outline:
        dm = np.where(out > 0, dmax, -1e9)
        sm = np.zeros_like(out, bool)
        for dy_, dx_ in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            q = np.full_like(dm, -1e9)
            ys_ = slice(max(0, -dy_), size - max(0, dy_)); yd_ = slice(max(0, dy_), size - max(0, -dy_))
            xs_ = slice(max(0, -dx_), size - max(0, dx_)); xd_ = slice(max(0, dx_), size - max(0, -dx_))
            q[ys_, xs_] = dm[yd_, xd_]
            sm |= (out > 0) & (q > dm + seam)
        lit = np.isin(out, list(keep_lit)) if keep_lit else np.zeros_like(sm)
        out[sm & ~lit] = outline
    if outline:
        o2 = out.copy()
        nz = (out != 0) & (out != outline)
        near = np.zeros_like(nz)
        near[:, 1:] |= nz[:, :-1]; near[:, :-1] |= nz[:, 1:]; near[1:] |= nz[:-1]; near[:-1] |= nz[1:]
        o2[(out == 0) & near] = outline
        out = o2
    if keep_mats is not None:
        # keep one part of a bigger scene: its visible pixels (occluded by the rest as the scene says)
        # plus the outer outline next to them
        kp = np.isin(dom, list(keep_mats)) & keep
        kn = np.zeros_like(kp)
        kn[:, 1:] |= kp[:, :-1]; kn[:, :-1] |= kp[:, 1:]; kn[1:] |= kp[:-1]; kn[:-1] |= kp[1:]
        out = np.where(kp | (kn & ~keep & (out == outline)), out, 0).astype(np.uint8)
    return (out, lout) if out_lam else out

class Scene:
    """several Vox (with their own rotations) rendered as one model: Scene([(vox, yaw_deg, pivot_xyz)])"""
    def __init__(self, items, mats):
        P, N, M, T = [], [], [], []
        for v, yaw, piv in items:
            t = math.radians(yaw); c, s_ = math.cos(t), math.sin(t)
            p = v.p - np.asarray(piv, float); n = v.n.copy()
            p = np.stack([p[:, 0] * c - p[:, 1] * s_, p[:, 0] * s_ + p[:, 1] * c, p[:, 2]], 1) + np.asarray(piv, float)
            n = np.stack([n[:, 0] * c - n[:, 1] * s_, n[:, 0] * s_ + n[:, 1] * c, n[:, 2]], 1)
            P.append(p); N.append(n); M.append(v.m); T.append(v.top)
        self.p = np.concatenate(P); self.n = np.concatenate(N); self.m = np.concatenate(M); self.top = np.concatenate(T)
        self.res = items[0][0].res; self.mats = mats

# ------------------------------------------------------------------ ground props (built voxel by voxel)
def box(mat, x0, x1, y0, y1, z0, z1, m):
    mat[z0:z1, y0:y1, x0:x1] = m

def prop_models():
    """ground objects standing on the Mode 7 plane: 'tower' (radar/control tower), 'tank' (fuel tank),
    'bunker' (AA gun turret). Materials index the PROP ramps."""
    res = 0.5; out = {}
    names = [None, "wall", "roof", "dark", "glass", "red", "metal", "gun"]
    # control tower
    m = np.zeros((40, 24, 24), np.uint8)
    box(m, 6, 18, 6, 18, 0, 6, 1); box(m, 9, 15, 9, 15, 6, 24, 1)
    for z in range(8, 24, 4): box(m, 9, 15, 9, 15, z, z + 1, 3)
    box(m, 7, 17, 7, 17, 24, 29, 4); box(m, 6, 18, 6, 18, 29, 31, 2)
    box(m, 11, 13, 11, 13, 31, 38, 6); box(m, 10, 14, 11, 13, 37, 38, 5); box(m, 11, 13, 10, 14, 37, 38, 5)
    out["tower"] = Vox(names, m, (-6, -6, 0), res)
    # fuel tanks: two cylinders with a pipe
    m = np.zeros((16, 26, 30), np.uint8)
    zz, yy, xx = np.mgrid[0:16, 0:26, 0:30]
    for cx_, cy_ in ((8, 9), (21, 16)):
        r_ = np.hypot(xx - cx_, yy - cy_)
        m[(r_ <= 6.5) & (zz < 11)] = 1
        m[(r_ <= 6.5 - (zz - 11) * 1.3) & (zz >= 11) & (zz < 14)] = 2
        m[(r_ <= 6.6) & (r_ > 5.6) & (zz >= 4) & (zz < 6)] = 5
    box(m, 8, 21, 11, 14, 2, 4, 6)
    out["tank"] = Vox(names, m, (-7.5, -6.5, 0), res)
    # AA bunker: low hexagonal pad, dome and a twin barrel pointing at the sky
    m = np.zeros((16, 24, 24), np.uint8)
    zz, yy, xx = np.mgrid[0:16, 0:24, 0:24]
    r_ = np.hypot(xx - 11.5, yy - 11.5)
    m[(r_ <= 11) & (zz < 3)] = 3; m[(r_ <= 10) & (zz < 3)] = 1
    m[(np.hypot(r_, (zz - 3) * 1.2) <= 7) & (zz >= 3)] = 6
    for bx in (9, 13):
        for k in range(10):
            m[min(15, 6 + k // 2 + 1), 11 - k, bx:bx + 2] = 7
    m[3][(r_[3] <= 10) & (r_[3] > 9)] = 5
    out["bunker"] = Vox(names, m, (-6, -6, 0), res)
    return out

# palette indices into the ENEMY OBJ palette (15 colours; same ramps as the planes)
PROP_RAMPS = {"wall": [5, 12, 12, 13, 13], "roof": [9, 10, 11, 11], "dark": 3, "glass": [15, 15, 5, 13],
              "red": [6, 6, 14], "metal": [4, 5, 12, 13, 13], "gun": [3, 4, 5]}

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "preview":
    sys.argv = [sys.argv[0], "/tmp/voxprev_assets"]
    import importlib.util
    raise SystemExit("run tools/sprite_stack_preview.py instead")

# ------------------------------------------------------------------ v1.2 small tumbling objects
def _ell(shape, c, r):
    zz, yy, xx = np.mgrid[0:shape[0], 0:shape[1], 0:shape[2]]
    return ((xx - c[0]) / r[0]) ** 2 + ((yy - c[1]) / r[1]) ** 2 + ((zz - c[2]) / r[2]) ** 2 <= 1

LETTERS = {"P": ["111.", "1..1", "111.", "1...", "1..."], "M": ["1...1", "11.11", "1.1.1", "1...1", "1...1"],
           "S": [".111", "1...", ".11.", "...1", "111."]}

def tumble_models():
    """small objects that tumble / roll / spin in flight (v1.2): debris chunks, missiles, power-up capsules,
    the boss's crest shards.  Coordinates: x right, y toward the viewer, z up; res 0.5 px."""
    res = 0.5; out = {}
    rnd = np.random.RandomState(7)
    # debris: bent, jagged armour plates (metal, a red paint edge, a hot torn edge)
    for k, seed in ((0, 3), (1, 11)):
        r_ = np.random.RandomState(seed)
        names = [None, "metal", "paint", "hot"]
        m = np.zeros((14, 14, 22), np.uint8)
        zz, yy, xx = np.mgrid[0:14, 0:14, 0:22]
        ang = np.arctan2(zz - 7, xx - 11); rad = np.hypot(xx - 11, (zz - 7) * 1.3)
        lim = 9 + 2.5 * np.sin(ang * 3 + seed) + 1.5 * np.sin(ang * 5 + seed * 2)
        bend = 0.04 * (xx - 11) ** 2 * (1 if k == 0 else -0.6)
        plate = (rad <= lim) & (np.abs(yy - 7 - bend) <= 1.0)
        m[plate] = 1
        m[plate & (rad > lim - 2.2) & (np.sin(ang * 2 + seed) > 0.2)] = 3
        m[plate & (np.abs((xx - zz - 4 * k) % 9) < 2) & (rad < lim - 2)] = 2
        out[f"deb{k}"] = Vox(names, m, (-11 * res * 2 / 2, -7 * res, -7 * res), res)
    # player missile (seen from behind: fins, motor glow); enemy missile (nose toward you, red band)
    names = [None, "body", "fin", "nose", "glow", "band"]
    m = np.zeros((16, 16, 16), np.uint8)
    zz, yy, xx = np.mgrid[0:16, 0:16, 0:16]
    rr = np.hypot(xx - 7.5, zz - 7.5)
    m[(rr <= 3.0) & (yy >= 2) & (yy < 14)] = 1
    m[(rr <= 3.2) & (yy >= 9) & (yy < 11)] = 5
    for a in range(4):                                   # cruciform fins near the tail (y small = far side)
        ca, sa = math.cos(a * math.pi / 2 + 0.3), math.sin(a * math.pi / 2 + 0.3)
        along = (xx - 7.5) * ca + (zz - 7.5) * sa; perp = -(xx - 7.5) * sa + (zz - 7.5) * ca
        m[(along > 2.5) & (along < 7.2) & (np.abs(perp) < 0.7) & (yy >= 2) & (yy < 6)] = 2
    m[(rr <= 1.9) & (yy >= 13) & (yy < 15)] = 3          # nose (toward the viewer)
    out["emsl"] = Vox(names, m.copy(), (-7.5 * res, -8 * res, -7.5 * res), res)
    m2 = m[:, ::-1, :].copy()                            # player missile: tail toward the viewer
    m2[(m2 == 3)] = 1
    m2[(rr <= 2.2) & (yy >= 14)] = 4
    out["msl"] = Vox(names, m2, (-7.5 * res, -8 * res, -7.5 * res), res)
    # power-up capsules: a pill with the letter embossed front and back
    for L_ in "PMS":
        names = [None, "shell", "band", "letter"]
        m = np.zeros((20, 14, 30), np.uint8)
        zz, yy, xx = np.mgrid[0:20, 0:14, 0:30]
        d = np.maximum(np.abs(xx - 14.5) - 5.0, 0) ** 2 + ((yy - 6.5) / 0.7) ** 2 + (zz - 9.5) ** 2
        m[d <= 9.2 ** 2] = 1
        m[(d <= 9.2 ** 2) & (np.abs(xx - 14.5) > 6.0) & (np.abs(xx - 14.5) < 7.5)] = 2
        out[f"pu{L_}"] = Vox(names, m, (-14.5 * res, -6.5 * res, -9.5 * res), res)
    # boss crest shard: a white blade with a blue edge
    names = [None, "white", "blue"]
    m = np.zeros((20, 8, 12), np.uint8)
    zz, yy, xx = np.mgrid[0:20, 0:8, 0:12]
    t = (19 - zz) / 19.0
    blade = (np.abs(xx - 5.5) <= 5.0 * (1 - t) + 0.6) & (np.abs(yy - 3.5) <= 1.6 * (1 - t) + 0.5)
    m[blade] = 1
    m[blade & (xx > 5.5 + 2.5 * (1 - t))] = 2
    out["shard"] = Vox(names, m, (-5.5 * res, -3.5 * res, -9.5 * res), res)
    return out

# ------------------------------------------------------------------ v1.2 ground props per stage
# Materials index OBJ palette 6, which every stage recolours (tools/gen_assets.py STAGE_PAL6):
#   1 outline, 2-5 greys, 6/7 orange (lights, rust), 8-11 nature ramp (palms / sand / pines / ...),
#   12-13 stone (grey / rock / ice), 14 warm light (windows, lamps), 15 dark glass.
PROP12_RAMPS = {"hull": [2, 3, 4, 5], "deck": [4, 5, 12, 12], "mark": [13], "steel": [2, 3, 4, 5, 12],
                "light": [14], "flare": [6, 14], "glass": [15, 15, 5], "trunk": [7, 7, 6], "leaf": [8, 9, 10, 11],
                "sand": [12, 13, 13], "wall": [2, 3, 4, 5], "win": [14], "winoff": [15], "red": [7, 6],
                "stone": [9, 10, 11, 11], "rock": [8, 12, 12, 13], "dish": [4, 5, 12, 13, 13], "camo": [8, 9, 10, 11],
                "dark": [1, 2], "ice": [12, 12, 13, 13, 13], "snow": [12, 13, 13], "pine": [8, 8, 9, 10],
                "metal": [2, 3, 4, 5, 12], "gun": [2, 3, 4], "pad": [3, 4, 5, 12], "wallp": [5, 12, 12, 13, 13],
                "roof": [9, 10, 11, 11]}
P12_NAMES = [None] + list(PROP12_RAMPS)
def _pm(nz, ny, nx):
    return np.zeros((nz, ny, nx), np.uint8), np.mgrid[0:nz, 0:ny, 0:nx]
def _id(n): return P12_NAMES.index(n)

def prop_models_v12():
    res = 0.5; out = {}
    R = np.random.RandomState(12)
    # aircraft carrier: long hull, flat deck with markings, island superstructure (heading = +y)
    m, (zz, yy, xx) = _pm(16, 48, 18)
    w = np.where(yy < 8, 3 + yy * 0.75, np.where(yy > 42, 9 - (yy - 42) * 0.9, 9))
    hull = (np.abs(xx - 8.5) <= w * 0.9) & (zz < 4)
    m[hull] = _id("hull")
    deck = (np.abs(xx - 8.5) <= w) & (zz == 4) & (yy > 1) & (yy < 47)
    m[deck] = _id("deck")
    m[deck & ((np.abs(xx - 8.5) < 0.6) & (yy % 6 < 3))] = _id("mark")
    m[deck & (np.abs(yy - 30 + (xx - 8.5) * 0.6) < 0.6)] = _id("mark")
    isl = (xx >= 13) & (xx <= 15) & (yy >= 22) & (yy <= 30) & (zz >= 5) & (zz < 12)
    m[isl] = _id("steel"); m[isl & (zz == 9) & (yy % 2 == 0)] = _id("light")
    m[(xx == 14) & (yy == 26) & (zz >= 12) & (zz < 15)] = _id("steel")
    out["carrier"] = Vox(P12_NAMES, m, (-8.5 * res, -24 * res, 0), res)
    # palm islet: sand mound with three palms
    m, (zz, yy, xx) = _pm(30, 30, 30)
    r_ = np.hypot(xx - 14.5, yy - 14.5)
    m[(r_ <= 13 - zz * 2.2) & (zz < 4)] = _id("sand")
    for (px, py, h, lean) in ((11, 13, 20, (-0.25, 0.1)), (18, 16, 24, (0.2, -0.15)), (15, 20, 16, (0.05, 0.3))):
        for z in range(2, h):
            cx_, cy_ = px + lean[0] * z, py + lean[1] * z
            m[z][(np.hypot(xx[0] - cx_, yy[0] - cy_) <= 1.0)] = _id("trunk")
        tx, ty = px + lean[0] * h, py + lean[1] * h
        for k in range(7):
            a = k * 2 * math.pi / 7 + px
            for t_ in np.linspace(0, 1, 14):
                fx, fy = tx + math.cos(a) * 9 * t_, ty + math.sin(a) * 9 * t_
                fz = h + 2 * t_ - 9 * t_ * t_
                xi, yi, zi = int(round(fx)), int(round(fy)), int(round(fz))
                if 0 <= xi < 30 and 0 <= yi < 30 and 0 <= zi < 30:
                    m[max(0, zi - 1):zi + 1, yi, max(0, xi - 1):xi + 1] = _id("leaf")
    out["palms"] = Vox(P12_NAMES, m, (-14.5 * res, -14.5 * res, 0), res)
    # oil rig: four legs, deck, derrick lattice, flare boom
    m, (zz, yy, xx) = _pm(40, 26, 26)
    for lx in (4, 20):
        for ly in (4, 20):
            m[0:12, ly:ly + 2, lx:lx + 2] = _id("steel")
    m[12:14, 2:24, 2:24] = _id("deck")
    m[14:18, 3:11, 13:23] = _id("wall"); m[16, 3:11:2, 13:23] = _id("light")
    for z in range(14, 36):
        hw_ = 5 - (z - 14) * 0.18
        c0, c1 = int(8 - hw_), int(8 + hw_)
        m[z, c0, c0] = m[z, c0, c1] = m[z, c1, c0] = m[z, c1, c1] = _id("steel")
        if z % 4 == 0: m[z, c0:c1 + 1, c0] = m[z, c0:c1 + 1, c1] = m[z, c0, c0:c1 + 1] = m[z, c1, c0:c1 + 1] = _id("steel")
    m[34:38, 7:10, 7:10] = _id("red")
    for k in range(10): m[13 + k // 3, 22 - k // 2, 22 + 0] = _id("steel")
    m[20:24, 16:19, 20:24] = _id("flare")
    out["oilrig"] = Vox(P12_NAMES, m, (-13 * res, -13 * res, 0), res)
    # AA bunker (v1.1 model)
    m, (zz, yy, xx) = _pm(16, 24, 24)
    r_ = np.hypot(xx - 11.5, yy - 11.5)
    m[(r_ <= 11) & (zz < 3)] = _id("dark"); m[(r_ <= 10) & (zz < 3)] = _id("pad")
    m[(np.hypot(r_, (zz - 3) * 1.2) <= 7) & (zz >= 3)] = _id("metal")
    for bx in (9, 13):
        for k in range(10):
            m[min(15, 6 + k // 2 + 1), 11 - k, bx:bx + 2] = _id("gun")
    ring = (r_[2] <= 10) & (r_[2] > 9) & ((np.arctan2(yy[2] - 11.5, xx[2] - 11.5) * 4 / math.pi) % 1 < 0.5)
    m[2][ring] = _id("red")
    out["bunker"] = Vox(P12_NAMES, m, (-6, -6, 0), res)
    # lit skyscraper: two stepped towers with window grids (lit at night) and a red beacon
    m, (zz, yy, xx) = _pm(56, 20, 20)
    m[0:44, 3:15, 3:15] = _id("wall")
    m[44:50, 5:13, 5:13] = _id("wall")
    m[50:54, 8:10, 8:10] = _id("steel"); m[54:56, 8:10, 8:10] = _id("red")
    m[0:30, 13:19, 12:19] = _id("wall")
    sh = (m == _id("wall"))
    win = sh & (zz % 4 != 0) & ((xx + yy) % 3 != 0) & (zz > 1)
    lit = np.repeat(R.rand(14, 20, 20) < 0.55, 4, 0)[:56]
    m[win & lit] = _id("win"); m[win & ~lit] = _id("winoff")
    out["skyscraper"] = Vox(P12_NAMES, m, (-10 * res, -10 * res, 0), res)
    # pyramid: stepped, sand stone
    m, (zz, yy, xx) = _pm(18, 34, 34)
    d = np.maximum(np.abs(xx - 16.5), np.abs(yy - 16.5))
    m[d <= 16 - zz * 0.92] = _id("stone")
    m[(d <= 16 - zz * 0.92) & (zz % 3 == 2) & (d > 15 - zz * 0.92)] = _id("sand")
    m[0:3, 15:18, 0:3] = _id("dark")
    out["pyramid"] = Vox(P12_NAMES, m, (-16.5 * res, -16.5 * res, 0), res)
    # rock mesa: layered red rock with an uneven top
    m, (zz, yy, xx) = _pm(22, 30, 30)
    a = np.arctan2(yy - 14.5, xx - 14.5); r_ = np.hypot(xx - 14.5, yy - 14.5)
    lim = 11 + 2.5 * np.sin(3 * a + 1) + 1.5 * np.sin(5 * a) - np.maximum(0, zz - 14) * 1.2
    top = 16 + 3 * np.sin(2 * a + 0.5)
    m[(r_ <= lim) & (zz < top)] = _id("rock")
    m[(r_ <= lim) & (zz < top) & (zz % 5 == 2)] = _id("stone")
    out["rocks"] = Vox(P12_NAMES, m, (-14.5 * res, -14.5 * res, 0), res)
    # radar station: block house, lattice mast, tilted dish
    m, (zz, yy, xx) = _pm(34, 26, 26)
    m[0:6, 4:14, 4:20] = _id("wallp"); m[6:7, 3:15, 3:21] = _id("roof")
    m[3, 4, 6:18:3] = _id("light")
    m[0:20, 17:19, 11:13] = _id("steel")
    dz, dy, dx = zz - 24, yy - 18, xx - 12
    # dish: paraboloid shell facing +y and up
    u = dy * 0.8 - dz * 0.6; v = dy * 0.6 + dz * 0.8
    shell = (np.hypot(dx, v) <= 8) & (np.abs(u - (dx ** 2 + v ** 2) * 0.06) <= 0.8)
    m[shell] = _id("dish")
    m[(np.abs(dx) <= 0.6) & (np.abs(v) <= 0.6) & (u > 0) & (u < 5)] = _id("steel")
    out["radar"] = Vox(P12_NAMES, m, (-12 * res, -12 * res, 0), res)
    # tank: camo hull with tracks, turret and long barrel (heading = +y)
    m, (zz, yy, xx) = _pm(14, 34, 22)
    m[0:3, 3:31, 2:6] = _id("dark"); m[0:3, 3:31, 16:20] = _id("dark")
    m[2:6, 2:32, 4:18] = _id("camo")
    m[(zz >= 6) & (zz < 9) & (np.hypot(xx - 10.5, yy - 14) <= 5.5)] = _id("camo")
    m[7:8, 18:33, 10:12] = _id("gun")
    m[9:10, 12:15, 8:10] = _id("metal")
    out["tank"] = Vox(P12_NAMES, m, (-10.5 * res, -16 * res, 0), res)
    # iceberg: jagged white / blue chunk floating
    m, (zz, yy, xx) = _pm(30, 34, 34)
    a = np.arctan2(yy - 16.5, xx - 16.5); r_ = np.hypot(xx - 16.5, yy - 16.5)
    hgt = 10 + 9 * np.cos(a * 2 + 0.7) * np.exp(-r_ / 18) + 6 * np.sin(3 * a)
    lim = 14 + 2 * np.sin(4 * a + 2) - zz * 0.42
    m[(r_ <= lim) & (zz < np.maximum(2, hgt * (1 - r_ / 18)))] = _id("ice")
    out["iceberg"] = Vox(P12_NAMES, m, (-16.5 * res, -16.5 * res, 0), res)
    # snow pines: three cones with snowy tips on a snow patch
    m, (zz, yy, xx) = _pm(34, 28, 28)
    m[(np.hypot(xx - 13.5, yy - 13.5) <= 12) & (zz < 1)] = _id("snow")
    for (px, py, h) in ((9, 10, 30), (19, 12, 24), (13, 20, 20)):
        r_ = np.hypot(xx - px, yy - py)
        m[(zz < 3) & (r_ <= 0.9)] = _id("trunk")
        cone = (zz >= 3) & (zz < h) & (r_ <= (h - zz) * 0.32 + 0.4 * ((zz % 4) < 2))
        m[cone] = _id("pine")
        m[cone & ((zz % 4) == 3)] = _id("snow")
        m[cone & (zz >= h - 3)] = _id("snow")
    out["pines"] = Vox(P12_NAMES, m, (-13.5 * res, -13.5 * res, 0), res)
    # igloo base: snow dome with an entrance tunnel, a radio mast with a lamp
    m, (zz, yy, xx) = _pm(26, 30, 30)
    r3 = np.hypot(np.hypot(xx - 13.5, yy - 13.5), zz * 1.1)
    m[(r3 <= 10.5)] = _id("snow")
    m[(r3 <= 10.5) & (zz % 3 == 0) & (r3 > 9.5)] = _id("ice")
    tun = (np.abs(xx - 13.5) <= 3) & (yy > 20) & (yy < 27) & (np.hypot(xx - 13.5, zz) <= 3.5)
    m[tun] = _id("snow"); m[tun & (yy == 26) & (np.hypot(xx - 13.5, zz) <= 2)] = _id("dark")
    m[8:24, 6:7, 22:23] = _id("steel"); m[24:26, 6:7, 22:23] = _id("red")
    out["igloo"] = Vox(P12_NAMES, m, (-13.5 * res, -13.5 * res, 0), res)
    # arctic gun turret: square pad, armoured box turret, twin barrels
    m, (zz, yy, xx) = _pm(14, 28, 22)
    m[0:2, 2:24, 1:21] = _id("pad")
    m[2:8, 6:18, 5:17] = _id("metal")
    m[8:9, 8:16, 7:15] = _id("steel")
    m[5:6, 16:27, 7:9] = _id("gun"); m[5:6, 16:27, 13:15] = _id("gun")
    m[1, 2:24:3, 1] = _id("light")
    out["turret"] = Vox(P12_NAMES, m, (-10.5 * res, -12 * res, 0), res)
    return out
