"""v1.8: explosion / smoke / afterburner animation sequences (streamed into the existing cells by the NMI).
Same glossy look as tools/boom17.py, but one continuous, eased sequence instead of two key frames."""
import math, numpy as np
from boom17 import L, H, _billows, _trace, _down

def _ease(t): return 1 - (1 - t) ** 2.2

def fireball_t(size, t, seed=3, ss=4):
    """t 0..1: white-hot core with flash spikes -> billowing orange -> cooling, sooty, ring + debris out"""
    c = size / 2
    e = _ease(t)
    R = size * (0.155 + 0.115 * e)
    base, _ = _billows(size, seed, 11, 1.0, (0.4, 0.85), 0.4, 0.62)
    balls = []
    for i, (bx, by, bz, br) in enumerate(base):
        k = 1.0 if i == 0 else min(1.0, 0.35 + 0.65 * min(1, t * 3 + (i % 3) * 0.12))
        balls.append((c + (bx - c) * R * (0.85 + 0.25 * e), c + (by - c) * R * (0.85 + 0.25 * e) - t * size * 0.05,
                      bz * R, br * R * k))
    hit, nx, ny, nz, idx, xx, yy = _trace(size, balls, ss)
    lam = nx * L[0] + ny * L[1] + nz * L[2]
    spec = (nx * H[0] + ny * H[1] + nz * H[2]) > (0.965 + 0.012 * t)
    dist = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / (R * 1.6)
    hot = 1.0 - 0.62 * t ** 0.8
    heat = (1.05 - dist) * hot + lam * 0.5 - max(0, t - 0.7) * 0.6
    g = np.zeros(hit.shape, np.uint8)
    for th, col in [(-9, 15), (0.28, 8), (0.55, 9), (0.8, 14), (1.02, 13)]:
        g[hit & (heat > th)] = col
    shade = hit & (lam < -0.15)
    g[shade & (g == 8)] = 15
    g[shade & (lam < -0.5) & (g == 15)] = 2
    if t > 0.3:                                   # soot creeps over the cooling billows from the top
        lim = 0.18 + 0.55 * (t - 0.3) / 0.7
        sm = hit & (heat < lim) & (yy < c + R * (0.1 + 0.9 * t))
        sv = lam * 0.5 + 0.5
        g[sm] = np.where(sv[sm] > 0.72, 6, np.where(sv[sm] > 0.5, 5, np.where(sv[sm] > 0.3, 4, 3)))
    if t < 0.97: g[spec & hit] = 13
    out = _down(g, ss)
    yy1, xx1 = np.mgrid[0:size, 0:size] + 0.5
    d = np.sqrt((xx1 - c) ** 2 + ((yy1 - c) * 1.15) ** 2)
    ang = np.arctan2(yy1 - c, xx1 - c)
    if t < 0.3:                                   # flash spikes, shrinking
        sl = size * (0.48 - 0.5 * t)
        spike = (np.abs(np.cos(ang * 4 + 0.4 + t * 2)) ** 24 > 0.5) & (np.sqrt((xx1 - c) ** 2 + (yy1 - c) ** 2) < sl) & (out == 0)
        out[spike] = 14 if t < 0.18 else 9
    if t > 0.28:                                  # shockwave ring: expands, thins, breaks up
        u = (t - 0.28) / 0.72
        rr_ = size * (0.30 + 0.17 * _ease(u))
        brk = -0.35 + 0.9 * u
        ring = (np.abs(d - rr_) < 0.75 - 0.25 * u) & (np.cos(ang * 5 + seed + u) > brk) & (out == 0)
        if u < 0.85: out[ring] = 14 if u < 0.45 else 9
        ring2 = (np.abs(d - rr_ * 0.93) < 0.55) & (np.cos(ang * 5 + seed + u) > brk + 0.25) & (out == 0)
        if u < 0.7: out[ring2] = 9 if u < 0.4 else 15
        r2 = np.random.default_rng(seed + 7)
        for _ in range(7):                        # debris chunks fly out
            a = r2.uniform(0, 2 * math.pi); dd = r2.uniform(0.62, 1.0) * size * (0.22 + 0.25 * _ease(u))
            x0 = int(c + math.cos(a) * dd); y0 = int(c + math.sin(a) * dd * 0.9 + u * u * 3)
            for (px, py, col) in ((0, 0, 1), (1, 0, 2), (0, 1, 2), (1, 1, 15)):
                X, Y = x0 + px, y0 + py
                if 0 <= X < size and 0 <= Y < size and out[Y, X] == 0: out[Y, X] = col
            X, Y = x0 - 1, y0 - 1
            if u < 0.75 and 0 <= X < size and 0 <= Y < size and out[Y, X] == 0: out[Y, X] = 9
    return out

