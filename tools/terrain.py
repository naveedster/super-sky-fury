"""Mode 7 ground generator (graphics v1): 1 px detail terrain with lighting, forests, beaches, surf,
lagoons, farm fields, roads, towns and an airfield, reduced to 256 8bpp tiles."""
import math, random
import numpy as np
from PIL import Image

def hexrgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

# colour slots usable by Mode 7: 1..27, 32..47 (28..31 = BG3 horizon band), 112..127
INFO = {}   # per map: land mask (1024^2), town tiles, airfield (v1.1 ground props)
SLOTS = list(range(1, 28)) + list(range(32, 48)) + list(range(112, 128))
GROUND = [
 ("deep3", "#123a88"), ("deep", "#18469a"), ("deep2", "#1e52aa"), ("swell", "#2c68c0"), ("crest", "#5c94dc"),
 ("fleck", "#a8ccf4"), ("white", "#eef6ff"),
 ("shal1", "#2672c0"), ("shal2", "#2f8ccc"), ("shal3", "#3eaad4"), ("shal4", "#62c8d8"), ("foam", "#dcf2f6"),
 ("sand1", "#f4e2a4"), ("sand2", "#e0c47c"), ("sand3", "#bc9c58"), ("wet", "#9c8c68"),
 ("g1", "#b0e05a"), ("g2", "#8ecc40"), ("g3", "#70b432"), ("g4", "#54982a"), ("g5", "#3c7a22"),
 ("f1", "#5aa236"), ("f2", "#3c8428"), ("f3", "#2a681e"), ("f4", "#1a4e14"), ("f5", "#0f3410"),
 ("r1", "#d0c8b0"), ("r2", "#a49c88"), ("r3", "#7c766a"), ("r4", "#56524c"),
 ("wheat1", "#f0d468"), ("wheat2", "#cca844"), ("soil1", "#a87848"), ("soil2", "#7c5634"),
 ("crop1", "#c4ea78"), ("crop2", "#9ad050"),
 ("road1", "#a09a90"), ("road2", "#5e5c58"),
 ("roof1", "#d84c30"), ("roof2", "#9a2c1c"), ("roof3", "#f4f0e4"), ("roof4", "#eca848"), ("dark", "#24301e"),
 ("plaza", "#cdc4aa"), ("tarmac", "#44484e"), ("tarm2", "#5a5e66"),
]

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0 + 1 / 32

