; =====================================================================
;  boss.s - the giant robot at the end of the wave sequence (boss v1)
;  WARNING -> flies down into view -> fight (3 phases) -> multi-explosion -> MISSION COMPLETE
;  Drawn as a 96x128 metasprite of 16x16 pieces (left half + h-flipped right half) from a boss OBJ
;  sheet streamed into VRAM during the WARNING; palette 7 animated (eyes / chest gem / hit flashes).
;  Music: the SPC700 is rebooted and the boss song is uploaded in the main loop's idle time.
; =====================================================================
.include "../assets/boss.inc"
.include "../assets/boss_fast.inc"
.include "../music/build/boss_up.inc"
.include "../music/build/field_up.inc"
.include "../music/build/title_up.inc"
.include "../music/build/boss_music.inc"

BS_OFF   = 0
BS_WARN  = 1
BS_ENTER = 2
BS_FIGHT = 3
BS_DYING = 4
BS_DONE  = 5
T_BOSS   = $82                ; wave script: the boss (waits for a clear sky first)
BOSS_TG  = $40                ; ms_tg value: your missile is locked on the boss
K_BOSS   = 5                  ; SFX follows the boss
K_BEAM   = 6                  ; SFX follows the chest beam's sweep
T_BIGBOOM = 7                 ; en_ty of a boss explosion (always the big fireball frames)
BZ_CAM   = 260                ; boss distance from the camera (px): same scale in chase + cockpit
EYE_DH   = 31                 ; eyes above the chest gem (world px)
BH_REST  = -16                ; rest height of the gem relative to you (px): below you, eyes above
WARN_T   = 200
ENTER_T  = 168
DYING_T  = 170                ; = the jingle's 2 silent bars, so MISSION COMPLETE lands on its fanfare
DONE_T   = 290
HP_BASE  = 150                ; boss v2 (was 280)
HP_MAX   = 262                 ; cap reached on loop 8 (was 480)
ATK_CANNON = 1
ATK_VOLLEY = 2
ATK_BEAM   = 3
ATK_SHARD  = 4
DMG_BEAM = 5
DMG_SHARD = 3
SA_BCANNON = SFXA_BCANNON
SA_CHARGE  = SFXA_CHARGE
SA_SHARDS  = SFXA_SHARDS
SA_PING    = SFXA_PING
SA_WEAK    = SFXA_WEAK
SB_RUMBLE  = SFXB_RUMBLE
SB_BEAM    = SFXB_BEAM
SB_SHARDW  = SFXB_SHARDW
SB_MEGA    = SFXB_MEGABOOM
SB_BMSL    = SFXB_BMSL
RD_BOSS  = 32                 ; text row: boss health bar
MU_FIELD = 0
MU_BOSS  = 1
MU_TITLE = 2

.segment "BSS"
b_st:    .res 2
b_t:     .res 2
b_x:     .res 2               ; 1/16 px, jet-relative (like the enemies)
b_z:     .res 2
b_h:     .res 2               ; gem height relative to you (1/16 px)
b_tx:    .res 2               ; strafe target x (px)
b_mvt:   .res 2               ; frames to the next strafe target
b_hp:    .res 2
b_hpmax: .res 2
b_ph:    .res 2               ; phase 0..2
b_cd:    .res 2               ; frames to the next attack
b_atk:   .res 2               ; current attack (0 = none)
b_at:    .res 2               ; attack timer
b_seq:   .res 2
b_arm:   .res 2               ; bit 0: left arm raised, bit 1: right arm raised
b_side:  .res 2
b_n:     .res 2
b_fg:    .res 2               ; hit flash timers: gem, eyes, whole body
b_fe:    .res 2
b_fb:    .res 2
b_mf:    .res 2               ; muzzle flash timer
b_mfx:   .res 2               ; muzzle flash side (-1/+1)
b_ping:  .res 2
pg_x:    .res 2               ; armour ping flash: x px, frames left
pg_t:    .res 2
b_vis:   .res 2
b_sx:    .res 2               ; last drawn gem position (screen)
b_sy:    .res 2
b_seg:   .res 2               ; health bar segments shown
b_bonus: .res 2
b_smk:   .res 2
b_galt:  .res 2               ; hover goal for the gem (absolute, in 'alt' units)
b_gt:    .res 2               ; frames to the next hover goal
b_aim:   .res 2               ; frames left showing the aim hint
b_cgem:  .res 2               ; animated colours (BGR555) for the NMI
b_ceye:  .res 2
b_cbody: .res 2
alt_prev: .res 2
bm_on:   .res 2               ; beam: 1 = telegraph, 2 = firing
bm_x:    .res 2               ; beam end point x (1/16 px)
bm_dir:  .res 2
bm_dh:   .res 2               ; beam height relative to the gem (1/16 px)
bm_warn: .res 2
b_gfx:   .res 2               ; 0 field sheet, 1 streaming boss rows, 2 boss sheet, 3 streaming field rows
vs_i:    .res 2               ; rows streamed so far
vs_view: .res 2
b_palq:  .res 2
bn_row:  .res 2               ; (NMI only)
b_wt:    .res 2               ; 1 = upload BossPal, 2 = upload NavyPal (NMI)
eb_k:    .res NEB*2           ; enemy round kind: 0 tracer, 1 crest shard
mu_img:  .res 2               ; ARAM image running: 0 field, 1 boss, $FF in transfer
mu_want: .res 2
mu_tgt:  .res 2
mu_st:   .res 2               ; 0 idle, 1 waiting for the IPL, 2 sending blocks
mu_blk:  .res 2
mu_n:    .res 2
mu_len:  .res 2
mu_pos:  .res 2
mu_kick: .res 2
mu_to:   .res 2
mu_ff:   .res 2               ; frames left holding $FF on port 0 (victory jingle)
mu_dead: .res 2
mu_stamp: .res 2
bd_offl:  .res 2           ; BossDraw scratch
bd_offr:  .res 2
bd_atr:   .res 2
bd_dx:    .res 2
bd_t:     .res 2
eb_lim:   .res 2           ; enemy tracer / missile slots the per-frame loops walk
em_lim:   .res 2

.segment "CODE"
.a16
.i16
; ---------------------------------------------------------------- start / stop
BossStart:
  lda #BS_WARN
  sta b_st
  stz b_t
  stz b_atk
  stz b_arm
  stz bm_on
  stz bm_warn
  stz b_vis
  stz b_seq
  stz b_ph
  stz b_fg
  stz b_fe
  stz b_fb
  stz b_mf
  stz b_wt
  lda #$FFFF
  sta b_seg
  lda diff
  asl
  asl
  asl
  asl                        ; +16 per loop (boss v2; was +32)
  clc
  adc d_hpb                  ; difficulty: HP_BASE on NORMAL
  cmp d_hpm
  bcc :+
  lda d_hpm                  ; (the bar maths needs hpmax/2 < 256)
: sta b_hp
  sta b_hpmax
  lda alt
  sta alt_prev
  lda #MU_BOSS
  sta mu_want
  lda #NEB*2
  sta eb_lim
  lda #NEM*2
  sta em_lim
  lda #1
  sta b_palq
  lda view
  cmp #VIEW_OVER             ; the overhead camera only sees ~100 px ahead: the fight is chase/cockpit
  bne @persp
  lda #VIEW_CHASE
  sta view
  lda #2
  sta b_gfx                  ; LoadView loads the whole boss sheet
  jsr LoadView
  bra @r
@persp:
  lda #1
  sta b_gfx                  ; stream the boss rows during the WARNING
  stz vs_i
  lda view
  sta vs_view
@r:
  lda row_dirty
  ora #RD_ALL|RD_BOSS
  sta row_dirty
  rts

; game over / restart while the boss is up: everything back to the field state
BossAbort:
  lda b_st
  bne :+
  rts
