; =====================================================================
;  SUPER SKY FURY v1.1 -- hit feedback, power-ups, new enemies, the sky fortress (mid-boss),
;  kill combos and four stages (each with its own ground palette, sky and haze; two Mode 7 maps).
;  Included from main.s.  The bank-0 hooks are small `jsl X_...` calls; the code lives in its own
;  bank (XCODE = $8C) and runs with DB = $80 (low RAM, registers: absolute), its own ROM data is
;  read with f: (long).  Bank-0 routines are reached through the T_ trampolines below.
; =====================================================================
T_BOMBER = 8                ; armoured bomber: slow, 8+ hits, guns, always drops a power-up
T_KAMI   = 9                ; kamikaze diver: homes on you and rams, blinks red
T_DART   = 10               ; dart: fast weaving fighter, flies in V / line formations
T_FORT   = 11               ; sky fortress: mid-boss, holds station ahead, wing guns + missiles
T_STAGE  = $83              ; script: next stage (fade, new ground / sky / haze, banner)
SA_TINK  = 11               ; field image: bullet on armour (live pan)
SB_PICKUP = 13              ; field image: power-up collected
NPU      = 2                ; power-up capsules in the air
NPOP     = 2                ; floating score / damage numbers (2 dynamic 32x16 OBJ slots)
NFX      = 4                ; impact sparks (screen space)
PU_LIFE  = 540
PP_LIFE  = 50
COMBO_T  = 150              ; kills within 2.5 s chain the multiplier (x2, x3, x4)
FORT_Z   = 240*16           ; the fortress holds station this far ahead
FORT_HW  = 56               ; ... and is this wide (hit half-width, px)
GL_PLUS  = 10
GL_X     = 11
GL_ORNG  = 12               ; + 12: orange set
GL_BLANK = 24

SS_SLOTS = 6                ; v1.1 sprite-stack 32x32 stream slots
.ifndef PRB
PRB = 90                    ; (v1.2: 105 -> 90 to pay for tumbling + more props)
.endif
.ifndef PR_EVERY
PR_EVERY = 2                ; ground props: full projection every n frames (2 or 4)
.endif
.ifndef PR_MAX
PR_MAX = 4                  ; ground props drawn per frame
.endif
.segment "ZEROPAGE"
pr_rp:   .res 3             ; v1.2: long pointer to this heading's PropRot row
.segment "BSS"
en_hp:  .res NEN*2
en_mx:  .res NEN*2
en_hf:  .res NEN*2          ; hit flash (frames)
en_hw:  .res NEN*2          ; hit box half-width (px)
en_sx:  .res NEN*2          ; screen position last frame (sparks / numbers)
en_sy:  .res NEN*2
hitstop: .res 2
bright: .res 2
combo_n: .res 2
combo_t: .res 2
p_spread: .res 2
p_rapid: .res 2
ms_reload: .res 2
pu_t:   .res NPU*2
pu_k:   .res NPU*2
pu_x:   .res NPU*2
pu_z:   .res NPU*2
pu_cyc: .res 2
pu_kc:  .res 2
pp_t:   .res NPOP*2
pp_x:   .res NPOP*2
pp_y:   .res NPOP*2
pp_g:   .res NPOP*8
pp_dirty: .res 2
pp_next: .res 2
pp_ds:  .res 2              ; slot of the running damage counter, $FFFF none
pp_dv:  .res 2              ; its value
fx_t:   .res NFX*2
fx_x:   .res NFX*2
fx_y:   .res NFX*2
fx_k:   .res NFX*2
fx_n:   .res 2
stage:  .res 2
st_next: .res 2
cur_map: .res 2
cur_pal: .res 2
st_tr:  .res 2
st_t:   .res 2
msg_a:  .res 2
msg_b:  .res 2
msg_t:  .res 2
msg_at: .res 2
bar_lag: .res 2
bar_cur: .res 2
bar_fl: .res 2
bar_lt: .res 2
fort_i: .res 2
b_jit:  .res 2
b_jt:   .res 2
b_rcp:  .res 2
v_hx:   .res 2
v_dmg:  .res 2
stg_hz: .res 2
b_dark: .res 2
x_t:    .res 2
x_k:    .res 2
x_i:    .res 2
b_stp:  .res 2
b_ja:   .res 2
pf_f:   .res 2
pf_sx:  .res 2
pf_sy:  .res 2
pf_a:   .res 2
bu_ln:  .res NBU*2          ; bullet lanes (1 centre, 2 left, 4 right)
x_bx:   .res 2
q_xy:   .res 2
x_dx:   .res 2
x_j:    .res 2
x_of:   .res 2
x_so:   .res 2
x_ln:   .res 2
v_lx:   .res 2
v_lane: .res 2
n_t:    .res 2              ; (NMI-private)
n_i:    .res 2
n_k:    .res 2
; v1.1 sprite stacking (streamed OBJ frames)
js_want: .res 2             ; chase jet frame wanted (0..JS_N-1) / in VRAM ($FFFF = unknown)
js_have: .res 2
ss_want: .res SS_SLOTS*2    ; 32x32 slots: frame wanted / frame in VRAM / build stamp of last use
ss_have: .res SS_SLOTS*2
ss_use:  .res SS_SLOTS*2
ss_fc:   .res 2
ss_u:    .res 2
ss_up:   .res 2             ; (NMI-private) uploads this vblank
pr_i:    .res 2
pr_n:    .res 2
pr_dx:   .res 2
pr_dy:   .res 2
pr_r0:   .res 2
pr_r1:   .res 2
pr_z:    .res 2
pr_x:    .res 2
pr_gy:   .res 2
pr_hs:   .res 2
pr_ph:   .res 2
pr_ld:   .res 2
pr_m:    .res 2
pc_n:    .res 2
pc_id:   .res PR_MAX*2
pc_sx:   .res PR_MAX*2
pc_gy:   .res PR_MAX*2
pc_vx:   .res PR_MAX*2
pc_vy:   .res PR_MAX*2
pc_u:    .res PR_MAX*2
pc_fr:   .res PR_MAX*2
pc_z:    .res PR_MAX*2
pn_id:   .res PR_MAX*2
pn_sx:   .res PR_MAX*2
pn_gy:   .res PR_MAX*2
pn_u:    .res PR_MAX*2
pn_fr:   .res PR_MAX*2
pn_z:    .res PR_MAX*2
pn_vx_t: .res PR_MAX*2
pn_vy_t: .res PR_MAX*2
pr_ch:   .res 2
pr_b:    .res 2
pr_be:   .res 2
pr_k:    .res 2
pr_cz:   .res 2
pr_cx:   .res 2
pr_t:    .res 2
pr_sg:   .res 2
b_hy:    .res 2             ; v1.2 boss head yaw (part id 2..6)
tb_i:    .res 2             ; (NMI-private) tumble round robin
tb_n:    .res 2
tb_bld:  .res 2             ; tumbling sets drawn by the frame being built (bit = set) / by the committed one
tb_cur:  .res 2
tb_tab:  .res 2
tb_hv:   .res 16            ; frame in VRAM per list entry ($FFFF unknown)
tb_ph:   .res 2             ; phase whose lap found nothing to upload ...
pr_ax:   .res 2
.ifdef PROPDBG
pd_proj: .res 2
pd_box:  .res 2
pd_rot:  .res 2
pd_scan: .res 2
pd_acc:  .res 2
.endif
;            ; v1.2: base cull axis (0 cos-major: dy, 2 sin-major: dx)
pr_dead: .res 10            ; v1.2: destroyed military props (bit per PropOff entry)
pr_hid:  .res 2             ; last prop hit (PropOff offset) ...
pr_hc:   .res 2             ; ... and its hits so far
.ifdef PROPTEST
pr_dbg:  .res 2
pr_dbz:  .res 2
pr_dbb:  .res 2
.endif
tb_pc:   .res 2             ; ... with these sets drawn
bp_n:    .res 2             ; (X_BossDraw scratch)
bp_d:    .res 2
bd_vo:   .res 2
bp_e:    .res 2             ; part loop end (5, or 3 with a merged body + arms list)             ; 0 chase, BPIdx_cock-BPIdx_chase in the cockpit
bp_sx:   .res 2
bp_sy:   .res 2
bp_k:    .res 2
bp_l:    .res 8

; ---------------------------------------------------------------- bank-0 trampolines
.segment "CODE"
T_Rand:      jsr Rand
             rtl
T_RotTerm:   jsr RotTerm
             rtl
T_KillEnemy: jsr KillEnemy
             rtl
T_SfxA:      jsr SfxA
             rtl
T_SfxB:      jsr SfxB
             rtl
T_LoadView:  jsr LoadView
             rtl
T_PutTxt:    jsr PutTxt
             rtl
T_BossSky:   jsr BossSky
             rtl
T_HudText:   jsr HudText
             rtl
T_ScaleR:    jsr ScaleR
             rtl
T_AddObj:    jsr AddObj
             rtl
T_Project:   jsr Project
             rtl
T_ProjOver:  jsr ProjOver
             rtl
T_FireEB:    jsr FireEB
             rtl
T_BossSegs:  jsr BossSegs
             rtl
T_BossWarnRow: jsr BossWarnRow
             rtl
T_BossBoomL: jsr BossBoom
             rtl
T_RelTrig:   jsr RelTrig
             rtl
T_LoadNow:   jsr LoadNow
             rtl
T_ScoreAdd:  clc                 ; v1.2: A = points (x100) -> score, HUD, extra lives
             adc score
             cmp #10000
             bcc :+
             lda #9999
:            sta score
             jsr ScoreText
             jsr ScoreLife
             rtl

.segment "XCODE"
.a16
.i16

; ---------------------------------------------------------------- game start / restart
X_GameInit:                 ; (InitCombat: LoadStatic has just loaded map A + the stage-0 palette)
  stz cur_map
  stz cur_pal
  jsr ResetRun
  rtl
X_Restart:                  ; (RestartGame: back to stage 1, reload the world if it changed)
  jsr ResetRun
  lda cur_map
  ora cur_pal
  beq :+
  jsl T_LoadView
: rtl

ResetRun:
  jsr PrRevive
  lda #$0F
  sta bright
  stz stage
  stz st_tr
  stz hitstop
  stz combo_n
  stz combo_t
  stz p_spread
  stz p_rapid
  lda #2
  sta pu_cyc                ; first capsule: SPREAD
  lda #3
  sta pu_kc                 ; ... after the 4th kill
  stz bar_lag
  stz bar_fl
  stz b_jit
  stz b_jt
  stz b_dark
  stz b_stp
  lda #45
  sta ms_reload
  lda #$FFFF
  sta fort_i
  sta pp_ds
  ldx #NPU*2-2
: stz pu_t,x
  dex
  dex
  bpl :-
  ldx #NPOP*2-2
: stz pp_t,x
  dex
  dex
  bpl :-
  ldx #NFX*2-2
: stz fx_t,x
  dex
  dex
  bpl :-
.ifdef WARP
  lda #WARP*2
  asl
  tax
  lda f:WarpTab,x
  sta wave_pos
  lda f:WarpTab+2,x
  sta stage
  lda #30
  sta wave_tm
.endif
  lda stage
  jsr Banner
  rts

; stage banner: A = stage -> "STAGE n" / name in the sky for 3 s
Banner:
  asl
  tax
  lda f:StTxtA,x
  sta msg_a
  lda f:StTxtB,x
  sta msg_b
  lda #$3000
  sta msg_at
  lda #200
  bra MsgSet
; A = text (row 3 only), Y = attr, 100 frames
Msg:
  sta msg_b
  sty msg_at
  stz msg_a
  lda #110
MsgSet:
  sta msg_t
  lda row_dirty
  ora #RD_SKYA|RD_SKYB|RD_WARN
  sta row_dirty
  rts

; ---------------------------------------------------------------- Spawn: per-type setup
; X = slot*2, t0 = type
X_SpawnInit:
  stz en_hf,x
  lda #1
  sta en_hp,x
  sta en_mx,x
  lda #HIT_X
  sta en_hw,x
  lda t0
  cmp #T_BOMBER
  bcs :+
  rtl
: cmp #T_BOMBER
  bne @nb
  lda diff
  asl
  clc
  adc #8
  sta en_hp,x
  sta en_mx,x
  lda #18
  sta en_hw,x
  stz en_hd,x
  lda #20
  sta en_dh,x
  lda #$0C
  sta en_pa,x
  lda #30
  sta en_spd,x
  rtl
@nb:
  cmp #T_KAMI
  bne @nk
  lda #$8000
  sta en_hd,x
  lda diff
  asl
  asl
  clc
  adc #50
  sta en_spd,x
  lda #$06
  sta en_pa,x
  rtl
@nk:
  cmp #T_DART
  bne @nd
  lda #$8000
  sta en_hd,x
  lda diff
  asl
  asl
  clc
  adc #74
  sta en_spd,x
  lda #$0E
  sta en_pa,x
  rtl
@nd:
  ; T_FORT
  lda diff
  asl
  asl
  asl
  asl
  clc
  adc #60
  cmp #400
  bcc :+
  lda #200
