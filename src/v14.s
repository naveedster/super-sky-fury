; =====================================================================
;  SUPER SKY FURY v1.4 -- "make the graphics better and the gameplay more fun"
;  barrel roll (double-tap L / R: i-frames, side slip, a whoosh circling your head), charge shot
;  (hold X, release: a piercing blast), graze bonus (rounds that just miss: points + charge, a
;  close whoosh on that ear), stage rank (S/A/B/C), shockwave rings, smoke columns over wrecked
;  ground targets, gun muzzle flashes, water shimmer (palette cycling), ground targets tested
;  every frame. Included from main.s after v11.s; same conventions (XCODE bank, DB = $80).
; =====================================================================
ROLL_T   = 26               ; barrel roll length (frames)
ROLL_CD  = 12               ; ... and the pause before the next one
ROLL_DX  = 44               ; side slip per frame (1/16 px): 26 x 2.75 = 72 px
TAP_WIN  = 14               ; double-tap window (frames)
CH_FULL  = 40               ; hold X this long for a charged shot
CH_GRAZE = 12               ; charge banked per graze
CB_LIFE  = 34               ; charge blast range (frames)
CB_SPD   = 18*16            ; ... speed (1/16 px per frame)
PJ_BUSY  = 24               ; objects already listed: smoke/rings go light
K_ROLL   = 7                ; SFX follow kind: the roll whoosh circles your head
GRAZE_X  = 30*16            ; graze box half-width / half-height (1/16 px)
GRAZE_H  = 24*16
NRG      = 2                ; shockwave rings on screen
RG_LIFE  = 16
NSC      = 1                ; smoke columns
SC_LIFE  = 240
.include "../assets/v14.inc"

.segment "BSS"
itab_r:    .res 10
itab_d:    .res 160         ; v1.5 desert shimmer tables (2 x 79 bytes, stride 80)
itd_ok:    .res 2          ; v1.5 ch 3 ramp table: sky entry, 127 + 9 ground lines
ct_buf:    .res 56          ; v1.5 contrail OAM cache (main.s ChaseTrails)
roll_t:  .res 2
roll_d:  .res 2
roll_cd: .res 2
tap_l:   .res 2
tap_r:   .res 2
ch_t:    .res 2
ch_k:    .res 2
cb_t:    .res 2
cb_x:    .res 2
cb_z:    .res 2
cb_hit:  .res 2
cb_bh:   .res 2
mf_t:    .res 2
mf_s:    .res 2
gz_n:    .res 2
st_kills: .res 2
st_spawn: .res 2
st_hits: .res 2
rk_t:    .res 2
rk_st:   .res 2             ; 0 not shown, 1 showing, 2 done (this transition)
rk_a:    .res 24
rk_b:    .res 34
sw_req:  .res 2
rg_t:    .res NRG*2
rg_x:    .res NRG*2
rg_y:    .res NRG*2
sc_t:    .res NSC*2
sc_x:    .res NSC*2
sc_z:    .res NSC*2
pr_acc:  .res 2             ; your travel (1/16 px) since the prop list was last projected
pn_x:    .res PR_MAX*2
pc_x:    .res PR_MAX*2
x14_a:   .res 2
x14_b:   .res 2
nm15:    .res 2           ; v1.5 NMI scratch
x15_sx:  .res 2
x15_dx:  .res 2
x15_f:   .res 2
x15_i:   .res 2
x15_lv:  .res 2
x15_cga: .res 2
cl_fog:  .res 2
cur_band: .res 2
nm15b:   .res 2
x14_i:   .res 2
x14_k:   .res 2
x14_p:   .res 2
x14_hi:   .res 2
x14_hw:  .res 2
pc_mil:  .res PR_MAX*2
pc_nmil: .res 2
ct_tr2:  .res 2
p_wide:  .res 2

.segment "CODE"
T_BossMslHit: jsr BossMissileHit
              rtl
T_MulSS:      jsr MulSS
              rtl

T_PutSpr:     jsr PutSpr
              rtl

.segment "XCODE"
.a16
.i16
; ---------------------------------------------------------------- reset (new run / new stage)
X14_Reset:
  stz roll_t
  stz roll_cd
  stz ch_t
  stz ch_k
  stz cb_t
  stz mf_t
  ldx #NSC*2-2
: stz sc_t,x
  dex
  dex
  bpl :-
  ldx #NRG*2-2
: stz rg_t,x
  dex
  dex
  bpl :-
X14_StageStats:
  stz gz_n
  stz st_kills
  stz st_spawn
  stz st_hits
  stz rk_st
  stz rk_t
  .repeat NSC, I              ; leftover smoke and rings stay behind (no X: callers vary)
  stz sc_t+I*2
  .endrepeat
  .repeat NRG, I
  stz rg_t+I*2
  .endrepeat
  stz cb_t
  rtl

; ---------------------------------------------------------------- per physics step (CombatStep, after Hits)
X14_Step:
  .ifdef NOSTEP
  rtl
  .endif
  lda tap_l                  ; (all idle: skip the countdowns)
  ora tap_r
  ora roll_cd
  ora mf_t
  ora rk_t
  beq @t0
  lda tap_l
  beq :+
  dec tap_l
: lda tap_r
  beq :+
  dec tap_r
: lda roll_cd
  beq :+
  dec roll_cd
: lda mf_t
  beq :+
  dec mf_t
: lda rk_t
  beq @t0
  dec rk_t
@t0:
  lda p_dead
  ora gameover
  beq @in
  stz roll_t
  stz ch_t
  bra @noin
