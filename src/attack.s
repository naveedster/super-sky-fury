; =====================================================================
;  SNES FLY - the enemies shoot back: tracer rounds, homing missiles,
;  shield + lives, hit flash / shake, game over. Included from combat.s.
;  Same jet-relative space as combat.s (x right, z ahead, h up; 1/16 px).
; =====================================================================
NEB      = 12              ; enemy tracer slots
NEM      = 4               ; enemy missile slots
SHIELD_MAX = 16            ; 8 bar segments, 2 points each
LIVES0   = 5                ; boss v2: 5 lives (start and after game over)
LIVES_MAX = 9               ; one HUD digit
UP_STEP  = 100              ; extra life every 10,000 points (score is in x100 units)
UP_FLASH = 120              ; '1UP!' HUD flash length (frames)
DMG_BUL  = 2
DMG_MSL  = 6
DMG_RAM  = 5
INV_HIT  = 45              ; invulnerable after a hit (frames)
INV_SPAWN = 150            ; ... and after a new jet arrives
DEAD_T   = 150             ; shot down -> next jet (or game over) after 2.5 s
EB_SPD   = 72              ; tracer speed (1/16 px per frame, plus your own speed when aimed)
MSL_FUEL = 330             ; enemy missile burn time (frames)
; sound-follow kinds (SfxA/SfxB: set sfx_nk/sfx_ni/sfx_nfx/sfx_nfz first)
K_NONE = 0
K_EN   = 1                 ; enemy plane slot
K_EB   = 2                 ; enemy tracer slot
K_EM   = 3                 ; enemy missile slot
K_FIX  = 4                 ; fixed point (sfx_nfx, sfx_nfz in px)
; text rows rebuilt through the row DMA (one per frame)
RD_HINT = 1                ; bottom hint row (warnings / pause / press start)
RD_WARN = 2                ; cockpit: warning row on the canopy glass
RD_SKYA = 4                ; chase sky rows: GAME OVER (top half)
RD_SKYB = 8                ;                 GAME OVER (bottom half)
RD_SKYC = 16               ;                 FINAL SCORE
RD_ALL  = 31

.segment "BSS"
eb_t:   .res NEB*2
eb_x:   .res NEB*2
eb_z:   .res NEB*2
eb_h:   .res NEB*2
eb_vx:  .res NEB*2
eb_vz:  .res NEB*2
eb_vh:  .res NEB*2
eb_w:   .res NEB*2
em_st:  .res NEM*2         ; 0 free, 1 tracking, 2 missed (flies on), 3 out of fuel
em_x:   .res NEM*2
em_z:   .res NEM*2
em_h:   .res NEM*2
em_hd:  .res NEM*2
em_spd: .res NEM*2
em_t:   .res NEM*2
em_w:   .res NEM*2
em_bp:  .res 2
en_cd:  .res NEN*2
en_bu:  .res NEN*2
en_ar:  .res NEN*2
p_shield: .res 2
p_lives: .res 2
next_up: .res 2             ; score (x100) of the next extra life
up_t:   .res 2              ; 1UP HUD flash timer
up_snd: .res 2              ; 1UP jingle pending (waits while the SPC upload runs)
p_inv:  .res 2
p_dead: .res 2
gameover: .res 2
go_t:   .res 2
go_req: .res 2
shake_t: .res 2
flash_t: .res 2
c_shk:  .res 2
c_flash: .res 2
hudbuf: .res 26
hud_flag: .res 2
warn:   .res 2
warn_ph: .res 2
warn_shown: .res 2
row_dirty: .res 2
sfxa_k: .res 2
sfxa_i: .res 2
sfxb_k: .res 2
sfxb_i: .res 2
sfx_nk: .res 2
sfx_ni: .res 2
sfx_nfx: .res 2
sfx_nfz: .res 2
sfx_fx: .res 4
sfx_fz: .res 4
sfx_par: .res 2
ph_d:   .res 2
ph_x:   .res 2
ph_y:   .res 2
a_j:    .res 2
sb_n:   .res 2
sb_l:   .res 2
flashtab: .res 8

.segment "CODE"
; ---------------------------------------------------------------- reset the player side
InitAttack:
  lda #SHIELD_MAX
  sta p_shield
  lda d_lives               ; difficulty: 7 / 5 (LIVES0) / 3
  sta p_lives
  lda #UP_STEP
  sta next_up
  stz up_t
  stz up_snd
.ifdef UPTEST
  lda #UPTEST                ; test builds: start just under the threshold (and with UPLIVES lives)
  sta score
.endif
.ifdef UPLIVES
  lda #UPLIVES
  sta p_lives
.endif
  stz p_inv
  stz p_dead
  stz gameover
  stz go_t
  stz go_req
  stz shake_t
  stz flash_t
  stz warn
  stz warn_shown
  lda #1
  sta em_bp
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
  jsr SlotsField
  ; hit-flash HDMA table (COLDATA, 2 writes per entry): all channels v/2, then red v (warm flash)
  A8
  lda #$7F
  sta flashtab
  lda #$61
  sta flashtab+3
  lda #$20
  sta flashtab+1
  sta flashtab+4
  lda #$C0
  sta flashtab+2
  sta flashtab+5
  stz flashtab+6
  A16
  jmp HudText