: sta en_hp,x
  sta en_mx,x
  lda #FORT_HW
  sta en_hw,x
  stz en_hd,x
  lda #28
  sta en_dh,x
  lda #$0E
  sta en_pa,x
  lda #10
  sta en_spd,x
  stx fort_i
  lda #24
  sta bar_lag
  stz bar_fl
  lda row_dirty
  ora #RD_BOSS
  sta row_dirty
  lda #.loword(TX_FORTW)
  ldy #$3800
  jsr Msg
  lda #160
  sta msg_t
  stz sfx_nfx
  lda #200
  sta sfx_nfz
  lda #K_FIX
  sta sfx_nk
  lda #SA_BEEP
  ldx #4
  ldy #10
  jsl T_SfxA
  ldx fort_i
  rtl

; ---------------------------------------------------------------- per physics step
X_Step:
  ; combo window, power-up timers
  lda combo_t
  beq :+
  dec combo_t
  bne :+
  stz combo_n
: lda p_rapid
  beq :+
  dec p_rapid
: lda #45
  ldx p_rapid
  beq :+
  lda #16
: sta ms_reload
  lda p_dead                ; shot down: the gun power-ups are lost
  beq :+
  stz p_spread
  stz p_rapid
: lda b_jt                 ; boss hit jolt: +-b_ja px, alternating every 2 frames
  beq @nj
  dec b_jt
  lda b_ja
  ldx b_jt
  cpx #0
  beq @nj
  txa
  and #2
  beq :+
  lda b_ja
  bra :++
: lda b_ja
  jsr XNeg
: sta b_jit
  bra @j
@nj:
  stz b_jit
@j:
  jsr EnemyStep
  jsr PuStep
  jsr PopStep
  jsr FxStep
  jsr BarStep
  jsr BossFx
  jsr StageStep
  rtl

EnemyStep:
  ldx #0
@l:
  lda en_st,x
  bne :+
  jmp @n
: lda en_hf,x
  beq :+
  dec en_hf,x
: lda en_st,x
  cmp #ST_LIVE
  beq :+
  jmp @n
: lda en_ty,x
  cmp #T_BOMBER
  bne @nb
  lda fwd                   ; you slowly overtake it from behind: ~20/16 px per step
  sec
  sbc #20
  bpl :+
  lda #0
: sta en_spd,x
  lda en_z,x                ; once it's close it climbs away over your canopy
  cmp #120*16
  bcs :+
  lda en_t,x
  and #3
  bne :+
  inc en_dh,x
: jmp @n
@nb:
  cmp #T_KAMI
  bne @nk
  lda en_t,x                ; blink red / white
  and #8
  beq :+
  lda #$0A
  bra :++
: lda #$06
: sta en_pa,x
  lda en_z,x                ; homes in while it is in front of you
  bmi @n
  lda en_x,x
  bmi :+
  sec
  sbc #9
  bpl @kx
  lda #0
  bra @kx
: clc
  adc #9
  bmi @kx
  lda #0
@kx:
  sta en_x,x
  lda en_t,x
  and #3
  bne @n
  lda en_dh,x
  beq @n
  bmi :+
  dec en_dh,x
  bra @n
: inc en_dh,x
  bra @n
@nk:
  cmp #T_FORT
  bne @n
  jsr FortStep
@n:
  inx
  inx
  cpx #NEN*2
  beq :+
  jmp @l
: rts

; X = fortress slot: comes in, holds station ahead, sways side to side, bobs, extra wing fire
FortStep:
  stz en_hd,x               ; always faces your way
  lda en_z,x
  cmp #FORT_Z
  bcc @hold
  lda fwd
  sec
  sbc #28
  bpl :+
  lda #0
: sta en_spd,x
  bra @sway
@hold:
  lda fwd
  sta en_spd,x
  lda en_z,x                ; (turning swings it round you: ease it back)
  cmp #FORT_Z-40*16
  bcs @sway
  clc
  adc #16
  sta en_z,x
@sway:
  stx x_i
  lda en_t,x
  asl
  and #$01FE
  tax
  lda f:SinTab,x
  ldx x_i
  asl
  asl
  asl
  asl
  asl                       ; +-255 * 32 = +-8160 = +-510 px ... scaled below
  cmp #$8000
  ror
  cmp #$8000
  ror                       ; +-127 px * 16
  sec
  sbc en_x,x
  cmp #$8000
  ror
  cmp #$8000
  ror
  cmp #$8000
  ror
  cmp #$8000
  ror
  clc
  adc en_x,x
  sta en_x,x
  ; bob
  lda en_t,x
  and #31
  bne :+
  lda en_t,x
  and #32
  beq @up
  dec en_dh,x
  bra :+
@up:
  inc en_dh,x
: ; wing guns: a pair of tracers every ~1.1 s once on station
  lda en_z,x
  cmp #FORT_Z+8*16
  bcs @r
  lda en_t,x
  and #63
  cmp #17
  bne @r
  lda p_dead
  ora gameover
  bne @r
  lda en_x,x
  pha
  sec
  sbc #44*16
  sta en_x,x
  jsl T_FireEB
  ldx x_i
  lda en_x,x
  clc
  adc #88*16
  sta en_x,x
  jsl T_FireEB
  ldx x_i
  pla
  sta en_x,x
@r:
  ldx x_i
  rts

; ---------------------------------------------------------------- hits on wave enemies
; Hits: X = enemy slot, Y = bullet slot (the bullet is inside the hit box)
X_BulletHit:
  lda bu_ln,y               ; that lane is spent; the round goes when all its lanes are
  eor v_lane
  sta bu_ln,y
  bne :+
  sta bu_d,y
: stx x_i
  lda v_lx
  sta t6                    ; hit lane x px
  jsr HitSpark
  ldx x_i
  lda en_hp,x
  dec a
  sta en_hp,x
  beq @kill
  bmi @kill
  ; armour took it: white flash, knocked back, metallic tink where it hit, number for the fortress
  lda #4
  sta en_hf,x
  lda en_z,x
  clc
  adc #3*16
  sta en_z,x
  jsr Tink
  ldx x_i
  cpx fort_i
  bne :+
  lda #1
  jsr DmgNum
  jsr FortBar
: ldx x_i
  rtl
@kill:
  lda #1
  jsl T_KillEnemy
  ldx x_i
  rtl

; MoveMissile: your missile reached enemy X
X_MissileHit:
  stx x_i
  lda en_sx,x
  sta t0
  lda en_sy,x
  sta t1
  lda #1
  jsr FxAt                  ; big flash at the impact
  lda #2
  sta hitstop
  lda #6
  jsr Shake
  ldx x_i
  lda en_hp,x
  sec
  sbc #6
  beq @kill
  bmi @kill
  sta en_hp,x
  lda #6
  sta en_hf,x
  lda en_z,x
  clc
  adc #10*16
  sta en_z,x
  stx sfx_ni
  lda #K_EN
  sta sfx_nk
  lda #SB_BOOM
  ldx #3
  ldy #40
  jsl T_SfxB
  ldx x_i
  cpx fort_i
  bne :+
  lda #6
  jsr DmgNum
  jsr FortBar
  lda #4
  sta bar_fl
: ldx x_i
  rtl
@kill:
  stz en_hp,x
  lda #2
  jsl T_KillEnemy
  ldx x_i
  rtl

; metallic hit SFX on channel A, panned live at enemy x_i
Tink:
  ldx x_i
  stx sfx_ni
  lda #K_EN
  sta sfx_nk
  lda #SA_TINK
  ldx #2
  ldy #7
  jsl T_SfxA
  rts

; spark where the round struck: enemy x_i's screen spot, nudged toward the bullet (t6 = bullet x px)
HitSpark:
  ldx x_i
  lda en_x,x
  ASR4
  sta t0
  lda t6
  sec
  sbc t0                    ; bullet - enemy (px), at most +-hit width
  cmp #$8000
  ror
  clc
  adc en_sx,x
  sta t0
  jsl T_Rand
  ldx x_i
  and #7
  sec
  sbc #4
  clc
  adc en_sy,x
  sta t1
  lda #0
  ; fall through
; A = kind (0 spark, 1 big flash, 2 weak-point burst), t0/t1 = screen x/y
FxAt:
  sta x_k
  lda fx_n
  inc a
  inc a
  cmp #NFX*2
  bcc :+
  lda #0
: sta fx_n
  tax
  lda x_k
  sta fx_k,x
  lda t0
  sta fx_x,x
  lda t1
  sta fx_y,x
  lda #6
  ldy x_k
  beq :+
  lda #9
: sta fx_t,x
  rts

; A = shake frames (keeps the larger)
Shake:
  cmp shake_t
  bcc :+
  sta shake_t
: rts

; ---------------------------------------------------------------- kills: points, combo, big-kill juice
; KillEnemy calls this first: X = slot, o_f = 1 (gun) / 2 (missile) -> A = points (x100)
X_KillPts:
  stx x_i
  lda combo_t
  beq :+
  lda combo_n
  cmp #4
  bcs :++
  inc combo_n
  bra :++
: lda #1
  sta combo_n
: lda #COMBO_T
  sta combo_t
  inc pu_kc                 ; every 7th kill leaves a capsule too
  lda pu_kc
  cmp #7
  bcc :+
  stz pu_kc
  jsr DropPU
  ldx x_i
: lda en_ty,x
  cmp #T_BOMBER
  bne @nb
  lda #2                    ; big boom
  sta o_f
  lda #3
  sta hitstop
  lda #10
  jsr Shake
  lda #3
  jsr FlashMin
  jsr DropPU
  lda #5
  bra @mul
@nb:
  cmp #T_FORT
  bne @nf
  lda #2
  sta o_f
  jsr FortDown
  lda #30
  jsr ScorePop
  lda #30
  bra @r
@nf:
  cmp #T_KAMI
  bne :+
  lda #2
  bra @mul
: lda o_f                   ; standard fighters / darts: 1, missile kill 2
  cmp #2
  bne :+
  lda #2
  sta hitstop
  lda #4
  jsr Shake
  lda #2
: 
@mul:
  sta t0
  ldx combo_n
  lda #0
: clc
  adc t0
  dex
  bne :-
  sta t0
  jsr ScorePop
  lda t0
@r:
  ldx x_i
  rts
; (called with jsl from KillEnemy)
X_KillPtsL:
  jsr X_KillPts
  rtl

FlashMin:
  cmp flash_t
  bcc :+
  sta flash_t
: rts

; the fortress goes down: a chain of big explosions across its span, shake, flash, power-ups
FortDown:
  lda #$FFFF
  sta fort_i
  lda row_dirty
  ora #RD_BOSS
  sta row_dirty
  lda #4
  sta hitstop
  lda #40
  jsr Shake
  lda #8
  jsr FlashMin
  lda #2
  jsr DropKind
  lda #0
  jsr DropKind
  ldx x_i
  lda #.loword(-40*16)
  jsr BigBoomAt
  lda #40*16
  jsr BigBoomAt
  lda #0
  jsr BigBoomAt
  ldx x_i
  rts

; A = x offset (1/16 px) from slot x_i: one T_BIGBOOM explosion if a slot is free
BigBoomAt:
  sta t0
  ldy #0
: lda en_st,y
  beq @ok
  iny
  iny
  cpy #NEN*2
  bne :-
  rts
@ok:
  ldx x_i
  lda #ST_BOOM
  sta en_st,y
  lda #T_BIGBOOM
  sta en_ty,y
  lda en_x,x
  clc
  adc t0
  sta en_x,y
  lda en_z,x
  sta en_z,y
  lda en_dh,x
  sta en_dh,y
  lda #0
  sta en_hd,y
  sta en_hf,y
  lda fwd
  sta en_spd,y
  tya
  and #6
  eor #$FFFF
  inc a
  clc
  adc #6
  sta en_t,y                ; staggered a few frames
  rts

; ---------------------------------------------------------------- power-ups
; drop one from slot x_i: bombers cycle spread / missiles / shield (skipping a spread you have)
DropPU:
  lda pu_cyc
  inc a
  cmp #3
  bcc :+
  lda #0
: sta pu_cyc
  cmp #0
  bne DropKind
  ldy p_spread
  beq DropKind
  lda #1
  sta pu_cyc
; A = kind
DropKind:
  sta x_k
  ldy #0
: lda pu_t,y
  beq @ok
  iny
  iny
  cpy #NPU*2
  bne :-
  rts
@ok:
  ldx x_i
  lda x_k
  sta pu_k,y
  lda en_x,x
  sta pu_x,y
  lda en_z,x
  bmi :+
  cmp #60*16
  bcs :++
: lda #60*16                ; never right on top of you: you get to fly into it
: sta pu_z,y
  lda #PU_LIFE
  sta pu_t,y
  rts

PuStep:
  ldx #0
@l:
  lda pu_t,x
  bne :+
  jmp @n
: dec pu_t,x
  bne :+
  jmp @n
: stx x_i
  lda pu_z,x                ; your turn swings it round you, flying forward brings it closer
  jsl T_RotTerm
  ldx x_i
  eor #$FFFF
  sec
  adc pu_x,x
  sta pu_x,x
  jsl T_RotTerm
  ldx x_i
  clc
  adc pu_z,x
  sec
  sbc fwd
  sta pu_z,x
  cmp #.loword(-60*16)
  bpl :+
  stz pu_t,x
  bra @n
: cmp #160*16              ; magnet: inside 160 px it drifts in towards your nose
  bpl @nm
  lda pu_x,x
  cmp #$8000
  ror
  cmp #$8000
  ror
  cmp #$8000
  ror
  sta x_t
  lda pu_x,x
  sec
  sbc x_t
  sta pu_x,x
