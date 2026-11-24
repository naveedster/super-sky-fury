#!/usr/bin/env python3
"""v1.6 Stage 1 boss art: Naveed's dad as a giant hovering bust.
dad_ref.jpg -> background removal (rembg u2net_human_seg; the cut-out is cached as dad_cut.png and
committed, so a normal build needs neither rembg nor the network) -> couch removed, holes filled ->
bust composite with a slightly enlarged head -> CLAHE + saturation -> downscale -> 15-colour SNES palette
(dark outline, 3 reds + gold for the Spain jersey, 3 skin, 4 silver/white for hair and beard, lens glare
and crest slots that the game animates) -> outline.  Output: dad_px (H x W indices), DAD_PAL (BGR555),
GLASS (origin: centre of the glasses, in output pixels)."""
import os, numpy as np
from PIL import Image, ImageDraw, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "dad_ref.jpg"); CUT = os.path.join(HERE, "dad_cut.png")

def cutout():
    if not os.path.exists(CUT):
        from rembg import remove, new_session
        remove(Image.open(REF).convert("RGB"), session=new_session("u2net_human_seg")).save(CUT)
    return Image.open(CUT).convert("RGBA")

# full-resolution landmarks (1536 x 2048 photo)
GL = (600, 650)            # centre of the glasses
ANCHOR = (620, 1100)       # bottom of the beard: the enlarged head is scaled about this point
HEAD_E = (620, 640, 330, 495)
COUCH = [(0, 600), (328, 600), (340, 700), (326, 970), (0, 1010)]
BODY_BOTTOM = 1370
S_BODY = 0.100
HEAD_K = 1.16

def bust():
    im = cutout(); W, H = im.size
    a = np.asarray(im).astype(np.float32) / 255
    alpha = a[..., 3]
    m = Image.new("L", (W, H), 255); d = ImageDraw.Draw(m); d.polygon(COUCH, fill=0)
    alpha = alpha * (np.asarray(m) / 255)
    # fill holes (the gold FIFA patch came out transparent): solid inside the body outline
    from scipy import ndimage
    solid = ndimage.binary_fill_holes(alpha > 0.5)
    solid = ndimage.binary_closing(solid, iterations=6)
    alpha = np.maximum(alpha, solid.astype(np.float32))
    # bust silhouette: shoulders inside a wide ellipse, flat cut under the chest
    sil = Image.new("L", (W, H), 0); d = ImageDraw.Draw(sil)
    d.ellipse((620 - 640, 860, 620 + 640, 2200), fill=255)
    d.rectangle((0, BODY_BOTTOM, W, H), fill=0)
    hd = Image.new("L", (W, H), 0); ImageDraw.Draw(hd).ellipse((HEAD_E[0] - HEAD_E[2], HEAD_E[1] - HEAD_E[3], HEAD_E[0] + HEAD_E[2], HEAD_E[1] + HEAD_E[3]), fill=255)
    sil = np.maximum(np.asarray(sil), np.asarray(hd)) / 255
    alpha = alpha * sil
    rgb = a[..., :3].copy()
    # dodge the shaded eye sockets so the eyes read at SNES size
    yy, xx = np.mgrid[0:H, 0:W]
    for cx, cy in ((500, 625), (705, 625)):
        e = np.exp(-(((xx - cx) / 95.0) ** 2 + ((yy - cy) / 55.0) ** 2))
        rgb = rgb * (1 + 0.55 * e[..., None])
    rgb = np.clip(rgb, 0, 1)
    body = np.dstack([rgb, alpha])
    # head layer: feathered ellipse, enlarged about ANCHOR
    hdm = np.asarray(hd.filter(ImageFilter.GaussianBlur(18))) / 255
    head = np.dstack([rgb, alpha * hdm])
    return body, head

WB = np.array([0.96, 1.15, 1.20])   # neutralise the warm room light (the beard becomes grey-white)
def enhance(img):
    import cv2
    rgb = (np.clip(img[..., :3] * WB, 0, 1) * 255).astype(np.uint8)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    cl = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(4, 4))
    lab[..., 0] = cl.apply(lab[..., 0])
    rgb = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.1, 0, 255)
    rgb = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    return np.dstack([rgb.astype(np.float32) / 255, img[..., 3]])

