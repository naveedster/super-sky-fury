; =====================================================================
;  SNES FLY - enemies, guns, missile, explosions, debris, score, stereo SFX
;  Included from main.s (CODE segment, bank $80). All objects live in
;  jet-relative space: x = right, z = ahead, in 1/16 px (signed 16-bit).
;  Turning rotates them, flying forward pulls them toward you.
; =====================================================================
NEN = 6                     ; enemy slots
NBU = 6                     ; bullet slots (spread gun = lanes on the same round)
NDE = 8                     ; debris slots
NOB = 48                    ; projected sprite objects per frame
ST_LIVE = 1
ST_BOOM = 2
T_HEAD   = 0                ; flies at you from the horizon, weaving
T_CROSSR = 1                ; crosses ahead, left to right
T_CROSSL = 2                ; crosses ahead, right to left
T_OVER   = 3                ; overtakes you from behind, then pulls away
T_SWOOP  = 4                ; dives in from above, head-on
T_TAIL   = 5                ; sits on your tail, fires a missile, breaks away
AR_MSL   = $0100            ; wave flag: carries a homing missile
AR_GUN   = $0200            ; wave flag: fires tracer bursts
T_WAIT   = $80              ; script: wait until the sky is clear
T_LOOP   = $81              ; script: back to the start, a bit faster
BOOM_T   = 40               ; explosion length (frames)
MUZZLE   = 14               ; bullet speed relative to you (px/frame)
BUL_LIFE = 300              ; bullet range (px)
HIT_X    = 9                ; bullet hit box half-width (px)
HIT_Z    = 12               ; bullet hit box half-depth (px)
; SFX ids (channel A = port 1, channel B = port 2)
SA_BOOST = 1
SA_BANKL = 2
SA_BANKR = 3
SA_GUNL  = 4
SA_GUNR  = 5
SA_MSL   = 6
SA_DEBLR = 7
SA_DEBRL = 8
SB_BOOM  = 1
SB_FLYBY = 2
SB_BIG   = 3
SA_BEEP  = 9
SA_HIT   = 10
SB_WHIZ  = 4
SB_MSW   = 5
SB_DIE   = 6
SB_ONEUP = 12               ; boss v2: extra-life jingle

.segment "BSS"
rng:    .res 2
rot_s:  .res 2
fwd:    .res 2
score:  .res 2
.ifdef SFXDBG
dbg_ida: .res 2
dbg_idb: .res 2
dbg_pa: .res 2
dbg_pb: .res 2
.endif
score_flag: .res 2
; missile smoke trails (graphics v1): 3 slots (your missile, 2 enemy missiles) x 4 screen positions
tr_x:   .res 5*8                ; player missile + NEM (4) enemy missiles (boss v1)
tr_y:   .res 5*8
tr_n:   .res 5*2
tr_h:   .res 5*2
tr_seen: .res 5*2
tr_s:   .res 2
tr_b:   .res 2
tr_k:   .res 2
tr_cx:  .res 2
tr_cy:  .res 2
en_st:  .res NEN*2
en_x:   .res NEN*2
en_z:   .res NEN*2
en_dh:  .res NEN*2
en_hd:  .res NEN*2
en_spd: .res NEN*2
en_ty:  .res NEN*2
en_pa:  .res NEN*2         ; OAM palette bits by type (graphics v1)
en_t:   .res NEN*2
en_wa:  .res NEN*2
en_fly: .res NEN*2
bu_d:   .res NBU*2
bu_gx:  .res NBU*2
bu_hd:  .res NBU*2
bu_x:   .res NBU*2
de_x:   .res NDE*2
de_z:   .res NDE*2
de_h:   .res NDE*2
de_vx:  .res NDE*2
de_vz:  .res NDE*2
de_vh:  .res NDE*2
de_t:   .res NDE*2
ob_sx:  .res NOB*2
ob_sy:  .res NOB*2
ob_tl:  .res NOB*2
ob_at:  .res NOB*2
ob_z:   .res NOB*2
obl:    .res NOB*8
obc:    .res 8
cl_cur: .res 2
cl_par: .res 2
o_s:    .res 2
o_c:    .res 2
cl_vx:  .res 32
cl_vy:  .res 32
cl_ox:  .res 32
cl_oy:  .res 32
cl_ob:  .res 32
cl_ls:  .res 32
cl_vok: .res 32
cl_ok2: .res 32
cl_vis: .res 32
scorebuf: .res 12
ms_st:  .res 2
ms_x:   .res 2
ms_z:   .res 2
ms_vx:  .res 2
ms_vz:  .res 2
ms_tg:  .res 2
ms_t:   .res 2
ms_cd:  .res 2
fire_cd: .res 2
gun_side: .res 2
wave_pos: .res 2
wave_tm: .res 2
diff:   .res 2
deb_t:  .res 2
deb_id: .res 2
seq_a:  .res 2
seq_b:  .res 2
sfxa_t: .res 2
sfxa_p: .res 2
sfxb_t: .res 2
sfxb_p: .res 2
elapsed: .res 2
zoff:   .res 2
hcam:   .res 2
ftab:   .res 2
obj_pri: .res 2
ob_n:   .res 2
cl_rr:  .res 2
q_p:    .res 2
q_dx:   .res 2
q_dy:   .res 2
q_x:    .res 2
q_y:    .res 2
q_t:    .res 2
q_a:    .res 2
o_i:    .res 2
o_f:    .res 2
o_a:    .res 2
c_i:    .res 2
c_j:    .res 2

.segment "CODE"
; ---------------------------------------------------------------- init
InitCombat:
  AXY16
  lda #$ACE1
  sta rng
  lda #150                  ; first wave ~2.5 s after the screen comes up
  sta wave_tm
  stz wave_pos
  ldx #30
@v:
  txa
  sta cl_order,x
  lda #1
  sta cl_vis,x
  dex
  dex
  bpl @v
  jsl X_GameInit             ; v1.1: stage 1, power-ups / combo / effects reset
  jsr ScoreText
  jmp InitAttack

; xorshift16 -> A
Rand:
  lda rng
  asl
  asl
  asl
  asl
  asl
  asl
  asl
  eor rng
  sta rng
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  eor rng
  sta rng
  xba
  and #$FF00
  eor rng
  sta rng
  rts

