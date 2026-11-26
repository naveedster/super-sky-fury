# SUPER SKY FURY: technical notes

This is the full development log and technical reference for SUPER SKY FURY. The game began
as "SNES FLY", so source files, labels, and the build output (`build/snesfly.sfc`) still use
that name. The public overview is in the [README](../README.md).

> Paths under `shots/`, `progress/`, `ref/`, the root-level milestone ROMs (`snesfly_*.sfc`),
> the emulator cores in `tools/cores/`, and old music drafts are local development artifacts.
> They are excluded by `.gitignore` and are not in the repository. The release ROM is
> `dist/super_sky_fury.sfc`. Current music renders are `music/{title,stage,boss,boss_victory}.{mp3,spc}`.

## v1.8: smooth sprite animation (stock SNES, no enhancement chip)

The ROM grows from 1 MB to 2 MB: LoROM, FastROM (header map byte `$30`, size byte `$0B`), banks `$80-$BF`. That
gives 64 x 32 KB banks. New banks: `JETB0-9` (`$A0-$A9`, jet frames), `SLOTB0-9` (`$AA-$B3`, near enemy and
prop frames), `ANIMB0` (mid-range enemy frames), `ANIMB1` (explosion, afterburner and thruster frames) and
`ANIMB2` (dad face patches). `ANIMB3-11` are reserved and empty; ld65 warns that those segments do not exist,
which is harmless. The new code is in `src/v18.s`, and the frames come from `tools/gen_assets.py` and
`tools/boom18.py`.

| Sprite | v1.7 | v1.8 |
|---|---|---|
| Chase jet | 15 (mirrored) | 149: 17 banks x 5 climb/dive + 64 barrel-roll angles |
| Near enemies | 16 headings (9 unique) | 192: 64 headings x 3 bank poses |
| Mid-range enemies | 8 directions (5 + flips) | the same 192 at 16x16, streamed into 5 cells |
| Ground targets (near) | 16 headings | 32 headings |
| Enemy explosion | 2 big + 2 smoke frames with flip flicker | flash + 24 fireball + 12 smoke, one sequence |
| Afterburner / boss thrusters | 2 / 2 | 16 / 16 (new frame every 2 vblanks) |
| Dad | static face | 3 eye states (blink), 4 mouth states synced to the voice, 1 px breath, damped recoil |
| Robot | 1-frame shudder, fixed 3 px arm kick | damped recoil, eased arm kick |

* **Streaming.** Everything goes through the chase-view NMI (`X_Stream` in `v11.s`, then `X18_MedStream` and
  `X18_FxStream`). Each step checks `SS_Line` (the scanline count into vblank, with about 37 lines available) and stops
  early when vblank is nearly over. DMA can move about 6.1 KB per vblank at 224 lines, and the budget stays well under that. The jet sends only the union of the old and new frame's non-empty tile rows (`JetRows`, at most 8 x
  256 B). Mid-range cells are 2 x 64 B. Fireball cells are 512 B and take turns with each other, one cell per
  vblank. Smoke cells are 128 B and the flames 2 x 64 B.
