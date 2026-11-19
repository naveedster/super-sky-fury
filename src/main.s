; =====================================================================
;  SNES FLY  -  a Mode 7 flight demo for real Super Nintendo hardware
;  LoROM / FastROM, no enhancement chip.  Assemble with ca65 (cc65).
; =====================================================================
.p816
.include "snes.inc"
.include "../assets/symbols.inc"

VIEW_CHASE = 0
VIEW_OVER  = 1
VIEW_COCK  = 2
CAMBACK    = 40          ; chase camera distance behind jet (px)
NHIST      = 8           ; overhead contrail history length (a point every 5 frames)
MSZ        = NE_CH*4     ; bytes per matrix data array (4 bytes per entry)
VSZ        = NE_CH*2     ; bytes per VOFS data array
TBL_MAXLATE = 2          ; ...but never more than this many frames running
TBL_BUDGET = 189         ; frame load (lines) above which a table rebuild waits a frame
ITSZ       = 164         ; bytes per indirect HDMA table

.macro CHK n
.ifdef DBGMARK
  php
  sep #$20
  pha
  lda #n+1
  sta f:$7E1E80
  pla
  plp
.endif
.ifdef PROFX
  php
  pha
  phx
  ldx #n*2
  jsr ProfAt
  plx
  pla
  plp
.endif
.endmacro

.macro ASR4
  cmp #$8000
  ror
  cmp #$8000
  ror
  cmp #$8000
  ror
  cmp #$8000
  ror
.endmacro

; one hardware 8x8 product for RotScale: dest = sign(v^sgn) * ((|v| * o) >> 7), |v| <= 767
; Y = |v|, X = (|v| >> 8) * 2, m_sign = v
.macro RPROD o8, hitab, sgn, dest
  tya
  and #$00FF
  ora o8
  sta WRMPYA                ; 16-bit store: WRMPYA = lo, WRMPYB = o -> multiply starts
  lda hitab,x               ; high byte contribution (hi * 256 * o >> 7), meanwhile
  sta m_t
  lda RDMPYL
  asl
  xba
  and #$00FF
  bcc :+
  ora #$0100
: clc
  adc m_t
  sta dest
  lda m_sign
  eor sgn
  bpl :+
  lda #0
  sec
  sbc dest
  sta dest
:
.endmacro

; ---------------------------------------------------------------- RAM
.segment "ZEROPAGE"
nmi_count: .res 2
last_frame: .res 2
joy:       .res 2
joy_prev:  .res 2
joy_new:   .res 2
view:      .res 2
paused:    .res 2
posx:      .res 2        ; world position, 10.6 fixed (1024 px wrap)
posy:      .res 2
heading:   .res 2        ; 8.8, hi byte = angle (0 = north, 64 = east)
turnrate:  .res 2
speed:     .res 2        ; units (1/64 px) per frame
alt:       .res 2        ; 8.8, hi byte = level 0..63
lev:       .res 2
climb:     .res 2        ; -1 / 0 / 1
boost:     .res 2
frame:     .res 2
bankf:     .res 2        ; -2..2 bank frame
sinv:      .res 2
cosv:      .res 2
camu_x:    .res 2        ; camera position (units)
camu_y:    .res 2
m_a:       .res 2
m_b:       .res 2
m_t:       .res 2
m_sign:    .res 2
os8:       .res 2
oc8:       .res 2
hi_s:      .res 6
hi_c:      .res 6
m_t2:      .res 2
hist_ctr:  .res 2
m_div:     .res 2
t0:        .res 2
t1:        .res 2
t2:        .res 2
t3:        .res 2
t4:        .res 2
t5:        .res 2
t6:        .res 2
t7:        .res 2
sx:        .res 2
sy:        .res 2
stile:     .res 2
sattr:     .res 2
sbig:      .res 2
oam_idx:   .res 2
bank_prev: .res 2        ; last bank frame (for the bank swoosh SFX)
sfx_seq:   .res 2        ; SFX request counter sent to the APU on port 1
src:       .res 2
src1:      .res 2
dst:       .res 2
cnt:       .res 2
c_flag:    .res 2
c_m7x:     .res 2
c_m7y:     .res 2
c_hofs:    .res 2
c_b3h:     .res 2        ; BG3 horizon band scroll (heading / 64)
c_vofs:    .res 2
c_ma:      .res 2
c_mb:      .res 2
c_mc:      .res 2
c_md:      .res 2
c_buf:     .res 2
front:     .res 2
c_bufv:    .res 2
front_v:   .res 2
tbl_key:   .res 2
tbl_late:  .res 2
tbl_skips: .res 2
maxl_at:   .res 2
oam_prev:  .res 2
lr_n:      .res 2
saw_lev:   .res 2
inidisp:   .res 2
hdma_mask: .res 2
ne:        .res 2
ne2:       .res 2
row_flag:  .res 2
row_addr:  .res 2
dig_flag:  .res 2
hist_pos:  .res 2
cl_n:      .res 2
tl_cb0:    .res 2
tl_cb1:    .res 2
tl_cs0:    .res 2
tl_cs1:    .res 2
cl_attr:   .res 2
zjet:      .res 2
abs_sin:   .res 2
abs_cos:   .res 2
campx:     .res 2
campy:     .res 2
pospx:     .res 2
pospy:     .res 2
t_ps:      .res 2
t_pc:      .res 2
loopi:     .res 2
loops:     .res 2
maxline:   .res 2
noprof:    .res 2
nmi_ln:    .res 2
st_ln:     .res 2
st_nmi:    .res 2
wc_dur:    .res 2
wc_n:      .res 2
profA:     .res 2
phys_n:    .res 2

mu_ptr: .res 3              ; boss.s: SPC700 upload source (long pointer)

.segment "BSS"
oam_lo:   .res 512
oam_hi:   .res 32
hm:       .res MSZ*4        ; 2 buffers x (AB array, CD array)
hv:       .res VSZ*2        ; 2 buffers of per-line BG1VOFS
itab:     .res ITSZ*6
ct_y0:    .res 2
ct_c1:    .res 2
ct_c2:    .res 2
ct_c3:    .res 2
ct_yd:    .res 2
ct_xd:    .res 2
tmpw:     .res 2
profmax:  .res 96
profcur:  .res 96
profprev: .res 2
profsum:  .res 192
profhot:  .res 96
profhot_n: .res 2
rowbuf:   .res 64
digbuf:   .res 16
hist_lx:  .res NHIST*2
hist_ly:  .res NHIST*2
hist_rx:  .res NHIST*2
hist_ry:  .res NHIST*2
cl_sx:    .res 32
cl_sy:    .res 32
cl_z:     .res 32
cl_t:     .res 32
cl_b:     .res 32
cl_order: .res 32
sh_x:     .res 32
sh_y:     .res 32
sh_t:     .res 32
sh_b:     .res 32

; ---------------------------------------------------------------- macros
.macro DMA_VRAM srcl, vaddr, len, vmainv, bbadv, dmapv
  A8
  lda #vmainv
  sta VMAIN
  A16
  lda #vaddr
  sta VMADDL
  lda #.loword(srcl)
  sta A1T0L
  lda #len
  sta DAS0L
  A8
  lda #^srcl
  sta A1B0
  lda #dmapv
  sta DMAP0
  lda #bbadv
  sta BBAD0
  lda #1
  sta MDMAEN
  A16
.endmacro

.macro HDMA_DIRECT ch, dmapv, bbadv, tbl
  A8
  lda #dmapv
  sta $4300+ch*16
  lda #bbadv
  sta $4301+ch*16
  lda #^tbl
  sta $4304+ch*16
  A16
  lda #.loword(tbl)
  sta $4302+ch*16
.endmacro

; =====================================================================
.segment "CODE"
Reset:
  sei
  clc
  xce
  jml FastReset
FastReset:
  AXY16
  ldx #$1FFF
  txs
  lda #$0000
  tcd
  A8
  lda #$80
  pha
  plb
  sta INIDISP
  stz NMITIMEN
  stz HDMAEN
  stz MDMAEN
  lda #1
  sta MEMSEL                ; FastROM (code runs in banks $80+)
  jsr InitRegs
  jsr ClearMem
  CHK 60
  jsr ApuUpload             ; boot the sound CPU: driver + samples + song (music starts)
  CHK 61
  AXY16
  lda #1
  sta opt_diff              ; NORMAL
  jsr ApplyDiff
.ifndef SKIPTITLE
  jmp TitleEnter            ; title screen / start menu (src/title.s)
.endif
  jsr LoadStatic
  CHK 62
  jsr InitGame
  CHK 63
  jsr LoadView
  CHK 64
  jsr PauseText
  ; fall into main loop

; ---------------------------------------------------------------- main
MainLoop:
  AXY16
@wait:
  lda last_frame
  cmp nmi_count
  bne @go
  jsr MusicPump             ; idle time: SPC700 song uploads (boss <-> field), until the next NMI
  bra @wait
@go:
  lda nmi_count
  sec
  sbc last_frame
  cmp #4
  bcc :+
  lda #3
: sta phys_n                ; frames elapsed (logic catches up if a frame was dropped)
  sta elapsed
  lda nmi_count
  sta last_frame
  jsr LineRel
  sta st_ln
  lda nmi_ln
  sta st_nmi
  CHK 9
  jsr ReadJoy
.ifdef AUTOPILOT
  jsr AutoPilot
.endif
  jsr InputMask
  jsr Buttons
  lda paused
  bne @nophys
@ph:
  jsr Physics
  dec phys_n
  bne @ph
  jsr SfxFrame
  CHK 0
@nophys:
  jsr MusicFrame
  lda go_req                ; game over: over to the chase camera
  beq @wc0
  jsr GameOverView
@wc0:
  jsr LineRel               ; (profiling: time spent waiting here is idle)
  sta wc_dur
  ldx lr_n
  stx wc_n
@wc:
  lda c_flag                ; previous commit consumed by NMI?
  beq @wcd
  jsr MusicPump
  bra @wc
@wcd:
  jsr LineRel
  ldx lr_n
@wco:
  cpx wc_n
  beq :+
  clc
  adc #262
  dex
  bra @wco
: sec
  sbc wc_dur
  sta wc_dur
  CHK 22
  jsr RowUpdate
  CHK 23
  jsr BuildFrame
  lda #$0F
  sta inidisp
  lda #1
  sta c_flag
  inc loops
  jsr Profile
  jmp MainLoop

