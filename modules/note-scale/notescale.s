| ============================================================================
| NOTE SCALE -- SCALE and ROOT on the two empty cells of MIDI NOTE SETUP.
|
| Stage one: make the two cells real. They store, they survive a track
| switch, and they save with the project. The scale NAMES and the keyboard
| in the blank box come next, on top of a foundation that is proven.
|
| WHY THE CELLS WERE INERT. A SETUP row's six cells are drawn from five
| per-slot tables (names, counts, formatters, cell-draw, and a 16-nibble
| enable mask). Poking all five makes a cell appear and its knob turn --
| and nothing more, because the panel's keymap LAYER carries a separate
| encoder table, and `a null encoder handler swallows the turn`
| (docs/firmware/PANEL.md). The value never reached storage.
|
| WHERE THE VALUE LIVES. There is no offset table. The renderer at
| 0x4003665c builds a cell's address as
|
|     *(0x46c82456) + 0x8f262 + part*0x18b2 + track*0x24 + CELL
|
| with the cell index added RAW, so a row's six cells are six consecutive
| bytes. MIDI NOTE SETUP is CHAN, BANK, PROG, ----, SBNK, ---- , so the two
| empty cells are +3 and +5. Both are zero in all sixteen banks, four parts
| and eight tracks of a real project, and neither is read from A0-A6
| anywhere in 0x40098000..0x400a6000.
|
| HOW A VALUE PERSISTS. Measured off the YES handler for this same row, at
| 0x4004af94..0x4004afe4 -- it is not enough to write one copy:
|
|     part store   DB + 0x8f262    + part*0x18b2 + track*0x24 + cell
|     shadow       0x100a53b0      + part*0x18b2 + track*0x24 + cell
|     dirty        DB + 0x95048   |= 1 << part
|     dirty        0x100b145e     |= 1 << part
|     dirty        DB + 0x9b332    = 1
|     dirty        0x100f8598      = 1
|
| modules/cc-map's README puts it exactly: "Without the dirty flags the Part
| store is inert." That is the whole of the bug the probes kept hitting.
| This module makes the same stores that firmware editor makes, in the same
| order, and the recipe is cc-map's -- credit there.
|
| THE HOOK. All six encoders of a SETUP row share one handler, 0x4003a8e8,
| named six times in the window layer's encoder table at 0x400bc60a
| (records of stride 0x16: index byte, then the handler). Its arguments are
| (encoder index, signed delta). Detouring it once covers the row; the stub
| acts only on cells 3 and 5, only while this window is open, and replays
| the displaced prologue for everything else.
|
| NOT MEASURED: any of it running.
| ============================================================================

        .set    WINOPEN,   0x400bc6c0   | non-zero while MIDI NOTE SETUP is up
        .set    CURTRACK,  0x100b14cc   | the current track, a byte
        .set    CURPART,   0x100b14cf   | the current part, a byte
        .set    DBPTR,     0x46c82456   | -> the loaded project buffer
        .set    PARTBASE,  0x8f262      | the MIDI row's base within it
        .set    SHADOW,    0x100a53b0   | the shadow copy's base
        .set    DIRTY_DB1, 0x95048      | DB + this |= 1 << part
        .set    DIRTY_ABS1, 0x100b145e  | |= 1 << part
        .set    DIRTY_DB2, 0x9b332      | DB + this = 1
        .set    DIRTY_ABS2, 0x100f8598  | = 1
        .set    TRACKSTEP, 0x24         | a track's block in the saved part
        .set    PARTSTEP,  0x18b2       | a part's stride in the buffer
        .set    ACCUM,     0x460d5cb4   | the row's live value, one long per
                                     | cell; the DRAW takes its low byte
        .set    LANE,      0x46c76de0   | the runtime mirror + 0x20
        .set    REDRAW,    0x40036548   | the row's draw routine
        .set    ENC_ON,    0x4003a8f0   | past the prologue we displace
        .set    CELL_SCALE, 3
        .set    CELL_ROOT,  5
        .set    MAX_SCALE, 35           | 0..35. Index 0 IS CHROMATIC, which is
                                        | this machine's OFF -- there is no
                                        | separate OFF state to leave room for.
        .set    MAX_ROOT,  11           | 0..11

        .global sc_enc
sc_enc:
        | (4,%sp) encoder index 0..5,  (8,%sp) signed delta.
        tst.l   WINOPEN
        beq.w   .Lstock                 | a different screen owns the knobs
        move.l  (4,%sp),%d0
        cmpi.l  #CELL_SCALE,%d0
        beq.s   .Lmine
        cmpi.l  #CELL_ROOT,%d0
        bne.w   .Lstock

.Lmine:
        | ColdFire MOVEM has no predecrement mode -- lea then (An), which
        | is why every stock prologue is written this way.
        lea     (-32,%sp),%sp           | 8 registers; args now +0x24/+0x28
        movem.l %d2-%d7/%a2-%a3,(%sp)
        move.l  (0x28,%sp),%d1          | the delta
        move.l  %d0,%d4                 | the cell, 3 or 5

        clr.l   %d2
        move.b  CURTRACK,%d2            | 1039, as 0x4004af28 reads it
        clr.l   %d3
        move.b  CURPART,%d3

        | %d5 = part*PARTSTEP + track*TRACKSTEP
        move.l  %d2,%d5
        lsl.l   #5,%d5                  | track*32
        move.l  %d2,%d6
        lsl.l   #2,%d6                  | track*4
        add.l   %d6,%d5                 | track*0x24
        move.l  #PARTSTEP,%d6
        muls.l  %d3,%d6                 | part*0x18b2  (as 0x4004af9e)
        add.l   %d6,%d5

        movea.l DBPTR,%a2               | the project buffer
        lea     (%a2,%d5.l),%a0
        adda.l  %d4,%a0
        adda.l  #PARTBASE,%a0           | the part store address

        | the new value: current + delta, clamped to this cell's range
        clr.l   %d7
        move.b  (%a0),%d7
        add.l   %d1,%d7
        bge.s   .Lhigh
        clr.l   %d7
.Lhigh:
        moveq   #MAX_ROOT,%d6
        cmpi.l  #CELL_SCALE,%d4
        bne.s   .Lclamp
        moveq   #MAX_SCALE,%d6
.Lclamp:
        cmp.l   %d6,%d7
        ble.s   .Lstore
        move.l  %d6,%d7