def boom_seq(n=24):
    return [fireball_t(32, i / (n - 1)) for i in range(n)]

def smoke_t(t, seed=12):
    """16x16 smoke dying out: grows, rises, thins; embers fade"""
    R = 4.3 + 1.4 * _ease(t)
    balls, r = _billows(16, seed, 6, R, (0.2, 0.7), 0.45, 0.7)
    balls = [(x, y - 1.6 * t, z, b * (1 - 0.25 * max(0, t - 0.6))) for (x, y, z, b) in balls]
    hit, nx, ny, nz, idx, xx, yy = _trace(16, balls)
    lam = nx * L[0] + ny * L[1] + nz * L[2]
    sv = lam * 0.5 + 0.5 - 0.15 * t
    g = np.zeros(hit.shape, np.uint8)
    g[hit] = np.where(sv[hit] > 0.8, 7, np.where(sv[hit] > 0.62, 6, np.where(sv[hit] > 0.45, 5, np.where(sv[hit] > 0.28, 4, 3))))
    out = _down(g, 4)
    if t > 0.75:                                  # breaking up at the end
        rr = np.random.default_rng(seed + 3)
        out[(out > 0) & (rr.random(out.shape) < (t - 0.75) * 2.4)] = 0
    rr = np.random.default_rng(seed)
    m = out > 0
    e = m & (rr.random(out.shape) < 0.16 * (1 - t))
    out[e] = np.where(rr.random(e.sum()) < 0.5 + 0.4 * t, 8, 9)
    return out

def smoke_seq(n=12):
    return [smoke_t(i / (n - 1)) for i in range(n)]

def flame_t(i, n=16):
    """16x16 chase afterburner, twin plumes flickering at 60 fps (indices 7 / 8 / 9 as before)"""
    g = np.zeros((16, 16), np.uint8)
    r = np.random.default_rng(100 + i)
    for side in (-1, 1):
        cx = 8 + side * 4
        ph = i * 2 * math.pi / n + (0 if side < 0 else 1.7)
        Ln = 11.0 + 2.2 * math.sin(ph) + 1.2 * math.sin(ph * 3 + 0.5) + r.uniform(-0.6, 0.6)
        wob = 0.35 * math.sin(ph * 2)
        for y in range(16):
            if y >= Ln: break
            f = y / Ln
            w = max(0.6, 2.5 * (1 - f) ** 0.8 * (1 + 0.12 * math.sin(ph * 5 + y)))
            x0 = cx + wob * f
            for x in range(16):
                dd = abs(x + 0.5 - x0)
                if dd < w + 0.6:
                    g[y, x] = 9 if dd < w * 0.45 and f < 0.55 else (8 if dd < w * 0.85 and f < 0.85 else 7)
        k = int(Ln + r.uniform(0.5, 2.5))       # a spark dash off the tip
        if k < 16 and r.random() < 0.7: g[k, int(cx + r.uniform(-1, 1))] = 8
    return g

def flame_seq(n=16):
    return [flame_t(i, n) for i in range(n)]

def bflame_t(i, n=16):
    """16x16 boss thruster (cloud palette: 7/8/9 orange..yellow, 1 white core), flickering at 60 fps"""
    g = np.zeros((16, 16), np.uint8)
    r = np.random.default_rng(300 + i)
    ph = i * 2 * math.pi / n
    L = 13.2 + 1.6 * math.sin(ph) + 0.9 * math.sin(ph * 3 + 1.1) + r.uniform(-0.5, 0.5)
    wob = 0.45 * math.sin(ph * 2 + 0.3)
    for y in range(16):
        if y >= L: break
        f = y / L
        w = max(0.6, 3.6 * (1 - f) * (1 + 0.1 * math.sin(ph * 4 + y * 0.9)))
        x0 = 8 + wob * f
        for x in range(16):
            dd = abs(x + 0.5 - x0)
            if dd < w + 0.6:
                g[y, x] = 1 if (dd < w * 0.35 and f < 0.35) else (9 if dd < w * 0.6 else (8 if dd < w * 0.9 else 7))
    return g

def bflame_seq(n=16):
    return [bflame_t(i, n) for i in range(n)]