Asr4:
  cmp #$8000
  ror
  cmp #$8000
  ror
  cmp #$8000
  ror
  cmp #$8000
  ror
  rts

Neg:
  eor #$FFFF
  inc a
  rts

; ---------------------------------------------------------------- per physics step
CombatStep:
  AXY16
.ifdef NOCOMBAT
  rts
.endif
  lda turnrate
  ldx #100
  jsr MulSS
  sta rot_s                 ; turn per step, scaled: dtheta * 4096
  lda speed
  lsr
  lsr
  sta fwd                   ; your speed in 1/16 px per step
  jsr PlayerTick
  jsr Weapons
  jsr Waves
  CHK 12
  jsr MoveEnemies
  CHK 44
  jsl X_Step
  CHK 45                 ; v1.1: new enemy types, power-ups, effects, bar, stages
  jsr EnemyFire
  CHK 13
  jsr MoveBullets
  CHK 14
  jsr MoveMissile
  jsr MoveEB
  jsr MoveEM
  jsr MoveDebris
  CHK 15
  jsr Hits
  jsr BossStep
  jsr BossColors
  CHK 16
  lda deb_t
  beq @nd
  dec deb_t
  bne @nd
  lda deb_id
  ldx #2
  ldy #26
  jsr SfxA
@nd:
  rts

; A = value (1/16 px), rotate by your turn: returns A = (A * rot_s) >> 12
RotTerm:
  ldx rot_s
  bne :+
  lda #0
  rts
: jsr MulSS
  jmp Asr4

; A = signed (|A| <= 255), X = unsigned 0..255 -> A = (A*X) >> 8 (one hardware multiply)
MulB:
  stx m_b
  cmp #$8000
  bcs @neg
  A8
  sta WRMPYA
  lda m_b
  sta WRMPYB
  nop
  nop
  nop
  A16
  lda RDMPYH
  and #$00FF
  rts
@neg:
  eor #$FFFF
  inc a
  A8
  sta WRMPYA
  lda m_b
  sta WRMPYB
  nop
  nop
  nop
  A16
  lda RDMPYH
  and #$00FF
  eor #$FFFF
  inc a
  rts

; ---------------------------------------------------------------- weapons
Weapons:
  lda fire_cd
  beq :+
  dec fire_cd
: lda ms_cd
  beq :+
  dec ms_cd
: lda joy
  and #KEY_Y
  beq @nogun
  lda fire_cd
  bne @nogun
  ldx #0
@f:
  lda bu_d,x
  beq @slot
  inx
  inx
  cpx #NBU*2
  bne @f
  bra @nogun
@slot:
  lda #6
  sta fire_cd
  lda #10
  sta bu_d,x
  lda heading
  xba
  and #$00FF
  sta bu_hd,x
  lda gun_side
  eor #1
  sta gun_side
  beq @left
  lda #7
  sta bu_gx,x
  lda #SA_GUNR
  bra @snd
@left:
  lda #.loword(-7)
  sta bu_gx,x
  lda #SA_GUNL
@snd:
  jsl X_Spread               ; v1.1: spread gun = two more rounds
  ldx #1
  ldy #6
  jsr SfxA
@nogun:
  lda joy_new
  and #KEY_A
  bne @rf12587
  jmp @nomsl
@rf12587:
  lda ms_st
  ora ms_cd
  bne @nomsl
  ; lock the nearest live enemy ahead of you (inside a 45 degree cone)
  lda #$7FFF
  sta t3
  lda #$FFFF
  sta ms_tg
  ldx #0
@tg:
  lda en_st,x
  cmp #ST_LIVE
  bne @tn
  lda en_z,x
  bmi @tn
  sta t0
  lda en_x,x
  jsr Abs
  cmp t0
  bcs @tn
  lda t0
  cmp t3
  bcs @tn
  sta t3
  stx ms_tg
@tn:
  inx
  inx
  cpx #NEN*2
  bne @tg
  lda ms_tg                 ; nothing else ahead: lock on the boss
  bpl :+
  lda b_st
  cmp #BS_FIGHT
  bne :+
  lda #BOSS_TG
  sta ms_tg
: lda #1
  sta ms_st
  stz ms_x
  lda #8*16
  sta ms_z
  stz ms_vx
  lda #96
  sta ms_vz
  stz ms_t
  lda ms_reload              ; v1.1: 45 frames, 16 with RAPID MISSILES
  sta ms_cd
  lda #SA_MSL
  ldx #3
  ldy #24
  jsr SfxA
@nomsl:
  rts

; ---------------------------------------------------------------- wave script
Waves:
  lda b_st                  ; the script waits while the boss is up
  beq :+
  rts
: lda wave_tm
  beq :+
  dec wave_tm
  rts
: ldx wave_pos
  lda f:WaveData,x
  and #$00FF
  cmp #T_WAIT
  bne @nw
  ldy #0
@chk:
  lda en_st,y
  bne @busy
  iny
  iny
  cpy #NEN*2
  bne @chk
  bra @adv
@busy:
  rts
@nw:
  cmp #T_BOSS
  bne @nb
  lda gameover              ; (boss v2 fix: never start him behind the GAME OVER screen)
  bne @busy
  ldy #0                    ; boss: once the sky is clear
: lda en_st,y
  bne @busy
  iny
  iny
  cpy #NEN*2
  bne :-
  jsr BossStart
  ldx wave_pos
  bra @adv
@nb:
  cmp #T_LOOP
  beq @lp
  cmp #T_STAGE               ; v1.1: next stage (fade, new world, banner)
  bne @spawn
  jsl X_WaveStage
  bcc @busy
  ldx wave_pos
  bra @adv
@lp:
  stz wave_pos
  lda diff
  cmp #6
  bcs :+
  inc diff
: rts
@spawn:
  lda f:WaveData,x
  sta t0
  lda f:WaveData+2,x
  sta t1
  lda f:WaveData+4,x
  sta t2
  lda f:WaveData+6,x
  sta t3
  jsr Spawn
  ldx wave_pos
@adv:
  lda f:WaveData+8,x
  sta wave_tm
  txa
  clc
  adc #10
  sta wave_pos
  rts

; t0 = type, t1 = x px, t2 = z px, t3 = weave amplitude
Spawn:
  ldx #0