: stz b_st
  jsr SlotsField
  stz b_aim
  stz bm_on
  stz bm_warn
  stz b_arm
  stz b_vis
  jsr BossGfxBack
  lda #MU_FIELD
  sta mu_want
  lda row_dirty
  ora #RD_ALL|RD_BOSS
  sta row_dirty
  rts

; field limits: the waves use the first 6 tracer / 2 missile slots, so the loops skip the boss-only ones
SlotsField:
  ldx #(NEB-6)*2-2
: stz eb_t+12,x
  dex
  dex
  bpl :-
  stz em_st+4
  stz em_st+6
  lda #6*2
  sta eb_lim
  lda #2*2
  sta em_lim
  rts

BossGfxBack:
  lda b_gfx
  beq @r
  lda #3
  sta b_gfx
  stz vs_i
  lda view
  sta vs_view
  lda #2
  sta b_palq
@r:
  rts

; debug shortcut (paused: hold L+R, press SELECT): clear the sky and jump to the boss entry
BossWarp:
  ldx #NEN*2-2
: stz en_st,x
  dex
  dex
  bpl :-
  ldx #NEB*2-2
: stz eb_t,x
  dex
  dex
  bpl :-
  ldx #NEM*2-2
: stz em_st,x
  dex
  dex
  bpl :-
  lda b_st
  bne @r
  lda #(WaveBoss-WaveData)
  sta wave_pos
  stz wave_tm
@r:
  rts

; ---------------------------------------------------------------- per physics step
BossStep:
  lda b_st
  bne :+
  rts
: ; your climb / dive moves the boss (and his beam) relative to you: 2 px per altitude level
  lda alt
  sec
  sbc alt_prev
  ASR4
  jsr Asr2
  sta t0                    ; / 64 ... * 2 px * 16 = /8 overall
  lda alt
  sta alt_prev
  lda t0
  asl
  eor #$FFFF
  sec
  adc b_h
  sta b_h
  lda b_fg
  beq :+
  dec b_fg
: lda b_fe
  beq :+
  dec b_fe
: lda b_fb
  beq :+
  dec b_fb
: lda b_mf
  beq :+
  dec b_mf
: lda pg_t
  beq :+
  dec pg_t
: lda b_ping
  beq :+
  dec b_ping
: inc b_t
  lda b_st
  asl
  tax
  jmp (.loword(BossStates),x)
BossStates: .word .loword(BsNone), .loword(BsWarn), .loword(BsEnter), .loword(BsFight), .loword(BsDying), .loword(BsDone)
BsNone:
  rts

BsWarn:
  lda mu_st                 ; the WARNING clock holds until the boss song is in (at most 3 s)
  beq :+
  lda b_wt
  cmp #180
  bcs :+
  inc b_wt
  dec b_t
  rts
: lda b_t
  and #15
  bne :+
  lda row_dirty
  ora #RD_SKYA|RD_SKYB|RD_WARN|RD_HINT
  sta row_dirty
: lda b_t
  cmp #WARN_T
  bcs :+
  rts
: lda #BS_ENTER
  sta b_st
  stz b_t
  lda #1
  sta b_vis
  stz b_x
  lda #BZ_CAM
  sec
  sbc zoff
  asl
  asl
  asl
  asl
  sta b_z
  lda #150*16
  sta b_h
  stz b_tx
  lda #60
  sta b_mvt
  lda row_dirty
  ora #RD_ALL|RD_BOSS
  sta row_dirty
  rts

BsEnter:
  jsr BossRumble
  ; descend: ease toward the rest height
  lda #.loword(BH_REST*16)
  sec
  sbc b_h
  jsr Asr4
  jsr Asr2
  ora #0
  bne :+
  lda #.loword(-1)
: clc
  adc b_h
  sta b_h
  jsr BossMoveXZ
  lda b_t
  cmp #ENTER_T
  bcs :+
  rts
: lda #BS_FIGHT
  sta b_st
  stz b_t
  lda #50
  sta b_cd
  lda alt                    ; first hover height: where he arrived (gem 16 px below you)
  sec
  sbc #$0800
  jsr ClampGoal
  sta b_galt
  lda #240
  sta b_gt
  sta b_aim
  lda row_dirty
  ora #RD_HINT
  sta row_dirty
  rts

ClampGoal:                   ; keep the gem (and the eyes, 31 px above it) inside your altitude range
  cmp #$8000
  bcs @lo
  cmp #$0800
  bcc @lo
  cmp #$2E00
  bcc :+
  lda #$2E00
: rts
@lo:
  lda #$0800
  rts

BsFight:
  jsr BossRumble
  jsr BossMoveXZ
  jsr BossBob
  jsr BossPhase
  jsr BossAttack
  jsr BossHits
  jsr BossSmoke
  lda b_hp
  beq :+
  rts
: ; ---- defeated
  lda #BS_DYING
  sta b_st
  stz b_t
  stz b_atk
  stz bm_on
  stz bm_warn
  stz b_arm
  stz b_aim
  lda #4
  sta mu_ff                 ; $FF on port 0: the boss song turns into the victory jingle
  ldx #NEB*2-2              ; his rounds vanish with him
: stz eb_t,x
  dex
  dex
  bpl :-
  ldx #NEM*2-2
: stz em_st,x
  dex
  dex
  bpl :-
  stz warn
  lda #INV_SPAWN
  sta p_inv
  lda row_dirty
  ora #RD_BOSS|RD_HINT|RD_WARN
  sta row_dirty
  rts

BsDying:
  lda b_t
  and #7
  bne @nb
  lda b_t
  cmp #DYING_T-36
  bcs @nb
  jsr BossBoom
@nb:
  lda b_t                   ; a mega boom every 40 frames, panned to where it went off
  cmp #2
  beq @mega
  cmp #42
  beq @mega
  cmp #82
  beq @mega
  cmp #DYING_T-40
  beq @final
  bra @nm
@final:
  ldx #5
: phx
  jsr BossBoom
  plx
  dex
  bne :-
  lda #24
  sta flash_t
  lda #30
  sta shake_t
@mega:
  jsr Rand
  and #$00FF
  sec
  sbc #128
  sta sfx_nfx
  lda b_z
  ASR4
  sta sfx_nfz
  lda #K_FIX
  sta sfx_nk
  lda #SB_MEGA
  ldx #6
  ldy #90
  jsr SfxB
  lda #12
  sta shake_t
  lda #8
  sta flash_t
  ; debris tearing past your ears, alternating sides (channel A)
  lda b_t
  and #64
  beq :+
  lda #SA_DEBLR
  bra :++
: lda #SA_DEBRL
: ldx #3
  ldy #26
  jsr SfxA
@nm:
  lda b_t                   ; sinks and shudders
  and #1
  bne :+
  lda b_h
  sec
  sbc #6
  sta b_h
: lda b_t
  cmp #DYING_T-30
  bne :+
  stz b_vis
: lda b_t
  cmp #DYING_T
  bcs :+
  rts
: ; ---- MISSION COMPLETE
  lda #BS_DONE
  sta b_st
  stz b_t
  lda diff
  asl
  sta t0
  asl
  asl
  clc
  adc t0                    ; 10 * loop
  clc
  adc #50                   ; bonus (x100 points): 5000 + 1000 per loop
  sta b_bonus
  clc
  adc score
  cmp #10000
  bcc :+
  lda #9999
: sta score
  jsr ScoreText
  jsr ScoreLife
  jsr BossGfxBack
  lda row_dirty
  ora #RD_ALL|RD_BOSS
  sta row_dirty
  rts

BsDone:
  lda b_t
  cmp #DONE_T
  bcs :+
  rts
: stz b_st
  jsr SlotsField
  lda #MU_FIELD
  sta mu_want
  lda #60
  sta wave_tm
  lda row_dirty
  ora #RD_ALL|RD_BOSS
  sta row_dirty
  rts

