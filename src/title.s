; =====================================================================
; SUPER SKY FURY -- title screen + start menu (options, credits, sound test)
;
; Screen: lines 0-87 Mode 1 (sky gradient HDMA on colour 0, logo + "DEVELOPED BY" on BG2),
;         lines 88-143 Mode 7 ocean band (rotating, scrolling; jets fly over it, OBJ prio 2),
;         lines 144-223 Mode 1 opaque BG2 panel (menu text; hides the jets, cursor jet = OBJ prio 3).
; BGMODE / TM switch per line by HDMA (ch5 / ch4), colour 0 by HDMA ch6.  The OPTIONS / CREDITS
; pages switch the band to Mode 1 and extend the panel up to row 11.
; BG2 map lives in WRAM $7F:8000 and is DMA'd in the NMI when dirty.
; Starting a game: InitRegs + ClearMem (options + SPC state kept), then the original boot path,
; so NORMAL plays exactly like before.
; =====================================================================
TMAP     = $7F8000
TS_FADEIN = 0
TS_PUSH   = 1
TS_MENU   = 2
TS_OPT    = 3
TS_CRED   = 4
TS_FADEOUT = 5
T_IDLE    = 20*60               ; menu idle -> back to PUSH START
PAL4A = (4 << 10) | $2000 | TF_PANEL      ; panel text, normal (yellow)
PAL5A = (5 << 10) | $2000 | TF_PANEL      ; panel text, credits (blue)
PAL6A = (6 << 10) | $2000 | TF_PANEL      ; panel text, selected (white/red)
PAL3S = (3 << 10) | $2000 | TF_SKY        ; sky text (gold, transparent)
SOLID = (4 << 10) | $2000 | T_SOLID
EDGE  = (4 << 10) | $2000 | T_EDGE
T_CURSOR = T_OVER_DOT                     ; the 32x32 cell the cursor jet is written over
NSND = 30                                 ; sound test entries

.segment "ZEROPAGE"
tptr:     .res 4

.segment "BSS"
ti_on:    .res 2            ; 1 while the title runs (NMI branch)
ti_bgo:   .res 12           ; v1.5: HDMA ch 3 BG1 scroll: 0 over the silhouette lines, Mode 7 values below
ti_shn:   .res 24           ; v1.5: HDMA ch 7 logo shine band (COLDATA)
ti_st:    .res 2            ; state
ti_t:     .res 2            ; frames in state
ti_fr:    .res 2            ; frame counter
ti_sel:   .res 2            ; menu / options row
ti_idle:  .res 2
ti_lock:  .res 2            ; ignore input for n frames
ti_dirty: .res 2            ; BG2 map needs a DMA
ti_page:  .res 2            ; 0 title band, 1 page (options / credits)
ti_ang:   .res 2            ; ocean rotation (8.8 of 256 steps)
ti_wx:    .res 4            ; ocean centre, 16.16
ti_wy:    .res 4
ti_ma:    .res 2
ti_mb:    .res 2
ti_mc:    .res 2
ti_md:    .res 2
ti_m7x:   .res 2
ti_m7y:   .res 2
ti_hofs:  .res 2
ti_vofs:  .res 2
ti_cy:    .res 2            ; cursor y (smoothed), target
ti_cyt:   .res 2
ti_cx:    .res 2
ti_fy:    .res 2            ; jet formation y (8.8), x, wait
ti_fx:    .res 2
ti_fw:    .res 2
ti_ey:    .res 2            ; enemy pair y (8.8), x
ti_ex:    .res 2
ti_mus:   .res 2            ; music test selection 0-3
ti_snd:   .res 2            ; sound test selection 0..NSND-1
ti_jing:  .res 2            ; CLEAR test: waiting for the boss image, then the jingle
ti_redo:  .res 2            ; mono changed: re-send the image (+ flag) when idle
opt_diff: .res 2            ; 0 easy, 1 normal, 2 hard
opt_mono: .res 2            ; 0 stereo, 1 mono (sent to ARAM $004F after every image upload)
d_lives:  .res 2            ; difficulty-derived game parameters (NORMAL = boss v2 values)
d_hpb:    .res 2
d_hpm:    .res 2
d_fire:   .res 2

.segment "CODE"
; ---------------------------------------------------------------- difficulty
ApplyDiff:
  lda opt_diff
  asl
  tax
  lda f:DiffLives,x
  sta d_lives
  lda f:DiffHpb,x
  sta d_hpb
  lda f:DiffHpm,x
  sta d_hpm
  lda f:DiffFire,x
  sta d_fire
  rts

