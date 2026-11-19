#!/usr/bin/env python3
"""Render an .spc through libgme (blargg's cycle-accurate SPC700 + S-DSP emulator) to WAV."""
import ctypes, sys, wave, numpy as np
spc, out, secs = sys.argv[1], sys.argv[2], float(sys.argv[3])
mute = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0
gme = ctypes.CDLL('libgme.so.0')
emu = ctypes.c_void_p()
err = gme.gme_open_file(spc.encode(), ctypes.byref(emu), 32000)
assert not err, ctypes.c_char_p(err).value
gme.gme_ignore_silence(emu, 1)
gme.gme_start_track(emu, 0)
gme.gme_mute_voices(emu, mute)
n = int(secs * 32000) * 2
buf = (ctypes.c_short * n)()
gme.gme_play(emu, n, buf)
a = np.frombuffer(buf, dtype=np.int16)
print('peak', np.abs(a).max(), 'rms', int(np.sqrt((a.astype(float) ** 2).mean())))
with wave.open(out, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(32000); w.writeframes(a.tobytes())