.Lstore:
        move.b  %d7,(%a0)               | *** the part store ***

        movea.l %d5,%a1                 | part*PARTSTEP + track*TRACKSTEP
        adda.l  #SHADOW,%a1
        adda.l  %d4,%a1
        move.b  %d7,(%a1)               | *** the shadow ***

        | the four dirty flags, without which the part store is inert
        moveq   #1,%d1
        lsl.l   %d3,%d1                 | 1 << part
        move.l  #DIRTY_DB1,%d5
        move.b  (%a2,%d5.l),%d0
        or.l    %d1,%d0
        move.b  %d0,(%a2,%d5.l)
        move.b  DIRTY_ABS1,%d0
        or.l    %d0,%d1
        move.b  %d1,DIRTY_ABS1
        moveq   #1,%d0
        move.l  #DIRTY_DB2,%d6
        move.l  %d0,(%a2,%d6.l)
        move.l  %d0,DIRTY_ABS2

        | THE LANE. The runtime mirror, which is the saved block + 0x20;
        | stock writes it at 0x4004aff8 as 0x46c76de0 + track*0x44 + cell.
        | Persistence does not need it -- the value already survived a reboot
        | without it -- but anything reading the block at RUNTIME reads here.
        move.l  %d2,%d0
        lsl.l   #6,%d0                  | track*64
        movea.l %d0,%a1
        lea     (%a1,%d2.l*4),%a0       | + track*4 = track*0x44
        adda.l  %d4,%a0                 | + cell
        adda.l  #LANE,%a0
        move.b  %d7,(%a0)

        | THE LIVE VALUE. The cell's number on screen does NOT come from the
        | part store -- the renderer reads this array (0x40036600 loads it,
        | 0x400366ac takes the low byte of the entry) and stock's own encoder
        | handler updates it at 0x4003a956. Writing storage alone left the
        | screen showing the old number until the page was left and re-entered,
        | which is exactly when this array is reloaded from storage.
        move.l  %d4,%d0
        lsl.l   #2,%d0                  | cell*4
        movea.l %d0,%a1
        adda.l  #ACCUM,%a1
        move.l  %d7,(%a1)

        | THE REDRAW. This is what was missing: the value changed and the
        | screen did not. cc-map leaves the redraw out on purpose, because a
        | CC arrives with no page in front of it -- its README says so. A
        | knob is the opposite case, and the stock editor calls the draw
        | routine explicitly at 0x4004b008 once its stores are done.
        |
        | Before the redraw: the scale just moved under this track's NOTE
        | page, so move its four note cells onto the new scale.
        bsr.w   sc_resnap
        jsr     REDRAW

        movem.l (%sp),%d2-%d7/%a2-%a3
        lea     (32,%sp),%sp
        clr.l   %d0
        rts

.Lstock:
        lea     (-16,%sp),%sp           | the displaced prologue, replayed
        movem.l %d2-%d3/%a2-%a3,(%sp)
        jmp     ENC_ON

| ---------------------------------------------------------------------------
| THE CELL FORMATTERS. A formatter is f(pos at 8(%fp), value at 12(%fp)); it
| replaces the value with a string pointer and tail-jumps the text routine.
| Same contract as the arp key-scale formatter at 0x4003b790, which this
| repository's ARP SCALES module already replaces the same way.
|
| The cell is four characters, so SCL draws the abbreviation -- MAJ, HARM,
| LY26. The full name belongs in the blank box, which is next.
| ---------------------------------------------------------------------------

        | The generated table at the foot of this file sets SCALE_COUNT too.
        | It is declared here as well so the compare below never depends on a
        | forward reference; dn2_scales.py --check fails if the two disagree.
        .set    SCALE_COUNT, 36
        .set    DRAWTEXT,   0x40013a08   | draw(dest, string), tail-callable
        .set    OUTOFRANGE, 0x400b442a   | stock's own out-of-range string

        .global sc_fmt_scale
sc_fmt_scale:
        link.w  %fp,#0
        move.l  (12,%fp),%d0
        cmpi.l  #SCALE_COUNT-1,%d0
        bhi.s   .Lsf_bad
        move.l  %d0,%d1                 | no pointer table: the abbreviations
        lsl.l   #2,%d1                  | are a five-byte stride, so the
        add.l   %d1,%d0                 | string is scale_abbr + 5*scale
        lea     scale_abbr:l,%a0
        adda.l  %d0,%a0
        move.l  %a0,%d0
        bra.s   .Lsf_go
.Lsf_bad:
        move.l  #OUTOFRANGE,%d0
.Lsf_go:
        move.l  %d0,(12,%fp)
        unlk    %fp
        jmp     DRAWTEXT

        .global sc_fmt_root
sc_fmt_root:
        link.w  %fp,#0
        move.l  (12,%fp),%d0
        cmpi.l  #11,%d0
        bhi.s   .Lrf_bad
        move.l  %d0,%d1                 | three bytes a root, the same way
        add.l   %d1,%d0
        add.l   %d1,%d0                 | root*3
        lea     scale_root:l,%a0
        adda.l  %d0,%a0
        move.l  %a0,%d0
        bra.s   .Lrf_go
.Lrf_bad:
        move.l  #OUTOFRANGE,%d0
.Lrf_go:
        move.l  %d0,(12,%fp)
        unlk    %fp
        jmp     DRAWTEXT

| ---------------------------------------------------------------------------
| THE NOTE KNOB. On the main NOTE page the knob steps one SCALE note per
| detent instead of one semitone, so only notes of the chosen scale can be
| selected at all.
|
| NO DETOUR. The firmware already has the extension point: a MIDI parameter
| page's descriptor carries a per-cell step function at descriptor+0x12a,
| and 0x40055008 -- the handler every encoder A..F is bound to in the base
| keymap layer at 0x400c085a -- calls it as
|
|     f(encoder, delta, value) -> the new value        (0x40055360)
|
| falling back to 0x4003240c when the entry is null. The MIDI NOTE page's
| descriptor is 0x400d3e3e (0x40031da4's jump table picks it for a MIDI
| track), its step table is 0x400d3f68, and slot 0 -- NOTE -- is null. Slot
| 2 is not: LEN carries 0x40040770, which is this same contract doing this
| same job for a cell whose values are not linear. So this module fills in
| one pointer where the firmware left a hole, and displaces nothing.
|
| The caller clamps the result to the cell's own minimum (0x400d3ea8, zero
| here) and maximum afterwards, so 0..127 is enforced whatever this returns.
|
| CHROMATIC -- scale 0, the machine's OFF -- tail-jumps the stock function
| with the arguments untouched, so the knob behaves exactly as it always did,
| encoder acceleration and all.
| ---------------------------------------------------------------------------

        .set    STOCKSTEP, 0x4003240c   | the stock add-and-clamp
        .set    NOTEBASE,  0x8f162      | the NOTE page's block, + track*32
        .set    SHADOW2,   0x100a52b0   | its shadow, + part*0x18b2 + track*32
        .set    LANE0,     0x46c76dc0   | its runtime lane, + track*0x44
        .set    TRACKSTEP2, 32          | a track's stride in that block
        .set    OFFSET_OFF, 64          | a chord offset of zero: the cell's OFF

        .global sc_step
