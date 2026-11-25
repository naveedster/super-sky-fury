; =====================================================================
;  SUPER SKY FURY v1.7 -- "make the game better" (again)
;  star medals (a value ladder: 100 .. 5000 points each, missing one resets it), mid-stage
;  checkpoints with CONTINUE at the game over, and one set piece per stage from the wave script
;  (T_EVENT): an ocean bomber convoy (medals x2), a desert sandstorm and an arctic blizzard
;  (crosswind gusts you have to steer against + heavy haze), a night flak barrage (bursts
;  around you that throw tracers).  Included from main.s after v14.s; XCODE bank, DB = $80.
; =====================================================================
T_EVENT   = $84             ; wave script: x = event, z = frames (EV_CHECK: none)
EV_CHECK  = 0
EV_STORM  = 1
EV_FLAK   = 2
EV_CONVOY = 3
PU_MEDAL  = 3               ; power-up kind 3: a star medal
MD_EVERY  = 2               ; a medal from every 2nd kill
MD_MAX    = 9*2             ; ladder top (index * 2)
.segment "BSS"
cp_ok:   .res 2
cp_pos:  .res 2
cp_st:   .res 2
md_lv:   .res 2
md_kc:   .res 2
md_n:    .res 2
ev_k:    .res 2
ev_t:    .res 2
ev_c:    .res 2
ev_len:  .res 2
wind:    .res 2
pu_sx:   .res NPU*2
pu_sy:   .res NPU*2

.segment "CODE"
T_Continue:                 ; (bank 0, from Buttons) game over -> back to the last checkpoint
  lda diff
  pha
  jsr RestartGame
  pla
  sta diff
  jsl X17_Continue
  rts

.segment "XCODE"
.a16
.i16
; new game from the title: no checkpoint yet
X17_NewGame:
  stz cp_ok
  stz cp_st
  stz cp_pos
  rtl

; ResetRun (game start, restart, continue): medals / events off
X17_Reset:
  stz md_lv
  stz md_kc
  stz md_n
  stz ev_k
  stz ev_t
  stz wind
  rts

X17_Continue:
  lda cp_pos
  sta wave_pos
  lda #60
  sta wave_tm
  lda cp_st
  cmp stage
  beq @same
  sta stage
  jsl T_LoadView
@same:
  lda stage
  jsr Banner
  rtl

; Waves: T_EVENT entry, X = wave_pos
X17_Event:
  lda f:WaveData+2,x
  bne @ev
  txa                        ; checkpoint: continue from the entry after this one
  clc
  adc #10
  sta cp_pos
  lda stage
  sta cp_st
  lda #1
  sta cp_ok
  lda f:WaveData+4,x         ; z = 1: silent (stage starts: the banner is up)
  beq :+
  rtl
: lda #.loword(TX_CHECK)
  ldy #$3400
  jsr Msg
  rtl
@ev:
  sta ev_k
  lda f:WaveData+4,x
  sta ev_t
  sta ev_len
  stz ev_c
  lda ev_k
  cmp #EV_STORM
  bne @nst
  lda #.loword(TX_SAND)
  ldy stage
  cpy #2
  bne :+
  lda #.loword(TX_BLIZ)
: bra @msg
@nst:
  cmp #EV_FLAK
  bne @ncv
  lda #.loword(TX_FLAK)
  bra @msg
@ncv:
  lda #.loword(TX_CONVOY)
@msg:
  ldy #$3800
  jsr Msg
  rtl

; once per physics step (X_Step)
X17_Step:
  stz wind
  lda ev_t
  bne :+
  rts
: lda b_st
  ora gameover
  beq :+
  stz ev_t                   ; (a boss or the game over ends any event)
  rts
: dec ev_t
  bne :+
  stz ev_k
  rts
: lda ev_k
  cmp #EV_STORM
  bne @nw
  ; crosswind gusts: a triangle wave, +-$A0 (a full stick turn is $160), 8.5 s period
  lda frame
  and #511
  cmp #256
  bcc :+
  eor #511
: sec
  sbc #128                   ; -128 .. 127
  sta t0
  asl
  asl
  clc
  adc t0                     ; * 5
  cmp #$8000
  ror
  cmp #$8000
  ror                        ; * 5/4
  sta wind
  lda ev_t                   ; ease in / out over the first / last 64 frames
  cmp #64
  bcc @ease
  lda ev_len
  sec
  sbc ev_t
  cmp #64
  bcs @r
@ease:
  sta t0
  lda wind
  cmp #$8000
  ror
  cmp #$8000
  ror
  ldx t0
  cpx #32
  bcs :+
  cmp #$8000
  ror
: sta wind
@r:
  rts