; ---------------------------------------------------------------- per physics step: timers
PlayerTick:
  jsr UpTick
  lda p_inv
  beq :+
  dec p_inv
: lda shake_t
  beq :+
  dec shake_t
: lda flash_t
  beq :+
  dec flash_t
: lda gameover
  beq :+
  inc go_t
  rts
: lda p_dead
  beq @r
  dec p_dead
  bne @r
  lda p_lives
  beq @over
  lda #SHIELD_MAX           ; next jet
  sta p_shield
  lda #INV_SPAWN
  sta p_inv
  jmp HudText
@over:
  lda #1
  sta gameover
  sta go_req
  stz go_t
@r:
  rts

; ---------------------------------------------------------------- damage
; A = damage, X = side (px, signed), Y = 1 if it came from behind -> carry set if it counted
PlayerHit:
  sta ph_d
  stx ph_x
  sty ph_y
  lda p_dead
  ora gameover
  ora p_inv
  ora roll_t                 ; v1.4: rolling = untouchable
  beq :+
  clc
  rts
: inc st_hits
  lda p_shield
  sec
  sbc ph_d
  bpl :+
  lda #0
: sta p_shield
  lda #INV_HIT
  sta p_inv
  lda #16
  sta shake_t
  lda #10
  sta flash_t
  ; impact on the side it came from (channel A, panned live from a fixed point)
  lda ph_x
  beq @c
  bmi @l
  lda #64
  bra @s
@l:
  lda #.loword(-64)
  bra @s
@c:
  lda #0
@s:
  sta sfx_nfx
  lda #4
  ldx ph_y
  beq :+
  lda #.loword(-18)
: sta sfx_nfz
  lda #K_FIX
  sta sfx_nk
  lda #SA_HIT
  ldx #4
  ldy #16
  jsr SfxA
  lda #3
  ldx #26
  CHK 42
  jsr SpawnBits             ; sparks off your airframe
  CHK 43
  CHK 40
  jsr HudText
  CHK 41
  lda p_shield
  bne :+
  jsr PlayerDie
: sec
  rts

PlayerDie:
  dec p_lives
  lda #DEAD_T
  sta p_dead
  stz p_inv
  lda #30
  sta shake_t
  lda #16
  sta flash_t
  ldx #NEB*2-2              ; the sky clears for the next jet
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
  ; the big one: centred, a touch behind you (channel B) + wreckage tearing past (channel A)
  stz sfx_nfx
  lda #.loword(-6)
  sta sfx_nfz
  lda #K_FIX
  sta sfx_nk
  lda #SB_DIE
  ldx #5
  ldy #72
  jsr SfxB
  lda #18
  sta deb_t
  lda #SA_DEBLR
  sta deb_id
  lda #6
  ldx #56
  jsr SpawnBits
  jmp HudText

; A = pieces, X = life (frames): shards flung off your jet, mostly back toward the camera
SpawnBits:
  sta sb_n
  stx sb_l
  ldy #0
@d:
  lda de_t,y
  bne @dn
  lda #0
  sta de_x,y
  sta de_h,y
  lda #6*16
  sta de_z,y
  phy
  jsr Rand
  ply
  sta t0
  and #$007F
  sec
  sbc #64
  sta de_vx,y
  lda t0
  xba
  and #$003F
  sec
  sbc #44
  sta de_vz,y
  lda t0
  lsr
  lsr
  and #$001F
  clc
  adc #6
  sta de_vh,y
  lda sb_l
  sta de_t,y
  dec sb_n
  beq @dd
@dn:
  iny
  iny
  cpy #NDE*2
  bne @d
@dd:
  rts

; ---------------------------------------------------------------- enemies open fire (per physics step)
EnemyFire:
  lda p_dead
  ora gameover
  beq :+
  rts
: ldx #0
@l:
  stx c_i
  lda en_st,x
  cmp #ST_LIVE
  beq :+
  jmp @n
: ; ramming: a live plane right on top of you
  lda en_z,x
  jsr Abs
  cmp #12*16
  bcs @noram
  lda en_x,x
  jsr Abs
  cmp #12*16
  bcs @noram
  lda en_dh,x
  jsr Abs
  cmp #8
  bcs @noram
  lda en_x,x
  ASR4
  tax
  ldy #0
  lda #DMG_RAM
  CHK 26
  jsr PlayerHit
  CHK 27
  bcs :+
  jmp @n
: ldx c_i
  lda #1
  jsr KillEnemy
  jmp @n
@noram:
  ldx c_i
  lda en_ar,x
  and #AR_MSL
  beq @nomsl
  CHK 30
  jsr MaybeLaunch
  CHK 31
  ldx c_i
@nomsl:
  lda en_ar,x
  and #AR_GUN
  bne :+
  jmp @n