@nm:
  lda pu_z,x
  ; collect: inside +-22 px, from 14 px behind to 26 px ahead
  cmp #.loword(-14*16)
  bmi @n
  cmp #26*16
  bpl @n
  lda pu_x,x
  jsr XAbs
  cmp #22*16
  bcs @n
  lda p_dead
  ora gameover
  bne @n
  stz pu_t,x
  lda pu_k,x
  jsr Collect
  ldx x_i
@n:
  inx
  inx
  cpx #NPU*2
  beq :+
  jmp @l
: rts

; A = kind 0 spread, 1 rapid missiles, 2 shield
Collect:
  cmp #1
  beq @m
  bcs @s
  lda #1
  sta p_spread
  lda #.loword(TX_PUP_P)
  bra @t
@m:
  lda #60*20
  sta p_rapid
  lda #.loword(TX_PUP_M)
  bra @t
@s:
  lda p_shield
  clc
  adc #8
  cmp #SHIELD_MAX
  bcc :+
  lda #SHIELD_MAX
: sta p_shield
  jsl T_HudText
  lda #.loword(TX_PUP_S)
@t:
  ldy #$3400
  jsr Msg
  stz sfx_nfx
  lda #4
  sta sfx_nfz
  lda #K_FIX
  sta sfx_nk
  lda #SB_PICKUP
  ldx #5
  ldy #14
  jsl T_SfxB
  rts

; Weapons: X = the new bullet's slot (A = gun SFX, kept). Spread gun: the same round carries two
; extra lanes at +-8 degrees (bu_ln bits 2 / 4): one bullet to move, hit-test and project, 3 to see and hit with.
X_Spread:
  pha
  lda #1
  ldy p_spread
  beq :+
  lda gun_side              ; alternate rounds carry the left / right lane (half the sprites of 3 streams)
  asl
  inc a
  inc a
  inc a                     ; 3 or 5
: sta bu_ln,x
  pla
  rtl

; lane offset (px) at range bu_d,x: d * 0.14
LaneOff:
  lda bu_d,x
  lsr
  lsr
  lsr
  sta x_of
  lsr
  lsr
  lsr
  clc
  adc x_of
  sta x_of
  rts

; Hits: bullet Y is level with enemy X (t1 = enemy x px): test its live lanes; carry set = hit (done)
X_LaneHit:
  lda bu_x,y
  sta x_bx
  sec
  sbc t1
  sta x_dx
  lda bu_ln,y
  and #1
  beq @l
  lda x_dx
  jsr XAbs
  cmp en_hw,x
  bcs @l
  lda x_bx
  sta v_lx
  lda #1
  bra @hit
@l:
  lda bu_ln,y
  and #6
  beq @no
  phx
  tyx
  jsr LaneOff
  plx
  lda bu_ln,y
  and #2
  beq @r
  lda x_dx
  sec
  sbc x_of
  jsr XAbs
  cmp en_hw,x
  bcs @r
  lda x_bx
  sec
  sbc x_of
  sta v_lx
  lda #2
  bra @hit
@r:
  lda bu_ln,y
  and #4
  beq @no
  lda x_dx
  clc
  adc x_of
  jsr XAbs
  cmp en_hw,x
  bcs @no
  lda x_bx
  clc
  adc x_of
  sta v_lx
  lda #4
  bra @hit
@no:
  clc
  rtl
@hit:
  sta v_lane
  jsl X_BulletHit
  sec
  rtl

; chase / cockpit: bullet c_i projected (sx, sy, t1, t5 = scale): its lanes
X_BulDraw:
  ldx c_i
  lda bu_ln,x
  sta x_ln
  lda #F_BUL0
  ldy t1
  cpy #120
  bcc :+
  lda #F_BUL1
: sta x_k
  lda obj_pri
  sta o_a
  lda sx
  sta x_t
  lda x_ln
  and #6
  beq @c
  jsr LaneOff
  lda x_of
  jsl T_ScaleR
  sta x_so
@c:
  lda x_ln
  and #1
  beq :+
  lda x_k
  jsl T_AddObj
: lda x_ln
  and #2
  beq :+
  lda x_t
  sec
  sbc x_so
  sta sx
  lda x_k
  jsl T_AddObj
: lda x_ln
  and #4
  beq :+
  lda x_t
  clc
  adc x_so
  sta sx
  lda x_k
  jsl T_AddObj
: rtl

; overhead: bullet c_i (t0 = x, t1 = d) after ProjOver succeeded for the centre
X_BulDrawO:
  ldx c_i
  lda bu_ln,x
  sta x_ln
  lda #$30
  sta o_a
  lda x_ln
  and #1
  beq :+
  lda #F_BUL0
  jsl T_AddObj
: lda x_ln
  and #6
  beq @r
  ldx c_i
  jsr LaneOff
  lda x_ln
  and #2
  beq :+
  ldx c_i
  lda bu_x,x
  sec
  sbc x_of
  jsr @one
: lda x_ln
  and #4
  beq @r
  ldx c_i
  lda bu_x,x
  clc
  adc x_of
  jsr @one
@r:
  rtl
@one:
  sta t0
  ldx c_i
  lda bu_d,x
  sta t1
  jsl T_ProjOver
  bcc :+
  lda #$30
  sta o_a
  lda #F_BUL0
  jsl T_AddObj
: rts

; ---------------------------------------------------------------- floating numbers
; A = points (x100) at enemy x_i's last screen spot: "+N00" (white) and "xM" (orange) for a combo
ScorePop:
  sta t2
  jsr PopSlot               ; -> Y = slot*2, X = glyph offset
  ldx x_i
  lda en_sx,x
  sta pp_x,y
  lda en_sy,x
  sec
  sbc #14
  sta pp_y,y
  jsr PopClear
  ; top row: + d d 0 0 (4 cells): N <= 9 -> "+N00", N >= 10 -> "NN00"
  ldx t3
  lda t2
  cmp #100
  bcc :+
  lda #99
: cmp #10
  bcs @two
  A8
  lda #GL_PLUS
  sta pp_g,x
  lda t2
  sta pp_g+1,x
  bra @zz
@two:
  A16
  ldy #0
: cmp #10
  bcc :+
  sbc #10
  iny
  bra :-
: A8
  sta pp_g+1,x
  tya
  sta pp_g,x
@zz:
  A8
  stz pp_g+2,x
  stz pp_g+3,x
  A16
  lda combo_n
  cmp #2
  bcc @d
  A8
  lda #GL_X+GL_ORNG
  sta pp_g+5,x
  lda combo_n
  clc
  adc #GL_ORNG
  sta pp_g+6,x
  A16
@d:
  jmp PopDirty

; running damage counter (fortress / boss): A = damage, t4/t5 = screen spot
DmgNum:
  sta t2
  ldx x_i
  lda en_sx,x
  sta t4
  lda en_sy,x
  sta t5
DmgNumAt:
  ldy pp_ds
  bmi @new
  lda pp_t,y
  beq @new
  cmp #PP_LIFE-24           ; still young: keep counting in the same slot
  bcc @new
  lda pp_dv
  clc
  adc t2
  sta t2
  bra @draw
@new:
  jsr PopSlot
  sty pp_ds
  lda t4
  sta pp_x,y
  lda t5
  sec
  sbc #18
  sta pp_y,y
@draw:
  lda t2
  cmp #999
  bcc :+
  lda #999
: sta t2
  sta pp_dv
  lda #PP_LIFE
  sta pp_t,y
  tya
  asl
  asl
  sta t3
  jsr PopClear
  ; right-aligned orange digits in cells 3, 2, 1
  lda t3
  clc
  adc #3
  sta t6
@dg:
  lda t2
  ldx #10
  jsr XDiv                  ; A = t2 / 10, t7 = remainder
  sta t2
  ldx t6
  lda t7
  clc
  adc #GL_ORNG
  A8
  sta pp_g,x
  A16
  dec t6
  lda t2
  bne @dg
  jmp PopDirty

; -> Y = slot*2 (oldest), t3 = glyph offset (slot*8), timer started
PopSlot:
  lda pp_next
  eor #2
  sta pp_next
  tay
  cpy pp_ds
  bne :+
  lda #$FFFF
  sta pp_ds
: lda #PP_LIFE
  sta pp_t,y
  tya
  asl
  asl
  sta t3
  rts
; blank the 8 cells of the slot at t3
PopClear:
  ldx t3
  A8
  lda #GL_BLANK
  sta pp_g,x
  sta pp_g+1,x
  sta pp_g+2,x
  sta pp_g+3,x
  sta pp_g+4,x
  sta pp_g+5,x
  sta pp_g+6,x
  sta pp_g+7,x
  A16
  rts
PopDirty:
  lda t3
  lsr
  lsr                       ; slot*2
  tax
  lda f:Bit1,x
  ora pp_dirty
  sta pp_dirty
  rts
Bit1: .word 1, 2

PopStep:
  ldx #0
@l:
  lda pp_t,x
  beq @n
  dec pp_t,x
  and #1
  beq @n
  lda pp_t,x
  cmp #PP_LIFE-30
  bcc @n                    ; rises for half a second, then hangs
  dec pp_y,x
@n:
  inx
  inx
  cpx #NPOP*2
  bne @l
  rts

FxStep:
  ldx #0
: lda fx_t,x
  beq :+
  dec fx_t,x
: inx
  inx
  cpx #NFX*2
  bne :--
  rts

; A / X (X 8-bit value) -> A quotient, t7 remainder (hardware divider)
XDiv:
  sta WRDIVL
  A8
  txa
  sta WRDIVB
  A16
  nop
  nop
  nop
  nop
  nop
  nop
  nop
  nop
  lda RDMPYL
  sta t7
  lda RDDIVL
  rts

XAbs:
  bpl :+
XNeg:
  eor #$FFFF
  inc a
: rts

; ---------------------------------------------------------------- boss / fortress health bar
FortBar:
  ldx fort_i
  bmi @r
  lda row_dirty
  ora #RD_BOSS
  sta row_dirty
@r:
  rts

BarStep:
  lda bar_fl
  beq :+
  dec bar_fl
  bne :+
  lda row_dirty
  ora #RD_BOSS
  sta row_dirty
: lda bar_lag               ; the "recent damage" segment drains after a short hold
  cmp bar_cur
  beq @r
  bcc @up
  lda bar_lt
  beq :+
  dec bar_lt
  rts
: lda #3
  sta bar_lt
  dec bar_lag
  lda row_dirty
  ora #RD_BOSS
  sta row_dirty
@r:
  rts
@up:
  lda bar_cur
  sta bar_lag
  rts

; RowBoss (after RowFromMap): label + 12 bar tiles from column 13
X_BossRow:
  ldx fort_i
  bmi @boss
  lda en_st,x
  cmp #ST_LIVE
  bne @boss
  lda en_hp,x
  asl
  asl
  asl
  sta t0
  asl
  clc
  adc t0                    ; hp * 24
  pha
  lda en_mx,x
  tax
  pla
  jsr XDiv
  ldy #.loword(TX_FORT)
  bra @draw
@boss:
  lda b_st
  cmp #BS_ENTER
  bcs :+
  jmp @r
: cmp #BS_DYING
  bcc :+
  jmp @r
: jsl T_BossSegs
  sta b_seg
  ldy #.loword(TX_BOSS)
@draw:
  sta bar_cur
  cmp bar_lag
  bcc :+
  sta bar_lag
  lda #20
  sta bar_lt
: lda a:$0000,y            ; label right-aligned against the bar (col 12)
  and #$00FF
  eor #$FFFF
  sec
  adc #12
  tax
  phy
  lda bar_fl
  ldy #$3800
  and #1
  beq :+
  ldy #$3000
: tya
  ply
  jsl T_PutTxt
  ; tiles: [0, cur) red, [cur, lag) yellow ("recent damage"), rest empty
  ldx #26
  lda #0
  sta t0                    ; half index
@b:
  lda t0
  inc a
  inc a
  cmp bar_cur
  beq @f2
  bcc @f2
  dec a
  cmp bar_cur
  beq @f1
  lda t0
  inc a
  inc a
  cmp bar_lag
  beq @l2
  bcc @l2
  dec a
  cmp bar_lag
  beq @l1
  lda #T_BAR0|$3800
  bra @put
@f2:
  lda #T_BAR2
  bra @pal
@f1:
  lda #T_BAR1
@pal:
  ldy bar_fl
  beq :+
  ora #$3000
  bra @put
: ora #$3800
  bra @put
@l2:
  lda #T_BAR2|$3000
  bra @put
@l1:
  lda #T_BAR1|$3000
@put:
  sta rowbuf,x
  inc t0
  inc t0
  inx
  inx
  cpx #26+24
  bne @b
@r:
  rtl

; ---------------------------------------------------------------- the boss
; BossHits (@dmg, after BossBar): v_dmg = 1 gem / 2 eyes, v_hx = bullet x px
X_BossHitFx:
  lda v_hx                  ; contact point on screen: b_sx + (bullet - boss x) * scale
  pha
  lda b_x
  ASR4
  sta t0
  pla
  sec
  sbc t0
  ldx b_rcp
  jsr XMulS8
  clc
  adc b_sx
  sta t0
  lda b_sy
  sta t1
  lda v_dmg
  cmp #2
  bne @gem
  lda #EYE_DH               ; eyes: higher up, a bigger burst
  ldx b_rcp
  jsr XMulS8
  eor #$FFFF
  sec
  adc b_sy
  sta t1
  lda #2
  jsr FxAt
  lda #6
  sta b_jt
  lda #2
  sta b_ja
  bra @n