; ---------------------------------------------------------------- movement
BossMoveXZ:
  ; your turn swings him sideways (like everything else), then he steers back in front of you
  lda b_z
  jsr RotTerm
  eor #$FFFF
  sec
  adc b_x
  sta b_x
  dec b_mvt
  bpl @st
  jsr Rand
  and #$007F
  sec
  sbc #64                   ; -64..63 px
  sta b_tx
  jsr Rand
  and #$003F
  clc
  adc #70
  sta b_mvt
@st:
  lda b_tx
  asl
  asl
  asl
  asl
  sec
  sbc b_x
  jsr Asr4
  jsr Asr2                  ; 1/64 of the gap per frame...
  cmp #$8000
  bcs @neg
  cmp #20
  bcc @add
  lda #20                   ; ...at most 1.25 px per frame
  bra @add
@neg:
  cmp #.loword(-20)
  bcs @add
  lda #.loword(-20)
@add:
  clc
  adc b_x
  cmp #$8000
  bcs :+
  cmp #200*16
  bcc @sx
  lda #200*16
  bra @sx
: cmp #.loword(-200*16)
  bcs @sx
  lda #.loword(-200*16)
@sx:
  sta b_x
  ; distance: same apparent size in chase and cockpit
  lda #BZ_CAM
  sec
  sbc zoff
  asl
  asl
  asl
  asl
  sec
  sbc b_z
  jsr Asr4
  clc
  adc b_z
  sta b_z
  rts

; hover bob + drift back to the rest height (you can climb / dive away from it to line up the shots)
BossBob:
  ; every 4-6 s he picks a new hover height (world fixed: you match it to hit the gem / eyes)
  dec b_gt
  bpl @g
  jsr Rand
  and #$00FF
  sta t0
  asl
  sta t1
  asl
  asl
  asl
  asl
  clc
  adc t1
  adc t1
  adc t0
  adc t0                     ; * 38 ($26): 0..$25DA
  clc
  adc #$0800
  jsr ClampGoal
  sta b_galt
  jsr Rand
  and #$007F
  clc
  adc #240
  sta b_gt
@g:
  lda b_aim
  beq :+
  dec b_aim
  bne :+
  lda row_dirty
  ora #RD_HINT
  sta row_dirty
: ; target = (goal - alt) / 8 (1/16 px) + bob
  lda b_galt
  sec
  sbc alt
  cmp #$8000
  ror
  cmp #$8000
  ror
  cmp #$8000
  ror
  sta t2
  lda frame
  asl
  asl
  and #$01FE
  tax
  lda f:SinTab,x
  ldx #80                    ; +-5 px bob
  jsr MulB
  clc
  adc t2
  sec
  sbc b_h
  ldx b_atk                  ; the beam keeps him steady
  cpx #ATK_BEAM
  bne :+
  lda #0
: jsr Asr4
  jsr Asr2
  cmp #$8000
  ror                        ; 1/128 of the gap per frame
  clc
  adc b_h
  cmp #$8000
  bcs :+
  cmp #60*16
  bcc @s
  lda #60*16
  bra @s
: cmp #.loword(-70*16)
  bcs @s
  lda #.loword(-70*16)
@s:
  sta b_h
  rts

BossRumble:
  lda sfxb_t                 ; engine rumble whenever channel B is free (lowest priority)
  bne :+
  lda #K_BOSS
  sta sfx_nk
  lda #SB_RUMBLE
  ldx #0
  ldy #230
  jmp SfxB
: rts

BossPhase:
  ; phase 1 above 2/3 health, phase 2 above 1/3, then phase 3
  lda b_hpmax
  jsr Third
  sta t0
  lda b_hp
  cmp t0
  bcs :+
  lda #2
  bra @s
: lda t0
  asl
  cmp b_hp
  bcs :+
  lda #0
  bra @s
: lda #1
@s:
  cmp b_ph
  beq :+
  sta b_ph
  stz b_seq
: rts

Third:                       ; A = A / 3 (A < 1024): (A * 86) >> 8
  ldx #86
  jmp MulSmall

; health bar segments (0..24) = hp * 12 / (hpmax / 2)
BossSegs:
  lda b_hp
  asl
  asl
  sta t0
  asl
  clc
  adc t0
  pha
  lda b_hpmax
  lsr
  tax
  pla
  jmp DivU

; ---------------------------------------------------------------- attacks
PatLen:  .word 3, 4, 6
PatOff:  .word 0, 3, 7
PatTab:  .word ATK_CANNON, ATK_CANNON, ATK_VOLLEY
         .word ATK_CANNON, ATK_BEAM, ATK_VOLLEY, ATK_CANNON
         .word ATK_SHARD, ATK_CANNON, ATK_BEAM, ATK_VOLLEY, ATK_SHARD, ATK_CANNON
GapTab:  .word 96, 76, 60
NShot:   .word 3, 5, 7
BossFastIdx: .repeat 8, I
  .word I*BOSS_FAST_N*4
.endrepeat
NMsl:    .word 2, 3, 4

BossAttack:
  lda b_atk
  bne @run
  lda p_dead                 ; holds fire while you're down
  ora gameover
  bne @r
  dec b_cd
  bpl @r
  lda b_ph
  asl
  tax
  lda b_seq
  cmp PatLen,x
  bcc :+
  lda #0
: sta t0
  inc a
  sta b_seq
  lda t0
  clc
  adc PatOff,x
  asl
  tax
  lda PatTab,x
  sta b_atk
  stz b_at
@run:
  lda b_atk
  asl
  tax
  jmp (.loword(AtkJump),x)
@r:
  rts
AtkJump: .word .loword(AtkDone), .loword(AtkCannon), .loword(AtkVolley), .loword(AtkBeam), .loword(AtkShard)

AtkDone:
  stz b_atk
  stz b_arm
  lda b_ph
  asl
  tax
  lda GapTab,x
  sta t0
  lda diff
  asl
  asl
  eor #$FFFF
  sec
  adc t0
  cmp #36
  bcs :+
  lda #36
: sta b_cd
  rts

; arm cannon: one arm comes up (30 frames of warning), then a fan of 3/5/7 rounds aimed around you
AtkCannon:
  inc b_at
  lda b_at
  cmp #1
  bne @a1
  lda b_side
  eor #1
  sta b_side
  inc a
  sta b_arm                  ; 1 = left arm, 2 = right arm
  rts
@a1:
  cmp #30
  beq @fire
  cmp #52
  beq @rf94658
  jmp @a2
@rf94658:
  lda b_ph
  cmp #2
  beq @rf8403
  jmp @r
@rf8403:
@fire:
  ; muzzle: 58 px out to that side, 8 px below the gem
  lda #.loword(-58*16)
  ldx b_side
  beq :+
  lda #58*16
: sta t5
  clc
  adc b_x
  sta fe_x
  lda b_z
  sta fe_z
  lda b_h
  sec
  sbc #8*16
  sta fe_h
  lda #6
  sta b_mf
  lda t5
  ASR4
  clc
  adc b_x
  ASR4
  sta sfx_nfx                ; the blast comes from that arm
  lda b_z
  ASR4
  sta sfx_nfz
  lda #K_FIX
  sta sfx_nk
  lda #SA_BCANNON
  ldx #3
  ldy #12
  jsr SfxA
  ; fan: aim points k * 22 px apart around you (centre round straight at you)
  lda b_ph
  asl
  tax
  lda NShot,x
  ldy b_at
  cpy #52
  bne :+
  sec
  sbc #4                     ; phase-3 follow-up fan: the 3 middle gaps (10 rounds up at once, keeps 60 fps)
: sta b_n
  sta c_j
  dec a
  lsr
  sta ck_half                ; half count
