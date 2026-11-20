#!/usr/bin/env python3
"""SUPER SKY FURY v1.3 -- the robot boss as a pre-rendered 3D model (DKC-style).

v1.2 extruded the old flat boss drawing into voxels.  v1.3 rebuilds the robot from the reference clips:
glossy white armour with cobalt-blue trim, broad angular shoulder pads jutting up and out round the head,
a V torso with the glowing red downward-triangle gem, a thin waist of ribbed dark plates, dark joints,
a crown of white / blue blades fanning up and out, a V visor with angular red eyes, bulky bell-bottom shins
with pointed knees, green ankle nodes and pointed feet.  No swords: wrist blasters under both forearms and
missile pods on the shoulders.

The model is a set of convex hulls (angular armour plates, crest blades, gem), ellipsoids (joints, ribbed
abdomen) and tapered prisms with smooth normals (limbs), all ray-traced analytically in numpy through a
low-angle perspective camera (it looks up at him).  Shading: cool blue ambient + front key, warm orange rim
lights from behind both sides, white specular; supersampled 3x3, then quantised to the 15-colour boss
palette with per-material ramps and a 4x4 ordered dither.  Groups (body / head yaw / arm pose) are rendered
in one scene so the body hides what it should, and cut into 16x16 cells around the chest gem.
"""
import math, os, sys
import numpy as np

# ------------------------------------------------------------------ palette (OBJ palette 7)
PAL = ["#000000",
       "#080a18",  # 1 outline / black
       "#1a1e34",  # 2 dark armour shadow
       "#363c5e",  # 3 dark armour lit
       "#ff9a3c",  # 4 warm orange rim / hot metal / gem facet
       "#4e5a92",  # 5 white, deep (blue ambient) shadow
       "#8792c6",  # 6 white shadow
       "#bcc6ea",  # 7 white mid
       "#e6ebfb",  # 8 white lit
       "#ffffff",  # 9 specular
       "#0e1c6a",  # 10 blue dark
       "#2246c8",  # 11 blue mid
       "#5c8cff",  # 12 blue light
       "#ff2a18",  # 13 eyes (animated by the NMI)
       "#ff3c22",  # 14 gem (animated by the NMI)
       "#34d070"]  # 15 green nodes
PAL_RGB = np.array([tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in PAL], np.uint8)
GEM_SCREEN_EYE = None   # filled by build_all: eye centre dy (px) above the gem

W_, B_, D_, G_, R_, E_, N_, GR_ = range(8)   # materials: white, blue, dark, grey ribs, gem, eyes, green, blaster glow
RAMP = {W_: [5, 6, 7, 8], B_: [10, 11, 12], D_: [1, 2, 3], G_: [1, 2, 3], R_: [14, 14, 14], E_: [13, 13, 13], N_: [2, 15, 15], GR_: [11, 12, 9]}
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16.0

def nrm(v):
    v = np.asarray(v, float); return v / np.linalg.norm(v)

