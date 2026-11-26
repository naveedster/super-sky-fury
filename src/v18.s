; =====================================================================
; SUPER SKY FURY v1.8: smooth sprite animation (2 MB LoROM)
;   chase jet: 17 bank angles x 5 nose pitches + a 64-step barrel roll, streamed one per vblank
;   near enemies: 64 yaws x 3 bank angles; ground props: 32 yaws (see tools/gen_assets.py)
; =====================================================================
JS_LEVEL = 2*JS_NB + JS_NB/2        ; level flight frame (also the sheet placeholder)
.ifndef LAG_LN
LAG_LN = 185                        ; v1.8 adaptive streaming: last frame's load (scanlines) that counts as heavy
.endif
.ifndef JET_LN
JET_LN = LAG_LN                     ; jet frame waits entirely on a heavy frame
.endif
.ifndef JWAIT
JWAIT = 3
.endif
.ifndef JHYS
JHYS = $20                          ; jet bank hysteresis (turn rate past a threshold)
.endif
.ifndef CWAIT
CWAIT = 2
.endif
.ifndef FX_LN
FX_LN = LAG_LN                      ; explosion cells: heavy-frame threshold
.endif

.segment "ZEROPAGE"
x18_v:  .res 2
x18_w:  .res 2
x18_r:  .res 2
x18_id: .res 2

.segment "BSS"
js_nose:  .res 2                    ; 0..8 eased nose pitch (4 = level)
js_bl:    .res 2                    ; shown bank level -8..8

.segment "XCODE"
; chase jet frame: bank level from |turnrate| (8 steps a side), nose eased toward climb / dive
X18_JetFrame:
  lda climb                         ; -1 / 0 / 1 -> target 0 / 4 / 8
  asl
  asl
  clc
  adc #4
  cmp js_nose
  beq @nd
  bcc @dn
  inc js_nose
  bra @nd
@dn:
  dec js_nose
@nd:
  lda turnrate                      ; signed bank level -8..8, with hysteresis: a one-step change needs
  jsr @lev                          ; the turn rate $20 past the threshold (no flicker on stick jitter)
  cmp js_bl
  beq @hv
  sta x18_r
  sec
  sbc js_bl
  bmi @dn2
  lda turnrate
  sec
  sbc #JHYS
  bra @ck
@dn2:
  lda turnrate
  clc
  adc #JHYS
@ck:
  jsr @lev
  cmp js_bl
  beq @hv
  lda x18_r
  sta js_bl
@hv:
  lda js_bl
  clc
  adc #JS_NB/2
  sta x_t
  lda js_nose
  and #$FFFE
  tax
  lda f:NoseOff,x
  clc
  adc x_t
.ifdef JETFIX
  lda #JS_LEVEL
.endif
  sta js_want
  lda #T_CHASE_JETS
  sta stile
  lda #$30
  sta sattr
  rtl
@lev:                               ; A = turn rate -> A = signed level
  tay
  bpl :+
  eor #$FFFF
  inc a
: ldx #0
: cmp f:BankThr,x
  bcc :+
  inx
  inx
  cpx #16
  bne :-
: txa
  lsr
  cpy #0
  bpl :+
  eor #$FFFF
  inc a
: rts
BankThr: .word $1A, $4E, $82, $B6, $EA, $11E, $152, $186
NoseOff: .word 0, 0, JS_NB, 0, 2*JS_NB, 0, 3*JS_NB, 0, 4*JS_NB

; NMI: may the jet frame upload this vblank? carry set = no
X18_JetGate:
.ifdef J30
  lda nmi_count
  sec
  sbc js_upn
  cmp #J30
  bcc @no
.endif
.ifndef NOLAG
  lda ld_last                       ; heavy frame (near the 262-line limit): the jet waits,
  cmp #JET_LN                       ; but never more than JWAIT vblanks in a row
  bcc :+
  lda lag_t
  cmp #JWAIT
  bcs :+
  inc lag_t
  bra @no
:
.endif
  stz lag_t
  lda nmi_count
  sta js_upn
  inc js_upd                        ; (the medium / fx cells wait a vblank)
  clc
  rts
@no:
  sec
  rts