@f:
  lda en_st,x
  beq @ok
  inx
  inx
  cpx #NEN*2
  bne @f
  rts
@ok:
  lda #ST_LIVE
  sta en_st,x
  lda t1
  asl
  asl
  asl
  asl
  sta en_x,x
  lda t2
  asl
  asl
  asl
  asl
  sta en_z,x
  lda t0
  and #$FF00
  sta en_ar,x
  lda t0
  and #$00FF
  sta t0
  sta en_ty,x
  phx
  and #7
  asl
  tax
  lda f:EnPalTab,x
  plx
  sta en_pa,x
  lda t0
  lda t3
  sta en_wa,x
  stz en_t,x
  stz en_fly,x
  lda diff
  lsr
  clc
  adc #2
  sta en_bu,x               ; first burst
  phx
  jsr Rand
  plx
  and #$003F
  clc
  adc #30
  sta en_cd,x               ; don't open fire the moment they appear
  phx
  jsr Rand
  plx
  and #$000F
  sec
  sbc #7
  sta en_dh,x               ; -7..+8 px around your altitude
  lda diff
  asl
  asl
  sta t4                    ; speed bonus per loop of the script
  lda t0
  cmp #T_HEAD
  bne :+
  lda #$8000
  sta en_hd,x
  lda #40
  bra @spd
: cmp #T_SWOOP
  bne :+
  lda #$8000
  sta en_hd,x
  lda #56
  sta en_dh,x
  lda #44
  bra @spd
: cmp #T_CROSSR
  bne :+
  lda #$4000
  sta en_hd,x
  lda #60
  bra @spd
: cmp #T_CROSSL
  bne :+
  lda #$C000
  sta en_hd,x
  lda #60
  bra @spd
: cmp #T_TAIL
  bne :+
  stz en_hd,x               ; tailer: creeps up behind you
  lda #30
  bra @spd
: stz en_hd,x               ; overtaker
  lda #92
@spd:
  clc
  adc t4
  sta en_spd,x
  jsl X_SpawnInit            ; v1.1: hit points / hit box / new types
  rts

; ---------------------------------------------------------------- enemies
MoveEnemies:
  ldx #0
@l:
  stx c_i
  lda en_st,x
  bne :+
  jmp @next
:
  ; your turn swings them around you
  lda en_z,x
  jsr RotTerm
  sta t0
  ldx c_i
  lda en_x,x
  sec
  sbc t0
  sta en_x,x
  jsr RotTerm
  ldx c_i
  clc
  adc en_z,x
  sec
  sbc fwd                   ; and you fly toward them
  sta en_z,x
  lda en_hd,x
  sec
  sbc turnrate
  sta en_hd,x
  lda en_t,x
  inc a
  sta en_t,x
  lda en_st,x
  cmp #ST_BOOM
  bne @alive
  lda en_t,x                ; wreck: coasts and slows, then is gone
  cmp #BOOM_T
  bcc :+
  stz en_st,x
  jmp @next
: lda en_ty,x
  cmp #T_BIGBOOM
  beq @bb
  lda en_spd,x
  lsr
  lsr
  lsr
  eor #$FFFF
  sec
  adc en_spd,x
  sta en_spd,x
@bb:
  lda en_hd,x
  xba
  and #$00FF
  sta t1
  bra @mv
@alive:
  lda en_ty,x
  cmp #T_TAIL
  bne @ntail
  lda en_t,x
  cmp #95
  bne @ntail
  lda #$3000                ; breaks away to its side and accelerates
  ldy en_x,x
  bpl :+
  lda #$D000
: sta en_hd,x
  lda #70
  sta en_spd,x
@ntail:
  lda en_ty,x
  cmp #T_SWOOP
  bne :+
  lda en_dh,x
  beq :+
  lda en_t,x
  and #1
  bne :+
  dec en_dh,x
: lda en_t,x
  asl
  asl
  asl
  and #$01FE
  tax
  lda f:SinTab,x
  ldx c_i
  ldy en_wa,x
  tyx
  jsr MulB
  sta t1                    ; weave (angle units)
  ldx c_i
  lda en_hd,x
  xba
  and #$00FF
  clc
  adc t1
  sta t1
@mv:
  lda t1
  and #$00FF
  asl
  sta t2
  tax
  lda f:SinTab,x
  ldy c_i
  ldx en_spd,y
  jsr MulB
  ldx c_i
  clc
  adc en_x,x
  sta en_x,x
  lda t2
  clc
  adc #128
  and #$01FF
  tax
  lda f:SinTab,x
  ldy c_i
  ldx en_spd,y
  jsr MulB
  ldx c_i
  clc
  adc en_z,x
  sta en_z,x
  ; gone? (far ahead, behind you, or off to the side)
  cmp #.loword(-200*16)
  bmi @kill
  cmp #1150*16
  bpl @kill
  lda en_x,x
  jsr Abs
  cmp #1400*16
  bcs @kill
  ; flyby: a live plane passing close sweeps its jet rush past your ears
  lda en_st,x
  cmp #ST_LIVE
  bne @next
  lda en_fly,x
  bne @next
  lda en_z,x
  jsr Abs
  cmp #150*16
  bcs @next
  lda en_x,x
  jsr Abs
  cmp #110*16
  bcs @next
  lda #1
  sta en_fly,x
  lda sfxb_t                ; don't steal the voice from a louder sound
  beq :+
  lda sfxb_p
  cmp #2
  bcs @next
: stx sfx_ni
  lda #K_EN
  sta sfx_nk
  lda #SB_FLYBY
  ldx #1
  ldy #64
  jsr SfxB
  bra @next
@kill:
  stz en_st,x
@next:
  ldx c_i
  inx
  inx
  cpx #NEN*2
  beq :+
  jmp @l
: rts

; ---------------------------------------------------------------- bullets
MoveBullets:
  ldx #0
@l:
  lda bu_d,x
  beq @n
  clc
  adc #MUZZLE
  cmp #BUL_LIFE
  bcc :+
  lda #0