@gem:
  lda #0
  jsr FxAt
  lda #4
  sta b_jt
  lda #1
  sta b_ja
@n:
  lda t0
  sta t4
  lda t1
  sta t5
  lda v_dmg
  sta t2
  jsr DmgNumAt
  rtl

; BossMissileHit: big flash on him, hit-stop, shake, the bar flashes
X_BossMslFx:
  lda b_sx
  sta t0
  sta t4
  lda b_sy
  sta t1
  sta t5
  lda #1
  jsr FxAt
  lda #3
  sta hitstop
  lda #12
  jsr Shake
  lda #2
  jsr FlashMin
  lda #12
  sta b_jt
  lda #4
  sta b_ja
  lda #6
  sta bar_fl
  lda #6
  sta t2
  jsr DmgNumAt
  lda row_dirty
  ora #RD_BOSS
  sta row_dirty
  rtl

; A = signed px (|A| < 256), X = 8.8 scale (<= 4096) -> A = A * X >> 8 (clamped scale)
XMulS8:
  cpx #256
  bcc :+
  ldx #255
: stx t7
  cmp #$8000
  php
  bcc :+
  jsr XNeg
: A8
  sta WRMPYA
  lda t7
  sta WRMPYB
  nop
  nop
  nop
  A16
  lda RDMPYH
  and #$00FF
  plp
  bcc :+
  jsr XNeg
: rts

; damage on the robot shows: sparks crawl over him below 2/3, smoke and a scorched palette below 1/3;
; his arrival shakes the sky
BossFx:
  lda b_st
  cmp b_stp
  beq @same
  sta b_stp
  cmp #BS_ENTER
  bne @same
  stz b_dark
  lda #24
  jsr Shake
  lda #3
  jsr FlashMin
@same:
  lda b_st
  cmp #BS_FIGHT
  bne @r
  lda b_vis
  beq @r
  lda b_hp
  asl
  sta t0
  asl
  clc
  adc t0                    ; hp * 6
  sta t0
  lda b_hpmax
  asl
  asl                       ; hpmax * 4  (hp < 2/3)
  cmp t0
  bcc @r
  lda frame
  and #15
  bne @smk
  jsl T_Rand
  sta t2
  and #$3F
  sec
  sbc #32
  clc
  adc b_sx
  sta t0
  lda t2
  xba
  and #$3F
  sec
  sbc #40
  clc
  adc b_sy
  sta t1
  lda #0
  jsr FxAt
@smk:
  lda b_hpmax               ; below 1/3: smoke from the hull (not in phase 2: it smokes anyway)
  sta t0
  lda b_hp
  asl
  clc
  adc b_hp
  cmp t0
  bcs @r
  lda b_dark
  bne :+
  lda #1
  sta b_dark
: lda b_ph
  cmp #2
  beq @r
  lda frame
  and #31
  bne @r
  jsr XBossBoom
@r:
  rts
XBossBoom:
  jsl T_BossBoomL
  bcc :+
  lda #26
  sta en_t,x
: rts

; ---------------------------------------------------------------- projection (chase / cockpit)
; ProjectObjects, enemy slot c_i projected (sx, sy, t1): A = attr (palette + flash). Carry set if
; the enemy was drawn here (bombers, fortress).
X_EnPal:
  lda sx
  sta en_sx,x
  lda sy
  sta en_sy,x
  lda en_hf,x
  cmp #2
  bcc @n
  lda en_hf,x               ; white flash + a jolt
  and #1
  beq :+
  lda #2
  bra :++
: lda #.loword(-2)
: clc
  adc sx
  sta sx
  lda #$0A
  bra @p
@n:
  lda en_pa,x
@p:
  ora obj_pri
  sta o_a
  lda en_ty,x
  cmp #T_BOMBER
  beq @bomb
  cmp #T_FORT
  beq @fort
  clc
  rtl
@bomb:
  jsr DrawBomber
  sec
  rtl
@fort:
  jsr DrawFort
  sec
  rtl

DrawBomber:
  lda t1
  cmp #210
  bcs @far
  lda #F_BOMB_N
  jsr AddO
  bra @dmg
@far:
  cmp #380
  bcs :+
  lda #F_BOMB_F
  jsr AddO
  rts
: lda #F_EXS
  jsr AddO
  rts
@dmg:
  ldx c_i
  lda en_hp,x
  asl
  cmp en_mx,x
  bcs @r
  ; below half: smoke streams off the right engine, fire below a quarter
  lda #8
  sta t2
  lda #.loword(-5)
  sta t3
  jsr Smoke
  ldx c_i
  lda en_hp,x
  asl
  asl
  cmp en_mx,x
  bcs @r
  lda #.loword(-9)
  sta t2
  lda #.loword(-3)
  sta t3
  jsr Fire
@r:
  rts

DrawFort:
  lda t1
  cmp #300
  bcc @near
  cmp #520
  bcs :+
  lda #F_BOMB_N
  jsr AddO
  rts
: lda #F_BOMB_F
  jsr AddO
  rts
@near:
  lda sx
  sta x_t
  lda #F_FORT_C
  jsr AddO
  lda x_t
  sec
  sbc #32
  sta sx
  lda #F_FORT_W
  jsr AddO
  lda x_t
  clc
  adc #32
  sta sx
  lda o_a
  pha
  eor #$40
  sta o_a
  lda #F_FORT_W
  jsr AddO
  pla
  sta o_a
  lda x_t
  sta sx
  ; damage: 3/4 smoke on the right wing, 1/2 smoke left + fire right, 1/4 fire everywhere + sparks
  ldx c_i
  lda en_hp,x
  asl
  asl
  sta x_k                   ; hp * 4
  lda en_mx,x
  asl
  clc
  adc en_mx,x
  cmp x_k                   ; mx * 3 > hp * 4 ?
  bcc @r
  beq @r
  lda #30
  sta t2
  lda #.loword(-4)
  sta t3
  jsr Smoke
  ldx c_i
  lda en_mx,x
  asl
  cmp x_k
  bcc @r
  beq @r
  lda #.loword(-28)
  sta t2
  lda #.loword(-4)
  sta t3
  jsr Smoke
  lda #26
  sta t2
  lda #0
  sta t3
  jsr Fire
  ldx c_i
  lda en_mx,x
  cmp x_k
  bcc @r
  beq @r
  lda #.loword(-24)
  sta t2
  lda #0
  sta t3
  jsr Fire
  lda #6
  sta t2
  lda #.loword(-6)
  sta t3
  jsr Fire
  lda frame
  and #7
  bne @r
  jsl T_Rand
  and #$3F
  sec
  sbc #32
  clc
  adc sx
  sta t0
  lda sy
  sta t1
  lda #0
  jsr FxAt
@r:
  rts

; puffs at (sx + t2, sy + t3): smoke (every other frame, rising) / fire (flicker)
Smoke:
  lda frame
  and #1
  bne Fire_r
  lda frame
  and #6
  sta pf_f
  lda t3
  sec
  sbc pf_f
  sta t3
  lda #F_X16B
  bra Puff
Fire:
  lda frame
  and #2
  bne Fire_r
  lda #F_X16C
Puff:
  sta pf_f
  lda sx
  sta pf_sx
  lda sy
  sta pf_sy
  lda o_a
  sta pf_a
  lda sx
  clc
  adc t2
  sta sx
  lda sy
  clc
  adc t3
  sta sy
  lda frame
  and #4
  asl
  asl
  asl
  asl
  ora obj_pri
  sta o_a
  lda pf_f
  jsr AddO
  lda pf_sx
  sta sx
  lda pf_sy
  sta sy
  lda pf_a
  sta o_a
Fire_r:
  rts

AddO:
  jsl T_AddObj
  rts

; end of ProjectObjects: power-up capsules, impact sparks, floating numbers
X_Project:
  ldx #0
@pu:
  lda pu_t,x
  beq @pun
  stx x_i
  cmp #120                  ; blinks before it's gone
  bcs :+
  lda frame
  and #4
  bne @pun0
: lda pu_x,x
  ASR4
  sta t0
  lda pu_z,x
  ASR4
  clc
  adc zoff
  sta t1
  lda hcam
  sta t2
  jsl T_Project
  bcc @pun0
  ldx x_i
  lda #$04
  ora obj_pri
  sta o_a
  lda pu_k,x
  clc
  adc #F_PU_P
  jsr AddO
  lda #$70
  tsb tb_bld
@pun0:
  ldx x_i
@pun:
  inx
  inx
  cpx #NPU*2
  bne @pu
  stz t1                    ; sparks / numbers: front band
  ldx #0
@fx:
  lda fx_t,x
  beq @fxn
  stx x_i
  lda fx_x,x
  sta sx
  lda fx_y,x
  sta sy
  lda fx_t,x
  and #1
  beq :+
  lda #$40
: ora obj_pri
  sta o_a
  lda fx_k,x
  beq @sm
  cmp #2
  beq @wk
  lda fx_t,x                ; big: explosion flash
  cmp #5
  lda #F_X32A
  bcs :+
  lda #F_X16A
: jsr AddO
  bra @fx0
@wk:
  lda #F_HSPARK             ; weak point: spark + flash
  jsr AddO
  lda #F_X16A
  jsr AddO
  bra @fx0
@sm:
  lda #F_HSPARK
  jsr AddO
@fx0:
  ldx x_i
@fxn:
  inx
  inx
  cpx #NFX*2
  bne @fx
  ; numbers: two 16x16 OBJ per slot (32x16)
  ldx #0
@pp:
  lda pp_t,x
  beq @ppn
  stx x_i
  lda pp_y,x
  sta sy
  lda pp_x,x
  sec
  sbc #8
  sta sx
  lda #$04
  ora obj_pri
  sta o_a
  txa
  asl
  clc
  adc #T_CHASE_POP0
  ldy view
  cpy #VIEW_COCK
  bne :+
  clc
  adc #T_COCK_POP0-T_CHASE_POP0
: sta x_t
  jsr AddRaw
  lda sx
  clc
  adc #16
  sta sx
  lda x_t
  inc a
  inc a
  jsr AddRaw
  ldx x_i
@ppn:
  inx
  inx
  cpx #NPOP*2
  bne @pp
  rtl

; A = ob_tl word (16x16 tile): append to depth band 0 (AddObj without the frame table)
AddRaw:
  ldx view
  cpx #VIEW_COCK
  bne :+
  ldx sy
  cpx #44
  bcc @full
  cpx #152
  bcs @full
: ldx ob_n
  cpx #NOB*2
  bcs @full
  sta ob_tl,x
  lda o_a
  sta ob_at,x
  lda sx
  sta ob_sx,x
  lda sy
  sta ob_sy,x
  txa
  ldx obc
  sta obl,x
  inx
  inx
  stx obc
  lda ob_n
  inc a
  inc a
  sta ob_n
@full:
  rts

; end of ProjectOver: the capsules from above
X_ProjOverExtra:
  ldx #0
@pu:
  lda pu_t,x
  beq @n
  stx x_i
  lda frame
  and #4
  bne @n0
  lda pu_x,x
  ASR4
  sta t0
  lda pu_z,x
  ASR4
  sta t1
  jsl T_ProjOver
  bcc @n0
  lda #$34
  sta o_a
  ldx x_i
  lda pu_k,x
  clc
  adc #F_PU_P
  jsr AddO
@n0:
  ldx x_i
@n:
  inx
  inx
  cpx #NPU*2
  bne @pu
  rtl

; ---------------------------------------------------------------- NMI: floating-number glyphs
X_Nmi:
  lda b_dark
  beq @nd
  lda b_palq                ; BossNmi is about to put the clean palette back: scorch it again next frame
  beq :+
  lda #1
  sta b_dark
  bra @nd
: lda b_dark
  cmp #1
  bne @nd
  lda b_gfx
  cmp #2
  bne @nd
  lda #2
  sta b_dark
  A8
  lda #240
  sta CGADD
  A16
  ldx #0
: lda f:BossPal,x           ; 7/8 brightness (v1.3: keep the white armour reading white)
  lsr
  and #$3DEF
  sta n_t
  lsr
  and #$1CE7
  clc
  adc n_t
  sta n_t
  lda f:BossPal,x
  lsr
  lsr
  lsr
  and #$0C63
  clc
  adc n_t
  A8
  sta CGDATA
  xba
  sta CGDATA
  A16
  inx
  inx
  cpx #26                   ; (13 and 14 = the animated eyes / gem)
  bne :-
@nd:
  lda pp_dirty
  bne :+
  rtl
: ldx view
  cpx #VIEW_OVER
  bne :+
  stz pp_dirty
  rtl
: A8
  lda #$80
  sta VMAIN
  lda #$01
  sta DMAP0
  lda #$18
  sta BBAD0
  lda #^PopFont
  sta A1B0
  A16
  lda #T_CHASE_POP0
  cpx #VIEW_COCK
  bne :+
  lda #T_COCK_POP0
: sta n_t
  ldx #0                    ; slot
