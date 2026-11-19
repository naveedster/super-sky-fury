#!/usr/bin/env python3
"""SUPER SKY FURY title screen art + tables (all generated; the logo font is Russo One, OFL).

The game name lives HERE ONLY: GAME_BANNER / GAME_TITLE drive the logo, the ROM header name
(assets/romname.inc) and the title text.  Outputs (assets/):
  title_tiles.bin   BG2 4bpp tiles (VRAM $4000): logo, sky font, panel font
  title_cursor.bin  OBJ 32x32 cell (4 rows x 4 tiles, 128 B per row): the menu cursor jet
  title.inc         palette, logo map, HDMA tables, sine table, text strings, constants
  romname.inc       the 21-byte internal ROM name
  title_logo.png    preview
"""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

GAME_BANNER = "SUPER"
GAME_TITLE = "SKY FURY"
DEVELOPER = "NAVEED FARBAKHSH"
YEAR = "2026"
ROM_NAME = f"{GAME_BANNER} {GAME_TITLE}"

OUT = sys.argv[1] if len(sys.argv) > 1 else "assets"
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_TTF = os.path.join(HERE, "fonts", "RussoOne-Regular.ttf")   # SIL OFL 1.1, see tools/fonts/OFL.txt

def hexrgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
def bgr555(c):
    r, g, b = c; return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)

# ------------------------------------------------------------------ palettes (CGRAM 48-111; Mode 7 owns the rest)
PANEL = "#0a1230"
PAL3 = ["#000000", "#06060e", "#14205a", "#2846a0", "#4a78dc", "#8cbcff", "#d4ecff", "#ffffff",
        "#ffcc30", "#f08010", "#801408", "#d82818", "#ff6c48", "#7a4400", "#fff0a8", "#0a0c26"]   # logo
PAL4 = ["#000000", "#ffd838", "#1e1400", "#b08a10", "#fff6c0", "#f09018"] + ["#000000"] * 9 + [PANEL]   # text
PAL5 = ["#000000", "#9cd0ff", "#000a1e", "#3a6ab0", "#ffffff", "#5c8ee0"] + ["#000000"] * 9 + [PANEL]   # credits
PAL6 = ["#000000", "#ffffff", "#5a0a00", "#ff6040", "#ffffff", "#ffb090"] + ["#000000"] * 9 + [PANEL]   # selected
PALS = PAL3 + PAL4 + PAL5 + PAL6

# ------------------------------------------------------------------ tiles
tiles = []
index = {}
def add(t):
    t = np.asarray(t, np.uint8)
    for hf in (0, 1):
        v = t[:, ::-1] if hf else t
        k = v.tobytes()
        if k in index:
            return index[k], hf
    index[t.tobytes()] = len(tiles); tiles.append(t.copy()); return len(tiles) - 1, 0
def mw(tile, pal, hf=0, prio=1):
    return tile | (pal << 10) | (prio << 13) | (hf << 14)
add(np.zeros((8, 8)))                       # 0: transparent