@k:
  lda c_j
  dec a
  sec
  sbc ck_half                ; -half..+half
  sta ck_k
  asl
  asl
  asl
  asl
  clc
  adc ck_k
  adc ck_k
  adc ck_k
  adc ck_k
  adc ck_k
  adc ck_k                   ; * 22
  ldx b_at
  cpx #52
  bne :+
  clc
  adc #11                    ; second fan offset by half a gap
: sta fe_ax
  stz fe_ah
  stz fe_k
  jsr FireFrom
  dec c_j
  bne @k
@r:
  rts
@a2:
  cmp #64
  bcc @r
  jmp AtkDone

; homing volley: 2/3/4 missiles off alternating shoulders, 16 frames apart
AtkVolley:
  inc b_at
  lda b_at
  cmp #1
  bne :+
  lda b_ph
  asl
  tax
  lda NMsl,x
  sta b_n
  lda #3
  sta b_arm
  lda #8
  sta b_at
: lda b_n
  bne @rf32216
  jmp @wait
@rf32216:
  lda b_at
  and #15
  beq @rf7168
  jmp @r
@rf7168:
  ; free slot?
  ldy #0
: lda em_st,y
  beq @ok
  iny
  iny
  cpy #NEM*2
  bne :-
  rts
@ok:
  dec b_n
  lda #1
  sta em_st,y
  lda #.loword(-49*16)
  ldx b_n
  txa
  and #1
  beq :+
  lda #49*16
  bra :++
: lda #.loword(-49*16)
: clc
  adc b_x
  sta em_x,y
  lda b_z
  sta em_z,y
  lda b_h
  clc
  adc #18*16
  sta em_h,y
  lda #0
  sta em_t,y
  sta em_w,y
  lda #$8000
  sta em_hd,y
  lda diff
  asl
  clc
  adc #34
  sta em_spd,y
  lda #1
  sta em_bp
  sty sfx_ni
  lda #K_EM
  sta sfx_nk
  lda #SB_BMSL
  ldx #2
  ldy #24
  jmp SfxB
@wait:
  lda b_at
  cmp #110
  bcc @r
  jmp AtkDone
@r:
  rts

; chest beam: the gem charges for a second (dotted aim line, "BEAM! CLIMB OR DIVE"), then a beam
; at the height you were at sweeps right across you. Change altitude by 9+ px and it passes.
AtkBeam:
  inc b_at
  lda b_at
  cmp #1
  bne @a1
  lda #1
  sta bm_on
  sta bm_warn
  lda b_h                    ; locked on your current height
  jsr Neg
  sta bm_dh
  jsr Rand
  and #1
  bne :+
  lda #.loword(-1)
: sta bm_dir
  ldx #140*16
  cmp #1
  bne :+
  ldx #.loword(-140*16)
: stx bm_x
  lda #K_BOSS
  sta sfx_nk
  lda #SA_CHARGE
  ldx #3
  ldy #66
  jmp SfxA
@a1:
  cmp #64
  bne @a2
  lda #2
  sta bm_on
  lda #K_BEAM
  sta sfx_nk
  lda #SB_BEAM
  ldx #4
  ldy #84
  jmp SfxB
@a2:
  bcc @r
  lda bm_on
  cmp #2
  bne @end
  ; sweep 6 px per frame
  lda bm_dir
  bmi :+
  lda bm_x
  clc
  adc #6*16
  bra :++
: lda bm_x
  sec
  sbc #6*16
: sta bm_x
  ; crossing you at your height?
  jsr Abs
  cmp #8*16
  bcs @nohit
  lda b_h
  clc
  adc bm_dh
  jsr Abs
  cmp #9*16
  bcs @nohit
  ldx #0
  ldy #0
  lda #DMG_BEAM
  jsr PlayerHit
@nohit:
  lda bm_x
  jsr Abs
  cmp #150*16
  bcc @r
@end:
  stz bm_on
  stz bm_warn
  lda b_at
  cmp #120
  bcc @r
  jmp AtkDone
@r:
  rts

; crest shard burst: the crest flashes, then a ring of 8 shards flies out at you. The ring closes on
; you at ~34 px radius: hold your line and they pass around you (and whizz past your ears).
ShardCos: .word 34, 24, 0, .loword(-24), .loword(-34), .loword(-24), 0, 24
ShardSin: .word 0, 24, 34, 24, 0, .loword(-24), .loword(-34), .loword(-24)
AtkShard:
  inc b_at
  lda b_at
  cmp #1
  bne :+
  lda #30
  sta b_fe                   ; eyes / crest glare
  rts
: cmp #30
  beq @go
  cmp #90
  bcc @r
  jmp AtkDone
@go:
  lda #K_BOSS
  sta sfx_nk
  lda #SA_SHARDS
  ldx #3
  ldy #16
  jsr SfxA
  lda b_x
  sta fe_x
  lda b_z
  sta fe_z
  lda b_h
  clc
  adc #52*16                 ; crest
  sta fe_h
  lda #1
  sta fe_k
  ldx #14
@k:
  stx c_j
  lda ShardCos,x
  sta fe_ax
  lda ShardSin,x
  sta fe_ah
  jsr FireFrom
  ldx c_j
  dex
  dex
  bpl @k
@r:
  rts

; smoke puffs off the damaged robot in phase 3
BossSmoke:
  lda b_ph
  cmp #2
  bne @r
  dec b_smk
  bpl @r
  lda #18
  sta b_smk
  jsr BossBoom
  bcc @r
  lda #26                    ; skip the fireball: straight to the smoke frames
  sta en_t,x
@r:
  rts

; one explosion somewhere on the robot (en_ slot; carry set + X = slot if there was room)
BossBoom:
  ldx #0
: lda en_st,x
  beq @ok
  inx
  inx
  cpx #NEN*2
  bne :-
  clc
  rts
@ok:
  lda #ST_BOOM
  sta en_st,x
  stz en_t,x
  lda #T_BIGBOOM
  sta en_ty,x
  stz en_hd,x
  lda fwd
  sta en_spd,x
  stx c_i
  jsr Rand
  ldx c_i
  and #$07FF
  sec
  sbc #$0400                 ; +-64 px
  clc
  adc b_x
  sta en_x,x
  lda b_z
  sec
  sbc #12*16
  sta en_z,x
  jsr Rand
  ldx c_i
  and #$007F
  sec
  sbc #80                    ; -80..+47 px around the gem
  sta t0
  lda b_h
  ASR4
  clc
  adc t0
  sta en_dh,x
  sec
  rts

; ---------------------------------------------------------------- your fire vs the boss
BossHits:
  lda b_z
  ASR4
  sta t3                     ; boss z px
  lda b_x
  ASR4
  sta t4                     ; boss x px
  lda b_h
  ASR4
  sta t5                     ; gem height relative to you (px)
  ldy #0
@b:
  lda bu_d,y
  bne :+
  jmp @bn
: sec
  sbc t3
  jsr Abs
  cmp #14
  bcc :+
  jmp @bn
: lda bu_x,y
  sec
  sbc t4
  jsr Abs
  sta t6                     ; |dx|
  ; chest gem
  cmp #12
  bcs @eye
  lda t5
  jsr Abs
  cmp #10
  bcs @eye
  lda #1                     ; chest gem: 1
  ldx #10
  stx b_fg
  bra @dmg
@eye:
  lda t6
  cmp #16
  bcs @body
  lda t5
  clc
  adc #EYE_DH
  jsr Abs
  cmp #8
  bcs @body
  lda #2                     ; eyes (31 px higher, smaller): 2
  ldx #10
  stx b_fe
@dmg:
  sta t0
  lda #0
  sta bu_d,y
  phy
  lda b_hp
  sec
  sbc t0
  bcs :+
  lda #0
: sta b_hp
  lda #K_BOSS
  sta sfx_nk
  lda #SA_WEAK
  ldx #2
  ldy #12
  jsr SfxA
  jsr BossBar
  ply
  bra @bn