; ---------------------------------------------------------------- enter / leave
; keeps options + SPC state across a full RAM clear (stack untouched by ClearMem)
.macro KEEP_CLEAR
  lda opt_diff
  pha
  lda opt_mono
  pha
  lda mu_img
  pha
  lda mu_dead
  pha
  jsr InitRegs
  AXY16
  jsr ClearMem
  AXY16
  pla
  sta mu_dead
  pla
  sta mu_img
  pla
  sta opt_mono
  pla
  sta opt_diff
  jsr ApplyDiff
.endmacro

; wait (pumping the SPC upload) until no image transfer is running, then blank + NMI off
TiQuiesce:
@w:
  lda mu_st
  beq @ok
  lda last_frame
  cmp nmi_count
  beq :+
  lda nmi_count
  sta last_frame
  jsr MusicFrame            ; IPL timeout
: jsr MusicPump
  bra @w
@ok:
  ; wait for vblank, then force blank
  lda nmi_count
: cmp nmi_count
  beq :-
  A8
  lda #$80
  sta INIDISP
  stz NMITIMEN
  stz HDMAEN
  A16
  rts

; blocking SPC image swap (force blank, NMI off): A = image
TiSwapNow:
  sta mu_want
  stz t5
  stz t6
@l:
  lda mu_dead
  bne @r
  jsr MusicPump
  lda mu_st
  bne :+
  lda mu_img
  cmp mu_want
  beq @r
  bra @l
: cmp #1                    ; waiting for the IPL: time out after ~3 s
  bne @l
  inc t5
  bne @l
  inc t6
  lda t6
  cmp #4
  bcc @l
  stz mu_st
  lda #1
  sta mu_dead
@r:
  rts

; game over -> title
GoTitle:
  AXY16
  jsr TiQuiesce
  KEEP_CLEAR
  ldx #$1FFF
  txs
  ; fall into TitleEnter

TitleEnter:
  AXY16
  lda #1
  sta ti_on
  jsr TitleLoad
  lda #MU_TITLE
  jsr TiSwapNow             ; title music ready before the fade-in
  stz ti_st
  stz ti_t
  lda #30
  sta ti_lock
  lda #$0200
  sta ti_wx+2
  sta ti_wy+2
  lda #148*256
  sta ti_fy
  lda #96
  sta ti_fx
  lda #200*256
  sta ti_ey
  lda #160
  sta ti_cy
  sta ti_cyt
  stz inidisp
  lda nmi_count
  sta last_frame
  A8
  lda RDNMI
  lda #$81
  sta NMITIMEN
  A16
  jmp TitleLoop

; START GAME: fade done -> clean RAM -> the original boot path
StartGame:
  AXY16
  jsr TiQuiesce
  KEEP_CLEAR
  ldx #$1FFF
  txs
  lda #MU_FIELD
  jsr TiSwapNow             ; stage music running from frame 0, like the original boot
  jsr LoadStatic
  jsr InitGame
  jsr LoadView
  jsr PauseText
  jmp MainLoop

; ---------------------------------------------------------------- VRAM / CGRAM / registers (force blank)
TitleLoad:
  jsr LoadStatic            ; palette, Mode 7 world, registers
  DMA_VRAM TitleTiles, $4000, TITLE_NTILES*32, $80, $18, $01
  DMA_VRAM ZeroByte, $5800, 2048, $80, $18, $09     ; BG1 map for the Mode 1 lines: blank
  DMA_VRAM TitleBossMap, $5800, 704, $80, $18, $01  ; v1.5: boss silhouette (rows 0-10)
  DMA_VRAM ObjOver, $6000, 16384, $80, $18, $01
  DMA_VRAM TitleCursor,     $6000+T_CURSOR*16,      128, $80, $18, $01
  DMA_VRAM (TitleCursor+128), $6000+T_CURSOR*16+256,  128, $80, $18, $01
  DMA_VRAM (TitleCursor+256), $6000+T_CURSOR*16+512,  128, $80, $18, $01
  DMA_VRAM (TitleCursor+384), $6000+T_CURSOR*16+768,  128, $80, $18, $01
  ; title palettes 3-6 (CGRAM 48-111)
  A8
  lda #48
  sta CGADD
  stz DMAP0
  lda #$22
  sta BBAD0
  lda #^TitlePal
  sta A1B0
  A16
  lda #.loword(TitlePal)
  sta A1T0L
  lda #128
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  lda #$A3
  sta OBSEL                 ; 32x32 / 64x64, tiles at $6000
  stz TS
  stz CGWSEL
  lda #$02
  sta CGADSUB               ; v1.5: BG2 + fixed colour (logo shine band, ch 7)
  stz M7SEL
  A16
  ; hide all sprites
  ldx #0