@s:
  lda pp_dirty
  and f:Bit1,x
  beq @sn
  stx n_i
  txa
  asl
  asl
  tay                       ; glyph offset
  txa
  asl
  clc
  adc n_t
  sta n_k                   ; first tile
  ldx #0                    ; cell 0..7
@c:
  phx
  lda f:CellTile,x
  clc
  adc n_k
  asl
  asl
  asl
  asl
  clc
  adc #$6000
  sta VMADDL
  lda pp_g,y
  and #$00FF
  asl
  asl
  asl
  asl
  asl
  clc
  adc #.loword(PopFont)
  sta A1T0L
  lda #32
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
  iny
  plx
  inx
  inx
  cpx #16
  bne @c
  ldx n_i
@sn:
  inx
  inx
  cpx #NPOP*2
  bne @s
  stz pp_dirty
  rtl
CellTile: .word 0, 1, 2, 3, 16, 17, 18, 19

; ---------------------------------------------------------------- hit-stop / stage transitions
; MainLoop, before each physics step: carry set = skip it (hit-stop). Also applies a stage switch.
X_HitStop:
  lda st_tr
  cmp #2
  bne :+
  jsr StageApply
: lda hitstop
  beq :+
  dec hitstop
  sec
  rtl
: clc
  rtl

; Waves: T_STAGE entry (X = wave_pos): carry set when the switch is done (advance the script)
X_WaveStage:
  lda st_tr
  bne @busy
  ldy #0                    ; the sky must be clear first
: lda en_st,y
  bne @no
  iny
  iny
  cpy #NEN*2
  bne :-
  lda gameover
  bne @no
  lda f:WaveData+2,x
  sta st_next
  cmp stage
  beq @skip                 ; (already there: e.g. the loop back to stage 1 after the boss)
  lda #1
  sta st_tr
  stz st_t
@no:
  clc
  rtl
@busy:
  cmp #4
  bne @no
  stz st_tr
@skip:
  sec
  rtl

StageStep:
  lda msg_at
  cmp #$3800
  bne :+
  lda frame
  and #15
  bne :+
  lda row_dirty
  ora #RD_SKYA|RD_SKYB|RD_WARN
  sta row_dirty
: lda msg_t
  beq @m
  dec msg_t
  bne @m
  stz msg_a
  stz msg_b
  lda row_dirty
  ora #RD_SKYA|RD_SKYB|RD_WARN
  sta row_dirty
@m:
  lda st_tr
  cmp #1
  bne @in
  inc st_t                  ; fade out over half a second
  lda st_t
  lsr
  eor #$FFFF
  sec
  adc #$0F
  bpl :+
  lda #0
: sta bright
  bne @r
  lda #2
  sta st_tr
  rts
@in:
  cmp #3
  bne @r
  inc st_t
  lda st_t
  lsr
  cmp #$0F
  bcc :+
  lda #$0F
  ldx #4
  stx st_tr
: sta bright
@r:
  rts

; black screen: new palette / map / sky / haze (LoadView does the uploads), banner, fade in
StageApply:
  jsr PrRevive
  lda st_next
  sta stage
  jsl T_LoadView
  lda #3
  sta st_tr
  stz st_t
  stz bright
  lda stage
  jsr Banner
  rts

; LoadView (force blank, NMI off), at the end: this stage's CGRAM / Mode 7 map, sky + haze HDMA
PropMidT: .word T_CHASE_PRM0, T_CHASE_PRM1, T_CHASE_PRM2, T_CHASE_PRM3, T_CHASE_PRF0, T_CHASE_PRF1, T_CHASE_PRF2, T_CHASE_PRF3
X_ViewLoad:
  jsr SS_Reset               ; the OBJ sheet was just reloaded
  lda view                   ; v1.2: chase field sheet -> this stage's mid / far ground prop frames
  bne @np
  lda b_gfx
  bne @np
  A8
  lda #$80
  sta VMAIN
  lda #$01
  sta DMAP0
  lda #$18
  sta BBAD0
  lda #^PropMid
  sta A1B0
  A16
  lda stage
  xba
  asl
  asl                        ; * 1024
  clc
  adc #.loword(PropMid)
  sta n_t
  ldy #0
@pm:
  tyx
  lda f:PropMidT,x
  asl
  asl
  asl
  asl
  clc
  adc #$6000
  sta n_k
  ldx #2
: lda n_k
  sta VMADDL
  clc
  adc #16*16
  sta n_k
  lda n_t
  sta A1T0L
  clc
  adc #64
  sta n_t
  lda #64
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
  dex
  bne :-
  iny
  iny
  cpy #16
  bne @pm
@np:
  lda stage
  ldx #STAGE_SZ
  jsr XMul16                ; A = stage * STAGE_SZ (+ StageData)
  clc
  adc #.loword(StageData)
  sta x_t
  lda stage
  cmp cur_pal
  beq @p
  sta cur_pal
  A8
  stz CGADD
  stz DMAP0
  lda #$22
  sta BBAD0
  lda #^StageData
  sta A1B0
  A16
  lda x_t
  sta A1T0L
  lda #512
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
@p:
  lda stage
  asl
  tax
  lda f:StageMap,x
  cmp cur_map
  bne :+
  jmp @m
: sta cur_map
  cmp #0
  beq :+
  jmp @mb
:
  DMA_VRAM M7Map,   $0000, 16384, $00, $18, $00
  DMA_VRAM M7Tiles, $0000, 16384, $80, $19, $00
  bra @m
@mb:
  DMA_VRAM M7MapB,   $0000, 16384, $00, $18, $00
  DMA_VRAM M7TilesB, $0000, 16384, $80, $19, $00
@m:
  ; HDMA ch 6 (CGRAM sky gradient), ch 7 (horizon haze) -> this stage's tables
  A8
  lda #^StageData
  sta $4364
  sta $4374
  A16
  lda x_t
  clc
  adc #512+2*SKYTAB_SZ
  sta stg_hz
  sta $4372
  lda view
  cmp #VIEW_COCK
  beq @ck
  cmp #VIEW_OVER
  beq @ov
  lda x_t
  clc
  adc #512
  bra @set
@ck:
  lda x_t
  clc
  adc #512+SKYTAB_SZ
  bra @set
@ov:
  lda x_t
  clc
  adc #512+2*SKYTAB_SZ+HAZE_SZ
@set:
  sta $4362
  lda #3
  sta pp_dirty              ; the numbers' tiles were overwritten with the sheet
  rtl

; A * X (16 x 16 -> 16), small values
XMul16:
  sta t6
  stx t7
  lda #0
  ldx #16
: asl
  asl t6
  bcc :+
  clc
  adc t7
: dex
  bne :--
  rts

; ---------------------------------------------------------------- text rows
; RowSky (chase sky rows 2, 3, 5): A = row. The boss's texts first, then stage / power-up messages.
X_SkyRow:
  sta x_k
  jsl T_BossSky
  bcs @r
  lda msg_t
  beq @r
  ldy msg_a
  lda x_k
  cmp #2
  beq :+
  ldy msg_b
  cmp #3
  bne @r
: cpy #0
  beq @r
  lda msg_at
  cmp #$3800                ; warnings blink
  bne :+
  lda frame
  and #16
  bne @r
  lda msg_at
: ldx #$FF
  jsl T_PutTxt
@r:
  rtl

; RowWarn (cockpit canopy row): carry set if a message was drawn
X_WarnRow:
  jsl T_BossWarnRow
  bcs @r
  lda msg_t
  beq @no
  ldy msg_b
  beq @no
  lda msg_at
  ldx #$FF
  jsl T_PutTxt
  sec
@r:
  rtl
@no:
  clc
  rtl

; ---------------------------------------------------------------- data
PopFont:  .incbin "../assets/popfont.bin"
          .res 32, 0                     ; GL_BLANK
StageData: .incbin "../assets/stages.bin"
.include "../assets/stages.inc"
StTxtA: .word .loword(TX_ST1), .loword(TX_ST2), .loword(TX_ST3), .loword(TX_ST4)
StTxtB: .word .loword(TX_SN1), .loword(TX_SN2), .loword(TX_SN3), .loword(TX_SN4)

; wave script: type (| AR_GUN fires tracers, | AR_MSL carries a missile), x px, z px, weave, frames to
; the next entry.  T_STAGE: x = stage.
G = AR_GUN
M = AR_MSL
WaveData:
  ; ======== STAGE 1: OCEAN STRIKE
  ; three gunners head-on
  .word T_HEAD|G,   0, 900, 0, 24
  .word T_HEAD|G, .loword(-60), 900, 0, 24
  .word T_HEAD|G,  60, 900, 0, 0
  .word T_WAIT, 0, 0, 0, 60
  ; crossers
  .word T_CROSSR, .loword(-480), 380, 0, 50
  .word T_CROSSL, 480, 470, 0, 50
  .word T_CROSSR, .loword(-480), 300, 0, 0
  .word T_WAIT, 0, 0, 0, 50
  ; a V of darts
  .word T_DART,    0, 1000, 10, 6
  .word T_DART, .loword(-50), 1060, 10, 0
  .word T_DART,   50, 1060, 10, 6
  .word T_DART, .loword(-100), 1120, 10, 0
  .word T_DART,  100, 1120, 10, 0
  .word T_WAIT, 0, 0, 0, 60
  ; overtakers, then one sits on your tail and lets a missile go
  .word T_OVER, .loword(-30), .loword(-110), 8, 45
  .word T_OVER, 30, .loword(-110), 8, 60
  .word T_TAIL|M, .loword(-40), .loword(-175), 0, 0
  .word T_WAIT, 0, 0, 0, 60
  ; an armoured bomber with two escorts
  .word T_BOMBER|G,  0, 760, 4, 40
  .word T_HEAD|G, .loword(-90), 950, 14, 0
  .word T_HEAD|G,  90, 950, 14, 0
  .word T_WAIT, 0, 0, 0, 60
WarpS2:
  .word T_STAGE, 1, 0, 0, 90
  ; ======== STAGE 2: DESERT STORM
  ; swoopers out of the sun
  .word T_SWOOP|G, .loword(-60), 950, 0, 28
  .word T_SWOOP|G,  60, 980, 0, 28
  .word T_SWOOP|G|M,  0, 1010, 0, 0
  .word T_WAIT, 0, 0, 0, 50
  ; crossers from both sides, two kamikazes through the middle
  .word T_CROSSL, 480, 420, 0, 24
  .word T_CROSSR, .loword(-480), 360, 0, 24
  .word T_KAMI,  70, 1000, 0, 30
  .word T_KAMI, .loword(-70), 1000, 0, 0
  .word T_WAIT, 0, 0, 0, 50
  ; darts line abreast
  .word T_DART, .loword(-150), 1000, 16, 0
  .word T_DART, .loword(-90), 1000, 16, 0
  .word T_DART, .loword(-30), 1000, 16, 0
  .word T_DART,   30, 1000, 16, 0
  .word T_DART,   90, 1000, 16, 0
  .word T_DART,  150, 1000, 16, 0
  .word T_WAIT, 0, 0, 0, 60
  ; two bombers side by side
  .word T_BOMBER|G, .loword(-70), 760, 0, 0
  .word T_BOMBER|G,  70, 800, 0, 0
  .word T_WAIT, 0, 0, 0, 60
WarpS3:
  .word T_STAGE, 2, 0, 0, 90
  ; ======== STAGE 3: ARCTIC FRONT
  .word T_DART,    0, 1000, 22, 6
  .word T_DART, .loword(-60), 1070, 22, 0
  .word T_DART,   60, 1070, 22, 0
  .word T_HEAD|G|M,  0, 1100, 18, 0
  .word T_WAIT, 0, 0, 0, 50
  .word T_OVER,  26, .loword(-110), 10, 40
  .word T_TAIL|M, .loword(-40), .loword(-175), 0, 60
  .word T_KAMI, .loword(-160), 1000, 0, 20
  .word T_KAMI,  160, 1000, 0, 20
  .word T_KAMI,    0, 1050, 0, 0
  .word T_WAIT, 0, 0, 0, 80
WarpFort:
  .word T_FORT|G|M,  0, 1000, 0, 0
  .word T_WAIT, 0, 0, 0, 90
WarpS4:
  .word T_STAGE, 3, 0, 0, 90
  ; ======== STAGE 4: NIGHT RAID
  .word T_OVER,  26, .loword(-110), 10, 30
  .word T_CROSSL, 480, 420, 0, 30
  .word T_CROSSR, .loword(-480), 340, 0, 40
  .word T_HEAD|G|M,   0, 1000, 18, 30
  .word T_TAIL|M, 40, .loword(-175), 0, 0
  .word T_WAIT, 0, 0, 0, 60
  .word T_BOMBER|G,  0, 760, 6, 30
  .word T_KAMI, .loword(-120), 1000, 0, 30
  .word T_KAMI,  120, 1000, 0, 0
  .word T_WAIT, 0, 0, 0, 50
  .word T_DART, .loword(-80), 1000, 26, 0
  .word T_DART,   80, 1000, 26, 10
  .word T_SWOOP|G|M,  0, 950, 0, 30
  .word T_HEAD|G, .loword(-90), 950, 14, 0
  .word T_HEAD|G,  90, 950, 14, 0
  .word T_WAIT, 0, 0, 0, 90
WaveBoss:
  .word T_BOSS, 0, 0, 0, 30
  .word T_STAGE, 0, 0, 0, 30
  .word T_LOOP, 0, 0, 0, 0