def rot(axis, deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    x, y, z = nrm(axis)
    return np.array([[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                     [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                     [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])

# ------------------------------------------------------------------ primitives
def hull_planes(pts):
    """convex hull of a small point set -> list of (n, d) with n.p <= d inside (brute force)"""
    P = np.asarray(pts, float); n = len(P); planes = []
    c = P.mean(0)
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                nn = np.cross(P[j] - P[i], P[k] - P[i]); l = np.linalg.norm(nn)
                if l < 1e-6: continue
                nn /= l; d = nn @ P[i]
                s = P @ nn - d
                if (s <= 1e-6).all(): pass
                elif (s >= -1e-6).all(): nn, d = -nn, -d
                else: continue
                if any(abs(nn @ q - 1) < 1e-6 and abs(d - e) < 1e-4 for q, e in planes): continue
                planes.append((nn, d))
    return planes

class Prim:
    def __init__(self, kind, mat, group, **kw):
        self.kind, self.mat, self.group = kind, mat, group
        self.R = np.eye(3); self.t = np.zeros(3); self.kw = kw; self.paint = kw.pop("paint", None)
        self.tag = kw.pop("tag", "")
    def moved(self, R, t):
        """apply world transform p -> R p + t after the current one"""
        q = Prim(self.kind, self.mat, self.group, **self.kw); q.paint = self.paint; q.tag = self.tag
        q.R = R @ self.R; q.t = R @ self.t + np.asarray(t, float)
        return q
    def hit(self, O, D):
        """-> t (inf = miss), world normal, local hit point"""
        Ri = np.linalg.inv(self.R)
        o = (O - self.t) @ Ri.T; d = D @ Ri.T
        N = len(O); t = np.full(N, np.inf); nl = np.zeros((N, 3))
        k = self.kind
        if k == "hull":
            te = np.full(N, -np.inf); tx = np.full(N, np.inf); ne = np.zeros((N, 3)); ok = np.ones(N, bool)
            for n_, d_ in self.kw["planes"]:
                num = d_ - o @ n_; den = d @ n_
                with np.errstate(divide="ignore", invalid="ignore"):
                    tt = num / den
                ent = den < -1e-9; ex = den > 1e-9; par = ~ent & ~ex
                ok &= ~(par & (num < 0))
                upd = ent & (tt > te); te = np.where(upd, tt, te); ne[upd] = n_
                tx = np.where(ex & (tt < tx), tt, tx)
            h = ok & (te <= tx) & (te > 0)
            t[h] = te[h]; nl[h] = ne[h]
        elif k == "ell":   # ellipsoid radii r at origin
            r = np.asarray(self.kw["r"], float)
            os_, ds = o / r, d / r
            a = (ds * ds).sum(1); b = (os_ * ds).sum(1); c = (os_ * os_).sum(1) - 1
            disc = b * b - a * c
            h = disc >= 0
            tt = (-b - np.sqrt(np.maximum(disc, 0))) / a
            h &= tt > 0
            t[h] = tt[h]
            p = o + d * t[:, None]
            nl[h] = (p[h] / (r * r))
        elif k == "prism":  # tapered n-gon prism along +y from y=0 (radii rx0,rz0) to y=L (rx1,rz1), smooth normals
            L = self.kw["L"]; r0 = np.asarray(self.kw["r0"], float); r1 = np.asarray(self.kw["r1"], float)
            pl = self.kw["planes"]
            te = np.full(N, -np.inf); tx = np.full(N, np.inf); ok = np.ones(N, bool)
            for n_, d_ in pl:
                num = d_ - o @ n_; den = d @ n_
                with np.errstate(divide="ignore", invalid="ignore"):
                    tt = num / den
                ent = den < -1e-9; ex = den > 1e-9; par = ~ent & ~ex
                ok &= ~(par & (num < 0))
                te = np.where(ent & (tt > te), tt, te); tx = np.where(ex & (tt < tx), tt, tx)
            h = ok & (te <= tx) & (te > 0)
            t[h] = te[h]
            p = o + d * t[:, None]
            f = np.clip(p[:, 1] / L, 0, 1)
            rx = r0[0] + (r1[0] - r0[0]) * f; rz = r0[1] + (r1[1] - r0[1]) * f
            nn = np.stack([p[:, 0] / rx, np.full(N, -(r1[0] - r0[0]) / L), p[:, 2] / rz], 1)
            # caps: flat ends
            capb = p[:, 1] < 0.35; capt = p[:, 1] > L - 0.35
            nn[capb] = (0, -1, 0); nn[capt] = (0, 1, 0)
            nl[h] = nn[h]
        nw = nl @ Ri
        l = np.linalg.norm(nw, axis=1, keepdims=True); l[l == 0] = 1
        return t, nw / l, o + d * np.where(np.isfinite(t), t, 0)[:, None]

def hull(pts, mat, group, **kw):
    return Prim("hull", mat, group, planes=hull_planes(pts), **kw)

def mirror_pts(pts):
    return [(-x, y, z) for x, y, z in pts]

def ell(c, r, mat, group, **kw):
    return Prim("ell", mat, group, r=r, **kw).moved(np.eye(3), c)

def limb(a, b, r0, r1, mat, group, sides=10, **kw):
    """tapered prism from a to b (r0 at a, r1 at b; r = (rx, rz)), smooth normals"""
    a = np.asarray(a, float); b = np.asarray(b, float); L = np.linalg.norm(b - a)
    r0 = np.broadcast_to(np.asarray(r0, float), (2,)); r1 = np.broadcast_to(np.asarray(r1, float), (2,))
    pts = []
    for i in range(sides):
        th = 2 * math.pi * (i + 0.5) / sides
        pts.append((r0[0] * math.cos(th) / math.cos(math.pi / sides), 0, r0[1] * math.sin(th) / math.cos(math.pi / sides)))
        pts.append((r1[0] * math.cos(th) / math.cos(math.pi / sides), L, r1[1] * math.sin(th) / math.cos(math.pi / sides)))
    p = Prim("prism", mat, group, L=L, r0=r0, r1=r1, planes=hull_planes(pts), **kw)
    y = (b - a) / L
    x = np.cross(y, (0, 0, 1.0)); 
    if np.linalg.norm(x) < 1e-6: x = np.array([1.0, 0, 0])
    x /= np.linalg.norm(x); z = np.cross(x, y)
    return p.moved(np.stack([x, y, z], 1), a)

# ------------------------------------------------------------------ the robot (world: x right, y up, z to the camera; gem at 0)
def blade(base, ang, L, w, th, tilt, mat, group, stripe=False):
    """crest blade: diamond cross-section, from base fanning at ang degrees from vertical, leaning back by tilt"""
    a = math.radians(ang)
    d = np.array([math.sin(a), math.cos(a), 0.0])
    d = rot((1, 0, 0), -tilt) @ d
    perp = np.cross(d, (0, 0, 1.0)); perp /= np.linalg.norm(perp)
    fz = np.cross(perp, d)
    b = np.asarray(base, float)
    pts = [b - perp * w, b + perp * w, b + d * L, b + d * L * 0.30 + fz * th, b + d * L * 0.30 - fz * th * 0.8,
           b + d * L * 0.62 - perp * w * 0.55 + fz * th * 0.2]
    paint = ("stripe", b, d, perp, w) if stripe else None
    return hull(pts, mat, group, paint=paint)

HEAD_SC = 1.16
def head_prims():
    G = "head"; P = []
    # helmet: pointed V brow with a blue centre ridge, V jaw, swept back
    hp = [(0, 61, 7), (-12, 52, 7.5), (12, 52, 7.5), (-13, 41, 5), (13, 41, 5), (-6, 32, 7), (6, 32, 7), (0, 29, 8),
          (-11, 56, -8), (11, 56, -8), (-11, 36, -7), (11, 36, -7), (0, 62, -6), (0, 57, 10)]
    P.append(hull(hp, W_, G, paint=("helm",)))
    # black V visor (face) with the eyes painted on
    vp = [(-10.5, 49.5, 8.6), (10.5, 49.5, 8.6), (-7.5, 38, 8.6), (7.5, 38, 8.6), (0, 31.5, 9.4), (0, 47.5, 10.8),
          (-9, 47, 4), (9, 47, 4), (0, 33, 4)]
    P.append(hull(vp, D_, G, paint=("visor",)))
    # blue cheek guards
    for s in (-1, 1):
        cp = [(s * 12.5, 51, 6), (s * 14.5, 45, 4), (s * 13.5, 37, 4), (s * 9, 35, 7.5), (s * 10.5, 49, 8), (s * 12, 44, 0)]
        P.append(hull(cp, B_, G))
    # crown of blades: a tall centre blade, two big pairs, a small pair low at the sides
    P.append(blade((0, 57, 1), 0, 34, 5.5, 3.6, 14, W_, G, stripe=True))
    for s in (-1, 1):
        P.append(blade((s * 5, 56, 0), s * 20, 31, 5.2, 3.4, 20, W_, G, stripe=True))
        P.append(blade((s * 9, 53, -1), s * 42, 27, 4.8, 3.2, 24, W_, G, stripe=True))
        P.append(blade((s * 11.5, 47, -2), s * 66, 18, 4.0, 2.6, 24, W_, G, stripe=True))
    # scale the head + crest up about the neck
    S_ = np.eye(3) * HEAD_SC; c = np.array([0, 30.0, 0])
    return [p.moved(np.eye(3), -c).moved(S_, c) for p in P]

def body_prims():
    G = "body"; P = []
    # neck
    P.append(limb((0, 22, -2), (0, 34, -2), (7, 6), (6, 5), D_, G))
    # chest: V torso, pecs ridge, tapering to the waist
    cp = [(-31, 26, 5), (31, 26, 5), (-31, 25, -11), (31, 25, -11), (-23, 22, 14), (23, 22, 14), (0, 20, 15.5),
          (-20, 5, 15), (20, 5, 15), (0, 6, 17.5), (-13, -11, 10), (13, -11, 10), (-13, -11, -7), (13, -11, -7),
          (-27, 10, -11), (27, 10, -11), (-30, 14, 8), (30, 14, 8)]
    P.append(hull(cp, W_, G, paint=("chest",)))
    # blue V collar under the face
    for s in (-1, 1):
        kp = [(s * 1, 27, 12), (s * 17, 30, 8), (s * 20, 26, 9), (s * 2, 21, 15.6), (s * 1, 30, 4), (s * 18, 31, 2), (s * 12, 20, 15)]
        P.append(hull(kp, B_, G))
    # the gem: downward triangle, faceted, proud of the chest
    gp = [(-12, 7.5, 16), (12, 7.5, 16), (0, -9.5, 15), (0, 1.5, 19.6), (-6, 5.5, 18.6), (6, 5.5, 18.6),
          (-11, 7, 12), (11, 7, 12), (0, -8, 11)]
    P.append(hull(gp, R_, G, tag="gem"))
    # ribbed dark abdomen
    for i, y in enumerate((-9.5, -13, -16.5, -20, -23.5)):
        rx = 12.5 - i * 0.5
        P.append(ell((0, y, 1), (rx, 2.4, 8.2), G_, G))
    P.append(limb((0, -26, 0), (0, -6, 0), (10, 7), (11, 7), D_, G))
    # pelvis + crotch plate (blue bar)
    pp = [(-18, -24, 8), (18, -24, 8), (-20, -29, 6), (20, -29, 6), (-14, -40, 8), (14, -40, 8), (0, -46, 9.5),
          (0, -27, 11), (-18, -25, -8), (18, -25, -8), (-14, -40, -7), (14, -40, -7)]
    P.append(hull(pp, W_, G, paint=("crotch",)))
    for s in (-1, 1):
        x = s
        # hip joint, thigh, knee joint
        P.append(ell((x * 15, -35, 0), (7.5, 7.5, 7.5), D_, G))
        P.append(limb((x * 15.5, -38, 0), (x * 19.5, -70, 2), (9.0, 8.5), (8.0, 7.5), W_, G))
        P.append(ell((x * 19.5, -72, 1), (7, 6, 6.5), D_, G, paint=("knee", x)))
        # bell-bottom shin: narrow under the knee, flaring out, pointed knee plate on top
        sp = []
        for i in range(10):
            th = 2 * math.pi * (i + 0.5) / 10
            sp.append((x * 20 + 8.5 * math.cos(th), -75, 2 + 8 * math.sin(th)))
            sp.append((x * 22 + 16.5 * math.cos(th), -106, 4 + 14 * math.sin(th)))
        sp.append((x * 19.5, -60, 11.5))
        P.append(hull(sp, W_, G, paint=("shin", x)))
        # pointed foot
        fp = [(x * 22 - 13, -106, 6), (x * 22 + 13, -106, 6), (x * 22 - 15, -113, 4), (x * 22 + 15, -113, 4), (x * 22, -114, 27),
              (x * 22, -108, 25), (x * 22 - 12, -113, -8), (x * 22 + 12, -113, -8), (x * 22, -106, 15)]
        P.append(hull(fp, W_, G, paint=("foot",)))
        # shoulder pads: broad, angular, jutting up and out round the head; blue under-trim
        # v1.4: swept higher and raked in at the tips, so the pads frame the head
        pd = [(x * 27, 30, 9), (x * 27, 30, -10), (x * 62, 76, 0), (x * 58, 68, 7), (x * 61, 13, 9), (x * 61, 13, -10),
              (x * 31, 9, 11), (x * 46, 30, 15.5), (x * 52, 12, 13), (x * 60, 70, -7), (x * 36, 40, 6), (x * 66, 40, 2)]
        P.append(hull(pd, W_, G, paint=("pad", x)))
        # missile pod on the back of each pad (the volley launchers)
        mp = [(x * 37, 36, -3), (x * 49, 41, -3), (x * 37, 41, -3), (x * 49, 46, -3), (x * 37, 36, -12), (x * 49, 41, -12),
              (x * 37, 41, -12), (x * 49, 46, -12)]
        P.append(hull(mp, B_, G, paint=("pod",)))
    return P

SHOULDER = np.array([-46.0, 15.0, 0.0])
def arm_prims(pose):
    """left arm (screen left, x < 0) in a pose: down / cannon / spread"""
    G = "arm"
    up = [ell((0, 0, 0), (8, 8, 8), D_, G), limb((0, -2, 0), (0, -23, 0), (6.5, 6.5), (6, 6), D_, G),
          ell((0, -25, 0), (6.5, 6.5, 6.5), D_, G)]
    fa = [limb((0, -26, 0), (0, -50, 0), (9, 9), (11, 10.5), W_, G, paint=("forearm",)),
          ell((0, -54, 1), (7.5, 6.5, 7.5), W_, G, paint=("fist",)),
          limb((-6.5, -30, 6), (-6.5, -60, 6), (3.2, 3.2), (3.4, 3.4), D_, G, paint=("barrel",), sides=8),
          ell((-6.5, -60.3, 6), (2.6, 1.0, 2.6), GR_, G, tag="muzzle")]
    if pose == "down":
        Rs = rot((0, 0, 1), -10) @ rot((1, 0, 0), 6); Re = rot((1, 0, 0), 22) @ rot((0, 1, 0), 15)
    elif pose == "cannon":   # forearm swung up and forward: the blaster points at you
        Rs = rot((0, 0, 1), -18) @ rot((1, 0, 0), 55); Re = rot((1, 0, 0), 38) @ rot((0, 1, 0), -10)
    else:                    # spread: arms out wide (spin / beam)
        Rs = rot((0, 0, 1), -74); Re = rot((0, 0, 1), -10) @ rot((1, 0, 0), 25)
    out = [p.moved(Rs, SHOULDER) for p in up]
    E = np.array([0, -25.0, 0])
    for p in fa:
        q = p.moved(np.eye(3), -E).moved(Re, E).moved(Rs, SHOULDER)
        out.append(q)
    return out

# ------------------------------------------------------------------ camera / tracing
CAM = np.array([0.0, -95.0, 430.0]); LOOK = np.array([0.0, -8.0, 0.0])
def rays(S, ss, cx, cy, scale):
    f = np.linalg.norm(CAM - LOOK) * scale
    fw = nrm(LOOK - CAM); rt = nrm(np.cross(fw, (0, 1, 0))); upv = np.cross(rt, fw)
    n = S * ss
    ii, jj = np.mgrid[0:n, 0:n]
    u = (jj + 0.5) / ss - cx; v = cy - (ii + 0.5) / ss
    D = fw[None, :] * f + u.reshape(-1, 1) * rt[None, :] + v.reshape(-1, 1) * upv[None, :]
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    O = np.broadcast_to(CAM, D.shape).copy()
    return O, D

def project(p, cx, cy, scale):
    f = np.linalg.norm(CAM - LOOK) * scale
    fw = nrm(LOOK - CAM); rt = nrm(np.cross(fw, (0, 1, 0))); upv = np.cross(rt, fw)
    q = np.asarray(p, float) - CAM; z = q @ fw
    return cx + f * (q @ rt) / z, cy - f * (q @ upv) / z

def trace(prims, O, D):
    N = len(O); T = np.full(N, np.inf); Nn = np.zeros((N, 3)); idx = np.full(N, -1)
    LP = np.zeros((N, 3))
    for i, p in enumerate(prims):
        t, n, lp = p.hit(O, D)
        m = t < T
        T[m] = t[m]; Nn[m] = n[m]; idx[m] = i; LP[m] = lp[m]
    return T, Nn, idx, LP

LK = nrm((-0.35, 0.55, 0.76))           # cool key light, upper left front
LR = [nrm((-0.9, -0.15, -0.45)), nrm((0.9, -0.15, -0.45))]   # warm rims from behind both sides
LF = nrm((0.25, -0.8, 0.5))             # blue floor bounce (from below: low-angle)

def paint_mat(p, prim, lp, wp):
    """per-hit material overrides (decals): returns material id (or -1 for no change) and extra 'lum' bias"""
    if prim.paint is None: return -1, 0.0
    k = prim.paint[0]
    x, y, z = wp
    if k == "visor":
        # angular eyes, slanted up-out, glowing
        for s in (-1, 1):
            ex = s * x
            if 1.6 < ex < 9.6 and (40.4 + 0.45 * (ex - 1.6)) < y < (45.0 + 0.30 * (ex - 1.6)) and z > 7.5:
                return E_, 0
        return -1, 0
    if k == "helm":
        if abs(x) < 2.0 + max(0, (y - 50)) * 0.15 and y > 48 and z > 0: return B_, 0
        return -1, 0
    if k == "stripe":
        _, b, d, perp, w = prim.paint
        q = np.asarray(wp) - b; s = q @ d; c = q @ perp
        if abs(c) < w * 0.32 * max(0.0, 1 - s / 30.0) + 0.3 and s < 26 and z > -2: return B_, 0
        return -1, 0
    if k == "chest":
        if 13 < abs(x) < 29 and 11 < y < 13.6 and z > 4: return B_, 0
        return -1, 0
    if k == "crotch":
        if abs(x) < 5.8 and -38 < y < -32.5 and z > 7: return B_, 0
        return -1, 0
    if k == "shin":
        s = prim.paint[1]
        xr = s * (x - s * 22)
        dk = math.hypot(x - s * 19.5, y + 74)
        if dk < 3.3 and z > 5: return N_, (0.4 if dk < 1.3 else 0)
        if y < -96 and z > 4 and abs(x - s * 22) < 12 - (y + 96) * -0.3: return B_, 0
        if y < -93 and xr > 10 and z < 8 and y > -104:
            dd = math.hypot(z - 2, y + 99)
            if dd < 3.6: return (N_ if dd < 2.6 else D_), (0.5 if dd < 1.2 else 0)
        if xr > 12.5 and y < -96: return B_, 0
        return -1, 0
    if k == "knee":
        s = prim.paint[1]
        dd = math.hypot(x - s * 19.5, y + 70.5)
        if dd < 3.4 and z > 3: return N_, (0.4 if dd < 1.4 else 0)
        return -1, 0
    if k == "foot":
        return -1, 0
    if k == "pad":
        s = prim.paint[1]
        if y < 18.5 - (s * x - 30) * 0.08 and z > -2: return B_, 0
        if s * x > 58 and y > 24 and z > 2: return B_, 0
        return -1, 0
    if k == "pod":
        for hx in (40, 46):
            if abs(abs(x) - hx) < 1.8 and z > -4.5 and 38 < y < 44: return D_, 0
        return -1, 0
    if k == "forearm":
        f = -lp[1]
        if 36 < f < 46: return B_, 0
        return -1, 0
    if k == "barrel":
        return -1, 0
    return -1, 0

def shade(prims, T, Nn, idx, LP, O, D, keep_groups=None):
    hit = np.isfinite(T)
    WP = O + D * np.where(hit, T, 0)[:, None]
    V = -D
    mat = np.full(len(T), -1); bias = np.zeros(len(T))
    for i, p in enumerate(prims):
        m = np.nonzero(idx == i)[0]
        if not len(m): continue
        mat[m] = p.mat
        if p.paint is not None:
            for j in m:
                mm, bb = paint_mat(None, p, LP[j], WP[j])
                if mm >= 0: mat[j] = mm
                bias[j] += bb
    ndl = np.clip((Nn * LK).sum(1), 0, 1)
    ndv = np.clip((Nn * V).sum(1), 0, 1)
    H = V + LK; H /= np.linalg.norm(H, axis=1, keepdims=True)
    spec = np.clip((Nn * H).sum(1), 0, 1) ** 26
    rim = np.zeros(len(T))
    for lr in LR:
        rim = np.maximum(rim, np.clip((Nn * lr).sum(1), 0, 1) * (1 - ndv) ** 1.5)
    bounce = np.clip((Nn * LF).sum(1), 0, 1)
    lum = 0.20 + 0.70 * ndl + 0.16 * bounce + 0.10 * ndv + bias
    # ribs: horizontal grooves on the abdomen
    g = mat == G_
    lum[g] = 0.25 + 0.75 * ndl[g]
    return hit, mat, lum, spec, rim, WP

def render(prims, keep, S=256, ss=3, cx=128.0, cy=128.0, scale=1.0, dmg=None):
    """-> palette index image S x S (gem at cx, cy) of the prims whose group is in keep (occluded by the rest)"""
    O, D = rays(S, ss, cx, cy, scale)
    T, Nn, idx, LP = trace(prims, O, D)
    hit, mat, lum, spec, rim, WP = shade(prims, T, Nn, idx, LP, O, D)
    grp = np.array([p.group for p in prims] + ["-"])
    kp = hit & np.isin(grp[idx], list(keep))
    n = S * ss
    def blk(a):
        return a.reshape(S, ss, S, ss).mean((1, 3))
    cov = blk(kp.reshape(n, n).astype(float))
    lumS = np.zeros(len(T)); lumS[kp] = lum[kp]
    L = blk(lumS.reshape(n, n)) / np.maximum(cov, 1e-6)
    SP = blk(np.where(kp, spec, 0).reshape(n, n)) / np.maximum(cov, 1e-6)
    RI = blk(np.where(kp, rim, 0).reshape(n, n)) / np.maximum(cov, 1e-6)
    Z = blk(np.where(kp, T, 0).reshape(n, n)) / np.maximum(cov, 1e-6)
    # majority material per pixel
    M = np.full((S, S), -1)
    best = np.zeros((S, S))
    for m_ in range(8):
        c = blk((kp & (mat == m_)).reshape(n, n).astype(float))
        u = c > best; M[u] = m_; best[u] = c[u]
    WPs = WP.reshape(S, ss, S, ss, 3).mean((1, 3))
    out = np.zeros((S, S), np.uint8)
    on = cov >= 0.5
    yy, xx = np.mgrid[0:S, 0:S]
    th = BAYER[yy % 4, xx % 4]
    for m_ in range(8):
        sel = on & (M == m_)
        if not sel.any(): continue
        rp = RAMP[m_]
        v = np.clip(L, 0, 1.05)
        if m_ in (W_,): v = np.clip((v - 0.18) / 0.82, 0, 1) ** 0.9
        else: v = np.clip((v - 0.15) / 0.85, 0, 1)
        f = v * (len(rp) - 1)
        k = np.floor(f + (th - 0.5) * 0.6 + 0.5).astype(int)
        k = np.clip(k, 0, len(rp) - 1)
        out[sel] = np.array(rp)[k[sel]]
        if m_ in (W_, B_):
            s1 = sel & (SP > (0.55 if m_ == W_ else 0.7))
            out[s1] = 9 if m_ == W_ else 12
            if m_ == B_: out[sel & (SP > 0.9)] = 9
        if m_ == R_:
            out[sel & (L > 0.88)] = 4
        if m_ in (W_, B_, D_, G_):
            r1 = sel & (RI > 0.40) & ~(SP > 0.5)
            r2 = sel & (RI > 0.30) & (RI <= 0.40) & (th > 0.5) & ~(SP > 0.5)
            out[r1 | r2] = 4
        if m_ == G_:
            # ribs: dark groove every 3.5 units
            ph = (WPs[:, :, 1] + 30) % 3.5
            out[sel & (ph < 0.9)] = 1
    # outline: silhouette pixels that border empty space and the far side of depth steps
    o = out > 0
    nb = np.zeros_like(o)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb |= ~np.roll(np.roll(o, dy, 0), dx, 1)
    edge = o & nb & (out != 4) & (out != 9) & (out != 13)
    out[edge & ((xx + yy) % 1 == 0)] = np.where(np.isin(out[edge], (5, 6, 10, 2, 3)), 1, np.where(np.isin(out[edge], (7, 8)), 5, out[edge]))
    Zp = np.where(o, Z, 1e9)
    for dy, dx in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        zn = np.roll(np.roll(Zp, dy, 0), dx, 1)
        far = o & (Zp - zn > 3.5) & (zn < 1e8)
        sel = far & ~np.isin(out, (4, 9, 13, 14, 12))
        out[sel] = np.where(np.isin(out[sel], (7, 8, 6)), 5, np.where(np.isin(out[sel], (11, 12)), 10, 1))
    if dmg is not None:
        h = out[:, :S // 2]; out = out.copy(); out[:, S // 2:] = h[:, ::-1][:, :S - S // 2]
        out = damage(out, WPs, M, dmg, th)
    return out

DMG_SPOTS = [(-16, 15, 5.5), (44, 30, 5.0), (-19, -54, 4.5), (24, -92, 4.5), (8, -3, 0)]
DMG_SCREEN = [(-20, -16), (46, -24), (-20, 50), (26, 92)]     # battle damage targets (px from the gem)
def damage_px(img, centres, r=6.0, seed=7):
    """scorch + a ragged hole with a hot rim at each screen centre (x, y in img px)"""
    o = img.copy(); rng = np.random.default_rng(seed); noise = rng.random(img.shape)
    yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
    th = BAYER[yy % 4, xx % 4]
    for cx, cy in centres:
        d = np.hypot(xx - cx, (yy - cy) * 1.15) / r * (0.85 + 0.3 * noise)
        sc = (img > 0) & (d < 1.25) & ~np.isin(img, (13, 14))
        o[sc] = np.where(np.isin(img[sc], (7, 8, 9)), np.where(th[sc] > 0.4, 5, 6),
                         np.where(np.isin(img[sc], (11, 12, 6)), 2, np.where(img[sc] == 5, 3, img[sc])))
        m2 = sc & (d < 0.8); o[m2] = np.where(th[m2] > 0.3, 2, 3)
        o[sc & (d < 0.36)] = 1
        o[sc & (d >= 0.36) & (d < 0.52) & (noise > 0.35)] = 4
    return o
def damage(out, WPs, M, spots, th):
    o = out.copy()
    rng = np.random.default_rng(7)
    noise = rng.random(out.shape)
    for sx, sy, r in spots:
        if r <= 0: continue
        d = np.hypot(WPs[:, :, 0] - sx, WPs[:, :, 1] - sy) / r
        d = d * (0.85 + 0.3 * noise)
        sc = (out > 0) & (d < 1.6) & ~np.isin(out, (13, 14))
        # scorch: blacken / soot ramp
        m = sc & (d < 1.6)
        o[m] = np.where(np.isin(out[m], (8, 9, 7)), np.where(th[m] > 0.4, 5, 6), np.where(np.isin(out[m], (11, 12, 6)), 2, np.where(out[m] == 5, 3, out[m])))
        m2 = sc & (d < 0.9)
        o[m2] = np.where(th[m2] > 0.3, 2, 3)
        hole = sc & (d < 0.38)
        o[hole] = 1
        ring = sc & (d >= 0.38) & (d < 0.55) & (noise > 0.35)
        o[ring] = 4
    return o

def to_rgb(img):
    rgb = PAL_RGB[img].copy(); rgb[img == 0] = (255, 0, 255); return rgb

# ------------------------------------------------------------------ frames for the game
POSES = ("down", "cannon", "spread")
HEAD_YAWS = (0, 20)
NECK = np.array([0.0, 30.0, -2.0])

def scene(head_yaw=0, pose_l="down", pose_r="down"):
    P = list(body_prims())
    Ry = rot((0, 1, 0), head_yaw)
    P += [p.moved(np.eye(3), -NECK).moved(Ry, NECK) for p in head_prims()]
    al = arm_prims(pose_l)
    P += al
    M = np.diag([-1.0, 1, 1])
    for p in arm_prims(pose_r):
        q = p.moved(np.eye(3), (0, 0, 0)); q.R = M @ q.R; q.t = M @ q.t
        # a mirrored hull: flip the plane normals with the points
        q.group = "armR"; P.append(q)
    for p in al: p.group = "armL"
    return P

class Mirrored(Prim):
    pass

def build_all(S=256, scale=1.0, cache=None):
    """-> dict of frames (palette index images, gem at (S/2, S/2)); cached on this file's source hash"""
    import hashlib, pickle
    key = hashlib.sha1(open(__file__, "rb").read() + repr((S, scale)).encode()).hexdigest()[:16]
    cache = cache or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", f"boss_rt_{key}.pkl")
    if os.path.exists(cache): return pickle.load(open(cache, "rb")), S
    fr, S = _build_all(S, scale)
    os.makedirs(os.path.dirname(cache), exist_ok=True); pickle.dump(fr, open(cache, "wb"))
    return fr, S

def _build_all(S, scale):
    c = S / 2
    gx, gy = project((0, 0, 17), 0, 0, scale)
    cxx, cyy = c - gx, c - gy
    fr = {}
    base = scene(0)
    fr["body"] = render(base, {"body"}, S, cx=cxx, cy=cyy, scale=scale)
    b = fr["body"].copy(); b[:, S // 2:] = b[:, :S // 2][:, ::-1][:, :S - S // 2]
    fr["body_dmg"] = damage_px(b, [(c + x * scale, c + y * scale) for x, y in DMG_SCREEN], 6.0 * scale)
    for y in HEAD_YAWS:
        fr[f"head{y}"] = render(scene(-y), {"head"}, S, cx=cxx, cy=cyy, scale=scale)
    for p in POSES:
        fr[f"arm_{p}"] = render(scene(0, p, "down"), {"armL"}, S, cx=cxx, cy=cyy, scale=scale)
    ex, ey = project((0, 30 + 13 * HEAD_SC, 9), cxx, cyy, scale)
    fr["_eye_dy"] = int(round(c - ey))
    fx, fy = project((-22, -113, 8), cxx, cyy, scale)
    fr["_foot"] = (int(round(fx - c)), int(round(fy - c)))
    mz = {}
    for p in POSES:
        sc = arm_prims(p)
        m = [q for q in sc if q.tag == "muzzle"][0]
        mx, my = project(m.t, cxx, cyy, scale)
        mz[p] = (int(round(mx - c)), int(round(my - c)))
    fr["_muzzle"] = mz
    px, py = project((-43, 42, -7), cxx, cyy, scale)
    fr["_pod"] = (int(round(px - c)), int(round(py - c)))
    return fr, S

def compose(fr, S, head=0, arms=("down", "down")):
    full = fr["body"] is fr.get("body_dmg")
    b = fr["body"].copy()
    if not full:
        h = b[:, :S // 2]; b[:, S // 2:] = h[:, ::-1][:, :S - S // 2]
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
    import time, pickle
    from PIL import Image
    t0 = time.time()
    fr, S = build_all()
    pickle.dump(fr, open("/tmp/brt/fr.pkl", "wb"))
    print("render", time.time() - t0, {k: v for k, v in fr.items() if k.startswith("_")})
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/brt"
    os.makedirs(out, exist_ok=True)
    tiles = [to_rgb(compose(fr, S, *a)) for a in ((0, ("down", "down")), (20, ("cannon", "down")), (-20, ("spread", "spread")))]
    d = fr["body_dmg"].copy(); h = d[:, :S // 2]
    f2 = dict(fr); f2["body"] = fr["body_dmg"]; tiles.append(to_rgb(compose(f2, S, 0, ("down", "cannon"))))
    big = np.concatenate(tiles, 1)
    Image.fromarray(big).resize((big.shape[1] * 2, big.shape[0] * 2), Image.NEAREST).save(f"{out}/boss_rt.png")