: lda en_cd,x
  beq @ready
  dec en_cd,x
  jmp @n
@ready:
  ; firing window: 180..640 px ahead, inside a ~14 degree cone
  lda en_z,x
  cmp #180*16
  bcc @wait
  cmp #640*16
  bcs @wait
  lsr
  lsr
  sta t0
  lda en_x,x
  jsr Abs
  cmp t0
  bcs @wait
  CHK 28
  jsr FireEB
  CHK 29
  ldx c_i
  dec en_bu,x
  beq @reload
  lda #7                    ; next round of the burst
  sta en_cd,x
  jmp @n
@reload:
  lda diff
  lsr
  clc
  adc #2
  sta en_bu,x               ; bursts: 2, 2, 3, 3, 4, 4, 5
  jsr Rand
  ldx c_i
  and #$001F
  sta t0
  lda diff
  asl
  asl
  asl
  eor #$FFFF
  sec
  adc d_fire                ; 110 (NORMAL; 150 easy, 80 hard) - 8*loop + 0..31 frames between bursts
  clc
  adc t0
  sta en_cd,x
  bra @n
@wait:
  lda #4
  sta en_cd,x
@n:
  ldx c_i
  inx
  inx
  cpx #NEN*2
  beq :+
  jmp @l
: rts

; X = enemy slot: one tracer aimed at you (with a little scatter)
FireEB:
  ldy #0
@f:
  lda eb_t,y
  beq @ok
  iny
  iny
  cpy #6*2                  ; wave enemies keep the pre-boss limit (6 tracers)
  bne @f
  rts
@ok:
  sty a_j
  lda #1
  sta eb_t,y
  lda #0
  sta eb_w,y
  lda en_x,x
  sta eb_x,y
  lda en_z,x
  sta eb_z,y
  lda en_dh,x
  asl
  asl
  asl
  asl
  sta eb_h,y
  lda en_z,x
  ASR4
  sta t1                    ; z px
  lda en_x,x
  ASR4
  sta t0                    ; x px
  jsr Rand
  sta t5
  and #$001F
  sec
  sbc #16                   ; -16..15 px of scatter sideways
  eor #$FFFF
  sec
  adc t0
  sta t2                    ; aim vector x (shooter minus aim point)
  lda t5
  xba
  and #$000F
  sec
  sbc #8                    ; -8..7 px vertically
  eor #$FFFF
  sec
  ldx c_i
  adc en_dh,x
  sta t3
  ; closing speed S = tracer speed + your speed
  lda diff
  asl
  asl
  clc
  adc #EB_SPD
  clc
  adc fwd
  sta t6
  ; distance ~ z + 3/8 |x|  -> q = S*256/d
  lda t2
  jsr Abs
  lsr
  lsr
  sta t7
  lsr
  clc
  adc t7
  clc
  adc t1
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
  adc fwd                   ; stored as world speed: your later speed changes still count
  ldy a_j
  sta eb_vz,y
  rts

; ---------------------------------------------------------------- enemy tracers (per physics step)
MoveEB:
  ldx #0
@l:
  lda eb_t,x
  bne :+
  jmp @n
: inc a
  sta eb_t,x
  cmp #170
  bcc :+
  jmp @kill
: stx c_j
  lda eb_z,x
  jsr RotTerm
  ldx c_j
  eor #$FFFF
  sec
  adc eb_x,x
  clc
  adc eb_vx,x
  sta eb_x,x
  lda eb_h,x
  clc
  adc eb_vh,x
  sta eb_h,x
  lda eb_z,x
  sta t6
  clc
  adc eb_vz,x
  sec
  sbc fwd
  sta eb_z,x
  bpl @ahead
  lda t6
  bpl :+
  jmp @behind
: ; it just crossed your wing line: 8 px either side, 7 px up/down
  lda eb_x,x
  jsr Abs
  cmp #8*16
  bcs @miss
  lda eb_h,x
  jsr Abs
  cmp #7*16
  bcs @miss
  lda eb_x,x
  ASR4
  tax
  phx
  ldx c_j
  lda eb_k,x
  plx
  ldy #0
  cmp #1
  lda #DMG_BUL
  bcc :+
  lda #DMG_SHARD            ; boss crest shard
:
  CHK 26
  jsr PlayerHit
  CHK 27
  ldx c_j
  bcs :+
  jsl X14_GrazeRoll          ; invulnerable: it flies through (v1.4: rolling through it = graze x2)
  bra @n
: jmp @kill
@miss:
  ldx c_j
  jsl X14_Graze              ; v1.4: near miss = graze
  bra @n
@ahead:
  ; whiz: about to pass close by your head (channel B follows the round)
  cmp #56*16
  bcs @n
  lda eb_w,x
  bne @n
  lda eb_x,x
  jsr Abs
  cmp #64*16
  bcs @n
  lda eb_h,x
  jsr Abs
  cmp #40*16
  bcs @n
  lda #1
  sta eb_w,x
  stx sfx_ni
  lda #K_EB
  sta sfx_nk
  lda eb_k,x
  beq :+
  lda #SB_SHARDW            ; crest shards: a longer, glassy whizz
  ldx #3
  ldy #22
  bra :++