sc_step:
        | (0x24,%sp) encoder, (0x28,%sp) delta, (0x2c,%sp) value -> %d0.
        lea     (-32,%sp),%sp
        movem.l %d2-%d7/%a2-%a3,(%sp)
        move.l  (0x2c,%sp),%d2          | the value
        move.l  (0x28,%sp),%d6          | the delta
        tst.l   %d6
        beq.w   .Lst_stock              | a turn of nothing is stock's business

        | SCL and ROT for this track, the two cells the SETUP page edits
        clr.l   %d0
        move.b  CURTRACK,%d0
        clr.l   %d1
        move.b  CURPART,%d1
        move.l  #PARTSTEP,%d5
        muls.l  %d1,%d5                 | part*0x18b2
        movea.l DBPTR,%a2
        adda.l  %d5,%a2                 | -> the part's block
        move.l  %d0,%d1
        lsl.l   #5,%d1                  | track*32
        move.l  %d0,%d5
        lsl.l   #2,%d5
        add.l   %d1,%d5                 | track*0x24
        lea     (%a2,%d5.l),%a3
        adda.l  #PARTBASE,%a3
        mvz.b   (CELL_SCALE,%a3),%d3
        beq.w   .Lst_stock              | CHROMATIC: every note is legal
        cmpi.l  #MAX_SCALE,%d3
        bhi.w   .Lst_stock              | junk in the byte: leave the knob be
        mvz.b   (CELL_ROOT,%a3),%d4
        cmpi.l  #MAX_ROOT,%d4
        bhi.w   .Lst_stock

        | the mask, rotated so bit k means `semitone k is in the scale`
        lea     scale_mask:l,%a3
        mvz.w   (%a3,%d3.l*2),%d3
        move.l  %d3,%d0
        lsl.l   %d4,%d0
        moveq   #12,%d1
        sub.l   %d4,%d1
        lsr.l   %d1,%d3
        or.l    %d0,%d3
        andi.l  #0xfff,%d3

        | Which cell? NOTE is the note itself. NOT2..NOT4 are offsets biased
        | by 64 from the track's own NOTE -- 0x4003baa8 adds them and draws
        | the result as a note name -- and an offset of zero is the cell's
        | OFF, which must stay reachable whatever the scale says.
        clr.l   %d7                     | %d7 = the bias: note = value + %d7
        movea.l #-1,%a3                 | no OFF stop on the NOTE cell
        move.l  (0x24,%sp),%d0
        cmpi.l  #2,%d0
        ble.s   .Lst_dir
        movea.l #OFFSET_OFF,%a3
        clr.l   %d1                     | track*32 again: the rotation above
        move.b  CURTRACK,%d1            | spent the register that held it
        lsl.l   #5,%d1
        lea     (%a2,%d1.l),%a0         | the NOTE page block, + track*32
        adda.l  #NOTEBASE,%a0
        mvz.b   (%a0),%d7               | this track's NOTE
        subi.l  #OFFSET_OFF,%d7

.Lst_dir:
        | the direction, and how many detents to serve
        moveq   #1,%d5
        tst.l   %d6
        bgt.s   .Lst_deg
        moveq   #-1,%d5
        neg.l   %d6
.Lst_deg:
        | the starting degree, by subtraction: ColdFire's remainder wants a
        | register pair, and the numbers here are tiny
        move.l  %d2,%d0
        add.l   %d7,%d0
.Lst_modlo:
        tst.l   %d0
        bge.s   .Lst_modhi
        addi.l  #12,%d0
        bra.s   .Lst_modlo
.Lst_modhi:
        cmpi.l  #12,%d0
        blt.s   .Lst_loop
        subi.l  #12,%d0
        bra.s   .Lst_modhi

.Lst_loop:
        move.l  %d2,%d4                 | where this detent started
.Lst_walk:
        add.l   %d5,%d2                 | one step of the stored value
        add.l   %d5,%d0                 | and the degree follows it
        bge.s   .Lst_wrap
        moveq   #11,%d0                 | walked down past C
.Lst_wrap:
        cmpi.l  #11,%d0
        ble.s   .Lst_range
        clr.l   %d0                     | walked up past B
.Lst_range:
        tst.l   %d2                     | the stored value stays 0..127
        blt.s   .Lst_back
        cmpi.l  #127,%d2
        bgt.s   .Lst_back
        cmpa.l  %d2,%a3
        beq.s   .Lst_take               | OFF is always a stop
        move.l  %d2,%d1                 | the note this value sounds
        add.l   %d7,%d1
        blt.s   .Lst_walk               | off the bottom: not a note
        cmpi.l  #127,%d1
        bgt.s   .Lst_walk
        btst    %d0,%d3
        beq.s   .Lst_walk               | not in the scale: keep walking
.Lst_take:
        subq.l  #1,%d6
        bne.w   .Lst_loop               | that is one detent served
        bra.s   .Lst_done
.Lst_back:
        move.l  %d4,%d2                 | ran off the keyboard: stay put
.Lst_done:
        move.l  %d2,%d0
        movem.l (%sp),%d2-%d7/%a2-%a3
        lea     (32,%sp),%sp
        rts

.Lst_stock:
        movem.l (%sp),%d2-%d7/%a2-%a3
        lea     (32,%sp),%sp
        jmp     STOCKSTEP               | our arguments are still in place

| ---------------------------------------------------------------------------
| SNAPPING. sc_snap moves one note onto the scale; sc_resnap moves the whole
| NOTE page there when SCL or ROT changes, so the page agrees with what the
| quantiser will play.
|
| Trigs already written into the pattern are deliberately NOT touched. They
| already SOUND in scale -- sc_lookup snaps every note at emit time -- and
| rewriting them would throw away the notes they were written with, which no
| change of scale could give back.
| ---------------------------------------------------------------------------

        .global sc_snap
sc_snap:
        | in: %d0 a note, %d3 the mask. out: %d0, the nearest note of the
        | scale, upward on a tie. Touches %d0, %d1, %d2 and %a0.
        movea.l %d0,%a0                 | where we started
        moveq   #0,%d1                  | the distance
.Lsn_try:
        move.l  %a0,%d0
        add.l   %d1,%d0
        bsr.s   .Lsn_ok
        bne.s   .Lsn_hit
        move.l  %a0,%d0
        sub.l   %d1,%d0
        bsr.s   .Lsn_ok
        bne.s   .Lsn_hit
        addq.l  #1,%d1
        cmpi.l  #6,%d1
        ble.s   .Lsn_try
        move.l  %a0,%d0                 | no scale note within six: leave it
.Lsn_hit:
        rts
.Lsn_ok:
        | in: %d0 a candidate. out: Z clear when it is a legal scale note.
        tst.l   %d0
        bmi.s   .Lsn_no
        cmpi.l  #127,%d0
        bgt.s   .Lsn_no
        move.l  %d0,%d2
.Lsn_mod:
        cmpi.l  #12,%d2
        blt.s   .Lsn_bit
        subi.l  #12,%d2
        bra.s   .Lsn_mod
.Lsn_bit:
        btst    %d2,%d3                 | Z set when the note is not in it
        rts
.Lsn_no:
        moveq   #0,%d2
        tst.l   %d2                     | Z set: not a legal note
        rts

        .global sc_resnap