: sta bu_d,x
  beq @n
  ; lateral drift from turning since it was fired: x = gx + d * sin(fire heading - heading)
  stx c_i
  lda heading
  xba
  and #$00FF
  sta t0
  lda bu_hd,x
  sec
  sbc t0
  and #$00FF
  asl
  tax
  lda f:SinTab,x
  sta t1
  jsr Abs
  tax
  ldy c_i
  lda bu_d,y
  jsr MulSmall
  bit t1
  bpl :+
  jsr Neg
: ldx c_i
  clc
  adc bu_gx,x
  sta bu_x,x
@n:
  inx
  inx
  cpx #NBU*2
  bne @l
  rts

; ---------------------------------------------------------------- missile
MoveMissile:
  lda ms_st
  bne :+
  rts
: inc ms_t
  lda ms_t
  cmp #100
  bcc :+
  stz ms_st
  rts
: lda ms_z
  jsr RotTerm
  sta t0
  lda ms_x
  sec
  sbc t0
  sta ms_x
  jsr RotTerm
  clc
  adc ms_z
  sta ms_z
  ; accelerate
  lda ms_vz
  cmp #256
  bcs :+
  adc #10
  sta ms_vz
: ; home on the target
  lda ms_tg
  cmp #BOSS_TG
  bne :+
  jsr MsBoss
  bcs @rf43582
  jmp @fly
@rf43582:
  rts
: ldx ms_tg
  bpl @rf22453
  jmp @fly
@rf22453:
  lda en_st,x
  cmp #ST_LIVE
  beq :+
  lda #$FFFF
  sta ms_tg
  bra @fly
: lda en_x,x
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
  ; hit?
  lda en_z,x
  sec
  sbc ms_z
  jsr Abs
  cmp #18*16
  bcs @fly
  lda en_x,x
  sec
  sbc ms_x
  jsr Abs
  cmp #14*16
  bcs @fly
  stz ms_st
  jsl X_MissileHit           ; v1.1: 6 damage, big flash, hit-stop, shake
  rts
@fly:
  lda ms_x
  clc
  adc ms_vx
  sta ms_x
  lda ms_z
  clc
  adc ms_vz
  sec
  sbc fwd
  sta ms_z
  rts

; ---------------------------------------------------------------- debris
MoveDebris:
  ldx #0
@l:
  lda de_t,x
  beq @n
  dec a
  sta de_t,x
  beq @n
  stx c_i
  lda de_z,x
  jsr RotTerm
  ldx c_i
  eor #$FFFF
  sec
  adc de_x,x
  clc
  adc de_vx,x
  sta de_x,x
  lda de_z,x
  clc
  adc de_vz,x
  sec
  sbc fwd
  sta de_z,x
  lda de_vh,x
  sec
  sbc #3
  sta de_vh,x
  clc
  adc de_h,x
  sta de_h,x
@n:
  inx
  inx
  cpx #NDE*2
  bne @l
  rts

; ---------------------------------------------------------------- bullet hits
Hits:
  ldx #0
@e:
  lda en_st,x
  cmp #ST_LIVE
  beq @rf35310
  jmp @en
@rf35310:
  lda en_z,x
  bpl @rf3783
  jmp @en
@rf3783:
  cmp #(BUL_LIFE+HIT_Z)*16
  bcs @en
  ASR4
  sta t0                    ; enemy z px
  lda en_x,x
  ASR4
  sta t1                    ; enemy x px
  ldy #0
@b:
  lda bu_d,y
  beq @bn
  sec
  sbc t0
  bpl :+
  eor #$FFFF
  inc a
: cmp #HIT_Z
  bcs @bn
  lda bu_x,y
  sec
  sbc t1
  bpl :+
  eor #$FFFF
  inc a
: jsl X_LaneHit              ; v1.1: lanes (spread gun) x per-type hit box -> damage / kill
  bcs @en
@bn:
  iny
  iny
  cpy #NBU*2
  bne @b
@en:
  inx
  inx
  cpx #NEN*2
  beq @rf51572
  jmp @e
@rf51572:
  rts

; X = enemy slot*2, A = points (x100). Explosion + debris + score + SFX.
KillEnemy:
  stx o_i
  sta o_f
  jsl X_KillPtsL             ; v1.1: A = points (type x combo), score popup, big-kill juice
  clc
  adc score
  cmp #10000
  bcc :+
  lda #9999
: sta score
  CHK 36
  jsr ScoreText
  jsr ScoreLife
  CHK 37
  ldx o_i
  lda #ST_BOOM
  sta en_st,x
  stz en_t,x
  ; explosion sound follows the wreck (channel B, live pan)
  stx sfx_ni
  lda #K_EN
  sta sfx_nk
  lda #SB_BOOM
  ldy #44
  ldx o_f
  cpx #2
  bne :+
  lda #SB_BIG               ; missile kills get the big boom
  ldy #58
: ldx #3
  jsr SfxB
  ; debris: 4 pieces, flung out and toward you
  ldy #0
  lda #4
  sta c_j
@d:
  lda de_t,y
  bne @dn
  ldx o_i
  lda en_x,x
  sta de_x,y
  lda en_z,x
  sta de_z,y
  lda en_dh,x
  asl
  asl
  asl
  asl
  sta de_h,y
  phy
  jsr Rand
  ply
  sta t0
  and #$003F
  sec
  sbc #32
  sta de_vx,y
  lda t0
  xba
  and #$001F
  clc
  adc #16
  eor #$FFFF
  inc a
  sta de_vz,y
  lda t0
  lsr
  lsr
  and #$001F
  clc
  adc #8
  sta de_vh,y
  lda #44
  sta de_t,y
  dec c_j
  beq @dd
@dn:
  iny
  iny
  cpy #NDE*2
  bne @d
@dd:
  ; close kills: debris whizzes past your head ~0.2 s later (channel A)
  ldx o_i
  lda en_z,x
  cmp #500*16
  bcs @far
  lda #12
  sta deb_t
  lda #SA_DEBLR
  ldy en_x,x
  bmi :+
  lda #SA_DEBRL
: sta deb_id
@far:
  rts

; ---------------------------------------------------------------- score text (6 BG2 digit tiles)
ScoreText:
  lda #$3000
  ldx view
  cpx #VIEW_COCK
  bne :+
  lda #$3400
: sta t3
  lda score
  sta t0
  ldx #0
  ldy #0
@d:
  stz t2