# ------------------------------------------------------------------ the logo (index image, 256 x 72)
W, H = 256, 72
logo = np.zeros((H, W), np.uint8)
def mask_text(txt, size, shear=0.0, track=0):
    f = ImageFont.truetype(FONT_TTF, size)
    w = sum(f.getbbox(c)[2] for c in txt) + track * (len(txt) - 1) + 40
    im = Image.new("L", (w, size * 2), 0); d = ImageDraw.Draw(im)
    x = 20
    for c in txt:
        d.text((x, size // 3), c, font=f, fill=255)
        x += f.getbbox(c)[2] + track
    if shear:
        im = im.transform(im.size, Image.AFFINE, (1, shear, -shear * size, 0, 1, 0), Image.BICUBIC)
    a = np.array(im) > 110
    ys, xs = np.nonzero(a)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r + r:
                out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out
def place(m, x0, y0):
    full = np.zeros((H, W), bool); h, w = m.shape
    full[y0:y0 + h, x0:x0 + w] = m; return full

# "SKY FURY": big italic chrome letters, 2-px dark outline, gold under-rim, deep drop shadow
big = mask_text(GAME_TITLE, 46, shear=0.22, track=1)
scale = min(1.0, 236 / big.shape[1])
if scale < 1.0:
    im = Image.fromarray(big.astype(np.uint8) * 255).resize((int(big.shape[1] * scale), int(big.shape[0] * scale)), Image.LANCZOS)
    big = np.array(im) > 110
bh, bw = big.shape
BX, BY = (W - bw) // 2, 26
letters = place(big, BX, BY)
outline = dilate(letters, 2) & ~letters
shadow = np.roll(np.roll(dilate(letters, 2), 4, 0), 3, 1) & ~dilate(letters, 2)
logo[shadow] = 15
logo[outline] = 1
ys = np.arange(H)[:, None] * np.ones((1, W), int)
rel = (ys - BY) / max(1, bh - 1)
chrome = np.select([rel < 0.12, rel < 0.26, rel < 0.40, rel < 0.50, rel < 0.53, rel < 0.66, rel < 0.82],
                   [7, 6, 5, 4, 2, 14, 8], 9)
logo[letters] = chrome[letters]
# bright glint streaks along the top edge of each letter
top = letters & ~np.roll(letters, 1, 0)
logo[top & (rel < 0.3)] = 7
# a lower rim line in dark gold right under the letters (inside the outline)
bot = letters & ~np.roll(letters, -1, 0)
logo[bot] = 13

# "SUPER" banner: red ribbon with notched tails, white letters
sm = mask_text(GAME_BANNER, 16, shear=0.0, track=3)
sh, sw = sm.shape
RW = sw + 28; RH = 16
RX, RY = (W - RW) // 2, 5
rib = np.zeros((H, W), bool)
for y in range(RH):
    inset = 0
    rib[RY + y, RX + inset:RX + RW - inset] = True
# notched swallow tails, slightly lower
tail = np.zeros((H, W), bool)
for y in range(RH):
    dn = abs(y - RH // 2)
    tail[RY + 3 + y, RX - 14 + (RH // 2 - dn) // 2 + 0: RX + 2] = True if RY + 3 + y < H else False
    tail[RY + 3 + y, RX + RW - 2: RX + RW + 14 - (RH // 2 - dn) // 2] = True
tail &= ~rib
for m, body, hi, lo in ((tail, 10, 11, 10), (rib, 11, 12, 10)):
    ol = dilate(m, 1) & ~m & ~rib & (logo == 0)
    logo[ol] = 1
    logo[m] = body
    logo[m & ~np.roll(m, 1, 0)] = hi
    logo[m & ~np.roll(m, -1, 0)] = lo
st = place(sm, (W - sw) // 2, RY + (RH - sh) // 2)
logo[dilate(st, 1) & ~st & rib] = 10
logo[st] = 7
logo[st & (ys >= RY + RH // 2 + 2)] = 14
# gold pinstripes framing the banner
for x in range(RX - 30, RX + RW + 30):
    pass

LOGO_ROW0 = 1              # logo occupies map rows 1..9 (lines 8-79: clear of the overscan)
logo_map = [0] * 32
for ty in range(H // 8):
    for tx in range(32):
        t = logo[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]
        i, hf = add(t)
        logo_map.append(mw(i, 3, hf) if i else 0)
n_logo = len(tiles)

# ------------------------------------------------------------------ fonts (5x7 glyphs, same shapes as the game font)
sys.path.insert(0, HERE)
FONT = {}
src = open(os.path.join(HERE, "gen_assets.py")).read()
a = src.index("FONT = {"); b = src.index("}", a)
exec(src[a:b + 1], {}, FONT)
FONT = FONT["FONT"]
FONT.update({
    '(': "00010001000100001000010000010000010", ')': "01000001000001000010000100010001000",
    '<': "00010001000100010000010000010000010", ',': "00000000000000000000001100010001000",
    "'": "00100001000100000000000000000000000",
})
CHARS = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-:/.!>()<,'"
def glyph(ch, bgc, cmap):
    bits = FONT[ch]; g = np.zeros((9, 9), bool)
    for y in range(7):
        for x in range(5):
            if bits[y * 5 + x] == '1': g[y + 1, x + 2] = True
    t = np.full((9, 9), bgc, np.uint8)
    for y in range(9):
        for x in range(9):
            if not g[y, x] and any(0 <= y + dy < 9 and 0 <= x + dx < 9 and g[y + dy, x + dx]
                                   for dy in (-1, 0, 1) for dx in (-1, 0, 1)): t[y, x] = cmap[2]
    for y in range(9):
        for x in range(9):
            if g[y, x]: t[y, x] = cmap[4] if y <= 2 else (cmap[1] if y <= 5 else cmap[5])
    for y in range(8, 0, -1):
        for x in range(8, 0, -1):
            if t[y, x] == bgc and g[y - 1, x - 1]: t[y, x] = cmap[2]
    return t[1:9, 1:9]
# sky font (transparent background, logo palette 3: gold) and panel font (opaque, palettes 4/5/6)
SKY_BASE = len(tiles)
for ch in CHARS:
    tiles.append(glyph(ch, 0, {1: 8, 2: 1, 4: 14, 5: 9}) if ch != ' ' else np.zeros((8, 8), np.uint8))
PANEL_BASE = len(tiles)
for ch in CHARS:
    tiles.append(glyph(ch, 15, {1: 1, 2: 2, 4: 4, 5: 5}) if ch != ' ' else np.full((8, 8), 15, np.uint8))
T_EDGE = len(tiles)                      # panel top edge: gold line
e = np.full((8, 8), 15, np.uint8); e[0, :] = 2; e[1, :] = 3; e[2, :] = 1; e[3, :] = 2
tiles.append(e)
T_SOLID = PANEL_BASE                     # blank opaque panel = panel-font space
assert len(tiles) <= 384, len(tiles)
def ptxt(s):
    return [CHARS.index(c) for c in s]

def to4bpp(t):
    out = bytearray()
    for y in range(8):
        for p in (0, 1):
            out.append(sum(((int(t[y, x]) >> p) & 1) << (7 - x) for x in range(8)))
    for y in range(8):
        for p in (2, 3):
            pass
    # proper interleave: rows of planes 0/1, then rows of planes 2/3
    out = bytearray()
    for y in range(8):
        out.append(sum(((int(t[y, x]) >> 0) & 1) << (7 - x) for x in range(8)))
        out.append(sum(((int(t[y, x]) >> 1) & 1) << (7 - x) for x in range(8)))
    for y in range(8):
        out.append(sum(((int(t[y, x]) >> 2) & 1) << (7 - x) for x in range(8)))
        out.append(sum(((int(t[y, x]) >> 3) & 1) << (7 - x) for x in range(8)))
    return bytes(out)
open(os.path.join(OUT, "title_tiles.bin"), "wb").write(b"".join(to4bpp(t) for t in tiles))

# ------------------------------------------------------------------ cursor jet (OBJ palette 0 = the player jet colours)
CUR = ["................",
       "...111..........",
       "...1751.........",
       "...17551........",
       "...175551.......",
       ".11117555111111.",
       "1981355577777771",
       "998135577cc77771"]
CUR = CUR + CUR[::-1]
cmap = {'.': 0, '1': 1, '3': 3, '5': 5, '7': 7, '8': 8, '9': 9, 'c': 12}
cell = np.zeros((32, 32), np.uint8)
for y, row in enumerate(CUR):
    for x, ch in enumerate(row):
        cell[8 + y, 8 + x] = cmap[ch]
cur = bytearray()
for ty in range(4):
    for tx in range(4):
        cur += to4bpp(cell[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8])
open(os.path.join(OUT, "title_cursor.bin"), "wb").write(cur)

# ------------------------------------------------------------------ HDMA tables
SKY_TOP, SKY_MID, SKY_LOW = hexrgb("#040828"), hexrgb("#2a1e6a"), hexrgb("#f07a3c")
BAND0, BAND1 = 88, 144                   # Mode 7 ocean band (lines 88..143)
def lerp(a, b, f): return tuple(int(round(a[i] + (b[i] - a[i]) * f)) for i in range(3))
grad = []
for y in range(BAND0):
    f = y / (BAND0 - 1)
    c = lerp(SKY_TOP, SKY_MID, f / 0.6) if f < 0.6 else lerp(SKY_MID, SKY_LOW, (f - 0.6) / 0.4)
    grad.append(bgr555(c))
def tbl(name, data):
    s = f"{name}:\n"
    for i in range(0, len(data), 16):
        s += "  .byte " + ",".join(f"${x:02x}" for x in data[i:i + 16]) + "\n"
    return s
cg = [0x80 | BAND0]
for c in grad:
    cg += [0, 0, c & 0xFF, c >> 8]
cg += [0]
md_title = [BAND0, 0x01, BAND1 - BAND0, 0x07, 1, 0x01, 0]
tm_title = [BAND0, 0x02, BAND1 - BAND0, 0x11, 1, 0x12, 0]
md_page = [1, 0x01, 0]
tm_page = [BAND0, 0x02, 1, 0x12, 0]

# ------------------------------------------------------------------ sine table (256 steps, signed 8.8)
sin = [int(round(256 * math.sin(2 * math.pi * i / 256))) & 0xFFFF for i in range(256)]

# ------------------------------------------------------------------ text strings (.byte len, col, then panel-font indices)
TEXT = {
    "TT_PUSH": "PUSH START BUTTON",
    "TT_START": "START GAME", "TT_OPTIONS": "OPTIONS", "TT_CREDITS": "CREDITS",
    "TT_COPY": f"(C) {YEAR} {DEVELOPER}",
    "TT_OPTHEAD": "- OPTIONS -", "TT_CREDHEAD": "- CREDITS -",
    "TT_DIFF": "DIFFICULTY", "TT_SOUND": "SOUND", "TT_MUSIC": "MUSIC TEST", "TT_SFX": "SOUND TEST",
    "TT_EXIT": "EXIT",
    "TT_EASY": "  EASY  ", "TT_NORMAL": " NORMAL ", "TT_HARD": "  HARD  ",
    "TT_STEREO": " STEREO ", "TT_MONO": "  MONO  ",
    "TT_M0": " TITLE  ", "TT_M1": " STAGE  ", "TT_M2": "  BOSS  ", "TT_M3": " CLEAR  ",
    "TT_HINT1": "LEFT/RIGHT:CHANGE  A:PLAY",
    "TT_HINT2": "B:BACK",
    "TT_C1": "GAME DESIGN AND DIRECTION", "TT_C2": f"BY {DEVELOPER}",
    "TT_C3": "DEVELOPED BY", "TT_C4": DEVELOPER,
    "TT_C5": "MUSIC AND SOUND", "TT_C6": "ORIGINAL 16-BIT STEREO SCORE",
    "TT_C7": "THANKS FOR PLAYING!",
}
for k, v in TEXT.items():
    assert len(v) <= 30, (k, v)
SKYTEXT = {"TS_DEV": f"DEVELOPED BY {DEVELOPER}"}

with open(os.path.join(OUT, "title.inc"), "w") as f:
    f.write("; generated by tools/title_art.py -- SUPER SKY FURY title screen\n")
    f.write(f"TITLE_NTILES = {len(tiles)}\nTF_PANEL = {PANEL_BASE}\nTF_SKY = {SKY_BASE}\nT_EDGE = {T_EDGE}\n"
            f"T_SOLID = {T_SOLID}\nCH_LT = {CHARS.index('<')}\nCH_GT = {CHARS.index('>')}\nTB_BAND0 = {BAND0}\nTB_BAND1 = {BAND1}\nLOGO_ROWS = {H // 8 + LOGO_ROW0}\n")
    f.write("TitlePal: .word " + ",".join(f"${bgr555(hexrgb(c)):04X}" for c in PALS) + "\n")
    f.write("TitleLogoMap:\n")
    for i in range(0, len(logo_map), 16):
        f.write("  .word " + ",".join(f"${x:04X}" for x in logo_map[i:i + 16]) + "\n")
    f.write(tbl("cg_title", cg) + tbl("md_title", md_title) + tbl("tm_title", tm_title) +
            tbl("md_page", md_page) + tbl("tm_page", tm_page))
    f.write("TiSin:\n")
    for i in range(0, 256, 16):
        f.write("  .word " + ",".join(f"${x:04X}" for x in sin[i:i + 16]) + "\n")
    for k, v in TEXT.items():
        f.write(f"{k}: .byte {len(v)}," + ",".join(str(x) for x in ptxt(v)) + f"   ; {v}\n")
    for k, v in SKYTEXT.items():
        f.write(f"{k}: .byte {len(v)}," + ",".join(str(x) for x in ptxt(v)) + f"   ; {v}\n")
name = ROM_NAME.upper().ljust(21)[:21]
assert len(name) == 21 and all(32 <= ord(c) < 127 for c in name)
with open(os.path.join(OUT, "romname.inc"), "w") as f:
    f.write(f'; generated by tools/title_art.py\n  .byte "{name}"   ; 21-byte internal ROM name\n')

# preview: logo over the sky gradient, 3x
rgb = np.zeros((H, W, 3), np.uint8)
for y in range(H):
    c = grad[y]; rgb[y, :] = ((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3)
for i in range(1, 16):
    rgb[logo == i] = hexrgb(PAL3[i])
Image.fromarray(rgb).resize((W * 3, H * 3), Image.NEAREST).save(os.path.join(OUT, "title_logo.png"))
print(f"title: {len(tiles)} BG2 tiles (logo {n_logo}), ROM name '{name}'")