@in:
  lda joy_new                ; barrel roll: double-tap L or R
  and #(KEY_L|KEY_R)
  beq @nr
  and #KEY_L
  beq @nl
  lda tap_l
  beq @tl
  lda #$FFFF
  jsr StartRoll
  bra @nl
@tl:
  lda #TAP_WIN
  sta tap_l
@nl:
  lda joy_new
  and #KEY_R
  beq @nr
  lda tap_r
  beq @tr
  lda #1
  jsr StartRoll
  bra @nr
@tr:
  lda #TAP_WIN
  sta tap_r
@nr:
  lda joy
  and #KEY_X
  ora ch_t
  beq @noin
  jsr ChargeIn
@noin:
  lda roll_t
  beq @nroll
  dec roll_t
  bne :+
  lda #ROLL_CD
  sta roll_cd
: lda roll_d
  bmi :+
  lda #ROLL_DX
  bra :++
: lda #.loword(-ROLL_DX)
: jsr SlideAll
@nroll:
  lda cb_t
  beq :+
  jsr MoveBlast
: lda pr_acc                 ; how far you flew since the props were projected
  clc
  adc fwd
  sta pr_acc
  lda frame                  ; ground targets: every other frame, swept over 2 frames of travel
  lsr
  bcs :+
  jsr PropHits
: lda sc_t
  beq :+
  jsr MoveCols
:
  .ifdef NORG
  rtl
  .endif
  lda rg_t
  ora rg_t+2
  beq @rgz
  ldx #NRG*2-2               ; rings
: lda rg_t,x
  beq :+
  dec rg_t,x
: dex
  dex
  bpl :--
@rgz:
  lda frame                  ; water shimmer: next phase every 8 frames (written by the NMI)
  and #7
  bne :+
  lda frame
  lsr
  lsr
  lsr
  and #7
  inc a
  sta sw_req
: rtl

; A = direction (+1 right, $FFFF left)
StartRoll:
  ldx roll_t
  bne @r
  ldx roll_cd
  bne @r
  sta roll_d
  lda #ROLL_T
  sta roll_t
  stz tap_l
  stz tap_r
  lda #K_ROLL                ; jet rush circling your head: front, the roll side, behind, the other side
  sta sfx_nk
  lda #SB_FLYBY
  ldx #4
  ldy #ROLL_T+4
  jsl T_SfxB
@r:
  rts

; SfxPos (K_ROLL): t0 = x px, t1 = z px of the whoosh
X14_RollPos:
  lda #ROLL_T
  sec
  sbc roll_t
  cmp #ROLL_T
  bcc :+
  lda #ROLL_T-1
: asl
  tax
  lda f:RollSZ,x
  sta t1
  lda f:RollSX,x
  ldx roll_d
  bpl :+
  eor #$FFFF
  inc a
: sta t0
  rtl

; A = side slip (1/16 px): everything around you moves the other way, the ground too
SlideAll:
  sta x14_a
  ldx #NEN*2-2
: lda en_x,x
  sec
  sbc x14_a
  sta en_x,x
  dex
  dex
  bpl :-
  ldx #NEB*2-2
: lda eb_x,x
  sec
  sbc x14_a
  sta eb_x,x
  dex
  dex
  bpl :-
  ldx #NEM*2-2
: lda em_x,x
  sec
  sbc x14_a
  sta em_x,x
  dex
  dex
  bpl :-
  ldx #NDE*2-2
: lda de_x,x
  sec
  sbc x14_a
  sta de_x,x
  dex
  dex
  bpl :-
  ldx #NPU*2-2
: lda pu_x,x
  sec
  sbc x14_a
  sta pu_x,x
  dex
  dex
  bpl :-
  ldx #NSC*2-2
: lda sc_x,x
  sec
  sbc x14_a
  sta sc_x,x
  dex
  dex
  bpl :-
  lda cb_x
  sec
  sbc x14_a
  sta cb_x
  lda ms_x
  sec
  sbc x14_a
  sta ms_x
  lda x14_a                  ; your rounds (px)
  ASR4
  sta x14_b
  ldx #NBU*2-2
: lda bu_gx,x
  sec
  sbc x14_b
  sta bu_gx,x
  dex
  dex
  bpl :-
  lda x14_a                  ; the world: right = (cos, sin), posx/posy in 1/64 px
  asl
  asl
  ldx cosv
  jsl T_MulSS
  clc
  adc posx
  sta posx
  lda x14_a
  asl
  asl
  ldx sinv
  jsl T_MulSS
  clc
  adc posy
  sta posy
  rts

; ---------------------------------------------------------------- charge shot (hold X, release)
ChargeIn:
  lda joy
  and #KEY_X
  beq @rel
  lda ch_t
  bne :+
  lda ch_k                   ; grazes bank a head start
  sta ch_t
  stz ch_k
: lda ch_t
  cmp #CH_FULL
  bcs @r
  inc a
  sta ch_t
  cmp #CH_FULL
  bcc @r
  stz sfx_nfx                ; full: a bright bip in front of you
  lda #10
  sta sfx_nfz
  lda #K_FIX
  sta sfx_nk
  lda #SA_BEEP
  ldx #2
  ldy #8
  jsl T_SfxA
@r:
  rts