@body:
  lda t6                     ; armour: the round bounces off with a ping and sparks
  cmp #60
  bcs @bn
  lda t5
  cmp #.loword(-65)
  bmi @bn
  cmp #140
  bpl @bn
  lda #0
  sta bu_d,y
  phy
  jsr Spark
  lda b_ping
  bne :+
  lda #5
  sta b_ping
  lda #K_BOSS
  sta sfx_nk
  lda #SA_PING
  ldx #1
  ldy #8
  jsr SfxA
: ply
@bn:
  iny
  iny
  cpy #NBU*2
  beq :+
  jmp @b
: rts

; Y = bullet slot: a bright impact flash where the round bounced off the armour
Spark:
  lda bu_x,y
  sta pg_x
  lda #6
  sta pg_t
  rts

; your missile hit him (called from MoveMissile)
BossMissileHit:
  lda b_hp
  sec
  sbc #6
  bcs :+
  lda #0
: sta b_hp
  lda #12
  sta b_fb
  jsr BossBoom
  lda #K_BOSS
  sta sfx_nk
  lda #SB_BIG
  ldx #3
  ldy #58
  jsr SfxB
  jmp BossBar

; health bar: redraw when the segment count changes
BossBar:
  jsr BossSegs
  cmp b_seg
  beq :+
  lda row_dirty
  ora #RD_BOSS
  sta row_dirty
: rts

; ---------------------------------------------------------------- shots from the boss
; fe_x / fe_z / fe_h = origin (1/16 px, h relative to you); fe_ax / fe_ah = aim point around you (px);
; fe_k = kind (0 tracer, 1 shard)
.segment "BSS"
k6s:   .res 2
bl_sx: .res 2
bl_sz: .res 2
bl_sh: .res 2
bl_x:  .res 2
bl_z:  .res 2
bl_h:  .res 2
ck_half: .res 2
ck_k:  .res 2
k6a:   .res 2
fe_x:  .res 2
fe_z:  .res 2
fe_h:  .res 2
fe_ax: .res 2
fe_ah: .res 2
fe_k:  .res 2
.segment "CODE"
FireFrom:
  ldy #0
@f:
  lda eb_t,y
  beq @ok
  iny
  iny
  cpy #NEB*2
  bne @f
  rts
@ok:
  sty a_j
  lda #1
  sta eb_t,y
  lda #0
  sta eb_w,y
  lda fe_k
  sta eb_k,y
  lda fe_x
  sta eb_x,y
  lda fe_z
  sta eb_z,y
  lda fe_h
  sta eb_h,y
  lda fe_z
  ASR4
  sta t1                     ; z px
  lda fe_x
  ASR4
  sec
  sbc fe_ax
  sta t2                     ; aim vector x (origin minus aim point)
  lda fe_h
  ASR4
  sec
  sbc fe_ah
  sta t3
  ; closing speed: slower for the shards so the ring reads
  lda diff
  asl
  asl
  clc
  adc #EB_SPD-8
  ldx fe_k
  beq :+
  sec
  sbc #16
: clc
  adc fwd
  sta t6
  ; arrival in z / S frames -> q = S*256/z (exact: rings and fans land where aimed)
  lda t1
  lsr
  lsr
  tax
  lda t6
  asl
  asl
  asl
  asl
  asl
  asl
  jsr DivU
  cmp #256
  bcc :+
  lda #255
: sta t7
  lda t2
  ldx t7
  jsr MulSS
  jsr Neg
  ldy a_j
  sta eb_vx,y
  lda t3
  ldx t7
  jsr MulSS
  jsr Neg
  ldy a_j
  sta eb_vh,y
  lda t1
  ldx t7
  jsr MulSS
  jsr Neg
  clc
  adc fwd
  ldy a_j
  sta eb_vz,y
  rts

; ---------------------------------------------------------------- drawing
; gem screen position -> b_sx, b_sy; carry clear if not visible
BossProj:
  lda b_x
  ASR4
  sta t0
  lda b_z
  ASR4
  clc
  adc zoff
  sta t1
  cmp #10
  bmi @no
  cmp #1280
  bpl @no
  asl
  tax
  lda f:RecipTab,x
  sta t5
  lda b_h
  ASR4
  eor #$FFFF
  sec
  adc hcam
  jsr ScaleR
  clc
  adc #HOR
  sta b_sy
  lda t0
  jsr ScaleR
  clc
  adc #128
  sta b_sx
  sec
  rts
@no:
  clc
  rts

; beam orbs, aim dots, muzzle flash: regular depth-sorted objects (called at the end of ProjectObjects)
BossObjs:
  lda b_vis
  bne :+
  rts
: lda pg_t                   ; armour ping flash (at your height, on his front)
  beq @nopg
  lda pg_x
  sta t0
  lda b_z
  ASR4
  sec
  sbc #6
  clc
  adc zoff
  sta t1
  lda hcam
  sta t2
  jsr Project
  bcc @nopg
  lda pg_t
  and #2
  asl
  asl
  asl
  asl
  asl
  ora obj_pri
  sta o_a
  lda #F_X16A
  jsr AddObj
@nopg:
  lda b_mf                   ; muzzle flash at the raised arm
  beq @nomf
  lda #.loword(-58)
  ldx b_side
  beq :+
  lda #58
: sta t0
  lda b_x
  ASR4
  clc
  adc t0
  sta t0
  lda b_z
  ASR4
  sec
  sbc #6
  clc
  adc zoff
  sta t1
  lda b_h
  ASR4
  eor #$FFFF
  sec
  adc hcam
  clc
  adc #8
  sta t2
  jsr Project
  bcc @nomf
  lda frame
  and #2
  asl
  asl
  asl
  asl
  asl
  ora obj_pri
  sta o_a
  lda #F_X16A
  jsr AddObj
@nomf:
.ifdef DBG_NOBEAMDRAW
  rts
.endif
  lda bm_on
  bne :+
  rts
: cmp #1
  bne @beam
  lda #F_BORB1               ; telegraph: small shimmering dots to where the sweep starts
  sta o_f
  bra @line
@beam:
  lda #F_BORB0
  sta o_f
@line:
  ; 10 points from the gem to the end point (bm_x, z = 24 px, gem + bm_dh): steps computed once
  lda bm_x
  sec
  sbc b_x
  jsr Div10S
  sta bl_sx
  lda #24*16
  sec
  sbc b_z
  jsr Div10S
  sta bl_sz
  lda bm_dh
  jsr Div10S
  sta bl_sh
  lda b_x
  sta bl_x
  lda b_z
  sta bl_z
  lda b_h
  sta bl_h
  ldy #10
@k:
  sty c_j
  lda bl_x
  clc
  adc bl_sx
  sta bl_x
  ASR4
  sta t0
  lda bl_z
  clc
  adc bl_sz
  sta bl_z
  ASR4
  clc
  adc zoff
  sta t1
  lda bl_h
  clc
  adc bl_sh
  sta bl_h
  ASR4
  eor #$FFFF
  sec
  adc hcam
  sta t2
  tya                        ; half the points each frame (shimmer; keeps the frame budget)
  eor frame
  lsr
  bcs @nx
  jsr Project
  bcc @nx
  lda frame
  and #4
  asl
  asl
  asl
  asl
  ora obj_pri
  ora #$0E                   ; palette 7 (boss colours)
  sta o_a
  lda o_f
  ldy c_j
  cpy #6
  bcc :+
  lda #F_BORB1               ; far half of the beam (first points from the gem): smaller orbs
: jsr AddObj
@nx:
  ldy c_j
  dey
  beq :+
  jmp @k
: rts

; A = signed 16-bit -> A / 10 (rounded toward zero)
Div10S:
  sta k6s
  jsr Abs
  ldx #10
  jsr DivU
  bit k6s
  bpl :+
  jsr Neg
