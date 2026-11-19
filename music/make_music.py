#!/usr/bin/env python3
"""SNES FLY music, draft 4 (full-length piece, multi-track driver with bar calls): "Afterburner Squadron" (original) -- wide stereo + funk rhythm section.
Builds:  music/build/apu.bin   (ARAM image from $0200: driver + sample dir + BRR samples + song stream)
         music/build/apu_blocks.inc (ca65 include describing upload blocks)
         music/draft1.spc       (SPC file for players / preview rendering)
Driver: a tiny custom SPC700 player that streams pre-compiled DSP register writes
with tick waits (1 tick = 1/64 note at 150 BPM = 25 ms, timer 0).
"""
import os, sys, math, struct
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from brr import encode

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'build'); os.makedirs(OUT, exist_ok=True)
SR = 32000
rng = np.random.default_rng(1991)

BPM = 156.25
TICKS_PER_16TH = 6
TICK_SEC = 60.0 / BPM / 4 / TICKS_PER_16TH   # 1/96 note = 16 ms
TIMER_DIV = round(8000 * TICK_SEC)    # timer0 runs at 8 kHz -> 128

# ---------------------------------------------------------------- samples
def additive(period, n_total, amps_fn, phases=None):
    """Periodic additive synthesis; amps_fn(t_seconds_array) -> (K, N) harmonic amps."""
    n = np.arange(n_total)
    t = n / SR
    A = amps_fn(t)
    K = A.shape[0]
    if phases is None:
        phases = np.zeros(K)
    y = np.zeros(n_total)
    for k in range(1, K + 1):
        y += A[k-1] * np.sin(2 * np.pi * k * n / period + phases[k-1])
    return y

def brassy(period, attack_len, bright_peak, bright_sus, kmax, blat=0.012, settle=0.12, square_mix=0.0):
    loop_len = period * max(1, 64 // period)  # >= 64 samples, multiple of 16
    n_total = attack_len + loop_len
    ks = np.arange(1, kmax + 1)[:, None]
    def amps(t):
        tt = np.minimum(t, attack_len / SR)  # loop region = steady state
        # cutoff (in harmonics): rises fast (blat) then settles
        rise = np.clip(tt / blat, 0, 1)
        fall = np.exp(-np.maximum(tt - blat, 0) / settle)
        cut = 1.5 + (bright_peak - 1.5) * rise
        cut = np.where(tt > blat, bright_sus + (bright_peak - bright_sus) * fall, cut)
        saw = 1.0 / ks
        odd = np.where(ks % 2 == 1, 1.0 / ks, 0)
        base = (1 - square_mix) * saw + square_mix * odd
        lp = 1.0 / (1.0 + (ks / cut[None, :]) ** 4)
        env = np.clip(tt / 0.004, 0, 1)  # tiny fade-in at the very start
        return base * lp * env[None, :]
    y = additive(period, n_total, amps)
    return y, attack_len

def norm(y, peak=0.92):
    return y / np.max(np.abs(y)) * peak

def to_i16(y):
    return np.clip(np.round(y * 32000), -32000, 32000).astype(int)

def pad16(y):
    r = (-len(y)) % 16
    return np.concatenate([y, np.zeros(r)])

def make_samples():
    S = {}
    # Lead: bright synth-brass, period 32 (native 1000 Hz)
    y, ls = brassy(32, 3200, bright_peak=14, bright_sus=7, kmax=15, settle=0.08, square_mix=0.25)
    S['lead'] = dict(y=norm(y), loop=ls, f0=SR / 32)
    # Stab brass: punchy blat, period 64 (500 Hz)
    y, ls = brassy(64, 4096, bright_peak=22, bright_sus=6, kmax=30, blat=0.008, settle=0.06)
    S['brass'] = dict(y=norm(y), loop=ls, f0=SR / 64)
    # Slap bass: period 128 (250 Hz). Bright pluck whose high harmonics decay fast.
    period = 128; att = 4096
    ks = np.arange(1, 41)[:, None]
    def bass_amps(t):
        tt = np.minimum(t, att / SR)[None, :]
        base = 1.0 / ks ** 1.1
        decay = np.exp(-tt * (4 + ks ** 1.6 * 2.2))
        sus = np.where(ks <= 4, 0.55, 0.06 / ks)
        body = base * (sus + (1 - sus) * decay)
        body[1] *= 1.3  # strong 2nd harmonic = "thumb" punch
        return body
    y = additive(period, att + period, bass_amps, phases=np.zeros(40))
    # slap click: short filtered noise burst
    click = rng.standard_normal(200) * np.exp(-np.arange(200) / 35) * 0.25
    y[:200] += click
    S['bass'] = dict(y=norm(y), loop=att, f0=SR / period)
    # Kick (stored at 16 kHz, played at P=$0800)
    sr = 16000; n = int(0.30 * sr); t = np.arange(n) / sr
    f = 45 + 140 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / sr
    y = np.sin(ph) * np.exp(-t / 0.13)
    y[:40] += rng.standard_normal(40) * np.exp(-np.arange(40) / 8) * 0.6
    y = np.tanh(y * 1.6)
    S['kick'] = dict(y=norm(y * np.minimum(1, (n - np.arange(n)) / 200)), loop=None, f0=None, rate=sr)
    # Snare (32 kHz): tone body + bright noise
    n = int(0.24 * SR); t = np.arange(n) / SR
    tone = (np.sin(2*np.pi*185*t) + 0.5*np.sin(2*np.pi*330*t)) * np.exp(-t / 0.045)
    nz = rng.standard_normal(n)
    nz = nz - 0.6 * np.concatenate([[0], nz[:-1]])  # brighten
    nz *= np.exp(-t / 0.07)
    y = 0.8 * tone + 0.75 * nz
    y = np.tanh(y * 1.3)
    S['snare'] = dict(y=norm(y * np.minimum(1, (n - np.arange(n)) / 300)), loop=None, f0=None, rate=SR)
    # Closed hat (32 kHz)
    n = int(0.05 * SR); t = np.arange(n) / SR
    nz = rng.standard_normal(n); nz = np.diff(np.concatenate([[0], nz]))
    y = nz * np.exp(-t / 0.012)
    S['hat'] = dict(y=norm(y, 0.8), loop=None, f0=None, rate=SR)
    # Open hat (32 kHz)
    n = int(0.22 * SR); t = np.arange(n) / SR
    nz = rng.standard_normal(n); nz = np.diff(np.concatenate([[0], nz]))
    y = nz * np.exp(-t / 0.07) * np.minimum(1, (n - np.arange(n)) / 300)
    S['ohat'] = dict(y=norm(y, 0.8), loop=None, f0=None, rate=SR)
    # Crash (16 kHz, played at P=$0800)
    sr = 16000; n = int(0.78 * sr); t = np.arange(n) / sr
    nz = rng.standard_normal(n); nz = nz - 0.85 * np.concatenate([[0], nz[:-1]])
    shimmer = 1 + 0.3 * np.sin(2 * np.pi * 7 * t)
    y = nz * (np.exp(-t / 0.35) * 0.85 + 0.15 * np.exp(-t / 0.02)) * shimmer
    y *= np.minimum(1, (n - np.arange(n)) / 2500)
    S['crash'] = dict(y=norm(y, 0.85), loop=None, f0=None, rate=sr)
    # Whoosh / jet flyby: looped band-limited noise (pitch-swept + panned by the stream).
    # 2560 samples (was 4096) to make room for the combat SFX; only SFX use it (crash/open hat = DSP noise).
    n = 2560
    nz = rng.standard_normal(n)
    F = np.fft.rfft(nz); f = np.fft.rfftfreq(n, 1 / SR)
    shape = (1 / np.sqrt(1 + (f / 2200) ** 4)) * (f / np.sqrt(f ** 2 + 180 ** 2)) / np.sqrt(np.maximum(f, 60) / 400)
    y = np.fft.irfft(F * shape, n)          # circular -> loops seamlessly
    y = np.tanh(2.2 * y / np.abs(y).max())     # denser noise = louder rush at the same peak
    S['whoosh'] = dict(y=norm(y, 0.9), loop=0, f0=None, rate=SR)
    return S

SAMPLE_ORDER = ['lead', 'brass', 'bass', 'kick', 'snare', 'hat', 'whoosh']   # crash/open hat = DSP noise

def build_brr(S):
    blobs = {}
    for name in SAMPLE_ORDER:
        s = S[name]
        y = s['y']
        if s['loop'] is not None:
            ls = s['loop']; assert ls % 16 == 0 and (len(y) - ls) % 16 == 0
            data = encode(to_i16(y), loop_start=ls)
            loop_off = ls // 16 * 9
        else:
            y = pad16(np.concatenate([y, np.zeros(32)]))
            data = encode(to_i16(y), loop_start=None)
            loop_off = 0
        blobs[name] = (data, loop_off)
        # keep wav of each instrument for reference
    return blobs

# ---------------------------------------------------------------- song
NOTE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
def m(name):
    """'C#5' -> midi"""
    base = NOTE[name[0]]; i = 1
    while i < len(name) and name[i] in '#b':
        base += 1 if name[i] == '#' else -1; i += 1
    return base + 12 * (int(name[i:]) + 1)

def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)

# voices
V_LEAD, V_HARM, V_STAB1, V_STAB2, V_BASS, V_KICK, V_SNARE, V_HAT = range(8)
# stereo map (L, R) on the S-DSP's signed 7-bit voice volumes (negative = phase-inverted)
PAN = {V_LEAD: (100, 66), V_HARM: (42, 100), V_STAB1: (120, 18), V_STAB2: (18, 120),
       V_BASS: (108, 108), V_KICK: (92, 92), V_SNARE: (110, 110), V_HAT: (40, 104)}
P_DOUBLE = (34, 96)          # detuned, 1-tick-late lead double (Haas) on the harmony voice
P_HARM = (40, 104)           # harmony a third below: opposite side to the lead
STAB_L, STAB_R = (122, 14), (14, 122)
CRASH_PAN = (116, -44)       # wide "surround" crash: R side phase-inverted (mono sum keeps 72/116)
TOM_PANS = [(118, 30), (96, 60), (60, 96), (30, 118)]   # high tom left -> floor tom right
ADSR = {  # (ADSR1, ADSR2)
    'lead':  (0x80 | (5 << 4) | 0xE, (6 << 5) | 0x0C),
    'pad':   (0x80 | (2 << 4) | 0xE, (7 << 5) | 0x08),     # slow attack: brass swell
    'brass': (0x80 | (6 << 4) | 0xF, (3 << 5) | 0x14),
    'bswell': (0x80 | (1 << 4) | 0xE, (7 << 5) | 0x06),    # brass swell, slow attack
    'bass':  (0x80 | (5 << 4) | 0xF, (4 << 5) | 0x12),
    'kick':  (0x8F, 0xE0), 'snare': (0x8F, 0xE0), 'hat': (0x8F, 0xE0),
    'ohat':  (0x8F, 0xE0 | 0x1A), 'crash': (0x8F, 0xE0 | 0x13),   # S-DSP noise, exponential decay
    'whoosh': (0x8F, 0xE0),
}
SAMPLE_OF = {'pad': 'lead', 'bswell': 'brass', 'ohat': 'whoosh', 'crash': 'whoosh'}
NOISE_INST = ('ohat', 'crash')
NOISE_GAIN = 0.5
NCLK = 0x1F   # noise clock 32 kHz (FLG bits 0-4)
INTRO = 10
SWING_FROM = 16 * INTRO      # 16th-note swing (off-16ths 1 tick late = 58%) from the main loop on
SWING_TICKS = 1