@rel:
  lda ch_t
  beq @r
  cmp #CH_FULL
  stz ch_t
  bcc @r
  lda cb_t
  bne @r
  lda #CB_LIFE
  sta cb_t
  stz cb_x
  lda #10*16
  sta cb_z
  stz cb_hit
  stz cb_bh
  lda #5
  jsr Shake
  lda #3
  jsr FlashMin
  lda #6
  sta mf_t
  lda #SA_MSL
  ldx #4
  ldy #24
  jsl T_SfxA
  rts

MoveBlast:
  lda cb_t
  bne :+
  rts
: dec cb_t
  bne :+
  rts
: lda cb_z
  jsl T_RotTerm
  eor #$FFFF
  sec
  adc cb_x
  sta cb_x
  lda cb_z
  clc
  adc #CB_SPD
  sta cb_z
  ldx #0                     ; every enemy in its path, once each
@e:
  lda en_st,x
  cmp #ST_LIVE
  bne @en
  lda f:Bit16,x
  and cb_hit
  bne @en
  lda en_z,x
  sec
  sbc cb_z
  clc
  adc #24*16
  cmp #(24+8)*16
  bcs @en
  lda en_x,x
  sec
  sbc cb_x
  jsr XAbs
  sta x14_a
  lda en_hw,x
  asl
  asl
  asl
  asl
  clc
  adc #22*16
  cmp x14_a
  bcc @en
  lda f:Bit16,x
  tsb cb_hit
  lda en_hp,x
  sec
  sbc #6
  bpl :+
  lda #0
: sta en_hp,x
  stx x14_i
  lda #4
  jsr FlashMin
  ldx x14_i
  jsl X_MissileHit
  ldx x14_i
@en:
  inx
  inx
  cpx #NEN*2
  bne @e
  lda b_st                   ; the boss: one big hit, the blast spends itself on him
  cmp #BS_FIGHT
  bne @nb
  lda b_z
  sec
  sbc cb_z
  clc
  adc #24*16
  cmp #32*16
  bcs @nb
  lda b_x
  sec
  sbc cb_x
  jsr XAbs
  cmp #56*16
  bcs @nb
  lda b_hp
  sec
  sbc #6
  bcs :+
  lda #0
: sta b_hp
  lda #5
  jsr FlashMin
  jsl T_BossMslHit
  stz cb_t
@nb:
  rts

; ---------------------------------------------------------------- grazes (MoveEB: a round crossing your wing line)
; X = tracer slot, it missed the hit box. Keeps X.
X14_Graze:
  lda eb_x,x
  jsr XAbs
  cmp #GRAZE_X
  bcs @r
  lda eb_h,x
  jsr XAbs
  cmp #GRAZE_H
  bcs @r
  lda #1
  bra Grazed
@r:
  rtl
; X = tracer slot that would have hit you, but you are invulnerable: rolling through it is a graze x2
X14_GrazeRoll:
  lda roll_t
  bne :+
  rtl
: lda #2
Grazed:
  sta x14_k
  stx x14_i
  lda p_dead
  ora gameover
  bne @x
  inc gz_n
  lda ch_k
  clc
  adc #CH_GRAZE
  cmp #CH_FULL-1
  bcc :+
  lda #CH_FULL-1
: sta ch_k
  lda x14_k
  jsl T_ScoreAdd
  ldx x14_i                  ; spark off your wing on that side, the rush tickles that ear
  lda eb_x,x
  bmi @l
  lda #128+22
  sta t0
  lda #SA_DEBRL
  bra @s
@l:
  lda #128-22
  sta t0
  lda #SA_DEBLR
@s:
  pha
  lda #130
  sta t1
  lda #0
  jsr FxAt
  pla
  ldx #2
  ldy #20
  jsl T_SfxA
@x:
  ldx x14_i
  rtl

; ---------------------------------------------------------------- weapon levels (P: 1 -> 3)
; X_LaneHit: hit half-width for enemy X (+4 px at LV3)
X14_HW:
  lda en_hw,x
  clc
  adc p_wide
  sta x14_hw
  rtl

; ---------------------------------------------------------------- ground targets, every frame
; The committed prop list (pc_*) was projected <= 2 frames ago; its depth is corrected by how far you
; flew since. Each round is swept over this frame's travel, so none tunnels through a target.
PropHits:
  lda pc_nmil                ; no standing military target in the list: nothing to hit
  bne :+
  rts
: lda b_gfx
  beq :+
  rts
: stz x14_i
@p:
  lda x14_i
  cmp pc_n
  bcc :+
  rts
: asl
  tax
  lda pc_mil,x               ; military, still standing (worked out at the commit)
  bne :+
  jmp @pn
: lda pr_acc
  ASR4
  eor #$FFFF
  sec
  adc pc_z,x
  sec
  sbc zoff
  sta x14_a                  ; depth ahead of you now (px)
  bpl :+
  jmp @pn
: lda pc_x,x
  sta x14_b
  lda lev                    ; higher = smaller targets on screen: a slightly wider net
  lsr
  lsr
  clc
  adc #18
  sta x14_k
  ldy #0
@b:
  lda bu_d,y
  beq @bn
  sec
  sbc x14_a
  clc
  adc #10
  cmp #14+4+20+20            ; crossed it during the last 2 frames' travel
  bcs @bn
  lda bu_x,y
  sec
  sbc x14_b
  jsr XAbs
  sta x14_p
  lda bu_ln,y                ; spread lanes widen the net
  and #6
  beq :+
  lda x14_p
  sec
  sbc #24
  bcc @hit
  sta x14_p
: lda x14_p
  cmp x14_k
  bcc @hit