def build(CGRAM, OUT, rng_seed=1234, islands=None, suffix="", nseed=0):
    G = {}
    for (n, c), s in zip(GROUND, SLOTS):
        G[n] = s; CGRAM[s] = hexrgb(c)
    assert len(GROUND) <= len(SLOTS)
    rng = np.random.default_rng(rng_seed); R = random.Random(rng_seed)

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
    def roll(a, dy, dx): return np.roll(np.roll(a, dy, 0), dx, 1)
    def dilate(m, n):
        out = m.copy()
        for _ in range(n):
            o = out.copy()
            o |= np.roll(out, 1, 0); o |= np.roll(out, -1, 0); o |= np.roll(out, 1, 1); o |= np.roll(out, -1, 1)
            out = o
        return out
    def blur(a, n):
        for _ in range(n):
            a = (a + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 5
        return a

    N = 1024
    yy, xx = np.mgrid[0:N, 0:N].astype(float)
    islands = islands or [(250, 330, 62), (300, 280, 40), (210, 360, 34), (120, 120, 46), (150, 90, 26), (420, 90, 28),
               (440, 420, 52), (470, 450, 30), (60, 400, 30), (200, 470, 20), (300, 430, 16), (470, 260, 18),
               (160, 260, 14), (350, 160, 12), (40, 220, 16),
               (380, 330, 26), (90, 300, 20), (330, 40, 24), (30, 40, 18), (250, 185, 22), (400, 220, 14), (110, 480, 14)]
    h = np.full((N, N), -1.0)
    for cx, cy, r in islands:
        cx *= 2; cy *= 2; r *= 2.25
        dx = np.minimum(abs(xx - cx), N - abs(xx - cx)); dy = np.minimum(abs(yy - cy), N - abs(yy - cy))
        h = np.maximum(h, 1 - np.sqrt(dx * dx + dy * dy) / r)
    h = h + (fbm(N, 6, 7, 7 + nseed) - 0.5) * 1.6 + (fbm(N, 4, 3, 21 + nseed) - 0.5) * 0.6 + (fbm(N, 20, 5, 33 + nseed) - 0.5) * 0.9
    land = h > 0.0
    # remove 1-px specks
    nb = sum(roll(land, dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
    land = (land & (nb >= 4)) | (~land & (nb >= 7))
    hs = blur(np.where(land, h, 0.0), 2)
    shade = (roll(hs, -1, -1) - roll(hs, 1, 1)) * 9.0          # light from the north-west
    img = np.zeros((N, N), np.uint8)
    dith = np.tile(BAYER4, (N // 4, N // 4))

    def ramp(mask, names, val):
        """val in [0,1): picks ramp entry with ordered dithering"""
        v = np.clip(val, 0, 0.999) * (len(names) - 1)
        i0 = np.floor(v).astype(int); fr = v - i0
        idx = np.clip(i0 + (fr > dith), 0, len(names) - 1)
        lut = np.array([G[n] for n in names], np.uint8)
        img[mask] = lut[idx[mask]]

    # ---- natural terrain. Large areas use tile-level shading steps with tile-periodic textures, so
    # interior tiles repeat exactly and the tile budget goes to coastlines and edges.
    T = 128
    def tmean(val, mask=None):
        if mask is None: m = val.reshape(T, 8, T, 8).mean(axis=(1, 3))
        else:
            w = mask.reshape(T, 8, T, 8).sum(axis=(1, 3)); s = np.where(mask, val, 0).reshape(T, 8, T, 8).sum(axis=(1, 3))
            m = s / np.maximum(w, 1)
        return np.kron(m, np.ones((8, 8)))
    def ramp_t(mask, names, val, steps=None):
        """tile-level shading: one dither level per tile"""
        v = np.clip(tmean(val, mask), 0, 0.999)
        n = len(names); S = steps or (n - 1) * 2
        lv = np.floor(v * S) / S * (n - 1) + 1e-6     # quantized level
        i0 = np.floor(lv).astype(int); fr = lv - i0
        idx = np.clip(i0 + (fr > dith), 0, n - 1)
        lut = np.array([G[c] for c in names], np.uint8)
        img[mask] = lut[idx[mask]]
    tyx = np.mgrid[0:N, 0:N] // 8
    thash = ((tyx[0] * 73856093) ^ (tyx[1] * 19349663)) % 1000 / 1000.0
    ly, lx = (np.mgrid[0:N, 0:N] % 8)

    dist = np.full((N, N), 99, int); cur = land.copy()
    for d in range(1, 26):
        nxt = dilate(cur, 1); dist[nxt & ~cur] = d; cur = nxt
    ocean = ~land
    depth = fbm(N, 4, 4, 99)
    # open ocean: 5 depth levels, plus wave-stroke patterns inside tiles
    ramp_t(ocean, ["deep3", "deep", "deep2"], (depth - 0.30) * 2.4, steps=4)
    pats = []
    pr = random.Random(5)
    for k in range(11):
        p = []
        for s in range(1 + (k % 3 == 0)):
            y = pr.randrange(1, 8); x = pr.randrange(0, 4); L = pr.randrange(3, 5)
            p.append((y, x, L, pr.random() < 0.35, pr.random() < 0.08))
        pats.append(p)
    waves = fbm(N // 8, 8, 3, 123)
    for ty in range(T):
        for tx in range(T):
            y0, x0 = ty * 8, tx * 8
            if dist[y0:y0 + 8, x0:x0 + 8].min() < 26: continue
            r_ = ((ty * 2654435761) ^ (tx * 40503)) % 997 / 997.0
            if r_ > 0.25 + waves[ty, tx] * 0.6: continue
            for (y, x, L, fl, wh) in pats[int(r_ * 7919) % 11]:
                img[y0 + y, x0 + x:x0 + x + L] = G["swell"]
                img[y0 + y - 1, x0 + x + 1:x0 + x + L - 1] = G["crest"]
                if fl: img[y0 + y - 1, x0 + x + 1] = G["fleck"]
                if wh: img[y0 + y - 1, x0 + x + 2] = G["white"]
    # shallows: pixel gradient right at the coast, tile steps further out
    near6 = ocean & (dist <= 12)
    ramp(near6, ["deep2", "shal1", "shal2", "shal3", "shal4"], 1 - (dist - 1) / 12.0 + (fbm(N, 24, 2, 71) - 0.5) * 0.25)
    surf = ocean & (dist == 1)
    img[surf & (dith < 0.8)] = G["foam"]
    sl = ocean & (dist == 3) & (np.sin(xx * 0.45 + yy * 0.3 + fbm(N, 32, 2, 81) * 12) > 0.4)
    img[sl] = G["foam"]; img[ocean & (dist == 4) & roll(sl, -1, 0)] = G["shal4"]
    # ---- land
    ldist = np.full((N, N), 99, int); cur = ~land
    for d in range(1, 10):
        nxt = dilate(cur, 1); ldist[nxt & ~cur] = d; cur = nxt
    beach = land & (ldist <= 3 + (fbm(N, 20, 2, 91) * 4).astype(int)) & (h < 0.55)
    ramp(beach, ["sand3", "sand2", "sand1"], 0.6 + shade * 0.6)
    img[land & (ldist == 1) & beach] = G["wet"]
    inland = land & ~beach
    rock = inland & (h > 1.30)
    forest = inland & ~rock & (h > 0.62 + (fbm(N, 12, 3, 101) - 0.5) * 1.1)
    grass = inland & ~rock & ~forest
    lightv = 0.5 + shade * 1.1
    ramp_t(grass, ["g5", "g4", "g3", "g2", "g1"], lightv + 0.05 + (fbm(N, 16, 2, 111) - 0.5) * 0.25, steps=8)
    # grass detail: tile-periodic tufts/bushes in some tiles
    tuft = grass & (thash < 0.45) & (((ly == 2) & (lx == 5)) | ((ly == 6) & (lx == 1)))
    img[tuft] = G["g4"]; img[grass & (thash < 0.45) & (ly == 1) & (lx == 5)] = G["g1"]
    bush = grass & (thash > 0.82) & (ly >= 3) & (ly <= 5) & (lx >= 3) & (lx <= 5)
    bmap = {(3, 4): "f1", (3, 3): "f2", (3, 5): "f2", (4, 3): "f2", (4, 4): "f2", (4, 5): "f3", (5, 4): "f4", (5, 5): "f5", (5, 3): "f3"}
    for (y_, x_), c in bmap.items(): img[bush & (ly == y_) & (lx == x_)] = G[c]
    # forest: crowns on a tile-periodic lattice, lit from the north-west, 3 light levels per tile
    lev = np.clip(np.floor(tmean(lightv, forest) * 3), 0, 2).astype(int)
    crown = np.zeros((8, 8), int)    # 0 gap, 1 highlight, 2 body, 3 shade
    for cy, cx in ((1, 1), (1, 5), (5, 3), (5, 7)):
        for dy in (-1, 0, 1, 2):
            for dx in (-1, 0, 1, 2):
                if abs(dy - 0.5) + abs(dx - 0.5) > 2.1: continue
                v = 1 if (dy + dx) <= -1 else (3 if dy + dx >= 2 else 2)
                crown[(cy + dy) % 8, (cx + dx) % 8] = v
    crown2 = crown[:, ::-1].copy(); crown2 = np.roll(crown2, 1, 1)
    cols = {0: [["f5", "f2", "f3", "f4"], ["f4", "f1", "f2", "f3"], ["f3", "f1", "f2", "f2"]]}[0]
    cp = np.where(thash < 0.5, crown[ly, lx], np.roll(crown, 4, 0)[ly, lx])
    for L_ in range(3):
        for v in range(4):
            img[forest & (lev == L_) & (cp == v)] = G[cols[L_][v]]
    # rock: tile-level shading + crack pattern
    ramp_t(rock, ["r4", "r3", "r2", "r1"], 0.5 + shade * 1.6 + (h - 1.3) * 0.5, steps=6)
    crack = rock & (((ly == 3) & (lx >= 1) & (lx <= 4)) | ((ly == 4) & (lx == 5)) | ((ly == 7) & (lx >= 4) & (thash > 0.5)))
    img[crack] = G["r4"]; img[rock & (ly == 2) & (lx >= 1) & (lx <= 3)] = G["r1"]

    # ---- tile-level man-made features on the big island
    T = 128
    tl = np.asarray(land).reshape(T, 8, T, 8).all(axis=(1, 3))
    tg = (grass | beach).reshape(T, 8, T, 8).all(axis=(1, 3)) & tl
    tflat = tl & ~rock.reshape(T, 8, T, 8).any(axis=(1, 3))
    # main landmass: flood fill from the big island centre
    lab = np.zeros((T, T), int); nl = 0; sizes = {}
    for sy in range(T):
        for sx in range(T):
            if not tflat[sy, sx] or lab[sy, sx]: continue
            nl += 1; st = [(sy, sx)]; n = 0
            while st:
                y, x = st.pop()
                if lab[y, x] or not tflat[y, x]: continue
                lab[y, x] = nl; n += 1
                st += [((y + 1) % T, x), ((y - 1) % T, x), (y, (x + 1) % T), (y, (x - 1) % T)]
            sizes[nl] = n
    big2 = sorted(sizes, key=lambda k: -sizes[k])[:3]
    print("flat components", sorted(sizes.values())[-4:])
    comp = np.isin(lab, big2)
    # tile distance to non-comp
    td = np.zeros((T, T), int); cur = ~comp
    for d in range(1, 8):
        nxt = cur | np.roll(cur, 1, 0) | np.roll(cur, -1, 0) | np.roll(cur, 1, 1) | np.roll(cur, -1, 1)
        td[nxt & ~cur] = d; cur = nxt
    td[~cur] = 8
    feature = np.zeros((T, T), int)      # 0 none, 1 road, 2 town, 3 field, 4 runway, 5 apron
    roadmask = np.zeros((T, T), int)     # N=1 E=2 S=4 W=8
    # towns: farthest-point sampling over interior tiles
    towns = []; pairs = []
    for L_ in big2:
        cand = [tuple(p) for p in np.argwhere((lab == L_) & (td >= 3))]
        if not cand: continue
        a0 = max(cand, key=lambda p: td[p])
        def md(p, q): return abs(p[0] - q[0]) + abs(p[1] - q[1])
        a1 = max(cand, key=lambda p: md(p, a0))
        a2 = max(cand, key=lambda p: md(p, a1))
        if md(a1, a2) >= 10: towns += [a1, a2]; pairs.append((a1, a2))
        else: towns.append(a0)
    # airfield: longest horizontal run of comp tiles with clearance, away from towns
    best = None
    for y in range(T):
        run = 0
        for x in range(T + 1):
            ok = x < T and comp[y, x] and td[y, x] >= 2 and comp[(y + 1) % T, x] and all(
                abs(y - t[0]) > 3 or abs(x - t[1]) > 4 for t in towns)
            if ok: run += 1
            else:
                if run >= 9 and (best is None or run > best[2]): best = (y, x - run, run)
                run = 0
    if best:
        y, x0, run = best; L = min(run, 12); x0 += (run - L) // 2
        for k in range(L):
            feature[y, x0 + k] = 4; feature[y + 1, x0 + k] = 5
        airfield = (y, x0, L)
    else:
        airfield = None
    # town blocks
    for ty, tx in towns:
        for dy in range(-1, 2):
            for dx in range(-2, 2):
                p = ((ty + dy) % T, (tx + dx) % T)
                if comp[p] and feature[p] == 0: feature[p] = 2
    # roads: BFS between consecutive towns (+ the airfield) on comp tiles
    def path(a, b):
        import heapq
        D = ((1, 0), (-1, 0), (0, 1), (0, -1))
        best = {}; pq = [(0, a, -1, None)]; prev = {}
        while pq:
            c, p, d, pp = heapq.heappop(pq)
            if (p, d) in best: continue
            best[(p, d)] = c; prev[(p, d)] = pp
            if p == b:
                out = [(p, d)]
                while prev[out[-1]] is not None: out.append(prev[out[-1]])
                return [q[0] for q in out[::-1]]
            for k, dd in enumerate(D):
                n = ((p[0] + dd[0]) % T, (p[1] + dd[1]) % T)
                if comp[n] and feature[n] not in (4, 5) and (n, k) not in best:
                    heapq.heappush(pq, (c + 1 + (4 if d not in (-1, k) else 0) + (0 if td[n] >= 2 else 2), n, k, (p, d)))
        return []
    if airfield:
        ap = (airfield[0] - 1, airfield[1] + airfield[2] // 2)
        same = [t for t in towns if lab[t] == lab[ap]]
        if same:
            # route one town's road through the airfield
            for i, (u, w) in enumerate(pairs):
                if lab[u] == lab[ap]: pairs[i] = (u, ap); pairs.append((ap, w)); break
    for a, b in pairs:
        p = path(a, b)
        for u, v in zip(p, p[1:]):
            dy = (v[0] - u[0] + 1) % T - 1; dx = (v[1] - u[1] + 1) % T - 1
            bu = {(-1, 0): 1, (0, 1): 2, (1, 0): 4, (0, -1): 8}[(dy, dx)]
            bv = {1: 4, 2: 8, 4: 1, 8: 2}[bu]
            roadmask[u] |= bu; roadmask[v] |= bv
    for p in np.argwhere(roadmask > 0):
        p = tuple(p)
        if feature[p] == 0: feature[p] = 1
    if airfield:   # taxiway connection
        y, x0, L = airfield; p = (y - 1, x0 + L // 2)
        roadmask[p] |= 4
    # fields: 2x2 tile plots near roads/towns
    near = (roadmask > 0) | (feature == 2)
    for _ in range(7): near = near | np.roll(near, 1, 0) | np.roll(near, -1, 0) | np.roll(near, 1, 1) | np.roll(near, -1, 1)
    plots = []
    for y in range(0, T, 2):
        for x in range(0, T, 2):
            blk = [(y, x), (y, x + 1), (y + 1, x), (y + 1, x + 1)]
            if all(tg[p] and comp[p] and feature[p] == 0 and near[p] for p in blk) and R.random() < 0.8:
                kind = R.randrange(4)
                for i, p in enumerate(blk): feature[p] = 3; plots.append((p, kind, i))

    # ---- draw features
    px = img.reshape(T, 8, T, 8)
    def grassbase():
        t = np.full((8, 8), G["g3"], np.uint8); t[(BAYER4.repeat(2, 0).repeat(2, 1)[:8, :8] > 0.7)] = G["g2"]; return t
    FIELD = [("wheat1", "wheat2", 0), ("crop1", "crop2", 1), ("soil1", "soil2", 0), ("crop2", "g4", 1)]
    for (p, kind, i) in plots:
        a, b, vert = FIELD[kind]
        t = np.zeros((8, 8), np.uint8)
        for y in range(8):
            for x in range(8):
                k = x if vert else y
                t[y, x] = G[a] if k % 2 == 0 else G[b]
        if i in (0, 1): t[0, :] = G["g5"]
        if i in (0, 2): t[:, 0] = G["g5"]
        if i == 0: t[0, 0] = G["f3"]
        px[p[0], :, p[1], :] = t
    def roadtile(m, base=None):
        t = grassbase() if base is None else base.copy()
        c0, c1 = 3, 5
        if m & 1: t[0:c0 + 1, c0 - 1:c1 + 1] = G["road2"]; t[0:c0 + 1, c0:c1] = G["road1"]
        if m & 4: t[c0 - 1:8, c0 - 1:c1 + 1] = G["road2"]; t[c0 - 1:8, c0:c1] = G["road1"]
        if m & 8: t[c0 - 1:c1 + 1, 0:c0 + 1] = G["road2"]; t[c0:c1, 0:c0 + 1] = G["road1"]
        if m & 2: t[c0 - 1:c1 + 1, c0 - 1:8] = G["road2"]; t[c0:c1, c0 - 1:8] = G["road1"]
        if m: t[c0:c1, c0:c1] = G["road1"]
        return t
    for p in np.argwhere(feature == 1):
        p = tuple(p); px[p[0], :, p[1], :] = roadtile(roadmask[p], px[p[0], :, p[1], :])
    def towntile(seed, m):
        r = random.Random(int(seed)); t = np.full((8, 8), G["plaza"], np.uint8)
        t[(BAYER4.repeat(2, 0).repeat(2, 1)[:8, :8] > 0.85)] = G["g3"]
        for (y, x) in ((0, 0), (0, 4), (4, 0), (4, 4)):
            if r.random() < 0.15:
                t[y + 1, x + 1] = G["f2"]; t[y + 2, x + 2] = G["f4"]; continue
            col = r.choice(["roof1", "roof1", "roof3", "roof4"])
            hw, hh = r.choice(((3, 2), (2, 3), (3, 3)))
            t[y:y + hh, x:x + hw] = G[col]
            t[y, x:x + hw] = G["roof3"] if col != "roof3" else G["r1"]
            if col == "roof1": t[y + hh - 1, x:x + hw] = G["roof2"]
            if y + hh < 8: t[y + hh, x + 1:min(8, x + hw + 1)] = G["dark"]
            if x + hw < 8: t[y + 1:y + hh + 1, x + hw] = G["dark"]
        if m:
            rt = roadtile(m); msk = rt == G["road1"]; t[msk] = G["road1"]; t[rt == G["road2"]] = G["road2"]
        return t
    for p in np.argwhere(feature == 2):
        p = tuple(p); px[p[0], :, p[1], :] = towntile((p[0] * 7 + p[1] * 3) % 5, roadmask[p])
    if airfield:
        y, x0, L = airfield
        for k in range(L):
            t = np.full((8, 8), G["tarmac"], np.uint8)
            t[0, :] = G["g4"]; t[7, :] = G["tarm2"]
            t[1, :] = G["tarm2"]; t[6, :] = G["tarm2"]
            if 0 < k < L - 1 and k % 2 == 0: t[3:5, 1:6] = G["white"]
            if k in (0, L - 1):
                for xx_ in range(1, 7, 2): t[2:6, xx_] = G["white"]
                if k == 0: t[:, 0] = G["g3"]
                else: t[:, 7] = G["g3"]
            px[y, :, x0 + k, :] = t
            a = np.full((8, 8), G["tarm2"], np.uint8)
            a[7, :] = G["g3"]
            if k % 3 == 1: a[2:5, 2:6] = G["tarmac"]; a[3, 1:7] = G["r1"]; a[2:5, 3] = G["r1"]   # parked plane
            if k in (0, L - 1): a[:, 0 if k == 0 else 7] = G["g3"]
            px[y + 1, :, x0 + k, :] = a
    img = px.reshape(N, N)

    # ---- tile reduction: ocean tiles and land tiles get separate budgets
    tiles = img.reshape(T, 8, T, 8).swapaxes(1, 2).reshape(T * T, 64)
    oceanset = [G[n] for n in ("deep3", "deep", "deep2", "swell", "crest", "fleck", "white")]
    isoc = np.isin(tiles, oceanset).all(axis=1)
    rgb = np.array([CGRAM[i] for i in range(256)], float)
    def reduce(idx, K, exact_keep=()):
        uniq, inv = np.unique(tiles[idx], axis=0, return_inverse=True); inv = inv.reshape(-1)
        counts = np.bincount(inv)
        print("  unique", len(uniq), "budget", K)
        if len(uniq) <= K: return uniq, inv
        feat = rgb[uniq].reshape(len(uniq), -1)
        # blurred features too, so structure matters a bit less than overall colour
        fb = rgb[uniq].reshape(len(uniq), 8, 8, 3)
        fb2 = fb.reshape(len(uniq), 4, 2, 4, 2, 3).mean(axis=(2, 4)).reshape(len(uniq), -1)
        feat = np.concatenate([feat * 0.6, fb2 * 2.0], 1)
        # forced keeps: designed tiles (fields, roads, towns, runway) used >= 2 times
        order = np.argsort(-counts)
        keep = [i for i in order if exact_keep and exact_keep(uniq[i]) and counts[i] >= 2][:56]
        ks = set(keep)
        for i in order[:K // 4]:
            if i not in ks and counts[i] >= 6: keep.append(i); ks.add(i)
        # k-means++ seeding (count weighted) so rare but distinct tiles (rock, towns) get centres too
        kr = np.random.default_rng(7)
        chosen = list(keep) if keep else [order[0]]
        d2 = ((feat - feat[chosen[0]]) ** 2).sum(1)
        for c_ in chosen[1:]: d2 = np.minimum(d2, ((feat - feat[c_]) ** 2).sum(1))
        while len(chosen) < K:
            p = d2 * np.sqrt(counts); p = p / p.sum()
            c_ = int(kr.choice(len(uniq), p=p)); chosen.append(c_)
            d2 = np.minimum(d2, ((feat - feat[c_]) ** 2).sum(1))
        cent = feat[chosen].copy()
        nk = len(keep)
        for it in range(18):
            d = (feat ** 2).sum(1)[:, None] - 2 * feat @ cent.T + (cent ** 2).sum(1)[None, :]
            a = d.argmin(1)
            for k in range(nk, K):
                m = a == k
                if m.any(): cent[k] = (feat[m] * counts[m, None]).sum(0) / counts[m].sum()
        d = (feat ** 2).sum(1)[:, None] - 2 * feat @ cent.T + (cent ** 2).sum(1)[None, :]
        a = d.argmin(1)
        med = np.zeros((K, 64), np.uint8)
        for k in range(K):
            m = np.nonzero(a == k)[0]
            if k < nk: med[k] = uniq[keep[k]]; continue
            if len(m) == 0: med[k] = uniq[order[0]]; continue
            dd = ((feat[m] - cent[k]) ** 2).sum(1)
            med[k] = uniq[m[dd.argmin()]]
        # final assignment against the actual medoid tiles
        mf_rgb = rgb[med].reshape(K, 8, 8, 3)
        mf = np.concatenate([mf_rgb.reshape(K, -1) * 0.6, mf_rgb.reshape(K, 4, 2, 4, 2, 3).mean(axis=(2, 4)).reshape(K, -1) * 2.0], 1)
        d = (feat ** 2).sum(1)[:, None] - 2 * feat @ mf.T + (mf ** 2).sum(1)[None, :]
        a = d.argmin(1)
        return med, a[inv]
    manmade = set(G[n] for n in ("wheat1", "wheat2", "soil1", "soil2", "crop1", "road1", "road2", "roof1", "roof2",
                                 "roof3", "roof4", "plaza", "tarmac", "tarm2", "r3", "r4"))
    oc_idx = np.nonzero(isoc)[0]; ld_idx = np.nonzero(~isoc)[0]
    KO = 48
    print("ocean:"); med_o, as_o = reduce(oc_idx, KO)
    KO = len(med_o)
    print("land:"); med_l, as_l = reduce(ld_idx, 256 - KO, lambda t: any(int(v) in manmade for v in t))
    tilemap = np.zeros(T * T, int)
    tilemap[oc_idx] = as_o; tilemap[ld_idx] = KO + as_l
    alltiles = np.zeros((256, 64), np.uint8)
    alltiles[:KO] = med_o; alltiles[KO:KO + len(med_l)] = med_l
    alltiles[alltiles == 0] = G["deep"]
    open(f"{OUT}/m7map{suffix}.bin", "wb").write(bytes(tilemap.astype(np.uint8)))
    open(f"{OUT}/m7tiles{suffix}.bin", "wb").write(bytes(alltiles.reshape(-1)))
    rec = alltiles[tilemap].reshape(T, T, 8, 8).swapaxes(1, 2).reshape(N, N)
    Image.fromarray(rgb[rec].astype(np.uint8)).save(f"{OUT}/preview_map{suffix}.png")
    Image.fromarray(rgb[img].astype(np.uint8)).save(f"{OUT}/preview_map_full{suffix}.png")
    print("towns", towns, "airfield", airfield)
    INFO[suffix] = dict(land=land, towns=list(towns), airfield=airfield)
    return G
