| ============================================================================
| STOP GUARD -- the panel's STOP and PLAY keys ask before they stop the
| sequencer, while this unit is the clock master and the PERSONALIZE row
| RiDylan mode is ticked.
|
| WHY. On stage the STOP key is one bump away from ending the performance.
| Everything else destructive on this machine asks first (FORMAT CARD,
| DELETE, RELOAD); transport does not. This adds the same YES/NO screen the
| firmware already draws, on the one key that had no undo.
|
| WHAT IT TOUCHES
|   the PLAY key handler 0x40061778, at its first instruction. Its two
|     keymap entries are left alone; the handler itself is the hook.
|   the STOP key handler 0x4004aca4, at its press-only dispatch 0x4004acce.
|     Stock there is `tst.l 0x460d1aec / beq +8 / jsr 0x400a14a4 / bra +6 /
|     jsr 0x400a10c8`, and everything after it is dead once we jump away.
|     sg_key replays exactly that pair when the guard does not apply.
|   the PERSONALIZE screen's three parallel arrays, relocated by the build
|     (schema.TableGrow) from sixteen entries to seventeen: the fifteen rows
|     both models show, then this one, then LED BRIGHTNESS. The order is the
|     point -- the screen shows a CONTIGUOUS range 0..count-1 and the stock
|     count is 15 on one model and 16 on the other, so a row appended after
|     LED BRIGHTNESS would be invisible on the model that hides it.
|   the item count at 0x40068fb2, `moveq #15` -> `moveq #16`. The model flag
|     at 0x46c8d18c still adds its own one, so the screen is 16 rows on the
|     model that hid LED BRIGHTNESS and 17 on the one that showed it. The
|     hidden row stays hidden either way.
|
| WHAT IT DOES NOT TOUCH. Any other caller of the stop routine -- there are
| twenty-six, including MIDI transport, the loader and the recorder. Only the
| panel key's own call site is redirected. A STOP pressed while the sequencer
| is already stopped is stock's second-press reset and is never guarded.
|
| WHERE THE SETTING LIVES, AND WHY IT SURVIVES A POWER CYCLE.
|   Stock's sixteen PERSONALIZE settings are longs in a live block at
|   0x80000070, each with a copy in the non-volatile block at 0x100fff00.
|   That block is magic ("ANDY" at 0x100fff04), version-stamped at
|   0x100fff0e, and checksummed: 0x4001f218 sums 252 sign-extended bytes from
|   0x100fff04, each XORed with its one-based index, plus 0x202, and
|   0x4001f23c stores that sum at 0x100fff00. At boot 0x4001f340 recomputes
|   it; on a match it copies exactly 100 bytes from 0x100fff00 to 0x80000070,
|   and on a mismatch it clears the store and writes defaults.
|
|   So every setting is one offset k in two blocks -- live 0x80000070 + k,
|   mirror 0x100fff00 + k -- and ANY long inside the copy that also lies
|   inside the checksum persists by the same mechanism stock's own rows use.
|   The sixteen rows take 0x8c, 0x90, 0x94, 0x98, 0x9c, 0xa0, 0xa4, 0xac,
|   0xb0, 0xb8, 0xbc, 0xc0, 0xc4, 0xc8, 0xcc and 0xd0 (offsets from
|   0x80000000). 0xb4 belongs to a seventeenth setting edited elsewhere.
|   0xa8 -- mirror 0x100fff38 -- is referenced by NOTHING in the image:
|   not by a literal in any of the 1,112,560 bytes, and not by the two bulk
|   clears, which stop below 0x100fff00 and above 0x100fff04 respectively.
|   That is the word this module takes.
|
|   No checksum call is needed here: the PERSONALIZE edit dispatcher calls
|   the row's setter and then jumps to 0x4001f23c itself (0x40069074), so
|   every row's write is stamped by stock code, this one included.
|
| INSTRUCTION FORMS. Every form below has precedent in the stock image, at
| the address named beside it. `pea` is avoided in favour of a register push
| for the same reason: the forms used are the ones the firmware runs.
|
| MEASURED, against the user's own 1.40C: every `expect` in manifest.py, the
| three arrays and their five reach sites, the count expression, the setter
| and getter contracts (copied from row 7, DIS. STOP-STOP ARM), the glyph
| pair, the popup's five arguments and its 0-means-yes handler (FORMAT CARD,
| 0x40069354), the popup's busy guard, the transport long, the two clock bits
| (from the config writer at 0x400884a4, which spells the names out), and the
| whole settings-block mechanism above.
|
| NOT MEASURED: any of it running. No hardware and no emulator pass. Treat
| this as a first draft that assembles, not as a working module.
| ============================================================================

        .set    GUARD,        0x800000a8   | the live flag (free; see above)
        .set    GUARD_MIRROR, 0x100fff38   | its copy in the non-volatile block
        .set    SYNC,         0x80000028   | b0 CLOCK RECEIVE, b1 CLOCK SEND
        .set    TRANSPORT,    0x800065b8   | 0 stopped, 1 playing, 2 paused
        .set    ALTSTOP,      0x460d1aec   | picks which stop routine runs
        .set    STOP,         0x400a10c8   | the stop routine
        .set    STOP_ALT,     0x400a14a4   | the one that calls it and more
        .set    KEY_RET,      0x4004ace4   | past the dispatch sg_key replaces
        .set    POPUP,        0x4006d57c   | popup(title, n, lines, mode, fn)
        .set    POPUP_BUSY,   0x460e5cd0   | non-zero: a popup is already up
        .set    POPUP_MODE,   3            | FORMAT CARD's mode: YES / NO
        .set    PLAYKEY,      0x40061778   | the PLAY key's press handler
        .set    PLAYKEY_PRE,  0x4009b5c0   | the readiness check it opens with
        .set    PLAYKEY_ON,   0x4006177e   | past the instruction we displace
        .set    GLYPH_ON,     0x400b5e90   | the ticked box
        .set    GLYPH_OFF,    0x400b5e8e   | the empty box

