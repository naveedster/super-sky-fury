#!/usr/bin/env python3
"""SNES FLY boss build: the boss-fight music (original composition in the spirit of a 16-bit
action-game boss theme: ~172 BPM rock beat, palm-muted 16th guitars hard L/R, lockstep slap bass,
minor-key square/saw lead with vibrato, WARNING stinger) + victory jingle + boss-only SFX.

The field image (make_music.build_field) is rebuilt and checked byte-for-byte against build/apu.bin.
The boss image = field image with: a new driver header (track starts, jingle starts, timer 116 =
172 BPM, boss SFX table entries) and a boss region written over the field song (which is not
needed while the boss plays): boss SFX streams, boss sample directory (field samples 0-6 shared +
gtr/gtrm/sqld), the 3 new samples, the boss song and the jingle.

Outputs (music/build/):
  boss_up.bin / boss_up.inc     ranges uploaded (IPL) to turn the field image into the boss image
  field_up.bin / field_up.inc   ranges that restore the field image afterwards
  boss.spc, boss_jingle.spc     for rendering; ../boss.mp3 (song) and ../boss_victory.mp3 (jingle)
"""
import os, sys, struct, math, subprocess, shutil
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_music as mm
from brr import encode

OUT = mm.OUT
ram_f, info = mm.build_field(write=False)
FIELD_END = info['end']
assert bytes(ram_f[mm.IMAGE_ADDR:FIELD_END]) == open(os.path.join(OUT, 'apu.bin'), 'rb').read(), \
    'field image drifted: run make_music.py first'
SR = 32000
BOSS_DIV = 116                      # timer0 8 kHz / 116 = 14.5 ms ticks -> 6 ticks/16th = 172.4 BPM
rng = np.random.default_rng(1993)

# ------------------------------------------------------------------ samples
def cab(f, lo, hi):
    """guitar cab: 2nd-order-ish low-pass at hi, high-pass at lo, presence bump ~2.2 kHz"""
    lp = 1 / (1 + (f / hi) ** 4)
    hp = (f / lo) ** 2 / (1 + (f / lo) ** 2)
    bump = 1 + 0.6 * np.exp(-((f - 2200) / 900) ** 2)
    return lp * hp * bump