: lda #SB_WHIZ
  ldx #2
  ldy #14
: jsr SfxB
  ldx c_j
  bra @n
@behind:
  cmp #.loword(-100*16)
  bpl @n
@kill:
  stz eb_t,x
@n:
  inx
  inx
  cpx eb_lim                 ; active slots only (6/2 in the field, 12/4 for the boss)
  beq :+
  jmp @l
: rts

; ---------------------------------------------------------------- enemy missiles
; X = enemy slot: launch once it is in position (tailers: from behind after 50 frames)
MaybeLaunch:
  lda en_ty,x
  cmp #T_TAIL
  bne @fwd
  lda en_t,x
  cmp #50
  bcs @go
  rts
@fwd:
  lda en_z,x
  cmp #420*16
  bcc @no
  cmp #760*16
  bcs @no
  lsr
  sta t0
  lda en_x,x
  jsr Abs
  cmp t0
  bcs @no
@go:
  ldy #0
@f:
  lda em_st,y
  beq @ok
  iny
  iny
  cpy #2*2                  ; wave enemies keep the pre-boss limit (2 missiles)
  bne @f
@no:
  rts
@ok:
  lda en_ar,x
  and #.loword(~AR_MSL)
  sta en_ar,x
  lda #1
  sta em_st,y
  lda en_x,x
  sta em_x,y
  lda en_z,x
  sta em_z,y
  lda en_dh,x
  asl
  asl
  asl
  asl
  sta em_h,y
  lda #0
  sta em_t,y
  sta em_w,y
  lda diff
  asl
  sta t0
  lda en_z,x
  bmi @behind
  lda #$8000
  sta em_hd,y
  lda #38
  bra @spd
@behind:
  lda #0
  sta em_hd,y
  lda #46
@spd:
  clc
  adc t0
  sta em_spd,y
  lda #1
  sta em_bp                 ; warning beep right away
  ; launch rush from the launcher's position (channel B, follows the missile)
  sty sfx_ni
  lda #K_EM
  sta sfx_nk
  lda #SB_MSW
  ldx #1
  ldy #30
  jmp SfxB

MoveEM:
  ldx #0
@l:
  lda em_st,x
  bne :+
  jmp @n
: stx c_j
  inc em_t,x
  lda em_z,x                ; your turn swings it around you
  jsr RotTerm
  sta t0
  ldx c_j
  lda em_x,x
  sec
  sbc t0
  sta em_x,x
  jsr RotTerm
  ldx c_j
  clc
  adc em_z,x
  sta em_z,x
  lda em_st,x
  cmp #1
  beq @track
  cmp #3
  beq :+
  jmp @fly                  ; missed: flies straight on
: lda em_h,x                ; out of fuel: drops away
  sec
  sbc #20
  sta em_h,x
  lda em_t,x
  cmp #40
  bcs :+
  jmp @fly
: jmp @kill
@track:
  lda em_t,x
  cmp #MSL_FUEL
  bcc :+
  lda #3
  sta em_st,x
  stz em_t,x
  jmp @fly
: lda em_h,x                ; ease to your altitude
  beq @hd
  bmi @hup
  sec
  sbc #8
  bpl @hs
  lda #0
  bra @hs
@hup:
  clc
  adc #8
  bmi @hs
  lda #0
@hs:
  sta em_h,x
@hd:
  ; guidance: c = x*cos(hd) - z*sin(hd) (px off its line of flight)
  lda em_x,x
  ASR4
  sta t1
  lda em_z,x
  ASR4
  sta t2
  lda em_hd,x
  xba
  and #$00FF
  asl
  tax
  lda f:SinTab,x
  sta t3
  txa
  clc
  adc #128
  and #$01FF
  tax
  lda f:SinTab,x
  sta t4
  lda t1
  ldx t4
  jsr MulSS
  sta t5
  lda t2
  ldx t3
  jsr MulSS
  eor #$FFFF
  sec
  adc t5
  sta t5
  ; overshot you? (you are behind it: x*sin + z*cos >= 0)
  lda t1
  ldx t3
  jsr MulSS
  sta t6
  lda t2
  ldx t4
  jsr MulSS
  clc
  adc t6
  bmi @ontrack
  ldx c_j
  lda #2
  sta em_st,x
  jsr MissWhoosh
  jmp @fly
@ontrack:
  ; turn = clamp(-c * 64, +-omega); omega = 1.75 heading units per frame (+1/16 per loop)
  lda t5
  bmi @cn
  cmp #48
  bcc @cm
  lda #48
  bra @cm
@cn:
  cmp #.loword(-48)
  bcs @cm
  lda #.loword(-48)
@cm:
  asl
  asl
  asl
  asl
  asl
  asl
  jsr Neg
  sta t6
  lda diff
  asl
  asl
  asl
  asl
  clc
  adc #$01C0
  sta t7
  lda t6
  bmi @tn
  cmp t7
  bcc @ta
  lda t7
  bra @ta