: lda #$E000
  sta oam_lo,x
  stz oam_lo+2,x
  inx
  inx
  inx
  inx
  cpx #512
  bne :-
  ldx #30
: stz oam_hi,x
  dex
  dex
  bpl :-
  stz ti_page
  jsr DrawTitle
  jsr MapDma
  jsr TiHdma
  lda #$00F8                ; v1.5: + ch 3 (BG1 scroll split), ch 7 (shine)
  sta hdma_mask
  jsr TitleAnim
  jsr TiRegs
  rts

; HDMA tables for the current page
TiHdma:
  lda ti_page
  bne @p
  HDMA_DIRECT 5, $00, <BGMODE, md_title
  HDMA_DIRECT 4, $00, <TM, tm_title
  bra @c
@p:
  HDMA_DIRECT 5, $00, <BGMODE, md_page
  HDMA_DIRECT 4, $00, <TM, tm_page
@c:
  HDMA_DIRECT 6, $03, <CGADD, cg_title
  HDMA_DIRECT 3, $03, <BG1HOFS, ti_bgo
  HDMA_DIRECT 7, $02, <COLDATA, ti_shn
  rts

; whole BG2 map -> VRAM $5C00 (call in vblank / force blank)
MapDma:
  A8
  lda #$80
  sta VMAIN
  A16
  lda #$5C00
  sta VMADDL
  lda #.loword(TMAP)
  sta A1T0L
  lda #2048
  sta DAS0L
  A8
  lda #^TMAP
  sta A1B0
  lda #$01
  sta DMAP0
  lda #$18
  sta BBAD0
  lda #1
  sta MDMAEN
  A16
  stz ti_dirty
  rts

; Mode 7 matrix + scroll (also used once at load)
TiRegs:
  ; v1.5: BG1 scroll split (silhouette fixed, Mode 7 below line 88) + logo shine band
  lda #88
  sta ti_bgo
  stz ti_bgo+1
  stz ti_bgo+3
  lda ti_hofs
  sta ti_bgo+6
  lda ti_vofs
  sta ti_bgo+8
  A8
  lda #1
  sta ti_bgo+5
  stz ti_bgo+10
  A16
  lda nmi_count
  and #$007F
  sec
  sbc #12
  bpl :+
  lda #100
: cmp #84
  bcc :+
  lda #100
: ldx ti_page
  beq :+
  lda #100
: cmp #1
  bcs :+
  lda #1
: A8
  sta ti_shn
  lda #$E0
  sta ti_shn+1
  sta ti_shn+2
  lda #$88
  sta ti_shn+3
  ldx #0
: lda f:ShineV,x
  sta ti_shn+4,x
  inx
  cpx #16
  bne :-
  lda #1
  sta ti_shn+20
  lda #$E0
  sta ti_shn+21
  sta ti_shn+22
  stz ti_shn+23
  A16
  A8
  lda ti_m7x
  sta M7X
  lda ti_m7x+1
  sta M7X
  lda ti_m7y
  sta M7Y
  lda ti_m7y+1
  sta M7Y
  lda ti_hofs
  sta BG1HOFS
  lda ti_hofs+1
  sta BG1HOFS
  lda ti_vofs
  sta BG1VOFS
  lda ti_vofs+1
  sta BG1VOFS
  lda ti_ma
  sta M7A
  lda ti_ma+1
  sta M7A
  lda ti_mb
  sta M7B
  lda ti_mb+1
  sta M7B
  lda ti_mc
  sta M7C
  lda ti_mc+1
  sta M7C
  lda ti_md
  sta M7D
  lda ti_md+1
  sta M7D
  A16
  rts

ShineV: .byte $E3,$E3,$E7,$E7,$EB,$EB,$EE,$EE,$EE,$EE,$EA,$EA,$E6,$E6,$E2,$E2

; ---------------------------------------------------------------- NMI part (called from NmiFast, A16)
TitleNmi:
  lda c_flag
  beq @r
  A8
  stz OAMADDL
  stz OAMADDH
  stz DMAP0
  lda #<OAMDATA
  sta BBAD0
  stz A1B0
  A16
  lda #.loword(oam_lo)
  sta A1T0L
  lda #544
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
  jsr TiRegs
  lda ti_dirty
  beq :+
  jsr MapDma
  jsr TiHdma
