#!/usr/bin/env python3
"""Stereo width metrics for a stereo WAV/raw: L/R correlation, side/mid energy ratio, mono-fold loss."""
import sys, wave, numpy as np
def load(path, rate=None, skip=0.0):
    if path.endswith('.wav'):
        w = wave.open(path); rate = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, 2).astype(float)
    else:
        a = np.fromfile(path, dtype='<i2').reshape(-1, 2).astype(float)
    return a[int(skip * rate):], rate
def metrics(a, rate):
    L, R = a[:, 0], a[:, 1]
    M, S = (L + R) / 2, (L - R) / 2
    corr = (L * R).sum() / np.sqrt((L * L).sum() * (R * R).sum())
    sm = np.sqrt((S * S).mean() / (M * M).mean())
    # mono fold-down loss vs stereo loudness (dB)
    mono_loss = 10 * np.log10((M * M).mean() / ((L * L).mean() + (R * R).mean()) * 2)
    # per-200ms windows: fraction of windows with corr < 0.5
    win = int(0.2 * rate); cs = []
    for i in range(0, len(L) - win, win):
        l, r = L[i:i + win], R[i:i + win]
        d = np.sqrt((l * l).sum() * (r * r).sum())
        if d > 0 and np.sqrt((l*l).mean()) > 200:
            cs.append((l * r).sum() / d)
    cs = np.array(cs)
    peak = np.abs(a).max()
    clip = int((np.abs(a) >= 32767).sum())
    return dict(corr=corr, side_mid=sm, side_mid_db=20 * np.log10(sm), mono_loss_db=mono_loss,
                win_corr_min=cs.min(), win_corr_median=float(np.median(cs)), frac_win_corr_lt_05=float((cs < 0.5).mean()),
                peak=int(peak), peak_dbfs=20 * np.log10(peak / 32768), clipped_samples=clip,
                rms_dbfs=20 * np.log10(np.sqrt((a * a).mean()) / 32768))
if __name__ == '__main__':
    path = sys.argv[1]; rate = int(sys.argv[2]) if len(sys.argv) > 2 else None
    skip = float(sys.argv[3]) if len(sys.argv) > 3 else 0
    a, rate = load(path, rate, skip)
    for k, v in metrics(a, rate).items():
        print(f'  {k:20s} {v:.3f}' if isinstance(v, float) else f'  {k:20s} {v}')