@s:
  lda t0
  cmp f:Pow10+2,x
  bcc @w
  sbc f:Pow10+2,x
  sta t0
  inc t2
  bra @s
@w:
  lda t2
  clc
  adc #FONT_0
  ora t3
  sta scorebuf,y
  iny
  iny
  inx
  inx
  cpx #8
  bne @d
  lda #FONT_0
  ora t3
  sta scorebuf+8
  sta scorebuf+10
  lda #1
  sta score_flag
  rts

; ---------------------------------------------------------------- SFX requests
; A = id, X = priority, Y = length in frames. Channel A = voice 7 (port 1).
SfxA:
  pha
  lda sfxa_t
  beq @go
  cpx sfxa_p
  bcs @go
  pla
  stz sfx_nk
  rts
@go:
  stx sfxa_p
  sty sfxa_t
  lda sfx_nk
  sta sfxa_k
  lda sfx_ni
  sta sfxa_i
  lda sfx_nfx
  sta sfx_fx
  lda sfx_nfz
  sta sfx_fz
  stz sfx_nk
  jsr SfxLiveA              ; pan/volume first, so the first tick is already placed
  lda seq_a
  clc
  adc #$10
  and #$00F0
  sta seq_a
  pla
  ora seq_a
.ifdef SFXDBG
  sta dbg_ida
.endif
  ldx mu_st                 ; (no port writes while a song is being uploaded)
  bne :+
  A8
.ifndef NOSFX
  sta f:$002141
.endif
  A16
:
  rts
; channel B = voice 1 (port 2); the object to follow must already be in sfxb_o
SfxB:
  pha
  lda sfxb_t
  beq @go
  cpx sfxb_p
  bcs @go
  pla
  stz sfx_nk
  rts
@go:
  stx sfxb_p
  sty sfxb_t
  lda sfx_nk
  sta sfxb_k
  lda sfx_ni
  sta sfxb_i
  lda sfx_nfx
  sta sfx_fx+2
  lda sfx_nfz
  sta sfx_fz+2
  stz sfx_nk
  jsr SfxLiveB
  lda seq_b
  clc
  adc #$10
  and #$00F0
  sta seq_b
  pla
  ora seq_b
.ifdef SFXDBG
  sta dbg_idb
.endif
  ldx mu_st                 ; (no port writes while a song is being uploaded)
  bne :+
  A8
.ifndef NOSFX
  sta f:$002142
.endif
  A16
:
  rts

; once per frame: age the SFX; live pan + volume for one tracking channel (alternating)
SfxFrame:
  lda sfxa_t
  sec
  sbc elapsed
  bcs :+
  lda #0
: sta sfxa_t
  lda sfxb_t
  sec
  sbc elapsed
  bcs :+
  lda #0
: sta sfxb_t
  lda sfx_par
  eor #1
  sta sfx_par
  beq @b
  CHK 32
  jsr SfxLiveA
  CHK 33
  bcs @r
  jmp SfxLiveB
@b:
  CHK 34
  jsr SfxLiveB
  CHK 35
  bcs @r
  jmp SfxLiveA
@r:
  rts

; ---------------------------------------------------------------- projection
; t0 = x (px, signed), t1 = camera z (px), t2 = height below the camera (px, signed)
; -> sx, sy = screen centre; carry clear if not visible.  Uses RecipTab (160*256/z), no divides.
Project:
  lda t1
  cmp #10
  bmi @no
  cmp #1280
  bpl @no
  lda t0
  cmp #$8000
  bcc :+
  eor #$FFFF
  inc a
: sta t3
  lda t1
  asl
  cmp t3
  bcc @no                   ; more than ~63 degrees off to the side
  tax
  lda f:RecipTab,x
  sta t5
  lda t2                    ; vertical first: the cockpit only shows its windscreen
  jsr ScaleR
  clc
  adc #HOR
  sta sy
  ldx view
  cpx #VIEW_COCK
  bne :+
  cmp #44
  bcc @no
  cmp #152
  bcs @no
: lda t0
  jsr ScaleR
  clc
  adc #128
  sta sx
  sec
  rts
@no:
  clc
  rts

; A = signed value (|A| < 1024), t5 = reciprocal -> A = (A * t5) >> 8
ScaleR:
  sta m_div
  cmp #$8000
  bcc :+
  eor #$FFFF
  inc a
: cmp #256
  bcs @big
  ldx t5
  cpx #256
  bcs :+
  lda m_div                 ; both fit in 8 bits: one multiply (boss v1 fix: was value*|value|)
  jmp MulB
: ldx m_div
  lda t5
  jmp MulSS
@big:
  lda m_div
  jsr Asr2
  tax
  lda t5
  jsr MulSS
  asl
  asl
  rts

; A = logical frame, o_a = attr (palette/priority/flips) -> append to the object list (t1 = depth)
AddObj:
  ldx view
  cpx #VIEW_COCK
  bne :+
  ldx sy                    ; cockpit: only inside the windscreen
  cpx #44
  bcc @full
  cpx #152
  bcs @full
: asl
  clc
  adc ftab
  tax
  lda f:FrameTab,x
  ldx ob_n
  cpx #NOB*2
  bcs @full
  sta ob_tl,x
  lda o_a
  sta ob_at,x
  lda sx
  sta ob_sx,x
  lda sy
  sta ob_sy,x
  ; depth band: [0,40) [40,150) [150,400) [400,...)
  ldy #0
  lda t1
  cmp #40
  bcc @b
  ldy #2
  cmp #150
  bcc @b
  ldy #4
  cmp #400
  bcc @b
  ldy #6
@b:
  lda obc,y
  phx
  tax
  pla
  sta obl,x
  inx
  inx
  txa
  sta obc,y
  ldx ob_n
  inx
  inx
  stx ob_n
@full:
  rts

ClearObjs:
  stz ob_n
  stz obc
  lda #NOB*2
  sta obc+2
  lda #NOB*4
  sta obc+4
  lda #NOB*6
  sta obc+6
  rts

; smoke trail behind a missile. In: A = slot*2, sx/sy/t1 = the missile's projection (kept).
; Emits the stored puffs, then records the current position every 4th frame (screen space, so the
; trail costs no projections).
TRAIL_LEN = 4
TrailEmit:
.ifdef NOTRAIL
  rts