: stz c_flag
@r:
  rts

; ---------------------------------------------------------------- main loop
TitleLoop:
  AXY16
@w:
  lda last_frame
  cmp nmi_count
  bne @go
  jsr MusicPump
  bra @w
@go:
  lda nmi_count
  sta last_frame
  jsr ReadJoy
  jsr MusicFrame
  jsr TiMusic
  inc ti_fr
  inc ti_t
  lda ti_lock
  beq :+
  dec ti_lock
  stz joy_new
: jsr TitleStep
  jsr TitleAnim
  lda #1
  sta c_flag
  bra TitleLoop

; music housekeeping: mono re-send, CLEAR jingle
TiMusic:
  lda mu_st
  bne @r
  lda ti_redo
  beq :+
  stz ti_redo
  lda #$FE                  ; force a re-upload of the running image (+ the mono flag)
  sta mu_img
  rts
: lda ti_jing
  beq @r
  lda mu_img
  cmp #MU_BOSS
  bne @r
  inc ti_jing
  lda ti_jing
  cmp #20                   ; let the boss song start, then turn it into the jingle
  bcc @r
  stz ti_jing
  lda #4
  sta mu_ff
@r:
  rts

; ---------------------------------------------------------------- state machine
TitleStep:
  lda ti_st
  asl
  tax
  jmp (.loword(TiStates),x)
TiStates: .word .loword(StFadeIn), .loword(StPush), .loword(StMenu), .loword(StOpt), .loword(StCred), .loword(StFadeOut)

StFadeIn:
  lda ti_t
  lsr
  cmp #15
  bcc :+
  lda #15
  sta inidisp
  lda #TS_PUSH
  jmp SetState
: sta inidisp
  lda joy_new
  and #KEY_START|KEY_A
  beq :+
  lda #15
  sta inidisp
  lda #TS_PUSH
  jmp SetState
: rts

StPush:
  lda ti_t
  and #31
  bne :+
  jsr DrawTitle             ; blink PUSH START
: lda joy_new
  and #KEY_START|KEY_A
  beq @r
  lda #SFXB_MENU_OK
  jsr TiSfxB
  stz ti_sel
  lda #TS_MENU
  jmp SetState
@r:
  rts

StMenu:
  inc ti_idle
  lda ti_idle
  cmp #T_IDLE
  bcc :+
  lda #TS_PUSH
  jmp SetState
: lda joy_new
  beq @r
  stz ti_idle
  bit #KEY_UP
  beq :+
  lda ti_sel
  beq @r
  dec ti_sel
  lda #SFXB_MENU_L
  jsr TiSfxB
  jmp DrawTitle
: bit #KEY_DOWN
  beq :+
  lda ti_sel
  cmp #2
  bcs @r
  inc ti_sel
  lda #SFXB_MENU_R
  jsr TiSfxB
  jmp DrawTitle
: bit #KEY_B
  beq :+
  lda #TS_PUSH
  jmp SetState
: and #KEY_START|KEY_A
  beq @r
  lda #SFXB_MENU_OK
  jsr TiSfxB
  lda ti_sel
  bne :+
  lda #TS_FADEOUT
  jmp SetState
: cmp #1
  bne :+
  stz ti_sel
  lda #TS_OPT
  jmp SetState
: lda #TS_CRED
  jmp SetState
@r:
  rts

StOpt:
  lda joy_new
  bne :+
  rts
: bit #KEY_UP
  beq :+
  lda ti_sel
  beq @r0
  dec ti_sel
  lda #SFXB_MENU_L
  jsr TiSfxB
  jmp DrawTitle
@r0:
  rts
: bit #KEY_DOWN
  beq :+
  lda ti_sel
  cmp #4
  bcs @r0
  inc ti_sel
  lda #SFXB_MENU_R
  jsr TiSfxB
  jmp DrawTitle
: bit #KEY_B
  beq :+
  jmp OptBack
: bit #KEY_LEFT
  beq :+
  lda #$FFFF
  jmp OptChange
: bit #KEY_RIGHT
  beq :+
  lda #1
  jmp OptChange
: and #KEY_START|KEY_A
  beq @r0
  lda ti_sel
  cmp #2
  bne :+
  jmp PlayMusic
: cmp #3
  bne :+
  jmp PlaySnd