; debug checkpoints (PROFX builds only): profmax[x] = worst scanline at checkpoint x
.ifdef PROFX
ProfAt:
  lda noprof
  bne @r
  phy
  A8
  lda $2137
  lda $213D
  xba
  lda $213D
  and #1
  xba
  A16
  clc
  adc #262-225
  cmp #262
  bcc :+
  sbc #262
: pha
  sec
  sbc profprev
  bpl :+
  clc
  adc #262
: cpx #18
  bne :+
  lda #0
: sta profcur,x
  cmp profmax,x
  bcc :+
  sta profmax,x
: phx
  pha
  txa
  asl
  tax
  pla
  clc
  adc profsum,x
  sta profsum,x
  bcc :+
  inc profsum+2,x
: plx
  pla
  sta profprev
  ply
@r:
  rts
.endif
; debug: track the latest scanline reached by the main loop (relative to vblank start)
; current scanline relative to vblank start (A16 in/out)
LineRel:
  phx
@again:
  ldx nmi_count             ; an NMI between latch and read would garble it: retry
  A8
  lda $213F                 ; reset the counter read flip-flop
  lda $2137                 ; latch counters
  lda $213D
  xba
  lda $213D
  and #1
  xba
  A16
  clc
  adc #262-225
  cmp #262
  bcc :+
  sbc #262
: cpx nmi_count
  bne @again
  stx lr_n                  ; the frame count that goes with this reading
  plx
  rts
; debug: frame load = NMI time + main-loop work time, in scanlines (262 = one full frame)
; work done so far this frame in scanlines: NMI time + main loop time, idle waits excluded
LoadNow:
  jsr LineRel
  ldx lr_n
@ov:
  cpx last_frame            ; each NMI during the work adds a whole frame
  beq :+
  clc
  adc #262
  dex
  bra @ov
: sec
  sbc st_ln
  clc
  adc st_nmi
  sec
  sbc wc_dur
  rts
Profile:
  lda noprof
  beq :+
  dec noprof
  rts
: jsr LoadNow
.if .defined(PROFX) .or .defined(RING)
  pha
  lda loops
  and #$7FFF
  asl
  tax
  pla
  sta f:$7F0000,x
.endif
.ifdef PROFX
  cmp #251                  ; heavy frame: add its breakdown to profhot
  bcc @nh
  pha
  inc profhot_n
  ldx #94
@cp:
  lda profcur,x
  clc
  adc profhot,x
  sta profhot,x
  dex
  dex
  bpl @cp
  pla
@nh:
.endif
  cmp maxline
  bcc :+
  sta maxline
  lda loops
  sta maxl_at
: rts

; ---------------------------------------------------------------- init
InitRegs:
  A8
  I16
  ldx #$2101
@l1:
  stz a:$0000,x             ; $2101-$210C
  inx
  cpx #$210D
  bne @l1
@l2:
  stz a:$0000,x             ; scroll regs, write twice
  stz a:$0000,x
  inx
  cpx #$2115
  bne @l2
  lda #$80
  sta VMAIN
  stz $2116
  stz $2117
  stz M7SEL
  stz M7A
  lda #1
  sta M7A
  stz M7B
  stz M7B
  stz M7C
  stz M7C
  stz M7D
  sta M7D
  stz M7X
  stz M7X
  stz M7Y
  stz M7Y
  stz CGADD
  ldx #$2123
@l3:
  stz a:$0000,x
  inx
  cpx #$2134
  bne @l3
  lda #$E0
  sta COLDATA
  stz NMITIMEN
  lda #$FF
  sta WRIO
  ldx #$4202
@l4:
  stz a:$0000,x
  inx
  cpx #$420D
  bne @l4
  A16
  rts

ClearMem:
  ; WRAM $0000-$1EFF via DMA (stack untouched)
  A8
  stz WMADDL
  stz WMADDM
  stz WMADDH
  lda #$08
  sta DMAP0
  lda #$80
  sta BBAD0
  lda #^ZeroByte
  sta A1B0
  A16
  lda #.loword(ZeroByte)
  sta A1T0L
  lda #$1F00
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  ; VRAM 64KB
  lda #$80
  sta VMAIN
  A16
  stz VMADDL
  stz DAS0L
  lda #.loword(ZeroByte)
  sta A1T0L
  A8
  lda #$09
  sta DMAP0
  lda #$18
  sta BBAD0
  lda #1
  sta MDMAEN
  A16
  rts

LoadStatic:
  ; palette
  A8
  stz CGADD
  lda #$00
  sta DMAP0
  lda #$22
  sta BBAD0
  lda #^Palette
  sta A1B0
  A16
  lda #.loword(Palette)
  sta A1T0L
  lda #512
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
  ; perspective scale tables (all levels) -> WRAM $7E:2000
  A8
  stz WMADDL
  lda #>PWRAM
  sta WMADDM
  stz WMADDH
  stz DMAP0
  lda #$80
  sta BBAD0
  lda #^Persp
  sta A1B0
  A16
  lda #.loword(Persp)
  sta A1T0L
  lda #64*PERSP_LEVEL_BYTES
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
  DMA_VRAM M7Map,   $0000, 16384, $00, $18, $00
  DMA_VRAM M7Tiles, $0000, 16384, $80, $19, $00
  DMA_VRAM Bg2Tiles, $4000, Bg2TilesEnd-Bg2Tiles, $80, $18, $01
  DMA_VRAM Bg3Tiles, $5800, Bg3TilesEnd-Bg3Tiles, $80, $18, $01
  DMA_VRAM MapBg3,     BG3_ROWS_VRAM0, 192, $80, $18, $01
  DMA_VRAM (MapBg3+192), BG3_ROWS_VRAM1, 192, $80, $18, $01
  A8
  lda #$04
  sta BG34NBA               ; BG3 chars at $4000 (band tiles are numbers $300+ = VRAM $5800)
  lda #$51
  sta BG3SC                 ; BG3 horizon band: 64x32 map at $5000
  stz BG3HOFS
  stz BG3HOFS
  lda #$FF
  sta BG3VOFS
  lda #$03
  sta BG3VOFS
  lda #$44
  sta BG12NBA               ; BG1/BG2 chars at $4000
  lda #$58
  sta BG1SC                 ; BG1 (mode 1 lines) -> blank map $5800
  lda #$5C
  sta BG2SC                 ; BG2 map at $5C00
  lda #$A3
  sta OBSEL                 ; 32x32 / 64x64 sprites, tiles at $6000
  stz M7SEL                 ; wrap
  lda #$13
  sta TM
  stz SETINI
  stz BG2HOFS
  stz BG2HOFS
  lda #$FF
  sta BG2VOFS
  lda #$03
  sta BG2VOFS
  A16
  rts

InitGame:
  AXY16
  lda #32000
  sta posx
  lda #48640
  sta posy
  stz heading
  stz turnrate
  lda #96
  sta speed
  lda #$2000
  sta alt
  lda #VIEW_CHASE
  sta view
  lda #$FFFF
  sta saw_lev
  sta tbl_key
  ldx #NHIST*2-2
@h:
  lda #500
  sta hist_lx,x
  sta hist_rx,x
  lda #760
  sta hist_ly,x
  sta hist_ry,x
  dex
  dex
  bpl @h
  jsr UpdateTrig
  jmp InitCombat

; ---------------------------------------------------------------- view loading (force blank)
LoadView:
  AXY16
  A8
  lda #$80
  sta INIDISP
  stz HDMAEN
  lda #$01
  sta NMITIMEN              ; NMI off while we touch VRAM
  A16
  lda #$80
  sta inidisp
  lda #3
  sta noprof
  lda #512
  sta oam_prev              ; hide every OAM entry on the first frame
  lda #$FFFF
  sta tbl_key
  stz c_flag
  stz front
  stz dig_flag
  lda view
  cmp #VIEW_OVER
  bne :+
  jmp @over
: cmp #VIEW_COCK
  bne :+
  jmp @cock
:
  ; ---- chase
  jsr BossSheetSel
  bne :+
  DMA_VRAM ObjChase, $6000, 16384, $80, $18, $01
  bra :++
: DMA_VRAM ObjChaseBoss, $6000, 16384, $80, $18, $01
:
  DMA_VRAM MapText,  $5C00, 2048,  $80, $18, $01
  lda #NE_CH
  sta ne
  lda #NE_CH2
  sta ne2
  HDMA_DIRECT 5, $00, <BGMODE, md_chase
  HDMA_DIRECT 4, $00, <TM, tm_chase
  HDMA_DIRECT 6, $03, <CGADD,  cg_chase
  lda #T_CHASE_CLOUDB0
  sta tl_cb0
  lda #T_CHASE_CLOUDB1
  sta tl_cb1
  lda #T_CHASE_CLOUDS0
  sta tl_cs0
  lda #T_CHASE_CLOUDS1
  sta tl_cs1
  lda #CAMBACK
  sta zjet
  sta zoff
  lda #17
  sta hcam
  lda #VIEW_CHASE*NFRAMES*2
  sta ftab
  lda #$30
  sta obj_pri
  A8
  lda #$83
  sta OBSEL                 ; 16x16 / 64x64
  A16
  jmp @persp
@cock:
  jsr BossSheetSel
  bne :+
  DMA_VRAM ObjCock, $6000, 16384, $80, $18, $01
  bra :++
: DMA_VRAM ObjCockBoss, $6000, 16384, $80, $18, $01
:
  DMA_VRAM MapCock, $5C00, 2048,  $80, $18, $01
  lda #NE_CK
  sta ne
  lda #NE_CK2
  sta ne2
  HDMA_DIRECT 5, $00, <BGMODE, md_cock
  HDMA_DIRECT 4, $00, <TM, tm_cock
  HDMA_DIRECT 6, $03, <CGADD,  cg_cock
  lda #T_COCK_CLOUDB0
  sta tl_cb0
  lda #T_COCK_CLOUDB1
  sta tl_cb1
  lda #T_COCK_CLOUDS0
  sta tl_cs0
  lda #T_COCK_CLOUDS1
  sta tl_cs1
  stz zjet
  stz zoff
  lda #5
  sta hcam
  lda #VIEW_COCK*NFRAMES*2
  sta ftab
  lda #$10
  sta obj_pri
  A8
  lda #$63
  sta OBSEL                 ; 16x16 / 32x32
  A16