sc_resnap:
        | Called from sc_enc the moment SCL or ROT changes. Writes the three
        | copies the firmware keeps of a NOTE-page parameter -- the part
        | store, the shadow and the runtime lane -- exactly as the stock
        | encoder handler does at 0x4005538a, 0x400553a2 and 0x400553e6. The
        | dirty flags are already set by the SCL or ROT store that preceded
        | this call.
        lea     (-40,%sp),%sp
        movem.l %d2-%d7/%a2-%a5,(%sp)

        clr.l   %d2
        move.b  CURTRACK,%d2
        clr.l   %d1
        move.b  CURPART,%d1
        move.l  #PARTSTEP,%d5
        muls.l  %d1,%d5                 | part*0x18b2
        move.l  %d2,%d6
        lsl.l   #5,%d6                  | track*32
        movea.l DBPTR,%a5

        | SCL and ROT, from the SETUP cells of this same track
        move.l  %d2,%d7
        lsl.l   #2,%d7
        add.l   %d6,%d7                 | track*0x24
        add.l   %d5,%d7
        lea     (%a5,%d7.l),%a0
        adda.l  #PARTBASE,%a0
        mvz.b   (CELL_SCALE,%a0),%d3
        beq.w   .Lrs_out                | CHROMATIC: nothing to snap
        cmpi.l  #MAX_SCALE,%d3
        bhi.w   .Lrs_out
        mvz.b   (CELL_ROOT,%a0),%d4
        cmpi.l  #MAX_ROOT,%d4
        bhi.w   .Lrs_out
        lea     scale_mask:l,%a0
        mvz.w   (%a0,%d3.l*2),%d3
        move.l  %d3,%d0
        lsl.l   %d4,%d0
        moveq   #12,%d1
        sub.l   %d4,%d1
        lsr.l   %d1,%d3
        or.l    %d0,%d3
        andi.l  #0xfff,%d3

        | the three copies
        move.l  %d5,%d7
        add.l   %d6,%d7                 | part*0x18b2 + track*32
        lea     (%a5,%d7.l),%a2
        adda.l  #NOTEBASE,%a2           | the part store
        movea.l %d7,%a3
        adda.l  #SHADOW2,%a3            | the shadow
        move.l  %d2,%d7
        lsl.l   #6,%d7
        move.l  %d2,%d0
        lsl.l   #2,%d0
        add.l   %d0,%d7                 | track*0x44
        movea.l %d7,%a4
        adda.l  #LANE0,%a4              | the runtime lane

        | NOTE first: the chord offsets are measured from it
        mvz.b   (%a2),%d0
        bsr.w   sc_snap
        move.l  %d0,%d4
        move.b  %d4,(%a2)
        move.b  %d4,(%a3)
        move.b  %d4,(%a4)

        | then the three chord offsets, which are biased by 64
        moveq   #3,%d5
.Lrs_chord:
        mvz.b   (%a2,%d5.l),%d6
        cmpi.l  #OFFSET_OFF,%d6
        beq.s   .Lrs_next               | OFF stays OFF
        move.l  %d6,%d0
        subi.l  #OFFSET_OFF,%d0
        add.l   %d4,%d0                 | the note it sounds
        tst.l   %d0
        blt.s   .Lrs_next
        cmpi.l  #127,%d0
        bgt.s   .Lrs_next
        bsr.w   sc_snap
        sub.l   %d4,%d0
        addi.l  #OFFSET_OFF,%d0         | back to an offset
        tst.l   %d0
        blt.s   .Lrs_next
        cmpi.l  #127,%d0
        bgt.s   .Lrs_next
        cmpi.l  #OFFSET_OFF,%d0
        beq.s   .Lrs_next               | never snap a sounding note into OFF
        move.b  %d0,(%a2,%d5.l)
        move.b  %d0,(%a3,%d5.l)
        move.b  %d0,(%a4,%d5.l)
.Lrs_next:
        addq.l  #1,%d5
        cmpi.l  #5,%d5
        ble.w   .Lrs_chord
.Lrs_out:
        movem.l (%sp),%d2-%d7/%a2-%a5
        lea     (40,%sp),%sp
        rts

| ---------------------------------------------------------------------------
| THE BOX. MIDI NOTE SETUP draws six cells, all of them at x 53 or beyond
| (the row loop puts column c at x = 53 + c*20, each 18 wide). A solid
| divider runs down x 52, drawn by 0x40011b94(surface, 0x34, 2, 0x36, 1).
| Everything left of it -- x 3..51, y 3..53 -- is empty on this page, which
| is the space this draws the scale into.
|
| THE HOOK is the row's own draw routine, 0x40036548. It takes no arguments
| (it ends `lea (0x34,%sp),%sp; rts` with nothing above the frame), so the
| stub can call the stock body through a replay trampoline with BSR and get
| control back afterwards. Afterwards matters: the first thing the stock
| body does is clear the whole window interior with
| 0x40012254(surface, 3, 3, 0x6e, 0x35, 0), so anything drawn first would be
| erased. sc_enc already calls this routine after a knob turn, so the box
| follows the value with no second hook.
|
| THE PRIMITIVES, all read off their own prologues and their stock callers:
|   0x40012254(surface, x1, y1, x2, y2, mode)   filled rectangle.
|       mode < 0 EORs the pixels, mode & 1 ORs them, otherwise it clears
|       them (0x40012322: `tst.l (0x40,%sp)`, then the three loops).
|   0x40012bd8(font, surface, x, y, -1, string) text. A null string draws
|       nothing -- it is tested at 0x40012be8 -- which is what an empty
|       second name line relies on.
|   0x40012f30(font, -1, string) -> %d0         the string's width in
|       pixels, so a line can be centred. The panel font at 0x400ba876 is
|       three pixels a glyph plus one of spacing: eleven characters is 43,
|       and the box is 49 wide.
|
| WHERE IT READS THE VALUE. Not the live array at 0x460d5cb4 -- that holds
| the last edited value, which the renderer uses only to decide which cell
| to highlight. The number a cell DRAWS comes from the part store, and this
| reads the same two bytes the same way, including taking the track and part
| from 0x80000000 and 0x80000003 as the renderer does at 0x40036564.
| ---------------------------------------------------------------------------

        .set    RECT,      0x40012254   | rect(surface, x1,y1,x2,y2, mode)
        .set    TEXT,      0x40012bd8   | text(font, surface, x,y, -1, str)
        .set    TEXTW,     0x40012f30   | width(font, -1, str) -> %d0
        .set    FONT,      0x400ba876   | the panel font
        .set    DRAWTRACK, 0x80000000   | the renderer's own track byte
        .set    DRAWPART,  0x80000003   | and its part byte
        .set    DRAW_ON,   0x40036550   | past the prologue we displace

        .set    BOX_L,     3            | the blank box: x 3..51, y 3..53
        .set    BOX_MID,   27
        | THE Y AXIS RUNS BOTTOM-UP. The stock row draws row 0's name at y 48
        | in a six-pixel font (0x400ba87a) and the window interior ends at 53:
        | 48+5 = 53, so 48 is the BOTTOM of those glyphs and 53 the top of the
        | box. Row 0 is the upper cell row and carries the larger y. Every
        | coordinate below is written that way, and so is kbd_rect.
        .set    LINE1_Y,   48           | the name, on the top line
        .set    LINE2_Y,   41           | and its second line just below
        .set    MARK_Y0,   5            | the root's tick, BELOW the keys
        .set    MARK_Y1,   7
        .set    BLACKKEYS, 0x54a        | semitones 1,3,6,8,10

        .global sc_draw