: cmp #4
  bne @r0
OptBack:
  lda #SFXB_MENU_OK
  jsr TiSfxB
  lda #MU_TITLE
  sta mu_want
  stz ti_jing
  lda #1
  sta ti_sel
  lda #TS_MENU
  jmp SetState

; A = +1 / -1 on the selected option row
OptChange:
  sta t0
  ldx ti_sel
  bne @n1
  lda opt_diff              ; difficulty 0..2 (clamped)
  clc
  adc t0
  bmi @r
  cmp #3
  bcs @r
  sta opt_diff
  bra @snd
@n1:
  cpx #1
  bne @n2
  lda opt_mono
  eor #1
  sta opt_mono
  lda #1
  sta ti_redo
  bra @snd
@n2:
  cpx #2
  bne @n3
  lda ti_mus
  clc
  adc t0
  and #3
  sta ti_mus
  bra @snd
@n3:
  cpx #3
  bne @r
  lda ti_snd
  clc
  adc t0
  bpl :+
  lda #NSND-1
: cmp #NSND
  bcc :+
  lda #0
: sta ti_snd
@snd:
  lda t0
  bmi :+
  lda #SFXB_MENU_R
  bra :++
: lda #SFXB_MENU_L
: jsr TiSfxB
  jmp DrawTitle
@r:
  rts

PlayMusic:
  stz ti_jing
  lda ti_mus
  asl
  tax
  lda f:MusImg,x
  sta mu_want
  lda mu_st
  bne :+
  lda #$FE                  ; restart even when that image is already playing
  sta mu_img
: lda ti_mus
  cmp #3
  bne :+
  lda #1
  sta ti_jing
: rts

PlaySnd:
  lda ti_snd
  asl
  tax
  lda f:SndTab,x
  cmp #$100
  bcs :+
  jmp TiSfxA
: and #$00FF
  jmp TiSfxB

StCred:
  lda joy_new
  and #KEY_START|KEY_A|KEY_B
  beq :+
  lda #SFXB_MENU_OK
  jsr TiSfxB
  lda #2
  sta ti_sel
  lda #TS_MENU
  jmp SetState
: rts

StFadeOut:
  lda ti_t
  lsr
  cmp #16
  bcs :+
  eor #15
  sta inidisp
  rts
: stz inidisp
  jmp StartGame

SetState:
  sta ti_st
  stz ti_t
  stz ti_idle
  ldx #0
  cmp #TS_OPT
  bcc :+
  cmp #TS_FADEOUT
  bcs :+
  ldx #1
: stx ti_page
  jmp DrawTitle

; menu SFX on channel B / sound test on A (fixed position: their own pans are in the streams)
TiSfxB:
  pha
  stz sfxb_t
  stz sfx_nfx
  lda #4
  sta sfx_nfz
  lda #K_FIX
  sta sfx_nk
  pla
  ldx #1
  ldy #30
  jmp SfxB
TiSfxA:
  pha
  stz sfxa_t
  stz sfx_nfx
  lda #4
  sta sfx_nfz
  lda #K_FIX
  sta sfx_nk
  pla
  ldx #1
  ldy #30
  jmp SfxA

; ---------------------------------------------------------------- map drawing (WRAM)
; fill words [x, y) of TMAP with A
TiFill:
  sta t0
: lda t0
  sta f:TMAP,x
  inx
  inx
  sty t1
  cpx t1
  bcc :-
  rts

; put string (label loword in Y) at map row A (centred), attr base in t2
PutC:
  sta t3
  sty tptr
  lda #^TT_PUSH
  sta tptr+2
  lda [tptr]
  and #$00FF
  sta t4                    ; length
  eor #$FFFF
  sec
  adc #32
  lsr                       ; col = (32 - len) / 2
  bra PutRC
; put string at row A, column X
PutAt:
  sta t3
  sty tptr
  lda #^TT_PUSH
  sta tptr+2
  lda [tptr]
  and #$00FF
  sta t4
  txa
PutRC:
  sta t5
  lda t3
  asl
  asl
  asl
  asl
  asl
  clc
  adc t5
  asl
  tax
  ldy #1
@l:
  lda [tptr],y
  and #$00FF
  clc
  adc t2
  sta f:TMAP,x
  inx
  inx
  cpy t4
  bcs @d
  iny
  bra @l
@d:
  rts

; panel colour attr for menu row n (Y = row index): selected -> PAL6A
SelAttr:
  lda #PAL4A
  cpy ti_sel
  bne :+
  lda #PAL6A