@persp:
  lda #$12                  ; cloud attr: palette 1, priority 1 (behind BG2 panels)
  sta cl_attr
  lda #$00FE                ; HDMA ch1-3 (matrix, VOFS), 4 (TM), 5-7
  sta hdma_mask
  stz front_v
  jsr BuildITabs
  ; ch1: indirect, 4 bytes -> M7A,M7A,M7B,M7B ; ch2 -> M7C,M7C,M7D,M7D ; ch3: 2 bytes -> BG1VOFS
  A8
  lda #$43
  sta $4310
  sta $4320
  lda #$42
  sta $4330
  lda #<M7A
  sta $4311
  lda #<M7C
  sta $4321
  lda #<BG1VOFS
  sta $4331
  lda #$7E
  sta $4314
  sta $4317
  sta $4324
  sta $4327
  sta $4334
  sta $4337
  A16
  lda #.loword(itab)
  sta $4312
  lda #.loword(itab)+ITSZ
  sta $4322
  lda #.loword(itab)+ITSZ*4
  sta $4332
  HDMA_DIRECT 7, $02, <COLDATA, haze
  A8
  stz CGWSEL                ; colour math with fixed colour (haze)
  lda #$01
  sta CGADSUB               ; add to BG1
  stz TS
  A16
  jmp @done
@over:
  DMA_VRAM ObjOver, $6000, 16384, $80, $18, $01
  DMA_VRAM MapText, $5C00, 2048,  $80, $18, $01
  HDMA_DIRECT 5, $00, <BGMODE, md_over
  HDMA_DIRECT 4, $00, <TM, tm_over
  HDMA_DIRECT 6, $03, <CGADD,  cg_over
  lda #$0070
  sta hdma_mask
  lda #T_OVER_CLOUDB0
  sta tl_cb0
  lda #T_OVER_CLOUDB1
  sta tl_cb1
  lda #T_OVER_CLOUDS0
  sta tl_cs0
  lda #T_OVER_CLOUDS1
  sta tl_cs1
  lda #$32
  sta cl_attr
  lda #VIEW_OVER*NFRAMES*2
  sta ftab
  lda #$30
  sta obj_pri
  A8
  lda #$A3
  sta OBSEL                 ; 32x32 / 64x64
  lda #$02
  sta CGWSEL                ; colour math with sub screen
  lda #$50
  sta CGADSUB               ; half-add on OBJ palettes 4-7 (shadows)
  lda #$01
  sta TS                    ; BG1 on sub screen
  lda #$E0
  sta COLDATA
  A16
@done:
  ldx #30
: lda #1
  sta cl_vis,x
  dex
  dex
  bpl :-
  jsr ScoreText             ; redraw the score on the new text layer
  jsr HudText
  lda row_dirty
  ora #RD_ALL
  sta row_dirty
  A8
  lda RDNMI
  lda #$81
  sta NMITIMEN
  A16
  rts

; build the indirect HDMA tables: [buf0 AB][buf0 CD][buf1 AB][buf1 CD][buf0 V][buf1 V]
; t0 = data base, t3 = entry size (4 or 2)
BuildITabs:
  AXY16
  ldy #0
  lda #.loword(hm)
  sta t0
  lda #4
  sta t3
  jsr OneITab               ; buf0 AB
  lda #.loword(hm)+MSZ
  sta t0
  jsr OneITab               ; buf0 CD
  lda #.loword(hm)+MSZ*2
  sta t0
  jsr OneITab               ; buf1 AB
  lda #.loword(hm)+MSZ*3
  sta t0
  jsr OneITab               ; buf1 CD
  lda #2
  sta t3
  lda #.loword(hv)
  sta t0
  jsr OneITab
  lda #.loword(hv)+VSZ
  sta t0
  jsr OneITab
  rts

OneITab:
  phy
  A8
  lda #64                   ; sky lines (values unused there)
  sta itab,y
  A16
  iny
  lda t0
  sta itab,y
  iny
  iny
  A8
  lda #$A0                  ; 32 lines, one entry per line (repeat mode)
  sta itab,y
  A16
  iny
  lda t0
  sta itab,y
  iny
  iny
  lda t3                    ; skip 32 entries
  asl
  asl
  asl
  asl
  asl
  clc
  adc t0
  sta t2
  ldx ne2
@e:
  A8
  lda #2                    ; one entry every two lines
  sta itab,y
  A16
  iny
  lda t2
  sta itab,y
  iny
  iny
  lda t2
  clc
  adc t3
  sta t2
  dex
  bne @e
  A8
  lda #0
  sta itab,y
  A16
  pla
  clc
  adc #ITSZ
  tay
  rts

; ---------------------------------------------------------------- NMI
NmiStub:
  jml NmiFast
NmiFast:
  AXY16
  pha
  phx
  phy
  phb
  phd
  lda #$0000
  tcd
  A8
  lda #$80
  pha
  plb
  lda RDNMI
  A16
  lda ti_on
  beq :+
  jsr TitleNmi
  jmp @nocommit
: lda c_flag
  bne :+
  jmp @nocommit
: A8
  ; OAM
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
  ; mode 7 centre / scroll
  lda c_m7x
  sta M7X
  lda c_m7x+1
  sta M7X
  lda c_m7y
  sta M7Y
  lda c_m7y+1
  sta M7Y
  A16
  lda c_hofs
  clc
  adc c_shk                 ; hit shake
  A8
  sta BG1HOFS
  xba
  sta BG1HOFS
  A16
  lda c_b3h
  clc
  adc c_shk
  A8
  sta BG3HOFS
  xba
  sta BG3HOFS
  A16
  lda c_shk
  ldx view
  cpx #VIEW_COCK
  beq :+
  lda #0
: A8
  sta BG2HOFS
  xba
  sta BG2HOFS
  lda c_vofs
  sta BG1VOFS
  lda c_vofs+1
  sta BG1VOFS
  lda view
  cmp #VIEW_OVER
  bne @persp
  lda c_ma
  sta M7A
  lda c_ma+1
  sta M7A
  lda c_mb
  sta M7B
  lda c_mb+1
  sta M7B
  lda c_mc
  sta M7C
  lda c_mc+1
  sta M7C
  lda c_md
  sta M7D
  lda c_md+1
  sta M7D
  bra @vram
@persp:
  A16
  lda #.loword(itab)
  ldx c_buf
  beq :+
  lda #.loword(itab)+ITSZ*2
: sta $4312
  clc
  adc #ITSZ
  sta $4322
  lda #.loword(itab)+ITSZ*4
  ldx c_bufv
  beq :+
  lda #.loword(itab)+ITSZ*5
: sta $4332
@vram:
  A16
  lda row_flag
  beq @nodig0
  A8
  lda #$80
  sta VMAIN
  A16
  lda row_addr
  sta VMADDL
  lda #.loword(rowbuf)
  sta A1T0L
  lda #64
  sta DAS0L
  A8
  stz A1B0
  lda #$01
  sta DMAP0
  lda #$18
  sta BBAD0
  lda #1
  sta MDMAEN
  A16
  stz row_flag
@nodig0:
  lda dig_flag
  beq @nodig
  A8
  lda #$80
  sta VMAIN
  A16
  lda #COCK_ALT_ADDR
  sta VMADDL
  lda digbuf
  sta VMDATAL
  lda digbuf+2
  sta VMDATAL
  lda digbuf+4
  sta VMDATAL
  lda digbuf+6
  sta VMDATAL
  lda digbuf+8
  sta VMDATAL
  lda #COCK_SPD_ADDR
  sta VMADDL
  lda digbuf+10
  sta VMDATAL
  lda digbuf+12
  sta VMDATAL
  lda digbuf+14
  sta VMDATAL
  stz dig_flag
@nodig:
  lda score_flag
  beq @nosc
  A8
  lda #$80
  sta VMAIN
  A16
  lda #SCORE_ADDR_TEXT
  ldx view
  cpx #VIEW_COCK
  bne :+
  lda #SCORE_ADDR_COCK
: sta VMADDL
  lda scorebuf
  sta VMDATAL
  lda scorebuf+2
  sta VMDATAL
  lda scorebuf+4
  sta VMDATAL
  lda scorebuf+6
  sta VMDATAL
  lda scorebuf+8
  sta VMDATAL
  lda scorebuf+10
  sta VMDATAL
  stz score_flag
@nosc:
  lda hud_flag
  beq @nohud
  A8
  lda #$80
  sta VMAIN
  A16
  lda #HUD_ADDR_TEXT
  ldx view
  cpx #VIEW_COCK
  bne :+
  lda #HUD_ADDR_COCK
: sta VMADDL
  ldx #0
: lda hudbuf,x
  sta VMDATAL
  inx
  inx
  cpx #26
  bne :-
  stz hud_flag
@nohud:
  jsr BossNmi               ; boss palette / colour animation / sheet streaming
  ; hit flash: red fixed colour added over the picture (HDMA ch 7 table swap in perspective views)
  lda view
  cmp #VIEW_OVER
  beq @fo
  lda c_flash
  beq @fp0
  A8
  ora #$60
  sta flashtab+2            ; second write: red = green = v
  sta flashtab+5
  lda c_flash
  lsr
  ora #$80
  sta flashtab+1            ; first write: blue = v/2 (warm white: never purple over the sea)
  sta flashtab+4
  lda #$35                  ; add the colour constant (BG1, BG3 band, OBJ, backdrop)
  sta CGADSUB
  A16
  lda #.loword(flashtab)
  sta $4372
  bra @fdone
@fp0:
  lda #.loword(haze)
  sta $4372
  A8
  lda #$01
  sta CGADSUB
  A16
  bra @fdone
@fo:
  lda c_flash
  A8
  beq @fo0
  lsr
  ora #$80
  sta COLDATA
  lda c_flash
  ora #$60
  sta COLDATA
  stz CGWSEL
  lda #$11                  ; add: warm flash
  sta CGADSUB
  A16
  bra @fdone
@fo0:
  lda #$E0
  sta COLDATA
  lda #$02
  sta CGWSEL
  lda #$50
  sta CGADSUB
  A16
@fdone:
  stz c_flag
@nocommit:
  A8
  lda hdma_mask
  sta HDMAEN
  lda inidisp
  sta INIDISP
  A16
  jsr LineRel
  sta nmi_ln
  inc nmi_count
  pld
  plb
  ply
  plx
  pla
EmptyHandler:
  rti

; ---------------------------------------------------------------- input
ReadJoy:
  A8
