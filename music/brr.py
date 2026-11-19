"""BRR encoder/decoder matching the S-DSP decode exactly (blargg snes_spc rules)."""
import numpy as np

def _clamp16(v):
    return -32768 if v < -32768 else (32767 if v > 32767 else v)

def _s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v

def decode_sample(n, shift, filt, p1, p2raw):
    """n: nibble -8..7, p1/p2raw: previous two outputs. returns output (doubled 15-bit)."""
    s = (n << shift) >> 1
    if shift >= 13:
        s = -2048 if n < 0 else 0
    p2 = p2raw >> 1
    if filt == 1:
        s += p1 >> 1
        s += (-p1) >> 5
    elif filt == 2:
        s += p1; s -= p2; s += p2 >> 4; s += (p1 * -3) >> 6
    elif filt == 3:
        s += p1; s -= p2; s += (p1 * -13) >> 7; s += (p2 * 3) >> 4
    s = _clamp16(s)
    return _s16(s * 2)

def encode(x, loop_start=None, force_filter0_blocks=()):
    """x: int array, len multiple of 16. loop_start: sample index (multiple of 16) or None (one-shot).
    Returns bytes."""
    x = [int(v) for v in x]
    assert len(x) % 16 == 0
    nb = len(x) // 16
    out = bytearray()
    p1 = p2 = 0
    for b in range(nb):
        t = x[b*16:(b+1)*16]
        filters = (0,) if (b == 0 or (loop_start is not None and b*16 == loop_start) or b in force_filter0_blocks) else (0, 1, 2, 3)
        best = None
        for f in filters:
            for sh in range(0, 13):
                q1, q2 = p1, p2
                err = 0; nibs = []
                for v in t:
                    # predicted part with n = 0
                    base = decode_sample(0, sh, f, q1, q2)
                    # step per nibble unit approx (1<<sh)
                    step = (1 << sh)
                    n0 = int(round((v - base) / step)) if step else 0
                    bn = None; be = None; bo = None
                    for n in (n0 - 1, n0, n0 + 1):
                        if n < -8 or n > 7:
                            continue
                        o = decode_sample(n, sh, f, q1, q2)
                        e = (o - v) ** 2
                        if be is None or e < be:
                            bn, be, bo = n, e, o
                    if bn is None:
                        n = -8 if n0 < -8 else 7
                        bo = decode_sample(n, sh, f, q1, q2); be = (bo - v) ** 2; bn = n
                    err += be
                    if best is not None and err >= best[0]:
                        break
                    nibs.append(bn); q2 = q1; q1 = bo
                else:
                    if best is None or err < best[0]:
                        best = (err, f, sh, nibs, q1, q2)
        err, f, sh, nibs, p1, p2 = best
        hdr = (sh << 4) | (f << 2)
        if b == nb - 1:
            hdr |= 1
            if loop_start is not None:
                hdr |= 2
        out.append(hdr)
        for i in range(0, 16, 2):
            out.append(((nibs[i] & 15) << 4) | (nibs[i+1] & 15))
    return bytes(out)