@tn:
  jsr Neg
  cmp t7
  bcc :+
  lda t7
: jsr Neg
@ta:
  ldx c_j
  clc
  adc em_hd,x
  sta em_hd,x
@fly:
  ldx c_j
  lda em_hd,x
  xba
  and #$00FF
  asl
  sta t3
  tax
  lda f:SinTab,x
  ldy c_j
  ldx em_spd,y
  jsr MulB
  ldx c_j
  clc
  adc em_x,x
  sta em_x,x
  lda t3
  clc
  adc #128
  and #$01FF
  tax
  lda f:SinTab,x
  ldy c_j
  ldx em_spd,y
  jsr MulB
  ldx c_j
  sta t0
  lda em_z,x
  sta t6
  clc
  adc t0
  sec
  sbc fwd
  sta em_z,x
  cmp #.loword(-260*16)
  bpl :+
  jmp @kill
: cmp #1200*16
  bmi :+
  jmp @kill
: lda em_x,x
  jsr Abs
  cmp #1300*16
  bcc :+
  jmp @kill
: lda em_st,x
  cmp #1
  bne @n
  ; hit: within 9 px sideways, 8 px up/down, as it reaches you
  lda em_x,x
  jsr Abs
  cmp #9*16
  bcs @n
  lda em_h,x
  jsr Abs
  cmp #8*16
  bcs @n
  lda em_z,x
  jsr Abs
  cmp #10*16
  bcc @hit
  lda em_z,x
  eor t6
  bpl @n
@hit:
  ldy #0
  lda t6
  bpl :+
  iny
: lda em_x,x
  ASR4
  tax
  lda #DMG_MSL
  CHK 26
  jsr PlayerHit
  CHK 27
  ldx c_j
  bcc @n
@kill:
  stz em_st,x
@n:
  inx
  inx
  cpx em_lim                 ; active slots only (6/2 in the field, 12/4 for the boss)
  beq :+
  jmp @l
:
  CHK 38
  jsr WarnStep
  CHK 39
  rts

; X = missile slot that just overshot: if it passed close, it screams past you (channel B)
MissWhoosh:
  lda em_w,x
  bne @r
  lda em_x,x
  jsr Abs
  cmp #96*16
  bcs @r
  lda em_z,x
  jsr Abs
  cmp #80*16
  bcs @r
  lda #1
  sta em_w,x
  stx sfx_ni
  lda #K_EM
  sta sfx_nk
  lda #SB_MSW
  ldx #2
  ldy #30
  jsr SfxB
@r:
  rts

; nearest tracking missile -> warning text + lock-on beeps (faster as it closes, panned to it)
WarnStep:
  lda #$7FFF
  sta t3
  lda #$FFFF
  sta t4
  ldx #0
@l:
  lda em_st,x
  cmp #1
  bne @nx
  lda em_x,x
  ASR4
  jsr Abs
  sta t0
  lda em_z,x
  ASR4
  jsr Abs
  clc
  adc t0
  cmp t3
  bcs @nx
  sta t3
  stx t4
@nx:
  inx
  inx
  cpx em_lim                 ; active slots only (6/2 in the field, 12/4 for the boss)
  bne @l
  ldx t4
  bpl @have
  stz warn
  lda #1
  sta em_bp
  bra @vis
@have:
  lda #1
  ldy em_z,x
  bpl :+
  lda #2
: sta warn
  dec em_bp
  bne @vis
  lda t3
  lsr
  lsr
  lsr
  cmp #5
  bcs :+
  lda #5
: cmp #30
  bcc :+
  lda #30
: sta em_bp
  stx sfx_ni
  lda #K_EM
  sta sfx_nk
  lda #SA_BEEP
  ldx #2
  ldy #4
  jsr SfxA
@vis:
  lda bm_warn               ; boss chest beam charging: "BEAM! CLIMB OR DIVE"
  beq :+
  lda #3
  sta warn
: inc warn_ph
  lda warn
  beq @off
  lda warn_ph
  and #8
  beq @off
  lda warn
  bra @cmp
@off:
  lda #0
@cmp:
  cmp warn_shown
  beq @r
  sta warn_shown
  lda row_dirty
  ora #(RD_HINT|RD_WARN)
  sta row_dirty
@r:
  rts

; ---------------------------------------------------------------- extra lives (boss v2)
UpTxt: .word FONT_SP, FONT_SP, FONT_0+1, FONT_U, FONT_P, FONT_EXCL, FONT_SP, FONT_SP

; after any score change: an extra life for every UP_STEP crossed (at most LIVES_MAX)
ScoreLife:
  lda score
  cmp next_up
  bcc @r
  lda next_up
  clc
  adc #UP_STEP
  sta next_up
  lda p_lives
  cmp #LIVES_MAX
  bcs ScoreLife             ; full: the threshold still moves on
  inc p_lives
  lda #UP_FLASH
  sta up_t
  lda #1
  sta up_snd
  bra ScoreLife
@r:
  rts

