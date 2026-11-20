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
           nose_pitch=0.0, dither=True, flat_top=0.10, out_lam=False):
    """sprite-stack render to a size x size palette-index image."""
    ph = math.radians(roll); yw = math.radians(yaw); al = math.radians(pitch_cam); npch = math.radians(nose_pitch)
    def xf(v):
        x, y, z = v[:, 0], v[:, 1], v[:, 2]
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
    lam = 0.16 + 0.84 * np.clip(N @ LIGHT, 0, 1)
    if view == "top": lam = 0.40 + 0.60 * np.abs(N @ LIGHT)
    lam = lam + flat_top * vox.top                               # stacked-slice highlight on each layer's top
    lam = np.clip(lam, 0, 1)
    W = size * ss
    cx = (sx * scale + size / 2) * ss; cy = (sy * scale + size / 2 + oy) * ss
    r = max(1, int(round(vox.res * scale * ss * 1.25)))
    offs = [(dx, dy) for dy in range(r) for dx in range(r)]
    X = np.concatenate([np.floor(cx - r / 2 + dx).astype(int) for dx, dy in offs])
    Y = np.concatenate([np.floor(cy - r / 2 + dy).astype(int) for dx, dy in offs])
    D = np.tile(dep, len(offs)); M = np.tile(vox.m, len(offs)); Lm = np.tile(lam, len(offs))
    ok = (X >= 0) & (X < W) & (Y >= 0) & (Y < W)
    X, Y, D, M, Lm = X[ok], Y[ok], D[ok], M[ok], Lm[ok]
    pix = Y * W + X
    o = np.lexsort((D, pix))                                      # per pixel: nearest (largest depth) last
    pix, M, Lm = pix[o], M[o], Lm[o]
    last = np.r_[pix[1:] != pix[:-1], True]
    mbuf = np.zeros(W * W, np.int32); lbuf = np.zeros(W * W)
    mbuf[pix[last]] = M[last]; lbuf[pix[last]] = Lm[last]
    mbuf = mbuf.reshape(size, ss, size, ss).transpose(0, 2, 1, 3).reshape(size, size, ss * ss)
    lbuf = lbuf.reshape(size, ss, size, ss).transpose(0, 2, 1, 3).reshape(size, size, ss * ss)
    cov = (mbuf > 0).sum(2)
    out = np.zeros((size, size), np.uint8); lout = np.zeros((size, size))
    nm = len(vox.mats)
    cnt = np.stack([(mbuf == k).sum(2) for k in range(nm)], 2); cnt[:, :, 0] = 0
    dom = cnt.argmax(2)
    lsum = (lbuf * (mbuf > 0)).sum(2) / np.maximum(cov, 1)
    keep = (cov * 2 >= ss * ss) | ((cov >= 5) & (cov * 3 > ss * ss))
    for yy in range(size):
        for xx in range(size):
            if not keep[yy, xx]: continue
            mname = vox.mats[dom[yy, xx]]; rp = ramps[mname]
            l = lsum[yy, xx]; lout[yy, xx] = l
            if isinstance(rp, (list, tuple)):
                f = l ** 1.5 * len(rp) + (BAYER[yy % 4, xx % 4] * 0.55 if dither else 0)
                out[yy, xx] = rp[min(len(rp) - 1, max(0, int(f)))]
            else:
                out[yy, xx] = rp
    if outline:
        o2 = out.copy()
        nz = (out != 0) & (out != outline)
        near = np.zeros_like(nz)
        near[:, 1:] |= nz[:, :-1]; near[:, :-1] |= nz[:, 1:]; near[1:] |= nz[:-1]; near[:-1] |= nz[1:]
        o2[(out == 0) & near] = outline
        out = o2
    return (out, lout) if out_lam else out

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