.endif
  ldx view                  ; no trails from the cockpit (keeps its frame budget)
  cpx #VIEW_COCK
  bne :+
  rts
: sta tr_s
  tax
  asl
  asl
  sta tr_b
  lda sx
  sta tr_cx
  lda sy
  sta tr_cy
  lda frame
  dec a
  cmp tr_seen,x
  beq :+
  stz tr_n,x                ; first frame seen (new missile or view change): restart the trail
: lda frame
  sta tr_seen,x
  lda tr_n,x
  sta tr_k
  beq @push
@lp:
  dec tr_k
  lda tr_k
  eor frame
  lsr
  bcs @nx                   ; every other puff per frame
  lda tr_k
  asl
  clc
  adc tr_b
  tax
  lda tr_x,x
  sta sx
  lda tr_y,x
  sta sy
  lda tr_k
  and #1
  beq :+
  lda #$40
: ora obj_pri
  sta o_a
  lda #F_PUFF
  jsr AddObj
@nx:
  lda tr_k
  bne @lp
@push:
  ldx tr_s
  lda frame
  and #1
  bne @done
  lda tr_h,x
  inc a
  and #TRAIL_LEN-1
  sta tr_h,x
  asl
  clc
  adc tr_b
  tay
  lda tr_cx
  sta tr_x,y
  lda tr_cy
  sta tr_y,y
  lda tr_n,x
  cmp #TRAIL_LEN
  bcs @done
  inc a
  sta tr_n,x
@done:
  lda tr_cx
  sta sx
  lda tr_cy
  sta sy
  rts

; enemy palette (attr bits) per type: HEAD red, CROSSR/L olive, OVER navy, SWOOP olive, TAIL navy
EnPalTab: .word $06, $0C, $0C, $0E, $0C, $0E, $06, $06

; project every object for the chase / cockpit views
ProjectObjects:
  jsr ClearObjs
.ifdef NOCOMBAT
  rts
.endif
  ; ---- enemies
  ldx #0
@e:
  lda en_st,x
  bne :+
  jmp @en
: stx c_i
  lda en_x,x
  ASR4
  sta t0
  lda en_z,x
  ASR4
  clc
  adc zoff
  sta t1
  lda hcam
  sec
  sbc en_dh,x
  sta t2
  jsr Project
  bcs :+
  jmp @en0
: ldx c_i
  lda en_st,x
  cmp #ST_BOOM
  beq @boom
  jsl X_EnPal                ; v1.1: palette (white hit flash + jolt); bombers / fortress drawn there
  bcc :+
  jmp @en0
: jsl X_EnFrame              ; v1.1: near / medium: sprite-stacked yaw frames
  bcs :+
  jmp @add
: lda t1
@s:
  cmp #240
  bcs :+
  lda #F_ES
  bra @add
: cmp #380
  bcs :+
  lda #F_EXS
  bra @add
: lda #F_EXXS
  bra @add
@boom:
  lda en_t,x
  lsr
  lsr
  and #1
  beq :+
  lda #$40
: ora obj_pri
  sta o_a
  lda en_t,x
  cmp #4
  bcc @x16a
  cmp #28
  bcs @smoke
  lda en_ty,x
  cmp #T_BIGBOOM
  beq :+
  lda t1
  cmp #170
  bcs @x16a
: lda en_t,x
  lda en_t,x
  cmp #12
  bcs :+
  lda #F_X32A
  bra @add
: lda #F_X32B
  bra @add
@x16a:
  lda #F_X16A
  bra @add
@smoke:
  lda en_t,x
  cmp #38
  bcs :+
  lda #F_X16C               ; fire dying into smoke, embers
  bra @add
: lda #F_X16B
@add:
  jsr AddObj
@en0:
  ldx c_i
@en:
  inx
  inx
  cpx #NEN*2
  beq :+
  jmp @e
:
  CHK 48
  ; ---- missile
  lda ms_st
  beq @nomsl
  lda ms_x
  ASR4
  sta t0
  lda ms_z
  ASR4
  clc
  adc zoff
  sta t1
  lda hcam
  inc a
  inc a
  sta t2
  jsr Project
  bcc @nomsl
  lda obj_pri
  sta o_a
  lda #F_MSL
  jsr AddObj
  lda #0
  jsr TrailEmit
@nomsl:
  CHK 49
  ; ---- debris
  ldx #0
@d:
  lda de_t,x
  beq @dn
  stx c_i
  lda de_x,x
  ASR4
  sta t0
  lda de_z,x
  ASR4
  clc
  adc zoff
  sta t1
  lda de_h,x
  ASR4
  eor #$FFFF
  sec
  adc hcam
  sta t2
  jsr Project
  bcc @dn0
  ldx c_i
  lda de_t,x
  and #$000C
  asl
  asl
  asl
  asl
  ora obj_pri
  ora #$06
  sta o_a
  lda de_t,x
  lsr
  lsr
  and #1
  clc
  adc #F_DEB0
  jsr AddObj
@dn0:
  ldx c_i
@dn:
  inx
  inx
  cpx #NDE*2
  beq @rf12260
  jmp @d
@rf12260:
  CHK 50
  ; ---- bullets
  ldx #0
@b:
  lda bu_d,x
  beq @bn
  stx c_i
  lda bu_x,x
  sta t0
  lda bu_d,x
  clc
  adc zoff
  sta t1
  lda hcam
  sta t2
  jsr Project
  bcc @bn0
  jsl X_BulDraw              ; v1.1: centre + spread lanes
@bn0:
  ldx c_i
@bn:
  inx
  inx
  cpx #NBU*2
  bne @b
  CHK 51
  ; ---- enemy tracers
  ldx #0
@eb:
  lda eb_t,x
  bne @rf32064
  jmp @ebn
@rf32064:
  stx c_i
  lda eb_x,x
  ASR4
  sta t0
  lda eb_z,x
  ASR4
  clc
  adc zoff
  sta t1
  lda eb_h,x
  ASR4
  eor #$FFFF
  sec
  adc hcam
  sta t2
  jsr Project
  bcc @ebn0
  lda obj_pri
  sta o_a
  ldx c_i
  lda eb_k,x                ; crest shard (boss palette 7)
  beq :+
  lda frame
  and #4
  asl
  asl
  asl
  asl
  ora obj_pri
  ora #$0E
  sta o_a
  lda #F_BSHARD
  bra :++