sc_draw:
        bsr.w   .Lstockdraw             | the stock row first; it clears
        lea     (-40,%sp),%sp
        movem.l %d2-%d7/%a2-%a5,(%sp)

        movea.l WINOPEN,%a0
        move.l  %a0,%d0
        beq.w   .Ldone
        lea     (0x24,%a0),%a2          | the surface, as 0x4003655c makes it

        | the cell address, exactly as the renderer builds it at 0x4003665c
        clr.l   %d0
        move.b  DRAWTRACK,%d0
        move.l  %d0,%d1
        lsl.l   #5,%d1
        lsl.l   #2,%d0
        add.l   %d1,%d0                 | track*0x24
        clr.l   %d1
        move.b  DRAWPART,%d1
        move.l  #PARTSTEP,%d7
        muls.l  %d1,%d7                 | part*0x18b2
        add.l   %d7,%d0
        movea.l DBPTR,%a0
        adda.l  %d0,%a0
        adda.l  #PARTBASE,%a0
        mvz.b   (CELL_SCALE,%a0),%d5
        mvz.b   (CELL_ROOT,%a0),%d4

        | An old project could hold anything in these two bytes. Clamp
        | rather than index off the end of a table.
        cmpi.l  #MAX_SCALE,%d5
        bls.s   .Ldr_sok
        clr.l   %d5
.Ldr_sok:
        cmpi.l  #MAX_ROOT,%d4
        bls.s   .Ldr_rok
        clr.l   %d4
.Ldr_rok:

        | The mask is written with the root at bit 0. The keyboard is
        | absolute, C at the left, so rotate it up by the root: bit k of
        | %d3 is now `semitone k is in the scale`.
        lea     scale_mask:l,%a0
        mvz.w   (%a0,%d5.l*2),%d3
        move.l  %d3,%d0
        lsl.l   %d4,%d0
        moveq   #12,%d1
        sub.l   %d4,%d1
        lsr.l   %d1,%d3                 | root 0 shifts it out entirely
        or.l    %d0,%d3
        andi.l  #0xfff,%d3

        | the name, on two lines, each centred
        lea     scale_l1tab:l,%a0
        movea.l (%a0,%d5.l*4),%a3
        moveq   #LINE1_Y,%d7
        bsr.w   .Lcentred
        | The second line is not in a table of its own -- it follows the
        | first, just past its terminator.
.Ldr_adv:
        tst.b   (%a3)+
        bne.s   .Ldr_adv
        moveq   #LINE2_Y,%d7
        bsr.w   .Lcentred

        | ------------------------------------------------------------------
        | THE KEYBOARD. A keyboard, not twelve boxes: one lit slab, the white
        | keys cut apart by a one-pixel gap, the black keys cut out of it,
        | and a dot on every note of the scale -- dark on a white key, lit on
        | a black one. Outlines were tried first and turned into a lattice
        | you cannot count.
        | ------------------------------------------------------------------
        lea     kbd_body:l,%a3
        pea     1                       | the slab
        mvz.b   (3,%a3),%d0
        move.l  %d0,-(%sp)
        mvz.b   (2,%a3),%d0
        move.l  %d0,-(%sp)
        mvz.b   (1,%a3),%d0
        move.l  %d0,-(%sp)
        mvz.b   (%a3),%d0
        move.l  %d0,-(%sp)
        move.l  %a2,-(%sp)
        jsr     RECT
        lea     (24,%sp),%sp

        | the six gaps between the white keys, one pixel each
        clr.l   %d2
.Ldr_sep:
        lea     kbd_sep:l,%a3
        mvz.b   (%a3,%d2.l),%d6
        lea     kbd_body:l,%a3
        clr.l   -(%sp)                  | mode 0 clears
        mvz.b   (3,%a3),%d0
        move.l  %d0,-(%sp)
        move.l  %d6,-(%sp)              | x2 = x1: a one-pixel column
        mvz.b   (1,%a3),%d0
        move.l  %d0,-(%sp)
        move.l  %d6,-(%sp)
        move.l  %a2,-(%sp)
        jsr     RECT
        lea     (24,%sp),%sp
        addq.l  #1,%d2
        cmpi.l  #5,%d2
        ble.w   .Ldr_sep

        | the five black keys cut out, and every scale note dotted
        clr.l   %d2
.Ldr_key:
        move.l  #BLACKKEYS,%d0
        btst    %d2,%d0
        beq.s   .Ldr_dot
        lea     kbd_rect:l,%a3
        move.l  %d2,%d0
        lsl.l   #2,%d0
        adda.l  %d0,%a3
        clr.l   -(%sp)                  | mode 0: the black key is a hole
        mvz.b   (3,%a3),%d0
        move.l  %d0,-(%sp)
        mvz.b   (2,%a3),%d0
        move.l  %d0,-(%sp)
        mvz.b   (1,%a3),%d0
        move.l  %d0,-(%sp)
        mvz.b   (%a3),%d0
        move.l  %d0,-(%sp)
        move.l  %a2,-(%sp)
        jsr     RECT
        lea     (24,%sp),%sp
.Ldr_dot:
        btst    %d2,%d3
        beq.s   .Ldr_next               | not in the scale
        lea     kbd_dotmode:l,%a3
        mvz.b   (%a3,%d2.l),%d6         | 0 on a white key, 1 on a black one
        lea     kbd_dot:l,%a3
        move.l  %d2,%d0
        lsl.l   #2,%d0
        adda.l  %d0,%a3
        move.l  %d6,-(%sp)
        mvz.b   (3,%a3),%d0
        move.l  %d0,-(%sp)
        mvz.b   (2,%a3),%d0
        move.l  %d0,-(%sp)
        mvz.b   (1,%a3),%d0
        move.l  %d0,-(%sp)
        mvz.b   (%a3),%d0
        move.l  %d0,-(%sp)
        move.l  %a2,-(%sp)
        jsr     RECT
        lea     (24,%sp),%sp
.Ldr_next:
        addq.l  #1,%d2
        cmpi.l  #11,%d2
        ble.w   .Ldr_key

        | the root, ticked under its own key
        lea     kbd_rect:l,%a3
        move.l  %d4,%d0
        lsl.l   #2,%d0
        adda.l  %d0,%a3
        pea     1
        pea     MARK_Y1
        mvz.b   (2,%a3),%d0
        move.l  %d0,-(%sp)
        pea     MARK_Y0
        mvz.b   (%a3),%d0
        move.l  %d0,-(%sp)
        move.l  %a2,-(%sp)
        jsr     RECT
        lea     (24,%sp),%sp

.Ldone:
        movem.l (%sp),%d2-%d7/%a2-%a5
        lea     (40,%sp),%sp
        rts

.Lcentred:
        | %a3 -> the string, %d7 = y, %a2 the surface. An empty or null
        | string draws nothing, which is what a one-word scale name gets.
        move.l  %a3,%d0
        beq.s   .Lcen_ret
        tst.b   (%a3)
        beq.s   .Lcen_ret
        move.l  %a3,-(%sp)
        pea     0xffff                | -1: no length limit
        pea     FONT
        jsr     TEXTW
        lea     (12,%sp),%sp
        asr.l   #1,%d0                  | half the width
        move.l  #BOX_MID,%d1
        sub.l   %d0,%d1
        cmpi.l  #BOX_L,%d1
        bge.s   .Lcen_x
        moveq   #BOX_L,%d1              | never start left of the box