; WARP=n test builds: script position + stage
WarpTab: .word WarpS2-WaveData, 0, WarpS3-WaveData, 1, WarpFort-WaveData, 2, WarpS4-WaveData, 2
         .word WaveBoss-WaveData, 3


; ================================================================ v1.1 sprite stacking
; Frames come from tools/voxstack.py (voxel models, sprite-stacked offline). The chase jet has ONE 64x64 VRAM
; slot and six 32x32 slots serve near enemies / ground props; X_Stream (NMI, after everything else) uploads
; what the frame just built asked for, inside a scanline budget, so VRAM is only written in vblank.
SlotTiles: .word T_CHASE_SLOT0, T_CHASE_SLOT1, T_CHASE_SLOT2, T_CHASE_SLOT3, T_CHASE_SLOT4, T_CHASE_SLOT5
.include "../assets/stack.inc"

SS_Reset:                    ; sheet (re)loaded from ROM: slots hold their placeholders, jet slot = frame 0
  lda #$FFFF
  ldx #0
: sta ss_want,x
  sta ss_have,x
  stz ss_use,x
  inx
  inx
  cpx #SS_SLOTS*2
  bne :-
  stz js_have
  stz js_want
  lda #$FFFF                 ; v1.2: tumbling frames are back to frame 0 of the sheet: re-upload
  sta tb_tab
  rts

; chase jet: frame from bank (|turnrate|, 5 steps) and climb / dive; h-flip when banking left
X_JetFrame:
  lda turnrate
  bpl :+
  eor #$FFFF
  inc a
: ldx #0
  cmp #$50
  bcc @r
  inx
  cmp #$B8
  bcc @r
  inx
  cmp #$128
  bcc @r
  inx
  cmp #$1A0
  bcc @r
  inx
@r:
  stx x_t
  lda climb
  beq @lv
  bmi :+
  lda #5
  bra @p
: lda #10
  bra @p
@lv:
  lda #0
@p:
  clc
  adc x_t
  sta js_want
  lda #T_CHASE_JETS
  sta stile
  lda #$30
  ldx turnrate
  bpl :+
  ora #$40
: sta sattr
  rtl

; near / medium enemy frame (chase: 16 / 8 directions of the voxel model; cockpit: the static frames)
; in: X = enemy, t1 = depth, o_a = attr.  out: carry clear + A = logical frame, or carry set = small (caller)
X_EnFrame:
  lda t1
  cmp #165
  bcc :+
  sec
  rtl
: ldy view
  beq @ch
  cmp #82
  bcs :+
  lda #F_EL_TOW
  clc
  rtl
: lda #F_EM
  clc
  rtl
@ch:
  cmp #82
  bcs @med
  lda en_hd,x
  clc
  adc #$0800
  xba
  lsr
  lsr
  lsr
  lsr
  and #$000F
  cmp #9
  bcc :+
  eor #$FFFF
  clc
  adc #17
  pha
  lda o_a
  eor #$40
  sta o_a
  pla
: phx
  jsr SlotGet
  plx
  cmp #$FFFF
  bne :+
  lda #F_EL_TOW
  clc
  rtl
: clc
  adc #F_SLOT0
  clc
  rtl
@med:
  lda en_hd,x
  clc
  adc #$1000
  xba
  lsr
  lsr
  lsr
  lsr
  lsr
  and #$0007
  cmp #5
  bcc :+
  eor #$FFFF
  clc
  adc #9
  pha
  lda o_a
  eor #$40
  sta o_a
  pla
: clc
  adc #F_EMY0
  clc
  rtl

; A = streamed frame id -> A = slot (0..5) holding it, or $FFFF (requested; draw a fallback this frame)
SlotGet:
  sta ss_u
  ldy #0
: lda ss_have,y
  cmp ss_u
  bne @n
  cmp ss_want,y
  bne @n
  lda ss_fc
  sta ss_use,y
  tya
  lsr
  rts
@n:
  iny
  iny
  cpy #SS_SLOTS*2
  bne :-
  ldy #0                     ; already on its way?
: lda ss_want,y
  cmp ss_u
  beq @fb
  iny
  iny
  cpy #SS_SLOTS*2
  bne :-
  ldy #0                     ; take a slot nobody drew from this frame
: lda ss_use,y
  cmp ss_fc
  bne @take
  iny
  iny
  cpy #SS_SLOTS*2
  bne :-
@fb:
  lda #$FFFF
  rts
@take:
  lda ss_u
  sta ss_want,y
  lda ss_fc
  sta ss_use,y               ; (its old content is not drawn this frame: the NMI may replace it)
  lda #$FFFF
  rts

;
; v1.2 shootable ground props --------------------------------------------------------
Bit16: .word 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768
; A = PropOff offset (8 per prop) -> X = pr_dead word offset, A = bit
PrBit:
  lsr
  lsr
  lsr
  pha
  and #15
  asl
  tax
  lda f:Bit16,x
  sta x_k
  pla
  lsr
  lsr
  lsr
  and #$FFFE
  tax
  lda x_k
  rts
PrRevive:
  ldx #8
: stz pr_dead,x
  dex
  dex
  bpl :-
  lda #$FFFF
  sta pr_hid
  rts
PROP_HP = 3
; prop pr_i accepted for drawing at entry Y (pr_x, pr_z, sx, pr_gy): your rounds crossing it hit.
; carry set = destroyed this frame.  Keeps Y.
PropHit:
  sty x_j
.ifdef PROPTEST
  inc pr_dbg
.endif
  lda pr_z
  sec
  sbc zoff
  sta x_dx                   ; depth ahead of you
  ldy #0
@b:
  lda bu_d,y
  beq @n
.ifdef PROPTEST
  sta pr_dbb
  lda x_dx
  sta pr_dbz
  lda bu_d,y
.endif
  sec
  sbc x_dx
  clc
  adc #22
.ifdef PROPTEST
  cmp #600
.else
  cmp #44                    ; within ~ one 2-frame step of bullet travel
.endif
  bcs @n
  lda bu_x,y
  sec
  sbc pr_x
  jsr XAbs
  sta x_bx
  lda bu_ln,y                ; spread lanes widen the net
  and #6
  beq :+
  lda x_bx
  sec
  sbc #24
  bcc @hit
  sta x_bx
: lda x_bx
.ifdef PROPTEST
  cmp #400
.else
  cmp #18
.endif
  bcc @hit
@n:
  iny
  iny
  cpy #NBU*2
  bne @b
  ldy x_j
  clc
  rts
@hit:
  lda #0
  sta bu_d,y                 ; the round is spent
  lda pr_i
  cmp pr_hid
  beq :+
  sta pr_hid
  stz pr_hc
: inc pr_hc
  lda sx                     ; spark + tink where it struck
  sta t0
  lda pr_gy
  sec
  sbc #7
  sta t1
  lda #0
  jsr FxAt
  lda pr_x
  sta sfx_nfx
  lda x_dx
  sta sfx_nfz
  lda #K_FIX
  sta sfx_nk
  lda pr_hc
  cmp #PROP_HP
  bcs @kill
  lda #SA_TINK
  ldx #2
  ldy #7
  jsl T_SfxA
  ldy x_j
  clc
  rts
@kill:
  lda pr_i                   ; down for this stage
  jsr PrBit
  ora pr_dead,x
  sta pr_dead,x
  lda #$FFFF
  sta pr_hid
  lda sx
  sta t0
  lda pr_gy
  sec
  sbc #8
  sta t1
  lda #1
  jsr FxAt                   ; big flash
  lda #4
  jsr Shake
  ldy #0                     ; a ground fireball that stays where the target stood
: lda en_st,y
  beq @ok
  iny
  iny
  cpy #NEN*2
  bne :-
  bra @pts
@ok:
  sty x_i
  lda #ST_BOOM
  sta en_st,y
  lda #T_BIGBOOM
  sta en_ty,y
  lda pr_x
  asl
  asl
  asl
  asl
  sta en_x,y
  lda x_dx
  asl
  asl
  asl
  asl
  sta en_z,y
  lda hcam
  sec
  sbc pr_ch
  clc
  adc #6
  sta en_dh,y
  lda #0
  sta en_hd,y
  sta en_hf,y
  sta en_spd,y
  sta en_t,y
  lda sx
  sta en_sx,y
  lda pr_gy
  sta en_sy,y
  stx sfx_ni                 ; explosion follows the fireball (stereo)
  tyx
  stx sfx_ni
  lda #K_EN
  sta sfx_nk
  lda #3                     ; +300
  jsr ScorePop
@pts:
  lda #SB_BIG
  ldx #3
  ldy #50
  jsl T_SfxB
  lda #3
  jsl T_ScoreAdd
  ldy x_j
  sec
  rts

; ground props standing on the Mode 7 plane (chase view): towers, fuel tanks, AA bunkers.
; Same world -> camera rotation as the clouds; frame by distance (3 size steps) and, near, by the
; prop's heading relative to the camera (16 streamed yaw frames).
PR_BUDGET = PRB             ; frame load (lines) at which props only glide on their screen velocity
X_Props:
.ifdef NOPROPS
  inc ss_fc
  rtl
.endif
  lda b_gfx
  beq :+
  stz pc_n
  jmp @x
: lda pr_ph                  ; full projection every PR_EVERY frames; in between the props glide
  inc a
  cmp #PR_EVERY
  bcc :+
  lda #0
: sta pr_ph
  beq :+
  jmp @adv
: jsl T_LoadNow
  sta pr_ld
  cmp #PR_BUDGET
  bcc :+
  jmp @adv                   ; busy frame: glide this one too
: stz pr_n
  ldx lev
  lda f:CamH,x
  and #$00FF
  sta pr_ch                  ; camera height
.ifdef PROPDBG
  inc pd_proj
.endif
  lda abs_cos                ; v1.2: bases behind the camera's half-plane skip the rotation
  cmp abs_sin
  lda #0
  bcs :+
  lda #2
: sta pr_ax
  lda heading                ; this heading's pre-rotated prop offsets
  xba
  and #$00FF
  pha
  and #$007F
  A8
  sta WRMPYA
  lda #NPROPS*2
  sta WRMPYB
  A16
  nop
  nop
  lda RDMPYL
  clc
  adc #.loword(PropRot)
  sta pr_rp
  pla
  asl
  xba
  and #$0001
  clc
  adc #^PropRot
  A8
  sta pr_rp+2
  A16
  lda cur_map
  beq :+
  lda #NBASE*8
: sta pr_b
  clc
  adc #NBASE*8
  sta pr_be
@bl:                         ; ---- bases: one box test, then one rotation for the centre
  ldx pr_b
  lda f:BaseMap0+4,x
  bne :+
  jmp @bn
: lda f:BaseMap0+2,x
  sec
  sbc campy
  and #$03FF
  cmp #$0200
  bcc :+
  ora #$FC00
: sta pr_dy
.ifdef NOCULL
  bra @dyk
.endif
  ldy pr_ax                  ; cos-major heading: behind when dy * sgn(cos) > 64
  bne @dyk
  bit cosv
  bpl :+
  eor #$FFFF
  inc a
: sec
  sbc #65
  bmi @dyk
  jmp @bn
@dyk:
  lda pr_dy
  bpl :+
  eor #$FFFF
  inc a
: cmp #440
  bcc :+
  jmp @bn
: lda f:BaseMap0,x
  sec
  sbc campx
  and #$03FF
  cmp #$0200
  bcc :+
  ora #$FC00
: sta pr_dx
.ifdef NOCULL
  bra @dxk
.endif
  ldy pr_ax                  ; sin-major heading: behind when dx * sgn(sin) < -64
  beq @dxk
  bit sinv
  bpl :+
  eor #$FFFF
  inc a
: clc
  adc #64
  bpl @dxk
  jmp @bn
@dxk:
.ifdef PROPDBG
  inc pd_box
.endif
  lda pr_dx
  bpl :+
  eor #$FFFF
  inc a
: cmp #440
  bcc :+
  jmp @bn
: lda pr_dy
  jsl T_RelTrig
  lda t_ps
  sta pr_r1
  lda t_pc
  sta pr_r0
  lda pr_dx
  jsl T_RelTrig
  lda t_ps
  sec
  sbc pr_r0
  sta pr_cz                  ; centre depth
  cmp #.loword(-64)
  bcs :+
  cmp #470
  bcc :+
  jmp @bn
: lda t_pc
  clc
  adc pr_r1
  sta pr_cx                  ; centre lateral
  bpl :+
  eor #$FFFF
  inc a
: sec
  sbc #96
  bcc @bv                    ; |x| < z + 96: some of the base may be in view
  sec
  sbc pr_cz
  bmi @bv
  jmp @bn
@bv:
.ifdef PROPDBG
  inc pd_rot
.endif
  ldx pr_b
  lda f:BaseMap0+4,x
  sta pr_k
  lda f:BaseMap0+6,x
  sta pr_i
@pl:                         ; ---- props of this base: small offsets, rotated with 8-bit multiplies
  ldx pr_i
  lda f:PropOff+4,x          ; v1.2: destroyed military props stay down
  cmp #3
  bne @alv
  txa
  jsr PrBit
  and pr_dead,x
  beq :+
  jmp @pn
: ldx pr_i
@alv:
.ifdef PROPDBG
  inc pd_scan