: rts

; A = value -> A * c_j / 10 (signed, |A| < 2048)
MulK6:
  sta k6s
  jsr Abs
  sta k6a
  lda #0
  ldx c_j
: clc
  adc k6a
  dex
  bne :-
  ldx #10
  jsr DivU
  bit k6s
  bpl :+
  jsr Neg
: rts

; the robot itself: last in the OAM list = behind everything else
BossDraw:
  lda b_vis
  bne :+
  rts
: lda b_gfx                  ; pieces only once the boss sheet is in VRAM
  cmp #2
  beq :+
  rts
: jsr BossProj
  bcs :+
  rts
: lda b_fb                   ; hit / dying shudder
  ora b_st
  and #$0004
  beq :+
  lda frame
  and #2
  dec a
  clc
  adc b_sx
  sta b_sx
: lda obj_pri
  ora #$0E                   ; palette 7
  sta t7
  ; fast path (whole body on screen, room in OAM): precomputed (dy<<8)+dx and tile/attr words
  lda b_sx
  cmp #BOSS_FAST_X0
  bmi @slow
  cmp #BOSS_FAST_X1+1
  bpl @slow
  lda b_sy
  cmp #BOSS_FAST_Y0
  bmi @slow
  cmp #BOSS_FAST_Y1+1
  bpl @slow
  lda oam_idx
  cmp #512-BOSS_FAST_N*4+1
  bcs @slow
  lda b_sy
  xba
  and #$FF00
  clc
  adc b_sx
  sta bd_dx                  ; (sy<<8)+sx
  lda obj_pri
  xba
  and #$FF00
  sta bd_t                   ; priority bits into the attr byte
  lda b_arm
  and #3
  ldx view
  cpx #VIEW_COCK
  bne :+
  ora #4
: asl
  tax
  lda f:BossFastIdx,x
  tax
  clc
  adc #BOSS_FAST_N*4
  sta bd_offl                ; end offset
  ldy oam_idx
@fl:
  lda f:BossFast_chase_0,x
  clc
  adc bd_dx
  sta oam_lo,y
  lda f:BossFast_chase_0+2,x
  ora bd_t
  sta oam_lo+2,y
  iny
  iny
  iny
  iny
  inx
  inx
  inx
  inx
  cpx bd_offl
  bne @fl
  sty oam_idx
  jmp @rf97377
@slow:
  lda t7
  ora #$40
  sta bd_atr                 ; right half: h-flipped
  lda b_arm                  ; tile column per half: +4 arms down, +6 arm raised
  and #1
  asl
  ora #4
  sta bd_offl
  lda b_arm
  and #2
  ora #4
  sta bd_offr
  ldx #0                     ; cell table offset
  lda view
  cmp #VIEW_COCK
  bne :+
  ldx #(BossCells_cock-BossCells_chase)
: stx t6
  lda #BOSS_NCELL
  sta c_j
  ldy oam_idx                ; Y = OAM write index for the whole body (perf: no per-piece JSR)
@c:
  ldx t6
  lda f:BossCells_chase+2,x
  clc
  adc b_sy
  sta sy
  clc
  adc #16
  cmp #240
  bcc :+
  jmp @nx                    ; the whole row is off screen vertically
: lda f:BossCells_chase,x
  sta bd_dx
  ; left half
  txa
  clc
  adc bd_offl
  tax
  lda f:BossCells_chase,x
  cmp #$FFFF
  beq @right
  sta stile
  lda bd_dx
  clc
  adc b_sx
  sta sx
  clc
  adc #16
  cmp #272
  bcs @right
  lda t7
  jsr BossPut
@right:
  lda t6
  clc
  adc bd_offr
  tax
  lda f:BossCells_chase,x
  cmp #$FFFF
  beq @nx
  sta stile
  lda bd_dx
  eor #$FFFF
  sec
  sbc #15                    ; -dx - 16
  clc
  adc b_sx
  sta sx
  clc
  adc #16
  cmp #272
  bcs @nx
  lda bd_atr
  jsr BossPut
@nx:
  lda t6
  clc
  adc #8
  sta t6
  dec c_j
  beq :+
  jmp @c
: sty oam_idx
@rf97377:
  ; thrusters under the boots (cloud palette: orange / yellow)
  lda frame
  and #2
  beq :+
  lda #T_CHASE_BFLAME1
  ldx view
  cpx #VIEW_COCK
  bne @f
  lda #T_COCK_BFLAME1
  bra @f
: lda #T_CHASE_BFLAME0
  ldx view
  cpx #VIEW_COCK
  bne @f
  lda #T_COCK_BFLAME0
@f:
  sta stile
  lda obj_pri
  ora #$02
  sta sattr
  lda b_sy
  clc
  adc #85
  sta sy
  lda b_sx
  sec
  sbc #19
  sta sx
  jsr BossSpr
  lda b_sx
  clc
  adc #3
  sta sx
  lda sattr
  ora #$40
  sta sattr
  jmp BossSpr

; body piece (on screen already checked): A = attr, sx/sy/stile set, Y = OAM index (advanced by 4)
BossPut:
  cpy #512
  bcs @full
  sta bd_t
  A8
  lda sx
  sta oam_lo,y
  lda sy
  sta oam_lo+1,y
  lda stile
  sta oam_lo+2,y
  lda stile+1
  and #1
  ora bd_t
  sta oam_lo+3,y
  A16
  lda sx
  bpl :+
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
  lda HiTab,x
  ora oam_hi,y
  sta oam_hi,y
  A16
  ply
: iny
  iny
  iny
  iny
@full:
  rts

; 16x16 piece: sx/sy top-left (signed), stile, sattr. Skipped if fully off screen.
BossSpr:
  lda sy
  clc
  adc #16
  cmp #240
  bcs @out                   ; y < -16 or y >= 224
  lda sx
  clc
  adc #16
  cmp #272
  bcs @out                   ; x < -16 or x >= 256
  ldx oam_idx
  cpx #512
  bcs @out
  A8
  lda sx
  sta oam_lo,x
  lda sy
  sta oam_lo+1,x
  lda stile
  sta oam_lo+2,x
  lda stile+1
  and #1
  ora sattr
  sta oam_lo+3,x
  A16
  lda sx
  bpl @nohi                  ; x < 0: set the 9th x bit in the high table
  txa
  and #$000C
  ora #1                     ; HiTab column 1 = the 9th x bit
  tay
  txa
  lsr
  lsr
  lsr
  lsr
  tax
  A8
  lda HiTab,y
  ora oam_hi,x
  sta oam_hi,x
  A16
@nohi:
  lda oam_idx
  clc
  adc #4
  sta oam_idx
@out:
  rts

; once per built frame: animated colours for the NMI (eyes glow, gem pulse, hit flashes)
BossColors:
  lda b_st
  bne :+
  rts
: ; eyes: slow red glow (white strobe when hit / crest glare)
  lda frame
  lsr
  and #$000E
  tax
  lda f:EyeGlow,x
  sta b_ceye
  lda b_fe
  beq :+
  lda frame
  and #2
  beq :+
  lda #$7FFF
  sta b_ceye
: ; gem: pulses; fast white strobe while the beam charges / fires and when hit
  lda frame
  lsr
  and #$000E
  tax
  lda f:GemGlow,x
  sta b_cgem
  lda bm_on
  ora b_fg
  beq :+
  lda frame
  and #2
  beq :+
  lda #$7FFF
  sta b_cgem
: rts
EyeGlow: .word $001C, $0C3F, $1C7F, $2CBF, $1C7F, $0C3F, $001C, $0016
GemGlow: .word $0418, $0C3C, $147F, $1CBF, $147F, $0C3C, $0418, $0012

; ---------------------------------------------------------------- NMI side (called every vblank)
BossNmi:
.ifdef DBG_NONMI
  rts