.Lcen_x:
        move.l  %a3,-(%sp)
        pea     0xffff
        move.l  %d7,-(%sp)
        move.l  %d1,-(%sp)
        move.l  %a2,-(%sp)
        pea     FONT
        jsr     TEXT
        lea     (24,%sp),%sp
.Lcen_ret:
        rts

.Lstockdraw:
        lea     (-0x34,%sp),%sp         | the displaced prologue, replayed
        movem.l %d2-%d7/%a2-%a6,(%sp)
        jmp     DRAW_ON

| ---------------------------------------------------------------------------
| The scale tables, generated by modules/scales/dn2_scales.py and INLINED
| rather than .include'd: the build assembles from the repository root, and
| an .include there once picked up a stray copy of an older table.
| ---------------------------------------------------------------------------
| Generated by dn2_scales.py -- do not edit by hand.
| The Digitone II's thirty-six keyboard scales, Appendix E order.
| Index 0 is CHROMATIC, which is this machine's OFF.

        .set    SCALE_COUNT, 36

| Twelve signed deltas per scale, scale-major.
        .align  2
scale_ut:
        .byte      0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0    | CHRO CHROMATIC
        .byte      0,   -1,    0,   -1,    0,    0,   -1,    0,   -1,    0,   -1,    0    | MAJ  IONIAN (MAJOR)
        .byte      0,   -1,    0,    0,   -1,    0,   -1,    0,   -1,    0,    0,   -1    | DOR  DORIAN
        .byte      0,    0,   -1,    0,   -1,    0,   -1,    0,    0,   -1,    0,   -1    | PHR  PHRYGIAN
        .byte      0,   -1,    0,   -1,    0,   -1,    0,    0,   -1,    0,   -1,    0    | LYD  LYDIAN
        .byte      0,   -1,    0,   -1,    0,    0,   -1,    0,   -1,    0,    0,   -1    | MIX  MIXOLYDIAN
        .byte      0,   -1,    0,    0,   -1,    0,   -1,    0,    0,   -1,    0,   -1    | MIN  AEOLIAN (MINOR)
        .byte      0,    0,   -1,    0,   -1,    0,    0,   -1,    0,   -1,    0,   -1    | LOC  LOCRIAN
        .byte      0,   -1,    1,    0,   -1,    0,   -1,    0,   -1,    1,    0,   -1    | PMIN PENTATONIC MINOR
        .byte      0,   -1,    0,   -1,    0,   -1,    1,    0,   -1,    0,   -1,   -2    | PMAJ PENTATONIC MAJOR
        .byte      0,   -1,    0,    0,   -1,    0,   -1,    0,   -1,    0,   -1,    0    | MELO MELODIC MINOR
        .byte      0,   -1,    0,    0,   -1,    0,   -1,    0,    0,   -1,   -2,    0    | HARM HARMONIC MINOR
        .byte      0,   -1,    0,   -1,    0,   -1,    0,   -1,    0,   -1,    0,   -1    | WHOL WHOLE TONE
        .byte      0,   -1,    1,    0,   -1,    0,    0,    0,   -1,    1,    0,   -1    | BLUE BLUES
        .byte      0,   -1,    0,    0,   -1,    0,   -1,    0,    0,   -1,    0,    0    | CMIN COMBO MINOR
        .byte      0,    0,   -1,   -2,    0,    0,    0,   -1,    0,   -1,   -2,    0    | PERS PERSIAN
        .byte      0,    0,   -1,   -2,    1,    0,    0,   -1,   -2,    1,    0,   -1    | IWA  IWATO
        .byte      0,    0,   -1,   -2,    1,    0,   -1,    0,   -1,    1,    0,   -1    | INSN IN-SEN
        .byte      0,   -1,    0,    0,   -1,   -2,    1,    0,    0,   -1,   -2,   -3    | HIRA HIRAJOSHI
        .byte      0,    0,   -1,    0,   -1,   -2,    1,    0,    0,   -1,   -2,   -3    | PELO PELOG
        .byte      0,    0,   -1,   -2,    0,    0,   -1,    0,    0,   -1,    0,   -1    | PHRD PHRYGIAN DOMINANT
        .byte      0,   -1,    0,    0,   -1,    0,    0,   -1,    0,    0,   -1,    0    | WHDI WHOLE-HALF DIMINISHED
        .byte      0,    0,   -1,    0,    0,   -1,    0,    0,   -1,    0,    0,   -1    | HWDI HALF-WHOLE DIMINISHED
        .byte      0,    0,   -1,    0,    0,    0,    0,   -1,    0,   -1,    0,   -1    | SPAN SPANISH
        .byte      0,   -1,    0,   -1,    0,    0,    0,   -1,    0,   -1,    0,   -1    | MLOC MAJOR LOCRIAN
        .byte      0,    0,   -1,    0,    0,   -1,    0,   -1,    0,   -1,    0,   -1    | ALT  SUPER LOCRIAN
        .byte      0,    0,   -1,    0,   -1,    0,   -1,    0,   -1,    0,    0,   -1    | DOR2 DORIAN b2
        .byte      0,   -1,    0,   -1,    0,   -1,    0,   -1,    0,    0,   -1,    0    | LYDA LYDIAN AUGMENTED
        .byte      0,   -1,    0,   -1,    0,   -1,    0,    0,   -1,    0,    0,   -1    | LYDD LYDIAN DOMINANT
        .byte      0,    0,   -1,   -2,    0,    0,   -1,    0,    0,   -1,   -2,    0    | DHRM DOUBLE HARMONIC MAJOR
        .byte      0,   -1,   -2,    0,    0,   -1,    0,    0,   -1,   -2,    0,    0    | LY26 LYDIAN #2 #6
        .byte      0,    0,   -1,    0,    0,   -1,   -2,    0,    0,    0,   -1,   -2    | ULPH ULTRAPHRYGIAN
        .byte      0,   -1,    0,    0,   -1,   -2,    0,    0,    0,   -1,   -2,    0    | HUNG HUNGARIAN MINOR
        .byte      0,    0,   -1,   -2,    0,    0,    0,   -1,   -2,    0,    0,   -1    | ORIE ORIENTAL
        .byte      0,   -1,   -2,    0,    0,    0,   -1,   -2,    0,    0,   -1,    0    | IO25 IONIAN #2 #5
        .byte      0,    0,    0,   -1,   -2,    0,    0,   -1,    0,    0,   -1,   -2    | LOBB LOCRIAN bb3 bb7

| Twelve bits per scale, low bit = the root: what the keyboard draws.
        .align  2