; NMI: rows to upload for js_have -> js_want (union of both frames' non-empty rows); n_t / n_k advanced
X18_JetRows:
  ldx js_want
  lda f:JetRows,x
  and #$00FF
  sta x18n_u
  ldx js_have
  cpx #JS_N
  bcc :+
  lda #$70                          ; unknown: all 8
  bra :++
: lda f:JetRows,x
  and #$00FF
: sta x18n_w
  and #$000F                        ; r0 = min
  sta x18n_v0
  lda x18n_u
  and #$000F
  cmp x18n_v0
  bcs :+
  sta x18n_v0
: lda x18n_w                        ; r1 = max
  and #$00F0
  sta x18n_v1
  lda x18n_u
  and #$00F0
  cmp x18n_v1
  bcc :+
  sta x18n_v1
: lda x18n_v0                       ; source += r0 * 256, VRAM += r0 * 256 words
  xba
  clc
  adc n_t
  sta n_t
  lda x18n_v0
  xba
  clc
  adc n_k
  sta n_k
  lda x18n_v1
  lsr
  lsr
  lsr
  lsr
  sec
  sbc x18n_v0
  inc a
  tax
  rts

; barrel roll: one of 64 rendered roll angles per frame (no flips)
X18_RollFrame:
  lda #ROLL_T
  sec
  sbc roll_t
  cmp #ROLL_T
  bcc :+
  lda #ROLL_T-1
: tax
  lda f:RollAng,x
  and #$00FF
  ldx roll_d
  bpl :+
  eor #$FFFF
  inc a
  and #JS_NROLL-1
: clc
  adc #JS_ROLL0
  sta js_want
  lda #T_CHASE_JETS
  sta stile
  lda #$30
  sta sattr
  lda #4
  sta js_nose
  rtl
RollAng:
.repeat ROLL_T, I
  .byte ((I+1)*JS_NROLL*2 + ROLL_T+1) / ((ROLL_T+1)*2)
.endrepeat

.segment "CODE"                ; (what follows in main.s, e.g. ApuUpload, lives in bank 0)

.segment "BSS"
en_wv:    .res NEN*2                ; v1.8: weave (8-bit angle units) of the last move
en_pw:    .res NEN*2                ; previous world display heading
en_pf:    .res NEN*2                ; frame it was taken
en_bk:    .res NEN*2                ; smoothed turn rate (bank)
en_sl:    .res NEN*2                ; slot (x2) drawn last frame, $FFFF none
en_ms:    .res NEN*2                ; medium slot (x2) drawn last frame, $FFFF none
MS_N = 5
ms_want:  .res MS_N*2
ms_have:  .res MS_N*2
ms_use:   .res MS_N*2
ms_bg:    .res 2
fx_req:   .res 6                    ; v1.8 fx cells A (X32A), B (X32B), C (X16C): wanted sequence frame
fx_st:    .res 6                    ; frame it was asked for
fx_have:  .res 6
fx_bg:    .res 2
fl_have:  .res 2
bf_have:  .res 2
fx_ok:    .res 2
ms_lw:    .res 2                    ; v1.8: vblanks the medium / fx cells have waited on heavy frames
fx_lw:    .res 2
ms_dt:    .res 2                    ; v1.8: medium cells asked for (NMI loop pending)                    ; v1.8: fx cells idle (all home, no recent requests)
.ifdef FXPROF
fxp_a: .res 2
fxp_b: .res 2
.endif
dv_vt:    .res 2                    ; v1.8 dad: voice frame + 1 (0 = not talking)
dv_bt:    .res 2                    ; frames to the next blink
dv_bk:    .res 2                    ; blink phase
dv_ew:    .res 2                    ; eye state wanted / in VRAM
dv_eh:    .res 2
dv_mw:    .res 2                    ; mouth state wanted / in VRAM
dv_mh:    .res 2
dv_bc:    .res 2                    ; breath clock
dv_br:    .res 2                    ; chest offset (px up)
x18n_u:   .res 2                    ; (NMI-private)
x18n_v0:  .res 2
js_upn:   .res 2                    ; vblank of the last jet upload
js_upd:   .res 2                    ; the jet uploaded this vblank
lag_t:    .res 2                    ; vblanks the jet frame has waited on heavy frames
x18n_v1:  .res 2
x18n_w:   .res 2

.segment "XCODE"
; near enemy (chase): 64 yaws x 3 banks. In: X = enemy. Out: A = logical frame, carry clear (rtl).
; When the wanted frame is not in VRAM yet the enemy keeps drawing its own slot (old yaw) and the
; slot is re-targeted in place, so turns never flash a stand-in sprite.
; enemy X -> x18_id = bank row * 64 + yaw64 (display heading incl. weave; bank from the smoothed turn)
X18_EnId:
  lda en_wv,x
  xba
  and #$FF00
  clc
  adc en_hd,x
  sta x18_v                         ; display heading (camera-relative)
  clc
  adc heading
  sta x18_w                         ; world heading
  lda frame
  dec a
  cmp en_pf,x
  beq :+
  stz en_bk,x                       ; not drawn last frame: no turn history, no own slot
  lda #$FFFF
  sta en_sl,x
  sta en_ms,x
  lda x18_w
  sta en_pw,x
: lda frame
  sta en_pf,x
  lda x18_w
  sec
  sbc en_pw,x
  sta x18_r                         ; turn this frame
  lda x18_w
  sta en_pw,x
  lda x18_r                         ; bank += (rate - bank) / 4
  sec
  sbc en_bk,x
  cmp #$8000
  ror a
  cmp #$8000
  ror a
  clc
  adc en_bk,x
  sta en_bk,x
  ldy #64                           ; bank 0 row
  cmp #$8000
  bcs @neg
  cmp #$A0
  bcc @yb
  ldy #128
  bra @yb
@neg:
  cmp #.loword(-$A0)
  bcs @yb
  ldy #0
@yb:
.ifdef NOBANK
  ldy #64
.endif
  sty x18_r
  lda x18_v
  clc
  adc #$0200
  xba
  lsr
  lsr
.ifdef NYAW32
  and #$003E
.else
  and #$003F
.endif
  clc
  adc x18_r
  sta x18_id
  rts

X18_EnNear:
  jsr X18_EnId
  lda #$FFFF
  sta en_ms,x
  phx
  jsr SlotGet
  plx
  cmp #$FFFF
  beq @miss
  asl
  sta en_sl,x
  lsr
  bra @ok
@miss:
  ldy en_sl,x                       ; own slot from last frame
  cpy #SS_SLOTS*2
  bcs @fb
  lda ss_use,y
  cmp ss_fc
  beq @shared                       ; somebody else drew it this frame: leave it alone
  lda x18_id                        ; re-target it in place (old yaw until the NMI loads the new one)
  sta ss_want,y
@use:
  lda ss_fc
  sta ss_use,y
  tya
  lsr
@ok:
  clc
  adc #F_SLOT0
  clc
  rtl
@shared:
  lda ss_want,y
  cmp ss_have,y
  beq @use                          ; still holds a frame of this model: draw it
@fb:
  lda #$FFFF
  sta en_sl,x
  lda #F_EL_TOW
  clc
  rtl

; medium enemy (chase): the same frames at 16x16, streamed into the 5 EMY cells
X18_EnMed:
.ifdef NOMED
  jml X18_MedOld
.endif
  lda b_gfx
  beq :+
  jml X18_MedOld
: jsr X18_EnId
  lda #$FFFF
  sta en_sl,x
  ldy #0                            ; resident?
: lda ms_have,y
  cmp x18_id
  bne @n1
  lda ms_want,y
  cmp x18_id
  beq @hit
@n1:
  iny
  iny
  cpy #MS_N*2
  bne :-
  ldy en_ms,x                       ; own cell from last frame: re-target in place
  cpy #MS_N*2
  bcs @take
  lda ms_use,y
  cmp ss_fc
  beq @take
  lda x18_id
  cmp ms_want,y
  beq @hit
  sta ms_want,y
  inc ms_dt                         ; (the NMI cell loop has work)
  bra @hit
@take:
  ldy #0                            ; a cell nobody drew this frame (and not already on its way)
: lda ms_use,y
  cmp ss_fc
  beq @n2
  lda ms_want,y
  cmp ms_have,y
  bne @n2
  lda x18_id
  sta ms_want,y
  inc ms_dt
  bra @hit
@n2:
  iny
  iny
  cpy #MS_N*2
  bne :-
  ldy en_ms,x                       ; all cells busy: keep drawing our cell / the nearest one
  cpy #MS_N*2
  bcc @hit
  ldy #0
@hit:
  tya
  sta en_ms,x
  lda ss_fc
  sta ms_use,y
  tya
  lsr
  clc
  adc #F_EMY0
  clc
  rtl

MedTiles: .word T_CHASE_EMY0, T_CHASE_EMY1, T_CHASE_EMY2, T_CHASE_EMY3, T_CHASE_EMY4
MedHome:  .word 64, 72, 80, 88, 96  ; the sheet's EMY0..4 = bank 0, yaw 0/45/90/135/180

; sheet (re)loaded: cells hold the sheet's own frames
X18_MsReset:
  ldx #0
: lda f:MedHome,x
  sta ms_want,x
  sta ms_have,x
  stz ms_use,x
  inx
  inx
  cpx #MS_N*2
  bne :-
  jmp X18_FxHome

X18_MsBg:
  lda b_gfx
  beq :++
  lda #1
  sta ms_bg
  lda b_gfx
  cmp #2
  beq :+
  sta fx_bg                         ; sheet rows streaming: the fx cells are re-homed afterwards
  stz dv_eh                         ; (and his face cells come back as the sheet's own)
  stz dv_mh
: lda b_gfx
: rts

; NMI tail of X_Stream (chase, field sheet): up to 5 medium cells (2 x 64 B each)
X18_MedStream:
  lda b_gfx                         ; fast path: field sheet, nothing asked for, no flame
  ora ms_bg
  ora fx_bg
  ora ms_dt
  ora boost
  bne @slow
  lda fx_ok
  beq @slow
  stz js_upd
  rtl
@slow:
  lda b_gfx
  beq :+
  lda #$FFFF
  ldx #0
@inv:
  sta ms_have,x
  sta ms_want,x
  inx
  inx
  cpx #MS_N*2
  bne @inv
  sta ms_bg
  jmp X18_FxStream
: lda ms_bg
  beq :+
  stz ms_bg
  jsr X18_MsReset                   ; field sheet back from ROM
  jmp X18_FxStream
: lda js_upd
.ifndef NOSHARE
  beq :+
  jmp X18_FxStream
.endif
:
.ifndef NOLAG
  lda ld_last                       ; heavy frame: mid-range cells wait (at most CWAIT vblanks)
  cmp #LAG_LN
  bcc :+
  lda ms_lw
  cmp #CWAIT
  bcs :+
  inc ms_lw
  jmp X18_FxStream
: stz ms_lw
.endif
: lda ms_dt
  bne :+
  jmp X18_FxStream                  ; nothing new asked for
: stz ms_dt
  ldy #0
@lp:
  lda ms_want,y
  cmp ms_have,y
  beq @nx
  jsr SS_Line
  cmp #30
  bcs @late
  lda ms_want,y
  sta ms_have,y
  xba
  lsr                               ; *128
  clc
  adc #.loword(MedFrames)
  sta n_t
  A8
  lda #^MedFrames
  sta A1B0
  A16
  tyx
  lda f:MedTiles,x
  asl
  asl
  asl
  asl
  clc
  adc #$6000
  sta VMADDL
  clc
  adc #16*16
  sta n_k
  lda n_t
  sta A1T0L
  lda #64
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
  lda n_k
  sta VMADDL
  lda n_t
  clc
  adc #64
  sta A1T0L
  lda #64
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
@nx:
  iny
  iny
  cpy #MS_N*2
  bne @lp
@done:
  jmp X18_FxStream
@late:
  inc ms_dt                         ; out of lines: the rest next vblank
  jmp X18_FxStream

; ---------------------------------------------------------------- v1.8 fx cells
FX_HOME_A = 3
FX_HOME_B = 5                        ; (B frame 5 = sequence frame 13)
FX_HOME_C = 2
FX_C0 = 24*512
FX_F0 = FX_C0 + 12*128
FX_B0 = FX_F0 + 16*128
FxHome:  .word FX_HOME_A, FX_HOME_B, FX_HOME_C
FxIdx:   .word 0, 16, 48                ; (x2) first entry of each cell in FxAddr
FxAddr:  .repeat 24, I
           .word .loword(FxFrames) + I*512
         .endrepeat
         .repeat 12, I
           .word .loword(FxFrames) + FX_C0 + I*128
         .endrepeat
FxBase:  .word 0, 8*512, FX_C0       ; first frame of each cell's sequence
FxSize:  .word 512, 512, 128         ; bytes per frame
FxRow:   .word 128, 128, 64          ; bytes per tile row
FxNRow:  .word 4, 4, 2
FxTile:  .word T_CHASE_X32A, T_CHASE_X32B, T_CHASE_X16C

X18_FxHome:
  ldx #4
: lda f:FxHome,x
  sta fx_have,x
  dex
  dex
  bpl :-
  stz fl_have
  stz bf_have
  stz fx_bg
  rts

; enemy explosion frame (combat.s @boom). In: X = enemy, t1 = depth. Out: A = frame, o_a = attr.
; One continuous 40-frame sequence: flash, 8 + 16 streamed fireball frames, 12 streamed smoke frames.
X18_Boom:
  lda obj_pri
  sta o_a
  lda en_t,x
  cmp #4
  bcc @fl
  cmp #28
  bcs @sm
  lda en_ty,x
  cmp #T_BIGBOOM
  beq :+
.ifndef FXTEST
  lda t1
  cmp #170
  bcs @fl
.endif
: lda en_t,x
  cmp #12
  bcs @b
  sec
  sbc #4
  ldy #0
  jsr @req
  lda #F_X32A
  rtl
@b:
  sec
  sbc #12
  ldy #2
  jsr @req
  lda #F_X32B
  rtl
@sm:
  sec
  sbc #28
  cmp #12
  bcc :+
  lda #11
: ldy #4
  jsr @req
  lda #F_X16C
  rtl
@fl:
  lda #F_X16A
  rtl
@req:                               ; the youngest explosion of the frame picks the cell's frame
  pha
  stz fx_ok                         ; (the NMI cell loop has work again)
  lda fx_st,y
  cmp frame
  beq :+
  lda frame
  sta fx_st,y
  pla
  sta fx_req,y
  rts
: pla
  cmp fx_req,y
  bcs :+
  sta fx_req,y
: rts

; NMI (chase, after the slot / medium uploads): the fx cells and the afterburner, line-budgeted
X18_FxStream:
.ifdef NOFX
  rtl
.endif
.ifdef FXPROF
  jsr SS_Line
  sta fxp_a
.endif
  lda b_gfx
  beq :+
  cmp #2
  beq :+
  rtl                               ; sheet rows streaming
: lda fx_bg
  beq :+
  jsr X18_FxHome                    ; a sheet just came back: cells hold their home frames
: A8
  lda #$80
  sta VMAIN
  lda #$01
  sta DMAP0
  lda #$18
  sta BBAD0
  A16
  lda b_gfx
  beq :+
  jsr X18_DadPatch                  ; v1.8: his blink / mouth cells first
: lda js_upd
.ifndef NOSHARE
  beq :+
  jmp @fl
.endif
:
.ifndef NOLAG
  lda ld_last                       ; heavy frame: explosion cells wait (at most CWAIT vblanks)
  cmp #FX_LN
  bcc :+
  lda fx_lw
  cmp #CWAIT
  bcs :+
  inc fx_lw
  jmp @fl
: stz fx_lw
.endif
: A8
  lda #^FxFrames
  sta A1B0
  A16
  lda fx_ok                         ; idle: every cell already holds its home frame
  beq :+
  jmp @fl
: lda frame
  sec
  sbc fx_st
  cmp #20
  bcc :+
  lda frame
  sec
  sbc fx_st+2
  cmp #20
  bcc :+
  lda frame
  sec
  sbc fx_st+4
  cmp #20
  bcc :+
  lda fx_have                       ; no requests for 20 frames: once all are home, go idle
  cmp f:FxHome
  bne :+
  lda fx_have+2
  cmp f:FxHome+2
  bne :+
  lda fx_have+4
  cmp f:FxHome+4
  bne :+
  inc fx_ok
  jmp @fl
: ldy #0
@lp:
.ifdef NOFXC
  jmp @fl
.endif
  tyx
  lda frame                         ; asked for in the last 16 frames: keep it, else back home
  sec
  sbc fx_st,x
  cmp #16
  bcc @act
  lda f:FxHome,x
  bra @w
@act:
  lda fx_req,x
@w:
  cmp fx_have,x
  bne :+
  jmp @nx
:
.ifndef FX60
  pha                               ; cells take turns: A and C on even vblanks, B on odd
  tya
  lsr
  eor nmi_count
  lsr
  pla
  bcc :+
  jmp @nx
:
.endif
  sta x18n_u
  jsr SS_Line
  cmp #31
  bcs @fl
  tyx
  lda x18n_u
  sta fx_have,x
  asl                               ; source = FxFrames + FxAddr[base + frame]
  clc
  adc f:FxIdx,x
  tax
  lda f:FxAddr,x
  sta n_t
  tyx
  lda f:FxTile,x
  asl
  asl
  asl
  asl
  clc
  adc #$6000
  sta n_k
  lda f:FxRow,x
  sta x18n_w
  lda f:FxNRow,x
  tax
: lda n_k
  sta VMADDL
  clc
  adc #16*16
  sta n_k
  lda n_t
  sta A1T0L
  clc
  adc x18n_w
  sta n_t
  lda x18n_w
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
  dex
  bne :-
@nx:
  iny
  iny
  cpy #6
  beq @fl
  jmp @lp
@fl:                                ; afterburner: 16 frames at 60 fps while boosting
.ifdef FXPROF
  jsr SS_Line
  sta fxp_b
.endif
  stz js_upd
  A8
  lda #^FxFrames
  sta A1B0
  A16
  lda boost
  beq @x
.ifndef NOLAG
  lda ld_last                       ; heavy frame: the flame holds its frame
  cmp #FX_LN
  bcs @x
.endif
  lda frame
  lsr                               ; (30 Hz: a new frame every other vblank)
  and #$000F
  cmp fl_have
  beq @x
  sta x18n_u
  jsr SS_Line
  cmp #32
  bcs @x
  lda x18n_u
  sta fl_have
  xba
  lsr                               ; * 128
  clc
  adc #.loword(FxFrames)+FX_F0
  sta n_t
  lda #T_CHASE_FLAME0*16+$6000
  sta VMADDL
  lda n_t
  sta A1T0L
  lda #64
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
  lda #T_CHASE_FLAME0*16+$6000+16*16
  sta VMADDL
  lda n_t
  clc
  adc #64
  sta A1T0L
  lda #64
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
@x:
.ifdef NOBF
  rtl
.endif
  lda b_gfx                         ; boss thrusters (boss sheet resident): 16 frames at 60 fps
  cmp #2
  bne @y
  lda frame
  lsr
  and #$000F
  cmp bf_have
  beq @y
  sta x18n_u
  jsr SS_Line
  cmp #32
  bcs @y
  lda x18n_u
  sta bf_have
  xba
  lsr
  clc
  adc #.loword(FxFrames)+FX_B0
  sta n_t
  lda #T_CHASE_BFLAME0*16+$6000
  sta VMADDL
  lda n_t
  sta A1T0L
  lda #64
  sta DAS0L
  A8
  lda #^FxFrames
  sta A1B0
  lda #1
  sta MDMAEN
  A16
  lda #T_CHASE_BFLAME0*16+$6000+16*16
  sta VMADDL
  lda n_t
  clc
  adc #64
  sta A1T0L
  lda #64
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
@y:
  rtl

; ---------------------------------------------------------------- v1.8 dad: blink, talking mouth, breath, recoil
; Eye (3 states) and mouth (4 states) tile patches stream into his sheet's face cells (assets/dadpatch.bin);
; the mouth follows the voice line's loudness (DadTalk, 60 Hz, from music/dad_voice.wav).
X18_DadVoice:                       ; (boss.s, when the voice line starts)
  lda #1
  sta dv_vt
  rtl

BlinkSeq: .byte 0, 1, 2, 2, 2, 1, 1, 0, 0  ; by dv_bk (counts down 8..1)

X18_DadAnim:                        ; once per built frame (BossColors)
  ; mouth: the voice envelope while he talks; a grimace when a missile hits
  stz dv_mw
  lda dv_vt
  beq @nv
  dec a
  tax
  lda f:DadTalk,x
  and #$00FF
  sta dv_mw
  inc dv_vt
  inx
  cpx #DP_TALK_N
  bcc @nv
  stz dv_vt
@nv:
  lda b_fb
  cmp #3
  bcc :+
  lda dv_mw
  bne :+
  lda #1
  sta dv_mw
: ; eyes: blink every 2.5 - 4.5 s; squeezed shut for a moment when hit
  lda dv_bk
  beq @nb
  dec dv_bk
  bra @eb
@nb:
  dec dv_bt
  bpl @eb
  lda frame
  asl
  asl
  asl
  eor frame
  and #$007F
  clc
  adc #150
  sta dv_bt
  lda #8
  sta dv_bk
@eb:
  ldx dv_bk
  lda f:BlinkSeq,x
  and #$00FF
  sta dv_ew
  lda b_fb
  cmp #3
  bcs @sq
  lda b_atk
  cmp #ATK_SHARD
  beq @br
  lda b_fe
  cmp #5
  bcc @br
  cmp #11
  bcs @br
@sq:
  lda #2
  sta dv_ew
@br:
  ; breath: the chest rises 1 px for ~1.3 s of every 3.2 s
  inc dv_bc
  lda dv_bc
  cmp #192
  bcc :+
  stz dv_bc
  lda #0
: stz dv_br
  cmp #56
  bcc :+
  cmp #136
  bcs :+
  lda #1
  sta dv_br
: rtl

; smooth recoil after a missile hit (replaces the 2-frame shudder); returns A = shudder bits
RecX: .byte 0, 0, 0, 0, <-1, 0, 1, 1, <-1, <-2, 0, 2, 2, 0, 0, 0
RecY: .byte 0, 0, 0, 0, 0, 0, <-1, <-1, <-1, <-1, <-2, <-2, <-3, 0, 0, 0
X18_Recoil:                         ; (both bosses)
  lda b_fb
  cmp #16
  bcc :+
  lda #15
: tax
  lda f:RecX,x
  and #$00FF
  cmp #$80
  bcc :+
  ora #$FF00
: clc
  adc b_sx
  sta b_sx
  lda f:RecY,x
  and #$00FF
  cmp #$80
  bcc :+
  ora #$FF00
: clc
  adc b_sy
  sta b_sy
  lda b_fg                          ; bullet hits: a 1 px flinch
  ora b_fe
  cmp #8
  bcc :+
  cmp #11
  bcs :+
  dec b_sy
: lda b_st
  rtl

; NMI (from X18_FxStream, his sheet resident): face patches, line-budgeted
X18_DadPatch:
.ifdef NODP
  rts
.endif
  lda b_dad
  bne :+
  rts
: lda dv_ew
  cmp dv_eh
  beq @m
  jsr SS_Line
  cmp #26
  bcs @x
  lda dv_ew
  sta dv_eh
  ldx #DP_EYE_N*128
  jsr @mul                          ; A = state * group bytes
  sta x18n_w
  ldx #0
: lda x18n_w
  jsr @cell
  lda x18n_w
  clc
  adc #128
  sta x18n_w
  inx
  inx
  cpx #DP_EYE_N*2
  bcc :-
@m:
  lda dv_mw
  cmp dv_mh
  beq @x
  jsr SS_Line
  cmp #28
  bcs @x
  lda dv_mw
  sta dv_mh
  ldx #DP_MOUTH_N*128
  jsr @mul
  clc
  adc #3*DP_EYE_N*128
  sta x18n_w
  ldx #DP_EYE_N*2                   ; (cell index offset into the joined tile list)
: lda x18n_w
  jsr @cell
  lda x18n_w
  clc
  adc #128
  sta x18n_w
  inx
  inx
  cpx #(DP_EYE_N+DP_MOUTH_N)*2
  bcc :-
@x:
  rts
@mul:                               ; A * X -> A
  stx x18n_u
  tax
  lda #0
  cpx #0
  beq :++
: clc
  adc x18n_u
  dex
  bne :-
: rts
@cell:                              ; A = source offset, X = tile list index (x2): one 16x16 cell
  clc
  adc #.loword(DadPatch)
  sta n_t
  lda f:DpEyeTile,x
  asl
  asl
  asl
  asl
  clc
  adc #$6000
  sta VMADDL
  clc
  adc #16*16
  sta n_k
  lda n_t
  sta A1T0L
  lda #64
  sta DAS0L
  A8
  lda #^DadPatch
  sta A1B0
  lda #1
  sta MDMAEN
  A16
  lda n_k
  sta VMADDL
  lda n_t
  clc
  adc #64
  sta A1T0L
  lda #64
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
  rts

.segment "ANIMB0"
MedFrames: .incbin "../assets/medframes.bin"
.segment "ANIMB1"
FxFrames: .incbin "../assets/fxframes.bin"
.segment "ANIMB2"
DadPatch: .incbin "../assets/dadpatch.bin"
.segment "XCODE"


.segment "CODE"