@bn:
  iny
  iny
  cpy #NBU*2
  bne @b
  lda cb_t                   ; the charge blast flattens it
  bne :+
  jmp @pn
:
  lda cb_z
  ASR4
  sec
  sbc x14_a
  clc
  adc #12
  cmp #18+4+24+24
  bcs @pn
  lda cb_x
  ASR4
  sec
  sbc x14_b
  jsr XAbs
  cmp #36
  bcs @pn
  lda pc_id,x
  sta pr_i
  sta pr_hid
  lda #PROP_HP-1
  sta pr_hc
  ldy #$FFFF
  bra @strike
@hit:
  lda pc_id,x
  sta pr_i
@strike:
  lda x14_b
  sta pr_x
  lda x14_a
  sta x_dx
  lda pc_sx,x
  sta sx
  lda pc_gy,x
  sta pr_gy
  phx
  jsr PropStrike
  plx
  bcc @pn
  stz pc_mil,x
  lda #$FFFF                 ; destroyed: smoke where it stood until the next projection
  sta pc_u,x
  lda #F_X16C
  sta pc_fr,x
@pn:
  inc x14_i
  jmp @p

; X_Props commit: X = slot, pc_id,x just set -> pc_mil,x = 1 if a military prop still standing (X kept)
PcMil:
  stz pc_mil,x
  phx
  lda pc_id,x
  pha
  tax
  lda f:PropOff+4,x
  cmp #3
  bne @no
  pla
  pha
  jsr PrBit
  and pr_dead,x
  bne @no
  pla
  plx
  inc pc_mil,x
  inc pc_nmil
  rts
@no:
  pla
  plx
  rts

; PropStrike, destroyed: a smoke column rises over the wreck (pr_x, x_dx px)
X14_Column:
  ldx #0
: lda sc_t,x
  beq @ok
  inx
  inx
  cpx #NSC*2
  bne :-
  ldx #0                     ; all busy: replace the first
@ok:
  lda #SC_LIFE
  sta sc_t,x
  lda pr_x
  asl
  asl
  asl
  asl
  sta sc_x,x
  lda x_dx
  asl
  asl
  asl
  asl
  sta sc_z,x
  rts

MoveCols:
  ldx #0
@l:
  lda sc_t,x
  beq @n
  dec a
  sta sc_t,x
  stx x14_i
  lda sc_z,x
  jsl T_RotTerm
  ldx x14_i
  eor #$FFFF
  sec
  adc sc_x,x
  sta sc_x,x
  lda sc_z,x
  sec
  sbc fwd
  sta sc_z,x
  cmp #.loword(-40*16)
  bpl @n
  stz sc_t,x
@n:
  inx
  inx
  cpx #NSC*2
  bne @l
  rts

; FxAt kind 1 (big flash at t0/t1): a shockwave ring expands from it
X14_Ring:
  lda b_gfx                  ; (the fortress fight has its own big blasts: keeps the frame rate)
  beq :+
  rts
: ldx #0
: lda rg_t,x
  beq @ok
  inx
  inx
  cpx #NRG*2
  bne :-
  ldx #0
  lda rg_t+2
  cmp rg_t
  bcs @ok
  ldx #2
@ok:
  lda #RG_LIFE
  sta rg_t,x
  lda t0
  sta rg_x,x
  lda t1
  sta rg_y,x
  rts

; ---------------------------------------------------------------- end of ProjectObjects (chase / cockpit)
X14_Project:
  .ifdef NOPJ
  rtl
  .endif
  lda cb_t                   ; nothing of ours on screen: done
  ora sc_t
  ora rg_t
  ora rg_t+2
  bne :+
  rtl
: lda cb_t                   ; charge blast: a white-hot fireball with a flickering core
  beq @nb
  lda cb_x
  ASR4
  sta t0
  lda cb_z
  ASR4
  clc
  adc zoff
  sta t1
  lda hcam
  sta t2
  jsl T_Project
  bcc @nb
  lda frame
  and #2
  asl
  asl
  asl
  asl
  asl
  ora obj_pri
  sta o_a
  lda #F_X32A
  jsr AddO
  lda frame
  and #4
  asl
  asl
  asl
  asl
  ora obj_pri
  sta o_a
  lda #F_X16A
  jsr AddO
@nb:
  stz x14_hw                 ; a busy frame draws the light version (1 puff, half the ring sparks)
  lda ob_n
  cmp #PJ_BUSY*2
  bcc :+
  inc x14_hw
:
  .ifdef NOSMK
  jmp @smk
  .endif
  ldx #0                     ; smoke columns: puffs climbing and drifting downwind
@c:
  lda sc_t,x
  bne :+
  jmp @cn
: stx x14_i
  lda sc_x,x                 ; one projection at the base, the puffs scaled up from it
  ASR4
  sta t0
  lda sc_z,x
  ASR4
  clc
  adc zoff
  sta t1
  ldx lev
  lda f:CamH,x
  and #$00FF
  sta t2
  jsl T_Project
  bcs :+
  jmp @cs
: lda sx
  sta x14_a
  lda sy
  sta x14_b
  stz x14_k