scale_mask:
        .short  0xfff    | CHRO CHROMATIC
        .short  0xab5    | MAJ  IONIAN (MAJOR)
        .short  0x6ad    | DOR  DORIAN
        .short  0x5ab    | PHR  PHRYGIAN
        .short  0xad5    | LYD  LYDIAN
        .short  0x6b5    | MIX  MIXOLYDIAN
        .short  0x5ad    | MIN  AEOLIAN (MINOR)
        .short  0x56b    | LOC  LOCRIAN
        .short  0x4a9    | PMIN PENTATONIC MINOR
        .short  0x295    | PMAJ PENTATONIC MAJOR
        .short  0xaad    | MELO MELODIC MINOR
        .short  0x9ad    | HARM HARMONIC MINOR
        .short  0x555    | WHOL WHOLE TONE
        .short  0x4e9    | BLUE BLUES
        .short  0xdad    | CMIN COMBO MINOR
        .short  0x973    | PERS PERSIAN
        .short  0x463    | IWA  IWATO
        .short  0x4a3    | INSN IN-SEN
        .short  0x18d    | HIRA HIRAJOSHI
        .short  0x18b    | PELO PELOG
        .short  0x5b3    | PHRD PHRYGIAN DOMINANT
        .short  0xb6d    | WHDI WHOLE-HALF DIMINISHED
        .short  0x6db    | HWDI HALF-WHOLE DIMINISHED
        .short  0x57b    | SPAN SPANISH
        .short  0x575    | MLOC MAJOR LOCRIAN
        .short  0x55b    | ALT  SUPER LOCRIAN
        .short  0x6ab    | DOR2 DORIAN b2
        .short  0xb55    | LYDA LYDIAN AUGMENTED
        .short  0x6d5    | LYDD LYDIAN DOMINANT
        .short  0x9b3    | DHRM DOUBLE HARMONIC MAJOR
        .short  0xcd9    | LY26 LYDIAN #2 #6
        .short  0x39b    | ULPH ULTRAPHRYGIAN
        .short  0x9cd    | HUNG HUNGARIAN MINOR
        .short  0x673    | ORIE ORIENTAL
        .short  0xb39    | IO25 IONIAN #2 #5
        .short  0x367    | LOBB LOCRIAN bb3 bb7

| The keyboard, in the display's BOTTOM-UP y. kbd_body is the lit
| slab; kbd_sep cuts the white keys apart; the black entries of
| kbd_rect cut the black keys out of it; kbd_dot marks the scale.
        .align  2
kbd_body:
        .byte     7,  11,  47,  37    | x1, y1, x2, y2
kbd_sep:
        .byte    12,  18,  24,  30,  36,  42

        .align  2
kbd_rect:
        .byte     7,  11,  11,  37    | C  white
        .byte    10,  23,  13,  37    | C# black
        .byte    13,  11,  17,  37    | D  white
        .byte    16,  23,  19,  37    | D# black
        .byte    19,  11,  23,  37    | E  white
        .byte    25,  11,  29,  37    | F  white
        .byte    28,  23,  31,  37    | F# black
        .byte    31,  11,  35,  37    | G  white
        .byte    34,  23,  37,  37    | G# black
        .byte    37,  11,  41,  37    | A  white
        .byte    40,  23,  43,  37    | A# black
        .byte    43,  11,  47,  37    | B  white

| The dot, and the mode it is drawn in: 0 clears, 1 lights.
        .align  2
kbd_dot:
        .byte     8,  13,  10,  15    | C 
        .byte    11,  25,  12,  26    | C#
        .byte    14,  13,  16,  15    | D 
        .byte    17,  25,  18,  26    | D#
        .byte    20,  13,  22,  15    | E 
        .byte    26,  13,  28,  15    | F 
        .byte    29,  25,  30,  26    | F#
        .byte    32,  13,  34,  15    | G 
        .byte    35,  25,  36,  26    | G#
        .byte    38,  13,  40,  15    | A 
        .byte    41,  25,  42,  26    | A#
        .byte    44,  13,  46,  15    | B 
        .align  2
kbd_dotmode:
        .byte     0,   1,   0,   1,   0,   0,   1,   0,   1,   0,   1,   0

| Pointers, indexed by scale, then by root.
        .align  2
scale_l1tab:
        .long   scale_p00a
        .long   scale_p01a
        .long   scale_p02a
        .long   scale_p03a
        .long   scale_p04a
        .long   scale_p05a
        .long   scale_p06a
        .long   scale_p07a
        .long   scale_p08a
        .long   scale_p09a
        .long   scale_p10a
        .long   scale_p11a
        .long   scale_p12a
        .long   scale_p13a
        .long   scale_p14a
        .long   scale_p15a
        .long   scale_p16a
        .long   scale_p17a
        .long   scale_p18a
        .long   scale_p19a
        .long   scale_p20a
        .long   scale_p21a
        .long   scale_p22a
        .long   scale_p23a
        .long   scale_p24a
        .long   scale_p25a
        .long   scale_p26a
        .long   scale_p27a
        .long   scale_p28a
        .long   scale_p29a
        .long   scale_p30a
        .long   scale_p31a
        .long   scale_p32a
        .long   scale_p33a
        .long   scale_p34a
        .long   scale_p35a

| The abbreviations, five bytes each: no pointer table, the cell
| reaches one as scale_abbr + 5*scale. Four characters plus a NUL is
| the whole of the panel's cell anyway.
        .align  2
scale_abbr:
        .asciz  "CHRO"   | 00
        .asciz  "MAJ"    | 01
        .space  1
        .asciz  "DOR"    | 02
        .space  1
        .asciz  "PHR"    | 03
        .space  1
        .asciz  "LYD"    | 04
        .space  1
        .asciz  "MIX"    | 05
        .space  1
        .asciz  "MIN"    | 06
        .space  1
        .asciz  "LOC"    | 07
        .space  1
        .asciz  "PMIN"   | 08
        .asciz  "PMAJ"   | 09
        .asciz  "MELO"   | 10
        .asciz  "HARM"   | 11
        .asciz  "WHOL"   | 12
        .asciz  "BLUE"   | 13
        .asciz  "CMIN"   | 14
        .asciz  "PERS"   | 15
        .asciz  "IWA"    | 16
        .space  1
        .asciz  "INSN"   | 17
        .asciz  "HIRA"   | 18
        .asciz  "PELO"   | 19
        .asciz  "PHRD"   | 20
        .asciz  "WHDI"   | 21
        .asciz  "HWDI"   | 22
        .asciz  "SPAN"   | 23
        .asciz  "MLOC"   | 24
        .asciz  "ALT"    | 25
        .space  1
        .asciz  "DOR2"   | 26
        .asciz  "LYDA"   | 27
        .asciz  "LYDD"   | 28
        .asciz  "DHRM"   | 29
        .asciz  "LY26"   | 30
        .asciz  "ULPH"   | 31
        .asciz  "HUNG"   | 32
        .asciz  "ORIE"   | 33
        .asciz  "IO25"   | 34
        .asciz  "LOBB"   | 35

| The same names again, split for the box: at most eleven characters.
| The second line FOLLOWS the first, so there is one pointer table and
| the drawing walks past the first line's terminator to reach it.
scale_p00a: .asciz  "CHROMATIC"
           .asciz  ""