@w:
  lda HVBJOY
  and #1
  bne @w
  A16
  lda JOY1L
  sta joy
  lda joy_prev
  eor #$FFFF
  and joy
  sta joy_new
  lda joy
  sta joy_prev
  rts

Buttons:
  lda joy_new
  and #KEY_START
  beq @nostart
  lda gameover
  beq @nogo
  lda go_t                  ; game over: START plays again
  cmp #60
  bcc @noview
.ifdef SKIPTITLE
  jmp RestartGame
.else
  jmp GoTitle               ; game over -> title screen
.endif
@nogo:
  lda paused
  eor #1
  sta paused
  jsr PauseText
@nostart:
  lda gameover
  bne @noview
  lda joy_new
  and #(KEY_SELECT|KEY_X)
  beq @noview
  ; debug shortcut: paused + hold L+R + SELECT = straight to the boss
  lda paused
  beq @nowarp
  lda joy
  and #(KEY_L|KEY_R)
  cmp #(KEY_L|KEY_R)
  bne @nowarp
  jsr BossWarp
  stz paused
  jmp PauseText
@nowarp:
  lda view
  inc a
  cmp #3
  bcc :+
  lda #0
: ldx b_st                  ; boss fight: chase <-> cockpit only (overhead sees too little ahead)
  beq :+
  cmp #VIEW_OVER
  bne :+
  inc a
: sta view
  jsr LoadView
  jsr PauseText
@noview:
  rts

; the bottom text row is rebuilt by RowUpdate (attack.s): pause / warnings / press start
PauseText:
  AXY16
  lda row_dirty
  ora #RD_HINT
  sta row_dirty
  rts

; ---------------------------------------------------------------- sound effects
; Afterburner (B) and hard-bank swooshes go to SFX channel A (voice 7); see combat.s SfxA.
SfxEvents:
  lda joy_new
  and #KEY_B
  beq @nob
  lda #SA_BOOST
  ldx #2
  ldy #31
  jsr SfxA
@nob:
  lda bankf
  cmp bank_prev
  beq @done
  sta bank_prev
  cmp #2
  bne @nr
  lda #SA_BANKR
  bra @go
@nr:
  cmp #.loword(-2)
  bne @done
  lda #SA_BANKL
@go:
  ldx #1
  ldy #31
  jmp SfxA
@done:
  rts

; ---------------------------------------------------------------- physics
Physics:
  AXY16
  inc frame
  ; --- steering: target turn rate
  stz t0
  lda joy
  and #KEY_LEFT
  beq :+
  lda #.loword(-$0160)
  sta t0
: lda joy
  and #KEY_RIGHT
  beq :+
  lda #$0160
  sta t0
: lda joy
  and #KEY_L
  beq :+
  lda #.loword(-$0280)
  sta t0
: lda joy
  and #KEY_R
  beq :+
  lda #$0280
  sta t0
: lda turnrate
  sec
  sbc t0
  beq @td
  bmi @incr
  cmp #$18
  bcc @set
  lda turnrate
  sec
  sbc #$18
  sta turnrate
  bra @td
@set:
  lda t0
  sta turnrate
  bra @td
@incr:
  clc
  adc #$18
  bpl @set
  lda turnrate
  clc
  adc #$18
  sta turnrate
@td:
  lda heading
  clc
  adc turnrate
  sta heading
  ; --- bank frame from turn rate
  lda turnrate
  jsr Abs
  ldx #0
  cmp #$90
  bcc @bk
  inx
  cmp #$1C0
  bcc @bk
  inx
@bk:
  stx bankf
  lda turnrate
  bpl :+
  lda #0
  sec
  sbc bankf
  sta bankf
:
  jsr SfxEvents
  ; --- climb / dive
  stz climb
  lda joy
  and #KEY_UP
  beq @noup
  lda alt
  clc
  adc #$30
  cmp #$3F00
  bcc :+
  lda #$3F00
: sta alt
  lda #1
  sta climb
@noup:
  lda joy
  and #KEY_DOWN
  beq @nodn
  lda alt
  sec
  sbc #$30
  bcs :+
  lda #0
: sta alt
  lda #$FFFF
  sta climb
@nodn:
  lda alt
  xba
  and #$00FF
  sta lev
  ; --- thrust
  stz boost
  lda joy
  and #KEY_B
  beq @slow
  lda #1
  sta boost
  lda speed
  clc
  adc #3
  cmp #208
  bcc :+
  lda #208
: sta speed
  bra @spd
@slow:
  lda speed
  dec a
  cmp #96
  bcs :+
  lda #96
: sta speed
@spd:
  jsr UpdateTrig
  ; --- move: forward = (sin, -cos)
  lda speed
  ldx sinv
  jsr MulSS
  clc
  adc posx
  sta posx
  lda speed
  ldx cosv
  jsr MulSS
  sta t0
  lda posy
  sec
  sbc t0
  sta posy
  ; --- contrail history (every 5th frame)
  dec hist_ctr
  bpl @nohist
  lda #4
  sta hist_ctr
  lda hist_pos
  clc
  adc #2
  cmp #NHIST*2
  bcc :+
  lda #0
: sta hist_pos
  lda #896                  ; 14 px wing half-span
  ldx cosv
  jsr MulSS
  sta t0
  lda #896
  ldx sinv
  jsr MulSS
  sta t1
  ldx hist_pos
  lda posx
  clc
  adc t0
  jsr Lsr6
  sta hist_rx,x
  lda posx
  sec
  sbc t0
  jsr Lsr6
  sta hist_lx,x
  lda posy
  clc
  adc t1
  jsr Lsr6
  sta hist_ry,x
  lda posy
  sec
  sbc t1
  jsr Lsr6
  sta hist_ly,x
@nohist:
  CHK 10
  jsr CombatStep
  CHK 11
  rts

UpdateTrig:
  AXY16
  lda heading
  xba
  and #$00FF
  asl
  tax
  lda f:SinTab,x
  sta sinv
  txa
  clc
  adc #128
  and #$01FF
  tax
  lda f:SinTab,x
  sta cosv
  jsr Abs
  sta abs_cos
  lda sinv
  jsr Abs
  sta abs_sin
  lda posx
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  sta pospx
  lda posy
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  sta pospy
  rts

; ---------------------------------------------------------------- math
; A = a (signed), X = s (signed, |s|<=255)  ->  A = (a*s)>>8
MulSS:
  sta m_a
  stx m_b
  eor m_b
  sta m_sign
  lda m_b
  bpl :+
  eor #$FFFF
  inc a
: A8
  sta WRMPYA
  A16
  lda m_a
  bpl :+
  eor #$FFFF
  inc a
: sta m_a
  A8
  sta WRMPYB
  nop
  nop
  nop
  nop
  A16
  lda RDMPYH
  and #$00FF
  sta m_t
  A8
  lda m_a+1
  sta WRMPYB
  nop
  nop
  nop
  nop
  A16
  lda RDMPYL
  clc
  adc m_t
  bit m_sign
  bpl :+
  eor #$FFFF
  inc a
: rts

; A = dividend (unsigned 16), X = divisor (1..255) -> A = quotient
DivU:
  sta WRDIVL
  txa
  A8
  sta WRDIVB
  nop
  nop
  nop
  nop
  nop
  nop
  nop
  nop
  A16
  lda RDDIVL
  rts

Lsr6:
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  rts

Abs:
  cmp #$8000
  bcc :+
  eor #$FFFF
  inc a
: rts

; A = signed rel (|rel| < 768) -> t_ps = (rel*sin)>>8, t_pc = (rel*cos)>>8
RelTrig:
  sta m_sign
  cmp #$8000
  bcc :+
  eor #$FFFF
  inc a
: sta m_a
  A8
  sta WRMPYA
  lda abs_sin
  sta WRMPYB
  nop
  nop
  nop
  nop
  lda RDMPYH
  sta t_ps
  lda abs_cos
  sta WRMPYB
  nop
  nop
  nop
  nop
  lda RDMPYH
  sta t_pc
  stz t_ps+1
  stz t_pc+1
  ldx m_a+1
  A16
  txa
  and #$00FF
  beq @nohi
  tax
@hi:
  lda t_ps
  clc
  adc abs_sin
  sta t_ps
  lda t_pc
  clc
  adc abs_cos
  sta t_pc
  dex
  bne @hi
@nohi:
  lda m_sign
  eor sinv
  bpl :+
  lda t_ps
  eor #$FFFF
  inc a
  sta t_ps
: lda m_sign
  eor cosv
  bpl :+
  lda t_pc
  eor #$FFFF
  inc a
  sta t_pc
: rts

; A = signed (|a| < 1024), X = unsigned 0..255 -> A = (a*x)>>8
MulSmall:
  sta m_sign
  cmp #$8000
  bcc :+
  eor #$FFFF
  inc a
: sta m_a
  stx m_b
  A8
  sta WRMPYA
  lda m_b
  sta WRMPYB
  nop
  nop
  nop
  nop
  lda RDMPYH
  sta m_t
  stz m_t+1
  ldx m_a+1
  A16
  txa
  and #$00FF
  beq @nh
  tax
  lda m_t
@h:
  clc
  adc m_b
  dex
  bne @h
  sta m_t
@nh:
  lda m_t
  bit m_sign
  bpl :+
  eor #$FFFF
  inc a
: rts

; signed 10-bit wrap of a pixel difference (world is 1024 px around)
Wrap10:
  and #$03FF
  cmp #$0200
  bcc :+
  ora #$FC00
: rts

Asr6:
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
  ror
  rts

; ---------------------------------------------------------------- perspective tables
PWRAM = $2000              ; all altitude levels' scale tables, copied to $7E:2000 at boot

; Per-entry matrix with BG1VOFS chosen so (line + VOFS - Y0) = FOCAL on every line:
;   A = cos*S   B = sin*S   C = sin*S   D = -cos*S      (S = z/FOCAL)
; HDMA entry layout: AB array [A,B] and CD array [C,D], 4 bytes per entry.
.macro MATPASS store1, neg1, store2, neg2, step
.local loop
loop:
  lda PWRAM,y               ; scale (DB = $7E: all levels live in WRAM)
  sta $03                   ; WRMPYB <- lo   (D = $4200)
  lda PWRAM+1,y
  pha
  lda $17                   ; RDMPYH
  and #$00FF
  sta a:tmpw
  pla
  sta $03                   ; WRMPYB <- hi
  lda a:tmpw
  clc
  nop
  adc $16                   ; RDMPYL