: sta t2
  rts

DrawTitle:
  lda #1
  sta ti_dirty
  ; logo rows 0..LOGO_ROWS-1
  ldx #0
: lda f:TitleLogoMap,x
  sta f:TMAP,x
  inx
  inx
  cpx #LOGO_ROWS*64
  bne :-
  ; rows LOGO_ROWS..17 transparent (sky / ocean band) or panel (pages)
  lda ti_page
  beq @band
  lda #0
  ldy #11*64
  jsr TiFill
  lda #EDGE
  ldy #12*64
  jsr TiFill
  lda #SOLID
  ldy #2048
  jsr TiFill
  bra @text
@band:
  lda #0
  ldy #18*64
  jsr TiFill
  lda #EDGE
  ldy #19*64
  jsr TiFill
  lda #SOLID
  ldy #2048
  jsr TiFill
@text:
  lda #PAL3S
  sta t2
  lda #LOGO_ROWS
  ldy #.loword(TS_DEV)
  jsr PutC
  lda ti_st
  cmp #TS_OPT
  bne :+
  jmp DrawOpt
: cmp #TS_CRED
  bne :+
  jmp DrawCred
: lda #PAL5A
  sta t2
  lda #26
  ldy #.loword(TT_COPY)
  jsr PutC
  lda ti_st
  cmp #TS_MENU
  beq @menu
  cmp #TS_FADEOUT
  beq @menu
  lda ti_fr
  and #32
  bne @r
  lda #PAL4A
  sta t2
  lda #22
  ldy #.loword(TT_PUSH)
  jsr PutC
@r:
  lda #300
  sta ti_cx                 ; cursor off screen
  rts
@menu:
  ldy #0
  jsr SelAttr
  lda #20
  ldy #.loword(TT_START)
  jsr PutC
  ldy #1
  jsr SelAttr
  lda #22
  ldy #.loword(TT_OPTIONS)
  jsr PutC
  ldy #2
  jsr SelAttr
  lda #24
  ldy #.loword(TT_CREDITS)
  jsr PutC
  lda ti_sel
  asl
  clc
  adc #20
  jsr CurRow
  lda #58                   ; jet just left of "START GAME" (col 11)
  sta ti_cx
  rts

; cursor target from map row A
CurRow:
  asl
  asl
  asl
  sec
  sbc #12
  sta ti_cyt
  rts

DrawOpt:
  lda #PAL6A
  sta t2
  lda #13
  ldy #.loword(TT_OPTHEAD)
  jsr PutC
  ; labels (col 3) + values (col 18)
  ldy #0
  jsr SelAttr
  lda #15
  ldx #3
  ldy #.loword(TT_DIFF)
  jsr PutAt
  lda opt_diff
  asl
  tax
  lda f:DiffNames,x
  tay
  lda #15
  jsr PutVal
  ldy #1
  jsr SelAttr
  lda #17
  ldx #3
  ldy #.loword(TT_SOUND)
  jsr PutAt
  ldy #.loword(TT_STEREO)
  lda opt_mono
  beq :+
  ldy #.loword(TT_MONO)
: lda #17
  jsr PutVal
  ldy #2
  jsr SelAttr
  lda #19
  ldx #3
  ldy #.loword(TT_MUSIC)
  jsr PutAt
  lda ti_mus
  asl
  tax
  lda f:MusNames,x
  tay
  lda #19
  jsr PutVal
  ldy #3
  jsr SelAttr
  lda #21
  ldx #3
  ldy #.loword(TT_SFX)
  jsr PutAt
  jsr SndNum
  ldy #4
  jsr SelAttr
  lda #23
  ldx #3
  ldy #.loword(TT_EXIT)
  jsr PutAt
  lda #PAL5A
  sta t2
  lda #25
  ldy #.loword(TT_HINT1)
  jsr PutC
  lda #26
  ldy #.loword(TT_HINT2)
  jsr PutC
  lda ti_sel
  asl
  clc
  adc #15
  jsr CurRow
  lda #$FFFC                ; jet just left of col 3
  sta ti_cx
  rts

; value string Y at row A, col 18, with < > arrows at cols 17 / 26
PutVal:
  pha
  ldx #18
  jsr PutAt
  pla
  asl
  asl
  asl
  asl
  asl
  clc
  adc #17
  asl
  tax
  lda t2
  clc
  adc #CH_LT
  sta f:TMAP,x
  lda t2
  clc
  adc #CH_GT
  sta f:TMAP+18,x
  rts