; per physics step: 1UP flash (HUD redrawn every 8 frames) and the pending jingle
UpTick:
  lda up_snd
  beq @nosnd
  lda mu_st                 ; the SPC is busy with a music upload: play it afterwards
  bne @nosnd
  lda sfxb_t                ; a louder sound (boss mega boom) still owns channel B: wait for it
  beq :+
  lda sfxb_p
  cmp #6
  bcs @nosnd
: stz up_snd
  stz sfx_nfx
  lda #4
  sta sfx_nfz
  lda #K_FIX
  sta sfx_nk
  lda #SB_ONEUP
  ldx #5
  ldy #44
  jsr SfxB
@nosnd:
  lda up_t
  beq @r
  dec up_t
  beq @hud                  ; flash over: the bar comes back
  lda up_t
  and #7
  cmp #7                    ; a new 8-frame phase starts
  bne @r
@hud:
  jmp HudText
@r:
  rts

; ---------------------------------------------------------------- HUD: "SH" + shield bar + lives
HudText:
  lda #$3000
  ldx view
  cpx #VIEW_COCK
  bne :+
  lda #$3400
: sta t4
  ora #FONT_S
  sta hudbuf
  lda t4
  ora #FONT_H
  sta hudbuf+2
  lda up_t                  ; 1UP flash: "1UP!" blinks in the bar slot (shown first, 8 frames on / 8 off)
  beq @bar
  and #8
  bne @bar
  ldx #0
: lda f:UpTxt,x
  ora t4
  sta hudbuf+4,x
  inx
  inx
  cpx #16
  bne :-
  jmp @lives
@bar:
  lda #$3400                ; bar: green, yellow at half, red when low
  ldx p_shield
  cpx #9
  bcs :+
  lda #$3000
  cpx #5
  bcs :+
  lda #$3800
: sta t3
  lda p_shield
  sta t0
  ldx #0
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
  ora t3
  sta hudbuf+4,x
  inx
  inx
  cpx #16
  bne @b
@lives:
  lda t4
  sta hudbuf+20
  ora #T_LIFE
  sta hudbuf+22
  lda p_lives
  clc
  adc #FONT_0
  ora t4
  sta hudbuf+24
  lda #1
  sta hud_flag
  rts

; ---------------------------------------------------------------- game flow
; after ReadJoy: no flying while you're a wreck or the game is over (START still works)
InputMask:
  lda p_dead
  ora gameover
  beq :+
  lda joy
  and #KEY_START
  sta joy
  lda joy_new
  and #KEY_START
  sta joy_new
: rts

; the game-over screen lives in the chase view's sky
GameOverView:
  stz go_req
  jsr BossAbort
  lda view
  cmp #VIEW_CHASE
  beq :+
  lda #VIEW_CHASE
  sta view
  jsr LoadView
: lda row_dirty
  ora #RD_ALL
  sta row_dirty
  rts

RestartGame:
  jsr BossAbort
  stz score
  jsr ScoreText
  stz diff
  stz wave_pos
  lda #90
  sta wave_tm
  stz ms_st
  ldx #NEN*2-2
: stz en_st,x
  dex
  dex
  bpl :-
  ldx #NBU*2-2
: stz bu_d,x
  dex
  dex
  bpl :-
  ldx #NDE*2-2
: stz de_t,x
  dex
  dex
  bpl :-
  jsr InitAttack
  lda #INV_SPAWN
  sta p_inv
  lda row_dirty
  ora #RD_ALL
  sta row_dirty
  jsl X_Restart              ; v1.1: back to stage 1
  rts

; once per built frame: shake offset + flash level for the NMI
FxCommit:
  lda shake_t
  beq @s0
  lsr
  lsr
  inc a
  cmp #5
  bcc :+
  lda #4
: sta t0
  lda frame
  and #2
  beq :+
  lda t0
  jsr Neg
  bra @s1
: lda t0
  bra @s1
@s0:
  lda #0
@s1:
  sta c_shk
  lda flash_t               ; warm flash (red full, green+blue half), fading over the last frames
  cmp #5
  bcc :+
  lda #5
: asl
  cmp cl_fog                ; v1.5: flying through a cloud whites the picture out
  bcs :+
  lda cl_fog
: sta c_flash
  rts

; ---------------------------------------------------------------- text rows (one 64-byte row DMA per frame)
RowUpdate:
  lda row_flag
  bne @r
  lda row_dirty
  bne :+
@r:
  rts
: bit #RD_BOSS
  beq :+
  and #.loword(~RD_BOSS)
  sta row_dirty
  jmp RowBoss
: bit #RD_HINT
  beq :+
  and #.loword(~RD_HINT)
  sta row_dirty
  jmp RowHint
: bit #RD_WARN
  beq :+
  and #.loword(~RD_WARN)
  sta row_dirty
  jmp RowWarn
: bit #RD_SKYA
  beq :+
  and #.loword(~RD_SKYA)
  sta row_dirty
  lda #2
  jmp RowSky
: bit #RD_SKYB
  beq :+
  and #.loword(~RD_SKYB)
  sta row_dirty
  lda #3
  jmp RowSky