.endif
  lda b_palq
  beq @nop
  A8
  lda #240
  sta CGADD
  A16
  ldx #0
  lda b_palq
  cmp #2
  beq @navy
: lda f:BossPal,x
  A8
  sta CGDATA
  xba
  sta CGDATA
  A16
  inx
  inx
  cpx #32
  bne :-
  bra @pd
@navy:
: lda f:NavyPal,x
  A8
  sta CGDATA
  xba
  sta CGDATA
  A16
  inx
  inx
  cpx #32
  bne :-
@pd:
  stz b_palq
  bra @stream
@nop:
  lda b_gfx
  cmp #2
  bne @stream
  A8
  lda #253                   ; palette 7 colours 13 (eyes) + 14 (gem)
  sta CGADD
  lda b_ceye
  sta CGDATA
  lda b_ceye+1
  sta CGDATA
  lda b_cgem
  sta CGDATA
  lda b_cgem+1
  sta CGDATA
  A16
@stream:
  lda b_gfx
  cmp #1
  beq @go
  cmp #3
  beq @go
  rts
@go:
  ; two 512-byte sheet rows per frame (one DMA each)
  jsr @row
  lda b_gfx
  cmp #1
  beq @row
  cmp #3
  beq @row
  rts
@row:
  ldx vs_i
  lda vs_view
  cmp #VIEW_COCK
  beq @ck
  cpx #BOSS_NROWS_CHASE
  bcc @rf94242
  jmp @fin
@rf94242:
  lda f:BossRows_chase,x
  bra @have
@ck:
  cpx #BOSS_NROWS_COCK
  bcc @rf6479
  jmp @fin
@rf6479:
  lda f:BossRows_cock,x
@have:
  and #$00FF
  sta bn_row
  inc vs_i
  A8
  lda #$80
  sta VMAIN
  A16
  lda bn_row
  xba                        ; row * 256 words
  clc
  adc #$6000
  sta VMADDL
  lda bn_row
  xba
  asl                        ; row * 512 bytes
  ldx vs_view
  cpx #VIEW_COCK
  beq @sc
  ldx b_gfx
  cpx #1
  beq :+
  clc
  adc #.loword(ObjChase)
  ldx #^ObjChase
  bra @dma
: clc
  adc #.loword(ObjChaseBoss)
  ldx #^ObjChaseBoss
  bra @dma
@sc:
  ldx b_gfx
  cpx #1
  beq :+
  clc
  adc #.loword(ObjCock)
  ldx #^ObjCock
  bra @dma
: clc
  adc #.loword(ObjCockBoss)
  ldx #^ObjCockBoss
@dma:
  sta A1T0L
  lda #512
  sta DAS0L
  A8
  txa
  sta A1B0
  lda #$01
  sta DMAP0
  lda #$18
  sta BBAD0
  lda #1
  sta MDMAEN
  A16
  rts
@fin:
  lda b_gfx                  ; 1 -> 2 (boss sheet in), 3 -> 0 (field sheet back)
  cmp #1
  bne :+
  lda #2
  sta b_gfx
  rts
: stz b_gfx
  rts

; ---------------------------------------------------------------- music: SPC700 image swaps
; Non-blocking IPL upload in the main loop's idle time. mu_want = image wanted (field / boss).
MusicPump:
.ifdef DBG_NOPUMP
  rts
.endif
  lda nmi_count
  sta mu_stamp
  lda mu_dead
  bne @r
  lda mu_st
  bne @busy
  lda mu_want
  cmp mu_img
  bne :+
@r:
  rts
: sta mu_tgt
  lda #$FF
  sta mu_img
  stz mu_to
  lda #1
  sta mu_st
  A8
  lda #$FE                   ; the driver jumps back into the IPL ROM
  sta $2140
  A16
  rts
@busy:
  cmp #1
  bne @xfer
  lda $2140                  ; IPL ready: $BBAA
  cmp #$BBAA
  bne @r
  stz mu_blk
  lda #$CC
  sta mu_kick
  jsr MuBlock
  lda #2
  sta mu_st
@xfer:
  ; stream bytes until the next frame starts (checked every 32 bytes)
  ldy mu_pos
  A8
@b:
  lda [mu_ptr],y
  sta $2141
  tya
  sta $2140
@e: cmp $2140
  bne @e
  iny
  cpy mu_len
  beq @done
  tya
  and #$1F
  bne @b
  A16
  lda nmi_count
  cmp mu_stamp
  A8
  beq @b
  A16
  sty mu_pos
  rts
@done:
  A16
  ; next kick = last index + 2 (never 0, $AA, $FE or $FF)
  lda mu_len
  inc a
  and #$00FF
  sta mu_kick
  jsr MuFixKick
  inc mu_blk
  lda mu_blk
  cmp mu_n
  bcs @start
  jsr MuBlock
  rts
@start:
  ldx #APU_DRIVER
  stx $2142
  A8
  stz $2141
  lda mu_kick
  sta $2140
: cmp $2140
  bne :-
  A16
  stz mu_st
  lda mu_tgt
  sta mu_img
  rts

MuFixKick:
  lda mu_kick
  beq @inc
  cmp #$AA
  beq @inc
  cmp #$FE
  bcs @inc
  rts
@inc:
  inc a
  and #$00FF
  sta mu_kick
  bra MuFixKick

; set up block mu_blk of the target image's table and send its header.
; All three images (field / boss / title) share one range table (make_boss.py writes the union),
; only the source bin differs.  One extra 1-byte block after the ranges: the mono flag (APU_MONO).
MuBlock:
  lda #BossUp_N+1
  sta mu_n
  lda mu_blk
  cmp #BossUp_N
  bcc @img
  lda #1                     ; mono flag block
  sta mu_len
  lda #.loword(opt_mono)
  sta mu_ptr
  lda #$7E
  sta mu_ptr+2
  lda #APU_MONO
  bra @hdr
@img:
  asl
  tax
  lda f:BossUp_Len,x
  sta mu_len
  lda f:BossUp_Off,x
  ldy mu_tgt
  cpy #MU_BOSS
  bne :+
  clc
  adc #.loword(BossUpBin)
  ldy #^BossUpBin
  bra @p
: cpy #MU_TITLE
  bne :+
  clc
  adc #.loword(TitleUpBin)
  ldy #^TitleUpBin
  bra @p
: clc
  adc #.loword(FieldUpBin)
  ldy #^FieldUpBin
@p:
  sta mu_ptr
  sty mu_ptr+2
  lda f:BossUp_Dst,x
@hdr:
  sta $2142
  stz mu_pos
  A8
  lda #1
  sta $2141
  lda mu_kick
  sta $2140
: cmp $2140
  bne :-
  A16
  rts

; once per frame (logic): IPL timeout, victory-jingle command
MusicFrame:
  lda mu_st
  cmp #1
  bne :+
  inc mu_to
  lda mu_to
  cmp #120                   ; no IPL answer in 2 s: give up on music, keep playing
  bcc :+
  stz mu_st
  lda #1
  sta mu_dead
: lda mu_ff
  beq :+
  dec mu_ff
  lda mu_st
  bne :+
  A8
  lda #$FF
  sta $2140
  A16
: rts

; ---------------------------------------------------------------- text rows
; boss health bar: chase = sky row 1, cockpit = canopy row 4
RowBoss:
  lda #1
  ldx view
  cpx #VIEW_COCK
  bne :+
  lda #4
: jsr RowFromMap
  lda b_st
  cmp #BS_ENTER
  bcc @set
  cmp #BS_DYING
  bcs @set
  ldy #.loword(TX_BOSS)
  lda #$3800
  ldx #8
  jsr PutTxt
  jsr BossSegs
  sta b_seg
  sta t0
  ldx #26