@nw:
  cmp #EV_FLAK
  bne @r
  lda p_dead
  bne @r
  inc ev_c
  lda diff
  asl
  asl
  eor #$FFFF
  sec
  adc #40                    ; a burst every 40 frames (less on later loops)
  cmp ev_c
  bcs @r
  stz ev_c
  ; flak burst: a big fireball somewhere ahead that throws one tracer at you
  ldy #0
: lda en_st,y
  beq @ok
  iny
  iny
  cpy #NEN*2
  bne :-
  rts
@ok:
  sty x_t
  lda #ST_BOOM
  sta en_st,y
  lda #T_BIGBOOM
  sta en_ty,y
  jsl T_Rand
  and #$0FF0                 ; +-128 px across
  sec
  sbc #$0800
  ldy x_t
  sta en_x,y
  jsl T_Rand
  and #$0FF0
  clc
  adc #170*16                ; 170 .. 425 px ahead
  ldy x_t
  sta en_z,y
  jsl T_Rand
  and #7
  sec
  sbc #3
  sta en_dh,y
  lda #0
  sta en_hd,y
  sta en_hf,y
  sta en_t,y
  lda fwd
  sta en_spd,y
  ldx x_t
  jsl T_FireEB
  ldx x_t                    ; the burst's crump follows it past you (channel B, live pan)
  stx sfx_ni
  lda #K_EN
  sta sfx_nk
  lda #SB_BOOM
  ldx #2
  ldy #20
  jsl T_SfxB
  rts

; X_KillPts (X = x_i = the enemy slot): every MD_EVERY-th kill leaves a star medal
X17_MedalDrop:
  inc md_kc
  lda md_kc
  cmp #MD_EVERY
  bcc @r
  stz md_kc
  lda #PU_MEDAL
  jsr DropKind
  ldx x_i
@r:
  rts

; Collect: a medal (X = x_i = power-up slot): its value, a popup where it was, the ladder climbs
X17_MedalGet:
  inc md_n
  ldx md_lv
  lda f:MedVal,x
  ldy ev_k
  cpy #EV_CONVOY
  bne :+
  ldy ev_t
  beq :+
  asl                        ; convoy: double
: pha
  jsl T_ScoreAdd
  ldx x_i
  lda pu_sx,x
  sta t4
  lda pu_sy,x
  sta t5
  pla
  jsr MedalPop
  lda md_lv
  cmp #MD_MAX
  bcs @top
  inc a
  inc a
  sta md_lv
  cmp #MD_MAX
  bne @snd
  lda #.loword(TX_MEDMAX)
  ldy #$3400
  jsr Msg
  bra @snd
@top:
@snd:
  stz sfx_nk                 ; bright chime, pitch climbs with the ladder (channel A, centred)
  lda #SA_BEEP
  ldx #2
  ldy #6
  jsl T_SfxA
  rts

; a medal got away: the ladder starts again
X17_MedalMiss:
  lda md_lv
  cmp #4*2
  bcc :+
  lda #.loword(TX_MEDLOST)
  ldy #$3800
  jsr Msg
: stz md_lv
  rts

; floating "+N00" / "NN00" at t4, t5 (A = points / 100)
MedalPop:
  sta t2
  jsr PopSlot
  lda t4
  sta pp_x,y
  lda t5
  sec
  sbc #10
  sta pp_y,y
  jsr PopClear
  ldx t3
  lda t2
  cmp #100
  bcc :+
  lda #99
: cmp #10
  bcs @two
  A8
  lda #GL_PLUS+GL_ORNG
  sta pp_g,x
  lda t2
  clc
  adc #GL_ORNG
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
  clc
  adc #GL_ORNG
  sta pp_g+1,x
  tya
  clc
  adc #GL_ORNG
  sta pp_g,x
@zz:
  A8
  lda #GL_ORNG
  sta pp_g+2,x
  sta pp_g+3,x
  A16
  jmp PopDirty

MedVal: .word 1, 2, 3, 5, 8, 10, 15, 20, 30, 50   ; x 100 points

; X_Project: draw power-up slot X (= x_i) at sx, sy: a capsule, or a star medal
X17_PuDraw:
  lda sx
  sta pu_sx,x
  lda sy
  sta pu_sy,x
  lda pu_k,x
  cmp #PU_MEDAL
  bne @cap
  lda frame                 ; white-hot star over a twinkling glow
  and #4
  beq @mdf
  lda #$C0
@mdf:
  ora obj_pri
  sta o_a
  lda #F_HSPARK
  jsl T_AddObj
  lda frame
  and #8
  bne @r
  lda obj_pri
  sta o_a
  lda #F_X16A
  jsl T_AddObj
@r:
  rts
@cap:
  lda #$04
  ora obj_pri
  sta o_a
  lda pu_k,x
  clc
  adc #F_PU_P
  jsl T_AddObj
  rts


.segment "CODE"                ; (what follows in main.s, e.g. ApuUpload, lives in bank 0)