: lda t1
  cmp #110
  lda #F_EBUL0
  bcc :+
  lda #F_EBUL1
: jsr AddObj
@ebn0:
  ldx c_i
@ebn:
  inx
  inx
  cpx eb_lim                 ; active slots only (6/2 in the field, 12/4 for the boss)
  beq @rf51672
  jmp @eb
@rf51672:
  CHK 52
  ; ---- enemy missiles (exhaust flicker = h-flip)
  ldx #0
@em:
  lda em_st,x
  beq @emn
  stx c_i
  lda em_x,x
  ASR4
  sta t0
  lda em_z,x
  ASR4
  clc
  adc zoff
  sta t1
  lda em_h,x
  ASR4
  eor #$FFFF
  sec
  adc hcam
  sta t2
  jsr Project
  bcc @emn0
  lda frame
  and #2
  asl
  asl
  asl
  asl
  asl
  ora obj_pri
  sta o_a
  lda #F_EMSL
  jsr AddObj
  lda c_i
  clc
  adc #2
  jsr TrailEmit
@emn0:
  ldx c_i
@emn:
  inx
  inx
  cpx em_lim                 ; active slots only (6/2 in the field, 12/4 for the boss)
  beq @rf36188
  jmp @em
@rf36188:
  CHK 53
  ; ---- your own jet going down in flames
  lda p_dead
  cmp #DEAD_T-44
  bcc @nw
  stz t0
  lda zoff
  bne :+
  lda #30
: sta t1
  lda hcam
  sta t2
  jsr Project
  bcc @nw
  lda p_dead
  and #4
  asl
  asl
  asl
  asl
  ora obj_pri
  sta o_a
  lda p_dead
  cmp #DEAD_T-16
  lda #F_X32A
  bcs :+
  lda #F_X32B
: jsr AddObj
@nw:
  CHK 46
  jsl X_Project
  CHK 47              ; v1.1: capsules, impact sparks, floating numbers
  jmp BossObjs

; overhead view: jet-relative coordinates map straight to the screen (the map turns with you)
; t0 = x px, t1 = z px -> sx, sy (carry clear if off screen)
ProjOver:
  lda t0
  jsr Abs
  cmp #400
  bcs @no
  lda t1
  jsr Abs
  cmp #400
  bcs @no
  ldx lev
  lda f:OverInv,x
  and #$00FF
  sta t4
  lda t0
  ldx t4
  jsr MulSmall
  clc
  adc t0
  clc
  adc #128
  sta sx
  lda t1
  ldx t4
  jsr MulSmall
  clc
  adc t1
  eor #$FFFF
  sec
  adc #120
  sta sy
  sec
  rts
@no:
  clc
  rts

ProjectOver:
  jsr ClearObjs
  stz t1
  ldx #0
@e:
  lda en_st,x
  bne @rf78191
  jmp @en
@rf78191:
  stx c_i
  lda en_x,x
  ASR4
  sta t0
  lda en_z,x
  ASR4
  sta t1
  jsr ProjOver
  bcc @en0
  ldx c_i
  lda en_st,x
  cmp #ST_BOOM
  beq @boom
  ; 8 directions from 3 frames + flips
  lda en_hd,x
  clc
  adc #$1000
  xba
  lsr
  lsr
  lsr
  lsr
  lsr
  and #7
  asl
  tax
  lda f:TopDirs,x
  xba
  and #$00C0
  ora #$36
  sta o_a
  lda f:TopDirs,x
  and #$00FF
  bra @add
@boom:
  lda #$30
  sta o_a
  lda en_t,x
  cmp #10
  lda #F_X32A
  bcc @add
  lda en_t,x
  cmp #28
  lda #F_X32B
  bcc @add
  lda #F_X16B
@add:
  jsr AddObj
@en0:
  ldx c_i
@en:
  inx
  inx
  cpx #NEN*2
  beq @rf54673
  jmp @e
@rf54673:
  CHK 8
  ldx #0
@b:
  lda bu_d,x
  beq @bn
  stx c_i
  lda bu_x,x
  sta t0
  lda bu_d,x
  sta t1
  jsr ProjOver
  bcc @bn0
  jsl X_BulDrawO
@bn0:
  ldx c_i
@bn:
  inx
  inx
  cpx #NBU*2
  bne @b
  CHK 46
  ldx #0
@d:
  lda de_t,x
  beq @dn
  stx c_i
  lda de_x,x
  ASR4
  sta t0
  lda de_z,x
  ASR4
  sta t1
  jsr ProjOver
  bcc @dn0
  lda #$36
  sta o_a
  lda #F_DEB0
  jsr AddObj
@dn0:
  ldx c_i
@dn:
  inx
  inx
  cpx #NDE*2
  bne @d
  CHK 47
  lda ms_st
  beq @nm
  lda ms_x
  ASR4
  sta t0
  lda ms_z
  ASR4
  sta t1
  jsr ProjOver
  bcc @nm
  lda #$30
  sta o_a
  lda #F_MSL
  jsr AddObj
  lda #0
  jsr TrailEmit
@nm:
  ; enemy tracers + missiles from above
  ldx #0
@oe:
  lda eb_t,x
  beq @oen
  stx c_i
  lda eb_x,x
  ASR4
  sta t0
  lda eb_z,x
  ASR4
  sta t1
  jsr ProjOver
  bcc @oen0
  lda #$30
  sta o_a
  lda #F_EBUL1
  jsr AddObj
@oen0:
  ldx c_i
@oen:
  inx
  inx
  cpx eb_lim                 ; active slots only (6/2 in the field, 12/4 for the boss)
  bne @oe
  ldx #0
@om:
  lda em_st,x
  beq @omn
  stx c_i
  lda em_x,x
  ASR4
  sta t0
  lda em_z,x
  ASR4
  sta t1
  jsr ProjOver
  bcc @omn0
  lda #$30
  sta o_a
  lda #F_EMSL
  jsr AddObj
  lda c_i
  clc
  adc #2
  jsr TrailEmit
@omn0:
  ldx c_i
