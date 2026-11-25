"""v1.7 explosions: glossy pre-rendered fireballs (DKC-style): a cluster of ray-traced billow spheres
lit from the upper left, temperature from the core outwards, specular glints, a hot shockwave ring
and tumbling debris chunks. Palette 0 (jet palette): 13 white, 14 pale yellow, 9 light orange,
8 orange, 15 red, 1 near-black, 2-7 greys."""
import math, numpy as np

L = np.array([-0.55, -0.65, 0.52]); L /= np.linalg.norm(L)
H = L + np.array([0, 0, 1.0]); H /= np.linalg.norm(H)

def _billows(size, seed, n, R, spread, rmin, rmax):
    r = np.random.default_rng(seed)
    c = size / 2
    out = [(c, c, 0.0, R)]
    for _ in range(n):
        a = r.uniform(0, 2 * math.pi); d = r.uniform(*spread) * R
        out.append((c + math.cos(a) * d, c + math.sin(a) * d * 0.9, r.uniform(-0.3, 0.3) * R, R * r.uniform(rmin, rmax)))
    return out, r

def _trace(size, balls, ss=4):
    n = size * ss
    yy, xx = (np.mgrid[0:n, 0:n] + 0.5) / ss
    depth = np.full((n, n), -1e9); nx = np.zeros((n, n)); ny = np.zeros((n, n)); nz = np.zeros((n, n))
    rad = np.zeros((n, n)); idx = np.full((n, n), -1)
    for i, (bx, by, bz, br) in enumerate(balls):
        dx = (xx - bx) / br; dy = (yy - by) / br
        q = 1 - dx * dx - dy * dy
        m = q > 0
        z = np.where(m, np.sqrt(np.clip(q, 0, 1)) * br + bz, -1e9)
        w = z > depth
        depth = np.where(w, z, depth); nx = np.where(w, dx, nx); ny = np.where(w, dy, ny)
        nz = np.where(w, np.sqrt(np.clip(q, 0, 1)), nz); idx = np.where(w, i, idx)
    return depth > -1e8, nx, ny, nz, idx, xx, yy

def _down(g, ss):
    n = g.shape[0] // ss
    b = g.reshape(n, ss, n, ss).transpose(0, 2, 1, 3).reshape(n, n, ss * ss)
    out = np.zeros((n, n), np.uint8)
    for y in range(n):
        for x in range(n):
            v = b[y, x]
            nzv = v[v > 0]
            if len(nzv) * 2 >= len(v):
                vals, cnt = np.unique(nzv, return_counts=True)
                out[y, x] = vals[cnt.argmax()]
    return out

def fireball(size, seed, phase="A", ss=4):
    """phase A: young, white-hot, tight; B: bigger, cooling, smoke cap, ring + debris"""
    R = size * (0.27 if phase == "A" else 0.25)
    balls, r = _billows(size, seed, 9 if phase == "A" else 11, R, (0.4, 0.85), 0.4, 0.62)
    hit, nx, ny, nz, idx, xx, yy = _trace(size, balls, ss)
    c = size / 2
    lam = nx * L[0] + ny * L[1] + nz * L[2]
    spec = (nx * H[0] + ny * H[1] + nz * H[2]) > (0.965 if phase == "A" else 0.975)
    dist = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / (R * 1.6)
    heat = (1.05 - dist) * (0.95 if phase == "A" else 0.7) + lam * 0.5
    g = np.zeros(hit.shape, np.uint8)
    ramp = [(-9, 15), (0.28, 8), (0.55, 9), (0.8, 14), (1.02, 13)]
    for th, col in ramp:
        g[hit & (heat > th)] = col
    shade = hit & (lam < -0.15)
    g[shade & (g == 8)] = 15
    g[shade & (lam < -0.5) & (g == 15)] = 2
    if phase == "B":                       # sooty smoke cap on the upper billows
        sm = hit & (heat < 0.42) & (yy < c + R * 0.3)
        sv = lam * 0.5 + 0.5
        g[sm] = np.where(sv[sm] > 0.72, 6, np.where(sv[sm] > 0.5, 5, np.where(sv[sm] > 0.3, 4, 3)))
    g[spec & hit] = 13
    out = _down(g, ss)
    yy1, xx1 = np.mgrid[0:size, 0:size] + 0.5
    if phase == "B":                       # shockwave ring: thin, hot leading edge, broken
        d = np.sqrt((xx1 - c) ** 2 + ((yy1 - c) * 1.15) ** 2)
        ang = np.arctan2(yy1 - c, xx1 - c)
        ring = (np.abs(d - size * 0.46) < 0.7) & (np.cos(ang * 5 + seed) > -0.35) & (out == 0)
        out[ring] = 14
        ring2 = (np.abs(d - size * 0.43) < 0.55) & (np.cos(ang * 5 + seed) > -0.1) & (out == 0)
        out[ring2] = 9
        rr = np.random.default_rng(seed + 7)
        for _ in range(7):                 # debris chunks: dark, with a hot glint
            a = rr.uniform(0, 2 * math.pi); dd = rr.uniform(0.36, 0.47) * size
            x0 = int(c + math.cos(a) * dd); y0 = int(c + math.sin(a) * dd * 0.9)
            for (px, py, col) in ((0, 0, 1), (1, 0, 2), (0, 1, 2), (1, 1, 15)):
                X, Y = x0 + px, y0 + py
                if 0 <= X < size and 0 <= Y < size and out[Y, X] == 0:
                    out[Y, X] = col
            X, Y = x0 - 1, y0 - 1
            if 0 <= X < size and 0 <= Y < size and out[Y, X] == 0: out[Y, X] = 9
    else:                                  # young: flash spikes out of the core
        d = np.sqrt((xx1 - c) ** 2 + (yy1 - c) ** 2)
        ang = np.arctan2(yy1 - c, xx1 - c)
        spike = (np.abs(np.cos(ang * 4 + 0.4)) ** 24 > 0.5) & (d < size * 0.48) & (out == 0)
        out[spike] = 14
    return out

def flash16(seed=3):
    """16x16 hot flash: a glossy white-hot ball with a 6-point star"""
    g = fireball(16, seed, "A")
    return g

def smoke16(seed, embers=False):
    balls, r = _billows(16, seed, 6, 5.0, (0.2, 0.7), 0.45, 0.7)
    hit, nx, ny, nz, idx, xx, yy = _trace(16, balls)
    lam = nx * L[0] + ny * L[1] + nz * L[2]
    spec = (nx * H[0] + ny * H[1] + nz * H[2]) > 0.97
    g = np.zeros(hit.shape, np.uint8)
    sv = lam * 0.5 + 0.5
    g[hit] = np.where(sv[hit] > 0.8, 7, np.where(sv[hit] > 0.62, 6, np.where(sv[hit] > 0.45, 5, np.where(sv[hit] > 0.28, 4, 3))))
    g[hit & spec] = 7
    out = _down(g, 4)
    if embers:
        rr = np.random.default_rng(seed)
        m = out > 0
        e = m & (rr.random(out.shape) < 0.12)
        out[e] = np.where(rr.random(e.sum()) < 0.5, 8, 9)
    return out