: and #.loword(~RD_SKYC)
  sta row_dirty
  lda #5
  jmp RowSky

; copy a 32-tile row from the view's ROM map: A = row
RowFromMap:
  sta t0
  asl
  asl
  asl
  asl
  asl
  clc
  adc #$5C00
  sta row_addr
  lda t0
  asl
  asl
  asl
  asl
  asl
  asl
  tax
  ldy #0
  lda view
  cmp #VIEW_COCK
  beq @ck
@tx:
  lda f:MapText,x
  sta rowbuf,y
  inx
  inx
  iny
  iny
  cpy #64
  bne @tx
  rts
@ck:
  lda f:MapCock,x
  sta rowbuf,y
  inx
  inx
  iny
  iny
  cpy #64
  bne @ck
  rts

ClearRowBuf:
  ldx #62
: stz rowbuf,x
  dex
  dex
  bpl :-
  rts

; Y = text (length-prefixed, in this bank), A = palette/priority bits, X = column; centred if X = $FF
PutTxt:
  sta t1
  sty t2
  lda a:$0000,y
  and #$00FF
  sta t3                    ; length
  cpx #$FF
  bne :+
  lda #32
  sec
  sbc t3
  lsr
  tax
: txa
  asl
  tax
  ldy t2
@c:
  iny
  lda a:$0000,y
  and #$00FF
  beq :+
  ora t1
: sta rowbuf,x
  inx
  inx
  dec t3
  bne @c
  rts

RowHint:
  lda view
  cmp #VIEW_COCK
  bne @tx
  lda #27                   ; cockpit: bottom row of the dashboard (pause only)
  jsr RowFromMap
  lda paused
  bne :+
  jmp @set
: ldy #.loword(TX_PAUSED)
  lda #$3000
  ldx #$FF
  jsr PutTxt
  jmp @set
@tx:
  lda #26
  jsr RowFromMap
  lda gameover
  beq :+
  jsr ClearRowBuf
  ldy #.loword(TX_PRESS)
  lda #$3000
  ldx #$FF
  jsr PutTxt
  jmp @set
: lda paused
  beq :+
  jsr ClearRowBuf
  ldy #.loword(TX_PAUSED)
  lda #$3000
  ldx #$FF
  jsr PutTxt
  jmp @set
: lda b_dad                ; v1.6: dad's taunt, entrance + early fight, on the dark HUD row
  beq @nott
  lda b_st
  cmp #BS_ENTER
  beq @taunt
  cmp #BS_FIGHT
  bne @nott
  lda b_t
  cmp #TAUNT_T-ENTER_T
  bcs @nott
@taunt:
  jsr ClearRowBuf
  ldy #.loword(TX_TAUNT)
  lda #$3800
  ldx #$FF
  jsr PutTxt
  jmp @set
@nott:
  lda b_aim
  beq :+
  lda warn_shown
  bne :+
  jsr ClearRowBuf
  ldy #.loword(TX_AIM)
  lda b_dad
  beq @aimr
  ldy #.loword(TX_DADAIM)
@aimr:
  lda #$3000
  ldx #$FF
  jsr PutTxt
  jmp @set
: lda b_st
  cmp #BS_WARN
  bne :+
  jsr ClearRowBuf
  ldy #.loword(TX_APPROACH)
  lda b_dad
  beq @appr
  ldy #.loword(TX_DADAPP)
@appr:
  lda #$3800
  ldx #$FF
  jsr PutTxt
  jmp @set
: lda warn_shown
  beq @set
  jsr ClearRowBuf
  jsr WarnTxt
@set:
  lda #1
  sta row_flag
  rts

WarnTxt:
  ldy #.loword(TX_WARN_F)
  lda warn_shown
  cmp #2
  bne :+
  ldy #.loword(TX_WARN_B)
: cmp #3
  bne :+
  ldy #.loword(TX_BEAM)
: lda #$3800
  ldx #$FF
  jmp PutTxt

RowWarn:
  lda view
  cmp #VIEW_COCK
  beq :+
  rts
: lda #3
  jsr RowFromMap
  jsl X_WarnRow              ; v1.1: boss warnings, then stage / power-up messages
  bcs :+
  lda warn_shown
  beq :+
  jsr WarnTxt
: lda #1
  sta row_flag
  rts

; A = sky row (2, 3 = big GAME OVER, 5 = FINAL SCORE); chase view only
RowSky:
  sta t5
  ldx view
  cpx #VIEW_CHASE
  beq :+
  rts
: jsr RowFromMap
  lda gameover
  bne :+
  lda t5
  jsl X_SkyRow               ; v1.1: boss texts, then stage banners / power-up messages
  jmp @set
: lda t5
  cmp #5
  beq @final
  ; big letters: G A M E _ O V E R from 7 (2 tiles each; BIG_x = TL, TR, BL, BR map words)
  ldy #0
@g:
  lda BigWord,y
  beq @sp
  ldx t5
  cpx #3
  bne :+
  clc
  adc #4                    ; bottom half