def g16(d, minus=1):
    return max(1, int(round(d * TICKS_PER_16TH)) - minus)

class Song:
    def __init__(self):
        self.notes = []
        self.up = []      # (first_bar, end_bar): played a whole step up by the driver
    def add(self, step16, voice, inst, midi, dur16, vel=1.0, gate=None, pitch=None, vib=False,
            pan=None, detune=0.0, delay=0, auto=None, swing=True):
        if os.environ.get('MUTESONG'):   # test builds only: silent song (to measure the SFX alone)
            return
        tick = int(round(step16 * TICKS_PER_16TH))
        if swing and step16 >= SWING_FROM and float(step16).is_integer() and int(step16) % 2 == 1:
            tick += SWING_TICKS
        tick += delay
        dur = int(round(dur16 * TICKS_PER_16TH))
        g = dur - 1 if gate is None else gate
        self.notes.append(dict(tick=tick, voice=voice, inst=inst, midi=midi, dur=dur, gate=max(1, g),
                               vel=vel, pitch=pitch, vib=vib, pan=pan, detune=detune, auto=auto))

CHORD = {  # bass root midi, stab voicing (2 notes)
    'Dm': (38, ('F4', 'A4')), 'Bb': (34, ('F4', 'Bb4')), 'C': (36, ('E4', 'G4')),
    'A': (33, ('E4', 'C#4')), 'Gm': (43, ('G4', 'Bb4')), 'D': (38, ('F#4', 'A4')),
    'F': (41, ('A4', 'C5')), 'B': (35, ('D#4', 'F#4')), 'Eb': (39, ('G4', 'Bb4')),
}
SEVENTH = {'Dm': 10, 'Bb': 9, 'C': 10, 'A': 10, 'Gm': 10, 'D': 10, 'F': 9, 'B': 10, 'Eb': 9}

def seq(s):
    out = []
    for tok in s.split():
        n, d = tok.split(':')
        out.append((None if n == 'r' else m(n), float(d)))
    return out

MEL_A = [
    'A4:2 D5:6 E5:2 F5:2 E5:2 D5:2',
    'F5:6 D5:2 Bb4:4 C5:2 D5:2',
    'E5:6 C5:2 G4:4 A4:2 Bb4:2',
    'A4:8 r:2 A4:2 D5:2 E5:2',
    'F5:6 G5:2 A5:4 G5:2 F5:2',
    'D5:6 F5:2 Bb5:4 A5:2 G5:2',
    'G5:6 E5:2 C5:4 D5:2 E5:2',
    'C#5:6 E5:2 A5:8',
]
MEL_A2_END = 'E5:4 C#5:2 E5:2 G5:4 A5:4'
MEL_B = [
    'Bb5:4 A5:2 G5:2 D5:4 G5:4',
    'A5:4 G5:2 F5:2 D5:8',
    'F5:4 G5:2 A5:2 Bb5:4 C6:4',
    'C6:6 Bb5:2 G5:4 E5:4',
    'D5:2 G5:2 Bb5:4 A5:2 G5:2 F5:2 G5:2',
    'A5:6 E5:2 C#5:4 E5:4',
    'D5:4 F5:4 E5:4 G5:4',
    'F#5:4 A5:4 D6:8',
]
MEL_C = ['D5:16', 'E5:16', 'F5:12 E5:2 D5:2', 'C#5:8 E5:4 A5:4']
# second theme (F major, dotted/syncopated, more lyrical)
MEL_D = [
    'C5:3 A4:3 C5:2 F5:6 E5:2',
    'G5:3 F5:3 E5:2 C5:8',
    'D5:3 E5:3 F5:2 A5:4 G5:4',
    'F5:6 D5:2 Bb4:8',
    'C5:3 A4:3 C5:2 F5:4 A5:4',
    'G5:3 A5:3 G5:2 E5:4 C5:4',
    'D5:4 F5:4 Bb5:4 A5:4',
    'G5:8 E5:4 C5:4',
]
MEL_D2_END = 'G5:4 A5:4 Bb5:4 C6:4'
# tension: long rising notes (played with slow-attack 'pad' envelope)
MEL_G = ['A4:16', 'Bb4:16', 'D5:16', 'F5:16', 'G5:16', 'Bb5:16', 'A5:16', 'D#5:8 F#5:8']
# brass soli: (bar, side, line); side 0 = left brass, 1 = right brass, 2 = both (harmony on right)
SOLI = [
    (0, 0, 'A4:2 D5:2 F5:2 E5:1 D5:1 F5:4 r:4'),
    (1, 1, 'C5:2 D5:2 F5:2 G5:1 F5:1 D5:4 r:4'),
    (2, 0, 'F5:2 D5:2 Bb4:2 C5:2 D5:4 r:4'),
    (3, 1, 'E5:2 G5:2 C5:2 D5:2 E5:4 r:4'),
    (4, 0, 'A5:2 G5:1 F5:1 G5:2 A5:2 D5:4 r:4'),
    (5, 1, 'A5:2 G5:1 F5:1 G5:2 A5:2 F5:4 r:4'),
    (6, 2, 'D5:4 F5:4 Bb5:8'),
    (7, 2, 'C#5:4 E5:4 A5:6 r:2'),
]
SOLI_LOW = {6: 'Bb4:4 D5:4 F5:8', 7: 'A4:4 C#5:4 E5:6 r:2'}

CH_A = ['Dm', 'Bb', 'C', 'Dm', 'Dm', 'Bb', 'C', 'A']
CH_B = ['Gm', 'Dm', 'Bb', 'C', 'Gm', 'A', 'Bb|C', 'D']
CH_C = ['Bb', 'C', 'Dm', 'A']
CH_D = ['F', 'C', 'Dm', 'Bb', 'F', 'C', 'Bb', 'C']
CH_E = ['Dm', 'Dm', 'Gm', 'Dm', 'Dm', 'Dm', 'Bb', 'A']
CH_F = ['Dm', 'Dm', 'Bb', 'C', 'Dm', 'Dm', 'Bb', 'A']
CH_G = ['Dm', 'Dm', 'Bb', 'Bb', 'Gm', 'Gm', 'A', 'B']

SCALES = {'Dm': [2, 4, 5, 7, 9, 10, 0], 'A': [2, 4, 5, 7, 9, 10, 1], 'D': [2, 4, 6, 7, 9, 11, 1]}
def third_below(midi, chord):
    sc = SCALES.get(chord, SCALES['Dm'])
    pc = midi % 12
    if pc in sc:
        i = sc.index(pc); tgt = sc[(i - 2) % 7]
        d = (pc - tgt) % 12
        return midi - d
    return midi - 4

def put_melody(song, bar, lines, chords=None, voice=V_LEAD, vel=1.0, harm=False, double=False, tr=0,
               inst='lead', vib_min=6):
    for bi, line in enumerate(lines):
        st = (bar + bi) * 16
        for midi, d in seq(line):
            if midi is not None:
                pan = None
                if harm:
                    ch = chords[bi].split('|')[0] if chords else 'Dm'
                    if ch not in SCALES:
                        ch = 'Dm'
                    midi = third_below(midi, ch); pan = P_HARM
                midi += tr
                song.add(st, voice, inst, midi, d, vel=vel, gate=g16(d), vib=(d >= vib_min), pan=pan)
                if double:   # width: detuned copy, 1 tick late, other side (Haas + chorus)
                    song.add(st, V_HARM, inst, midi, d, vel=vel * 0.62, gate=g16(d) - 1, vib=(d >= vib_min),
                             pan=P_DOUBLE, detune=+9.0, delay=1)
            st += d

# Funky slap bass: (step, kind, interval, len16, vel); kind r=note, g=ghost (dead note), p=octave pop
BASS_FUNK = [
    [(0, 'r', 0, 2, 1.0), (2, 'g', 0, 1, 0), (3, 'p', 12, 1, 0), (5, 'r', 0, 1, 0.8), (6, 'g', 0, 1, 0),
     (7, 'p', 12, 1, 0), (8, 'r', 0, 1, 0.95), (9, 'g', 0, 1, 0), (10, 'r', 's', 1, 0.85), (11, 'p', 12, 1, 0),
     (13, 'r', 0, 1, 0.8), (14, 'r', 7, 1, 0.85), (15, 'p', 12, 1, 0)],
    [(0, 'r', 0, 1, 1.0), (1, 'g', 0, 1, 0), (2, 'r', 0, 1, 0.75), (3, 'p', 12, 1, 0), (4, 'g', 0, 1, 0),
     (6, 'r', 7, 1, 0.85), (7, 'p', 12, 1, 0), (8, 'r', 0, 2, 0.95), (10, 'g', 0, 1, 0), (11, 'p', 12, 1, 0),
     (12, 'r', 's', 1, 0.85), (13, 'g', 0, 1, 0), (14, 'p', 12, 1, 0), (15, 'r', 7, 1, 0.8)],
]
BASS_PUMP = [[(s, 'p' if s % 4 == 2 else 'r', 12 if s % 4 == 2 else 0, 1, 0.9) for s in range(0, 16, 2)] +
             [(s, 'g', 0, 1, 0) for s in (3, 7, 11, 15)]]
# bass solo for the breakdown: pentatonic runs, slaps, pops, ghosts (intervals over the chord root)
BASS_SOLO = [
    [(0, 'r', 0, 2, 1.0), (2, 'g', 0, 1, 0), (3, 'p', 12, 1, 0), (4, 'r', 0, 1, 0.85), (5, 'r', 3, 1, 0.8),
     (6, 'r', 5, 1, 0.85), (7, 'p', 12, 1, 0), (8, 'r', 7, 2, 0.95), (10, 'g', 0, 1, 0), (11, 'r', 10, 1, 0.85),
     (12, 'p', 12, 1, 0), (13, 'r', 10, 1, 0.8), (14, 'r', 7, 1, 0.85), (15, 'r', 5, 1, 0.8)],
    [(0, 'r', 0, 1, 1.0), (1, 'g', 0, 1, 0), (2, 'r', 0, 1, 0.8), (3, 'p', 12, 1, 0), (5, 'r', 0, 1, 0.8),
     (6, 'p', 15, 1, 0), (7, 'p', 12, 1, 0), (8, 'r', 10, 1, 0.9), (9, 'r', 7, 1, 0.85), (10, 'r', 5, 1, 0.85),
     (11, 'r', 3, 1, 0.85), (12, 'r', 0, 2, 1.0), (14, 'p', 12, 1, 0), (15, 'g', 0, 1, 0)],
    [(0, 'p', 12, 1, 0), (1, 'g', 0, 1, 0), (2, 'p', 15, 1, 0), (3, 'p', 12, 1, 0), (4, 'r', 10, 1, 0.9),
     (5, 'g', 0, 1, 0), (6, 'r', 7, 1, 0.9), (7, 'r', 5, 1, 0.85), (8, 'r', 3, 1, 0.85), (9, 'r', 0, 1, 0.9),
     (10, 'g', 0, 1, 0), (11, 'r', 0, 1, 0.85), (12, 'p', 12, 1, 0), (13, 'p', 17, 1, 0), (14, 'p', 19, 1, 0),
     (15, 'p', 24, 1, 0)],
    [(0, 'r', 0, 3, 1.0), (3, 'p', 12, 1, 0), (4, 'g', 0, 1, 0), (5, 'r', 0, 1, 0.8), (6, 'p', 12, 1, 0),
     (7, 'g', 0, 1, 0), (8, 'r', 7, 1, 0.9), (9, 'p', 19, 1, 0), (10, 'r', 7, 1, 0.85), (11, 'p', 12, 1, 0),
     (12, 'r', 0, 1, 0.9), (13, 'g', 0, 1, 0), (14, 'r', 10, 1, 0.85), (15, 'p', 12, 1, 0)],
]
BASS_PULSE = [[(s, 'm', 0, 2, 0) for s in range(0, 16, 2)]]   # muted 8th pulse (tension / intro)