.if neg1
  eor #$FFFF
  inc a
.endif
  sta store1,x
.if neg2
  eor #$FFFF
  inc a
.endif
  sta store2,x
.if step = 1
  inx
  inx
  inx
  inx
  iny
  iny
.else
  txa
  clc
  adc #4*step
  tax
  tya
  clc
  adc #2*step
  tay
.endif
  cpy a:cnt
  bne loop
.endmacro

; exact entries: 0-11, even 12-30, every 4th from 32 to ne-4, and ne-2, ne-1 (the rest are interpolated)
.macro MATSEG store1, neg1, store2, neg2
  ldx a:t6
  ldy a:ct_y0
  lda a:ct_c1
  sta a:cnt
  MATPASS store1, neg1, store2, neg2, 1
  lda a:ct_c2
  sta a:cnt
  MATPASS store1, neg1, store2, neg2, 2
  lda a:ct_c3
  sta a:cnt
  MATPASS store1, neg1, store2, neg2, 4
  ldx a:ct_xd
  ldy a:ct_yd
  MATPASS store1, neg1, store2, neg2, 1
.endmacro

ComputeTables:
  AXY16
.ifdef NOTABLES
  rts
.endif
  A8
  lda lev
  sta WRMPYA
  lda #PERSP_LEVEL_BYTES
  sta WRMPYB
  nop
  nop
  nop
  nop
  A16
  lda RDMPYL
  sta ct_y0                 ; this level's scale table (offset into PWRAM)
  clc
  adc #24
  sta ct_c1
  adc #40
  sta ct_c2
  lda ne
  asl
  clc
  adc ct_y0
  sta ct_c3
  sec
  sbc #4
  sta ct_yd
  lda front
  eor #1
  sta t7
  lda #0
  ldx t7
  beq :+
  lda #MSZ*2
: sta t6                    ; X start (buffer offset)
  lda ne
  dec a
  dec a
  asl
  asl
  clc
  adc t6
  sta ct_xd
  ; ---- pass 1: |cos| -> A and D
  lda cosv
  jsr Abs
  A8
  sta WRMPYA
  lda #$7E
  pha
  plb
  A16
  phd
  lda #$4200
  tcd
  lda a:cosv
  bpl :+
  jmp CT_cneg
: MATSEG hm, 0, hm+MSZ+2, 1
  jmp CT_p2
CT_cneg:
  MATSEG hm+MSZ+2, 0, hm, 1
CT_p2:
  ; ---- pass 2: |sin| -> B and C
  pld
  lda sinv
  jsr Abs
  A8
  sta f:WRMPYA
  A16
  phd
  lda #$4200
  tcd
  lda a:sinv
  bpl :+
  jmp CT_sneg
: MATSEG hm+2, 0, hm+MSZ, 0
  jmp CT_done
CT_sneg:
  MATSEG hm+2, 1, hm+MSZ, 0
CT_done:
  pld
  A8
  lda #$80
  pha
  plb
  A16
  ; odd entries 13..31: midpoints
  lda t6
  clc
  adc #33*4
  sta t5
  lda t6
  clc
  adc #13*4
  tax
@m:
  jsr CT_Mid
  txa
  clc
  adc #8
  tax
  cpx t5
  bcc @m
  ; entry ne-3: midpoint of ne-4 and ne-2
  lda ne
  sec
  sbc #3
  asl
  asl
  clc
  adc t6
  tax
  jsr CT_Mid
  ; entries between the every-4th ones: linear quarters
  lda ne
  sec
  sbc #4
  asl
  asl
  clc
  adc t6
  sta t5
  lda t6
  clc
  adc #32*4
  tax
@q:
  jsr CT_Quad
  txa
  clc
  adc #16
  tax
  cpx t5
  bcc @q
  lda t7
  sta front
  sta c_buf
  rts

; X = entry offset: entry = average of its neighbours (A, B; C = B, D = -A)
CT_Mid:
  lda hm-4,x
  cmp #$8000
  ror
  sta tmpw
  lda hm+4,x
  cmp #$8000
  ror
  clc
  adc tmpw
  sta hm,x
  eor #$FFFF
  inc a
  sta hm+MSZ+2,x
  lda hm-2,x
  cmp #$8000
  ror
  sta tmpw
  lda hm+6,x
  cmp #$8000
  ror
  clc
  adc tmpw
  sta hm+2,x
  sta hm+MSZ,x
  rts

; X = entry offset of an exact entry; fills the 3 entries up to the next exact one (4 later)
CT_Quad:
  lda hm+16,x
  sec
  sbc hm,x
  cmp #$8000
  ror
  cmp #$8000
  ror
  sta tmpw
  lda hm,x
  clc
  adc tmpw
  sta hm+4,x
  eor #$FFFF
  inc a
  sta hm+MSZ+6,x
  lda hm+4,x
  clc
  adc tmpw
  sta hm+8,x
  eor #$FFFF
  inc a
  sta hm+MSZ+10,x
  lda hm+8,x
  clc
  adc tmpw
  sta hm+12,x
  eor #$FFFF
  inc a
  sta hm+MSZ+14,x
  lda hm+18,x
  sec
  sbc hm+2,x
  cmp #$8000
  ror
  cmp #$8000
  ror
  sta tmpw
  lda hm+2,x
  clc
  adc tmpw
  sta hm+6,x
  sta hm+MSZ+4,x
  clc
  adc tmpw
  sta hm+10,x
  sta hm+MSZ+8,x
  clc
  adc tmpw
  sta hm+14,x
  sta hm+MSZ+12,x
  rts

; per-entry BG1VOFS = Y0 + FOCAL - line  (written every frame into the back buffer)
ComputeVofs:
  lda front_v
  eor #1
  sta front_v
  sta c_bufv
  ldx #0
  cmp #0
  beq :+
  ldx #VSZ
: lda c_m7y
  clc
  adc #FOCAL-HOR
.repeat 32, I
  sta hv+I*2,x
  dec a
.endrepeat
.repeat NE_CH2, I
  sta hv+64+I*2,x
  dec a
  dec a
.endrepeat
  rts


; cockpit: only its 88 ground lines (NE_CK entries) are used by the HDMA table
ComputeVofsCk:
  lda front_v
  eor #1
  sta front_v
  sta c_bufv
  ldx #0
  cmp #0
  beq :+
  ldx #VSZ
: lda c_m7y
  clc
  adc #FOCAL-HOR
.repeat 32, I
  sta hv+I*2,x
  dec a
.endrepeat
.repeat NE_CK2, I
  sta hv+64+I*2,x
  dec a
  dec a
.endrepeat
  rts


; camera in camu_x/camu_y -> commit regs, recompute tables if needed
PerspCommon:
  AXY16
  lda camu_x
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  sta c_m7x
  sec
  sbc #128
  sta c_hofs
  lda heading
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  sta c_b3h
  lda camu_y
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  sta c_m7y
  sta c_vofs
  ldy view
  cpy #VIEW_COCK
  bne :+
  jsr ComputeVofsCk
  bra :++
: jsr ComputeVofs
: CHK 21
  lda heading
  xba
  and #$00FF
  sta t0
  lda lev
  xba
  ora t0
  cmp tbl_key
  beq @same
  ; heading/zoom changed: rebuild the matrix tables, unless this frame is already
  ; too heavy to fit them (then the ground follows one frame later; never twice running)
  pha
  lda tbl_late
  cmp #TBL_MAXLATE
  bcs @now
  jsr LoadNow
  cmp #TBL_BUDGET
  bcc @now
  pla
  inc tbl_late
  inc tbl_skips
  bra @same
@now:
  stz tbl_late
  pla
  sta tbl_key
  jmp ComputeTables
@same:
  lda front
  sta c_buf
  rts

; ---------------------------------------------------------------- sprites
; sx, sy (signed), stile (0-511), sattr (vhoopppN without N), sbig
PutSpr:
  ldx oam_idx
  cpx #512
  bcs @out
  lda sx
  clc
  adc #64
  cmp #320
  bcs @out
  lda sy
  clc
  adc #64
  cmp #288
  bcs @out
  A8                        ; byte stores (graphics v1: ~18 cycles less per sprite)
  lda sx                    ; x, y, tile low, attr | tile bit 8
  sta oam_lo,x
  lda sy
  sta oam_lo+1,x
  lda stile
  sta oam_lo+2,x
  lda sattr
  and #$FE
  sta m_t
  lda stile+1
  and #1
  ora m_t
  sta oam_lo+3,x
  ; high table only when x bit 8 or the size bit is set
  lda sx+1
  and #1
  sta m_t
  lda sbig
  asl
  ora m_t
  A16                       ; (REP leaves Z alone)
  beq @nohi
  and #$0003
  sta m_t
  txa
  and #$000C
  ora m_t
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

BeginOam:
  stz oam_idx
  ldx #30
@c:
  stz oam_hi,x
  dex
  dex
  bpl @c
  rts

; hide the entries used last frame but not this one (the rest are already off screen)
FinishOam:
  ldx oam_idx
  A8
  lda #$E0
@l:
  cpx oam_prev
  bcs @d
  sta oam_lo+1,x
  inx
  inx
  inx
  inx
  bra @l
@d:
  A16
  lda oam_idx
  sta oam_prev
  rts

BuildFrame:
  AXY16
  jsr BeginOam
  lda view
  cmp #VIEW_OVER
  bne :+
  jsr BuildOver
  bra @f
: cmp #VIEW_COCK
  bne :+
  jsr BuildCock
  bra @f
: jsr BuildChase
@f:
  jsr FxCommit
  jmp FinishOam

; ---------------------------------------------------------------- clouds (perspective views)
ProjectClouds:
  AXY16
  lda b_gfx                 ; the boss sheet replaces the cloud tiles
  beq :+
  stz cl_n
  stz cl_cur
  rts
:
.ifdef NOCLOUDS
  stz cl_n
  stz cl_cur
  rts
.endif
  ldx lev
  lda f:CamH,x
  and #$00FF
  sta t6                    ; camera height
  stz cl_n
  stz cl_cur
  lda camu_x
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  sta campx
  lda camu_y
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  sta campy
  inc cl_par
  lda cl_rr                 ; two culled clouds get re-tested each frame
  clc
  adc #4
  and #(NUM_CLOUDS*2-1)
  sta cl_rr
  ldy #0