@pf:
  lda frame
  lsr
  clc
  adc x14_k
  and #63
  sta x14_p                  ; height above the ground (px)
  jsl T_ScaleR               ; (t5 = this depth's reciprocal, from Project)
  sta x14_hi
  eor #$FFFF
  sec
  adc x14_b
  sta sy
  lda x14_hi
  lsr
  lsr
  clc
  adc x14_a
  sta sx
  lda obj_pri
  sta o_a
  lda x14_p
  cmp #10
  lda #F_X16C
  bcc :+
  lda #F_X16B
: jsr AddO
  lda x14_hw
  bne @cs
  lda x14_k
  clc
  adc #32
  sta x14_k
  cmp #63
  bcc @pf
@cs:
  ldx x14_i
@cn:
  inx
  inx
  cpx #NSC*2
  beq :+
  jmp @c
:
@smk:
  .ifdef NORGD
  rtl
  .endif
  ldx #0                     ; shockwave rings: 6 sparks flying out on a flattened circle
@r:
  lda rg_t,x
  bne @rgo
  jmp @rn
@rgo:
  stx x14_i
  lda #RG_LIFE
  sec
  sbc rg_t,x
  asl
  asl
  sta x14_k                  ; step * 12 (6 points x 2 bytes)
  asl
  clc
  adc x14_k
  sta x14_k
  lda #6
  sta x14_p
@rp:
  ldx x14_k
  lda f:RingTab,x
  and #$00FF
  cmp #$0080
  bcc :+
  ora #$FF00
: ldy x14_i
  clc
  adc rg_x,y
  sta sx
  lda f:RingTab+1,x
  and #$00FF
  cmp #$0080
  bcc :+
  ora #$FF00
: clc
  adc rg_y,y
  sta sy
  stz t1
  lda obj_pri
  sta o_a
  lda rg_t,y
  cmp #RG_LIFE-6
  lda #F_X16A
  bcs :+
  lda #F_HSPARK
: jsr AddO
  inc x14_k
  inc x14_k
  lda x14_hw
  beq :+
  inc x14_k
  inc x14_k
  dec x14_p
: dec x14_p
  beq :+
  bpl @rp
:
  ldx x14_i
@rn:
  inx
  inx
  cpx #NRG*2
  beq @rx
  jmp @r
@rx:
  rtl

; ---------------------------------------------------------------- jet frame during a roll (X_JetFrame)
X14_JetFrame:
  lda #ROLL_T
  sec
  sbc roll_t
  cmp #ROLL_T
  bcc :+
  lda #ROLL_T-1
: tax
  lda f:RollFr,x
  and #$00FF
  sta x14_a
  and #$0007
  sta js_want
  lda #T_CHASE_JETS
  sta stile
  lda x14_a
  and #$00C0
  ldx roll_d
  bpl :+
  eor #$0040
: ora #$30
  sta sattr
  rtl

; ---------------------------------------------------------------- NMI: water shimmer (6 colours)
; ---------------------------------------------------------------- v1.5: the jet's shadow on the ground
; the sun is behind / above (45 deg): the shadow falls ahead of the jet, alt px further out, so it is on
; screen at every altitude and shrinks / rises toward the horizon as you climb
; ---------------------------------------------------------------- v1.5: per-stage horizon band (force blank)
X15_Band:
  lda view
  cmp #VIEW_OVER
  bne :+
  rtl
: lda stage
  cmp cur_band
  bne :+
  rtl
: sta cur_band
  xba
  asl
  asl
  asl                        ; * 2048
  clc
  adc #.loword(BandTiles)
  sta x15_f
  A8
  lda #$80
  sta VMAIN
  lda #$01
  sta DMAP0
  lda #$18
  sta BBAD0
  lda #^BandTiles
  sta A1B0
  A16
  lda #$5800
  sta VMADDL
  lda x15_f
  sta A1T0L
  lda #2048
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
  lda cur_band               ; maps: 384 bytes per stage = 2 x 192
  asl
  asl
  asl
  asl
  asl
  asl
  asl                        ; * 128
  sta x15_f
  asl                        ; * 256
  clc
  adc x15_f                  ; * 384
  adc #.loword(BandMaps)
  sta x15_f
  lda #BG3_ROWS_VRAM0
  sta VMADDL
  lda x15_f
  sta A1T0L
  lda #192
  sta DAS0L
  A8
  lda #^BandMaps
  sta A1B0
  lda #1
  sta MDMAEN
  A16
  lda #BG3_ROWS_VRAM1
  sta VMADDL
  lda x15_f
  clc
  adc #192
  sta A1T0L
  lda #192
  sta DAS0L
  A8
  lda #1
  sta MDMAEN
  A16
@r:
  rtl

X15_Shadow:
.ifdef NOSHADOW
  rtl
.endif
  lda b_gfx                  ; (the boss sheet has no shadow tile)
  bne @r
  ldx lev
  lda f:ShadowY,x            ; precomputed ground-point projection per altitude level
  and #$00FF
  cmp #202
  bcs @r
  ldx oam_idx
  cpx #512-8+1
  bcs @r
  A8
  sta oam_lo+1,x
  sta oam_lo+5,x
  lda #112
  clc
  adc c_shk
  sta oam_lo,x
  adc #16
  sta oam_lo+4,x
  lda #<T_CHASE_SHADOW
  sta oam_lo+2,x
  sta oam_lo+6,x
  lda #$38 | >T_CHASE_SHADOW  ; palette 4 (black), priority 3
  sta oam_lo+3,x
  lda #$78 | >T_CHASE_SHADOW  ; h-flipped right half
  sta oam_lo+7,x
  A16
  txa
  clc
  adc #8
  sta oam_idx
@r:
  rtl

; ---------------------------------------------------------------- v1.5: cloud whiteout + low sun glare
; X15_Fog: a cloud right on the jet whites the picture out (via the flash colour constant, see FxCommit)
; t2 = cloud depth (< 64), t3 = lateral, t4 = camera - cloud height (the jet is 17 below the camera)
X15_Fog:
.ifdef NOFOG
  rtl
.endif
.ifndef FOGALL
  lda view                   ; chase view only (the jet sits 17 below the camera there)
  bne @r
.endif
  lda t2
  cmp #22
  bcc @r
  cmp #44
  bcs @r
  lda t3
  bpl :+
  eor #$FFFF
  inc a
: cmp #16
  bcs @r
  lda t4
  sec
  sbc #17
  bpl :+
  eor #$FFFF
  inc a
: cmp #18
  bcs @r
  lda #11
  sta cl_fog
@r:
  rtl

X15_Sun:
.ifdef NOSUN
  rtl
.endif
  lda cl_fog                 ; cloud whiteout, fading out (rides the flash colour constant)
  beq @nf
  dec cl_fog
@nf:
  lda #$2F                   ; colour math on BG1-4 + backdrop (the glare tables light the sky too)
  sta x15_cga
  stz x15_lv
  lda b_gfx
  bne @hz
  lda stage
  cmp #2
  bcs @hz                    ; ocean dawn + desert sunset only
  asl
  tax
  lda f:SunAz,x
  sec
  sbc c_b3h
  and #1023
  cmp #512
  bcc :+
  ora #$FC00
: clc
  adc #128
  sta x15_sx                 ; sun centre x
  clc
  adc #16
  cmp #288
  bcs @hz                    ; off screen
  lda x15_sx
  sec
  sbc #8
  sta sx
  lda #SUN_Y-8
  sta sy
  stz sbig
  lda #T_CHASE_X16A
  sta stile
  lda #$20                   ; palette 0, priority 2 (in front of the horizon band)
  sta sattr
  jsl T_PutSpr
  lda x15_sx                 ; glare level by how close to straight ahead
  sec
  sbc #128
  bpl :+
  eor #$FFFF
  inc a
: ldx #3
  cmp #36
  bcc @lv
  dex
  cmp #76
  bcc @lv
  dex
  cmp #124
  bcc @lv
  dex
@lv:
  stx x15_lv
@hz:
  lda stage                  ; ch 7 table = GlareTab[stage][level]
  asl
  asl
  ora x15_lv
  sta x15_f
  xba                        ; * 256
  sta x15_i
  lda x15_f
  asl
  asl
  asl
  asl                        ; * 16  (GL_SZ = $110)
  clc
  adc x15_i
  adc #.loword(GlareTab)
  sta stg_hz
  rtl
.assert GL_SZ = $110, error, "glare size"
SUN_Y = 40
SunAz:  .word 96, 900

; A = signed value (|A| < 256), x15_f = factor * 16 (< 256) -> A = A * f / 16
T_MulB16:
  cmp #$8000
  php
  bcc :+
  eor #$FFFF
  inc a
: A8
  sta WRMPYA
  lda x15_f
  sta WRMPYB
  nop
  nop
  nop
  nop
  A16
  lda RDMPYL
  lsr
  lsr
  lsr
  lsr
  plp
  bcc :+
  eor #$FFFF
  inc a
: rtl

X14_Nmi:
  .ifdef NONMI
  rtl
  .endif
  lda view                   ; v1.5: animated sky (chase): HDMA ch 6 -> next phase table every 4 frames
  bne @nsk
  lda nmi_count
  and #3
  bne @nsk
  lda nmi_count
  lsr
  lsr
  and #SKYPH_N-1
  sta nm15
  lda stage
  asl
  asl
  asl
  asl
  ora nm15                   ; stage * 16 + phase
  sta nm15
  asl
  asl
  asl
  asl
  asl
  sta nm15b                  ; * 32
  lda nm15
  xba                        ; * 256
  clc
  adc nm15b
  adc #.loword(SkyPh)        ; (SKYPH_SZ = $120)
.assert SKYPH_SZ = $120, error, "sky phase size"
  sta $4362
  A8
  lda #^SkyPh
  sta $4364
  A16
@nsk:
  lda sw_req
  bne :+
  rtl
: dec a
  stz sw_req
  sta nm15
  lda stage
  asl
  asl
  asl
  clc
  adc nm15                  ; stage * 8 + phase
  asl
  sta nm15                  ; * 2
  asl
  asl
  asl
  clc
  adc nm15                  ; * 18 (v1.5: 9 slots)
  tax
  A8
.repeat NSHIM, I
  lda #.ident(.sprintf("SHIM_I%d", I))
  sta CGADD
  lda f:ShimTab+I*2,x
  sta CGDATA
  lda f:ShimTab+I*2+1,x
  sta CGDATA
.endrepeat
  A16
  rtl

; ---------------------------------------------------------------- stage rank (X_WaveStage, before the fade)
; carry set = go on with the transition, clear = the rank is still on screen
X14_RankGate:
  .ifdef NORANK
  sec
  rtl
  .endif
  lda rk_st
  cmp #2
  bcs @go
  cmp #1
  beq @show
  jsr RankBuild
  lda #1
  sta rk_st
  lda #170
  sta rk_t
  clc
  rtl
@show:
  lda rk_t
  bne :+
  lda #2
  sta rk_st
@go:
  sec
  rtl
: clc
  rtl

RankBuild:
  ; points: kills / spawned (x100), -8 per hit taken, + grazes (up to 20)
  lda st_spawn
  bne :+
  lda #100
  bra @pc
: lda st_kills
  cmp st_spawn
  bcc :+
  lda #100
  bra @pc
: A8
  ldx st_kills
  lda #100
  sta WRMPYA
  txa
  sta WRMPYB
  A16
  nop
  nop
  nop
  lda RDMPYL
  sta WRDIVL
  A8
  lda st_spawn
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
  lda RDDIVL
@pc:
  sta x14_a
  lda st_hits
  asl
  asl
  asl
  eor #$FFFF
  sec
  adc x14_a
  sta x14_a
  lda gz_n
  cmp #20
  bcc :+
  lda #20
: clc
  adc x14_a
  ldy #FONT_S
  cmp #100
  bpl @rk
  ldy #FONT_A
  cmp #82
  bpl @rk
  ldy #FONT_B
  cmp #60
  bpl @rk
  ldy #FONT_C
@rk:
  sty x14_b
  ; "STAGE CLEAR  RANK X"
  ldx #.loword(rk_a)
  stx x14_p
  ldx #0
: lda f:RkTxtA,x
  and #$00FF
  cmp #$00FF
  beq :+
  jsr RkPut
  inx
  bra :-
: lda x14_b
  jsr RkPut
  lda #.loword(rk_a)
  jsr RkLen
  ; "KILLS nn/nn  GRAZE nn  HITS nn"
  ldx #.loword(rk_b)
  stx x14_p
  lda #FONT_K
  jsr RkPut
  lda #FONT_I
  jsr RkPut
  lda #FONT_L
  jsr RkPut
  jsr RkPut
  lda #FONT_S
  jsr RkPut
  lda #FONT_SP
  jsr RkPut
  lda st_kills
  jsr RkNum
  lda #FONT_SLASH
  jsr RkPut
  lda st_spawn
  jsr RkNum
  lda #FONT_SP
  jsr RkPut
  jsr RkPut
  lda #FONT_G
  jsr RkPut
  lda #FONT_R
  jsr RkPut
  lda #FONT_A
  jsr RkPut
  lda #FONT_Z
  jsr RkPut
  lda #FONT_E
  jsr RkPut
  lda #FONT_SP
  jsr RkPut
  lda gz_n
  jsr RkNum
  lda #FONT_SP
  jsr RkPut
  jsr RkPut
  lda #FONT_H
  jsr RkPut
  lda #FONT_I
  jsr RkPut
  lda #FONT_T
  jsr RkPut
  lda #FONT_S
  jsr RkPut
  lda #FONT_SP
  jsr RkPut
  lda st_hits
  jsr RkNum
  lda #.loword(rk_b)
  jsr RkLen
  lda #.loword(rk_a)
  sta msg_a
  lda #.loword(rk_b)
  sta msg_b
  lda #$3400
  sta msg_at
  lda #170
  jsr MsgSet
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
; append tile A to the text at x14_p (+1: the length byte)
RkPut:
  pha
  phx
  ldx x14_p
  A8
  sta a:$0001,x
  A16
  inc x14_p
  plx
  pla
  rts
; A = 0..99 -> two digits
RkNum:
  cmp #100
  bcc :+
  lda #99
: ldx #0
: cmp #10
  bcc :+
  sbc #10
  inx
  bra :-
: pha
  txa
  clc
  adc #FONT_0
  jsr RkPut
  pla
  clc
  adc #FONT_0
  jmp RkPut
; A = text start: length byte = x14_p - start
RkLen:
  sta x14_k
  lda x14_p
  sec
  sbc x14_k
  ldx x14_k
  A8
  sta a:$0000,x
  A16
  rts

RkTxtA: .byte FONT_S, FONT_T, FONT_A, FONT_G, FONT_E, FONT_SP, FONT_C, FONT_L, FONT_E, FONT_A, FONT_R, FONT_SP, FONT_SP
        .byte FONT_R, FONT_A, FONT_N, FONT_K, FONT_SP, $FF

; ---------------------------------------------------------------- data
RollFr: .byte $00,$01,$02,$02,$03,$03,$84,$83,$83,$82,$82,$81,$80,$C0,$C1,$C2,$C2,$C3,$C3,$44,$43,$43,$42,$42,$41,$40
RollSX: .word 4,12,19,25,30,33,34,33,30,25,19,12,4,.loword(-4),.loword(-12),.loword(-19),.loword(-25),.loword(-30)
        .word .loword(-33),.loword(-34),.loword(-33),.loword(-30),.loword(-25),.loword(-19),.loword(-12),.loword(-4)
RollSZ: .word 30,28,25,20,14,7,0,.loword(-7),.loword(-14),.loword(-20),.loword(-25),.loword(-28),.loword(-30),.loword(-30)
        .word .loword(-28),.loword(-25),.loword(-20),.loword(-14),.loword(-7),0,7,14,20,25,28,30
ShimTab: .incbin "../assets/shim.bin"
.pushseg
.segment "SKYB"
SkyPh: .incbin "../assets/skyph.bin"     ; v1.5: 4 stages x 16 animated sky tables
GlareTab: .incbin "../assets/glare.bin"
.segment "BANDB"
BandTiles: .incbin "../assets/bands.bin"   ; v1.5: 4 stages x 2 KB BG3 band tiles
BandMaps:  .incbin "../assets/bandmaps.bin"
RampTab:                                 ; v1.5: BG1VOFS ramp, RampTab[j] = 1120 - j
.repeat 1168, I
  .word (1120 - I) & $FFFF
.endrepeat  ; v1.5: 4 stages x 4 sun-glare levels of the haze table
.popseg
RingTab:
  .byte .lobyte(6),.lobyte(0),.lobyte(3),.lobyte(3),.lobyte(-3),.lobyte(3),.lobyte(-6),.lobyte(0),.lobyte(-3),.lobyte(-3),.lobyte(3),.lobyte(-3),.lobyte(9),.lobyte(0),.lobyte(4),.lobyte(5),.lobyte(-5),.lobyte(5),.lobyte(-9),.lobyte(0),.lobyte(-4),.lobyte(-5),.lobyte(5),.lobyte(-5)
  .byte .lobyte(12),.lobyte(1),.lobyte(5),.lobyte(7),.lobyte(-7),.lobyte(6),.lobyte(-12),.lobyte(-1),.lobyte(-5),.lobyte(-7),.lobyte(7),.lobyte(-6),.lobyte(15),.lobyte(1),.lobyte(6),.lobyte(9),.lobyte(-10),.lobyte(8),.lobyte(-15),.lobyte(-1),.lobyte(-6),.lobyte(-9),.lobyte(10),.lobyte(-8)
  .byte .lobyte(18),.lobyte(2),.lobyte(6),.lobyte(11),.lobyte(-12),.lobyte(9),.lobyte(-18),.lobyte(-2),.lobyte(-6),.lobyte(-11),.lobyte(12),.lobyte(-9),.lobyte(21),.lobyte(3),.lobyte(6),.lobyte(13),.lobyte(-15),.lobyte(10),.lobyte(-21),.lobyte(-3),.lobyte(-6),.lobyte(-13),.lobyte(15),.lobyte(-10)
  .byte .lobyte(24),.lobyte(5),.lobyte(6),.lobyte(15),.lobyte(-18),.lobyte(11),.lobyte(-24),.lobyte(-5),.lobyte(-6),.lobyte(-15),.lobyte(18),.lobyte(-11),.lobyte(27),.lobyte(6),.lobyte(5),.lobyte(17),.lobyte(-22),.lobyte(11),.lobyte(-27),.lobyte(-6),.lobyte(-5),.lobyte(-17),.lobyte(22),.lobyte(-11)
  .byte .lobyte(29),.lobyte(8),.lobyte(4),.lobyte(19),.lobyte(-25),.lobyte(12),.lobyte(-29),.lobyte(-8),.lobyte(-4),.lobyte(-19),.lobyte(25),.lobyte(-12),.lobyte(31),.lobyte(9),.lobyte(3),.lobyte(22),.lobyte(-29),.lobyte(12),.lobyte(-31),.lobyte(-9),.lobyte(-3),.lobyte(-22),.lobyte(29),.lobyte(-12)
  .byte .lobyte(33),.lobyte(11),.lobyte(1),.lobyte(24),.lobyte(-32),.lobyte(12),.lobyte(-33),.lobyte(-11),.lobyte(-1),.lobyte(-24),.lobyte(32),.lobyte(-12),.lobyte(35),.lobyte(13),.lobyte(-1),.lobyte(26),.lobyte(-36),.lobyte(12),.lobyte(-35),.lobyte(-13),.lobyte(1),.lobyte(-26),.lobyte(36),.lobyte(-12)
  .byte .lobyte(37),.lobyte(16),.lobyte(-3),.lobyte(27),.lobyte(-40),.lobyte(12),.lobyte(-37),.lobyte(-16),.lobyte(3),.lobyte(-27),.lobyte(40),.lobyte(-12),.lobyte(38),.lobyte(18),.lobyte(-6),.lobyte(29),.lobyte(-44),.lobyte(11),.lobyte(-38),.lobyte(-18),.lobyte(6),.lobyte(-29),.lobyte(44),.lobyte(-11)
  .byte .lobyte(39),.lobyte(20),.lobyte(-9),.lobyte(31),.lobyte(-48),.lobyte(11),.lobyte(-39),.lobyte(-20),.lobyte(9),.lobyte(-31),.lobyte(48),.lobyte(-11),.lobyte(40),.lobyte(23),.lobyte(-12),.lobyte(33),.lobyte(-52),.lobyte(10),.lobyte(-40),.lobyte(-23),.lobyte(12),.lobyte(-33),.lobyte(52),.lobyte(-10)

; BuildChase, right after the jet: muzzle flash at the firing gun, the charge glow at the nose
X14_JetFx:
  .ifdef NOJF
  rtl
  .endif
  lda mf_t
  beq @nm
  lda mf_s
  beq :+
  lda #128+4
  bra :++
: lda #128-20
: clc
  adc c_shk
  sta sx
  lda #118
  sta sy
  stz sbig
  lda #T_CHASE_X16A
  sta stile
  lda frame
  and #2
  asl
  asl
  asl
  asl
  asl
  ora #$30
  sta sattr
  jsl T_PutSpr
@nm:
  lda ch_t
  cmp #8
  bcc @r
  lda #120
  clc
  adc c_shk
  sta sx
  lda #108
  sta sy
  stz sbig
  lda #$30
  sta sattr
  lda ch_t
  cmp #CH_FULL
  bcc @half
  lda frame
  and #2
  beq :+
  lda #T_CHASE_X16A
  bra :++
: lda #T_CHASE_HSPARK
: sta stile
  jsl T_PutSpr
  rtl
@half:
  lda frame
  and #4
  beq @r
  lda #T_CHASE_HSPARK
  sta stile
  jsl T_PutSpr
  rtl
@r:
  rtl


.segment "CODE"                ; (what follows in main.s, e.g. ApuUpload, lives in bank 0)