; sound test number (01..NSND) at row 21, col 21-22, arrows
SndNum:
  lda #21*32+17
  asl
  tax
  lda t2
  clc
  adc #CH_LT
  sta f:TMAP,x
  lda t2
  clc
  adc #CH_GT
  sta f:TMAP+18,x
  lda ti_snd
  inc a
  ldy #0
: cmp #10
  bcc :+
  sbc #10
  iny
  bra :-
: clc
  adc #1                    ; font index of '0' = 1
  adc t2
  sta f:TMAP+10,x
  tya
  clc
  adc #1
  adc t2
  sta f:TMAP+8,x
  rts

DrawCred:
  lda #PAL6A
  sta t2
  lda #13
  ldy #.loword(TT_CREDHEAD)
  jsr PutC
  lda #PAL4A
  sta t2
  lda #15
  ldy #.loword(TT_C1)
  jsr PutC
  lda #PAL5A
  sta t2
  lda #16
  ldy #.loword(TT_C2)
  jsr PutC
  lda #PAL4A
  sta t2
  lda #18
  ldy #.loword(TT_C3)
  jsr PutC
  lda #PAL5A
  sta t2
  lda #19
  ldy #.loword(TT_C4)
  jsr PutC
  lda #PAL4A
  sta t2
  lda #21
  ldy #.loword(TT_C5)
  jsr PutC
  lda #PAL5A
  sta t2
  lda #22
  ldy #.loword(TT_C6)
  jsr PutC
  lda #24
  ldy #.loword(TT_COPY)
  jsr PutC
  lda #PAL6A
  sta t2
  lda #26
  ldy #.loword(TT_C7)
  jsr PutC
  lda #300
  sta ti_cx
  rts

; ---------------------------------------------------------------- animation: ocean + jets + cursor
TitleAnim:
  ; rotation
  lda ti_ang
  clc
  adc #$0018
  sta ti_ang
  xba
  and #$00FF
  asl
  tax
  lda f:TiSin,x            ; sin
  sta t0
  txa
  clc
  adc #128                  ; +64 steps = cos
  and #$01FF
  tax
  lda f:TiSin,x
  sta t1                    ; cos
  ; scale 3/4 (closer to the waves)
  lda t1
  jsr Sc34
  sta ti_ma
  sta ti_md
  lda t0
  jsr Sc34
  sta ti_mb
  eor #$FFFF
  inc a
  sta ti_mc
  ; fly forward: centre -= (sin, cos) * 0.75 px
  lda ti_mb
  jsr SxW
  lda ti_wx
  sec
  sbc t2
  sta ti_wx
  lda ti_wx+2
  sbc t3
  sta ti_wx+2
  lda ti_md
  jsr SxW
  lda ti_wy
  sec
  sbc t2
  sta ti_wy
  lda ti_wy+2
  sbc t3
  sta ti_wy+2
  lda ti_wx+2
  and #$03FF
  sta ti_wx+2
  sta ti_m7x
  sec
  sbc #128
  and #$1FFF
  sta ti_hofs
  lda ti_wy+2
  and #$03FF
  sta ti_wy+2
  sta ti_m7y
  sec
  sbc #116
  and #$1FFF
  sta ti_vofs
  ; sprites
  ldx #0
  lda ti_page
  beq :+
  jmp @nojets
: ; jet formation flying up the band
  lda ti_fw
  beq @fly
  dec ti_fw
  bne @fhide
  lda #148*256
  sta ti_fy
  jsr Rand
  and #$007F
  clc
  adc #56
  sta ti_fx
@fhide:
  lda #$E0
  sta t4
  bra @fput
@fly:
  lda ti_fy
  sec
  sbc #$0180
  sta ti_fy
  xba
  and #$00FF
  sta t4
  cmp #40
  bcs @fput
  lda #150
  sta ti_fw
  lda #$E0
  sta t4
@fput:
  ; leader + 2 wingmen
  lda ti_fx
  sta t5
  lda #T_OVER_JET0
  sta t6
  lda #$20                  ; prio 2, palette 0
  sta t7
  jsr PutJet
  lda ti_fx
  sec
  sbc #30
  sta t5
  lda t4
  cmp #$E0
  beq :+
  clc
  adc #22
: sta t4
  jsr PutJet
  lda ti_fx
  clc
  adc #30
  sta t5
  jsr PutJet
  ; enemy pair diving the other way
  lda ti_ey
  clc
  adc #$0200
  cmp #220*256
  bcc :+
  jsr Rand
  and #$007F
  clc
  adc #64
  sta ti_ex
  lda #20*256