@loop:
  lda cl_vis,y
  beq @culled
  ; clouds farther than 120 px are re-projected every other frame; in between they
  ; continue at their measured screen velocity (covers yaw and forward parallax)
  lda cl_z,y
  cmp #120
  bcc @do0
  lda cl_vok,y
  beq @do0
  lda paused
  bne @do0
  tya
  lsr
  eor cl_par
  lsr
  bcc @do0
  lda cl_sx,y
  clc
  adc cl_vx,y
  sta cl_sx,y
  lda cl_sy,y
  clc
  adc cl_vy,y
  sta cl_sy,y
  lda cl_sx,y
  clc
  adc #64
  cmp #320
  bcc :+
  lda #$7FFF
  sta cl_z,y
: jmp @skip
@culled:
  lda #$7FFF
  sta cl_z,y
  tya
  eor cl_rr
  and #$FFFD                ; y == cl_rr or cl_rr+2
  beq @doc
  jmp @skip
@doc:
  lda #0
  sta cl_ok2,y
  bra @do
@do0:
  lda cl_z,y                ; remember last position for the velocity estimate
  cmp #$7FFF
  bne :+
  lda #0
  bra :++
: lda cl_sx,y
  sta cl_ox,y
  lda cl_sy,y
  sta cl_oy,y
  lda cl_b,y
  sta cl_ob,y
  lda #1
: sta cl_ok2,y
  lda #$7FFF                ; not drawn unless projected below
  sta cl_z,y
@do:
  lda cloud_y,y
  sec
  sbc campy
  jsr Wrap10
  jsr RelTrig
  lda t_ps
  sta t1                    ; ry*sin
  lda t_pc
  sta t0                    ; ry*cos
  lda cloud_x,y
  sec
  sbc campx
  jsr Wrap10
  jsr RelTrig
  lda t_ps
  sec
  sbc t0
  sta t2                    ; z = rx*sin - ry*cos
  lda t_pc
  clc
  adc t1
  sta t3                    ; x (lateral)
  ; coarse visibility (wide margin so a culled cloud is re-tested before it can appear)
  lda t2
  clc
  adc #16
  bmi @cull
  lda t2
  asl
  adc #56
  sta t0                    ; |x| < 2 z + 56 (view is |x| < 0.8 z; covers 8 frames of hard turning)
  lda t3
  jsr Abs
  cmp t0
  bcs @cull
  lda #1
  sta cl_vis,y
  lda t2
  bmi @skipj
  cmp #20
  bcs :+
@skipj:
  jmp @skip
@cull:
  lda #0
  sta cl_vis,y
  jmp @skip
:
  lda t6
  sec
  sbc cloud_h,y
  sta t4                    ; height difference (camera - cloud)
  lda t2
  asl
  tax
  lda f:RecipTab,x
  sta t5
  lda t3
  jsr ScaleR
  clc
  adc #128
  sta t0                    ; screen x of cloud centre
  lda t4
  jsr ScaleR
  clc
  adc #HOR
  sta t1                    ; screen y of cloud base
  ; choose sprite (arrays indexed by cloud id)
  lda cloud_shape,y
  and #2
  bne @small
  lda t2
  cmp #260
  bcs @small
  lda cloud_shape,y
  and #1
  beq :+
  lda tl_cb1
  bra :++
: lda tl_cb0
: sta cl_t,y
  lda #1
  sta cl_b,y
  lda t0
  sec
  sbc #32
  sta cl_sx,y
  lda t1
  sec
  sbc #40
  cmp #.loword(-64)
  bcs @bigok
  cmp #160
  bcc @bigok
  jmp @skip
@bigok:
  sta cl_sy,y
  jmp @keep
@small:
  lda view
  bne @sm32
  lda t2
  cmp #400
  bcc @sm32
  ; chase, far away: 16x16 half-size cloud
  lda cloud_shape,y
  and #1
  asl
  adc #T_CHASE_CLOUDT0
  sta cl_t,y
  lda #2
  sta cl_b,y
  lda t0
  sec
  sbc #8
  sta cl_sx,y
  lda t1
  sec
  sbc #10
  sta cl_sy,y
  bra @keep
@sm32:
  lda cloud_shape,y
  and #1
  beq :+
  lda tl_cs1
  bra :++
: lda tl_cs0
: sta cl_t,y
  lda #0
  sta cl_b,y
  lda t0
  sec
  sbc #16
  sta cl_sx,y
  lda t1
  sec
  sbc #20
  cmp #.loword(-32)
  bcs :+
  cmp #186
  bcs @skip
: sta cl_sy,y
@keep:
  lda cl_sx,y
  clc
  adc #64
  cmp #320
  bcs @skip
  lda t2
  sta cl_z,y
  ; screen velocity since the last projection (1 or 2 frames ago)
  lda cl_ok2,y
  beq @nov
  lda cl_b,y
  cmp cl_ob,y
  bne @nov
  lda cl_par
  sec
  sbc cl_ls,y
  and #$FF
  cmp #3
  bcs @nov
  tax
  lda cl_sx,y
  sec
  sbc cl_ox,y
  cpx #2
  bne :+
  cmp #$8000
  ror
: sta cl_vx,y
  lda cl_sy,y
  sec
  sbc cl_oy,y
  cpx #2
  bne :+
  cmp #$8000
  ror
: sta cl_vy,y
  lda #1
  bra :+
@nov:
  lda #0
: sta cl_vok,y
  lda cl_par
  sta cl_ls,y
@skip:
  iny
  iny
  cpy #NUM_CLOUDS*2
  beq :+
  jmp @loop
: ; insertion sort of the persistent order by z (nearly sorted from last frame: ~linear)
  CHK 17
  lda #NUM_CLOUDS*2
  sta cl_n
  ldx #2
@is:
  cpx cl_n
  bcs @sorted
  lda cl_order,x
  sta t6                    ; key
  tay
  lda cl_z,y
  sta t7                    ; key z
  txy
@in:
  dey
  dey
  bmi @ins
  phx
  lda cl_order,y
  tax
  lda cl_z,x
  plx
  cmp t7
  bcc @ins
  beq @ins
  lda cl_order,y
  sta cl_order+2,y
  bra @in
@ins:
  lda t6
  sta cl_order+2,y
  inx
  inx
  bra @is
@sorted:
  rts

Mul80:
  asl
  asl
  asl
  asl
  sta m_t
  asl
  asl
  clc
  adc m_t
  rts

; emit the next clouds (nearest first) with z < t7, continuing from cl_cur
EmitClouds:
  ldy cl_cur
@l:
  cpy cl_n
  bcs @d
  lda cl_order,y
  tax
  lda cl_z,x
  cmp t7
  bcs @d
  phy
  txy
  lda cl_sx,y
  sta sx
  lda cl_sy,y
  sta sy
  lda cl_t,y
  sta stile
  lda cl_b,y
  sta sbig
  lda cl_attr
  sta sattr
  jsr CloudSpr
  ply
  iny
  iny
  bra @l
@d:
  sty cl_cur
  rts

; chase (16/64 OBSEL): 32x32 clouds are 2x2 16x16s; cockpit (16/32): 64x64 clouds are 2x2 32x32s
CloudSpr:
  lda view
  cmp #VIEW_COCK
  beq @ck
  lda sbig
  cmp #2
  bne :+
  stz sbig                  ; far 16x16 cloud
  jmp PutSpr
: cmp #0
  bne @one
  lda #16
  sta q_p
  lda #2
  sta q_dx
  lda #32
  sta q_dy
  jmp PutQuad
@ck:
  lda sbig
  bne :+
  inc sbig                  ; 32x32 = large here
@one:
  jmp PutSpr
: lda #32
  sta q_p
  lda #4
  sta q_dx
  lda #64
  sta q_dy
  jmp PutQuad

; ---------------------------------------------------------------- chase view
BuildChase:
  AXY16
  lda #CAMBACK*64
  ldx sinv
  jsr MulSS
  sta t0
  lda posx
  sec
  sbc t0
  sta camu_x
  lda #CAMBACK*64
  ldx cosv
  jsr MulSS
  clc
  adc posy
  sta camu_y
  CHK 1
.ifdef CALIB
  CHK 18
  ldx #1000
: dex
  bne :-
  CHK 19
.endif
  jsr ProjectClouds
  CHK 2
  jsr ProjectObjects
  CHK 3
  ; objects + clouds in front of the jet
  jsr EmitFront
  CHK 5
  ; jet (gone while shot down / game over, blinking while invulnerable)
  lda p_dead
  ora gameover
  beq :+
  jmp @nojet
: lda p_inv
  and #4
  beq :+
  jmp @nojet
: lda #96
  clc
  adc c_shk
  sta sx
  lda #102
  sta sy
  lda #1
  sta sbig
  lda bankf
  jsr Abs
  asl
  tax
  lda f:ChaseJetTiles,x
  sta stile
  lda #$30
  ldx bankf
  bpl :+
  ora #$40
: sta sattr
  jsr PutSpr
  ; afterburner
  lda boost
  beq @nofl
  lda #120
  sta sx
  lda #150
  sta sy
  stz sbig
  lda frame
  and #2
  beq :+
  lda #T_CHASE_FLAME1
  bra :++
: lda #T_CHASE_FLAME0
: sta stile
  lda #$32
  sta sattr
  jsr PutSpr
@nofl:
  CHK 6
  jsr ChaseTrails
@nojet:
  CHK 7
  ; behind the jet: interleave objects and clouds by depth bands
  jsr EmitBack
  jsr BossDraw
  CHK 4
  jsr PerspCommon
  CHK 20
  rts

; wingtip contrails: 2 x 7 dots trailing toward the camera
ChaseTrails:
  lda bankf
  jsr Abs
  asl
  asl
  asl
  tax                       ; 8 bytes per frame entry: LX LY RX RY
  lda bankf
  bmi @flip
  lda f:WingTips,x
  sta t0
  lda f:WingTips+2,x
  sta t1
  lda f:WingTips+4,x
  sta t2
  lda f:WingTips+6,x
  sta t3
  bra @go
@flip:
  lda #63
  sec
  sbc f:WingTips+4,x
  sta t0
  lda f:WingTips+6,x
  sta t1
  lda #63
  sec
  sbc f:WingTips,x
  sta t2
  lda f:WingTips+2,x
  sta t3
@go:
  lda #$12
  sta sattr
  stz sbig
  stz tmpw                  ; acc = turnrate * k^2 (built by odd steps)
  lda turnrate
  sta m_div                 ; step = turnrate * (2k-1)
  ldy #1