def place(layer, scale, about, out_wh, origin):
    """scale an RGBA float layer by `scale` about full-res point `about`, which lands at out pixel `origin`"""
    H, W = layer.shape[:2]
    prem = layer.copy(); prem[..., :3] *= prem[..., 3:4]
    im = Image.fromarray((np.clip(prem, 0, 1) * 255).astype(np.uint8), "RGBA")
    nw, nh = int(round(W * scale)), int(round(H * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", out_wh, (0, 0, 0, 0))
    ox = int(round(origin[0] - about[0] * scale)); oy = int(round(origin[1] - about[1] * scale))
    canvas.paste(im, (ox, oy))
    return np.asarray(canvas).astype(np.float32) / 255

OUT_W, OUT_H = 128, 144
def compose():
    body, head = bust()
    body = enhance(body); head = enhance(head)
    s_head = S_BODY * HEAD_K
    # output frame: the beard anchor at x = 66, head top just inside the frame
    top = HEAD_E[1] - HEAD_E[3]
    ay = int(round((ANCHOR[1] - top) * s_head)) + 1
    org = (63, ay)
    b = place(body, S_BODY, ANCHOR, (OUT_W, OUT_H), org)
    h = place(head, s_head, ANCHOR, (OUT_W, OUT_H), org)
    # composite premultiplied: head over body
    a = h[..., 3:4] + b[..., 3:4] * (1 - h[..., 3:4])
    c = h[..., :3] + b[..., :3] * (1 - h[..., 3:4])
    rgb = np.where(a > 1e-4, c / np.maximum(a, 1e-4), 0)
    gl = (org[0] + (GL[0] - ANCHOR[0]) * s_head, org[1] + (GL[1] - ANCHOR[1]) * s_head)
    return rgb, a[..., 0], gl, s_head, org

# palette (index: role).  13 = crest (game: glows / flashes), 14 = lens glare (game: telegraph strobe)
PAL_RGB = {
    1: (24, 14, 18),      # outline
    2: (104, 12, 20),     # jersey deep red
    3: (170, 24, 32),     # jersey red
    4: (226, 58, 52),     # jersey highlight
    5: (232, 192, 96),    # gold stripes / logo
    6: (128, 74, 56),     # skin shadow
    7: (188, 120, 92),    # skin
    8: (236, 178, 146),   # skin light
    9: (92, 92, 104),     # hair / beard deep shadow
    10: (150, 150, 162),  # silver
    11: (202, 202, 212),  # light silver
    12: (250, 250, 252),  # white
    13: (60, 36, 30),     # pupils (game: glow red when he telegraphs, white when hit)
    14: (226, 240, 252),  # lens glare (game: strobes while he charges, flashes when hit)
    15: (52, 40, 44),     # eyes, brows, glasses rims, nostrils
}
MATCH_RGB = dict(PAL_RGB)
MATCH_RGB.update({2: (90, 14, 30), 3: (150, 24, 40), 4: (200, 60, 66), 5: (220, 190, 120),
                  6: (118, 84, 82), 7: (170, 132, 124), 8: (214, 178, 166),
                  9: (84, 88, 96), 10: (138, 142, 148), 11: (186, 190, 194), 12: (232, 234, 236), 15: (46, 40, 44)})
def quantize(rgb, a, gl, s_head, org):
    import cv2
    H, W = a.shape
    op = a > 0.5
    lab_p = cv2.cvtColor(np.array([[MATCH_RGB[i] for i in range(1, 16)]], np.uint8), cv2.COLOR_RGB2LAB)[0].astype(np.float32)
    lab = cv2.cvtColor((np.clip(rgb, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
    usable = [i for i in range(1, 16) if i not in (1, 13, 14)]
    d = ((lab[:, :, None, :] - lab_p[None, None, [u - 1 for u in usable], :]) * np.array([1.0, 1.35, 1.35])) ** 2
    idx = np.array(usable)[d.sum(-1).argmin(-1)]
    px = np.where(op, idx, 0).astype(np.uint8)
    # special regions (full-res landmarks -> output)
    def P(x, y): return (org[0] + (x - ANCHOR[0]) * s_head, org[1] + (y - ANCHOR[1]) * s_head)
    yy, xx = np.mgrid[0:H, 0:W]
    L = lab[..., 0]
    for cx, cy in ((500, 612), (702, 612)):          # pupils -> slot 13 (glow red when he telegraphs)
        qx, qy = P(cx, cy); r = 22 * s_head
        eye = ((xx - qx) / (r * 1.3)) ** 2 + ((yy - qy) / r) ** 2 < 1
        if eye.any():
            thr = np.percentile(L[eye], 35)
            px[eye & op & (L <= thr)] = 13
    for cx, cy, w, h in ((505, 640, 92, 70), (705, 640, 92, 70)):   # rimless lenses: lit lower edge + glare streak
        qx, qy = P(cx, cy); rw, rh = w * s_head, h * s_head
        for t in np.linspace(0.15 * np.pi, 0.85 * np.pi, 24):
            ex, ey = int(round(qx + rw * np.cos(t))), int(round(qy + rh * np.sin(t)))
            if 0 <= ey < H and 0 <= ex < W and op[ey, ex]: px[ey, ex] = 11
        for k in range(4):                           # glare: short diagonal at the upper left of each lens
            ex, ey = int(round(qx - rw * 0.45 + k)), int(round(qy - rh * 0.55 + k))
            if op[ey, ex]: px[ey, ex] = 14
        ex, ey = int(round(qx - rw * 0.45 + 1)), int(round(qy - rh * 0.55))
        if op[ey, ex]: px[ey, ex] = 14
    for (x0, y0, x1, y1) in ((430, 560, 560, 580), (780, 560, 650, 580)):   # stern brows: inner ends lower
        ax_, ay_ = P(x0, y0 - 10); bx_, by_ = P(x1, y1)
        for t in np.linspace(0, 1, 14):
            ex, ey = int(round(ax_ + (bx_ - ax_) * t)), int(round(ay_ + (by_ - ay_) * t))
            if op[ey, ex]: px[ey, ex] = 9; 
            if op[ey + 1, ex] and t > 0.5: px[ey + 1, ex] = 15
    qx, qy = (org[0] + (975 - ANCHOR[0]) * S_BODY, org[1] + (1085 - ANCHOR[1]) * S_BODY)   # Spain crest: gold on red
    crest = ((xx - qx) / 9.0) ** 2 + ((yy - qy) / 10.0) ** 2 < 1
    cr = crest & op & ~np.isin(px, (1,))
    px[cr & (L > np.percentile(L[cr], 55))] = 5
    px[cr & (L <= np.percentile(L[cr], 55)) & (L > np.percentile(L[cr], 20))] = 3
    px[cr & (L <= np.percentile(L[cr], 20))] = 2
    bx, by = P(604, 628)                            # bridge
    for k in range(-2, 3):
        px[int(round(by)), int(round(bx)) + k] = 11
    # 1-px dark outline around the silhouette (inside the frame)
    o = np.zeros_like(op)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        o |= np.roll(np.roll(op, dy, 0), dx, 1)
    px[o & ~op] = 1
    px[0, :] = px[-1, :] = 0; px[:, 0] = px[:, -1] = 0
    return px

def bgr555(c): r, g, b = c; return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)
DAD_PAL = [0] + [bgr555(PAL_RGB[i]) for i in range(1, 16)]

PXC = os.path.join(HERE, "dad_px.png")   # the finished 16-colour sprite (committed); the photo itself stays private

def build():
    if not (os.path.exists(REF) or os.path.exists(CUT)):
        im = Image.open(PXC)
        return np.asarray(im).astype(np.uint8).copy(), tuple(int(v) for v in im.info["gl"].split(","))
    rgb, a, gl, s_head, org = compose()
    px = quantize(rgb, a, gl, s_head, org)
    g = (int(round(gl[0])), int(round(gl[1])))
    from PIL import PngImagePlugin
    im = Image.fromarray(px.astype(np.uint8), "P")
    im.putpalette([c for i in range(16) for c in (PAL_RGB[i] if i else (0, 0, 0))])
    meta = PngImagePlugin.PngInfo(); meta.add_text("gl", f"{g[0]},{g[1]}")
    im.save(PXC, pnginfo=meta)
    return px, g

def preview(px, path, k=4):
    lut = np.array([(0, 90, 160)] + [PAL_RGB[i] for i in range(1, 16)], np.uint8)
    Image.fromarray(lut[px]).resize((px.shape[1] * k, px.shape[0] * k), Image.NEAREST).save(path)

if __name__ == "__main__":
    px, g = build()
    print("dad", px.shape, "glasses at", g, "opaque", int((px > 0).sum()))
    import sys; preview(px, sys.argv[1] if len(sys.argv) > 1 else "/tmp/dad_px.png")