* **Budgeted, adaptive.** `ld_last` (the last frame's load in scanlines, set in `Profile`) above `LAG_LN` (185)
  marks a heavy frame. Then the jet, mid-range and explosion uploads wait, for at most `JWAIT` (3) or `CWAIT` (2)
  vblanks in a row, before catching up. The cells skip a vblank when the jet uploaded in it (`js_upd`). An idle path (`fx_ok`,
  `ms_dt`) skips the cell loops when nothing has been requested. An explosion request is held for 16 frames, then the
  cell returns to its home frame (the frame that the static sheets and the cockpit and overhead views show).
* **Easing.** Jet bank level has hysteresis (a one-step change needs the turn rate `$20` past the threshold), and
  the climb pose eases 1 step per frame. Each enemy's bank pose comes from its smoothed world-heading change,
  `bank += (rate - bank) / 4`, with thresholds at +-`$A0`. The headings include the weave offset `en_wv`.
* **Dad.** His body is split into two parts at the chest so the lower part can breathe 1 px (64 of every 192
  frames). The eyes and mouth are 16x16 patches cut from the finished `dad_px.png` sprite (`_dad_eyes`,
  `_dad_mouth`), and they are DMAed over his face tiles when the state changes. The mouth level comes from the RMS of
  `music/dad_voice.wav` at 60 Hz, quantized to 0-3 (`DadTalk`) and started on the voice SFX. Blinks come every
  150-277 frames. He grimaces and squints under heavy damage. Recoil (`X18_Recoil`, used by both bosses) is a
  damped offset from the hit timer instead of a 1-frame jump. The photo files `tools/dad/dad_ref.jpg` and
  `dad_cut.png` stay gitignored.

**Frame drops vs v1.7** (snes9x, SKIPTITLE scenario builds, `progress/v18/seeds.sh`: bot runs from 120 start
offsets, frames 300-2100, or 300-2700 for s1; a dropped frame is an NMI without a finished main loop):

| Scenario | v1.7 drops | v1.8 drops | v1.7 load | v1.8 load |
|---|---|---|---|---|
| Stage 1 from start (s1) | 1316 | 1149 | 186.5 | 188.2 |
| Stage 1 warp (w0) | 2088 | 1847 | 194.7 | 195.5 |
| Stage 2 (w1) | 299 | 293 | 191.1 | 190.9 |
| Stage 3 (w2) | 108 | 108 | 200.2 | 200.8 |
| Stage 4 (w3) | 1049 | 1107 | 184.7 | 186.8 |
| **Total (600 runs)** | **4860** | **4504** | | |

The 12-offset `perfm12.sh` run, which also covers the boss and view scenarios, gives v1.7 437 vs v1.8 388 in total.
Dad fight (autopilot): 0 vs 0. Robot: 12 vs 12. Cockpit: 22 vs 9. Overhead: 2 vs 2. Drop counts are chaotic run to
run (one extra drop changes the whole timeline), which is why many offsets are summed. Stage 4 is the only
scenario where v1.8 is above v1.7, by +5.5%, which is within the run-to-run spread of these sums (about +-75). Load is in scanlines per frame, NMI included. It is about 1 line higher
because of the streaming.

Tested by playing from the title into the game with the bot on snes9x (current), the Delta snes9x 1.55 core and
Mesen-S: all three reach the dad fight with matching state. bsnes runs the ROM, but its peek readout is empty in
this harness, as in earlier versions. Audio: the dad voice starts at the same time as in v1.7 (6.11 s into the
warp test), the music still ducks under it, and stereo width and RMS match v1.7.

## v1.7: medals, set pieces, checkpoints, explosions, voice ducking

* **Voice ducking (SPC700, `music/make_music.py`):** SFX stream opcode `$7F` (never a valid step byte: step
  volumes are at most 124, so `$FC` = vol 124 + key-on is a step and could not be used) calls `duckon`, which
  halves the music-owned voices' (`$31`) VOL L/R twice (signed `ror`, about -12 dB) and sets `$58`. While `$58` is
  set, `wout` scales every music VOL write the same way. `send` (end of the SFX B stream that started the duck,
  `$59`) and a new channel-B start call `duckoff`. `make_boss.py` emits the opcode before the voice line.
  To make room in ARAM the snare sample was trimmed by 12 ms (0.228 s). Measured on snes9x: music RMS drops
  from about 4700 to 1700 during the line; voice-vs-reference correlation 0.80 ("Naveed") and 0.68 (the rest),
  up from 0.41 / 0.38 in v1.6.
* **Medals (`src/v17.s`):** power-up kind 3 (`PU_MEDAL`), NPU 2 -> 4. `X17_MedalDrop` (from `X_KillPts`) drops one
  every `MD_EVERY`=2 kills; `X17_MedalGet` scores `MedVal[md_lv]` x100 (x2 during the convoy) through `T_ScoreAdd`,
  pops an orange number at the medal's screen position (`pu_sx/pu_sy`, saved by `X17_PuDraw`), climbs the ladder.
  `PuGone` (expiry / passed behind) calls `X17_MedalMiss`. Medals draw with existing tiles (F_HSPARK twinkle with
  flips + F_X16A glow), as every OBJ sheet is full.
* **Events (`T_EVENT`, `X17_Event` / `X17_Step`):** wave-script entries `T_EVENT, kind, len` for the checkpoint
  (`EV_CHECK`, z=1 silent), sandstorm/blizzard (`EV_STORM`), flak (`EV_FLAK`) and convoy (`EV_CONVOY`). Storms
  add a triangle-wave crosswind (`wind`, +-$A0 with ease in/out) to the turn rate in `Physics`, and switch the
  ch 7 COLDATA haze to `StormTab` (`assets/storm.bin`, generated by `storm_tab()` in `gen_assets.py`: 4 stages x
  4 levels, ramping 16 frames per level, held to the HUD so the ground half has no band). Flak spawns a
  `T_BIGBOOM` burst at a random spot ahead every 40 - 4*diff frames that fires shrapnel (`T_FireEB`) with a panned
  boom. A boss or game over ends any event.
* **Checkpoints / continue:** `cp_pos` (entry after the checkpoint) and `cp_st`; `T_Continue` (bank 0) runs
  `RestartGame` keeping the difficulty, then `X17_Continue` sets `wave_pos`, reloads the view if the stage
  differs, and shows the stage banner. The game-over hint row shows `START:CONTINUE  SELECT:TITLE`.
* **Difficulty / rank:** burst gap + `StFireAdj` (24 / 10 / 0 / -10 frames by stage); rank adds `md_lv/2`,
  thresholds S 96 / A 80 / B 56.
* **Explosions (`tools/boom17.py`):** a small ray-marcher over a cluster of spheres (Lambert + specular + rim,
  heat ramp in the jet palette: white 13 -> pale yellow 14 -> yellow 9 -> orange 8 -> red 15), frame A with flash
  spikes, frame B cooling with a smoke cap, a shockwave ring of arcs and debris chunks, plus 16 px smoke puffs
  with embers. Same names and footprint as before (`X32A/X32B/X16B/X16C`), so no OBJ sheet changes;
  `OLD_BOOM=1 ./build.sh` rebuilds the v1.6 frames.
* **Fixes:** jet shadow skipped while `p_inv&4` (blinks with the jet) in overhead and chase; cloud pass mist is
  `cl_fog/2` instead of `cl_fog`; comma glyph is 8 rows. `src/v17.s` ends with `.segment "CODE"` so the
  `ApuUpload` that `main.s` includes after it stays in bank 0 (found when a test build hung at boot).
* **Not done:** true see-through clouds via colour math (chase-view colour math is used by the distance haze /
  glare, and the overhead sub-screen blend for OBJ palettes 4-7 renders opaque on all tested emulators; left as
  is), shadows under enemies, a view toggle during the dad fight (he only has a chase-view sheet), curved
  horizon / lens ghosts, and a real battleship or train (the ocean set piece is the bomber convoy).
* **Tests:** snes9x, snes9x155delta (Delta) and Mesen-S: title -> game with the bot (reaches the dad on all
  three), AUTOPILOT dad fight (defeated, Stage 2 and 3 follow, no game over) and robot fight (defeated, loops to
  Stage 1), warp builds for every stage, continue from the checkpoint after a forced game over (UPLIVES=1),
  voice/duck measurement.

## v1.6: the Stage 1 dad boss

* **Engine:** the robot boss code (`src/boss.s`) with a `b_dad` flag set by the wave script (`T_BOSS, 1` at the end of
  Stage 1; the Stage 4 `T_BOSS, 0` is the robot). The flag picks his palette (`DadPal`, palette 7, colours 13/14
  animated in NMI for the pupils and lens glare), his own chase sprite sheet (`assets/obj_chase_dad.bin`, the robot
  sheet with the robot cells swapped for 66 cells of the dad), his part list (`BP_DAD`, plus a damaged version below 1/3 HP),
  texts, 3/4 HP, a +28-frame gap between attacks, and chase view only (the view button does nothing during his fight).
* **Art:** `tools/dad/dad_art.py` builds the bust from the photo (background removal, white balance, CLAHE, head
  enlarged 1.16x, quantised to a hand-picked 15-colour palette, drawn-in rimless lenses, brows and a gold crest).
  The result is cached in `tools/dad/dad_px.png`, which the build uses when the photo is missing.
* **Voice:** `tools/dad/make_voice.sh` (edge-tts en-US-ChristopherNeural, pitch down, high/low-pass, EQ, compressor,
  limiter, 9000 Hz mono) to `music/dad_voice.wav`. `music/make_boss.py` encodes it as one-shot BRR sample 10
  (11691 bytes at $90BE in the boss SPC image, 407 bytes below the echo buffer) and SFX B id 12 plays it at pitch $0480 with
  priority 15 and a 150-frame lock, so nothing interrupts it.
  It is checked by cross-correlating emulator audio with the source WAV (match at the entrance frame) and by an
  isolated libgme render of the boss SPC (voice-only correlation 0.75).
* **Text:** the taunt is on the dark HUD hint row (above his head it was hidden), in the red warning palette, from the
  entrance until 230 frames after it. The font gained a comma.

## v1.5: graphics push (stock SNES, no enhancement chip)

* **Frame budget first.** `ChaseTrails` now caches its OAM output (`ct_buf`): it does a full build every
  other frame and copies the cached entries with `mvn` in between, as long as the cache is less than 2
  frames old. The chase Mode 7 vertical scroll (HDMA ch3, BG1VOFS) no longer rebuilds a per-line table
  each frame. Outside the desert, NMI points an indirect HDMA table (`itab_r`, 10 bytes) at a fixed ramp
  (`RampTab` in bank 23, `(1120-i) & $FFFF`). The desert uses a double-buffered `itab_d` that points into
  the same ramp, with 24 wobble entries from `HeatWob` (8 phases) for the heat shimmer. The jet shadow is
  written straight into OAM from a per-altitude `ShadowY` table, with no projection.
* **Gloss pass.** `tools/voxstack.py` `render(gloss=...)` adds Blinn-Phong specular toward a fixed key
  light, a warm back-rim term, and per-material masks (only metal and paint get a highlight). It is applied
  to the jet (`GLOSS_JET`), the enemies, the bomber, the fortress (`GLOSS_EN`), and props larger than 16 px
  (`GLOSS_PROP`). Palettes are unchanged in size: the highlight reuses each ramp's top index, and the rim
  reuses a warm index.
* **Skies.** Each stage has 16 sky phases (`SkyPh`, $120 bytes each: smoothstep gradients, error-diffused
  to 5 bits). Every 4 frames, NMI repoints the CGRAM HDMA (ch6) at the current phase. The kinds are dawn
  (ocean), heat (desert sunset), aurora (arctic), and neon (night). The night water shimmer table also
  cycles neon colours.
* **Horizon bands.** BG3 gets a per-stage 2 KB tile set plus two 192-entry maps (`BANDB`, bank 24),
  DMA'd by `X15_Band` when the stage changes: islands (121 tiles), mesas with caprock and lit west slopes
  (99), snow-capped ice peaks (106), and a city skyline with lit windows (49).
* **Haze and glare.** The COLDATA HDMA (ch7) reads `GlareTab` (bank 23, $110 bytes per stage and level):
  haze that thickens toward the horizon, plus 4 glare levels. On the dawn and sunset stages, `X15_Sun`
  places a sun sprite at a fixed bearing on the horizon and picks the glare level from how close it is to
  screen centre. Colour math is now applied to BG1-4 and the backdrop in chase (`x15_cga` = $2F) so the
  glare also lights the sky.
* **Cloud white-out.** `X15_Fog` (chase only) flags a cloud right on the jet (depth 22-43, lateral < 16,
  height within 18). `FxCommit` takes the larger of the hit flash and the fog level, so the picture whites
  out through the existing flash constant and fades over about 10 frames.
* **Title.** A boss silhouette (from `boss_rt.py`, 94x88, BG2 palette 3, behind the logo) and a shine band
  on the logo (HDMA ch3 BG1HOFS and ch7 COLDATA, moving 1 line per frame). The title uses 367 of 384 tiles.
* **Layout.** `SwirlTab` moved to BANK1 (bank 0 was full in PROFX builds). New segments: `SKYB` (ROM23)
  and `BANDB` (ROM24). The chase sprite sheet has 0 free tiles (the shadow tile used the last one).

**Performance** (same method as v1.4: RING builds, `rcm.sh` K=6 with SELECT for view, `NORANK`;
`bossbench.sh` K=4 for the boss, all three builds measured the same way).

| Run | v1.3 | v1.4 | v1.5 |
|---|---|---|---|
| sa0 chase: frames over 262 | 124 | 196 | 101 |
| sa0 chase: mean lines | 187.0 | 188.6 | 183.3 |
| sa1 overhead: frames over 262 | 15 | 15 | 15 |
| sa2 cockpit: frames over 262 | 1 | 2 | 5 |
| boss: frames over 262 (K=4) | 5 | 6 | 2 |
| boss: mean lines | 139.4 | 138.5 | 133.9 |

Each stage run is about 32,300 frames. Chase now drops 0.31% of frames (v1.3 0.38%, v1.4 0.61%).
Cockpit drops 3 more frames than v1.4 (out of 32,000).

**Verification.** The release ROM's `tools/dev/boss_win_rel.txt` replay reaches MISSION COMPLETE on
snes9x, snes9x 1.55 (Delta), and Mesen-S. Full run: an AUTOPILOT build played from the title by the
harness bot clears all four stages and beats the boss (MISSION COMPLETE around frame 10,200 to 11,000) on
all three cores, then loops to stage 1. A 4-core smoke test (`cores.sh`, including bsnes) runs clean.

**Not done.** A curved horizon, lens-flare ghosts (tried, then dropped for cost), true translucent clouds
(the cloud pass is a white-out, not per-pixel transparency), enemy ground shadows, and a mid-screen palette
split.

## v1.4: barrel roll, charge shot, graze, ranks, ground-target fix, effects

All new code is in `src/v14.s` (bank $8C XCODE, plus a few bank-0 trampolines). It is hooked from
CombatStep (`X14_Step`), ProjectObjects (`X14_Project`), the NMI (`X14_Nmi`), BuildChase (`X14_JetFx`),
MoveEB (graze), PlayerHit (no damage while rolling), and X_WaveStage (the rank gate).

* **Barrel roll.** A second press of L or R within 14 frames starts a 26-frame roll (12-frame cooldown).
  `X14_JetFrame` plays a 26-step frame/flip table. `SlideAll` moves every jet-relative object by
  44/16 px per frame, and the world position moves by MulSS with cos and sin. PlayerHit ignores hits
  while `roll_t` is set. The whoosh reuses the live-surround SB_FLYBY with a new follow kind
  (`K_ROLL`): `RollSX`/`RollSZ` carry it front, to the roll side, behind, and to the other side. ARAM
  is full, so no new samples were added.
* **Charge shot.** Hold X for 40 frames; each graze banks 12. When it is full, SA_BEEP plays.
  Releasing X fires `cb_*`, which lives 34 frames. Each enemy it touches gets `X_MissileHit` and 6 extra
  damage, and it keeps flying. The boss takes 6 plus a missile hit, and that ends the blast. It also
  flattens ground targets. It is drawn as X32A + X16A, flickering (chase and cockpit).
* **Graze.** A tracer that misses within 30 px sideways and 24 px in height gives +100 points and a
  spark on that wing, plays debris L/R in that ear, and banks charge. A tracer passed through during
  a roll counts double.
* **Weapon levels.** P stacks: LV2 is the v1.3 spread. LV3 fires all three lanes on every round with
  `fire_cd` 5 and +4 px hit half-width (`p_wide`).
* **Rank.** `X14_RankGate` holds the stage switch for 170 frames with STAGE CLEAR, the rank, and the
  stats: kills/spawned, grazes, and hits. The percentage is computed with the hardware multiplier and
  divider: S at 100 or more, A at 82, B at 60, otherwise C.
* **Ground targets.** v1.3 only tested hits during the full prop projection (every 2nd frame, skipped
  on busy frames) with a ±22 px depth window, so bullets passed through targets. Now the
  committed prop list stores x (`pc_x`) and a "standing military" flag (`PcMil`). `PropHits`
  corrects each prop's depth by the distance flown since the projection (`pr_acc`). Every 2nd physics
  frame it sweeps each round over two frames of travel. The net widens with altitude (18 + lev/4 px)
  and with the spread lanes. `PropStrike` is the old hit/kill body, shared with the charge blast.
  A kill adds a colour-math flash and a smoke column (two puffs climbing and drifting, 4 s).
* **Effects.** Shockwave ring: FxAt kind 1 adds 6 sparks on an expanding flattened circle (16 frames;
  not during the boss). Muzzle flash at the firing wing, and a charge glow on the nose. Water
  shimmer: the NMI rewrites 6 CGRAM colours (swell, crest, fleck, white, foam, shallows) every 8
  frames from a per-stage table (`assets/shim.bin`, 4 stages x 8 phases). The desert sky is now a
  sunset (warm band and clouds, warmer haze), and the night sky has a city glow near the horizon.
  Boss shoulder pads (`tools/boss_rt.py`) sweep up to the crest and rake inward at the tips. The
  chase sheet still has 20 tiles free.
* **Bug found on the way.** `v14.s` ended in the XCODE segment, so `ApuUpload` (included after it) landed
  in bank $8C and was called with a near `jsr`, which meant no music. `v14.s` now ends with
  `.segment "CODE"`.

**Performance** (RING builds, frame load in scanlines; 262 = a dropped frame). The stage runs use
`rcm.sh` with K=6, with X mapped to SELECT for v1.4, and with `NORANK` so stage progression lines up
with v1.3. The boss uses `bossbench.sh` with K=8.

| Run | Build | over 262 | over 250 | p99 | mean | max |
|---|---|---|---|---|---|---|
| sa0 (chase) | v1.3 | 124 | 896 | 259 | 187.0 | 294 |
| sa0 (chase) | v1.4 | 196 | 1122 | 260 | 188.6 | 295 |
| sa1 (overhead) | v1.3 | 15 | 18 | 214 | 144.1 | 324 |
| sa1 (overhead) | v1.4 | 15 | 20 | 214 | 145.2 | 337 |
| sa2 (cockpit) | v1.3 | 1 | 10 | 237 | 163.2 | 272 |
| sa2 (cockpit) | v1.4 | 2 | 10 | 238 | 164.7 | 275 |
| boss | v1.3 | 6 | 72 | 234 | 138.9 | 285 |
| boss | v1.4 | 11 | 92 | 238 | 138.7 | 283 |

The new hooks cost about 1.5 to 2 lines per frame. To pay for them: ChaseTrails was rewritten (with
the same dots, it is about 2 lines cheaper), the new effects skip work when idle, PropHits runs only
when a military target is listed and on every other frame, and smoke and rings drop to a light
version on busy frames (24+ objects). Heavy chase scenes still drop slightly more frames than v1.3
(0.6% of frames vs 0.4%).

**Verification.** `tools/dev/boss_win_rel.txt` reaches MISSION COMPLETE with the release ROM on snes9x,
snes9x 1.55 (Delta), and Mesen-S. Full run on the same 3 cores: an AUTOPILOT build played from the
title by the harness bot (BOT/BOTPU) clears all four stages, and the boss autopilot wins (BS_DONE
around frame 10,700).

## v1.3: reference-matched boss

**Model.** `tools/boss_rt.py` replaces the voxel boss with an analytic model (convex hulls,
ellipsoids, tapered prisms) that is raytraced offline. Materials are white armour, cobalt, dark
joints, grey ribs, red gem and eyes, and green knee nodes. Lighting uses a cool key and ambient, a
warm orange rim, Blinn-Phong specular, and a little floor bounce. It is supersampled, then
quantized with ordered dither to the 15-colour boss palette (colours 13 and 14 are the animated
eyes and gem). The camera sits low, so the boss towers over the player. Frames: body, damaged body
(scorch and holes at fixed screen spots, mirrored from the clean half), head at 5 yaws, and arms
in down, cannon, and spread poses. Renders are cached in `build/boss_rt_<hash>.pkl` (a cold build
takes about 3 minutes). The cockpit view uses a 0.8 scale and fewer head yaws to fit its sheet.

**Drawing.** `gen_assets.py` writes `BPIdx` entries of 16 bytes (offset, count, fast bounds, first
row dy, rows, `BPRows` offset) and bakes priority into each `BPData` entry per view. When neither
cannon is firing, the body and both arms come from one combined list (`CmbTab`, `BP_CMB`), so
`X_BossDraw` runs 3 passes instead of 5. Each pass finds the first visible row and the first row
past the bottom edge from `BPRows` and copies them with an unrolled loop (up to 96 sprites).
Cells with 10 or fewer opaque pixels are dropped. Chase sheet: 69 cells (20 tiles free); cockpit:
33 cells (12 free).

**Effects.** `BossOrbs` draws the beam charge swirl and the spin ring from precomputed `SwirlTab`
and `SpinTab` positions, split into back and front passes around the body. The `BSHARD` tumbling
object is now an 8-frame blue plasma orb (`tumble_cfg.plasma_frames`). The spin attack charges
(SA_CHARGE), then fires the ring from the chest. Muzzle and pod positions, `EYE_DH` (68), and the
body hit range (-130..200) were updated for the taller model; HP and weak points are unchanged.

**Performance (v1.3 vs v1.2).** `progress/v13/bossbench.sh` runs a RING SKIPTITLE AUTOPILOT build,
warps to the boss, and records 4 shifted runs over frames 700-3600 (11600 frames):

| Build | over 262 | over 250 | p99 | mean | max |
|---|---|---|---|---|---|
| v1.2 | 4 | 33 | 236 | 140.3 | 287 |
| v1.3 | 1 | 25 | 234 | 140.8 | 265 |

Stage runs (rcm.sh sa0, K=6) are identical to v1.2.

**Verification.** `tools/dev/boss_win_rel.txt` (the boss_win replay with title-menu timing)
reaches MISSION COMPLETE with the release ROM on snes9x, snes9x 1.55 (Delta), and Mesen-S.

## v1.2: more sprite stacking

**Boss.** `tools/boss_vox.py` rebuilds the `boss_art.py` parts as voxels. Each part is extruded
with its own depth profile (blades, cylinders, domes), and decal plates carry the visor, eyes,
and collar. Seams between parts come from part IDs, with gamma 1.8 and a light from the upper
left. Every frame is rendered at 208x208, anchored at the chest gem:
* the body, plus a damaged body (holes, scorch rims, soot near 4 spots)
* the head at 0/18/36 degrees (mirrored for left), rendered in a scene with the body so the
  shoulder pads hide the crest correctly
* the arms in down, cannon, and spread poses

`gen_assets.py` cuts the frames into 16x16 cells. It dedupes identical and mirrored cells and
writes `boss_parts.inc`, a per-part cell list with bounds for a fast path when the part is fully
on screen. `X_BossDraw` (src/v11.s) draws the head, left arm, right arm, then the body:
* The head yaw follows `b_sx`, one step every 8 frames.
* The arms are spread during the beam and shard attacks and in cannon pose when that side fires.
  The firing arm recoils 3 px.
* The body uses the damaged frame below 1/3 HP.

The cockpit sheet only has room for the body, the forward head, and the down and cannon arms.
The world-space hit boxes are unchanged.

**Tumbling objects.** `voxstack.tumble_models()` and `tools/tumble_cfg.py` define 8 frame sets
(DEB0, DEB1, MSL, EMSL, PU_P, PU_M, PU_S, BSHARD), each 8 frames of 16x16 (`tumble.bin`, bank
$8F). The sheet keeps one frame of each set. `X_Tumble` (NMI, after `X_Stream`) refreshes it:
* It handles only sets drawn in the committed frame (`tb_cur`, set by `tsb tb_bld` at the
  `AddObj` sites).
* Animation runs at 7.5 fps, with at most one 128-byte upload per vblank, inside the line budget.
* It returns at once when nothing has changed in this phase.

**Ground props.** `voxstack.prop_models_v12()` has 13 models. Each stage maps four slots
(0 water, 1 nature, 2 structure, 3 military) to models (`STAGE_PROPS`, `StageMod`).
* Near frames (16 yaws, 32x32) are in banks $90-$93 and streamed through the six 32x32 slots.
* Mid and far frames (16x16) are uploaded per stage by `X_ViewLoad` (`PropMid`).
* Palette 6 colours 8-15 are set per stage in the stage CGRAM image.
* Bases are 9 per map: the airfield, towns, and open land, plus 3 on open water.
* Prop offsets are pre-rotated for all 256 headings (`PropRot`, banks $94/$95, read through a
  long pointer in direct page). This replaces four multiplies per prop.
* Bases more than 64 px behind the camera's half-plane skip the centre rotation.
* `PRB` dropped from 105 to 90 lines.

**Shootable props.** `PropHit` runs during the projection pass, every other frame. It tests
your rounds against each drawn military prop within 22 px of depth (one 2-frame bullet step)
and 18 px of lateral distance (+24 px for spread lanes). There is no altitude test, so strafing
counts. Each hit gives a spark and a K_FIX-panned tink. The third hit sets the prop's bit in
`pr_dead` (cleared on a stage change or restart), spawns a T_BIGBOOM explosion slot on the ground
(speed 0, so it stays put, with stereo tracking), and gives +300 points (`T_ScoreAdd`).

**Night.** The stage-4 CGRAM image darkens OBJ palettes 0, 3, 6, and 7 (x0.55 R, x0.62 G,
x0.8 B). Lamp, flame, window, and HUD colours keep their values.

**ROM.** The ROM is now 1 MB (header $0A, version $02; v1.3: $03), and banks $90-$95 are used.

**Performance (v1.2 vs v1.1).** The ring harness (`progress/v12/rcm.sh`) runs a RING SKIPTITLE
build over 18 input shifts of each stress script. "Over 262" and "over 250" are frame counts
above those lines.

| Script | v1.1 over 262 | v1.1 over 250 | v1.1 mean | v1.2 over 262 | v1.2 over 250 | v1.2 mean |
|---|---|---|---|---|---|---|
| sa0 (dense) | 330 | 2170 | 181.2 | 376 | 2145 | 186.2 |
| sa1 | 15 | 28 | 143.3 | 19 | 33 | 143.6 |
| sa2 | 46 | 64 | 162.6 | 46 | 78 | 163.3 |

The boss test run (`tools/dev/boss_v12.txt`, frames 900 and later) had 5 frames over 262 (v1.1:
3), with mean lines 141.5 (v1.1: 130.9).

## v1.1: stages, variety, hit feedback, sprite stacking

Most v1.1 code lives in `src/v11.s` (bank $8C, called through `jsl` hooks and `T_x` trampolines into bank 0).

### Sprite stacking (`tools/voxstack.py`)
* **Models**: the plan-form polygons of the v1.0 jet, enemy fighter, bomber, and fortress are voxelized
  (0.4-unit voxels) into solid models: fuselages are filled down to a keel line and wings become thick
  plates. Ground props (control tower, fuel tanks, AA bunker) are built voxel by voxel.
* **Render**: the model is rotated (nose pitch, bank, yaw), sliced into layers, and the layers are
  stacked back to front with a z-buffer at 4x supersampling. Smooth normals come from the blurred
  occupancy field. Each layer's top face gets a highlight, a 4x4 ordered dither runs between ramp
  steps, and a 1-pixel dark outline is added. Colours are the game's existing 15-colour OBJ palette ramps.
* **Frames**: the jet has 15 64x64 frames (5 bank levels x level/climb/dive, mirrored for left banks).
  Enemy fighters have 16 headings (9 unique plus h-flips) at 32x32 and 8 headings at 16x16. Each
  ground prop has 16 headings at 32x32 plus mid and far 16x16 frames. The frame is picked from the
  object's heading relative to the camera.
* **VRAM streaming**: the chase sheet holds one 64x64 jet slot and six 32x32 slots. The frames live in
  ROM banks $8D/$8E. `X_Stream` runs at the end of the NMI, after every other VRAM job, and reads the V
  counter before each upload. A jet frame (2 KB) starts only before line 18 of vblank and a slot (512 B)
  only before line 27, with at most 3 slots per frame. Slots are assigned least-recently-drawn, and an
  object whose frame is not resident yet draws a static fallback frame for that frame. Measured worst
  NMI end is 32 lines into the 37-line vblank (snes9x and Mesen-S). Streaming is off while the boss
  sheet is resident or streaming.
* **Ground props**: grouped into 8 bases per map (airfield, towns, AA sites). A base is culled with one
  box test and one rotation, and its props use 8-bit offset rotations. The full projection runs every
  other frame; in between, props glide on their measured screen velocity. Under load (more than 105
  lines used when props are reached) they glide instead of being re-projected. At most 4 props are drawn,
  and they sort by depth with the other objects.

### Performance (6 input-shifted runs of each 90 s script, snes9x, RING build)
| | v1.0 over262 / over250 / p99 / mean | v1.1 |
|---|---|---|
| chase (sa0) | 4 / 17 / 215 / 124 | 7 / 55 / 225 / 155 |
| overhead (sa1) | 1 / 3 / 221 / 132 | 0 / 1 / 210 / 151 |
| cockpit (sa2) | 0 / 0 / 201 / 116 | 0 / 0 / 213 / 140 |

(over262 = frames that missed 60 fps, out of about 32,000 per row.)

## Title screen and start menu (title v1, current)

ROM: `dist/super_sky_fury.sfc` (also `super_sky_fury_v1.sfc` / `snesfly_title_v1.sfc` locally),
md5 `b35b5e6430852d4708f85912fbc60161`, 512 KB LoROM FastROM, checksum $2264 / complement $DD9B,
internal name `SUPER SKY FURY` (21 bytes, space-padded, generated into `assets/romname.inc`).

### Flow

Power-on -> boot SPC upload (field image, as before) -> blocking swap to the **title** SPC image
(during force blank) -> title screen. START (or A) opens the menu:

* **START GAME**: wipes the RAM with `KEEP_CLEAR` (it saves only `opt_diff`, `opt_mono` and the SPC
  bookkeeping, runs `InitRegs` + `ClearMem`, restores them, then calls `ApplyDiff`). The game
  therefore starts in exactly the power-on state the pre-title builds had. It then swaps to the
  field SPC image and enters the unchanged game (`LoadStatic`/`InitGame`/`LoadView` -> `MainLoop`).
* **OPTIONS**: DIFFICULTY < EASY / NORMAL / HARD >, SOUND < STEREO / MONO >, MUSIC TEST
  < TITLE / STAGE / BOSS / CLEAR > (A plays the song), SOUND TEST < 01-30 > (every game and menu sound
  effect on both SFX channels), and EXIT. Left/right changes a value, A plays, B goes back.
* **CREDITS**: GAME DESIGN AND DIRECTION BY NAVEED FARBAKHSH / DEVELOPED BY NAVEED FARBAKHSH /
  MUSIC AND SOUND: ORIGINAL 16-BIT STEREO SCORE / (C) 2026 NAVEED FARBAKHSH / THANKS FOR PLAYING!
* GAME OVER -> START returns to the title. Building with `-D SKIPTITLE` restores the old direct
  restart.

### Difficulty

| | lives | boss HP base | boss HP cap | enemy fire interval (base) |
|---|---|---|---|---|
| EASY | 7 | 110 | 200 | 150 |
| **NORMAL** (= boss v2 exactly) | 5 | 150 | 262 | 110 |
| HARD | 3 | 200 | 330 | 80 |

These are the variables `d_lives`, `d_hpb`, `d_hpm` and `d_fire`. `attack.s` and `boss.s` read
them where they previously used constants.

### Screen

* Lines 0-87 use Mode 1. A CGRAM HDMA (channel 6) draws the sky gradient. The logo is on BG2: a
  "SUPER" banner over "SKY FURY", set in Russo One (SIL OFL, `tools/fonts/`) with a gradient,
  outline and drop shadow. `tools/title_art.py` renders it to 4bpp tiles. The banner and title
  text come from the constants `GAME_BANNER`, `GAME_TITLE`, `DEVELOPER` and `YEAR`, which also
  generate the ROM header name.
* Lines 88-143 are a Mode 7 ocean band. Its rotation and scroll matrix is written in the NMI. The
  player jet and v-flipped enemy jets fly over it as OBJ priority 2.
* Lines 144-223 are an opaque BG2 panel (priority 1) holding the text. It hides the jets, while
  the cursor jet sits above it at OBJ priority 3.
* BGMODE and TM switch per line by HDMA (channels 5 and 4). The BG2 map is shadowed in WRAM
  ($7F:8000) and DMA'd only when it changes.
* Cursor: a small jet sprite that bobs. Moving up plays a left-panned blip and moving down a
  right-panned one. Confirming plays a chirp that sweeps from left to right.

### Music and SPC images

The title theme is original: 150 BPM, a 2-bar fanfare intro, then A, U and V sections in an
X-style rock arrangement. The intro lasts 3.2 s and the loop 25.5 s. `music/make_boss.py` builds
a third SPC image (title song + menu SFX). All three images (field, boss, title) share one union
upload range table (6 ranges, 17,975 bytes per swap), and only the source bin differs
(BANK8/9/10).

### Mono option

An extra 1-byte block after the ranges writes `opt_mono` to ARAM $004F. When mono is on, the
driver's `wreg` folds each pan into a centred average. It also rewrites EVOL R to the EVOL L
value, because the echo return is phase-inverted on one side. An offline mono render has an L/R
correlation of 1.0000. Changing the option re-sends the image, which gives about 1.25 s of
silence.

### Tests

`tests/title_nav.txt` (navigation through every page, difficulty changes and start), `tests/title_mono.txt`,
`tests/title_video.txt`. Run with `tools/lrharness <core> <rom> <script> <outdir>`.

| core | title/menu/options/credits | game starts | difficulty values | NORMAL = v2 |
|---|---|---|---|---|
| snes9x | OK (reference screenshots) | OK | OK | WRAM-identical to v2 for 3200 frames of the boss_win replay (except SPC bookkeeping and profiling counters) |
| snes9x 1.55 (Delta) | pixel-identical to snes9x | OK | OK | identical until about game frame 560 (see below) |
| Mesen-S | OK | OK | OK | WRAM-identical, as snes9x |
| bsnes (default) | OK (512-wide output) | OK | OK | - |
| bsnes + accuracy options | OK | OK | OK | - |
| bsnes2014 accuracy | checked by RAM (this core's screenshot capture is garbled in the harness for v2 too) | OK | OK | identical until about game frame 560; 0 missed frames in 647 title frames |

The replay offset is 158 frames on every core. On Delta's core and bsnes2014, the boss_win replay
(which alternates input every frame) is latched one frame differently from about game frame 560
onward. v2 itself reads a pad value that is one frame stale. The different upload contents shift
the timing by a fraction of a frame; the game rules are unchanged. `ReadJoy` was deliberately
left as it was. Game over -> title -> second game works (5 lives on NORMAL).

Boot timing: the field upload takes 73 frames (as in v2), the title swap 27 frames, and the title
music is audible at about 2.2 s.

---

# Development history (earlier milestones)

## SNES FLY: a Mode 7 flight demo for real Super Nintendo hardware (original notes)

A SNES remake of the "fly" web demo by @creativedash
(https://x.com/creativedash/status/2122000830895386680). You fly a dark-grey and orange
fighter jet over an endless ocean dotted with islands. There are three camera views:
chase, overhead and cockpit. All art and code are original. The art is generated by
`tools/gen_assets.py`, and none of the demo's assets are used.

* ROM: **`snesfly_boss_v2.sfc`** (current: boss v1 with less boss health, more lives and extra lives;
  a copy of `build/snesfly.sfc`, md5 `fda1337921f706812b3a0bfd89c090d3`, 512 KB, checksum $11BE). See "Boss v2" below.
* `snesfly_boss_v1.sfc`: the first boss build (md5 `7da66526448482d0e8ee271eadde76f5`, checksum $8DAF). See "Boss v1".
* Previous ROM: `snesfly_graphics_v1.sfc` (the graphics overhaul on top of enemies v2,
  md5 `7d1c1f64a70d9d9993e59b0ade1f53ca`, checksum $DC3A). See "Graphics v1" below.
  Older builds are kept: `snesfly_enemies_v2.sfc` (enemies shoot back, md5 `44cd7ec3...`), `snesfly_enemies_v1.sfc` (enemies you can kill, no damage), `snesfly_music_v4.sfc` (music draft 4, no enemies),
  `snesfly.sfc` / `snesfly_music.sfc` (earlier). 256 KB up to graphics v1, 512 KB from boss v1; LoROM + FastROM, no
  enhancement chip, NTSC, valid header and checksum.
* Runs on a real console through a flash cart (EverDrive, FXPak/SD2SNES, etc.) and in
  any SNES emulator (bsnes, snes9x, Mesen).

## Controls

| Button | Action |
|---|---|
| D-pad left/right | turn (the jet banks) |
| D-pad up/down | climb / dive (changes altitude, zoom and horizon scale) |
| Y (hold) | guns: twin cannons, alternating left/right barrel, 10 shots/s |
| A | heat-seeking missile (locks the nearest enemy ahead; 0.75 s reload) |
| B | afterburner: speed up, orange thruster flame (A is no longer thrust) |
| L / R | hard bank (tighter turn, full bank angle) |
| SELECT | cycle view: chase -> overhead -> cockpit (v1.4: X is now the charge shot) |
| X (hold, release) | v1.4 charge shot: a piercing blast once CHARGE READY beeps |
| double-tap L or R | v1.4 barrel roll (26 frames, invulnerable, slides sideways) |
| START | pause; on the GAME OVER screen: play again |
| START, then hold L+R and press SELECT | **debug shortcut**: while paused, clears the sky and jumps straight to the boss (WARNING). Unpause with START |
| SELECT during the boss | cycles chase <-> cockpit only (no overhead, see below) |

Score: 100 per gun kill, 200 per missile kill (shown at the bottom, or on the canopy arch in
the cockpit). You start with 5 lives (the jet icon + digit next to the shield bar) and get an extra
life every 10,000 points (up to 9). Since v2 the enemies attack you: see "Enemy attacks" below.
Dodging: a missile warning (beep + "MISSILE! BREAK L/R" / "MISSILE BEHIND! B:BOOST") tells you what to do:
hard-bank (L/R + d-pad) to out-turn a missile coming at you, afterburner (B) to outrun one on your tail.

## Build

    ./build.sh

This needs `ca65`/`ld65` (cc65 package), `python3` and `numpy` + `Pillow`. The script
regenerates every asset into `assets/`, rebuilds the music (`music/make_music.py`), assembles `src/main.s`, links with
`src/lorom.cfg` and fixes the header checksum (`tools/fixchecksum.py`).

## How it works

* **Ground**: a 128x128-tile Mode 7 map (1024x1024 px) that wraps, so the ocean is endless.
  It is generated procedurally: noise islands with beach, grass, forest and hills, terrace
  "step" shading, shallow-water rings and foam, and wave flecks. It is reduced to 256 unique
  8x8 tiles (open ocean uses 12 hand-made fleck variants; island tiles are k-medoid clustered).
* **Chase / cockpit perspective**: per-scanline Mode 7 matrices through indirect HDMA.
  The trick is that HDMA also writes **BG1VOFS on every line**, so `(line + VOFS - Y0)`
  is constant (= the focal length). That makes `B = C = sin*S` and `D = -A = -cos*S`, so
  each line needs only 2 hardware multiplies instead of 4. Tables are recomputed only when
  heading or altitude changes. They are double-buffered and swapped in vblank, so the
  picture never tears. The 32 lines nearest the horizon get one entry per line; the rest
  share an entry between 2 lines. Per-altitude scale tables (64 levels) are precomputed in ROM.
* **Sky**: HDMA rewrites CGRAM colour 0 every line for the gradient. HDMA also switches
  BGMODE per line: Mode 1 above the horizon, Mode 7 for the ground, Mode 1 for the
  text strip or dashboard. A TM HDMA hides sprites under the text strip.
* **Horizon haze**: COLDATA HDMA with fixed-colour addition on BG1.
* **Overhead view**: flat Mode 7 rotation and zoom; the map turns so the jet always points up.
  Jet and cloud shadows are palette 4 sprites blended at 50% with the ground on the
  sub screen (colour-math half-add), so they are real translucent shadows. Clouds use
  1.25x parallax over their shadows.
* **Cockpit**: the canopy arch and dashboard are BG2 (Mode 1). The radar sweep (16 angles
  from 5 tiles + flips), the attitude ball (bank x pitch frames), the HUD crosshair, the
  pitch ladder and the canopy pillars are sprites. ALT/SPD are BG2 digits rewritten in vblank.
* **HDMA channels**: 1 = M7A/M7B, 2 = M7C/M7D, 3 = BG1VOFS, 4 = TM, 5 = BGMODE,
  6 = CGRAM, 7 = COLDATA. Channel 0 is kept for general DMA, which only runs in vblank
  or forced blank.
* **Game logic** is frame-rate independent: physics catches up if a frame is ever dropped.

## Boss v2 ("give the boss less health and give me more lives")

Only these values and features changed from boss v1. Everything else (attacks, timing, art, music) is identical.

| | Boss v1 | Boss v2 |
|---|---|---|
| Boss HP, first loop | 280 | **150** (`HP_BASE`, `src/boss.s`) |
| Boss HP per later loop | +32 | **+16** |
| Boss HP cap | 480 | **262** (`HP_MAX`, reached on the 8th boss) |
| Lives at start and after GAME OVER -> START | 3 | **5** (`LIVES0`, `src/attack.s`) |
| Extra life | none | **every 10,000 points** (`UP_STEP` = 100 in the game's x100 score units), at most **9** lives (`LIVES_MAX`, one HUD digit) |

* **Phases and damage**: phases still change at 2/3 and 1/3 of his HP, and the damage per hit is unchanged.
  The recorded test replay now beats him in 23 s (v1: 32.6 s).
* **1UP**: when the score crosses a multiple of 10,000 (from kills or the boss bonus), you get a life. For
  2 s, "1UP!" blinks in the shield-bar slot of the HUD (8 frames on, 8 off), and the lives digit updates
  at once.
* **1UP jingle**: a new channel-B SFX (`oneup`, id 12 in `music/make_music.py`). It is a bright rising
  4-note arpeggio, each note bouncing hard left and right, then a shimmering top note that swirls across
  the stereo field (about 0.7 s).
  * If the boss's mega boom or a music upload is busy, the jingle waits and plays right after.
  * It can cut off the tail of the explosion from the kill that earned it.
* **At 9 lives**: the 10,000-point thresholds still move on, but you get no extra life and no flash.
* **Fix**: the wave script no longer starts the boss behind the GAME OVER screen. In v1, waiting about 45 s
  on GAME OVER would trigger the WARNING.
* **Music**: the field music is unchanged. The music image grew by the new SFX stream (`apu.bin` md5
  `5d30998d...`), so the song now starts 76 samples (2.4 ms) later at boot. After alignment, the render
  matches v1 within ±47 out of 32,768.
* **Test builds**: `-D UPTEST=n` starts with score n (x100), and `-D UPLIVES=n` starts with n lives. They
  were used to test the 1UP and the cap.

### Boss v2 tests (`snesfly_boss_v2.sfc`)

| Test | snes9x | snes9x 1.55 (Delta) | Mesen-S |
|---|---|---|---|
| Recorded replay wins (boss HP 150) | yes, 0 drops, worst 254 lines | yes, 0 drops, 260 | yes, 0 drops, 254 |
| Autopilot win, chase | yes, 0 drops, 247 | yes, 0 drops, 244 | yes, 0 drops, 247 |
| Autopilot win, cockpit | yes, 0 drops, 221 | yes, 0 drops, 224 | yes, 0 drops, 221 |
| Idle: 5 deaths -> GAME OVER -> START | 5 lives again, score 0, boss reset, field music back | same | same |

* **Field stress runs** (snes9x): 0 drops in chase (worst 256 lines), overhead 252, cockpit 236. These are
  unchanged from v1.
* **HUD**: shows 5 lives in chase and cockpit.
* **1UP checks** (snes9x, test builds):
  * 9,900 -> 10,000 points gives 5 -> 6 lives, the next threshold moves to 20,000, "1UP!" blinks, and the
    jingle plays, alternating left and right.
  * At 9 lives, crossing a threshold gives no extra life and no flash.
  * 8 -> 9 lives shows "9".
  * A 1UP from the boss bonus plays its jingle after the mega boom, before the music upload.

## Boss v1 ("make him a giant boss you fight at the end of the waves")

Reference: `ref/boss_ref.jpg` (white/silver humanoid robot, blue armour accents, spiky crest, red eyes,
red chest gem, green ankle lights). Comparison of the reference and the sprite in both poses and views:
`shots/boss_sprite_vs_ref.png`. Video (24.8 s, recorded from this ROM in snes9x with its stereo audio):
`shots/gameplay_boss.mp4`. Boss music render: `music/boss.mp3` (plus `music/boss_victory.mp3`, the jingle).

### Reaching the boss

* **Normally**: play through the wave script. After the last wave (`WaveBoss` in `src/combat.s`, just before
  the script loops) the game waits until the sky is clear, then starts the boss. With steady play that is
  about 30 s in (the scripted test runs reach it at about 27 s).
* **Debug shortcut**: press START to pause, hold **L+R** and press **SELECT**. The sky clears, the boss
  WARNING starts at once, and START unpauses. (Code: `BossWarp` in `src/boss.s`, check in `Buttons` in `src/main.s`.)
* After a win, the waves resume one difficulty step harder (`diff` + 1: faster, more aggressive enemies),
  and the next boss has 32 more HP (capped at 480) and shorter gaps between attacks.

### Sequence

1. **WARNING** (about 3.3 s): the field music swaps to the boss track. It opens on a two-bar alarm siren
   (a B/F tritone sweeping left <-> right) and a low drone. A big red flashing "WARNING" fills the sky
   (cockpit view: on the canopy), with "HUGE ENEMY APPROACHING" on the hint row. The boss sprite sheet
   streams into VRAM during this time, 2 rows per frame.
2. **Fly-in** (2.8 s): he drops in from above, growing out of the distance, with thruster flames under his
   boots. A low engine rumble follows his position in the stereo field. The health bar ("BOSS" plus 12
   segments) appears on the top sky row (cockpit: the canopy arch).
3. **Fight**: he hovers ahead of you at a fixed world height, picking a new hover point every 4–6 s and
   bobbing ±5 px. He keeps facing you as you turn. For the first 4 s the hint row reads
   "MATCH HEIGHT - SHOOT GEM/EYES".
4. **Defeat** (2.8 s + 4.8 s): a chain of large explosions across his body, panned to where each one
   pops, plus a mega boom. He shudders and sinks, then vanishes in the last blast. Then "MISSION COMPLETE" and "BONUS 5000"
   (+1000 per loop) land on the victory-jingle fanfare. After that the field music and the waves return.

### Weak points and damage

* **Chest gem**: 1 HP per gun hit. It flashes white and gives a bright hit "tink" (SFX `WEAK`).
* **Eyes**: 2 HP per gun hit. Being higher up, they need a slightly higher approach. They strobe white when hit.
* **Missiles** (A): lock onto the boss and do 6 HP anywhere on the body.
* **Armour**: gun hits elsewhere on the body do no damage. They give a metallic ping (SFX `PING`, panned)
  and a bright impact flash, so you can see you're missing.
* HP: 280 on the first loop. A perfect-aim fight takes about 34 s; the recorded test replay takes 40 s
  and loses one life.

### Attacks (3 phases, at 2/3 and 1/3 HP; each phase has a fixed pattern loop)

| Phase | Pattern | Gap between attacks |
|---|---|---|
| 1 | Cannon, Cannon, Volley | 96 frames |
| 2 | Cannon, Beam, Volley, Cannon | 76 frames |
| 3 | Shards, Cannon, Beam, Volley, Shards, Cannon | 60 frames |

(Gaps shrink by 4 frames per loop, minimum 36.) Every attack is telegraphed:

* **Arm cannon**: he raises one arm for 0.5 s (the raised-arm sprite cells swap in), then fires a fan of
  3/5/7 tracer rounds (by phase) aimed 22 px apart around you, with a muzzle flash at that arm. The SFX
  (`BCANNON`) comes from that arm's side. In phase 3 a second, 3-round fan follows, offset by half a gap.
  Dodge it by turning or climbing out of the fan.
* **Homing volley**: 2/3/4 missiles launch from his shoulders (`BMSL` launch sound per shoulder) and home
  in with smoke trails. Use the usual "MISSILE! BREAK L/R" warning: hard-bank, or boost if one is
  behind you. Each missile whizzes past the ear on its side (`MSW`).
* **Chest beam sweep** (phases 2 and 3): "BEAM! CLIMB OR DIVE" plus a 1 s charge (the gem strobes; the
  `CHARGE` sound rises). The beam locks to the height you were at when the charge began. Then a row of 10
  energy orbs sweeps sideways across the sky at 6 px/frame (`BEAM` SFX panned along the sweep). If you're
  still at the locked height, it's 5 damage. Change altitude during the charge to dodge it.
* **Crest shard burst** (phase 3): his crest glares, then 8 shards fly out in a ring (radius 34 px) and
  spread past you. Each shard whizzes past on its own side (`SHARDW`) and does 3 damage.

### How he is drawn

* **Art** (`tools/boss_art.py`, called by `gen_assets.py`): pixel art in the Capcom 16-bit style,
  modelled on the reference. It uses one 16-colour palette (OBJ palette 7: silver/white ramp, navy and
  blue accents, red, green), dark outlines, and 2–3-step shading lit from the upper left. The left half
  is drawn as 21 16x16 cells (96 x 128 px), and the right half is the same cells horizontally flipped,
  so the whole body is 42 sprites. Arm cells have a raised-arm variant, used for the cannon telegraph.
  There are two sizes: chase (the full sheet) and cockpit (bigger, because he is closer to the camera).
* **VRAM**: the boss sheet takes over the cloud tiles in the sprite sheet while he is up. It streams in
  2 rows per frame during the WARNING and is restored afterwards (`BossNmi`, `b_gfx`). Clouds are hidden
  during the fight.
* **Animation**:
  * hover bob and drift;
  * raised-arm cells for the cannon;
  * flickering boot thrusters;
  * eyes with a slow red glow, and a pulsing chest gem (CGRAM colour animation every frame, `BossColors`);
  * white strobes on hits and during the beam charge;
  * a shudder on missile hits and while dying.
* **Projection**: he is placed in the world (x/z ahead of you, at a height) and projected with the same
  perspective maths as the enemies (`BossProj`). He sits 260 units ahead, at scale 0.615 at his rest height.
* **Fast path** (`tools/boss_fast.py` -> `assets/boss_fast.inc`): if the whole body is on screen, the 42
  OAM entries are built from a precomputed table. Each sprite then needs one 16-bit add for the packed
  `(y<<8)+x` and one tile/attr word copy, about 19 scanlines instead of 46. Near the screen edges a
  checked path clips each piece.

### Stereo sound (the "tickle the ears" brief)

All boss SFX are positional through the existing pan system (`SfxPos`, new sources `K_BOSS` and `K_BEAM`):

* **Cannon blasts**: from the firing arm.
* **Shoulder missile launches**: from each shoulder.
* **Fly-bys**: missiles (`MSW`), shards (`SHARDW`) and tracer rounds (`WHIZ`) pass the ear on their side.
* **Beam**: the sweep pans across.
* **Engine rumble**: follows his screen position while channel B is free.
* **Hits**: armour pings and weak-point "tinks" come from where you hit.
* **Death explosions**: panned per explosion, then a centred mega boom.

The boss music itself is wide too: guitars hard left/right, the lead and harmony on opposite sides with echo,
and crashes and tom fills moving across the field.

### Boss music (original, Mega Man X-style)

An original composition (`music/make_boss.py`; no Capcom melodies are used), E minor (with a D# leading tone), **172 BPM**:

* the WARNING stinger described above;
* a rock kit (kick, backbeat snare, hats, crashes alternating left and right, tom fills rolling left to right);
* **palm-muted 16th-note guitar chugs** on two detuned tracks panned **hard left and hard right**, with
  open power-chord stabs;
* **slap bass** locked to the kick;
* a **minor-key square/saw lead with vibrato** on one side, and a harmony line on the opposite side;
* echo on the lead and harmony (128 ms with feedback). The guitars stay dry and tight.

The track loops (about 64 s, `music/boss.mp3`). When he dies the driver jumps to a short victory jingle
(`music/boss_victory.mp3`): a few silent bars under the explosions, then the fanfare on MISSION COMPLETE.
After that the field image is restored and the **field music is unchanged** (`music/build/apu.bin` is
byte-identical, md5 `8e1aff9a...`).

* **The swap**: the boss song, its 3 new samples and the boss SFX are uploaded through the IPL boot ROM
  into the space the field song uses (17,967 bytes). The upload is non-blocking: it runs 32 bytes at a
  time in the main loop's idle waits. It takes about 0.6 s when idle and up to 1.7 s in a busy field.
  The WARNING holds until it is done.
* **Restore**: the field image is uploaded back the same way.

### Views: overhead is disabled for the boss (chase and cockpit only)

The fight is built around height (match his height to hit the gem or eyes; climb or dive to dodge the
beam) and around reading telegraphs on a big figure ahead of you. The overhead camera looks straight down
and only sees about 100 px ahead, so he would be a blob at the top edge, and neither the height-based weak
points nor the beam dodge would be readable.

* If you are in overhead view when the WARNING starts, the game switches to chase. That costs one frame,
  like any view switch.
* SELECT then cycles chase <-> cockpit only. In cockpit he looms through the canopy, the health bar moves
  onto the canopy arch, and WARNING and MISSION COMPLETE appear on the canopy rows.
* Overhead becomes available again once the field returns.

### Fixes made along the way (they also affect the field)

* **`ScaleR` bug** (`src/combat.s`): the fast path computed `v*|v|` instead of `v*recip`, so objects
  further than z = 160 (and clouds) were misplaced. This was a pre-existing bug, found while placing the
  boss. Far enemies and clouds now sit where they should.
* **Missile trail arrays**: these were sized for 3 enemy missiles and overflowed once there were 4.
  They now have 5 slots.
* **Enemy slots**: the tracer/missile arrays grew to 12/4 for the boss. Wave enemies still use only the
  first 6/2 and the per-frame loops walk only the active range (`eb_lim`/`em_lim`), so the field costs
  and the difficulty stay as in graphics v1.
* **Off-screen sprites**: boss pieces partly off the left edge set the 9th x bit correctly (fixes
  left-edge wraparound).

### Test results (`snesfly_boss_v1.sfc`)

Scripts: `tools/dev/boss_win.txt` is a recorded human replay that wins. Lose run: warp, then no input.
`-D AUTOPILOT` builds an autopilot that matches height, aims and dodges (`AutoPilot` in `src/boss.s`).

| Core | Win | Lose (idle) | Boss frames |
|---|---|---|---|
| snes9x (current) | replay wins, 0 dropped frames (worst 247 lines); autopilot wins in chase (1 drop) and cockpit (0 drops) | game over after about 57 s; boss aborted, sheet and field music restored | max 247–267 lines |
| Mesen-S | replay wins, 0 drops; autopilot wins | same | identical counts to snes9x |
| snes9x 1.55 (Delta 1.55 core) | replay drifts on timing, so not used; autopilot wins, 0 drops | same | max 253 |
| bsnes2014 accuracy | autopilot wins (1 drop) | same | max 268 |
| bsnes (current), default and accuracy settings | autopilot wins: screenshots show the explosions, MISSION COMPLETE, BONUS 5000 and the return to the field; rendering matches snes9x | n/a (no RAM peek) | n/a |

* bsnes_mercury is not tested because it crashes the harness on load.
* "Drop" means a main-loop iteration missed a vblank (`loops` < `nmi_count`). Game logic catches up, so a
  drop is a one-frame visual repeat.
* The one remaining autopilot drop happens in phase 3. A homing volley (3 missiles with trails) lands on a
  frame where turning forces the Mode 7 tables to be rebuilt (about 65 lines). The human replay never
  hits that combination.
* Field (stress scripts `tools/dev/sa0/1/2.txt`, 90 s each): 0 drops in chase (worst 256 lines),
  overhead 251, cockpit 236. This is the same budget as graphics v1 (251/248/277). The only extra frame is
  the forced overhead -> chase switch at the WARNING.

### Trade-offs

* **During the SPC upload** (0.6–1.7 s when the music swaps in and out) there is silence, and the sound
  effects are muted. The swap in is covered by the WARNING; the swap out happens under the MISSION
  COMPLETE hold.
* **Field render difference**: the boss music's state checks make the field-music render not
  bit-identical to graphics v1. The music data is identical, but the driver polls one more port each
  tick. The difference is inaudible (spectral median difference 0.03%).
* **Clouds**: hidden during the boss, because their tiles hold his sheet.
* **Beam orbs**: half of them are drawn each frame (a deliberate shimmer) to keep 60 fps.
* **Cockpit**: his crest overlaps the top of the canopy frame when he flies high.
* **Phase 3 cannon**: the follow-up fan is 3 rounds, so no more than 10 boss rounds are in the air at once
  (60 fps).
* **Overhead view**: not available during the fight (see above).

### Files (boss v1)

    src/boss.s            the boss: states, attacks, weak points, drawing, colours, text, music swap, debug warp, autopilot
    tools/boss_art.py     boss pixel art (from ref/boss_ref.jpg), called by gen_assets.py -> assets/boss*.bin, boss.inc
    tools/boss_fast.py    BossDraw fast-path tables -> assets/boss_fast.inc
    music/make_boss.py    boss song, WARNING stinger, victory jingle, boss SFX, IPL upload ranges -> music/build/boss_up.*, field_up.*
    music/boss.mp3        boss track render; music/boss_victory.mp3: jingle
    shots/boss_sprite_vs_ref.png, shots/gameplay_boss.mp4
    tools/dev/boss_win.txt  recorded winning replay; tools/dev/ringcmp.sh, ring.py: per-frame load logging
    progress/boss/        work-in-progress snapshots and notes

## Graphics v1 ("make the graphics better")

Files: `tools/terrain.py` (new ground generator), `tools/gen_assets.py` (sprites, palettes, sky, HUD,
cockpit, BG3 band), `src/main.s` (BG3 layer, flash colours, PutSpr, cockpit VOFS), `src/combat.s`
(enemy palettes, explosion frames, missile trails). Before/after: `shots/graphics_before_after.png`;
video: `shots/gameplay_graphics.mp4`. Gameplay, timing and music are unchanged (music build is
byte-identical; the scripted test runs give the same scores as v2).

* **Ground** (`tools/terrain.py`): 1 px resolution terrain on the 1024x1024 map with NW lighting
  (slope shading), 46 ground colours. Ocean: 5 depth bands with wave-stroke tiles, a 12 px dithered
  shallows ramp, surf foam plus a broken second surf line. Land: wet and dry beach, a 5-step grass
  ramp with tufts and bushes, forest canopy at 3 light levels, rock with cracks. Man-made features:
  towns on the three biggest islands linked by roads (Dijkstra paths with a turn penalty), an
  airfield with a runway, apron and parked planes, and hedged crop fields in 4 colours. Still 256
  tiles: the ocean and land have separate budgets (48/208), and land is clustered with k-means++
  plus medoid reassignment, with man-made and frequent tiles always kept, so the repetition is far
  lower than v2's.
* **Sky**: a new 5-stop gradient (deep blue to a pale horizon) and a stronger, longer horizon haze
  (64 lines, COLDATA HDMA). A new **BG3 layer** (2bpp, palette 7) draws a band of distant islands
  and a cumulus bank on the horizon in chase and cockpit. It scrolls with your heading
  (BG3HOFS = heading/64, written in vblank) as a parallax layer.
* **Player jet**: re-rendered with per-face Lambert lighting from the upper left, a 16-colour ramp,
  roundels, fin stripe, canopy glint and flaps; all bank frames redone (the top view uses softer
  lighting so banked frames don't go dark).
* **Enemies**: the same shaded renderer. There are three colour schemes by type (red, olive camo,
  navy), set at spawn (`en_pa`) in chase and cockpit. The overhead view keeps the single red
  scheme, because palettes 4-7 are half-blended there for the shadows.
* **Effects**: a new fireball ramp (white core, then orange, then smoke) with embers and smoke rim,
  one extra explosion frame (X16C) at the start of a big blast, smoke puffs, brighter tracers.
  Missile trails: your missile and enemy missiles leave a 4-puff smoke trail (sampled every 2nd
  frame, alternate puffs shown each frame). The hit flash now adds warm white (more red/green
  than blue) and also covers BG3/OBJ/backdrop, so it no longer reads lavender over the sea.
* **HUD**: a Capcom-style font (pale top highlight, warm lower shade, dark outline and drop
  shadow) and framed, bevelled shield-bar segments.
* **Cockpit**: redrawn canopy frame with rim, rivets and warning-light housings; glare-shield lip,
  panel gradient, seams and screws; radar bezel with ticks; 4 dials with ticks and red arcs; a
  lit-ring attitude housing; centre console, digital ALT/SPD panel (matching green backdrop) and
  annunciator buttons.

**VRAM map** (words): Mode 7 $0000-$3FFF, BG1/BG2 tiles $4000, BG3 map $5000 (64x32, only the 3 band
rows are uploaded), BG3 tiles $5800 (reusing the BG1 map area, which is never shown in Mode 1 regions),
BG2 map $5C00, OBJ $6000. All uploads happen at boot or on a view switch with the screen force-blanked.

**CPU**: the extra work (trails, BG3 scroll) is paid for by a faster `PutSpr` (8-bit stores) and a
cockpit-only VOFS table fill. Average load per frame is lower than v2 in every view (chase -0.6,
overhead -1.0, cockpit -3.1 lines over 7 phase-shifted runs of each stress script). Worst frames over
those runs: chase same as v2, overhead 254 vs 251, cockpit 277 vs 280. Still no dropped frames.

## Enemy attacks (v2: "make the enemies attack me")

Files: `src/attack.s` (new), hooks in `src/combat.s` / `src/main.s`, new art in `tools/gen_assets.py`,
new SFX in `music/make_music.py`.

**Who shoots what**
* **Tracers** (head-on and swoop fighters, waves flagged `G`): bursts of 2 + difficulty/2 rounds, 7 frames
  apart, fired when the enemy is 180-640 px ahead and roughly facing you (|x| < z/4); cooldown
  110 - 8*difficulty + random 0-31 frames. Each round is aimed at where you are with a little scatter
  (+/-16 px sideways, +/-8 px vertically), flies at a fixed world speed and is drawn as an orange/red ball
  (two sizes) in the same Mode 7 perspective as everything else, so it rises from the horizon and swells as
  it comes at the camera. Up to 6 tracers in the air.
* **Homing missiles** (waves flagged `M`, and the new **tailer**: an enemy that slides in behind you,
  launches and breaks away): up to 2 in the air, 330 frames of fuel. Guidance turns the missile toward you
  at a limited rate (about 1.75 heading units/frame, + difficulty). A hard bank (2.5 units/frame) out-turns
  one that is coming at you; the afterburner (speed 52 vs. the missile's 46 + 2*difficulty) outruns one on
  your tail until its fuel runs out. A missile that overshoots is marked "missed" and flies on.
  Drawn nose-on (grey body, red nose, flickering yellow exhaust).
* **Ramming**: flying through an enemy (within 12 px, 8 px vertically) costs shield too.

**Damage, shield, lives**
* Shield bar in the HUD ("SH" + 8 cells, green > 8, yellow 5-8, red <= 4) and a lives counter (jet icon + digit).
  Shield 16. Tracer -2, missile -6, ram -5.
* A hit gives a short warm screen flash (COLDATA: red full, green/blue half, fading over ~10 frames), a
  screen shake (up to 4 px, BG + jet sprite), sparks off the airframe and the impact sound on the side
  the hit came from. Then 45 frames of invulnerability (the jet blinks).
* Shield at 0: you are shot down (fireball where you were, debris, the big "die" sound). 2.5 s later you
  respawn with full shield and 150 frames of invulnerability; all enemy rounds and missiles are cleared.
* 3 lives. After the last one: **GAME OVER** in big red letters, FINAL SCORE, "PRESS START TO PLAY AGAIN"
  (Start works after 1 s; the view switches to chase for the screen). Restart resets score, lives, waves.
* Fairness: waves ramp up as before (the difficulty counter grows with each loop of the wave script);
  enemies only open fire when they are ahead and facing you, there is a warm-up cooldown on every spawn,
  and doing nothing but firing loses about 2 lives a minute in wave 1-2 (game over around 75-80 s).

**Stereo SFX for the attacks** (same two borrowed voices, same priority scheme, music data unchanged)
* **Incoming tracer whiz** (channel B, priority 2, 14 frames): starts when a round is within 56 px ahead and
  64 px to the side; the CPU re-sends its pan and volume every other frame while it passes, so it sweeps
  across your head; once it is behind you the driver drops the pitch to 3/4 (Doppler) and phase-inverts
  the right channel (the "behind" cue). The sample itself also falls in pitch.
* **Missile warning beep** (channel A, priority 2): a two-tone "bip" panned live to the missile's side,
  repeating faster as it closes (every 30 frames far away down to every 5 frames).
* **Missile launch rush** (channel B, priority 1) from the launcher's position, and a **dodge whoosh**
  (channel B) when a missile passes within 96 x 80 px without hitting: panned live, Doppler drop behind you.
* **Impact** (channel A, priority 4): metallic crunch + rattle placed hard on the side the hit came from
  (left/right, front/behind).
* **Shot down** (channel B, priority 5, 72 frames): huge boom, crack and tearing rumble, then debris whizzes.
* Protocol v2: port 1 = channel A command, port 2 = channel B command (both (seq<<4)|id); port 3 =
  [channel][behind][pan 0-63], port 0 = [channel][volume 0-127] (channel A volume capped at 125, so $FE,
  the reboot command, never appears). The driver latches pan and volume per channel, so both channels
  can now be panned live (the CPU updates A and B on alternate frames).
* Measured with the music muted (test build): warning beeps on a missile to your left come out at
  L/R balance -0.87 (pan 3), drifting to -0.1 as the missile crosses to centre; impacts from the left
  -0.3 to -0.5, from the right/behind +0.53; whiz -0.1 to -0.2 for rounds passing on the left.
  (A few windows are mixed because the other channel was sounding at the same time.)
* The song stream is byte-identical to v1 except for 688 relocated pointers (the SFX engine grew,
  so the song moved from $482A to $49EB). **ARAM free: 222 bytes** (was 671).

**Frame budget in v2.** The attack code added up to ~35 lines of logic and many more objects, so:
* the frame-load metric is now honest: *NMI time + main-loop work, idle waits excluded* (a frame that
  spills past the next vblank is counted past 262 instead of wrapping);
* overhead clouds farther than 240 px in x or y are culled before rotation (63 -> 25 lines); the
  overhead contrail keeps 8 points (one every 5 frames) instead of 12 (one every 4), so it is a little
  sparser; RotScale uses one 16-bit store to start each hardware multiply;
* OAM: only the entries used last frame but not this one are hidden (was all 128 every frame);
  cockpit canopy pillars are block-copied (MVN) as ready-made OAM entries; inlined shifts/abs in the
  object projection; the cockpit rejects objects outside the windscreen before the second multiply;
* **graceful degradation**: if a frame is already too heavy to fit a Mode 7 matrix-table rebuild
  (heading/altitude changed), the rebuild waits a frame (at most 2 frames running), so in the heaviest
  turning fights the ground rotation can lag your heading by 1-2 frames. Sprites never lag.

## Combat (enemies v1)

Enemies live in jet-relative space (Afterburner style): x = right, z = ahead, 1/16 px units.
When you turn, every object is rotated around you; flying forward pulls them toward you. Their own
heading turns with you too, so they keep their course in the world. They are drawn with the same
focal length as the Mode 7 ground (160) through a reciprocal table (160*256/z, no divides), so they
rise out of the horizon and grow in true perspective. Sprite size steps with depth: 32x32 near
(nose-on or tail-on frame), 16x16 banked/level, then three smaller frames down to a 2-px speck.

Enemy types (red fighters, `src/combat.s` `WaveData`):
* **Head-on**: comes at you from the horizon (900+ px out), sometimes weaving (sine weave of its heading).
* **Crosser** (left->right or right->left): cuts across ahead of you, drawn banked.
* **Overtaker**: comes from behind you, roars past your canopy and pulls away ahead (gives a flyby).
* **Swoop**: dives from 56 px above your altitude toward you, head-on.
* Waves: 3 head-ons; 3 crossers; 2 overtakers; mixed weavers + swoop; mixed; each wave waits for the
  sky to clear. The script loops and gets faster each loop (up to +24 speed).

Weapons and effects: bullets fly at 14 px/frame relative to you (300 px range, 6 in the air max) and
drift sideways correctly when you turn after firing. Missiles accelerate and steer onto their target.
A kill gives a fireball (16 -> 32 px, 2 frames, flicker-flipped) that drifts and slows, then a
smoke puff, plus 4 tumbling debris shards thrown out and toward you with gravity. In the overhead
view enemies are top-down sprites with 8 headings (3 frames + flips).

### Sound effects (all panned; the "tickle the ears" brief)

Two SFX channels borrow music voices only while they sound and give them back afterwards (the
driver shadows every DSP write to those voices, so the music resumes exactly):
* **Channel A = voice 7** (hi-hats / noise cymbals). Priority: gunfire 1, bank swoosh 1, boost 2, debris 2,
  missile launch 3 (a higher or equal priority interrupts).
  * Gunfire: each shot comes from its own barrel side: left shot hard left, right shot hard right
    (measured 18-20 dB L/R difference, alternating every 6 frames).
  * Missile launch: a hiss that sweeps from centre forward and away.
  * Debris whizz: 0.2 s after a close kill, a noise burst sweeps across your head from the side the
    enemy was on to the other side (L->R or R->L).
  * Boost and bank swooshes: as before (bank swooshes sweep in the direction of the bank).
* **Channel B = voice 1** (harmony / lead double). Priority: flyby 1, explosion 3, missile-kill big boom 3.
  * Flyby: when a live enemy passes within 150 px ahead/behind and 110 px to the side, a jet roar
    starts and is panned *live* every frame from the enemy's position.
  * Explosion / big boom: panned live to the wreck as it drifts.
  * Live pan: the 65816 sends pan (port 3: 0-127, plus bit 7 = "behind you") and volume
    (port 0: 0-127, from distance) every frame. Pan = 64 +/- 63*x/(|x|+|z|+8). Behind you, the right
    channel is phase-inverted (a surround-decoder / headphone "behind" cue) and the pitch drops to 3/4
    (Doppler), so a passing jet sweeps front -> side -> behind.
* SFX protocol: port 1 = (seq<<4)|id for channel A, port 2 = (seq<<4)|id for channel B; a new seq
  starts the effect. Port 0 never carries $FE (the driver's reboot command).
* ARAM: 671 bytes free (driver $021C, SFX engine + streams $03DD, song ends $BD61 below the echo buffer).

### Frame budget (60 fps)

Measured worst main-loop end line (out of 262 per frame; vblank starts at 0) while firing, turning,
climbing and killing, on snes9x, Delta's snes9x 1.55 core, bsnes2014 accuracy and Mesen-S:
chase 249, overhead 222, cockpit 234, and 0 dropped frames. To pay for combat:
* matrix tables: exact entries 0-11, every 2nd to 31, every 4th after, the rest linearly
  interpolated; all 64 altitude scale tables copied once to WRAM ($7E:2000) so nothing is copied per frame;
* clouds: visibility culling (2 culled clouds re-tested per frame), clouds beyond 120 px re-projected
  every other frame and moved at their measured screen velocity in between, and a persistent depth order;
  far chase-view clouds use a new 16x16 sprite;
* sprites: OBSEL per view (chase 16/64, cockpit 16/32, overhead 32/64) to free VRAM for the enemy
  art; a faster PutSpr; objects bucketed into depth bands so clouds and planes overlap correctly;
* overhead view: rotation + zoom folded into one set of 8-bit coefficients per frame.

## Music, draft 4 (current: `snesfly_music_v4.sfc`)

A full-length piece: a 15.4 s build-up intro, then a 147.5 s loop (96 bars), for 2:43 before the
first repeat. The flybys are no longer in the music; the whoosh sample is kept for the in-game
boost and bank SFX. Draft 3 is kept as `snesfly_music_v3.sfc`, `build/snesfly_draft3.sfc`,
`music/make_music_draft3.py`, `music/build_draft3/` and `music/draft3.*`.

Structure (bars at 156 BPM, 1.536 s each):
1. Intro (10 bars, not repeated): hats ping-pong L/R; brass swells slide in from alternating sides;
   lead/harmony pad swells cross the stereo field; muted bass pulse -> pumping octaves -> 16ths;
   kick, then snare; tom rolls panning L->R; brass hits alternating sides; the rising lead line over
   a crescendo snare roll; one beat of silence; full-band hit into the loop.
2. A (8): main theme, lead + wide double.  3. A' (8): with harmony on the other side.
4. B (8): climbing second theme.  5. C (4): bridge, four on the floor.
6. D (8): new contrasting theme in F major, dotted/syncopated melody.  7. D' (8): with harmony and
   busier brass, drum break at the end.
8. E (8): funky breakdown, a slap-bass solo (pentatonic runs, octave pops, ghost notes) over light
   drums with sparse brass stabs crossing the stereo field.
9. F (8): brass soli: the left brass calls, the right brass answers, then both together in harmony;
   the lead punches in from the middle.
10. G (8): tension: quiet pulse, slow brass swells sweeping between the sides, lead pad notes rising,
    tom rolls, snare comes back, builds to a B major chord.
11. A, A', B again a whole step up (E minor), the climax (24 bars).
12. C bridge back in D minor, which leads into the loop.

Engine changes:
* The SPC700 driver is now a 5-track sequencer (lead, harmony, brass, bass, drums), each with its own
  pointer, wait counter and CALL/RET. The song is compiled bar by bar per track (half-bars for bass
  and drums); identical bars are stored once and CALLed. Stream commands: `$00-$7F` reg/value,
  `$80-$FB` wait 1-124 ticks, `$FC` CALL, `$FD` RET, `$FE` JMP, `$FF n` transpose on/off.
* Key change for free: `$FF 1` makes the driver multiply that track's pitch writes by 287/256
  (+2 semitones, 2 cents flat) with `MUL YA`, so the E-minor climax reuses the A/A'/B bar data.
* KON/KOFF from all tracks are OR-ed and written once per tick (KOFF every tick).
* Crash and open hat are now the S-DSP noise generator (NON on voice 7, 32 kHz noise clock) with
  exponential-decay envelopes, which freed 11 KB of samples. NON is shadowed like the voice-7 registers,
  so the SFX borrow/restore still works.
* ARAM: driver `$0200` (580 bytes), directory `$0500`, samples `$0520`, SFX tables `$46DE`, song data
  `$476E` (30.0 KB; 74.6 KB before de-duplication), end `$BCA5`, **859 bytes free**, echo
  `$C000-$FFFF` (EDL 8 = 128 ms).
* Width (bsnes accuracy, 168 s render): corr 0.575, side/mid -5.7 dB, mono fold loss -1.0 dB, peak
  -3.1 dBFS, no clipping (intro corr 0.69, loop 0.57).

## Music, draft 3 (current: `snesfly_music_v3.sfc`)

Draft 3 is draft 2 with a 10-bar (15.4 s) build-up intro instead of the 4-bar opening. The main loop,
stereo work and in-game SFX are unchanged, and the loop point is still right after the intro.
Draft 2 is kept as `snesfly_music_v2.sfc`, `build/snesfly_draft2.sfc`, `music/make_music_draft2.py`,
`music/build_draft2/`, `music/main_draft2.s` and `music/draft2.*`.

* Bars 1-2: near silence. Quiet hi-hat ticks ping-pong left/right, and a distant jet passes right to left.
* Bars 3-4: a muted, quiet bass pulse on D enters, the hats move to 16ths, and a closer jet passes left to right.
* Bars 5-6: the kick comes in four-on-the-floor, the bass starts pumping octaves, and the snare joins on the backbeat in bar 6.
* Bars 7-8: brass stabs enter, each hit hard on one side and alternating L/R. A third jet comes from
  "behind you", and an open hat whips across.
* Bars 9-10: the lead (with its wide double) climbs D-E-F-G-A-Bb-C#. Brass hits every beat, the bass drives in
  16ths, and the snare rolls 8ths -> 16ths -> 32nds in a crescendo. A big jet swells from behind and tears across.
  The band then stops for one beat, and the loop's downbeat lands as a full-band hit with the crash.
* The swing now starts with the main loop (the build is straight).
* ARAM: song stream 19.6 KB; to make room the echo is now EDL 8 = 128 ms (an 8th-note triplet) at
  `$C000-$FFFF`. Data ends at `$BE1A` (486 bytes free).
* Width (bsnes accuracy): whole render corr 0.55 / side-mid -5.4 dB; intro corr 0.62; loop corr 0.54;
  mono fold loss -1.1 dB; peak -3.3 dBFS, no clipping.

## Music, draft 2 (current: `snesfly_music_v2.sfc`)

Draft 2 keeps the melody and chords of draft 1 and changes the mix and the rhythm section.
Draft 1 is kept as `snesfly_music.sfc` / `music/snesfly_music_draft1.sfc`, `music/make_music_draft1.py`,
`music/build_draft1/` and `music/draft1.*`.

* **Tempo** 156.25 BPM (was 150). Tick = 1/96 note = 16 ms (timer divider 128), so 16ths can swing
  by one tick (58% swing from bar 2 on).
* **Groove**: funk slap bass with dead-note ghosts and octave pops (two alternating bar patterns,
  7ths chosen per chord), syncopated kicks, ghost snares, swung 16th hats with an open hat that
  chokes, a half-bar snare/tom mini-break in bar 4 of each phrase, and a drum break at the end of
  every section (bass + brass drop out, snare 16ths + 32nd pickups, toms rolling L->R).
* **Stereo**: lead slightly left; a detuned (+9 cents), 1-tick-late (16 ms Haas) copy of the lead on
  the right during A and B; harmony on the right in A' and C; brass stabs hard L/R, swapping
  sides every hit, and long stabs sweep across each other; bass, kick and snare centre; hats right
  with the open hat whipping R->L; toms pan L->R; crash with a phase-inverted right side.
* **Flybys**: a looped-noise "jet" sample with per-tick pitch drop, volume swell and pan travel
  (Doppler-style) on every section break plus two in the intro; some start phase-inverted ("behind you").
* **Echo**: EDL 9 = 144 ms (a dotted 16th) at ESA `$B800` (`$B800-$FFFF`, checked by an assert so it
  can never wrap into page 0), FIR low-pass (repeats get darker), EFB `$50`, EVOL L `$26` / R `-$1A`
  (repeats spread around the listener). Echo writes stay off (FLG bit 5) while ESA/EDL settle
  (300 ms), the buffer is flushed with EVOL/EFB at 0, then the echo is faded in. EON is switched per
  note: melody, brass, backbeat snares, crash, open hat and flybys are echoed; kick, bass, closed
  hats and ghost notes stay dry.
* **In-game SFX** (new): the driver watches APU port 1. `SfxEvents` in `src/main.s` writes
  `(seq << 2) | id` to `$2141`: 1 = afterburner whoosh on pressing B/A (rushes in from behind and
  past), 2/3 = wind swoosh when a hard bank to the left/right begins (pans across the same way).
  The SFX borrows voice 7 (hi-hats) for 0.5 s; the driver shadows voice-7 registers and the song's
  KOFF, masks voice-7 writes/KON/KOFF while the SFX plays, then restores them.
* **ARAM map**: `$0200` driver (296 bytes), `$0400` sample directory, `$0430` BRR samples, song
  stream (~17 KB), SFX tables (144 bytes, end `$B562`), echo `$B800-$FFFF`.
* Width (bsnes accuracy, whole 62 s render): L/R correlation 0.98 -> 0.50, side/mid -20.9 dB ->
  -4.8 dB, mono fold-down loss -0.03 dB -> -1.3 dB (worst 100 ms window -3.8 dB), peak -3.4 dBFS, no
  clipping. Measure with `python3 music/width.py file.wav`.
* Files: `music/draft2.{wav,mp3,spc}`, `shots/gameplay_music_v2.mp4` (headphone demo with boosts and
  hard banks, script `tools/demo_v2.txt`), `shots/mesen2_v2_dsp_probe.png`.

## Music (draft 1 notes)

`music/` holds the in-flight track, **"Afterburner Squadron" (draft 1)**: an original
150 BPM D-minor action theme in the style of Capcom's U.N. Squadron (SNES, 1991). It does
not copy any existing melody. Everything is generated by `music/make_music.py`:

* **Instruments** are synthesized in Python (additive synth brass with a filter "blat",
  a bright lead, a slap bass, kick, snare, closed/open hat, crash) and encoded to **BRR**
  by `music/brr.py`, an encoder that uses the exact S-DSP decode rules.
* **Driver**: a tiny custom SPC700 player (74 bytes at ARAM `$0200`, hand-assembled in
  `driver_code()`). The song is pre-compiled into a stream of S-DSP register writes plus
  waits. 1 tick = 1/64 note = 25 ms, from timer 0. Vibrato on long lead notes is baked
  into the stream as per-tick pitch writes.
* **Voices**: 0 lead, 1 harmony (doubles as part of the intro chord), 2-3 brass stabs
  (panned L/R), 4 slap bass, 5 kick (+ toms = the kick pitched up), 6 snare, 7 hats/crash.
  Echo is ~96 ms (about a sixteenth note), on lead, harmony, stabs and snare.
* **ARAM map**: `$0200` driver, `$0300` sample directory, `$0400` BRR samples (~28 KB),
  then the song stream (~11 KB, ends `$9EDE`), echo buffer `$C000-$EFFF`.
* **ROM integration**: `music/build/apu_upload.inc` (generated) holds `ApuUpload`, which
  sends the 40 KB ARAM image through the standard IPL boot-ROM protocol and starts the
  driver. It runs once at reset, right after `ClearMem`, with NMI off and the screen
  blanked. This adds about 1 s of black screen at power-on. The data lives in BANK5/BANK6
  (the ROM is still 256 KB). After boot the S-CPU never touches the APU again, so the
  music costs no 65816 CPU time.
* **Preview**: `music/draft1.mp3` / `.wav` are recorded from the ROM itself running in
  bsnes (accuracy mode), so they are what the console plays. `music/draft1.spc` plays in
  any SPC player. `music/render_spc.py` renders an .spc through libgme (note that libgme
  plays about 1.5x louder than bsnes/snes9x). `shots/gameplay_music.mp4` is a gameplay
  capture with the music.
* The test harness records audio when `LR_AUDIO=out.raw` is set (s16le stereo, at the
  core's rate: 48 kHz for bsnes, 32040 Hz for snes9x).

Structure: intro 4 bars (6.4 s: full-band chord hits, snare roll, groove), then a 44.8 s
loop: A (8 bars, main theme), A' (the theme with a harmony a third below, plus a new
ending), B (8 bars, climbing second theme that resolves on a bright D major), C (4-bar
bridge with long notes, pumping bass and 4-on-the-floor), then back to A.

## Hardware-safety notes

* All VRAM/CGRAM/OAM DMA happens in vblank (NMI) or with the screen force-blanked. A
  view switch force-blanks for one frame while it reloads VRAM.
* Mode 7 centre/scroll registers are written only in vblank. Matrix, VOFS, TM, BGMODE,
  CGRAM and COLDATA changes during the frame are done only by HDMA (in hblank).
* No general DMA ever runs while HDMA is active (this avoids the 5A22 v1 DMA/HDMA
  collision bug).
* The APU upload waits for the IPL's `$BBAA` ready signal (one 16-bit read of `$2140/$2141`)
  and checks every byte's echo. The `$BBAA` wait has a ~3 s timeout: if the APU never answers,
  the game starts without music instead of hanging on a black screen.
* Block "kick" values follow the IPL rule (2..127 above the last index, nonzero) and are never
  `$AA` or `$FE`, so a stale port value can't be mistaken for the ready signal.
* CPU-only resets (flash-cart in-game reset, where the SPC700 keeps running): `ApuUpload` first
  writes `$FE` to `$2140`. The driver checks port 0 every tick, and on `$FE` it sets FLG = `$E0`
  (soft reset, mute, echo writes off), re-enables the IPL ROM with ports cleared (`$F1 = $B0`)
  and jumps to `$FFC0`, so the normal upload runs again. On a cold boot the IPL ignores `$FE`
  (it only reacts to `$CC`).
  The driver keeps echo writes disabled until EDL/ESA have settled (300 ms), and only
  then enables echo with zero volume and feedback, so no stray RAM is overwritten or heard.
* All PPU and CPU registers are initialised at reset; WRAM and VRAM are cleared by DMA;
  unused sprites are parked off-screen.
* The main loop waits for the auto-joypad read to finish before reading `$4218`.
* CPU budget (snes9x, worst case while turning, boosting and changing altitude): chase
  view peaks at line 238 of 262, overhead 221, cockpit 214, so it holds a steady 60 fps.
  `loops`/`maxline` in WRAM are debug counters (`tools/perf.sh` reads them).

## Testing

Graphics v1: `tools/dev/gfxshots.sh ROM outdir core` takes 16 fixed screenshots (all three views) from
the sa0/1/2 runs; `tools/dev/pair.py` builds the before/after sheet; `tools/dev/ringcmp.sh` compares
per-frame load (RING build) between builds.

| core | chase (worst load / drops) | overhead | cockpit | screenshots | sa0/1/2 score |
|---|---|---|---|---|---|
| snes9x | 251 / 0 | 248 / 0 | 277 / 0 * | reference | 8 / 8 / 15 |
| snes9x 1.55 (Delta) | 251 / 0 | 248 / 0 | 277 / 0 * | 16/16 pixel-identical | same |
| Mesen-S | 252 / 0 | 248 / 0 | 277 / 0 * | 16/16 pixel-identical | same |
| bsnes (default) | - | - | - | 16/16 pixel-identical | same (same frames) |
| bsnes accuracy mode | - | - | - | 16/16 pixel-identical (512-wide output, even columns) | same |

(The sa2 cockpit run now plays out differently from v2 after a few minutes, because frame timing
changed slightly, so its score differs from v2's; across 7 phase-shifted cockpit runs the worst
frame is 277 vs v2's 280.)

Enemies v2 table (previous build):

Enemies v2 (attacks): scripted runs in `tools/dev/` (`sa0/1/2.txt`: 90 s of random steering, guns,
missiles, boost and banking in chase / overhead / cockpit, taking hits and losing lives; sa0 ends in
GAME OVER; `rec_attack_C.txt` also presses Start and checks the restart). Helpers: `tools/dev/pk.sh`
(peek variables by label at the end of a run), `tools/dev/trace.sh` (per-frame variable trace, via the
harness' new `TRACE`/`TRACEOUT` env), `tools/dev/qb.sh` (variant builds: `-D RING` per-frame load log at
$7F:0000, `-D PROFX` per-section timings, `-D SFXDBG` / `-D NOSFX` SFX logging/muting; `MUTESONG=1
python3 music/make_music.py` builds a silent song for SFX measurements; none of these are in the ROM).

| core | chase (worst load / drops) | overhead | cockpit | sa0 game over | restart |
|---|---|---|---|---|---|
| snes9x | 251 / 0 | 244 / 0 | 276 / 0 * | yes, score 000800 | yes (score 0, 3 lives) |
| snes9x 1.55 (Delta's core) | 251 / 0 | 244 / 0 | 276 / 0 * | yes, identical | - |
| Mesen-S | 251 / 0 | 244 / 0 | 276 / 0 * | yes, identical | yes |
| bsnes (default) | no RAM peek: same hit frame (1192) and same GAME OVER screen/score as snes9x | | | yes | |
| bsnes accuracy mode | same as bsnes default (VRAM blocking outside vblank, random RAM) | | | yes | |

Load = NMI time + main-loop work in scanlines (262 = one frame). Drops = NMIs minus main-loop passes over
5425 frames (the last frame of each run is still being built when the run stops, so 1 is reported as
"loops = nmi - 1" there). * A few of the heaviest cockpit frames (turning while ~25 objects are on
screen) need slightly more than one frame of CPU; the main loop then runs a little ahead into the idle
time of the next frame, and no frame is dropped. NMI handler ends at most 7 lines into vblank.
The game is deterministic: every core produced the same hits, deaths and final score from the same
inputs. `shots/accuracy/attack_acc_hit_gameover.png` is the bsnes accuracy-mode hit + GAME OVER.

`shots/gameplay_attack.mp4` (28.0 s, 512x448 60 fps H.264, AAC 48 kHz stereo, snes9x core) is edited from two
scripted runs: 0-13.3 s = frames 300-1100 of `rec_attack_A.txt` (tracers coming in, three hits with
flash/shake/side-panned impacts, kills, a missile on your tail, a hard break to the right and the missile
missing with a whoosh), 13.3-18.6 s = frames 1450-1770 (a missile hit that shoots you down, respawn),
18.6-28 s = frames 4180-4740 of `rec_attack_C.txt` (last life lost, GAME OVER, FINAL SCORE, Start ->
new game). Video and sound are the emulator's own output, cut at the same frames.
`shots/gameplay_graphics.mp4` (25.0 s, 512x448 60 fps H.264 crf 18, AAC 192k 48 kHz stereo, snes9x):
chase = sa0 frames 850-1350, overhead = sa1 frames 600-1050, cockpit = sa2 frames 450-1000.
`shots/gameplay_attack.png`: tracers incoming (left) and a missile break (right).

Enemies v1: `tools/demo_enemies.txt` is the scripted combat run used for
`shots/gameplay_enemies.mp4` (28 s, H.264 + AAC 48 kHz stereo, bsnes core, 11 kills) and
`shots/gameplay_enemies.png`; `shots/accuracy/enemies_acc_*.png` are from bsnes in accuracy mode.
`tools/perf.sh <core>` measures the frame budget (build with `-D PROFX` for per-section timings).


`tools/lrharness.c` is a small headless libretro frontend: a scripted joypad plus PPM frame
dumps (`tools/shoot.sh`, `tools/demo.txt`, `tools/perf.sh`). Cores are in `tools/cores/`
(nightly libretro builds of bsnes and snes9x).

* **bsnes** (default options) is used for the screenshots and video in `shots/`.
* **bsnes in accuracy mode**: `CORE_OPTS="$(cat tools/bsnes_accuracy_opts.txt)"`. This
  turns off the fast PPU, fast DSP and fast math; turns on VRAM-write blocking outside
  vblank and the sprite-per-line limit; disables the HD Mode 7 enhancements; and starts
  from randomized power-on RAM ("High" entropy). Output matches the normal run:
  `shots/accuracy/`.
* **snes9x**: identical rendering, and used for the CPU-budget measurements.

### Audio compatibility matrix (music RMS per second, s16, first 9-10 s)

Every core below plays the music (second 0 is the boot upload, then RMS ~3700-5200):

| Emulator / core | Used by | Result |
|---|---|---|
| Snes9x **1.55 (rileytestut/snes9x @ 3ab93fc, the exact core inside Delta on iPhone)**, built as a libretro core: `tools/cores/snes9x155delta_libretro.so` | Delta (iOS) | music OK, same samples as current snes9x |
| snes9x (current libretro) | RetroArch, many apps | music OK |
| snes9x2010 / snes9x2005 / snes9x2005_plus / snes9x2002 | low-end, mobile and web frontends | music OK (2002/2005 use the old APU and play ~1-2 dB louder, occasional peaks clip) |
| bsnes (default + accuracy options), bsnes_hd_beta, bsnes2014 accuracy/balanced, bsnes_mercury_balanced, bsnes_cplusplus98 | RetroArch, OpenEmu-style frontends | music OK |
| Mesen-S (libretro) | RetroArch | music OK |
| Mesen2 2.1.1 standalone (Lua probe of DSP state) | desktop | driver running, FLG = $00, MVOL = $30, voice envelopes peak at 127 every second |

The CPU-only-reset path was tested with a variant ROM that calls `ApuUpload` a second time 2 s
into the music: in every core above the music stops, re-uploads in under 1 s and restarts.

If the ROM is silent on a phone, check the device first. In Delta: Settings > Game Audio >
turn off "Respect Silent Mode" (or flip the ringer switch off silent), check volume, Focus/Do
Not Disturb, Sound Recognition and the Bluetooth output. Delta keys games by file hash, so
make sure you're launching the new import, not the earlier no-music `snesfly.sfc`.
* The Debian bsnes-mercury-accuracy core could not be used: it segfaults inside its own
  `retro_init` on this machine.

## Simplified compared with the web demo

* No roll of the horizon. Mode 7 perspective can't rotate the screen plane, so banking
  is shown on the jet sprite, the attitude ball and the contrail curve.
* Clouds are flat sprites in 2 sizes (near and far) rather than truly scaled. There are
  16 clouds in the world; that number is limited by CPU time, since each one is projected
  in software every frame.
* Contrails are dotted sprite trails (7 dots per wingtip in chase, 12 history points per
  wingtip overhead).
* Jet pitch is not modelled: up/down changes altitude, and the HUD ladder and attitude
  ball show the climb or dive.
* Music only (one looping track, see `music/`); no sound effects yet. The music keeps
  playing while paused.
* A is an alternate thrust button rather than a barrel roll.

## Files

    src/main.s          65816 source (ca65): main loop, NMI, views, rendering
    src/combat.s        enemies, waves, your weapons, object projection, SFX channels
    src/attack.s        v2: enemy tracers + missiles, shield/lives/game over, HUD rows, live SFX panning
    tools/dev/          v2 test scripts and helpers (stress runs, trace/peek, video scripts)
    src/snes.inc        register definitions + macros
    src/boss.s          boss v1: the giant robot boss (see "Boss v1")
    src/v17.s           v1.7: medals, stage events (convoy / storms / flak), checkpoints + continue
    src/v18.s           v1.8: animation streaming (jet, enemy, explosion, flame cells), dad face, recoil
    src/lorom.cfg       linker config (LoROM FastROM, 64 x 32 KB banks = 2 MB since v1.8)
    tools/terrain.py    graphics v1: Mode 7 ground generator (terrain, towns, roads, airfield, tiles)
    tools/gen_assets.py procedural art, palettes, perspective/sin tables, HDMA tables
    tools/boom17.py     v1.7: ray-traced glossy explosion / smoke frames used by gen_assets.py
    tools/boom18.py     v1.8: 40-frame explosion sequence, 16-frame afterburner and boss thruster frames
    tools/fixchecksum.py
    tools/lrharness.c   headless libretro test harness
    assets/             generated binaries (+ preview_map.png, sheet_*.png)
    shots/              screenshots, contact_sheet.png, gameplay.mp4, gameplay.gif,
                        gameplay_music.mp4, gameplay_enemies.*, gameplay_attack.mp4/.png,
                        graphics_before_after.png, gameplay_graphics.mp4
    music/make_music.py instruments, BRR, song, SPC700 driver, upload code, draft1.spc
    music/brr.py        BRR encoder (exact S-DSP decode rules)
    music/render_spc.py render an .spc to WAV through libgme
    music/draft1.*      draft 1 preview (mp3/wav recorded from the ROM in bsnes) + .spc
    music/build/        generated ARAM image, upload blocks, apu_upload.inc