@omn:
  inx
  inx
  cpx em_lim                 ; active slots only (6/2 in the field, 12/4 for the boss)
  bne @om
  lda p_dead
  cmp #DEAD_T-44
  bcc @nw
  stz t0
  stz t1
  jsr ProjOver
  lda #$30
  sta o_a
  lda p_dead
  cmp #DEAD_T-16
  lda #F_X32A
  bcs :+
  lda #F_X32B
: jsr AddObj
@nw:
  CHK 25
  jsl X_ProjOverExtra
  jmp BossObjs

; Y = band*2: emit that depth band's objects in the order they were projected
EmitObjs:
  lda obc,y
  sta o_f                   ; end
  lda BandBase,y
@l:
  cmp o_f
  bcs @d
  sta o_i
  tax
  ldy obl,x
  jsr EmitOne
  lda o_i
  inc a
  inc a
  bra @l
@d:
  rts
BandBase: .word 0, NOB*2, NOB*4, NOB*6

; Y = object index
EmitOne:
  lda ob_tl,y
  and #$3000
  bne @big0
  ; v1.1 fast path: 16x16 fully addressable (x 0..247, y 0..223): two word stores, no high table
  lda ob_sx,y
  sec
  sbc #8
  cmp #248
  bcs @sm
  sta sx
  lda ob_sy,y
  sec
  sbc #8
  cmp #224
  bcs @sm
  xba
  ora sx
  ldx oam_idx
  cpx #512
  bcs @r
  sta oam_lo,x
  lda ob_at,y
  and #$00FE
  xba
  sta m_t
  lda ob_tl,y
  and #$01FF
  ora m_t
  sta oam_lo+2,x
  txa
  clc
  adc #4
  sta oam_idx
@r:
  rts
@sm:
  lda ob_at,y
  sta sattr
  lda ob_tl,y
  and #$01FF
  sta stile
  lda ob_sx,y
  sec
  sbc #8
  sta sx
  lda ob_sy,y
  sec
  sbc #8
  sta sy
  stz sbig
  jmp PutSpr
@big0:
  sta t5
  lda ob_at,y
  sta sattr
  lda ob_tl,y
  and #$01FF
  sta stile
  lda ob_sx,y
  sec
  sbc #16
  sta sx
  lda ob_sy,y
  sec
  sbc #16
  sta sy
  lda t5
  cmp #$2000
  beq @quad
  stz sbig
  cmp #$3000
  beq :+
  inc sbig                  ; cockpit: 32x32 is the large size
: jmp PutSpr
@quad:
  lda #16
  sta q_p
  lda #2
  sta q_dx
  lda #32
  sta q_dy
  stz sbig
  ; fall through

; one 2x2 metasprite: sx, sy top-left, stile, sattr (flips honoured), q_p piece px, q_dx/q_dy tile steps
PutQuad:
  ; v1.1 fast path: 16 px pieces, all four on screen with x < 256: 8 word stores, no high table
  lda q_p
  cmp #16
  bne @sl
  lda sx
  cmp #225
  bcs @sl
  lda sy
  cmp #193
  bcs @sl
  ldx oam_idx
  cpx #512-15
  bcc @fast
@sl:
  jmp @slow
@fast:
  stz t4
  lda sattr
  and #$40
  beq :+
  lda q_dx
  sta t4
: stz t5
  lda sattr
  and #$80
  beq :+
  lda q_dy
  sta t5
: lda sattr
  and #$00FE
  xba
  sta m_t
  lda q_dx
  sec
  sbc t4
  sta q_x                   ; (dx - left)
  lda q_dy
  sec
  sbc t5
  sta q_y                   ; (dy - top)
  lda sy
  xba
  ora sx
  sta q_xy
  sta oam_lo,x              ; top-left
  clc
  adc #16
  sta oam_lo+4,x            ; top-right
  adc #$1000
  sta oam_lo+8,x            ; bottom-right
  sec
  sbc #16
  sta oam_lo+12,x           ; bottom-left
  lda stile
  clc
  adc t4
  adc t5
  ora m_t
  sta oam_lo+2,x
  lda stile
  clc
  adc q_x
  adc t5
  ora m_t
  sta oam_lo+6,x
  lda stile
  clc
  adc q_x
  adc q_y
  ora m_t
  sta oam_lo+10,x
  lda stile
  clc
  adc t4
  adc q_y
  ora m_t
  sta oam_lo+14,x
  txa
  clc
  adc #16
  sta oam_idx
  rts
@slow:
  lda sx
  sta q_x
  lda sy
  sta q_y
  lda stile
  sta q_t
  stz t4                    ; tile offset of the left column
  lda sattr
  and #$40
  beq :+
  lda q_dx
  sta t4
: stz t5                    ; tile offset of the top row
  lda sattr
  and #$80
  beq :+
  lda q_dy
  sta t5
: lda q_t
  clc
  adc t4
  adc t5
  sta stile
  jsr PutSpr                ; top-left
  lda q_x
  clc
  adc q_p
  sta sx
  lda q_dx
  sec
  sbc t4
  clc
  adc t5
  adc q_t
  sta stile
  jsr PutSpr                ; top-right
  lda q_y
  clc
  adc q_p
  sta sy
  lda q_dy
  sec
  sbc t5
  clc
  adc q_dx
  sec
  sbc t4
  clc
  adc q_t
  sta stile
  jsr PutSpr                ; bottom-right
  lda q_x
  sta sx
  lda q_dy
  sec
  sbc t5
  clc
  adc t4
  adc q_t
  sta stile
  jmp PutSpr                ; bottom-left

; ---------------------------------------------------------------- data
; overhead enemy facing: low byte = frame, high byte bits 6-7 = h/v flip
TopDirs: .word F_TOP0, F_TOP1, F_TOP2, F_TOP1|$8000, F_TOP0|$8000, F_TOP1|$C000, F_TOP2|$4000, F_TOP1|$4000
; (v1.1: the wave script moved to src/v11.s, per stage)

.include "attack.s"
.include "../assets/texts.inc"
.include "../assets/bigfont.inc"

.segment "BANK1"
; 160*256/z for z = 0..1279 (perspective scale, focal length 160)
RecipTab:
.repeat 1280, I
.if I < 10
  .word 4096
.else
  .word (40960 + I/2) / I
.endif
.endrepeat
.segment "CODE"
