"""v1.2 tumbling small objects: which voxel model, palette ramps and motion each streamed 16x16 frame set uses."""
import math
import numpy as np
import voxstack as vs

# name -> (palette, ramps); motion in tumble_frames
TUMBLE = {
    "DEB0": ("frame", {"metal": [2, 3, 4, 5, 12, 13], "paint": [8, 9, 10, 11], "hot": [7, 6, 14]}),
    "DEB1": ("frame", {"metal": [2, 3, 4, 5, 12, 13], "paint": [8, 9, 10, 11], "hot": [7, 6, 14]}),
    "MSL":  ("jet", {"body": [3, 4, 5, 6, 7, 13], "fin": [2, 3, 4, 5], "nose": [15], "glow": [8, 9, 14, 14], "band": [15, 15, 8]}),
    "EMSL": ("jet", {"body": [3, 4, 5, 6, 7, 13], "fin": [2, 3, 4, 5], "nose": [15, 15, 8], "glow": [8, 9, 14], "band": [15, 15, 8]}),
    "PU_P": ("hud", {"shell": [5, 9, 9, 9, 6], "band": [8, 5, 9], "letter": [6]}),
    "PU_M": ("hud", {"shell": [8, 4, 4, 4, 6], "band": [8, 8, 4], "letter": [6]}),
    "PU_S": ("hud", {"shell": [3, 2, 1, 1, 7], "band": [8, 3, 2], "letter": [6]}),
    "BSHARD": ("boss", {"white": [5, 6, 7, 8, 9], "blue": [10, 11, 12]}),
}
NTF = 8
MODEL = {"DEB0": "deb0", "DEB1": "deb1", "MSL": "msl", "EMSL": "emsl", "PU_P": "puP", "PU_M": "puM", "PU_S": "puS",
         "BSHARD": "shard"}
OUTL = {"frame": 1, "jet": 1, "hud": 8, "boss": 1}

def tumble_frames(models, name):
    pal, ramps = TUMBLE[name]
    v = models[MODEL[name]]
    out = []
    for k in range(NTF):
        a = 360.0 * k / NTF
        if name.startswith("DEB"):
            tm = [("x", a), ("z", a * 0.5 + 20), ("y", 30)]          # tumbling end over end
        elif name in ("MSL", "EMSL"):
            tm = [("y", a / 4)]                                      # roll (4-fold fins: 90 deg cycle)
        elif name.startswith("PU"):
            tm = [("z", 38 * math.sin(2 * math.pi * k / NTF)), ("x", 10 * math.cos(2 * math.pi * k / NTF))]
        else:
            tm = [("x", a), ("y", 25), ("z", a * 0.25)]
        sc = {"DEB0": 1.25, "DEB1": 1.15, "MSL": 1.6, "EMSL": 1.6, "BSHARD": 1.35}.get(name, 1.0)
        g = vs.render(v, ramps, "chase", tumble=tm, pitch_cam=-8, size=16, scale=sc, ss=4, outline=OUTL[pal],
                      light=(-0.5, 0.6, 0.62), ambient=0.25, gamma=1.4, dither=False, flat_top=0.0)
        if name.startswith("PU"):
            # the letter: printed on the turning shell (squeezed by the turn), white with a dark under-edge
            F = vs.LETTERS[name[-1]]; w = len(F[0]); yaw = 38 * math.sin(2 * math.pi * k / NTF)
            c = math.cos(math.radians(yaw)); dx = -math.sin(math.radians(yaw)) * 2.0
            for y_, row in enumerate(F):
                for x_, ch in enumerate(row):
                    if ch != "1": continue
                    px = int(round(8 + dx - w / 2 + x_)); py = 6 + y_
                    if g[py, px] not in (0, 8):
                        g[py, px] = 6
                        if py + 1 < 16 and g[py + 1, px] not in (0, 6, 8): g[py + 1, px] = 8
        out.append(g)
    return out