: sta ti_ey
  xba
  and #$00FF
  cmp #160
  bcc :+
  lda #$E0
: cmp #50
  bcs :+
  lda #$E0
: sta t4
  lda ti_ex
  sta t5
  lda #T_OVER_TOP0
  sta t6
  lda #$A6                  ; v-flip (nose down), prio 2, palette 3 (enemy colours)
  sta t7
  jsr PutJet
  lda ti_ex
  clc
  adc #40
  sta t5
  lda t4
  cmp #$E0
  beq :+
  sec
  sbc #16
: sta t4
  jsr PutJet
@nojets:
  ; cursor jet (prio 3), bobbing left/right; smoothed vertical move
  lda ti_cyt
  sec
  sbc ti_cy
  beq @cy
  cmp #$8000
  ror
  bne :+
  lda ti_cyt
  sec
  sbc ti_cy
: clc
  adc ti_cy
  sta ti_cy
@cy:
  lda ti_cy
  sta t4
  lda ti_fr
  asl
  asl
  asl
  and #$01FE
  tax
  lda f:TiSin,x
  cmp #$8000
  ror
  cmp #$8000
  ror
  cmp #$8000
  ror
  cmp #$8000
  ror
  cmp #$8000
  ror
  cmp #$8000
  ror                       ; -4..+4
  clc
  adc ti_cx
  sta t5
  lda #T_CURSOR
  sta t6
  lda #$30                  ; prio 3, palette 0
  sta t7
  jsr PutJet
  ; hide the remaining title slots
: cpx #8*4
  bcs :+
  lda #$E000
  sta oam_lo,x
  inx
  inx
  inx
  inx
  bra :-
: ; high table for slots 0-7: x bit 8 from ti_hx (built by PutJet)
  lda ti_hx
  sta oam_hi
  stz ti_hx
  stz oam_idx_ti
  rts

; one 32x32 sprite: x t5 (signed), y t4 (low byte), tile t6, attr t7; slot index in oam_idx_ti
PutJet:
  ldx oam_idx_ti
  A8
  lda t5
  sta oam_lo,x
  lda t4
  sta oam_lo+1,x
  lda t6
  sta oam_lo+2,x
  lda t6+1
  and #1
  ora t7
  sta oam_lo+3,x
  A16
  lda t5
  and #$0100
  beq @nx
  txa                       ; slot = x / 4 -> high-table bit (slot * 2)
  lsr
  tay
  lda #1
@sh:
  dey
  bmi @set
  asl
  bra @sh
@set:
  tsb ti_hx
@nx:
  inx
  inx
  inx
  inx
  stx oam_idx_ti
  rts

; A = 8.8 matrix value * 3/4 (signed)
Sc34:
  sta t2
  asl
  clc
  adc t2
  cmp #$8000
  ror
  cmp #$8000
  ror
  rts
; A = signed 8.8 -> t3:t2 = A * 0.75 as 16.16 (sign extended)
SxW:
  jsr Sc34
  pha
  xba
  and #$FF00
  sta t2
  pla
  xba
  and #$00FF
  cmp #$0080
  bcc :+
  ora #$FF00
: sta t3
  rts

.segment "BSS"
ti_hx:      .res 2
oam_idx_ti: .res 2

.segment "RODATA"
DiffLives: .word 7, LIVES0, 3
DiffHpb:   .word 110, HP_BASE, 200
DiffHpm:   .word 200, HP_MAX, 330
DiffFire:  .word 150, 110, 80
MusImg:    .word MU_TITLE, MU_FIELD, MU_BOSS, MU_BOSS
DiffNames: .word .loword(TT_EASY), .loword(TT_NORMAL), .loword(TT_HARD)
MusNames:  .word .loword(TT_M0), .loword(TT_M1), .loword(TT_M2), .loword(TT_M3)
; sound test: < $100 = channel A id, $1xx = channel B id
SndTab:    .word 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
           .word $101, $102, $103, $104, $105, $106, $10C
           .word 11, 12, 13, 14, 15
           .word $107, $108, $109, $10A, $10B
           .word $10D, $10E, $10F

.segment "BANK6"
.include "../assets/title.inc"
TitleTiles:  .incbin "../assets/title_tiles.bin"
TitleCursor: .incbin "../assets/title_cursor.bin"

.segment "CODE"