def guitar(dark):
    N = 512                         # 2 root periods (125 Hz) = 3 fifth periods = 4 octave periods
    X = np.zeros(N // 2 + 1, complex)
    for h0, amp in ((2, 1.0), (3, 0.85), (4, 0.45)):
        for k in range(1, 60):
            h = h0 * k
            if h > N // 2 - 1:
                break
            X[h] += amp / k * np.exp(1j * rng.uniform(0, 2 * np.pi))
    clean = np.fft.irfft(X, N)
    clean /= np.sqrt((clean ** 2).mean())
    dist = np.tanh(3.2 * clean) + 0.15 * np.tanh(9 * clean)   # two-stage fuzz
    F = np.fft.rfft(dist); f = np.fft.rfftfreq(N, 1 / SR)
    F *= cab(f, 90, 1300 if dark else 3600)
    if dark:
        F[2] *= 1.8                 # palm-mute "chunk": fat fundamental
    loop = np.fft.irfft(F, N)
    att = 1024
    t = np.arange(att) / SR
    body = np.tile(loop, att // N) * (1 + (0.5 if dark else 0.3) * np.exp(-t / 0.012))
    pick = rng.standard_normal(att) * np.exp(-t / (0.002 if dark else 0.004)) * 0.6
    pick = pick - 0.7 * np.concatenate([[0], pick[:-1]])
    y = np.concatenate([body + pick * np.abs(loop).max(), loop])
    return dict(y=mm.norm(y, 0.9), loop=att, f0=SR / 256)

def square_lead():
    N = 64                          # 500 Hz: 25% pulse + saw, band-limited to 31 harmonics
    X = np.zeros(N // 2 + 1, complex)
    for k in range(1, N // 2):
        a = 0.62 * 2 * math.sin(math.pi * k * 0.25) / (math.pi * k) + 0.38 / k
        X[k] = a * np.exp(-1j * math.pi / 2)
    loop = np.fft.irfft(X, N)
    att = 4 * N
    t = np.arange(att) / SR
    y = np.concatenate([np.tile(loop, 4) * (1 + 0.25 * np.exp(-t / 0.003)), loop])
    return dict(y=mm.norm(y, 0.9), loop=att, f0=SR / N)

NEW = {'gtr': guitar(False), 'gtrm': guitar(True), 'sqld': square_lead()}
NEW_ORDER = ['gtr', 'gtrm', 'sqld']
S = dict(info['S']); S.update(NEW)
srcn = dict(info['srcn'])
for i, n in enumerate(NEW_ORDER):
    srcn[n] = 7 + i
    mm.SRC[n] = 7 + i
VOICE_SR = 9000
VOICE_SRCN = 7 + len(NEW_ORDER)                     # 10
mm.SRC['voice'] = VOICE_SRCN
blobs = {}
for n in NEW_ORDER:
    s = NEW[n]
    ls = s['loop']; y = s['y']
    assert ls % 16 == 0 and (len(y) - ls) % 16 == 0
    blobs[n] = (encode(mm.to_i16(y), loop_start=ls), ls // 16 * 9)

# ------------------------------------------------------------------ song settings (module globals of make_music)
mm.TICK_SEC = BOSS_DIV / 8000
mm.SWING_FROM = 10 ** 9            # straight 16ths
V_LEAD, V_HARM, V_GL, V_GR, V_BASS, V_KICK, V_SNARE, V_HAT = range(8)
GL, GR = (110, 4), (4, 110)          # guitars hard left / hard right
mm.PAN.update({V_LEAD: (100, 62), V_HARM: (36, 100), V_GL: GL, V_GR: GR, V_BASS: (112, 112),
               V_KICK: (104, 104), V_SNARE: (100, 108), V_HAT: (44, 100)})
mm.P_DOUBLE = (30, 100)
mm.ADSR.update({
    'gtr':   (0x80 | (3 << 4) | 0xF, (5 << 5) | 0x0C),     # open power chord: rings
    'gtrm':  (0x80 | (6 << 4) | 0xF, (2 << 5) | 0x16),     # palm mute: thump then choke
    'sqld':  (0x80 | (4 << 4) | 0xF, (6 << 5) | 0x08),
    'siren': (0x80 | (2 << 4) | 0xE, (7 << 5) | 0x04),
})
mm.SAMPLE_OF['siren'] = 'sqld'
mm.MVOL = 0x2C
mm.EON_MELODIC = (1 << V_LEAD) | (1 << V_HARM)     # echo on the lead (guitars stay tight and dry)
m = mm.m
Song = mm.Song
g16 = mm.g16

ROOT = {'E': 40, 'F': 41, 'F#': 42, 'G': 43, 'A': 45, 'A#': 46, 'B': 47, 'C': 48, 'C#': 49, 'D': 50, 'D#': 51}

def gtr(song, step, root, kind, ln=1, vel=1.0):
    inst = 'gtrm' if kind == 'M' else 'gtr'
    gate = 4 if kind == 'M' else g16(ln)
    v = vel * (0.82 if kind == 'M' else 1.0)
    song.add(step, V_GL, inst, root, ln, vel=v, gate=gate, pan=GL)
    song.add(step, V_GR, inst, root, ln, vel=v, gate=max(1, gate - 1), pan=GR, detune=+12.0, delay=1)
    # bass in lockstep (E1 octave), accents an octave up = slap pop
    b = root - 12
    if kind == 'M':
        song.add(step, V_BASS, 'bass', b, ln, vel=0.62 * vel, gate=3)
    else:
        song.add(step, V_BASS, 'bass', b, ln, vel=1.0 * vel, gate=g16(ln))

# riffs: (step, kind, len16, semitones over the chord root)
RIFF_A = [(0, 'O', 2, 0), (2, 'M', 1, 0), (3, 'M', 1, 0), (4, 'M', 1, 0), (5, 'M', 1, 0), (6, 'O', 2, 0),
          (8, 'M', 1, 0), (9, 'M', 1, 0), (10, 'O', 2, -2), (12, 'O', 2, 0), (14, 'M', 1, 0), (15, 'M', 1, 0)]
RIFF_A_TURN = [(0, 'O', 2, 0), (2, 'M', 1, 0), (3, 'M', 1, 0), (4, 'O', 2, 0), (6, 'M', 1, 0), (7, 'M', 1, 0),
               (8, 'O', 2, 0), (10, 'O', 2, 1), (12, 'O', 2, 2), (14, 'M', 1, 2), (15, 'M', 1, 2)]
RIFF_A_END = [(0, 'O', 4, 0), (4, 'M', 1, 0), (5, 'M', 1, 0), (6, 'M', 1, 0), (7, 'M', 1, 0),
              (8, 'O', 2, 0), (10, 'O', 2, 0), (12, 'O', 2, 0), (14, 'O', 2, 0)]
RIFF_B = [(0, 'O', 2, 0), (2, 'O', 1, 0), (3, 'M', 1, 0), (4, 'O', 2, 0), (6, 'O', 1, 0), (7, 'M', 1, 0),
          (8, 'O', 2, 0), (10, 'O', 1, 0), (11, 'M', 1, 0), (12, 'O', 2, 0), (14, 'M', 1, 0), (15, 'M', 1, 0)]
RIFF_C = [(s, 'M', 1, 0) for s in range(16)]

def put_riff(song, bar, chords, riffs):
    for bi, ch in enumerate(chords):
        riff = riffs[bi] if isinstance(riffs, list) and isinstance(riffs[0], list) else riffs
        for step, kind, ln, iv in riff:
            vel = 1.0 if kind == 'O' else (0.95 if step % 4 == 0 else 0.8)
            gtr(song, (bar + bi) * 16 + step, ROOT[ch] + iv, kind, ln, vel)

TOMS = [(0x1A00, (120, 24)), (0x1600, (96, 60)), (0x1200, (60, 96)), (0x0F00, (24, 120))]
CRASH_L, CRASH_R = (118, -40), (-40, 118)

def kick(song, st, v=1.0):
    song.add(st, V_KICK, 'kick', None, 1, vel=v, pitch=0x0880)
def snare(song, st, v=1.0):
    song.add(st, V_SNARE, 'snare', None, 1, vel=v, pitch=0x1000)
def hat(song, st, v):
    song.add(st, V_HAT, 'hat', None, 1, vel=v, pitch=0x1000)
def crash(song, st, pan=CRASH_L):
    song.add(st, V_HAT, 'crash', None, 1, vel=1.0, pitch=0x0800, pan=pan)
def ohat(song, st, pan=(44, 100)):
    song.add(st, V_HAT, 'ohat', None, 2, vel=0.85, pitch=0x1000, pan=pan)
def toms(song, st, steps, vel=1.0):
    for i, s in enumerate(steps):
        p, pan = TOMS[min(3, i * 4 // len(steps))]
        song.add(st + s, V_KICK, 'kick', None, 1, vel=vel, pitch=p, pan=pan)

def drums(song, bar, nbars, style, crash_first=True, fill_last=True):
    for b in range(nbars):
        st = (bar + b) * 16
        last = fill_last and b == nbars - 1
        odd = b % 2 == 1
        if style == 'A':
            ks = [0, 3, 6, 8, 10] if not odd else [0, 6, 8, 10, 11, 14]
        elif style == 'B':
            ks = [0, 2, 3, 6, 8, 10, 11, 14]
        else:
            ks = [0, 4, 8, 12]
        for k in ks:
            if last and k >= 8:
                continue
            kick(song, st + k, 1.0 if k % 4 == 0 else 0.85)
        for s in (4, 12):
            if last and s >= 8:
                continue
            snare(song, st + s)
        if style == 'C' and b >= 2:
            for s in range(2, 16, 2):
                if s not in (4, 12) and not (last and s >= 8):
                    snare(song, st + s, 0.45 + 0.04 * s)
        first = crash_first and b == 0
        if first:
            crash(song, st, CRASH_L if (bar // 4) % 2 == 0 else CRASH_R)
        hend = 8 if last else 16
        for s in range(1 if first else 0, hend, 1 if style == 'B' else 2):
            if style == 'A' and odd and s == 14:
                ohat(song, st + s, (110, -30)); continue
            hat(song, st + s, 0.9 if s % 4 == 0 else (0.62 if s % 2 == 0 else 0.4))
        if last:                    # fill: snare 16ths + toms rolling left -> right, crash out
            for s in (8, 9, 10, 11):
                snare(song, st + s, 0.55 + 0.1 * (s - 8))
            toms(song, st, [12, 13, 14, 15])

def melody(song, bar, lines, vel=1.0):
    mm.put_melody(song, bar, lines, voice=V_LEAD, vel=vel, double=True, inst='sqld', vib_min=4)

INTRO_BARS = 4
CH_A = ['E', 'E', 'C', 'D', 'E', 'E', 'C', 'B']
MEL_A = ['E5:3 F#5:3 G5:2 B5:4 A5:2 G5:2', 'F#5:6 E5:2 D5:4 E5:4',
         'C5:3 D5:3 E5:2 G5:4 F#5:2 E5:2', 'D5:6 F#5:2 A5:8',
         'B5:3 A5:3 G5:2 E5:4 G5:2 A5:2', 'B5:6 C6:2 B5:4 A5:4',
         'G5:3 F#5:3 E5:2 D#5:4 E5:2 F#5:2', 'D#5:8 B4:4 r:4']
CH_B = ['A', 'E', 'A', 'B', 'C', 'D', 'B', 'B']
MEL_B = ['A5:4 C6:4 B5:2 A5:2 E5:4', 'G5:4 B5:4 A5:2 G5:2 E5:4',
         'A5:2 B5:2 C6:4 D6:4 C6:2 B5:2', 'B5:12 D#6:4',
         'C6:3 B5:3 A5:2 G5:4 A5:4', 'D6:3 C6:3 B5:2 A5:4 F#5:4',
         'G5:2 A5:2 B5:4 F#5:2 G5:2 D#5:4', 'E5:12 r:4']
CH_C = ['E', 'E', 'C', 'B']
MEL_C = ['B5:12 C6:4', 'B5:16', 'E6:8 D6:8', 'D#6:16']

def stinger(song):
    # bars 0-1: alarm siren (B5 / F5 tritone) sweeping across the stereo field, low E/F drone,
    # heartbeat kicks, snare roll crescendo
    for i in range(4):
        st = i * 8
        note = m('B5') if i % 2 == 0 else m('F5')
        a, b = ((120, 10), (10, 120)) if i % 2 == 0 else ((10, 120), (120, 10))
        auto = mm.sweep_pan(a, b, 46, 2)
        song.add(st, V_LEAD, 'siren', note, 8, vel=0.9, gate=46, pan=a, auto=auto)
        song.add(st, V_HARM, 'siren', note, 8, vel=0.6, gate=45, pan=b, detune=-18.0, delay=1,
                 auto=mm.sweep_pan(b, a, 45, 2))
    for bar, ch in ((0, 'E'), (1, 'F')):
        gtr(song, bar * 16, ROOT[ch], 'O', 16, vel=0.85)
        for s in (0, 4, 8, 12):
            kick(song, bar * 16 + s, 0.9 if s == 0 else 0.7)
    crash(song, 0, CRASH_L); crash(song, 16, CRASH_R)
    for s in range(16):
        snare(song, 16 + s, 0.25 + 0.05 * s)
    # bar 2: unison hits
    for s, ch, ln in ((0, 'E', 3), (3, 'E', 3), (6, 'E', 2), (8, 'G', 2), (10, 'F#', 2), (12, 'F', 2), (14, 'E', 2)):
        gtr(song, 32 + s, ROOT[ch], 'O', ln)
        kick(song, 32 + s)
    crash(song, 32, CRASH_R); snare(song, 32 + 12)
    # bar 3: palm-muted 16ths crescendo, snare 16ths, toms L -> R; lead climbs in
    for s in range(16):
        gtr(song, 48 + s, ROOT['E'], 'M', 1, vel=0.6 + 0.025 * s)
        if s < 12:
            snare(song, 48 + s, 0.35 + 0.05 * s)
        if s % 4 == 0:
            kick(song, 48 + s)
    toms(song, 48, [12, 13, 14, 15])
    melody(song, 3, ['B4:4 E5:4 G5:4 B5:4'], vel=0.85)

def compose_boss():
    song = Song()
    stinger(song)
    b = INTRO_BARS
    # A: gallop riff
    put_riff(song, b, CH_A, [RIFF_A, RIFF_A, RIFF_A, RIFF_A_TURN, RIFF_A, RIFF_A, RIFF_A, RIFF_A_END])
    drums(song, b, 8, 'A'); melody(song, b, MEL_A)
    b += 8
    # B: driving 8ths
    put_riff(song, b, CH_B, [RIFF_B] * 7 + [RIFF_A_END])
    drums(song, b, 8, 'B'); melody(song, b, MEL_B)
    b += 8
    # C: build - all palm-muted 16ths, four on the floor, snare 8ths, screaming lead
    put_riff(song, b, CH_C, RIFF_C)
    drums(song, b, 4, 'C'); melody(song, b, MEL_C)
    b += 4
    return song, INTRO_BARS * mm.BAR_TICKS, b * mm.BAR_TICKS

def compose_jingle():
    song = Song()
    b = 2                           # 2 bars (2.8 s) of silence: the boss explodes
    melody(song, b, ['G#4:2 B4:2 E5:2 G#5:2 B5:8', 'A5:2 F#5:2 A5:2 C#6:2 B5:8', 'E6:16'])
    for s, ch, ln in ((0, 'E', 2), (2, 'E', 2), (4, 'E', 2), (6, 'E', 2), (8, 'E', 8)):
        gtr(song, b * 16 + s, ROOT[ch], 'O', ln)
    for s, ch, ln in ((0, 'A', 2), (2, 'A', 2), (4, 'A', 2), (6, 'A', 2), (8, 'B', 8)):
        gtr(song, (b + 1) * 16 + s, ROOT[ch], 'O', ln)
    gtr(song, (b + 2) * 16, ROOT['E'], 'O', 16)
    for s in range(8):
        snare(song, b * 16 + s, 0.4 + 0.07 * s)
    for bb in range(3):
        kick(song, (b + bb) * 16); kick(song, (b + bb) * 16 + 8)
        crash(song, (b + bb) * 16 + (8 if bb < 2 else 0), CRASH_L if bb % 2 == 0 else CRASH_R)
    toms(song, (b + 1) * 16, [12, 13, 14, 15])
    snare(song, (b + 1) * 16 + 4); snare(song, (b + 1) * 16 + 12)
    end = (b + 4) * mm.BAR_TICKS     # last bar silent: the loop
    return song, (b + 3) * mm.BAR_TICKS, end

# ------------------------------------------------------------------ boss-only SFX (live pan/volume = DYN)
DYN = mm.DYN
Sfx = mm.Sfx
def boss_sfx():
    out = {}
    rr = np.random.default_rng(23)
    # A11 arm cannon: deep boom + crack + short rush
    s = Sfx().src('kick')
    for k in range(3):
        s.step(124, 0x0700 - k * 0x80, DYN, kon=(k == 0))
    s.src('snare')
    for k in range(8):
        s.step(120 * (1 - k / 10), 0x0C00 - k * 0x60, DYN, kon=(k == 0))
    out['bcannon'] = s.end()
    # v1.6 voice line: one key-on at 9 kHz, centre, then hold the channel until the sample has played out
    s = Sfx().src('voice')
    s.step(124, 0x0480, mm.panb(0.0), kon=True)
    s.hold(int(math.ceil(2.45 / (BOSS_DIV / 8000))))
    out['voice'] = s.end()
    # A12 beam charge (telegraph): rising, pulsing square whine, ~1 s
    s = Sfx().src('sqld')
    n = 34
    for k in range(n):
        f = k / (n - 1)
        v = (40 + 84 * f) * (1.0 if k % 2 == 0 else 0.55)
        s.step(v, 0x0300 + 0x2300 * f ** 1.5, DYN, kon=(k == 0)).hold(1)
    out['charge'] = s.end()
    # A13 shard burst: bright crack + crystalline pings
    s = Sfx().src('snare')
    for k in range(4):
        s.step(124 * (1 - k / 5), 0x2400, DYN, kon=(k == 0))
    s.src('sqld')
    for k in range(12):
        s.step(110 * (1 - k / 13), 0x2600 if k % 2 == 0 else 0x1E00 + rr.integers(0, 0x400), DYN, kon=(k == 0 or k == 6))
    out['shards'] = s.end()
    # A14 armour ping (shot bounced off): metallic tick + ringing blip
    s = Sfx().src('snare')
    s.step(110, 0x2000, DYN, kon=True)
    s.src('sqld')
    for k, v in enumerate((100, 70, 52, 36, 24, 14)):
        s.step(v, 0x2700 if k % 2 == 0 else 0x2500, DYN, kon=(k == 0))
    out['ping'] = s.end()
    # A15 weak point hit: crunchy kick+snare and a descending zap
    s = Sfx().src('kick')
    s.step(124, 0x0A00, DYN, kon=True); s.step(124, 0x0900, DYN)
    s.src('snare')
    for k in range(5):
        s.step(124 * (1 - k / 7), 0x1400 - k * 0x100, DYN, kon=(k == 0))
    s.src('sqld')
    for k in range(6):
        s.step(100 * (1 - k / 7), 0x1C00 - k * 0x300, DYN, kon=(k == 0))
    out['weak'] = s.end()
    # B7 engine rumble: low wobbling roar, ~3.5 s (the S-CPU re-triggers it, pan/volume follow the boss)
    s = Sfx().src('whoosh')
    n = 60
    for k in range(n):
        p = 0x0480 + 0x90 * math.sin(2 * math.pi * k / 9)
        v = 104 + 18 * math.sin(2 * math.pi * k / 5)
        s.step(v, p, DYN, kon=(k == 0)).hold(3)
    out['rumble'] = s.end()
    # B8 chest beam: kick + harsh fluttering roar, ~1.2 s
    s = Sfx().src('kick')
    s.step(124, 0x0600, DYN, kon=True); s.step(124, 0x0500, DYN)
    s.src('whoosh')
    for k in range(40):
        f = k / 39
        v = 124 * (1.0 if k % 2 == 0 else 0.72) * (1 - 0.5 * f)
        s.step(v, 0x1700 + (0x300 if k % 2 else -0x200) - 0x600 * f, DYN, kon=(k == 0)).hold(1)
    out['beam'] = s.end()
    # B9 shard whizzing past: bright fast-falling crackle (Doppler drop behind you)
    s = Sfx().src('whoosh')
    n = 12
    for k in range(n):
        f = k / (n - 1)
        env = min(1.0, (k + 1) / 2) * (1 - f) ** 0.8 * (1.0 if k % 2 == 0 else 0.7)
        s.step(124 * env, 0x2700 - 0x1600 * f, DYN, kon=(k == 0))
    out['shardw'] = s.end()
    # B10 boss explosion: huge boom, crack, long tearing rumble
    s = Sfx().src('kick')
    for k in range(8):
        s.step(124, 0x0480 - k * 0x40, DYN, kon=(k == 0))
    s.src('snare')
    for k in range(10):
        s.step(124 * (1 - k / 14), 0x0580 - k * 0x30, DYN, kon=(k == 0))
    s.src('whoosh')
    n = 70
    for k in range(n):
        f = k / n
        v = 124 * (1 - f) ** 1.1 * (0.55 + 0.45 * rr.random())
        s.step(v, 0x0900 - 0x0600 * f, DYN, kon=(k == 0))
    out['megaboom'] = s.end()
    # B11 missile volley launch: thump + rising rush
    s = Sfx().src('kick')
    s.step(124, 0x0800, DYN, kon=True)
    s.src('whoosh')
    for k in range(18):
        f = k / 17
        s.step(124 * min(1.0, 0.5 + k / 4) * (1 - 0.6 * f), 0x0800 + 0x1A00 * f, DYN, kon=(k == 0)).hold(1)
    out['bmsl'] = s.end()
    return out


# ------------------------------------------------------------------ title theme (original): "Sky Fury Overture"
# D major/mixolydian fanfare at 150 BPM: a 2-bar unison-hit intro (crashes L/R, snare roll, toms
# rolling across), then a heroic 8-bar melody over driving 8ths and a 4-bar climb, looped.
TITLE_DIV = 133                      # 8 kHz / 133 -> 6 ticks/16th = 150.4 BPM
CH_T = ['D', 'D', 'A#', 'C', 'D', 'D', 'A#', 'A']
MEL_T = ['D5:2 F#5:2 A5:4 D6:4 C#6:2 A5:2', 'B5:4 A5:4 F#5:2 E5:2 F#5:4',
         'F5:2 A#5:2 D6:4 C6:2 A#5:2 A5:4', 'G5:4 A5:4 C6:4 E6:4',
         'D6:4 C#6:2 D6:2 A5:4 F#5:4', 'G5:2 F#5:2 E5:2 F#5:2 A5:8',
         'A#5:4 A5:4 G5:4 F5:4', 'E5:4 G5:4 A5:8']
CH_U = ['G', 'A', 'B', 'A']
MEL_U = ['B5:4 D6:4 G6:4 F#6:2 E6:2', 'C#6:4 E6:4 A6:8',
         'B5:2 C#6:2 D6:4 F#6:4 E6:2 D6:2', 'C#6:8 E6:4 r:4']
CH_V = ['A#', 'C', 'D', 'D']
MEL_V = ['D6:6 F6:6 D6:4', 'E6:6 G6:6 E6:4', 'F#6:16', 'A6:8 F#6:4 E6:4']
T_INTRO = 2

def compose_title():
    song = Song()
    # bar 0: "da da-da DAAA" unison hits, crash left; bar 1: Bb - C - D climb, crash right, snare roll, toms L->R
    for s, ch, ln in ((0, 'D', 3), (3, 'D', 3), (6, 'D', 2), (8, 'C', 2), (10, 'D', 6)):
        gtr(song, s, ROOT[ch], 'O', ln); kick(song, s)
    crash(song, 0, CRASH_L); crash(song, 10, CRASH_R)
    for s, ch, ln in ((0, 'A#', 4), (4, 'C', 4), (8, 'D', 8)):
        gtr(song, 16 + s, ROOT[ch], 'O', ln); kick(song, 16 + s)
    crash(song, 16, CRASH_L)
    for s in range(12):
        snare(song, 16 + s, 0.3 + 0.05 * s)
    toms(song, 16, [12, 13, 14, 15])
    melody(song, 0, ['D5:3 D5:3 D5:2 C5:2 D5:6', 'A#4:4 C5:4 D5:8'], vel=0.9)
    b = T_INTRO
    put_riff(song, b, CH_T, [RIFF_B] * 7 + [RIFF_A_END])
    drums(song, b, 8, 'B'); melody(song, b, MEL_T)
    b += 8
    put_riff(song, b, CH_U, [RIFF_A, RIFF_A, RIFF_A_TURN, RIFF_A_END])
    drums(song, b, 4, 'A'); melody(song, b, MEL_U)
    b += 4
    put_riff(song, b, CH_V, RIFF_C)
    drums(song, b, 4, 'C'); melody(song, b, MEL_V)
    b += 4
    return song, T_INTRO * mm.BAR_TICKS, b * mm.BAR_TICKS

def title_sfx():
    """menu SFX (fixed pan, panned hard so the cursor 'moves' between the ears)"""
    out = {}
    lr = mm.lr_to_vp
    for name, side in (('menu_l', -1), ('menu_r', 1)):
        s = Sfx().src('sqld')
        for k, (a, p) in enumerate(((112, 0x2400), (96, 0x3000), (60, 0x3000), (34, 0x3000), (16, 0x3000))):
            l, r = (a, a * 0.12) if side < 0 else (a * 0.12, a)
            v, pn = lr(l, r)
            s.step(v, p, pn, kon=(k < 2))
        out[name] = s.end()
    # select: two-tone rising chirp sweeping left -> right, then a sparkle
    s = Sfx().src('sqld')
    seq = [(0x1800, 0.0), (0x1800, 0.1), (0x2000, 0.3), (0x2000, 0.4), (0x3000, 0.6), (0x3000, 0.7),
           (0x3000, 0.8), (0x3000, 0.9), (0x3000, 1.0), (0x3000, 1.0), (0x3000, 1.0)]
    for k, (p, f) in enumerate(seq):
        a = 116 * (1.0 if k < 8 else (11 - k) / 4)
        v, pn = lr(a * math.cos(f * math.pi / 2), a * math.sin(f * math.pi / 2))
        s.step(v, p, pn, kon=(k in (0, 2, 4)))
    out['menu_ok'] = s.end()
    return out

# ------------------------------------------------------------------ build the boss image
ram_b = bytearray(ram_f)
R0 = info['song_addr']
addr = R0
sfx_bytes = boss_sfx()
ext = {}
for name in list(mm.SFX_A_BOSS.values()) + list(mm.SFX_B_BOSS.values()):
    b = sfx_bytes[name]
    ext[name] = addr
    ram_b[addr:addr + len(b)] = b
    addr += len(b)
sfx_total = addr - R0
BDIR = (addr + 0xFF) & ~0xFF
nent = 7 + len(NEW_ORDER) + 1          # v1.6: + the voice line (entry 10)
ram_b[BDIR:BDIR + 28] = ram_f[mm.DIR_ADDR:mm.DIR_ADDR + 28]
addr = BDIR + 4 * nent
for i, n in enumerate(NEW_ORDER):
    data, loff = blobs[n]
    struct.pack_into('<HH', ram_b, BDIR + 4 * (7 + i), addr, addr + loff)
    ram_b[addr:addr + len(data)] = data
    print(f'  boss sample {7 + i} {n:5s} ${addr:04X} {len(data)} bytes')
    addr += len(data)
mm.DIR_ADDR = BDIR
song, loop_tick, end_tick = compose_boss()
song_addr = addr
blob, starts = mm.compile_song(song, loop_tick, end_tick, S, srcn, song_addr)
ram_b[song_addr:song_addr + len(blob)] = blob
addr += len(blob)
# jingle: no init block (just key everything off), straight into its bars
real_init = mm.init_stream
mm.init_stream = lambda: (bytes((0x5C, 0xFF)), 1)
jsong, jloop, jend = compose_jingle()
jaddr = addr
jblob, jstarts = mm.compile_song(jsong, jloop, jend, S, srcn, jaddr)
mm.init_stream = real_init
ram_b[jaddr:jaddr + len(jblob)] = jblob
BOSS_END = jaddr + len(jblob)
# v1.6: the Stage 1 boss's voice line ("Naveed! I will destroy you!"): 9 kHz one-shot BRR, sample 10,
# played on SFX channel B (id 12) at pitch $0480 (9000 / 32000 * $1000); see tools/dad/make_voice.sh
import wave as _wave
_w = _wave.open(os.path.join(HERE, 'dad_voice.wav'))
assert _w.getframerate() == VOICE_SR and _w.getnchannels() == 1
_vx = np.frombuffer(_w.readframes(_w.getnframes()), np.int16).astype(np.int32)
_vx = np.concatenate([_vx, np.zeros((-len(_vx)) % 16 + 16, np.int32)])
_vx = (_vx * 0.92).astype(np.int32)                 # BRR headroom
vblob = encode(_vx)
VOICE_ADDR = BOSS_END
struct.pack_into('<HH', ram_b, BDIR + 4 * VOICE_SRCN, VOICE_ADDR, VOICE_ADDR)
ram_b[VOICE_ADDR:VOICE_ADDR + len(vblob)] = vblob
BOSS_END = VOICE_ADDR + len(vblob)
print(f'  voice sample {VOICE_SRCN} ${VOICE_ADDR:04X} {len(vblob)} bytes ({len(_vx) / VOICE_SR:.2f} s at {VOICE_SR} Hz); '
      f'{mm.ECHO_ADDR - BOSS_END} bytes left before the echo buffer')
assert BOSS_END <= mm.ECHO_ADDR
secs, _ = mm.assemble_driver(starts, info['sfx_addr'], jstarts, timer_div=BOSS_DIV, external=ext)
(o1, drv), (o2, sfxc) = secs
assert len(drv) == info['main_len'] and len(sfxc) == info['sfx_len']
ram_b[mm.DRIVER_ADDR:mm.DRIVER_ADDR + len(drv)] = drv
ram_b[info['sfx_addr']:info['sfx_addr'] + len(sfxc)] = sfxc
print(f'  boss region ${R0:04X}-${BOSS_END:04X} ({BOSS_END - R0} bytes): sfx {sfx_total}, dir ${BDIR:04X}, '
      f'song ${song_addr:04X} {len(blob)} B, jingle ${jaddr:04X} {len(jblob)} B; '
      f'loop {(end_tick - loop_tick) * mm.TICK_SEC:.1f}s intro {loop_tick * mm.TICK_SEC:.1f}s')

# ------------------------------------------------------------------ build the title image
# = the boss image (same boss SFX/dir/samples) + menu SFX streams, the title song at song_addr, own tempo
ram_t = bytearray(ram_b)
tsfx = title_sfx()
text = dict(ext)
taddr = song_addr
for name in mm.SFX_B_TITLE.values():
    b = tsfx[name]
    text[name] = taddr
    ram_t[taddr:taddr + len(b)] = b
    taddr += len(b)
tsong, tloop, tend = compose_title()
tsong_addr = taddr
tblob, tstarts = mm.compile_song(tsong, tloop, tend, S, srcn, tsong_addr)
ram_t[tsong_addr:tsong_addr + len(tblob)] = tblob
TITLE_END = tsong_addr + len(tblob)
assert TITLE_END <= mm.ECHO_ADDR
secs, _ = mm.assemble_driver(tstarts, info['sfx_addr'], tstarts, timer_div=TITLE_DIV, external=text)
(o1, tdrv), (o2, tsfxc) = secs
assert len(tdrv) == info['main_len'] and len(tsfxc) == info['sfx_len']
ram_t[mm.DRIVER_ADDR:mm.DRIVER_ADDR + len(tdrv)] = tdrv
ram_t[info['sfx_addr']:info['sfx_addr'] + len(tsfxc)] = tsfxc
TT = TITLE_DIV / 8000
print(f'  title image: menu sfx {tsong_addr - song_addr} B, song ${tsong_addr:04X} {len(tblob)} B, end ${TITLE_END:04X}; '
      f'intro {tloop * TT:.1f}s loop {(tend - tloop) * TT:.1f}s')

# ------------------------------------------------------------------ upload ranges
def ranges(a, b, lo, hi, gap=24, c=None):
    c = c if c is not None else b
    def d(k):
        return a[k] != b[k] or a[k] != c[k]
    out = []; i = lo
    while i < hi:
        if d(i):
            j = i; last = i
            while j < hi and j - last <= gap:
                if d(j):
                    last = j
                j += 1
            out.append((i, last + 1)); i = last + 1
        else:
            i += 1
    return out
hi = max(FIELD_END, BOSS_END, TITLE_END)
rg = ranges(ram_f, ram_b, mm.IMAGE_ADDR, hi, c=ram_t)   # union: any image can replace any other
def write_up(name, ram, label):
    data = bytearray(); tab = []
    for a0, a1 in rg:
        tab.append((a0, a1 - a0, len(data))); data += ram[a0:a1]
    open(os.path.join(OUT, name + '.bin'), 'wb').write(data)
    with open(os.path.join(OUT, name + '.inc'), 'w') as f:
        f.write(f'; generated by music/make_boss.py: {len(tab)} ARAM ranges, {len(data)} bytes\n')
        f.write(f'{label}_N = {len(tab)}\n{label}_SIZE = {len(data)}\n')
        f.write(f'{label}_Dst: .word ' + ','.join(f'${t[0]:04X}' for t in tab) + '\n')
        f.write(f'{label}_Len: .word ' + ','.join(f'${t[1]:04X}' for t in tab) + '\n')
        f.write(f'{label}_Off: .word ' + ','.join(f'${t[2]:04X}' for t in tab) + '\n')
    return len(data)
nb = write_up('boss_up', ram_b, 'BossUp')
nf = write_up('field_up', ram_f, 'FieldUp')
nt = write_up('title_up', ram_t, 'TitleUp')
print(f'  upload: {len(rg)} ranges, {nb} bytes per image swap: ' +
      ', '.join(f'${a:04X}-${b - 1:04X}' for a, b in rg))
with open(os.path.join(OUT, 'boss_music.inc'), 'w') as f:
    f.write('; generated by music/make_boss.py\n')
    f.write(f'APU_DRIVER = ${mm.DRIVER_ADDR:04X}\n')
    for i, n in mm.SFX_A_BOSS.items():
        f.write(f'SFXA_{n.upper()} = {i}\n')
    for i, n in mm.SFX_B_BOSS.items():
        f.write(f'SFXB_{n.upper()} = {i}\n')
    for i, n in mm.SFX_B_TITLE.items():
        f.write(f'SFXB_{n.upper()} = {i}\n')
    f.write('APU_MONO = $004F               ; driver flag: 0 = stereo, 1 = mono (sent after every image upload)\n')

# ------------------------------------------------------------------ renders
mm.write_spc(os.path.join(OUT, 'boss.spc'), ram_b, None, 'SUPER SKY FURY - Boss')
jram = bytearray(ram_b)   # render-only copy: the jingle with a full init block (in the game the boss song did it)
jsong, jloop, jend = compose_jingle()
jb2, js2 = mm.compile_song(jsong, jloop, jend, S, srcn, jaddr)
jram[jaddr:jaddr + len(jb2)] = jb2
secs, _ = mm.assemble_driver(js2, info['sfx_addr'], js2, timer_div=BOSS_DIV, external=ext)
jram[mm.DRIVER_ADDR:mm.DRIVER_ADDR + len(secs[0][1])] = secs[0][1]
mm.write_spc(os.path.join(OUT, 'boss_jingle.spc'), jram, None, 'SUPER SKY FURY - Mission Clear')
mm.write_spc(os.path.join(OUT, 'title.spc'), ram_t, None, 'SUPER SKY FURY - Title')
if '--render' in sys.argv:
    tot = loop_tick * mm.TICK_SEC + 2 * (end_tick - loop_tick) * mm.TICK_SEC
    subprocess.run([sys.executable, os.path.join(HERE, 'render_spc.py'), os.path.join(OUT, 'boss.spc'),
                    '/tmp/boss.wav', f'{tot + 3:.1f}'], check=True)
    subprocess.run([sys.executable, os.path.join(HERE, 'render_spc.py'), os.path.join(OUT, 'boss_jingle.spc'),
                    '/tmp/boss_jingle.wav', '8.5'], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', '/tmp/boss.wav', '-af',
                    f'afade=t=out:st={tot:.1f}:d=3', '-c:a', 'libmp3lame', '-b:a', '224k',
                    os.path.join(HERE, 'boss.mp3')], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '2.0', '-i', '/tmp/boss_jingle.wav',
                    '-c:a', 'libmp3lame', '-b:a', '224k', os.path.join(HERE, 'boss_victory.mp3')], check=True)
    print('  rendered music/boss.mp3, music/boss_victory.mp3')
if '--render' in sys.argv or '--render-title' in sys.argv:
    tt = tloop * TT + 2 * (tend - tloop) * TT
    subprocess.run([sys.executable, os.path.join(HERE, 'render_spc.py'), os.path.join(OUT, 'title.spc'),
                    '/tmp/title.wav', f'{tt + 3:.1f}'], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', '/tmp/title.wav', '-af',
                    f'afade=t=out:st={tt:.1f}:d=3', '-c:a', 'libmp3lame', '-b:a', '224k',
                    os.path.join(HERE, 'title.mp3')], check=True)
    print('  rendered music/title.mp3')