.endif
  txa                        ; v1.2: offsets rotated offline (PropRot): dz, dx bytes
  lsr
  lsr
  tay
  lda [pr_rp],y
  sta pr_r1
  and #$00FF
  cmp #$0080
  bcc :+
  ora #$FF00
: clc
  adc pr_cz
  sta pr_z                   ; z = cz + ox*S - oy*C
  cmp #28
  bcs :+
  jmp @pn
: cmp #400
  bcc :+
  jmp @pn
: lda pr_r1
  xba
  and #$00FF
  cmp #$0080
  bcc :+
  ora #$FF00
: clc
  adc pr_cx
  sta pr_x                   ; x = cx + ox*C + oy*S
  bpl :+
  eor #$FFFF
  inc a
: sta x_t                    ; |x|
  lda pr_z                   ; in view: |x| < 0.8 z + 24 (~ z - z/4 - z/16 + 24)
  lsr
  lsr
  sta pr_r0
  lsr
  lsr
  clc
  adc pr_r0
  eor #$FFFF
  sec
  adc pr_z
  clc
  adc #24
  cmp x_t
  bcs :+
  jmp @pn
: lda pr_z
  asl
  tax
  lda f:RecipTab,x
  sta t5
  lsr
  lsr
  lsr
  lsr
  sta pr_hs                  ; screen px per 16 world px (ScaleR(v) = v * t5 / 256)
  cmp #3
  bcs :+
  jmp @pn
: lda pr_x
  jsl T_ScaleR
  clc
  adc #128
  sta sx
  cmp #.loword(-16)
  bcs :+
  cmp #272
  bcc :+
  jmp @pn
: lda pr_ch
  jsl T_ScaleR
  clc
  adc #HOR
  sta pr_gy                  ; screen y of the prop's foot
  cmp #232
  bcc :+
  jmp @pn
: ldx pr_i
  lda pr_n
  asl
  tay
  txa
  sta pn_id,y
  lda sx
  sta pn_sx,y
  lda pr_gy
  sta pn_gy,y
  lda pr_z
  sta pn_z,y
  lda #$FFFF
  sta pn_u,y
  lda f:PropOff+4,x
  sta x_t                    ; type
  lda pr_hs
.ifdef NOPNEAR
  cmp #$7FFF
.else
  cmp #12
.endif
  bcc @mid
  ; near: 16 yaws, streamed (the mid-size frame stands in until the slot is loaded)
  lda f:PropOff+6,x
  xba
  asl
  asl
  asl
  asl
  sec
  sbc heading
  clc
  adc #$0800
  xba
  lsr
  lsr
  lsr
  lsr
  and #$000F
  sta pr_m
  lda stage                  ; v1.2: this stage's model for the slot
  asl
  asl
  adc x_t
  asl
  tax
  lda f:StageMod,x
  clc
  adc pr_m
  sta pn_u,y
@mid0:
  lda x_t
  clc
  adc #F_PRM0
  bra @st
@mid:
  cmp #6
  bcs @mid0
  lda x_t
  clc
  adc #F_PRF0
@st:
.ifdef PROPDBG
  inc pd_acc
.endif
  sta pn_fr,y
  lda x_t                    ; v1.2: military props take gunfire
  cmp #3
  bne :+
  lda pr_hs
  cmp #5
  bcc :+
.ifdef NOPHIT
  clc
.else
  jsr PropHit
.endif
  bcc :+
  lda #$FFFF                 ; destroyed: not drawn
  sta pn_u,y
  lda #F_X16C
  sta pn_fr,y
: inc pr_n
  lda pr_n
  cmp #PR_MAX
  bcc @pn
  jmp @done
@pn:
  lda pr_i
  clc
  adc #8
  sta pr_i
  dec pr_k
  beq @bn
  jmp @pl
@bn:
  lda pr_b
  clc
  adc #8
  sta pr_b
  cmp pr_be
  beq @done
  jmp @bl
@done:                       ; ---- new list: screen velocity from the same prop two frames ago
  ldy #0
@vl:
  cpy pr_n
  beq @vd
  tya
  asl
  tax
  lda #0
  sta pr_m                   ; vx
  sta pr_k                   ; vy
  phy
  ldy #0
@vm:
  cpy pc_n
  beq @vf
  phy
  tya
  asl
  tay
  lda pc_id,y
  cmp pn_id,x
  bne :+
  lda pn_sx,x
  sec
  sbc pc_sx,y
  cmp #$8000
  ror
.if PR_EVERY = 4
  cmp #$8000
  ror
.endif
  sta pr_m
  lda pn_gy,x
  sec
  sbc pc_gy,y
  cmp #$8000
  ror
.if PR_EVERY = 4
  cmp #$8000
  ror
.endif
  sta pr_k
  ply
  bra @vf
: ply
  iny
  bra @vm
@vf:
  ply
  lda pr_m
  sta pn_vx_t,x
  lda pr_k
  sta pn_vy_t,x
  iny
  bra @vl
@vd:
  ldx #0                     ; commit
: cpx #PR_MAX*2
  beq :+
  lda pn_id,x
  sta pc_id,x
  lda pn_sx,x
  sta pc_sx,x
  lda pn_gy,x
  sta pc_gy,x
  lda pn_u,x
  sta pc_u,x
  lda pn_fr,x
  sta pc_fr,x
  lda pn_z,x
  sta pc_z,x
  lda pn_vx_t,x
  sta pc_vx,x
  lda pn_vy_t,x
  sta pc_vy,x
  inx
  inx
  bra :-
: lda pr_n
  sta pc_n
  bra @emit
@adv:                        ; glide: advance by the measured screen velocity
  ldx #0
  ldy pc_n
  bne :+
  jmp @x
: lda pc_sx,x
  clc
  adc pc_vx,x
  sta pc_sx,x
  lda pc_gy,x
  clc
  adc pc_vy,x
  sta pc_gy,x
  inx
  inx
  dey
  bne :-
@emit:                       ; ---- draw the list
.ifdef NOPDRAW
  jmp @x
.endif
  stz pr_i
@el:
  lda pr_i
  cmp pc_n
  bne :+
  jmp @x
:
  asl
  tax
  lda pc_sx,x
  sta sx
  cmp #.loword(-16)
  bcs :+
  cmp #272
  bcs @en
: lda pc_gy,x
  cmp #232
  bcs @en
  lda #$0C                   ; olive enemy palette
  ora obj_pri
  sta o_a
  lda pc_z,x
  sta t1
  lda pc_u,x
  cmp #$FFFF
  beq @es
  phx
  jsr SlotGet
  plx
  cmp #$FFFF
  beq @es
  clc
  adc #F_SLOT0
  pha
  lda pc_gy,x
  sec
  sbc #13
  bra @ea
@es:
  lda pc_fr,x
  pha
  lda pc_gy,x
  sec
  sbc #5
@ea:
  sta sy
  pla
  jsl T_AddObj
@en:
  inc pr_i
  bra @el
@x:
  inc ss_fc
  rtl

; A = small signed offset (|a| < 256), Y = signed trig (|t| <= 255) -> A = (a * t) >> 8, signed
PMul:
  sta pr_t
  tya
  eor pr_t
  sta pr_sg
  tya
  bpl :+
  eor #$FFFF
  inc a
: A8
  sta WRMPYA
  A16
  lda pr_t
  bpl :+
  eor #$FFFF
  inc a
: A8
  sta WRMPYB
  nop
  nop
  nop
  A16
  lda RDMPYH
  and #$00FF
  bit pr_sg
  bpl :+
  eor #$FFFF
  inc a
: rts

; NMI: upload the requested jet frame / slot frames (after every other VRAM job, inside a line budget)
X_Stream:
.ifdef NOSTREAM
  rtl
.endif
  lda view
  beq :+
  rtl
: lda b_gfx
  beq @nb
  cmp #2
  beq :+
  lda #$FFFF                 ; boss sheet rows are streaming: redo the jet afterwards, no uploads now
  sta js_have
  rtl
: lda #$FFFF                 ; boss resident: slots are boss cells
  ldx #0
: sta ss_want,x
  sta ss_have,x
  inx
  inx
  cpx #SS_SLOTS*2
  bne :-
@nb:
  A8
  lda #$80
  sta VMAIN
  lda #$01
  sta DMAP0
  lda #$18
  sta BBAD0
  A16
  lda js_want
  cmp js_have
  beq @slots
  jsr SS_Line
  cmp #18
  bcc :+
  jmp @slots
: A8
  lda #^JetFrames
  sta A1B0
  A16
  lda js_want
  xba
  asl
  asl
  asl
  clc
  adc #.loword(JetFrames)
  sta n_t                    ; source
  lda #T_CHASE_JETS*16+$6000
  sta n_k                    ; VRAM word address
  ldx #8
: lda n_k
  sta VMADDL
  clc
  adc #16*16
  sta n_k
  lda n_t
  sta A1T0L
  clc
  adc #256
  sta n_t
  lda #256
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
  dex
  bne :-
  lda js_want
  sta js_have
@slots:
  lda b_gfx
  beq :+
  rtl
: stz ss_up
  ldy #0
@sl:
  lda ss_want,y
  cmp ss_have,y
  bne @rf61857
  jmp @sn
@rf61857:
  cmp #$FFFF
  bne @rf21295
  jmp @sn
@rf21295:
  jsr SS_Line
  cmp #27
  bcc @rf29831
  jmp @r
@rf29831:
  lda ss_want,y
  sec
  sbc #SS_PR
  bcs @spr
  adc #SS_PR
  xba
  asl                        ; * 512
  clc
  adc #.loword(SlotFrames)
  sta n_t
  A8
  lda #^SlotFrames
  bra @sbk
@spr:                        ; ground prop frame m: bank $90 + m/64, offset (m & 63) * 512
.a16
  pha
  and #$003F
  xba
  asl
  ora #$8000
  sta n_t
  pla
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  clc
  adc #^PropFrames
  A8
@sbk:
  sta A1B0
  A16
  tyx
  lda f:SlotTiles,x
  asl
  asl
  asl
  asl
  clc
  adc #$6000
  sta n_k
  ldx #4
: lda n_k
  sta VMADDL
  clc
  adc #16*16
  sta n_k
  lda n_t
  sta A1T0L
  clc
  adc #128
  sta n_t
  lda #128
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
  dex
  bne :-
  lda ss_want,y
  sta ss_have,y
  inc ss_up
  lda ss_up
  cmp #3
  bcs @r
@sn:
  iny
  iny
  cpy #SS_SLOTS*2
  beq @r
  jmp @sl
@r:
  rtl

; lines since vblank began (A16 out); 37+ = vblank is over
SS_Line:
  A8
  lda $213F
  lda $2137
  lda $213D
  xba
  lda $213D
  and #1
  xba
  A16
  sec
  sbc #225
  bcs :+
  adc #262
: rts


; ================================================================ v1.2 boss: sprite-stacked part groups
; The robot is drawn as 4 part frames from tools/boss_vox.py (OAM lists in boss_parts.inc), front to back:
; head + crest (5 yaws, turns to track you), left arm, right arm (down / cannon / spread), body (clean /
; battle-damaged below 1/3 health). Occlusion between the parts is baked into the frames.
.segment "BOSSB"                 ; v1.3: the part lists live in their own bank (read with long loads)
.include "../assets/boss_parts.inc"
.segment "XCODE"
BP_HEAD0 = 4
BP_ARM   = 7
BP_CMB   = 13                ; v1.3: merged body + arms lists (combo * 2 + damaged)
X_BossDraw:
  lda #0
  ldx view
  cpx #VIEW_COCK
  bne :+
  lda #BPIdx_cock-BPIdx_chase
: sta bd_vo
  lda obj_pri
  xba
  and #$FF00
  sta bd_t                   ; priority bits into the attr byte
  ; ---- head yaw: toward you (screen centre), one step every 8 frames; straight ahead while the beam fires
  lda b_sx
  sec
  sbc #128
  ldx #BP_HEAD0
  cmp #.loword(-56)
  bpl :+
  ldx #BP_HEAD0+2            ; far left of the screen: look right (at you)
  bra @ht
: cmp #.loword(-20)
  bpl :+
  ldx #BP_HEAD0+1
  bra @ht
: cmp #57
  bmi :+
  ldx #BP_HEAD0-2
  bra @ht
: cmp #21
  bmi @ht
  ldx #BP_HEAD0-1
@ht:
  lda bm_on
  beq :+
  ldx #BP_HEAD0
: stx bp_k
  lda b_hy
  bne :+
  lda #BP_HEAD0
  sta b_hy
: lda frame
  and #7
  bne @hd
  lda b_hy
  cmp bp_k
  beq @hd
  bcc :+
  dec b_hy
  bra @hd
: inc b_hy
@hd:
  ; ---- list of (part id, dx, dy): head, left arm, right arm, body
  lda b_hy
  sta bp_l
  lda #0                     ; arm poses: spread while the beam charges, cannon when raised
  ldx b_atk
  cpx #ATK_BEAM
  beq @spr
  cpx #ATK_SHARD
  bne :+
  lda b_at                   ; v1.3 spin: arms out, then 4 frames a step: head and arms swing round
  cmp #14
  bcc @spr
  cmp #66
  bcs @spr
  and #$000C
  lsr
  tax
  lda f:SpinHd,x
  sta bp_l
  lda f:SpinAL,x
  sta bp_l+2
  lda f:SpinAR,x
  sta bp_l+3
  bra @bd