def put_bass(song, bar, chords, patterns=BASS_FUNK, break_bars=(), tr=0, vel_scale=1.0):
    for bi, chname in enumerate(chords):
        parts = chname.split('|')
        pat = patterns[bi % len(patterns)]
        for step, kind, iv, ln, vel in pat:
            if bi in break_bars and step >= 8:
                continue
            ch = parts[0] if (len(parts) == 1 or step < 8) else parts[1]
            root = CHORD[ch][0] + tr
            if iv == 's':
                iv = SEVENTH[ch]
            st = (bar + bi) * 16 + step
            if kind == 'g':
                song.add(st, V_BASS, 'bass', root, ln, vel=0.34, gate=2)
            elif kind == 'p':
                song.add(st, V_BASS, 'bass', root + iv, ln, vel=1.0, gate=4)
            elif kind == 'm':   # muted pulse
                song.add(st, V_BASS, 'bass', root, ln, vel=0.5 * vel_scale, gate=3)
            else:
                song.add(st, V_BASS, 'bass', root + iv, ln, vel=vel * vel_scale, gate=g16(ln))

def sweep_pan(a, b, n, step=2):
    out = []
    for k in range(step, n, step):
        f = k / n
        out.append((k, a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    return out

STAB_A = [(0, 3), (6, 2), (10, 2), (14, 2)]
STAB_C = [(0, 1), (2, 1), (3, 1), (6, 1), (8, 1), (10, 1), (11, 1), (14, 1)]
STAB_D = [(0, 2), (3, 1), (6, 2), (8, 2), (11, 1), (14, 2)]
STAB_E = [(0, 3), (10, 2)]
def put_stabs(song, bar, chords, pattern=STAB_A, vel=1.0, break_bars=(), tr=0):
    for bi, chname in enumerate(chords):
        parts = chname.split('|')
        hit = 0                              # per bar, so identical bars compile identically
        for step, ln in pattern:
            if bi in break_bars and step >= 8:
                continue
            ch = parts[0] if (len(parts) == 1 or step < 8) else parts[1]
            a, b = CHORD[ch][1]
            flip = hit % 2 == 1
            hit += 1
            for v, n, side in ((V_STAB1, a, 0), (V_STAB2, b, 1)):
                pan = (STAB_L, STAB_R)[side ^ flip]
                other = (STAB_L, STAB_R)[1 - (side ^ flip)]
                gate = max(2, g16(ln, 2))
                auto = sweep_pan(pan, other, gate, 2) if ln >= 3 else None
                song.add((bar + bi) * 16 + step, v, 'brass', m(n) + tr, ln, vel=vel, gate=gate, pan=pan, auto=auto)

def put_hats(song, st, s_from, s_to, odd, light=False):
    ohat = 14 if odd else 6
    for s in range(s_from, s_to):
        if light and s % 2 == 1:
            continue
        if s == ohat + 1:
            continue
        if s == ohat:
            song.add(st + s, V_HAT, 'ohat', None, 2, vel=0.85, pitch=0x1000, pan=(40, 104),
                     auto=sweep_pan((40, 104), (104, 34), 10, 2))
        else:
            v = 0.9 if s % 4 == 0 else (0.7 if s % 2 == 0 else 0.38)
            song.add(st + s, V_HAT, 'hat', None, 1, vel=v, pitch=0x1000)

def tom_roll(song, st, steps, vel=1.0):
    """toms rolling across the stereo field, high-left to floor-right"""
    pitches = (0x1A00, 0x1600, 0x1200, 0x0F00)
    for i, s in enumerate(steps):
        j = min(3, i * 4 // len(steps))
        song.add(st + s, V_KICK, 'kick', None, 1, vel=vel, pitch=pitches[j], pan=TOM_PANS[j])

def put_drums(song, bar, nbars, crash_first=True, fill_last=True, four_floor=False,
              mini_break=(3,), light=False):
    for b in range(nbars):
        st = (bar + b) * 16
        last = fill_last and b == nbars - 1
        mini = (b in mini_break) and not last and nbars >= 8
        odd = b % 2 == 1
        if four_floor:
            kicks = [0, 4, 8, 12, 14] if odd else [0, 4, 8, 11, 12]
        elif light:
            kicks = [0, 7, 10] if odd else [0, 10]
        else:
            kicks = [0, 3, 8, 10, 14] if odd else [0, 7, 10]
        for k in kicks:
            if (last and k >= 8) or (mini and k >= 12):
                continue
            song.add(st + k, V_KICK, 'kick', None, 1, vel=1.0 if k % 4 == 0 else 0.85, pitch=0x0800)
        for s in (4, 12):
            if last and s >= 8:
                continue
            song.add(st + s, V_SNARE, 'snare', None, 1, vel=1.0, pitch=0x1000)
        ghosts = [] if light else ([2, 7, 10, 15] if odd else [7, 9])
        for s in ghosts:
            if (last and s >= 8) or (mini and s >= 12):
                continue
            song.add(st + s, V_SNARE, 'snare', None, 1, vel=0.26, pitch=0x1000)
        hat_from = 1 if (crash_first and b == 0) else 0
        if b == 0 and crash_first:
            song.add(st, V_HAT, 'crash', None, 1, vel=1.0, pitch=0x0800, pan=CRASH_PAN)
        put_hats(song, st, hat_from, 8 if last else (12 if mini else 16), odd, light=light)
        if mini:
            song.add(st + 12, V_SNARE, 'snare', None, 1, vel=0.9, pitch=0x1000)
            song.add(st + 13, V_SNARE, 'snare', None, 1, vel=0.4, pitch=0x1000)
            song.add(st + 14, V_KICK, 'kick', None, 1, vel=1.0, pitch=0x1600, pan=TOM_PANS[1])
            song.add(st + 15, V_KICK, 'kick', None, 1, vel=1.0, pitch=0x1100, pan=TOM_PANS[3])
        if last:   # drum break: snare 16ths + toms rolling L -> R + open hats ping-ponging
            for i, s in enumerate(range(8, 16)):
                if s in (8, 10, 12, 14):
                    song.add(st + s, V_SNARE, 'snare', None, 1, vel=0.6 + 0.06 * i, pitch=0x1000)
            tom_roll(song, st, [9, 11, 13, 15])
            song.add(st + 14.5, V_SNARE, 'snare', None, 0.5, vel=0.75, pitch=0x1000)
            song.add(st + 15.5, V_SNARE, 'snare', None, 0.5, vel=0.85, pitch=0x1000)
            for i, s in enumerate((8, 10, 12, 14)):
                pan = (110, -30) if i % 2 == 0 else (-30, 110)
                song.add(st + s, V_HAT, 'ohat', None, 2, vel=0.7, pitch=0x1000, pan=pan)

def swell(song, step16, voice, inst, midi, n16, side_from, side_to, vel=1.0, tr=0):
    """brass/lead swell: volume crescendo while it pans from one side to the other"""
    n = int(round(n16 * TICKS_PER_16TH)) - 1
    auto = []
    for k in range(2, n, 2):
        f = k / n
        g = 0.15 + 0.85 * f * f
        auto.append((k, (side_from[0] + (side_to[0] - side_from[0]) * f) * g,
                        (side_from[1] + (side_to[1] - side_from[1]) * f) * g))
    song.add(step16, voice, inst, midi + tr, n16, vel=vel, gate=n,
             pan=(side_from[0] * 0.15, side_from[1] * 0.15), auto=auto)

def ramp(x0, x1, f):
    return x0 + (x1 - x0) * max(0.0, min(1.0, f))

def compose_intro(song):
    ich = ['Dm', 'Dm', 'Dm', 'Dm', 'Dm', 'Dm', 'Bb', 'C', 'Bb', 'A']
    k = 0
    for bar in range(0, 10):      # hats tick back and forth, 8ths -> 16ths, getting louder
        step = 2 if bar < 2 else 1
        for st in range(0, 16, step):
            f = (bar * 16 + st) / 128
            sw = math.sin(2 * math.pi * k / 12); k += 1
            vel = ramp(0.2, 0.85, f) * (1.0 if st % 4 == 0 else (0.8 if st % 2 == 0 else 0.55))
            if bar in (7, 9) and st == 14:
                song.add(bar * 16 + st, V_HAT, 'ohat', None, 2, vel=0.85, pitch=0x1000, pan=(104, 34),
                         auto=sweep_pan((104, 34), (34, 104), 10, 2))
                break
            if bar == 9 and st >= 12:
                break
            song.add(bar * 16 + st, V_HAT, 'hat', None, 1, vel=vel, pitch=0x1000,
                     pan=(int(74 - 52 * sw), int(74 + 52 * sw)))
    # brass swells sliding in from alternating sides (stab voices), bars 0-5
    swell(song, 0, V_STAB1, 'bswell', m('D4'), 16, STAB_L, (80, 80), vel=0.6)
    swell(song, 16, V_STAB2, 'bswell', m('A4'), 16, STAB_R, (80, 80), vel=0.6)
    swell(song, 32, V_STAB1, 'bswell', m('F4'), 16, STAB_L, STAB_R, vel=0.7)
    swell(song, 48, V_STAB2, 'bswell', m('A4'), 16, STAB_R, STAB_L, vel=0.7)
    swell(song, 64, V_STAB1, 'bswell', m('D4'), 32, STAB_L, STAB_R, vel=0.75)
    swell(song, 64, V_STAB2, 'bswell', m('A4'), 32, STAB_R, STAB_L, vel=0.75)
    # lead-voice pad swells (rising) bars 2-7, harmony voice answers from the other side
    swell(song, 32, V_LEAD, 'pad', m('D5'), 32, (40, 110), (110, 40), vel=0.55)
    swell(song, 64, V_HARM, 'pad', m('F5'), 32, (110, 40), (40, 110), vel=0.55)
    swell(song, 96, V_LEAD, 'pad', m('G5'), 32, (40, 110), (110, 40), vel=0.65)
    # bass: muted pulse (2-3) -> pumping octaves (4-7) -> driving 16ths (8-9)
    for bar in range(2, 10):
        root = CHORD[ich[bar]][0]
        for st in range(0, 16, 2 if bar < 8 else 1):
            if bar == 9 and st >= 14:
                break
            f = (bar - 2) / 8 + st / 128
            if bar < 4:
                song.add(bar * 16 + st, V_BASS, 'bass', root, 2, vel=ramp(0.28, 0.5, f * 4), gate=3)
            elif bar < 8:
                oc = 12 if st % 4 == 2 else 0
                song.add(bar * 16 + st, V_BASS, 'bass', root + oc, 2, vel=ramp(0.6, 0.85, (bar - 4) / 4), gate=5)
            else:
                oc = 12 if st % 4 == 3 else 0
                song.add(bar * 16 + st, V_BASS, 'bass', root + oc, 1, vel=0.9 if oc else 0.8, gate=4)
    for bar in range(4, 10):
        for st in range(0, 16, 2 if bar == 9 else 4):
            if bar == 9 and st >= 14:
                break
            song.add(bar * 16 + st, V_KICK, 'kick', None, 1, vel=ramp(0.7, 1.0, (bar - 4) / 4), pitch=0x0800)
    tom_roll(song, 3 * 16, [12, 13, 14, 15], vel=0.7)        # first tom roll pans L -> R
    tom_roll(song, 5 * 16, [12, 13, 14, 15], vel=0.85)
    for bar in (5, 6, 7):
        for st in (4, 12):
            song.add(bar * 16 + st, V_SNARE, 'snare', None, 1, vel=ramp(0.7, 0.9, (bar - 5) / 2), pitch=0x1000)
    for i, st in enumerate(range(0, 16, 2)):
        song.add(8 * 16 + st, V_SNARE, 'snare', None, 2, vel=0.4 + 0.03 * i, pitch=0x1000)
    for i, st in enumerate(range(0, 12)):
        song.add(9 * 16 + st, V_SNARE, 'snare', None, 1, vel=0.62 + 0.025 * i, pitch=0x1000)
    for i in range(4):
        song.add(9 * 16 + 12 + i * 0.5, V_SNARE, 'snare', None, 0.5, vel=0.92 + 0.02 * i, pitch=0x1000, swing=False)
    tom_roll(song, 7 * 16, [8, 10, 12, 13, 14, 15], vel=0.95)   # tom roll across before the climb
    hits = {6: [(0, 2), (6, 2), (10, 2)], 7: [(0, 2), (3, 1), (6, 2)],
            8: [(0, 2), (4, 2), (8, 2), (12, 2)], 9: [(0, 2), (4, 2), (8, 2), (12, 1)]}
    hk = 0
    for bar, hl in hits.items():
        a, bn = CHORD[ich[bar]][1]
        for st, ln in hl:
            side = (STAB_L, STAB_R)[hk % 2]; hk += 1
            vel = ramp(0.65, 1.0, (bar - 6 + st / 16) / 4)
            for v, n in ((V_STAB1, a), (V_STAB2, bn)):
                song.add(bar * 16 + st, v, 'brass', m(n), ln, vel=vel, gate=max(2, g16(ln, 2)), pan=side)
    st = 8 * 16
    for i, (n, d) in enumerate(seq('D5:4 E5:4 F5:4 G5:4 A5:4 Bb5:4 C#6:6')):
        vel = 0.72 + 0.04 * i
        song.add(st, V_LEAD, 'lead', n, d, vel=vel, gate=g16(d), vib=(d >= 6))
        song.add(st, V_HARM, 'lead', n, d, vel=vel * 0.62, gate=g16(d) - 1, vib=(d >= 6),
                 pan=P_DOUBLE, detune=+9.0, delay=1)
        st += d

def sec_A(song, b, tr=0, second=False):
    if not second:
        put_melody(song, b, MEL_A, double=True, tr=tr)
    else:
        mel = MEL_A[:7] + [MEL_A2_END]
        put_melody(song, b, mel, tr=tr)
        put_melody(song, b, mel, chords=CH_A, voice=V_HARM, vel=0.62, harm=True, tr=tr)
    put_bass(song, b, CH_A, break_bars=(7,), tr=tr); put_stabs(song, b, CH_A, break_bars=(7,), tr=tr)
    put_drums(song, b, 8)
    return b + 8

def sec_B(song, b, tr=0, last_chord=None):
    ch = list(CH_B)
    if last_chord:
        ch[7] = last_chord
    put_melody(song, b, MEL_B, double=True, tr=tr)
    put_bass(song, b, ch, break_bars=(7,), tr=tr); put_stabs(song, b, ch, break_bars=(7,), tr=tr)
    put_drums(song, b, 8)
    return b + 8

def sec_C(song, b):
    put_melody(song, b, MEL_C)
    put_melody(song, b, MEL_C, chords=CH_C, voice=V_HARM, vel=0.55, harm=True)
    put_bass(song, b, CH_C, patterns=BASS_PUMP, break_bars=(3,))
    put_stabs(song, b, CH_C, pattern=STAB_C, vel=0.9, break_bars=(3,))
    put_drums(song, b, 4, four_floor=True)
    return b + 4

def sec_D(song, b, second=False):
    mel = MEL_D if not second else MEL_D[:7] + [MEL_D2_END]
    put_melody(song, b, mel, double=not second, vib_min=4)
    if second:
        put_melody(song, b, mel, chords=['Dm'] * 8, voice=V_HARM, vel=0.6, harm=True, vib_min=4)
    put_bass(song, b, CH_D, break_bars=(7,) if second else ())
    put_stabs(song, b, CH_D, pattern=STAB_D if second else STAB_A, vel=0.9, break_bars=(7,) if second else ())
    put_drums(song, b, 8, fill_last=second, mini_break=(3,) if second else (3, 7))
    return b + 8

def sec_E(song, b):
    """funky breakdown: bass solo over light drums, sparse stabs flying across"""
    put_bass(song, b, CH_E, patterns=BASS_SOLO, break_bars=(7,))
    put_stabs(song, b, CH_E, pattern=STAB_E, vel=0.8, break_bars=(7,))
    put_drums(song, b, 8, crash_first=False, light=True, mini_break=(3,))
    return b + 8

def sec_F(song, b):
    """brass soli: call (left) and response (right), then both together"""
    for bar, side, line in SOLI:
        st = (b + bar) * 16
        for midi, d in seq(line):
            if midi is not None:
                if side in (0, 2):
                    song.add(st, V_STAB1, 'brass', midi, d, vel=1.0, gate=g16(d, 2), pan=STAB_L)
                if side == 1:
                    song.add(st, V_STAB2, 'brass', midi, d, vel=1.0, gate=g16(d, 2), pan=STAB_R)
            st += d
        if side == 2:
            st = (b + bar) * 16
            for midi, d in seq(SOLI_LOW[bar]):
                if midi is not None:
                    song.add(st, V_STAB2, 'brass', midi, d, vel=0.9, gate=g16(d, 2), pan=STAB_R)
                st += d
    # the lead answers each brass call with a short punch from the middle
    for bar in range(6):
        song.add((b + bar) * 16 + 12, V_LEAD, 'lead', m('D5') if bar % 2 == 0 else m('A4'), 2, vel=0.7,
                 gate=g16(2))
    put_bass(song, b, CH_F, break_bars=(7,))
    put_drums(song, b, 8)
    return b + 8

def sec_G(song, b):
    """tension: quiet, pulsing, building back up (ends on B = dominant of the new key)"""
    for i, line in enumerate(MEL_G):
        st = (b + i) * 16
        for midi, d in seq(line):
            side = (40, 110) if i % 2 == 0 else (110, 40)
            other = (side[1], side[0])
            swell(song, st, V_LEAD, 'pad', midi, d, side, other, vel=ramp(0.5, 0.95, i / 7))
            st += d
    for i, ch in enumerate(CH_G):   # brass swells, alternating sides
        a, bn = CHORD[ch][1]
        sf = STAB_L if i % 2 == 0 else STAB_R
        st_ = STAB_R if i % 2 == 0 else STAB_L
        swell(song, (b + i) * 16, V_STAB1, 'bswell', m(a), 16, sf, st_, vel=ramp(0.5, 0.95, i / 7))
        swell(song, (b + i) * 16, V_STAB2, 'bswell', m(bn), 16, st_, sf, vel=ramp(0.5, 0.95, i / 7))
    put_bass(song, b, CH_G[:4], patterns=BASS_PULSE, vel_scale=0.9)
    put_bass(song, b + 4, CH_G[4:], patterns=[[(s, 'r', 12 if s % 4 == 2 else 0, 2, 0.8) for s in range(0, 16, 2)]])
    for i in range(8):
        st = (b + i) * 16
        for s in range(0, 16, 4 if i < 6 else 2):
            song.add(st + s, V_KICK, 'kick', None, 1, vel=ramp(0.6, 1.0, i / 7), pitch=0x0800)
        put_hats(song, st, 0, 16, i % 2 == 1, light=(i < 4))
        if i >= 4:
            for s in (4, 12):
                song.add(st + s, V_SNARE, 'snare', None, 1, vel=ramp(0.6, 0.9, (i - 4) / 3), pitch=0x1000)
        if i in (1, 3, 5):
            tom_roll(song, st, [12, 13, 14, 15], vel=0.8)
    st = (b + 7) * 16
    for s in range(0, 16):
        song.add(st + s, V_SNARE, 'snare', None, 1, vel=0.5 + 0.03 * s, pitch=0x1000)
    tom_roll(song, st, [8, 10, 12, 14], vel=1.0)
    return b + 8

def compose():
    song = Song()
    compose_intro(song)
    b = INTRO
    LOOP_BAR = b
    b = sec_A(song, b)                 # A   main theme
    b = sec_A(song, b, second=True)    # A'  with harmony
    b = sec_B(song, b)                 # B   climbing second theme
    b = sec_C(song, b)                 # C   bridge
    b = sec_D(song, b)                 # D   new contrasting theme (F major)
    b = sec_D(song, b, second=True)    # D'  with harmony + busier brass
    b = sec_E(song, b)                 # E   funky breakdown / bass solo
    b = sec_F(song, b)                 # F   brass soli, left calls / right answers
    b = sec_G(song, b)                 # G   tension, building back
    up0 = b                            # key change: the driver plays these bars a whole step up,
    b = sec_A(song, b)                 # A   (E minor)            so they reuse the A/A'/B bar data
    b = sec_A(song, b, second=True)    # A'
    b = sec_B(song, b)                 # B
    song.up.append((up0, b))
    b = sec_C(song, b)                 # C   bridge back home to D minor -> loop
    return song, LOOP_BAR * 16 * TICKS_PER_16TH, b * 16 * TICKS_PER_16TH
# ---------------------------------------------------------------- compiler
IMAGE_ADDR = 0x0200   # upload start: sample directory, then the driver
DIR_ADDR = 0x0200
DRIVER_ADDR = 0x0200 + 4 * 7   # driver entry point (right after the 7-entry directory)
REBOOT_CMD = 0xFE   # S-CPU writes this to $2140 to send the SPC700 back to its IPL ROM
EDL = 8   # 8 x 16 ms = 128 ms = an 8th-note triplet at 156 BPM; buffer 8 x 2 KB = 16 KB
ECHO_ADDR = 0x10000 - EDL * 0x800
ECHO_FIR = [0x40, 0x20, 0x10, 0x08, 0x00, 0x00, 0xF8 - 0x100, 0x00]   # darkening repeats, DC gain 0.88
EVOL = (0x26, -0x1A)   # echo return: right side phase-inverted = repeats spread around/behind you
EFB = 0x50
MVOL = 0x30
BAR_TICKS = 16 * TICKS_PER_16TH
# Stream: $00-$7F reg,val | $80-$FB wait 1..124 ticks | $FC lo hi CALL | $FD RET | $FE lo hi JMP
#         $FF n  transpose this track's pitch writes a whole step up (n=1) / off (n=0)
CMD_CALL, CMD_RET, CMD_JMP, CMD_TRANS = 0xFC, 0xFD, 0xFE, 0xFF
TRANSPOSING = (0, 1, 2, 3)   # melodic tracks follow the key change; drums don't
UP_MUL = 287   # pitch * 287/256 = +2 semitones (-2 cents)
MAX_WAIT = 0xFB - 0x7F
# tracks (each has its own pointer/wait/return address in the driver)
TRACKS = [(V_LEAD,), (V_HARM,), (V_STAB1, V_STAB2), (V_BASS,), (V_KICK, V_SNARE, V_HAT)]
TRACK_OF = {v: i for i, t in enumerate(TRACKS) for v in t}
SEG_DIV = [1,1,1,2,2]   # segments per bar, per track
EON_MELODIC = (1 << V_LEAD) | (1 << V_HARM) | (1 << V_STAB1) | (1 << V_STAB2)

def s8(x):
    x = int(round(max(-128, min(127, x))))
    return x & 0xFF

def pitch_reg(inst, midi, S):
    f0 = S[SAMPLE_OF.get(inst, inst)]['f0']
    p = int(round(4096 * hz(midi) / f0))
    assert 0 < p <= 0x3FFF, (inst, midi, p)
    return p

def echo_send(v, inst, vel):
    if inst in ('crash', 'ohat'):
        return True
    if inst == 'snare':
        return vel >= 0.5
    return False

def wait_bytes(n):
    out = bytearray()
    while n > 0:
        k = min(n, MAX_WAIT); out.append(0x7F + k); n -= k
    return out

def compile_segment(evs_by_tick, nticks, drum_track):
    """One bar of one track, compiled from an empty register cache (so equal bars give equal bytes)."""
    out = bytearray(); cache = {}
    def w(reg, val):
        if cache.get(reg) != val:
            out.extend((reg, val)); cache[reg] = val
    def wp(v, p):   # pitch: always lo then hi together (the driver transposes the pair)
        b = v << 4
        if cache.get(b + 2) != (p & 0xFF) or cache.get(b + 3) != (p >> 8):
            out.extend((b + 2, p & 0xFF, b + 3, p >> 8)); cache[b + 2] = p & 0xFF; cache[b + 3] = p >> 8
    pending = 0
    eon = None
    for t in range(nticks):
        evs = evs_by_tick.get(t)
        if evs:
            out += wait_bytes(pending); pending = 0
            kon = koff = 0
            for e in evs:
                if e[0] == 'koff':
                    koff |= 1 << e[1]
            now = set()
            for e in evs:
                if e[0] == 'note':
                    _, v, inst, p, vel, pan, srcn = e
                    now.add(v); kon |= 1 << v; koff &= ~(1 << v)
                    base = v << 4
                    l, r = pan if pan is not None else PAN[v]
                    g = vel * (NOISE_GAIN if inst in NOISE_INST else 1.0)
                    w(base + 0, s8(l * g)); w(base + 1, s8(r * g))
                    wp(v, p)
                    w(base + 4, srcn)
                    a1, a2 = ADSR[inst]
                    w(base + 5, a1); w(base + 6, a2)
                    if v == V_HAT:
                        w(0x3D, 0x80 if inst in NOISE_INST else 0x00)   # NON: noise on voice 7
                    if drum_track:
                        cur = eon if eon is not None else EON_MELODIC
                        cur = (cur | (1 << v)) if echo_send(v, inst, vel) else (cur & ~(1 << v))
                        eon = cur
                        w(0x4D, cur)
            for e in evs:
                if e[0] == 'pitch' and e[1] not in now:
                    wp(e[1], e[2])
                elif e[0] == 'vol' and e[1] not in now:
                    g = NOISE_GAIN if e[4] in NOISE_INST else 1.0
                    w((e[1] << 4) + 0, s8(e[2] * g)); w((e[1] << 4) + 1, s8(e[3] * g))
            if koff:
                out.extend((0x5C, koff))     # the driver ORs KOFF/KON of all tracks per tick
            if kon:
                out.extend((0x4C, kon))
        pending += 1
    out += wait_bytes(pending)
    return bytes(out)

def init_stream():
    out = bytearray()
    def w(reg, val):
        out.extend((reg, val & 0xFF))
    w(0x6C, 0x60 | NCLK)    # FLG: mute, echo writes OFF while ESA/EDL change
    w(0x5C, 0xFF)
    for r, val in ((0x0C, 0), (0x1C, 0), (0x2C, 0), (0x3C, 0), (0x0D, 0), (0x2D, 0), (0x3D, 0),
                   (0x4D, 0), (0x5D, DIR_ADDR >> 8), (0x6D, ECHO_ADDR >> 8), (0x7D, EDL)):
        w(r, val)
    for i, c in enumerate(ECHO_FIR):
        w(0x0F + i * 0x10, c)
    t1 = int(math.ceil(0.30 / TICK_SEC))
    out += wait_bytes(t1)   # > 240 ms: new EDL/ESA latched before echo writes resume
    w(0x6C, 0x20 | NCLK)    # unmute, echo writes still off
    w(0x6C, 0x00 | NCLK)    # echo writes on (EVOL/EFB 0: old buffer junk is never heard)
    t2 = int(math.ceil((EDL * 0.016 + 0.05) / TICK_SEC))
    out += wait_bytes(t2)   # one full pass: buffer flushed with silence
    w(0x0C, MVOL); w(0x1C, MVOL)
    w(0x2C, s8(EVOL[0])); w(0x3C, s8(EVOL[1]))
    w(0x0D, EFB)
    w(0x4D, EON_MELODIC | (1 << V_SNARE))
    return bytes(out), t1 + t2

def compile_song(song, loop_tick, end_tick, S, srcn, base_addr):
    """Returns (blob, track_start_addrs). Bars are deduplicated per track and CALLed."""
    nt = len(TRACKS)
    nbars = end_tick // BAR_TICKS
    assert loop_tick % BAR_TICKS == 0 and end_tick % BAR_TICKS == 0
    ev = [dict() for _ in range(nt)]
    def add(t, e):
        tr = TRACK_OF[e[1]]
        assert 0 <= t < end_tick, (t, e)
        ev[tr].setdefault(t, []).append(e)
    vib_start = int(round(0.25 / TICK_SEC)); vib_per = 0.175 / TICK_SEC; vib_ramp = 0.3 / TICK_SEC
    for n in song.notes:
        v = n['voice']; t = n['tick']
        p = n['pitch'] if n['pitch'] is not None else pitch_reg(n['inst'], n['midi'], S)
        if n['detune']:
            p = int(round(p * 2 ** (n['detune'] / 1200)))
        add(t, ('note', v, n['inst'], p, n['vel'], n['pan'], srcn[SAMPLE_OF.get(n['inst'], n['inst'])]))
        if n['inst'] not in ('kick', 'snare', 'hat', 'ohat', 'crash'):
            add(t + n['gate'], ('koff', v))
        if n['vib']:
            for k in range(vib_start, n['gate'], 2):
                depth = min(1.0, (k - vib_start) / vib_ramp) * 0.28
                pv = int(round(p * 2 ** (depth * math.sin(2 * math.pi * (k - vib_start) / vib_per) / 12)))
                add(t + k, ('pitch', v, min(pv, 0x3FFF)))
        if n['auto']:
            for a in n['auto']:
                if a[0] >= n['gate'] and n['inst'] != 'ohat':
                    continue
                add(t + a[0], ('vol', v, a[1] * n['vel'], a[2] * n['vel'], n['inst']))
    for n in song.notes:
        bar = n['tick'] // BAR_TICKS
        if any(u0 <= bar < u1 for u0, u1 in song.up) and n['pitch'] is None:
            p = pitch_reg(n['inst'], n['midi'], S)
            assert p * UP_MUL // 256 * 1.03 < 0x3FFF, n
    init, init_ticks = init_stream()
    segs = {}      # bytes -> offset in blob
    blob = bytearray()
    tops = []
    stats = dict(raw=0, calls=0, unique=0)
    for ti in range(nt):
        div = SEG_DIV[ti]
        seg = BAR_TICKS // div
        bars = []
        for bi in range(nbars * div):
            local = {}
            for t, es in ev[ti].items():
                if bi * seg <= t < (bi + 1) * seg:
                    local[t - bi * seg] = es
            bars.append(compile_segment(local, seg, ti == len(TRACKS) - 1))
        tops.append(bars)
        stats['raw'] += sum(len(b) for b in bars)
    # segment bodies (each ends with RET)
    for bars in tops:
        for b in bars:
            if len(b) > 3 and b not in segs:
                segs[b] = len(blob); blob += b + bytes((CMD_RET,)); stats['unique'] += 1
    starts = []
    for ti, bars in enumerate(tops):
        loop_bar = loop_tick // (BAR_TICKS // SEG_DIV[ti])
        starts.append(len(blob))
        blob += init if ti == 0 else wait_bytes(init_ticks)
        loop_at = None
        for bi, b in enumerate(bars):
            if bi == loop_bar:
                loop_at = len(blob)
            if ti in TRANSPOSING:
                for (u0, u1) in song.up:
                    if bi == u0 * SEG_DIV[ti]:
                        blob += bytes((CMD_TRANS, 1))
                    if bi == u1 * SEG_DIV[ti]:
                        blob += bytes((CMD_TRANS, 0))
            if len(b) <= 3:
                blob += b
            else:
                a = base_addr + segs[b]
                blob += bytes((CMD_CALL, a & 0xFF, a >> 8)); stats['calls'] += 1
        a = base_addr + loop_at
        blob += bytes((CMD_JMP, a & 0xFF, a >> 8))
    print(f"  stream: {stats['raw']} bytes of bar data -> {stats['unique']} unique bars, {len(blob)} bytes total")
    return bytes(blob), [base_addr + s for s in starts]

# ---------------------------------------------------------------- in-game SFX + driver (enemies build)
# Two SFX channels borrow music voices with priority handled on the S-CPU side:
#   channel A = voice 7 (hi-hats / noise cymbals): boost + bank swooshes, gunfire, missile launch,
#               debris whizzing past.  Command on APU port 1 ($2141) = (seq << 4) | id.
#   channel B = voice 1 (harmony / lead double): explosions, enemy flybys, missile kills.
#               Command on APU port 2 ($2142) = (seq << 4) | id.  Its pan and volume follow the
#               object live: port 3 ($2143) = pan 0 (left) .. 127 (right), bit 7 = behind you
#               (right side phase-inverted + Doppler pitch drop); port 0 ($2140) = volume 0..127.
# SFX stream (one step per 16 ms tick): [vol|$80=key-on] [pitch] [pan]  (pan $FF = live from ports)
#   $FE s = sample s,  $FD n = hold the last step n more ticks,  $FF = end (music gets the voice back).
# Pitch byte: < $80 -> P = b*16 ; >= $80 -> P = $800 + (b-$80)*64.
#
# Attack build (v2): both channels can be panned live. Port 3 = [ch][behind][pan 0..63], port 0 =
# [ch][volume 0..127] (ch bit 7: 1 = channel A, 0 = channel B; channel A volume stays <= 125 so port 0
# never carries $FE). The driver latches pan/volume per channel; the S-CPU alternates frames.
SFX_A = {1: 'boost', 2: 'bank_l', 3: 'bank_r', 4: 'gun_l', 5: 'gun_r', 6: 'missile', 7: 'debris_lr', 8: 'debris_rl',
         9: 'beep', 10: 'hit'}
SFX_B = {1: 'explode', 2: 'flyby', 3: 'bigboom', 4: 'whiz', 5: 'mswoosh', 6: 'die', 12: 'oneup'}
SFXTAB_N = 32
DYN = 0xFF
SRC = {n: i for i, n in enumerate(SAMPLE_ORDER)}

def pb(preg):
    preg = int(round(preg))
    if preg < 0x800:
        return max(1, min(0x7F, int(round(preg / 16))))
    return 0x80 + max(0, min(0x7F, int(round((preg - 0x800) / 64))))

def panb(p, behind=False):
    """p in [-1, 1] (left .. right)"""
    return max(0, min(127, int(round((p + 1) / 2 * 127)))) | (0x80 if behind else 0)

def lr_to_vp(l, r):
    """explicit (L, R) amplitudes (R may be negative = phase-inverted) -> (vol, pan byte)"""
    v = math.hypot(l, r)
    if v < 0.5:
        return 0, 64
    th = math.atan2(abs(r), max(0.0, l))
    return min(124, int(round(v))), panb(th / (math.pi / 2) * 2 - 1, r < 0)

class Sfx:
    def __init__(self):
        self.b = bytearray()
    def src(self, name):
        self.b += bytes((0xFE, SRC[name])); return self
    def step(self, vol, preg, pan, kon=False):
        v = max(0, min(124, int(round(vol))))
        self.b += bytes((v | (0x80 if kon else 0), pb(preg) if preg else 0, pan)); return self
    def hold(self, n):
        while n > 0:
            k = min(n, 255); self.b += bytes((0xFD, k)); n -= k
        return self
    def end(self):
        self.b += bytes((0xFF,)); return bytes(self.b)

def sfx_streams():
    out = {}
    # 1-3: the draft-2 boost / bank swooshes, same shapes (16 steps x 2 ticks)
    for sid, name in ((1, 'boost'), (2, 'bank_l'), (3, 'bank_r')):
        s = Sfx().src('whoosh')
        for k in range(SFX_STEPS):
            f = k / (SFX_STEPS - 1)
            env = math.sin(math.pi * min(1.0, f * 1.6)) if f < 0.62 else max(0.0, 1 - (f - 0.31) / 0.69) * 0.98
            env = max(0.0, min(1.0, env)) * (1 - f) ** 0.5
            if sid == 1:
                l = 100 * env
                r = 100 * env * (-0.7 + 1.7 * min(1.0, f / 0.45))
                ph = 0x10 + int(0x18 * math.sin(math.pi * min(1.0, f / 0.7))) - int(0x08 * f)
            else:
                side = (f * 2 - 1) * (1 if sid == 3 else -1)
                l = 92 * env * math.sqrt((1 - side) / 2)
                r = 92 * env * math.sqrt((1 + side) / 2)
                ph = 0x1C - int(0x10 * f)
            if k == SFX_STEPS - 1:
                break
            v, p = lr_to_vp(l, r)
            s.step(v, max(1, min(0x3F, ph)) << 8, p, kon=(k == 0)).hold(1)
        out[name] = s.end()
    # 4/5: gunfire, hard on that wing's side, sliding toward the centre as the round flies off
    for name, side in (('gun_l', -1), ('gun_r', 1)):
        s = Sfx().src('snare')
        for k, (v, p, x) in enumerate([(124, 0x1A00, 1.0), (104, 0x1800, 0.86), (78, 0x1640, 0.72),
                                       (52, 0x1500, 0.58), (30, 0x1400, 0.45), (14, 0x1300, 0.35)]):
            s.step(v, p, panb(side * x), kon=(k == 0))
        out[name] = s.end()
    # 6: missile launch: ignition rush from behind you, then it screams off ahead
    s = Sfx().src('whoosh')
    n = 40
    for k in range(0, n, 2):
        f = k / n
        v = 124 * min(1.0, 0.45 + k / 5) * (1 - f) ** 1.3
        p = 0x0C00 + 0x1600 * min(1.0, f / 0.45)
        behind = k < 6
        s.step(v, p, panb(0.0, behind), kon=(k == 0)).hold(1)
    out['missile'] = s.end()
    # 7/8: debris tearing past your head: bright crackling rush, side to side, ending behind you
    rr = np.random.default_rng(7)
    for name, d in (('debris_lr', 1), ('debris_rl', -1)):
        s = Sfx().src('whoosh')
        n = 26
        for k in range(n):
            f = k / (n - 1)
            env = min(1.0, k / 4) * (1 - f) ** 0.8
            crackle = 0.55 + 0.45 * rr.random()
            v = 118 * env * crackle
            p = 0x2000 - 0x0C00 * f + rr.integers(-0x200, 0x200)
            s.step(v, p, panb(d * (-1 + 2 * f), f > 0.7), kon=(k == 0))
        out[name] = s.end()
    # B1: explosion: low snare crack/boom, then a crackling debris rumble (pan/volume live)
    s = Sfx().src('snare')
    for k in range(10):
        s.step(124 * (1 - k / 14), 0x0780 - k * 0x38, DYN, kon=(k == 0))
    s.src('whoosh')
    rr = np.random.default_rng(11)
    n = 34
    for k in range(n):
        f = k / n
        v = 116 * (1 - f) ** 1.6 * (0.6 + 0.4 * rr.random())
        s.step(v, 0x0A00 - 0x0500 * f, DYN, kon=(k == 0))
    out['explode'] = s.end()
    # B2: enemy flyby: jet rush that follows the plane (live pan/volume, Doppler drop behind you)
    s = Sfx().src('whoosh')
    s.step(124, 0x0D00, DYN, kon=True).hold(64)
    out['flyby'] = s.end()
    # B3: missile kill: deep kick boom + crack, longer debris rumble
    s = Sfx().src('kick')
    for k in range(5):
        s.step(124, 0x0600 - k * 0x60, DYN, kon=(k == 0))
    s.src('snare')
    for k in range(9):
        s.step(124 * (1 - k / 13), 0x0700 - k * 0x40, DYN, kon=(k == 0))
    s.src('whoosh')
    rr = np.random.default_rng(13)
    n = 46
    for k in range(n):
        f = k / n
        v = 120 * (1 - f) ** 1.4 * (0.6 + 0.4 * rr.random())
        s.step(v, 0x0B00 - 0x0600 * f, DYN, kon=(k == 0))
    out['bigboom'] = s.end()
    # A9: missile lock-on warning: a bright two-tone "bip", panned live to the missile's side
    s = Sfx().src('lead')
    s.step(112, 0x2C00, DYN, kon=True).hold(1)
    s.step(100, 0x3400, DYN).hold(1)
    s.step(0, 0, DYN)
    out['beep'] = s.end()
    # A10: you're hit: metallic crunch + rattle on the side the shot came from (live pan)
    s = Sfx().src('kick')
    s.step(124, 0x0900, DYN, kon=True)
    s.step(124, 0x0800, DYN)
    s.src('snare')
    rr = np.random.default_rng(17)
    for k in range(12):
        f = k / 12
        s.step(124 * (1 - f) ** 1.2, 0x1E00 - 0x0E00 * f + rr.integers(-0x300, 0x300), DYN, kon=(k == 0 or k == 5))
    out['hit'] = s.end()
    # B4: enemy round whizzing past your ear: bright, fast falling rush (live pan; behind = Doppler drop)
    s = Sfx().src('whoosh')
    n = 14
    for k in range(n):
        f = k / (n - 1)
        env = min(1.0, (k + 1) / 3) * (1 - f) ** 0.9
        s.step(124 * env, 0x3000 - 0x1800 * f, DYN, kon=(k == 0))
    out['whiz'] = s.end()
    # B5: dodged missile screaming past (live pan/volume, Doppler drop behind you)
    s = Sfx().src('whoosh')
    for k in range(12):
        f = k / 11
        s.step(124 * min(1.0, 0.5 + k / 4), 0x2200 - 0x0600 * f, DYN, kon=(k == 0)).hold(1)
    s.step(80, 0x1800, DYN).hold(6)
    out['mswoosh'] = s.end()
    # B6: you're shot down: huge kick boom, crack, long tearing rumble
    s = Sfx().src('kick')
    for k in range(6):
        s.step(124, 0x0500 - k * 0x50, DYN, kon=(k == 0))
    s.src('snare')
    for k in range(10):
        s.step(124 * (1 - k / 14), 0x0600 - k * 0x38, DYN, kon=(k == 0))
    s.src('whoosh')
    rr = np.random.default_rng(19)
    n = 50
    for k in range(n):
        f = k / n
        v = 124 * (1 - f) ** 1.2 * (0.55 + 0.45 * rr.random())
        s.step(v, 0x0A00 - 0x0600 * f, DYN, kon=(k == 0))
    out['die'] = s.end()
    # B12 (boss v2): extra life: bright rising arpeggio bouncing L/R, then a shimmering top note
    # swirling across the stereo field
    s = Sfx().src('lead')
    for k, (p, x) in enumerate([(0x1300, -0.85), (0x17F0, 0.85), (0x1C80, -0.55), (0x2600, 0.55)]):
        s.step(118, p, panb(x), kon=True).hold(3)
    for k in range(14):
        f = k / 13
        s.step(118 * (1 - f) ** 0.8, 0x2600 + (0x80 if k % 2 else 0), panb(0.9 * math.sin(f * 2 * math.pi))).hold(1)
    s.step(0, 0, panb(0.0))
    out['oneup'] = s.end()
    return out

SFX_STEPS = 16
TRK = 0x80     # track state: $80+8t ptr lo/hi, +2/+3 return addr, +4 wait, +5 transpose

def driver_main_asm(track_starts, track_starts2=None, timer_div=None):
    # boss build: a second song (victory jingle) started by $FF on port 0 (edge-triggered), and a
    # per-image timer divider (tempo). The field image passes its own song as song 2 (never used).
    nt = len(track_starts)
    if track_starts2 is None:
        track_starts2 = track_starts
    if timer_div is None:
        timer_div = TIMER_DIV
    def ini(starts):
        return '\n'.join(f'  mov {TRK + 8 * t},#{a & 0xFF}\n  mov {TRK + 8 * t + 1},#{a >> 8}\n'
                          f'  mov {TRK + 8 * t + 4},#0\n  mov {TRK + 8 * t + 5},#0' for t, a in enumerate(starts))
    init = ini(track_starts)
    init2 = ini(track_starts2)
    return f'''
start:
  mov $fa,#{timer_div}
  mov $f1,#$31            ; timer0 on, clear the input ports, IPL ROM off
  mov a,#0
  mov $22,a               ; SFX channel A idle
  mov $2a,a               ; SFX channel B idle
  mov $30,a               ; SFX key-on bits for this tick
  mov $31,#$ff            ; voices the music owns (KON/KOFF mask)
  mov $27,#$70            ; channel A = voice 7
  mov $2f,#$10            ; channel B = voice 1
rp1: mov a,$f5
  cmp a,$f5
  bne rp1
  mov $05,a
rp2: mov a,$f6
  cmp a,$f6
  bne rp2
  mov $06,a
  ; $48 = last port-0 value seen (song-2 edge detect): 0 after the IPL clears page 0
{init}
idle:
  mov a,$f4
  cmp a,#{REBOOT_CMD}
  beq reboot
  mov a,$fd               ; timer0 counter
  beq idle
  call sfx
  call tick
  mov a,$f4               ; after the tick (keeps the idle poll, and so the music timing, unchanged)
  cmp a,$48
  beq idle
  mov $48,a
  cmp a,#$ff
  bne idle
{init2}
  bra idle
reboot:
  mov $f2,#$6c
  mov $f3,#$e0            ; FLG: soft reset, mute, echo writes off
  mov $f1,#$b0            ; IPL ROM on, clear input ports, timers off
  jmp !$ffc0
; ---- one tick of every track
tick:
  mov $07,#0
  mov $09,#0
  mov x,#0
trk:
  mov a,{TRK + 4}+x
  beq go
  dec {TRK + 4}+x
  jmp !next
go:
  mov a,{TRK}+x
  mov $00,a
  mov a,{TRK + 1}+x
  mov $01,a
cl:
  mov y,#0
  mov a,[$00]+y
  incw $00
  cmp a,#$80
  bcc regw
  jmp !cmd
regw:
  mov $0e,a
  mov a,[$00]+y
  incw $00
  mov y,$0e
  cmp y,#$4c
  bne nk
  or a,$07
  mov $07,a
  jmp !cl
nk:
  cmp y,#$5c
  bne nf
  or a,$09
  mov $09,a
  jmp !cl
nf:
  mov $0f,a
  mov a,{TRK + 5}+x
  beq notr
  mov a,y
  and a,#$0f
  cmp a,#2
  bne t3
  mov $0c,$0f             ; pitch lo: hold until hi arrives
  jmp !cl
t3:
  cmp a,#3
  bne notr
  mov $0d,$0f
  mov a,$0c
  mov y,#{UP_MUL - 256}
  mul ya
  mov $0a,y
  mov $0b,#0
  mov a,$0d
  mov y,#{UP_MUL - 256}
  mul ya
  addw ya,$0a
  addw ya,$0c             ; pitch * 287/256
  mov $0a,a
  mov $0b,y
  mov a,$0e
  dec a
  mov y,a
  mov a,$0a
  call wreg
  mov y,$0e
  mov a,$0b
  call wreg
  jmp !cl
notr:
  mov a,$0f
  call wreg
  jmp !cl
; write DSP register Y = A, through the shadow of voice 1, voice 7 and NON (skipped while an SFX owns the voice)
wreg:
  push a                  ; title v1: MONO ($4f != 0, set by the S-CPU's upload): voice VOL L/R ->
  mov a,$4f               ; both sides (|L| + |R|) / 2 (L is held in $4d until its R arrives)
  beq wn
  mov a,y
  and a,#$8e
  beq wv
  cmp y,#$3c              ; MONO: echo return R = L (EVOL R always follows EVOL L; L/R phase trick off)
  bne wn
  pop a
  mov a,#{EVOL[0] & 0xFF}
  bra wo
wv:
  pop a
  bpl wp
  eor a,#$ff
  inc a
wp:
  mov $4e,y
  bbs $4e.0,wr
  mov $4d,a
  ret
wr:
  clrc
  adc a,$4d
  ror a                   ; (wo keeps A and Y)
  dec y
  call wo
  inc y
  bra wo
wn:
  pop a
wo:
  cmp y,#$3d
  beq wsa
  push a
  mov a,y
  and a,#$f8
  cmp a,#$70
  beq wsa_p
  cmp a,#$10
  beq wsb_p
  pop a
wout:
  mov $f2,y
  mov $f3,a
  ret
wsa_p:
  pop a
wsa:
  mov !$0000+y,a
  push a
  mov a,$22
  bne wskip
  pop a
  bra wout
wsb_p:
  pop a
  mov !$0000+y,a
  push a
  mov a,$2a
  bne wskip
  pop a
  bra wout
wskip:
  pop a
  ret
cmd:
  cmp a,#$fc
  bcc wt
  beq call_
  cmp a,#$fd
  beq ret_
  cmp a,#$ff
  bne jmp_
  mov a,[$00]+y
  incw $00
  mov {TRK + 5}+x,a
  jmp !cl
jmp_:
  mov a,[$00]+y
  push a
  incw $00
  mov a,[$00]+y
  mov $01,a
  pop a
  mov $00,a
  jmp !cl
call_:
  mov a,[$00]+y
  mov $0e,a
  incw $00
  mov a,[$00]+y
  mov $0f,a
  incw $00
  mov a,$00
  mov {TRK + 2}+x,a
  mov a,$01
  mov {TRK + 3}+x,a
  mov $00,$0e
  mov $01,$0f
  jmp !cl
ret_:
  mov a,{TRK + 2}+x
  mov $00,a
  mov a,{TRK + 3}+x
  mov $01,a
  jmp !cl
wt:
  and a,#$7f
  mov {TRK + 4}+x,a
  mov a,$00
  mov {TRK}+x,a
  mov a,$01
  mov {TRK + 1}+x,a
next:
  mov a,x
  clrc
  adc a,#8
  mov x,a
  cmp x,#{8 * nt}
  beq flush
  jmp !trk
flush:                    ; KOFF then KON, SFX-owned voices masked out of the music's bits
  mov a,$09
  and a,$31
  mov $f2,#$5c
  mov $f3,a
  mov a,$07
  and a,$31
  or a,$30
  beq nokon
  mov $f2,#$4c
  mov $f3,a
nokon:
  mov $30,#0
  ret
'''

def driver_sfx_asm():
    return f'''
sfx:
lp3: mov a,$f7            ; live pan: [ch][behind][pan6] -> per-channel latch (pan7 | behind<<7)
  cmp a,$f7
  bne lp3
  mov $35,a
  and a,#$3f
  asl a
  bbc $35.6,lp3a
  or a,#$80
lp3a:
  bbs $35.7,lp3b
  mov $3b,a
  bra lp0
lp3b:
  mov $3a,a
lp0: mov a,$f4            ; live volume: [ch][vol7]
  cmp a,$f4
  bne lp0
  mov $35,a
  and a,#$7f
  bbs $35.7,lp0b
  mov $3f,a
  bra ra
lp0b:
  mov $3c,a
ra: mov a,$f5
  cmp a,$f5
  bne ra
  cmp a,$05
  beq nob_a
  mov $05,a
  and a,#$0f
  beq nob_a
  mov x,#0
  call sstart
nob_a:
rb: mov a,$f6
  cmp a,$f6
  bne rb
  cmp a,$06
  beq nob_b
  mov $06,a
  and a,#$0f
  beq nob_b
  clrc
  adc a,#16
  mov x,#8
  call sstart
nob_b:
  mov x,#0
  call srun
  mov x,#8
srun:
  mov y,#0
cpin: mov a,$20+x
  mov !$0040+y,a
  inc x
  inc y
  cmp y,#8
  bne cpin
  mov a,x
  setc
  sbc a,#8
  mov $3e,a
  mov a,$42
  beq sdone
  mov a,$43
  beq sparse
  dec $43
  mov a,$46
  cmp a,#$ff
  bne sstore
  call sapply
  bra sstore
sparse:
  mov y,#0
  mov a,[$40]+y
  incw $40
  cmp a,#$ff
  bne snend
  jmp !send
snend:
  cmp a,#$fe
  bne snsrc
  mov a,[$40]+y
  incw $40
  push a
  mov a,$47
  or a,#4
  mov $f2,a
  pop a
  mov $f3,a
  bra sparse
snsrc:
  cmp a,#$fd
  bne sstep
  mov a,[$40]+y
  incw $40
  mov $43,a
  mov a,$46
  cmp a,#$ff
  bne sstore
  call sapply
  bra sstore
sstep:
  mov $44,a
  mov a,[$40]+y
  incw $40
  mov $45,a
  mov a,[$40]+y
  incw $40
  mov $46,a
  mov a,$44
  bpl snokon
  and a,#$7f
  mov $44,a
  call vbit
  or a,$30
  mov $30,a
snokon:
  call sapply
sstore:
  mov x,$3e
  mov y,#0
cpout: mov a,!$0040+y
  mov $20+x,a
  inc x
  inc y
  cmp y,#8
  bne cpout
sdone:
  ret
send:
  mov a,$47
  mov $f2,a
  mov $f3,#0              ; VOL L 0
  inc a
  mov $f2,a
  mov $f3,#0              ; VOL R 0
  mov a,$47
  or a,#7
  mov $f2,a
  mov $f3,#0              ; GAIN 0
  mov a,$47
  or a,#5
  mov $f2,a
  mov $f3,#0              ; ADSR1 0
  call vbit
  mov $f2,#$5c
  mov $f3,a               ; KOFF the voice
  mov y,#$40
sdly: dbnz y,sdly         ; ~250 us > 2 DSP samples
  mov $f3,#0              ; KOFF = 0
  mov x,$47               ; restore the music's 8 voice registers from the shadow
srl: mov $f2,x
  mov a,(x)+
  mov $f3,a
  mov a,x
  and a,#7
  bne srl
  mov a,$47
  cmp a,#$70
  bne snonon
  mov $f2,#$3d
  mov a,$3d
  mov $f3,a               ; NON from its shadow
snonon:
  call vbit
  or a,$31
  mov $31,a               ; music owns the voice again
  mov $42,#0
  bra sstore
vbit:
  mov a,$47
  cmp a,#$70
  beq vb7
  mov a,#$02
  ret
vb7: mov a,#$80
  ret
; X = channel offset (0 = A, 8 = B), A = table index
sstart:
  cmp a,#{SFXTAB_N}
  bcs sstx
  asl a
  mov y,a
  mov a,!SFXTAB+y
  mov $20+x,a
  mov a,!SFXTAB+1+y
  mov $21+x,a
  mov a,#0
  mov $23+x,a
  mov a,#1
  mov $22+x,a
  mov a,$27+x
  mov $47,a
  mov $f2,a
  mov $f3,#0
  inc a
  mov $f2,a
  mov $f3,#0
  mov a,$47
  or a,#5
  mov $f2,a
  mov $f3,#0              ; ADSR off -> GAIN mode
  mov a,$47
  or a,#7
  mov $f2,a
  mov $f3,#$7f            ; GAIN direct, full
  mov $f2,#$5c
  mov $f3,#0              ; KOFF 0
  mov a,$47
  cmp a,#$70
  bne sstnn
  mov $f2,#$3d
  mov a,$3d
  and a,#$7f
  mov $f3,a               ; no noise on voice 7 during the SFX
sstnn:
  call vbit
  eor a,#$ff
  and a,$31
  mov $31,a
sstx:
  ret
; apply $44 vol, $45 pitch byte, $46 pan to voice $47
sapply:
  mov a,$45
  beq spno
  bmi sphi
  xcn a
  push a
  and a,#$0f
  mov $37,a
  pop a
  and a,#$f0
  mov $36,a
  bra spdop
sphi:
  and a,#$7f
  push a
  lsr a
  lsr a
  clrc
  adc a,#8
  mov $37,a
  pop a
  and a,#3
  xcn a
  asl a
  asl a
  mov $36,a
spdop:
  mov a,$46
  cmp a,#$ff
  bne spw
  call lpan
  bpl spw
  mov a,$37               ; behind you: pitch * 3/4 (Doppler drop)
  lsr a
  mov $39,a
  mov a,$36
  ror a
  mov $38,a
  lsr $39
  ror $38
  movw ya,$36
  subw ya,$38
  movw $36,ya
spw:
  mov a,$47
  or a,#2
  mov $f2,a
  mov a,$36
  mov $f3,a
  mov a,$47
  or a,#3
  mov $f2,a
  mov a,$37
  mov $f3,a
spno:
  mov a,$46
  cmp a,#$ff
  bne spfix
  call lpan
  mov $32,a
  call lvol
  mov y,a
  mov a,$44
  mul ya
  asl a
  mov a,y
  rol a
  mov $33,a
  bra spgo
spfix:
  mov $32,a
  mov a,$44
  mov $33,a
spgo:
  mov a,$4f               ; MONO: SFX centred, never phase-inverted
  beq spst
  mov $32,#$40
spst:
  mov a,$32
  and a,#$7f
  lsr a
  lsr a
  lsr a
  mov $34,a
  mov y,a
  mov a,!PANL+y
  mov y,a
  mov a,$33
  mul ya
  asl a
  mov a,y
  rol a
  push a
  mov a,$47
  mov $f2,a
  pop a
  mov $f3,a
  mov y,$34
  mov a,!PANR+y
  mov y,a
  mov a,$33
  mul ya
  asl a
  mov a,y
  rol a
  mov y,$32
  bpl sprp
  eor a,#$ff
  inc a
sprp:
  push a
  mov a,$47
  inc a
  mov $f2,a
  pop a
  mov $f3,a
  ret
lpan: mov a,$3e           ; this channel's live pan latch
  bne lpb
  mov a,$3a
  ret
lpb: mov a,$3b
  ret
lvol: mov a,$3e
  bne lvb
  mov a,$3c
  ret
lvb: mov a,$3f
  ret
'''

SFX_A_BOSS = {11: 'bcannon', 12: 'charge', 13: 'shards', 14: 'ping', 15: 'weak'}
SFX_B_BOSS = {7: 'rumble', 8: 'beam', 9: 'shardw', 10: 'megaboom', 11: 'bmsl'}
SFX_B_TITLE = {13: 'menu_l', 14: 'menu_r', 15: 'menu_ok'}   # title image only

def sfx_section(org, external=None):
    """SFX engine code + pan law + pointer table + streams, assembled at org.
    external: {name: ARAM address} of streams that live outside the section (boss image only);
    without it those table entries point to the stub (the field image)."""
    streams = sfx_streams()
    panl = [int(round(127 * math.cos(i / 15 * math.pi / 2))) for i in range(16)]
    panr = [int(round(127 * math.sin(i / 15 * math.pi / 2))) for i in range(16)]
    names = ['STUB'] * SFXTAB_N
    for i, n in SFX_A.items():
        names[i] = n
    for i, n in SFX_B.items():
        names[16 + i] = n
    ext = {}
    external = external or {}
    for i, n in SFX_A_BOSS.items():
        names[i] = n if n in external else 'STUB'
    for i, n in list(SFX_B_BOSS.items()) + list(SFX_B_TITLE.items()):
        names[16 + i] = n if n in external else 'STUB'
    data = ''
    data += 'PANL: .byte ' + ','.join(map(str, panl)) + '\nPANR: .byte ' + ','.join(map(str, panr)) + '\n'
    data += 'SFXTAB: .word ' + ','.join(f'S_{n}' for n in names) + '\n'
    data += 'S_STUB: .byte $ff\n'
    for n, b in streams.items():
        data += f'S_{n}:\n'
        for i in range(0, len(b), 24):
            data += '  .byte ' + ','.join(f'${x:02x}' for x in b[i:i + 24]) + '\n'
    sizes = {n: len(b) for n, b in streams.items()}
    return driver_sfx_asm() + data, sizes

def assemble_driver(track_starts, sfx_org, track_starts2=None, timer_div=None, external=None):
    from spcasm import Asm
    a = Asm({f'S_{n}': v for n, v in (external or {}).items()})
    secs = a.assemble([(DRIVER_ADDR, driver_main_asm(track_starts, track_starts2, timer_div)),
                       (sfx_org, sfx_section(sfx_org, external)[0])])
    return secs, a.syms


def write_spc(path, ram, dsp_init, title):
    hdr = bytearray(0x100)
    hdr[0:33] = b'SNES-SPC700 Sound File Data v0.30'
    hdr[33:35] = b'\x1a\x1a'; hdr[35] = 0x1A; hdr[36] = 30
    struct.pack_into('<H', hdr, 0x25, DRIVER_ADDR)
    hdr[0x27] = 0; hdr[0x28] = 0; hdr[0x29] = 0; hdr[0x2A] = 0x02; hdr[0x2B] = 0xEF
    def txt(off, n, s):
        b = s.encode()[:n]; hdr[off:off + len(b)] = b
    txt(0x2E, 32, title); txt(0x4E, 32, 'SUPER SKY FURY'); txt(0x6E, 16, 'Grok Bot')
    txt(0x7E, 32, 'Draft 4, full-length, wide stereo'); txt(0xA9, 3, '120'); txt(0xAC, 5, '5000')
    txt(0xB1, 32, 'Naveed Farbakhsh')
    ram = bytearray(ram)
    ram[0xF0:0x100] = bytes(16); ram[0xF1] = 0x00
    dsp = bytearray(128); dsp[0x6C] = 0xE0
    extra = bytes(64)
    with open(path, 'wb') as f:
        f.write(hdr); f.write(ram); f.write(dsp); f.write(bytes(64)); f.write(extra)

def write_upload_asm(image):
    """Generate a ca65 include: ApuUpload routine (IPL boot-ROM protocol) + data in BANK5/6."""
    nblk = (len(image) + 0x7FFF) // 0x8000
    assert nblk <= 2, 'only BANK5/BANK6 reserved for music'
    L = ['; generated by music/make_music.py -- do not edit',
         '; ApuUpload: call with A 8-bit, X/Y 16-bit, DB = $00-$3F/$80-$BF, NMI/IRQ off.',
         '; Uploads the SPC700 driver + samples + song via the IPL ROM protocol and starts it.',
         'ApuUpload:', '  php', '  sep #$20', '  .a8', '  rep #$10', '  .i16',
         '  ; If only the S-CPU was reset (flash-cart in-game reset), the SPC700 is still',
         '  ; running our driver: $FE on port 0 makes it jump back into the IPL ROM.',
         '  ; On a cold boot the IPL ignores it (it only reacts to $CC).',
         f'  lda #${REBOOT_CMD:02X}', '  sta $2140',
         '  ; wait for the IPL ready signal $BBAA (16-bit read of $2140/$2141), with a',
         '  ; ~3 s timeout so a missing/stuck APU can never hang the game at a black screen',
         '  ldy #$0008',
         '@ready: ldx #$0000',
         '@rdy1: rep #$20', '  .a16', '  lda $2140', '  cmp #$BBAA', '  sep #$20', '  .a8',
         '  beq @go_up', '  dex', '  bne @rdy1', '  dey', '  bne @ready',
         '  plp', '  rts                       ; no APU answer: run without music',
         '@go_up:']
    kick = 0xCC
    for i in range(nblk):
        blk = image[i * 0x8000:(i + 1) * 0x8000]
        open(os.path.join(OUT, f'apu_blk{i}.bin'), 'wb').write(blk)
        dest = IMAGE_ADDR + i * 0x8000
        L += [f'  ; block {i}: {len(blk)} bytes -> ARAM ${dest:04X}',
              f'  ldx #${dest:04X}', '  stx $2142', '  lda #$01', '  sta $2141',
              f'  lda #${kick:02X}', '  sta $2140',
              f'@k{i}: cmp $2140', f'  bne @k{i}',
              '  ldx #$0000',
              f'@b{i}: lda f:ApuBlk{i},x', '  sta $2141', '  txa', '  sta $2140',
              f'@e{i}: cmp $2140', f'  bne @e{i}',
              '  inx', f'  cpx #${len(blk):04X}', f'  bne @b{i}']
        kick = ((len(blk) - 1) + 2) & 0xFF
        while kick in (0, 0xAA, REBOOT_CMD):   # nonzero; never look like a stale $AA ready byte
            kick = (kick + 1) & 0xFF
    L += [f'  ; start the driver at ${DRIVER_ADDR:04X}',
          f'  ldx #${DRIVER_ADDR:04X}', '  stx $2142', '  stz $2141',
          f'  lda #${kick:02X}', '  sta $2140',
          '@go: cmp $2140', '  bne @go', '  plp', '  rts', '']
    for i in range(nblk):
        L += [f'.segment "BANK{5 + i}"', f'ApuBlk{i}: .incbin "../music/build/apu_blk{i}.bin"']
    L += ['.segment "CODE"', '']
    open(os.path.join(OUT, 'apu_upload.inc'), 'w').write('\n'.join(L))

def main():
    build_field(write=True)

def build_field(write=True):
    S = make_samples()
    blobs = build_brr(S)
    srcn = {}
    ram = bytearray(0x10000)
    assert len(SAMPLE_ORDER) == 7
    from spcasm import Asm
    main_len = len(Asm({'sfx': 0}).assemble([(DRIVER_ADDR, driver_main_asm([0x1234] * len(TRACKS)))])[0][1])
    sfx_addr = DRIVER_ADDR + main_len
    secs, _ = assemble_driver([0x1234] * len(TRACKS), sfx_addr)
    sfx_len = len(secs[1][1])
    addr = sfx_addr + sfx_len
    for i, name in enumerate(SAMPLE_ORDER):
        data, loff = blobs[name]
        srcn[name] = i
        struct.pack_into('<HH', ram, DIR_ADDR + 4 * i, addr, addr + loff)
        ram[addr:addr + len(data)] = data
        print(f'  sample {i} {name:6s} ${addr:04X} {len(data):5d} bytes')
        addr += len(data)
    song, loop_tick, end_tick = compose()
    blob_addr = addr
    blob, starts = compile_song(song, loop_tick, end_tick, S, srcn, blob_addr)
    ram[blob_addr:blob_addr + len(blob)] = blob
    end = blob_addr + len(blob)
    secs, syms = assemble_driver(starts, sfx_addr)
    (o1, drv), (o2, sfxc) = secs
    assert len(sfxc) == sfx_len and len(drv) == main_len
    ram[sfx_addr:sfx_addr + sfx_len] = sfxc
    ram[DRIVER_ADDR:DRIVER_ADDR + len(drv)] = drv
    _, sizes = sfx_section(sfx_addr)
    print(f'  driver ${DRIVER_ADDR:04X} {len(drv)} bytes; sfx engine+data ${sfx_addr:04X} {sfx_len} bytes '
          f'(streams {sum(sizes.values())}: {sizes})')
    print(f'  song ${blob_addr:04X} {len(blob)} bytes; end ${end:04X}; free before echo: {ECHO_ADDR - end} bytes')
    assert end <= ECHO_ADDR, 'ARAM overflow into echo buffer'
    assert ECHO_ADDR + EDL * 0x800 <= 0x10000 and ECHO_ADDR % 0x100 == 0, 'echo buffer must not wrap'
    image = bytes(ram[IMAGE_ADDR:end])
    info = dict(S=S, blobs=blobs, srcn=srcn, sfx_addr=sfx_addr, sfx_len=sfx_len, main_len=main_len,
                song_addr=blob_addr, end=end, starts=starts)
    if not write:
        return ram, info
    open(os.path.join(OUT, 'free.txt'), 'w').write(str(ECHO_ADDR - end))
    open(os.path.join(OUT, 'apu.bin'), 'wb').write(image)
    write_upload_asm(image)
    write_spc(os.path.join(HERE, 'enemies_v1.spc'), ram, None, 'Afterburner Squadron (draft 4)')
    secs = loop_tick * TICK_SEC, (end_tick - loop_tick) * TICK_SEC
    print(f'  intro {secs[0]:.1f}s, loop {secs[1]:.1f}s; ARAM image {len(image)} bytes')
    return ram, info

if __name__ == '__main__':
    main()