: sta t0
  tya
  asl
  clc
  adc #14
  sta t1
  ldx t0
  lda a:0,x
  ora #$3800
  ldx t1
  sta rowbuf,x
  ldx t0
  lda a:2,x
  ora #$3800
  ldx t1
  sta rowbuf+2,x
@sp:
  iny
  iny
  cpy #18
  bne @g
  bra @set
@final:
  ldy #.loword(TX_FINAL)
  lda #$3000
  ldx #7
  jsr PutTxt
  ldx #0
: lda scorebuf,x
  and #$03FF
  ora #$3000
  sta rowbuf+38,x
  inx
  inx
  cpx #12
  bne :-
@set:
  lda #1
  sta row_flag
  rts
BigWord: .word .loword(BIG_G), .loword(BIG_A), .loword(BIG_M), .loword(BIG_E), 0, .loword(BIG_O), .loword(BIG_V), .loword(BIG_E), .loword(BIG_R)

; ---------------------------------------------------------------- live pan / volume for both SFX channels
; t0 = x px, t1 = z px, t7 = channel bit ($80 = A, 0 = B) -> ports 3 (pan) and 0 (volume)
SfxSend:
  lda mu_st
  beq :+
  rts
: lda t0
  jsr Abs
  sta t2
  lda t1
  jsr Abs
  clc
  adc t2
  sta t3
  clc
  adc #8
  sta t4
@n1:
  lda t4
  cmp #256
  bcc :+
  lsr t4
  lsr t2
  bra @n1
: lda t2
  asl
  asl
  asl
  asl
  asl
  asl
  sec
  sbc t2
  ldx t4
  jsr DivU
  cmp #64
  bcc :+
  lda #63
: bit t0
  bpl :+
  jsr Neg
: clc
  adc #64
  cmp #128
  bcc :+
  lda #127
: lsr                       ; 0..63
  ldx t1
  cpx #.loword(-6)
  bcs :+
  bit t1
  bpl :+
  ora #$40                  ; behind you
: ora t7
.ifdef SFXDBG
  bit #$80
  bne @dpa
  sta dbg_pb
  bra @dpd
@dpa:
  sta dbg_pa
@dpd:
.endif
  A8
  sta f:$002143
  A16
  lda t3
  lsr
  clc
  adc #40
  sta t4
  lda #8128
  sta t5
@n2:
  lda t4
  cmp #256
  bcc :+
  lsr t4
  lsr t5
  bra @n2
: lda t5
  ldx t4
  jsr DivU
  cmp #128
  bcc :+
  lda #127
: ldx t7
  beq @v
  cmp #80                   ; channel A (warning beeps, impacts): never too quiet
  bcs :+
  lda #80
: cmp #126
  bcc @v
  lda #125                  ; keeps $FE (APU reboot) off port 0
@v:
  ldx mu_ff
  bne :+
  ora t7
  A8
  sta f:$002140
  A16
: rts

; A = kind, X = index, Y = fixed-point offset -> t0, t1 (px); carry clear if the object is gone
SfxPos:
  cmp #K_EN
  bne :+
  lda en_st,x
  bne @rf37557
  jmp @gone
@rf37557:
  lda en_x,x
  ASR4
  sta t0
  lda en_z,x
  jmp @z
: cmp #K_EB
  bne :+
  lda eb_t,x
  bne @rf62533
  jmp @gone
@rf62533:
  lda eb_x,x
  ASR4
  sta t0
  lda eb_z,x
  jmp @z
: cmp #K_EM
  bne :+
  lda em_st,x
  bne @rf89579
  jmp @gone
@rf89579:
  lda em_x,x
  ASR4
  sta t0
  lda em_z,x
  jmp @z
: cmp #K_BOSS
  bne :+
  lda b_st
  beq @gone
  lda b_x
  ASR4
  sta t0
  lda b_z
  jmp @z
: cmp #K_BEAM
  bne :+
  lda bm_on
  beq @gone
  lda bm_x
  ASR4
  sta t0
  lda #20*16                ; the beam's near end sweeps right past you
  jmp @z
: cmp #K_ROLL
  bne :+
  lda roll_t
  beq @gone
  jsl X14_RollPos            ; v1.4: the roll whoosh circles your head
  sec
  rts
: lda sfx_fx,y
  sta t0
  lda sfx_fz,y
  sta t1
  sec
  rts
@z:
  ASR4
  sta t1
  sec
  rts
@gone:
  clc
  rts

SfxLiveA:
  lda sfxa_t
  beq @no
  lda sfxa_k
  beq @no
  ldx sfxa_i
  ldy #0
  jsr SfxPos
  bcc @no
  lda #$80
  sta t7
  jsr SfxSend
  sec
  rts
@no:
  clc
  rts

SfxLiveB:
  lda sfxb_t
  beq @no
  lda sfxb_k
  beq @no
  ldx sfxb_i
  ldy #2
  jsr SfxPos
  bcc @no
  stz t7
  jsr SfxSend
  sec
  rts
@no:
  clc
  rts