@k:
  sty t4
  lda tmpw
  clc
  adc m_div
  sta tmpw
  lda m_div
  clc
  adc turnrate
  adc turnrate
  sta m_div
  ; lag = -(turnrate * k^2) >> 10
  lda tmpw
  xba
  and #$00FF
  cmp #$0080
  bcc :+
  ora #$FF00
: cmp #$8000
  ror
  cmp #$8000
  ror
  eor #$FFFF
  inc a
  sta t5
  ; tile by distance
  lda t4
  cmp #3
  bcs :+
  lda #T_CHASE_DOT0
  bra @tl
: cmp #5
  bcs :+
  lda #T_CHASE_DOT1
  bra @tl
: lda #T_CHASE_DOT2
@tl:
  sta stile
  ; vertical: tip + k*5
  lda t4
  asl
  asl
  clc
  adc t4
  sta t6
  ; left dot
  lda t4
  asl
  sta t7
  lda t0
  clc
  adc #96
  sec
  sbc t7
  clc
  adc t5
  sta sx
  lda t1
  clc
  adc #102
  clc
  adc t6
  sta sy
  jsr PutDot
  ; right dot
  lda t2
  clc
  adc #96
  clc
  adc t7
  clc
  adc t5
  sta sx
  lda t3
  clc
  adc #102
  clc
  adc t6
  sta sy
  jsr PutDot
  ldy t4
  iny
  cpy #8
  beq :+
  jmp @k
:
  rts

; small on-screen sprite fast path (contrail dots): no size bit, x in 0..255
PutDot:
  lda sx
  cmp #256
  bcc :+
  jmp PutSpr
: ldx oam_idx
  cpx #512
  bcs @out
  A8
  sta oam_lo,x
  lda sy
  sta oam_lo+1,x
  lda stile
  sta oam_lo+2,x
  lda stile+1
  ora sattr
  sta oam_lo+3,x
  A16
  txa
  clc
  adc #4
  sta oam_idx
@out:
  rts

Asr2:
  cmp #$8000
  ror
  cmp #$8000
  ror
  rts

; depth-ordered emission: band 0 = nearer than the chase jet, then 3 bands behind it
EmitFront:
  ldy #0
  jsr EmitObjs
  lda #40
  sta t7
  jmp EmitClouds
EmitBack:
  ldy #2
  jsr EmitObjs
  lda #150
  sta t7
  jsr EmitClouds
  ldy #4
  jsr EmitObjs
  lda #400
  sta t7
  jsr EmitClouds
  ldy #6
  jsr EmitObjs
  lda #$7FFF
  sta t7
  jmp EmitClouds

; ---------------------------------------------------------------- cockpit view
BuildCock:
  AXY16
  lda posx
  sta camu_x
  lda posy
  sta camu_y
  jsr ProjectClouds
  jsr ProjectObjects
  ; HUD crosshair
  lda #112
  sta sx
  lda #84
  sta sy
  lda #1
  sta sbig
  lda #T_COCK_CROSS
  sta stile
  lda #$34
  sta sattr
  jsr PutSpr
  ; pitch ladder (moves with climb): 16x16 pieces
  stz sbig
  lda climb
  asl
  asl
  asl
  clc
  adc #78
  sta sy
  lda #64
  sta sx
  lda #T_COCK_LADDER
  sta stile
  lda #$34
  sta sattr
  jsr PutSpr
  lda #176
  sta sx
  lda #$74
  sta sattr
  jsr PutSpr
  lda sy
  clc
  adc #36
  sta sy
  lda #T_COCK_LADDERD
  sta stile
  lda #$34
  sta sattr
  lda #64
  sta sx
  jsr PutSpr
  lda #80
  sta sx
  jsr PutSpr
  lda #160
  sta sx
  jsr PutSpr
  lda #176
  sta sx
  jsr PutSpr
  lda #1
  sta sbig
  ; attitude ball
  lda #112
  sta sx
  lda #166
  sta sy
  lda bankf
  jsr Abs
  sta t0
  asl
  adc t0                    ; *3
  sta t0
  lda climb
  inc a
  clc
  adc t0
  asl
  tax
  lda f:BallTiles,x
  sta stile
  lda #$34
  ldx bankf
  bpl :+
  ora #$40
: sta sattr
  jsr PutSpr
  ; radar sweep
  lda #18
  sta sx
  lda #172
  sta sy
  lda frame
  lsr
  lsr
  and #15
  asl
  tax
  lda f:SweepTab,x
  and #$01FF
  sta stile
  lda f:SweepTab,x
  xba
  and #$00C0
  ora #$34
  sta sattr
  jsr PutSpr
  ; canopy pillars: 6 x 16x16 per side, fixed: block-copied into the OAM buffer
  ; (x < 256 and small size, so the high table stays 0)
  lda oam_idx
  cmp #512-PILLAR_BYTES+1
  bcs @nopil
  clc
  adc #.loword(oam_lo)
  tay
  ldx #.loword(PillarOam)
  lda #PILLAR_BYTES-1
  phb
  mvn #^PillarOam, #$7E
  plb
  lda oam_idx
  clc
  adc #PILLAR_BYTES
  sta oam_idx
@nopil:
  ; enemies + clouds (behind dashboard: priority 1), nearest first
  jsr EmitFront
  jsr EmitBack
  jsr BossDraw
  ; digital readouts every 4 frames
  lda frame
  and #3
  bne :+
  jsr Readouts
: jmp PerspCommon

Readouts:
  ; ALT = 500 + alt*120/256 ... use lev*120 + 500
  lda alt
  lsr
  sta t0                    ; alt/2 (0..$1F80)
  lsr
  lsr
  lsr
  lsr
  sta t1
  lda t0
  sec
  sbc t1                    ; ~ alt*15/32
  clc
  adc #500
  ldy #0
  ldx #5
  jsr ToDigits
  lda speed
  asl
  clc
  adc #60
  ldy #10
  ldx #3
  jsr ToDigits
  lda #1
  sta dig_flag
  rts

; A = value, X = number of digits (5 or 3), Y = offset in digbuf
ToDigits:
  sta t0
  txa
  cmp #5
  beq :+
  lda #4                    ; 3 digits -> start at 100 (index 2*2)
  bra :++
: lda #0
: sta t1                    ; index into Pow10
@d:
  lda #0
  sta t2
  ldx t1
@s:
  lda t0
  cmp f:Pow10,x
  bcc @w
  sbc f:Pow10,x
  sta t0
  inc t2
  bra @s
@w:
  lda t2
  clc
  adc #FONT_0
  ora #$3400
  sta digbuf,y
  iny
  iny
  inc t1
  inc t1
  lda t1
  cmp #10
  bne @d
  rts

; ---------------------------------------------------------------- overhead view
; t0 = relx px, t1 = rely px  -> t2 = dx, t3 = dy (screen offsets at ground scale)
RotScale:
  ; rx: |rx| -> Y, hi*2 -> X, sign -> m_sign
  lda t0
  sta m_sign
  bpl :+
  eor #$FFFF
  inc a
: tay
  xba
  and #$00FF
  asl
  tax
  RPROD oc8, hi_c, cosv, t2       ; rx*C
  RPROD os8, hi_s, sinv, m_t2     ; rx*S
  lda t1
  sta m_sign
  bpl :+
  eor #$FFFF
  inc a
: tay
  xba
  and #$00FF
  asl
  tax
  RPROD oc8, hi_c, cosv, t3       ; ry*C
  RPROD os8, hi_s, sinv, m_t      ; ry*S
  lda t2
  clc
  adc m_t
  sta t2                    ; dx = rx*cos + ry*sin
  lda t3
  sec
  sbc m_t2
  sta t3                    ; dy = ry*cos - rx*sin
  rts

; per frame: o_s, o_c = |sin|, |cos| * (1 + inv/256) / 2  (fit in 8 bits; MulCS undoes the /2)
OverCoefs:
  ldx lev
  lda f:OverInv,x
  and #$00FF
  sta t4
  lda abs_cos
  ldx t4
  jsr MulSmall
  clc
  adc abs_cos
  lsr
  sta o_c
  lda abs_sin
  ldx t4
  jsr MulSmall
  clc
  adc abs_sin
  lsr
  sta o_s
  xba
  sta os8
  lda o_c
  xba
  sta oc8
  ; |v| >= 256 parts for RotScale: hi * 256 * o >> 7 = hi * 2o
  stz hi_s
  stz hi_c
  lda o_s
  asl
  sta hi_s+2
  asl
  sta hi_s+4
  lda o_c
  asl
  sta hi_c+2
  asl
  sta hi_c+4
  rts

; A = signed rel (|rel| <= 767) -> t_ps = rel*sin*k, t_pc = rel*cos*k (overhead ground scale)
MulCS:
  sta m_sign
  cmp #$8000
  bcc :+
  eor #$FFFF
  inc a
: sta m_a
  A8
  sta WRMPYA
  lda o_s
  sta WRMPYB
  nop
  nop
  nop
  nop
  ldx RDMPYL
  lda o_c
  sta WRMPYB
  nop
  nop
  nop
  nop
  ldy RDMPYL
  A16
  txa
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  sta t_ps
  tya
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  sta t_pc
  ldx m_a+1
  txa
  and #$00FF
  beq @nh
  tax
@h:
  lda o_s
  asl
  adc t_ps
  sta t_ps
  lda o_c
  asl
  adc t_pc
  sta t_pc
  dex
  bne @h
@nh:
  lda m_sign
  eor sinv
  bpl :+
  lda t_ps
  eor #$FFFF
  inc a
  sta t_ps
: lda m_sign
  eor cosv
  bpl :+
  lda t_pc
  eor #$FFFF
  inc a
  sta t_pc
: rts

BuildOver:
  AXY16
  lda posx
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  sta c_m7x
  sec
  sbc #128
  sta c_hofs
  lda posy
  lsr
  lsr
  lsr
  lsr
  lsr
  lsr
  sta c_m7y
  sec
  sbc #120
  sta c_vofs
  ldx lev
  lda f:OverS,x
  and #$00FF
  sta t5
  ldx cosv
  jsr MulSS
  sta c_ma
  sta c_md
  lda t5
  ldx sinv
  jsr MulSS
  sta c_mc
  eor #$FFFF
  inc a
  sta c_mb
  ; jet
  lda p_dead
  ora gameover
  bne @nojt
  lda p_inv
  and #4
  beq :+