| ---------------------------------------------------------------------------
| THE KEY. Detoured at 0x4004acce, which the handler reaches only on a PRESS
| (both paths above it return on release). %d2 carries the pressed flag and
| is read again at KEY_RET, so it must survive; %d0 and %a0 are free.
| ---------------------------------------------------------------------------

        .global sg_key
sg_key:
        tst.l   GUARD                   | 4ab9, as 0x400a1132
        beq.s   .Lstock                 | row not ticked
        tst.l   TRANSPORT               | as 0x400a10d0
        beq.s   .Lstock                 | already stopped: stock's reset press
        move.b  SYNC,%d0                | 1039, as 0x4006714e
        btst    #0,%d0                  | 0800 0000, as 0x400672c4
        bne.s   .Lstock                 | CLOCK RECEIVE on: we are the slave
        tst.l   POPUP_BUSY              | as 0x4006d58c
        bne.s   .Lswallow               | a screen is already up: see below

        lea     sg_answer:l,%a0         | 41f9 -- :l, or a same-unit label
        move.l  %a0,-(%sp)              |   assembles PC-relative
        moveq   #POPUP_MODE,%d0
        move.l  %d0,-(%sp)              | mode 3
        lea     sg_lines:l,%a0
        move.l  %a0,-(%sp)              | the three lines
        move.l  %d0,-(%sp)              | three of them
        lea     sg_title:l,%a0
        move.l  %a0,-(%sp)              | the title
        jsr     POPUP
        lea     (20,%sp),%sp            | 4fef 0014
.Lswallow:
        | Nothing stops here, either way. If a screen was already up the
        | guard cannot ask, and the guard is ON: a second bump on STOP must
        | not be the one that ends the set. Untick the row, or slave the
        | clock, and the key is stock's again.
        jmp     KEY_RET

.Lstock:
        tst.l   ALTSTOP
        beq.s   .Lplain
        jsr     STOP_ALT
        jmp     KEY_RET
.Lplain:
        jsr     STOP
        jmp     KEY_RET

| ---------------------------------------------------------------------------
| THE PLAY KEY. Detoured at its handler's first instruction, 0x40061778,
| which the keymap tables reach as the PRESS entry for key 0x28 (both
| tables: 0x400c0056 and 0x400c063a hold it, and neither is touched).
|
| PLAY while the sequencer is stopped STARTS it and is never guarded. PLAY
| while it runs is the press that ends a set, so it asks -- and the answer
| handler is sg_answer, the same one the STOP key uses. That is deliberate:
| one warning with one meaning. The screen says STOP PLAYBACK?, so YES
| stops, rather than reproducing whatever the stock handler would have done
| with the modifier state as it was at press time -- state the popup has
| already outlived by the time anyone answers.
|
| The stub's own arguments are the handler's: two slots above the return
| address, which the stock handler WRITES a command into before tail-jumping
| to the mode routine at 0x4007e998. Nothing here touches them, and the
| swallow path returns through a bare rts -- which is stock's own
| do-nothing exit for this handler, at 0x400618bc.
| ---------------------------------------------------------------------------

        .global sg_play