@spr:
  lda #BP_ARM+4
  sta bp_l+2
  inc a
  sta bp_l+3
  bra @bd
: lda b_arm
  lsr
  lda #BP_ARM                ; left: down / cannon
  bcc :+
  lda #BP_ARM+2
: sta bp_l+2
  lda b_arm
  and #2
  beq :+
  lda #BP_ARM+3
  bra :++
: lda #BP_ARM+1
: sta bp_l+3
@bd:
  lda #0                     ; body: clean / damaged (scorched palette time)
  ldx b_dark
  beq :+
  inc a
: sta bp_l+4                 ; (byte list: head, armL, armR, body in bp_l+0, +2, +3, +4; dy for arms below)
  A8
  lda bp_l
  sta bp_l+1
  A16
  ; v1.3: no recoil running: body + both arms are one pre-merged list (rows: arm cells before body cells)
  lda #5
  sta bp_e
  lda b_mf
  bne @sep
  lda bp_l+2
  and #$00FF
  sec
  sbc #BP_ARM
  lsr
  sta t0                     ; left pose 0..2
  asl
  adc t0
  sta t0
  lda bp_l+3
  and #$00FF
  sec
  sbc #BP_ARM+1
  lsr
  clc
  adc t0
  tax
  lda f:CmbTab,x
  and #$00FF
  cmp #$00FF
  beq @sep
  asl
  ora bp_l+4
  and #$00FF
  clc
  adc #BP_CMB
  A8
  sta bp_l+2
  A16
  lda #3
  sta bp_e
@sep:
  ; ---- draw: part ids in bytes bp_l+1 .. bp_e-1
  ldy oam_idx
  lda #1
  sta bp_n
@part:
  ldx bp_n
  lda bp_l,x
  and #$00FF
  sta bp_k                   ; part id
  ; per-part offset: arms breathe 1 px, the firing arm kicks up 3 px
  lda b_sy
  cpx #2
  bcc @noff
  cpx #4
  bcs @noff
  pha
  lda b_mf
  beq :+
  txa                        ; X = 2 left arm, 3 right arm; b_side 0 = left
  dec a
  dec a
  cmp b_side
  bne :+
  pla
  sec
  sbc #3
  pha
: pla
@noff:
  sta bp_sy
  lda bp_k                   ; index entry: 16 bytes (v1.3)
  asl
  asl
  asl
  asl
  clc
  adc bd_vo                  ; + the cockpit table's offset
  tax
  lda f:BPIdx_chase+2,x
  sta t3                     ; entries
  lda b_sx                   ; fast path: the part inside the screen horizontally, rows clipped
  sec
  sbc f:BPIdx_chase+4,x
  bpl :+
  jmp @slow
: lda f:BPIdx_chase+6,x
  sec
  sbc b_sx
  bpl :+
  jmp @slow
: lda f:BPIdx_chase,x
  sta bp_d
  lda f:BPIdx_chase+8,x      ; first row dy
  clc
  adc bp_sy
  sta t0                     ; y0: screen y of row 0
  cmp #.loword(-15)
  bmi @clip                  ; (signed: |y0| small)
  clc
  adc f:BPIdx_chase+10,x     ; + 16 * rows
  cmp #240
  bcs @clip
  lda t3                     ; all rows on screen
  bra @room
@clip:
  ; rows k0 <= k < k1 touch the screen: k0 = max(0, floor(-y0 / 16)), k1 = min(rows, ceil((224 - y0) / 16))
  lda f:BPIdx_chase+12,x
  sta t7                     ; row table
  lda f:BPIdx_chase+10,x
  lsr
  lsr
  lsr
  lsr
  sta t6                     ; rows
  lda #0
  sec
  sbc t0
  bpl :+
  lda #0
: lsr
  lsr
  lsr
  lsr
  sta t1
  lda #224+15
  sec
  sbc t0
  bpl :+
  jmp @pn                    ; below the screen
: lsr
  lsr
  lsr
  lsr
  cmp t6
  bcc :+
  lda t6
: sec
  sbc t1
  beq @pnj
  bpl :+
@pnj:
  jmp @pn                    ; nothing on screen
: sta t2                     ; visible rows
  lda t1
  asl
  clc
  adc t7
  tax
  lda f:BPRows,x
  sta t5                     ; first visible entry (byte offset)
  txa
  clc
  adc t2
  adc t2
  tax
  lda f:BPRows,x
  sec
  sbc t5
  lsr
  lsr
  lsr                        ; visible entries
  pha
  lda t5
  clc
  adc bp_d
  sta bp_d
  pla
@room:
  sta t3
  asl
  asl
  sta t0
  tya
  clc
  adc t0
  cmp #513
  bcc :+
  jmp @slow2                 ; no room: the clipping path for the whole part
: lda bp_sy
  xba
  and #$FF00
  clc
  adc b_sx
  sta t4                     ; (sy<<8)+sx
  ; v1.3: straight-line copy, up to 64 sprites per pass (entered part-way: entries n-1 .. 0)
@fc:
  lda t3
  cmp #97
  bcc :+
  lda #96
: sta t6                     ; this pass
  asl
  tax
  lda f:BDUnTab-2,x
  sta t7
  ldx bp_d
.ifndef BDX2
  pea .loword(@fdone-1)      ; the copy ends in an rts
  jmp (t7)
.endif
@fdone:
  lda t6                     ; Y += 4n, data += 8n
  asl
  asl
  sta t0
  tya
  clc
  adc t0
  tay
  lda t0
  asl
  clc
  adc bp_d
  sta bp_d
  lda t3
  sec
  sbc t6
  sta t3
  bne @fc
  jmp @pn
@slow2:
  lda bp_k
  asl
  asl
  asl
  asl
  clc
  adc bd_vo
  tax
  lda f:BPIdx_chase+2,x
  sta t3
  lda b_sx
  sta bp_sx
@slow:
.ifdef FASTONLY
  jmp @pn
.endif
  lda b_sx
  sta bp_sx
  lda f:BPIdx_chase,x
  tax
@sl:
  cpy #512
  bcs @pn
  lda f:BPData+4,x
  clc
  adc bp_sy
  sta sy
  clc
  adc #16
  cmp #240
  bcs @sn                    ; y < -16 or y >= 224
  lda f:BPData+2,x
  clc
  adc bp_sx
  sta sx
  clc
  adc #16
  cmp #272
  bcs @sn
  A8
  lda sx
  sta oam_lo,y
  lda sy
  sta oam_lo+1,y
  A16
  lda f:BPData+6,x
  ora bd_t
  A8
  xba
  sta oam_lo+3,y
  xba
  sta oam_lo+2,y
  A16
  lda sx
  bpl :+
  phx
  phy
  tya
  and #$000C
  ora #1                     ; HiTab column 1 = the 9th x bit
  tax
  tya
  lsr
  lsr
  lsr
  lsr
  tay
  A8
  lda .loword(HiTab),x
  ora oam_hi,y
  sta oam_hi,y
  A16
  ply
  plx
: iny
  iny
  iny
  iny
@sn:
  txa
  clc
  adc #8
  tax
  dec t3
  bne @sl
@pn:
  inc bp_n
  lda bp_n
  cmp bp_e
  beq :+
  jmp @part
: sty oam_idx
  rtl
.repeat 96, I
  .ident(.sprintf("BDUn%d", 95-I)):
  lda f:BPData+8*(95-I),x
  clc
  adc t4
  sta oam_lo+4*(95-I),y
  lda f:BPData+8*(95-I)+6,x  ; (priority bits baked in per view)
  sta oam_lo+4*(95-I)+2,y
.endrepeat
  rts
CmbTab: .byte 0, 2, 6, 1, 3, $FF, 5, $FF, 4   ; [left pose * 3 + right pose] -> combo (poses: down, cannon, spread)
SpinHd: .word BP_HEAD0-2, BP_HEAD0, BP_HEAD0+2, BP_HEAD0
SpinAL: .word BP_ARM+4, BP_ARM+4, BP_ARM, BP_ARM
SpinAR: .word BP_ARM+1, BP_ARM+5, BP_ARM+5, BP_ARM+1
BDUnTab:
.repeat 96, I
  .word .loword(.ident(.sprintf("BDUn%d", I)))
.endrepeat


; ================================================================ v1.2 tumbling objects (NMI)
; Debris chunks, missiles, capsules and crest shards: 8 sprite-stacked frames each in ROM (tumble.bin). Two
; of the sheet's frames are refreshed per vblank, round robin, after every other VRAM job (line budget).
.include "../assets/tumble.inc"
TB_LINES = 31
SetBit: .word 1, 2, 4, 8, 16, 32, 64, 128
X_Tumble:
.ifdef NOTUMBLE
  rtl
.endif
  lda tb_cur                 ; nothing tumbling on screen
  bne :+
  rtl
: lda b_gfx                  ; sheet rows streaming: tiles in flux
  lsr
  bcc :+
  lda #$FFFF
  sta tb_tab
  rtl
: ldx #TbOver-TbChase
  lda view
  cmp #VIEW_OVER
  beq @t
  ldy b_gfx                  ; (0 field sheet, 2 boss sheet)
  cmp #VIEW_COCK
  beq @ck
  ldx #0
  cpy #2
  bne @t
  ldx #TbChaseB-TbChase
  bra @t
@ck:
  ldx #TbCock-TbChase
  cpy #2
  bne @t
  ldx #TbCockB-TbChase
@t:
  cpx tb_tab                 ; another list (view / sheet changed): nothing known to be in VRAM
  beq :++
  stx tb_tab
  lda #$FFFF
  sta tb_ph
  ldy #14
: sta tb_hv,y
  dey
  dey
  bpl :-
: stx n_k
  lda frame
  lsr
  lsr
  lsr
  sta n_i                    ; animation phase (7.5 frames / s)
  cmp tb_ph                  ; everything drawn is up to date for this phase: done
  bne :+
  lda tb_cur
  cmp tb_pc
  bne :+
  rtl
: lda f:TbChase,x            ; entries
  sta tb_n
  jsr SS_Line
  cmp #TB_LINES
  bcc :+
  rtl
:
  ldy tb_n                   ; one lap at most, one upload per vblank
@sk:
  lda tb_i
  cmp tb_n
  bcc :+
  lda #0
  sta tb_i
: asl
  asl
  clc
  adc n_k
  tax                        ; X = entry offset - 2 (entries start at +2)
  lda f:TbChase+4,x          ; frame set
  sta n_t
  asl
  phx
  tax
  lda f:SetBit,x
  plx
  and tb_cur
  beq @nx
  phx
  lda tb_i
  asl
  tax
  lda n_t                    ; wanted frame: phase + set * 3
  asl
  adc n_t
  adc n_i
  and #7
  cmp tb_hv,x
  bne @go
  plx
@nx:
  inc tb_i
  dey
  bne @sk
  lda n_i                    ; a whole lap without uploads
  sta tb_ph
  lda tb_cur
  sta tb_pc
  rtl
@go:
  sta tb_hv,x
  plx
  xba
  lsr                        ; frame * 128
  sta n_k
  lda n_t
  xba
  asl
  asl                        ; set * 1024
  clc
  adc n_k
  clc
  adc #.loword(TumbleFrames)
  sta A1T0L
  A8
  lda #$80
  sta VMAIN
  lda #$01
  sta DMAP0
  lda #$18
  sta BBAD0
  lda #^TumbleFrames
  sta A1B0
  A16
  lda f:TbChase+2,x          ; sheet tile
  asl
  asl
  asl
  asl
  clc
  adc #$6000
  sta VMADDL
  sta n_t
  lda #64
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
  lda n_t
  clc
  adc #16*16
  sta VMADDL
  lda #64                    ; (A1T0 has advanced by 64)
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
  inc tb_i
@r:
  rtl

.segment "BANK11"
M7MapB:   .incbin "../assets/m7mapB.bin"
M7TilesB: .incbin "../assets/m7tilesB.bin"

.segment "CODE"

.segment "BANK13"
JetFrames:  .incbin "../assets/jetframes.bin"     ; 15 x 64x64 (8 rows of 8 tiles)
.segment "BANK15"
PropMid: .incbin "../assets/propmid.bin"         ; per stage: 4 mid + 4 far 16x16 prop frames
TumbleFrames: .incbin "../assets/tumble.bin"      ; 8 sets x 8 frames x 16x16 (v1.2)
.segment "BANK14"
SlotFrames: .incbin "../assets/slotframes.bin"   ; 32x32 (4 rows of 4 tiles): 9 enemy yaws
; v1.2: near ground prop frames (13 models x 16 yaws x 512 B), 64 frames per bank from $90
.segment "PROPB0"
PropFrames: .incbin "../assets/propframes.bin", 0, 32768
.segment "PROPB1"
  .incbin "../assets/propframes.bin", 32768, 32768
.segment "PROPB2"
  .incbin "../assets/propframes.bin", 65536, 32768
.segment "PROPB3"
  .incbin "../assets/propframes.bin", 98304
; v1.2: prop offsets rotated for every heading (headings 0-127 in $94, 128-255 in $95)
.segment "PROPB4"
PropRot: .incbin "../assets/proprot.bin", 0, 128*NPROPS*2
.segment "PROPB5"
  .incbin "../assets/proprot.bin", 128*NPROPS*2
.segment "CODE"