@nojt:
  jmp @nofl
: lda #112
  clc
  adc c_shk
  sta sx
  lda #104
  sta sy
  stz sbig
  lda bankf
  jsr Abs
  asl
  tax
  lda f:OverJetTiles,x
  sta stile
  sta t7                    ; remember for shadow
  lda #$30
  ldx bankf
  bpl :+
  ora #$40
: sta sattr
  sta t6
  jsr PutSpr
  lda boost
  beq @nofl
  lda #110
  sta sy
  lda frame
  and #2
  beq :+
  lda #T_OVER_FLAME1
  bra :++
: lda #T_OVER_FLAME0
: sta stile
  lda #$32
  sta sattr
  jsr PutSpr
@nofl:
  CHK 1
  jsr OverCoefs
  jsr ProjectOver
  ldy #0
  jsr EmitObjs
  ldy #2
  jsr EmitObjs
  ldy #4
  jsr EmitObjs
  ldy #6
  jsr EmitObjs
  CHK 2
  ; clouds (+ remember shadows)
  ldy #0
@cl:
  sty loopi               ; scratch (loop index)
  lda cloud_x,y
  sec
  sbc pospx
  jsr Wrap10
  sta t0
  lda cloud_y,y
  sec
  sbc pospy
  jsr Wrap10
  sta t1
  ; far away in either axis: off screen at any heading (|v| * zoom > the screen corner + sprite)
  jsr Abs
  cmp #240
  bcc :+
  jmp @cull
:
  lda t0
  jsr Abs
  cmp #240
  bcc :+
  jmp @cull
:
  jsr RotScale
  ldy loopi
  lda cloud_shape,y
  and #2
  beq @big
  lda cloud_shape,y
  and #1
  beq :+
  lda tl_cs1
  bra :++
: lda tl_cs0
: sta stile
  stz sbig
  lda #16
  sta t4
  bra @pos
@big:
  lda cloud_shape,y
  and #1
  beq :+
  lda tl_cb1
  bra :++
: lda tl_cb0
: sta stile
  lda #1
  sta sbig
  lda #32
  sta t4
@pos:
  ; shadow at ground position + sun offset
  lda #128+10
  clc
  adc t2
  sec
  sbc t4
  sta sh_x,y
  lda #120+14
  clc
  adc t3
  sec
  sbc t4
  sta sh_y,y
  lda stile
  sta sh_t,y
  lda sbig
  sta sh_b,y
  ; cloud with parallax (x1.25)
  lda t2
  jsr Asr2
  clc
  adc t2
  clc
  adc #128
  sec
  sbc t4
  sta sx
  lda t3
  jsr Asr2
  clc
  adc t3
  clc
  adc #120
  sec
  sbc t4
  sta sy
  ; keep 64px sprites from wrapping into the top of the screen
  lda sbig
  beq :+
  lda sy
  bmi :+
  cmp #164
  bcs @nocl
: lda cl_attr
  sta sattr
  jsr PutSpr
  bra @nocl
@cull:
  ldy loopi
  lda #300                  ; shadow off screen too
  sta sh_y,y
@nocl:
  ldy loopi
  iny
  iny
  cpy #NUM_CLOUDS*2
  beq :+
  jmp @cl
:
  CHK 3
  ; contrails
  lda #$12
  sta sattr
  stz sbig
  lda #T_OVER_DOT
  sta stile
  ldy #0
@tr:
  sty t7
  lda hist_lx,y
  jsr TrailDot
  ldy t7
  lda hist_rx,y
  jsr TrailDotR
  ldy t7
  iny
  iny
  cpy #NHIST*2
  bne @tr
  CHK 4
  ; jet shadow (palette 4 = half-transparent black)
  lda p_dead
  ora gameover
  beq :+
  jmp @nosh0
: lda bankf
  jsr Abs
  asl
  tax
  lda f:OverJetTiles,x
  sta stile
  lda lev
  lsr
  lsr
  sta t0
  lda #112+6
  clc
  adc t0
  sta sx
  lda #104+10
  clc
  adc t0
  sta sy
  stz sbig
  lda #$38
  ldx bankf
  bpl :+
  ora #$40
: sta sattr
  jsr PutSpr
@nosh0:
  ; cloud shadows
  ldy #0
@sh:
  sty t7
  lda sh_x,y
  sta sx
  lda sh_y,y
  sta sy
  lda sbig
  lda sh_t,y
  sta stile
  lda sh_b,y
  sta sbig
  beq :+
  lda sy
  bmi :+
  cmp #164
  bcs @nosh
: lda #$38
  sta sattr
  jsr PutSpr
@nosh:
  ldy t7
  iny
  iny
  cpy #NUM_CLOUDS*2
  bne @sh
  rts

; A = world x (px) of a trail point; Y = history index
TrailDot:
  sec
  sbc pospx
  jsr Wrap10
  sta t0
  lda hist_ly,y
  bra TrailCommon
TrailDotR:
  sec
  sbc pospx
  jsr Wrap10
  sta t0
  lda hist_ry,y
TrailCommon:
  sec
  sbc pospy
  jsr Wrap10
  sta t1
  jsr RotScale
  lda t2
  clc
  adc #128
  sta sx
  lda t3
  clc
  adc #120
  sta sy
  lda #T_OVER_DOT
  sta stile
  lda #$12
  sta sattr
  stz sbig
  jmp PutSpr

.include "combat.s"
.include "boss.s"
.include "title.s"
.include "../music/build/apu_upload.inc"

; =====================================================================
.segment "RODATA"
ZeroByte: .byte 0
HiTab:    .byte 0,1,2,3, 0,4,8,12, 0,16,32,48, 0,64,128,192
.include "../assets/tables.inc"
.include "../assets/clouds.inc"
.include "../assets/frames.inc"

; =====================================================================
.segment "BANK1"
Persp:    .incbin "../assets/persp.bin"
Palette:  .incbin "../assets/palette.bin"
SinTab:   .incbin "../assets/sin.bin"
CamH:     .incbin "../assets/camh.bin"
OverS:    .incbin "../assets/overs.bin"
OverInv:  .incbin "../assets/overinv.bin"
Bg3Tiles: .incbin "../assets/bg3tiles.bin"
Bg3TilesEnd:
MapBg3:   .incbin "../assets/map_bg3.bin"
ChaseJetTiles: .word T_CHASE_JET0, T_CHASE_JET1, T_CHASE_JET2
OverJetTiles:  .word T_OVER_JET0, T_OVER_JET1, T_OVER_JET2
WingTips: .word WT0_LX, WT0_LY, WT0_RX, WT0_RY
          .word WT1_LX, WT1_LY, WT1_RX, WT1_RY
          .word WT2_LX, WT2_LY, WT2_RX, WT2_RY
KSquare:  .word 0, 1, 4, 9, 16, 25, 36, 49
BallTiles: .word T_COCK_BALL00, T_COCK_BALL01, T_COCK_BALL02
           .word T_COCK_BALL10, T_COCK_BALL11, T_COCK_BALL12
           .word T_COCK_BALL20, T_COCK_BALL21, T_COCK_BALL22
; radar sweep: low 9 bits tile, bits 14-15 = h/v flip (stored in hi byte bits 6-7)
SweepTab: .word T_COCK_SWEEP0, T_COCK_SWEEP1, T_COCK_SWEEP2, T_COCK_SWEEP3, T_COCK_SWEEP4
          .word T_COCK_SWEEP3|$8000, T_COCK_SWEEP2|$8000, T_COCK_SWEEP1|$8000, T_COCK_SWEEP0|$8000
          .word T_COCK_SWEEP1|$C000, T_COCK_SWEEP2|$C000, T_COCK_SWEEP3|$C000, T_COCK_SWEEP4|$C000
          .word T_COCK_SWEEP3|$4000, T_COCK_SWEEP2|$4000, T_COCK_SWEEP1|$4000
Pow10:    .word 10000, 1000, 100, 10, 1
; cockpit canopy pillars as ready-made OAM entries (x, y, tile, attr)
PillarOam:
.repeat 6, I
  .byte 0, 64+I*16, <T_COCK_PILLAR, $36|(>T_COCK_PILLAR & 1)
  .byte 240, 64+I*16, <T_COCK_PILLAR, $76|(>T_COCK_PILLAR & 1)
.endrepeat
PILLAR_BYTES = 48
; "PAUSED" with spaces, palette 4, priority
PausedStr: .word $3000, $3000|26, $3000|11, $3000|31, $3000|29, $3000|15, $3000|14, $3000, $3000, $3000

.segment "BANK2"
M7Map:    .incbin "../assets/m7map.bin"
M7Tiles:  .incbin "../assets/m7tiles.bin"

.segment "BANK3"
ObjChase: .incbin "../assets/obj_chase.bin"
ObjOver:  .incbin "../assets/obj_over.bin"

.segment "BANK4"
ObjCock:  .incbin "../assets/obj_cock.bin"
Bg2Tiles: .incbin "../assets/bg2tiles.bin"
Bg2TilesEnd:
MapText:  .incbin "../assets/map_text.bin"
MapCock:  .incbin "../assets/map_cock.bin"

; =====================================================================
.segment "HEADER"
.include "../assets/romname.inc"  ; "SUPER SKY FURY" padded to 21 (tools/title_art.py)
  .byte $30                       ; LoROM, FastROM
  .byte $00                       ; ROM only
  .byte $09                       ; 512 KB (boss v1)
  .byte $00                       ; no SRAM
  .byte $01                       ; North America
  .byte $00                       ; developer
  .byte $00                       ; version
  .word $FFFF                     ; checksum complement (fixed by build)
  .word $0000                     ; checksum

.segment "VECTORS"
  .word 0, 0
  .word .loword(EmptyHandler)     ; COP
  .word .loword(EmptyHandler)     ; BRK
  .word .loword(EmptyHandler)     ; ABORT
  .word .loword(NmiStub)          ; NMI
  .word 0
  .word .loword(EmptyHandler)     ; IRQ
  .word 0, 0
  .word .loword(EmptyHandler)     ; COP (emu)
  .word 0
  .word .loword(EmptyHandler)     ; ABORT (emu)
  .word .loword(EmptyHandler)     ; NMI (emu)
  .word .loword(Reset)            ; RESET
  .word .loword(EmptyHandler)     ; IRQ/BRK (emu)