@b:
  lda t0
  beq @e0
  cmp #2
  bcc @e1
  sbc #2
  sta t0
  lda #T_BAR2
  bra @put
@e1:
  stz t0
  lda #T_BAR1
  bra @put
@e0:
  lda #T_BAR0
@put:
  ora #$3800
  sta rowbuf,x
  inx
  inx
  cpx #26+24
  bne @b
@set:
  lda #1
  sta row_flag
  rts

; chase sky rows during the boss: big flashing WARNING (rows 2-3), MISSION COMPLETE + BONUS
; A = row (2, 3, 5), row already copied from the map. Carry set if handled.
BossSky:
  sta t5
  lda b_st
  cmp #BS_WARN
  beq @warn
  cmp #BS_DONE
  beq @done
  clc
  rts
@warn:
  lda b_t
  and #16
  bne @ok
  lda t5
  cmp #5
  beq @ok
  ; W A R N I N G from column 8 (2 tiles each, I narrow)
  ldy #0
@g:
  lda WarnWord,y
  sta t0
  lda t5
  cmp #3
  bne :+
  lda #4
  bra :++
: lda #0
: clc
  adc t0
  tax                        ; BIG_x + 0 (top) / + 4 (bottom)
  tya
  asl
  clc
  adc #18
  sta t1
  lda a:0,x
  ora #$3800
  ldx t1
  sta rowbuf,x
  lda t0
  clc
  adc #2
  ldx t5
  cpx #3
  bne :+
  clc
  adc #4
: tax
  lda a:0,x
  ora #$3800
  ldx t1
  sta rowbuf+2,x
  iny
  iny
  cpy #14
  bne @g
@ok:
  sec
  rts
@done:
  lda t5
  cmp #2
  bne :+
  ldy #.loword(TX_MISSION)
  lda #$3000
  ldx #$FF
  jsr PutTxt
  sec
  rts
: cmp #5
  bne @ok
  jsr BonusTxt
  sec
  rts
WarnWord: .word .loword(BIG_W), .loword(BIG_A), .loword(BIG_R), .loword(BIG_N), .loword(BIG_I), .loword(BIG_N), .loword(BIG_G)

; "BONUS 5000" centred (b_bonus x100)
BonusTxt:
  ldy #.loword(TX_BONUS)
  lda #$3000
  ldx #10
  jsr PutTxt
  lda b_bonus
  ldx #32
  jmp PutNum100

; A = value (< 1000), X = rowbuf offset: digits (no leading zeros) followed by "00"
PutNum100:
  stx t1
  sta t0
  stz t2                     ; started
  ldx #4                     ; Pow10 (bank $81) index: 100, 10, 1
@d:
  ldy #0
  lda t0
: cmp f:Pow10,x
  bcc :+
  sbc f:Pow10,x
  iny
  bra :-
: sta t0
  stx t3
  tya
  ora t2
  beq @sk
  sta t2
  tya
  clc
  adc #FONT_0
  ora #$3000
  ldx t1
  sta rowbuf,x
  inx
  inx
  stx t1
@sk:
  ldx t3
  inx
  inx
  cpx #10
  bne @d
  lda #FONT_0
  ora #$3000
  ldx t1
  sta rowbuf,x
  sta rowbuf+2,x
  rts

; cockpit canopy row 3 during the boss. Carry set if handled.
BossWarnRow:
  lda b_st
  cmp #BS_WARN
  beq @w
  cmp #BS_DONE
  beq @d
  clc
  rts
@w:
  lda b_t
  and #16
  bne :+
  ldy #.loword(TX_WARNING)
  lda #$3800
  ldx #$FF
  jsr PutTxt
: sec
  rts
@d:
  lda b_t
  cmp #150
  bcs :+
  ldy #.loword(TX_MISSION)
  lda #$3000
  ldx #$FF
  jsr PutTxt
  sec
  rts
: jsr BonusTxt
  sec
  rts

; your missile homing on the boss (from MoveMissile): carry set if it hit (missile gone)
MsBoss:
  lda b_st
  cmp #BS_FIGHT
  beq :+
  lda #$FFFF
  sta ms_tg
  clc
  rts
: lda b_x
  sec
  sbc ms_x
  ASR4
  jsr Asr2
  cmp #$8000
  bcs @neg
  cmp #24
  bcc @add
  lda #24
  bra @add
@neg:
  cmp #.loword(-24)
  bcs @add
  lda #.loword(-24)
@add:
  clc
  adc ms_vx
  cmp #$8000
  bcs @vn
  cmp #200
  bcc @vs
  lda #200
  bra @vs
@vn:
  cmp #.loword(-200)
  bcs @vs
  lda #.loword(-200)
@vs:
  sta ms_vx
  lda b_z
  sec
  sbc ms_z
  jsr Abs
  cmp #18*16
  bcs @no
  lda b_x
  sec
  sbc ms_x
  jsr Abs
  cmp #40*16
  bcs @no
  lda b_h                    ; it flies level: only hits if he's in its path
  cmp #.loword(-65*16)
  bmi @no
  cmp #140*16
  bpl @no
  stz ms_st
  jsr BossMissileHit
  sec
  rts
@no:
  clc
  rts

; LoadView: finish any boss sheet stream at once -> Z clear if the boss sheet is wanted
BossSheetSel:
  lda b_gfx
  cmp #3
  bne :+
  stz b_gfx
: lda b_gfx
  beq :+
  lda #2
  sta b_gfx
: lda b_gfx
  rts

.ifdef AUTOPILOT
; test builds only: plays the boss fight (match the gem height, dodge the beam, keep firing)
AutoPilot:
  lda b_st
  cmp #BS_ENTER
  bcs :+
  rts
: cmp #BS_DYING
  bcc :+
  lda joy
  and #KEY_START
  sta joy
  rts
: lda #KEY_Y
  sta ap_j
  lda frame
  and #63
  bne :+
  lda ap_j
  ora #KEY_A
  sta ap_j
: lda b_h                    ; gem height relative to you (1/16 px)
  ldx bm_on
  beq @aim
  clc                        ; beam: get 14+ px away from its height
  adc bm_dh
  sta t0
  jsr Abs
  cmp #16*16
  bcs @steer
  lda t0
  bmi @up
  bra @dn
@aim:
  ldx ap_eye
  beq :+
  clc
  adc #EYE_DH*16
: cmp #$8000
  bcs :+
  cmp #3*16
  bcc @steer
@up:
  lda ap_j
  ora #KEY_UP
  sta ap_j
  bra @steer
: cmp #.loword(-3*16)
  bcs @steer
@dn:
  lda ap_j
  ora #KEY_DOWN
  sta ap_j
@steer:
  lda b_x
  cmp #$8000
  bcs :+
  cmp #10*16
  bcc @done
  lda ap_j
  ora #KEY_RIGHT
  sta ap_j
  bra @done
: cmp #.loword(-10*16)
  bcs @done
  lda ap_j
  ora #KEY_LEFT
  sta ap_j
@done:
  lda p_dead
  ora gameover
  beq :+
  stz ap_j
: lda ap_j
  sta joy
  eor ap_prev
  and ap_j
  sta joy_new
  lda ap_j
  sta ap_prev
  rts
.segment "BSS"
ap_j:    .res 2
ap_prev: .res 2
ap_eye:  .res 2
.segment "CODE"
.endif

; ---------------------------------------------------------------- big data
.segment "BANK7"
ObjChaseBoss: .incbin "../assets/obj_chase_boss.bin"
ObjCockBoss:  .incbin "../assets/obj_cock_boss.bin"
.segment "BANK8"
BossUpBin:    .incbin "../music/build/boss_up.bin"
.segment "BANK9"
FieldUpBin:   .incbin "../music/build/field_up.bin"
.segment "BANK10"
TitleUpBin:   .incbin "../music/build/title_up.bin"
.segment "CODE"