scale_p01a: .asciz  "IONIAN"
           .asciz  "(MAJOR)"
scale_p02a: .asciz  "DORIAN"
           .asciz  ""
scale_p03a: .asciz  "PHRYGIAN"
           .asciz  ""
scale_p04a: .asciz  "LYDIAN"
           .asciz  ""
scale_p05a: .asciz  "MIXOLYDIAN"
           .asciz  ""
scale_p06a: .asciz  "AEOLIAN"
           .asciz  "(MINOR)"
scale_p07a: .asciz  "LOCRIAN"
           .asciz  ""
scale_p08a: .asciz  "PENTATONIC"
           .asciz  "MINOR"
scale_p09a: .asciz  "PENTATONIC"
           .asciz  "MAJOR"
scale_p10a: .asciz  "MELODIC"
           .asciz  "MINOR"
scale_p11a: .asciz  "HARMONIC"
           .asciz  "MINOR"
scale_p12a: .asciz  "WHOLE"
           .asciz  "TONE"
scale_p13a: .asciz  "BLUES"
           .asciz  ""
scale_p14a: .asciz  "COMBO"
           .asciz  "MINOR"
scale_p15a: .asciz  "PERSIAN"
           .asciz  ""
scale_p16a: .asciz  "IWATO"
           .asciz  ""
scale_p17a: .asciz  "IN-SEN"
           .asciz  ""
scale_p18a: .asciz  "HIRAJOSHI"
           .asciz  ""
scale_p19a: .asciz  "PELOG"
           .asciz  ""
scale_p20a: .asciz  "PHRYGIAN"
           .asciz  "DOMINANT"
scale_p21a: .asciz  "WHOLE-HALF"
           .asciz  "DIMINISHED"
scale_p22a: .asciz  "HALF-WHOLE"
           .asciz  "DIMINISHED"
scale_p23a: .asciz  "SPANISH"
           .asciz  ""
scale_p24a: .asciz  "MAJOR"
           .asciz  "LOCRIAN"
scale_p25a: .asciz  "SUPER"
           .asciz  "LOCRIAN"
scale_p26a: .asciz  "DORIAN"
           .asciz  "b2"
scale_p27a: .asciz  "LYDIAN"
           .asciz  "AUGMENTED"
scale_p28a: .asciz  "LYDIAN"
           .asciz  "DOMINANT"
scale_p29a: .asciz  "DOUBLE HRM"
           .asciz  "MAJOR"
scale_p30a: .asciz  "LYDIAN"
           .asciz  "#2 #6"
scale_p31a: .asciz  "ULTRA"
           .asciz  "PHRYGIAN"
scale_p32a: .asciz  "HUNGARIAN"
           .asciz  "MINOR"
scale_p33a: .asciz  "ORIENTAL"
           .asciz  ""
scale_p34a: .asciz  "IONIAN"
           .asciz  "#2 #5"
scale_p35a: .asciz  "LOCRIAN"
           .asciz  "bb3 bb7"


| The twelve roots, three bytes each: scale_root + 3*root.
        .align  2
scale_root:
        .asciz  "C"
        .space  1
        .asciz  "C#"
        .asciz  "D"
        .space  1
        .asciz  "D#"
        .asciz  "E"
        .space  1
        .asciz  "F"
        .space  1
        .asciz  "F#"
        .asciz  "G"
        .space  1
        .asciz  "G#"
        .asciz  "A"
        .space  1
        .asciz  "A#"
        .asciz  "B"
        .space  1
        .align  2

| ---------------------------------------------------------------------------
| THE SCALE LOCK. Two caves on the MIDI note-trig emitter, so what the track
| SENDS is in the chosen scale.
|
| FUN_4009f794 is the emitter for all eight MIDI tracks and it runs whether
| or not the arp is on, so this covers plain note trigs and the arp's
| per-step offsets alike. Stock's own quantiser lives there: it decodes the
| arp KEY byte into one local, then indexes a twelve-entry snap table. These
| two caves replace the decode and the lookup, reading SCL and ROT instead of
| the KEY byte and indexing the thirty-six-scale table above.
|
| THE TRICK, which is Maxolydian's and is credited in modules/arp-scales:
| the index downstream is taken mod 12, so any multiple of twelve added to
| the local is invisible to it. The local can therefore carry both fields:
|
|     local = 12*scale + (12 - root)
|
|     idx   = (note + local) % 12 = (note - root) % 12      unchanged
|     scale = (local - 1) / 12                              recovered below
|
| No extra stack slot and no change to the stock frame. arp_model.py proves
| the arithmetic over every state and note.
|
| The octave fold is this module's own: stock snaps downward only, so at MIDI
| note 0 a snap can land on -1 and the note is dropped. A scale repeats every
| octave, so a result outside 0..127 comes back by twelve and is still in the
| scale. Two compares, and the whole class of edge case goes -- stock's
| included.
| ---------------------------------------------------------------------------

        .set    SC_SCALE,  0x23          | cell 3 in the runtime block
        .set    SC_ROOT,   0x25          | cell 5
        .set    LOCAL,     -64           | the decode's local, (LOCAL,%fp)
        .set    RET_DECODE, 0x4009fb00   | past the block the decode replaces
        .set    RET_LOOKUP, 0x4009fb80   | past the add and store it replaces

        .global sc_decode
sc_decode:
        | %a0 is the track's runtime block. Stock clobbers %d0-%d3 across the
        | block being replaced, so they are free; nothing else may be touched.
        clr.l   %d0
        move.b  (SC_SCALE,%a0),%d0
        beq.s   .Lsd_off                 | 0 = CHROMATIC: every note passes
        clr.l   %d1
        move.b  (SC_ROOT,%a0),%d1
        moveq   #12,%d2
        mulu.l  %d2,%d0                  | 12*scale  (register form; ColdFire
                                         | has no immediate MULU.L)
        move.l  %d2,%d3
        sub.l   %d1,%d3                  | 12 - root
        add.l   %d3,%d0
        move.l  %d0,(LOCAL,%fp)
        jmp     RET_DECODE
.Lsd_off:
        clr.l   (LOCAL,%fp)
        jmp     RET_DECODE

        .global sc_lookup
sc_lookup:
        | entry: %d0 = the note, %d1 = the index, %a2 -> the note byte.
        | The detour replaces the table load AND the add and store after it.
        move.l  (LOCAL,%fp),%d2
        subq.l  #1,%d2
        moveq   #12,%d3
        divu.l  %d3,%d2                  | %d2 = scale
        mulu.l  %d3,%d2                  | scale*12
        add.l   %d1,%d2                  | + idx
        lea     scale_ut:l,%a0
        mvs.b   (%a0,%d2.l),%d3
        add.l   %d3,%d0
        bge.s   .Lsl_high
        addi.l  #12,%d0                  | fell below 0: up an octave
        bra.s   .Lsl_store
.Lsl_high:
        cmpi.l  #127,%d0
        ble.s   .Lsl_store
        subi.l  #12,%d0                  | past 127: down an octave
.Lsl_store:
        move.b  %d0,(%a2)
        jmp     RET_LOOKUP