sg_play:
        tst.l   GUARD
        beq.s   .Lplaystock             | row not ticked
        tst.l   TRANSPORT
        beq.s   .Lplaystock             | stopped: PLAY starts, never guarded
        move.b  SYNC,%d0
        btst    #0,%d0
        bne.s   .Lplaystock             | CLOCK RECEIVE on: we are the slave
        tst.l   POPUP_BUSY
        bne.s   .Lplayswallow

        lea     sg_answer:l,%a0
        move.l  %a0,-(%sp)
        moveq   #POPUP_MODE,%d0
        move.l  %d0,-(%sp)
        lea     sg_lines:l,%a0
        move.l  %a0,-(%sp)
        move.l  %d0,-(%sp)
        lea     sg_title:l,%a0
        move.l  %a0,-(%sp)
        jsr     POPUP
        lea     (20,%sp),%sp
.Lplayswallow:
        rts                             | as stock's own 0x400618bc

.Lplaystock:
        jsr     PLAYKEY_PRE             | the instruction the detour displaced
        jmp     PLAYKEY_ON

| ---------------------------------------------------------------------------
| THE ANSWER. popup's handler, one long argument, 0 = YES (FORMAT CARD's own
| handler at 0x40069394 tests it the same way). Tail-jumps into the stop
| routine exactly as the key handler would have, so its `rts` returns to the
| popup's caller.
| ---------------------------------------------------------------------------

        .global sg_answer
sg_answer:
        move.l  (4,%sp),%d0             | 202f 0004
        bne.s   .Lno
        tst.l   ALTSTOP
        beq.s   .Lplain2
        jmp     STOP_ALT
.Lplain2:
        jmp     STOP
.Lno:
        rts

| ---------------------------------------------------------------------------
| THE ROW. getter: no arguments, returns the glyph in %d0. setter:
| (delta, wrap) on the stack, clamps or wraps to 0..1, writes the live long
| and its mirror. Both are row 7's (DIS. STOP-STOP ARM, 0x40068d50/0x40068d90)
| instruction for instruction, with this module's addresses.
| ---------------------------------------------------------------------------

        .global sg_get
sg_get:
        move.l  #GLYPH_ON,%d0
        tst.l   GUARD
        bne.s   .Ldrawn
        move.l  #GLYPH_OFF,%d0
.Ldrawn:
        rts

        .global sg_set
sg_set:
        move.l  (4,%sp),%d1             | delta
        add.l   GUARD,%d1               | d2b9, as 0x40068d54
        tst.l   (8,%sp)                 | wrap, or clamp?
        beq.s   .Lclamp
        move.l  %d1,%d0                 | wrap to 0..1
        moveq   #1,%d1
        cmp.l   %d0,%d1
        bge.s   .Lhigh
        clr.l   %d0
        bra.s   .Lstore
.Lhigh:
        tst.l   %d0
        bge.s   .Lstore
        bra.s   .Lone
.Lclamp:
        move.l  %d1,%d0                 | clamp to 0..1: %d0 = max(%d1, 0)
        not.l   %d0
        add.l   %d0,%d0
        subx.l  %d0,%d0
        and.l   %d1,%d0
        ble.s   .Lstore
.Lone:
        moveq   #1,%d0
.Lstore:
        move.l  %d0,GUARD
        move.l  %d0,GUARD_MIRROR        | stamped by the dispatcher's 0x4001f23c
        rts

| ---------------------------------------------------------------------------
| TEXT. The popup draws 21 columns; the PERSONALIZE label column holds 18
| (DISABLE YES/NO ARM and DIS. STOP-STOP ARM are both exactly 18).
| ---------------------------------------------------------------------------

        .align  2
        .global sg_lines
sg_lines:
        .long   sg_line1
        .long   sg_line2
        .long   sg_line3

sg_title:       .asciz  "CONFIRM STOP"
sg_line1:       .asciz  "OCTATRACK IS MASTER"
sg_line2:       .asciz  "AND IS PLAYING."
sg_line3:       .asciz  "STOP PLAYBACK?"

        .global sg_label
sg_label:       .asciz  "RiDylan mode"
        .align  2

| ---------------------------------------------------------------------------
| The stock row the relocated arrays must carry LAST, so that the model which
| shows one row fewer hides it and not this module's. Absolute symbols, so the
| build's TableGrow can name them beside this unit's own; manifest.py asserts
| all three against the stock arrays before anything moves.
| ---------------------------------------------------------------------------

        .global led_label
        .set    led_label, 0x400b63f8    | "LED BRIGHTNESS"
        .global led_get
        .set    led_get,   0x40068c80
        .global led_set
        .set    led_set,   0x4006907c
