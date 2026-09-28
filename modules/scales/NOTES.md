# The MIDI track's arp block — what is measured

Working notes for the scale feature. Everything here is read from Jesse's
own 1.40C at base 0x40000400; nothing is inferred unless it says so.

## The per-track mirror

`FUN_4009f794`, the MIDI note-trig emitter, walks eight tracks. Its bases
are loaded at 0x4009f986..0x4009f9a0 and advanced per track at
0x4009ffec..0x400a000e:

| base | address | stride | note |
| --- | --- | --- | --- |
| `(-0x18,%a6)` | `0x46c76dc0` | `0x44` | the block the arp decode reads |
| `(-0x20,%a6)` | `0x46c77bba` | `1` | byte arrays indexed by track |
| `(-0x24,%a6)` | `0x80006676` | `1` | |

The `0x44` stride is `moveq #0x44,%d1 / add.l %d1,(-0x18,%a6)` at
0x4009fff0. The array's extent is confirmed independently: 0x40003dcc
copies eight blocks from `0x46c76dc0` stride `0x44` and stops at
`0x46c76fe0`, which is exactly 8 x 0x44 past the base.

So the arp KEY scale byte for track *t* is `0x46c76dc0 + t*0x44 + 0x31`:
track 1 at **0x46c76df1**, track 2 at **0x46c76e35**.

## The ARP SETUP page's parameter table

Names, 4 characters plus NUL at stride 6 from 0x400d3fe6:

| idx | name | at | enum count |
| --- | --- | --- | --- |
| 0 | TRAN | 0x400d3fe6 | 128 |
| 1 | LEG | 0x400d3fec | 2 |
| 2 | MODE | 0x400d3ff2 | 7 |
| 3 | SPD | 0x400d3ff8 | 96 |
| 4 | RNGE | 0x400d3ffe | 8 |
| 5 | NLEN | 0x400d4004 | 128 |
| 6 | ----- | 0x400d400a | 1 |
| 7 | ----- | 0x400d4010 | 1 |
| 8 | LEN | 0x400d4016 | 16 |
| 9 | ----- | 0x400d401c | 1 |
| 10 | ----- | 0x400d4022 | 1 |
| 11 | KEY | 0x400d4028 | 25 |

Counts are longs at stride 4 from 0x400d406a; KEY's is the 0x400d4096 the
ARP SCALES module already pokes. Formatters are longs at stride 4 from
0x400d409a; KEY's is at 0x400d40c6 and holds 0x4003b790, the formatter
that module detours. Both arrays agree with the name order, which is what
makes the index mapping measured rather than assumed.

## Storage offsets — RETRACTED, then redone

**First attempt, wrong.** I scanned for byte accesses at displacements
0x26..0x31 and read four hits as confirmation that parameters are stored
consecutively from 0x26 (slot *i* at `0x26 + i`), with one of them --
displacement 0x2f, a slot the panel draws as `-----` -- appearing to prove
that a dashed slot is NOT free.

All of that was a decoding bug. Three of the four hits were `(d16,A7)`:
stack frame reads in unrelated routines. A7 is the stack pointer, not a
pointer to this block, and those sites say nothing whatever about the
per-track layout. The only real datum was KEY itself.

**Redone, excluding A7.** Byte accesses at displacement 0x00..0x43 off
A0..A6 anywhere in 0x40098000..0x400a6000:

| disp | what |
| --- | --- |
| 0x20 | read, A0, 0x4009fa72 — inside the quantiser, where A0 IS the mirror |
| 0x31 | read, A0, 0x4009fad2 — KEY |

Nothing else in 0x21..0x30 or 0x32..0x43 is touched from A0..A6 in that
whole region.

So: the consecutive-layout guess is neither confirmed nor refuted, and the
four dashed slots are neither shown free nor shown used. The runtime simply
does not read most of the block -- the other parameters are consumed by the
editor and the loader, which live elsewhere. **No byte of this block may be
claimed as free on the evidence gathered so far.**

Lesson worth keeping: a displacement scan that does not exclude A7 will
manufacture confirmations for any offset you care to look for, because
stack frames use every small displacement there is.

## The open question

Writing the mirror sets the live value. It does not prove the value is what
gets SAVED. The stock KEY editor writes every copy correctly, so the safe
move is to write through it rather than to poke the mirror -- which means
finding the MIDI page's parameter writer (the analogue of the page-1 writer
0x40054cd8 that mode-defaults uses). That trace is the next job, and no
code should be written before it lands.

## The writer, found (28 Sep 2026)

A MIDI-track parameter write touches THREE things together, in one routine
around 0x40028786-0x40028960:

1. **the live mirror** — `A1` is built as
   `lea (0x20,A4,D5.l),A1 / adda.l #0x46c76dc0,A1` with `D0 = D5 = track`,
   `lsl.l #2,D0` and `lsl.l #6,D5`, so `track*4 + track*64 = track*0x44`
   exactly. The store is `move.b (A2),(-0x20,A1)` at 0x4002895e.
2. **the project buffer** — `movea.l 0x46c82456,A0` then
   `adda.l D3,A0 / adda.l D1,A0 / adda.l #0x8f162,A0` and
   `move.b (A2),(A0)` at 0x40028910. So **`0x46c82456` holds the pointer to
   the loaded project in RAM**, and `0x8f162` is a part-relative base.
   `tools/hw/ot_project.py` has `PART_BASE = 0x8eed6`, which is `0x28c`
   below it — so the constants in this routine are the SAME file offsets
   that tooling already uses, and the MIDI parameter area starts `0x28c`
   into a part.
3. **the dirty flags** — `(A0,D5.l) |= D6` in the project buffer, plus
   `0x100b145e |= D6`, plus `0x100f8598 = 1`. Without these a write is live
   but never saved.

That third item is the answer to the open question above: writing the
mirror alone would set the value and lose it, silently, at save time.

Still to pin before code: the per-track stride and the parameter offset
inside the part's MIDI area (the `D3` and `D1` terms), so the project-buffer
address can be computed for the KEY byte of tracks 1 and 2.

## The saved layout, measured from a real project (28 Sep 2026)

Jesse saved "MIDI TEST01" with KEY set on MIDI tracks 1 and 2, LEN set on
track 1, and every other MIDI track's KEY left at OFF. Diffing `bank01.work`
against an untouched `bank02.work` gives 21 changed bytes, all in part 0.

**The MIDI track block in a saved part:**

    PART_BASE + part*PART_STRIDE + 0x4eb + track*0x24
    = 0x8eed6  + part*0x18bb    + 0x4eb + track*0x24

36 bytes per track, eight tracks. Within the block:

| offset | parameter | evidence |
| --- | --- | --- |
| +0x00 | (channel or mode) | changed on tracks 1 and 2 |
| +0x0e | LEN | track 1 = 0x0d, default 0x07 |
| +0x11 | **KEY** | track 1 = 0x1f, track 2 = 0x33, tracks 3-8 = 0 |

The KEY column is exactly the signature asked for: two distinct values, six
zeroes, nothing else in the block moved.

**And it cross-checks the RAM side.** The mirror block is stride 0x44 with
KEY at +0x31; the saved block is stride 0x24 with KEY at +0x11. Both
differences are 0x20, so

    mirror[t] + 0x20 + k  ==  saved block[t] + k,   k = 0 .. 0x23

The saved block IS the top 0x24 bytes of the runtime block, and the low 0x20
bytes are runtime-only state. That is why the writer builds its pointer as
`lea (0x20,A4,D5.l),A1` -- the 0x20 in that instruction is this offset. Two
measurements taken by completely different methods, agreeing to the byte.

**Bytes zero in all 16 banks x 4 parts x 8 tracks** (block offsets):
0x03, 0x05-0x0d, 0x0f, 0x10, 0x12, 0x13, 0x1e-0x23.

0x12 and 0x13 sit immediately after KEY, are zero everywhere in this
project, and are not read from A0-A6 anywhere in 0x40098000..0x400a6000.
They are the candidates for SCALE and ROOT -- mirror 0x32 and 0x33.

Zero-everywhere in ONE project is not proof of unused. The probe below is.

## The slot enable mask (28 Sep 2026) — why two probes drew nothing

Two probes gave a slot a name, an enum count and a formatter, and the panel
kept drawing dashes. The poke was verified present in the built
`out/mainos_bus.bin` at the right offset, so the build was never the
problem: the table simply was not sufficient.

Each page block ends with **two longs that are a 16-nibble per-slot enable
mask** — nibble *i* for slot *i*, read LSB-first through the low long and
then the high one. A slot whose nibble is zero draws as dashes whatever its
name, count and formatter say.

| page | low long | at | high long | at |
| --- | --- | --- | --- | --- |
| NOTE | `0x11111111` | 0x400d3fcc | `0x00000101` | 0x400d3fc8 |
| ARP | `0x00111111` | 0x400d415e | `0x00001001` | 0x400d415a |

Decoded, NOTE gives slots 9 and 11 a zero — exactly the two dashes. ARP
gives slots 6, 7, 9 and 10 a zero — exactly its four. **Twenty-four slots
across two pages, every nibble agreeing with whether the slot has a real
name, with no exceptions.** That is what makes this the gate rather than
another guess.

The mask is also what the NOTE SETUP draw routine pushes: `0x40036630` and
`0x40036636` push the two longs, having loaded slot 6's name at
`lea 0x400d3e78,%a6` and slot 6's formatter at `lea 0x400d3f20,%a4`. So the
draw path and the mask agree about where the SETUP row starts, which
independently confirms the name and formatter bases too.

Method note: both failures were diagnosed by checking the artifact
(`grep` the built image for the poked bytes) before theorising. The poke
was there both times, which is what ruled out the build and pointed at the
table.

## Why a woken slot draws but forgets (28 Sep 2026)

With the mask poked, SCL and ROT appeared on MIDI NOTE SETUP and their
knobs moved. But Jesse found that setting them on track 1, switching to
track 2 and coming back leaves both blank -- and then track 2 is blank too.

A value that does not survive a track switch is not in per-track storage at
all; it is in the editor's working state, lost as soon as the track's
parameter set is reloaded. That matches the remaining NULL field exactly.

Each page block carries FOUR per-slot arrays, not two:

| array | at (NOTE) | what |
| --- | --- | --- |
| names | 0x400d3e54, stride 6 | the 4-char label |
| counts | 0x400d3ed8, stride 4 | the enum count |
| formatters | 0x400d3f08, stride 4 | how the value draws |
| **handlers** | **0x400d3f38, stride 4** | **binds the slot to its byte** |

plus the 16-nibble enable mask in the two longs at 0x400d3fc8/0x400d3fcc.

Every enabled slot on the NOTE page has a handler -- 0x400467a4 for NOTE,
VEL, LEN, CHAN, BANK, PROG and SBNK, 0x4004661c for NOT2/3/4 -- and slots
9 and 11 hold NULL. The handler is shared between slots with different
storage, so it must take the slot index and derive the offset itself.

This also retires a worry raised by the TEST02 diff: the two bytes that
moved there (+0x0e, +0x11) were an ARP page visit, NOT SCL and ROT
aliasing ARP LEN and KEY. Nothing was aliased, because nothing was stored.

The live test is now seconds rather than a save-and-diff cycle: set the
value, switch track, switch back. If it survives, it is bound.

## Correction: the empty cells are not a dead end (28 Sep 2026)

I wrote above that the two empty NOTE SETUP cells were a dead end because
stock allocates no storage behind them. That conclusion was wrong in the
way that matters: it confounded "stock does not do this" with "this cannot
be done". Writing code into stock pages is what this repository is for.

Three probes failed because they tried to make stock's own machinery adopt
a slot it never had. The right move is to supply the missing half myself.
Everything except one hook is already measured:

| piece | status |
| --- | --- |
| storage | **measured free**: block +0x12/+0x13 = mirror +0x32/+0x33. Zero in all 16 banks x 4 parts x 8 tracks, and not read from A0-A6 anywhere in 0x40098000..0x400a6000 |
| mirror address | **measured**: 0x46c76dc0 + track*0x44 + 0x32 |
| saved address | **measured** from Jesse's own bank01.work: PART_BASE + part*PART_STRIDE + 0x4eb + track*0x24 + 0x12 |
| the two agree | **proved**: saved block == mirror + 0x20, both KEY offsets differ by exactly 0x20 |
| drawing the cell | **pokeable**: the draw array at 0x400d3f38 accepts a pointer; the cell drew as soon as it was filled in |
| making it visible | **pokeable**: the enable mask at 0x400d3fc8 |
| name, count, formatter | **pokeable**, all three confirmed |
| persistence | mirror byte + project-buffer byte + dirty flags (0x100b145e, 0x100f8598); the project buffer is *(0x46c82456), and 0x8f162 = PART_BASE + 0x28c shows the buffer uses the same part layout as the file |
| **the encoder hook** | **NOT YET FOUND** -- where a knob turn on this SETUP window becomes a parameter write |

So one unknown remains, and it is the same one that has been circling since
the writer trace: the edit path. 0x4004ad80, reached twice from the window
descriptor, is a KEY handler (it takes a pressed flag at (0xc,A6)), not the
encoder. The encoder path is the next thing to find, and it is the last
thing needed before code.

The BANK/SBNK repurpose in modules/slot-probe is SHELVED: it works, but it
costs MIDI bank select, and Jesse would rather keep it. It stays as the
fallback if the encoder hook proves unreachable.

## The parameter accessor (28 Sep 2026) — progress, not the answer

`0x40027e4c` is the entry of the routine whose body writes the mirror, the
project buffer and the dirty flags. Its prologue takes five arguments:

    (0x38,%a7) -> %a2   the PROJECT BUFFER base. It immediately does
                        `move.l #0x8ed8,%d0 / cmp.l (%a2,%d0.l),%d7`, and
                        offsets of that size are bank-file scale, which is
                        what makes it the buffer rather than a struct.
    (0x3c,%a7) -> %d4
    (0x40,%a7) -> %d5
    (0x44,%a7) -> %d0   a SELECTOR, 0..4, bounds-checked against 4 and fed
                        to a jump table at 0x40027e7e
                        (`move.w (8,%pc,%d0.l*2),%d0 / jmp (2,%pc,%d0.l)`)
    (0x48,%a7)          a flag; non-zero branches to 0x4002887e

So it is a five-way generic accessor over the loaded project, and the
per-parameter offsets are hardcoded in its cases (the case examined writes
mirror + track*0x44 + 0x00, which is the byte TEST01 showed changing on
tracks 1 and 2 — CHAN).

**Unresolved and odd:** the literal 0x40027e4c appears NOWHERE in the image,
and an exhaustive scan of every PC-relative reach (bsr.b/w/l, bra, jsr/jmp
(d16,pc)) finds exactly two, both at 0x40028f9a and 0x40028fda, which are
themselves inside the 0x40027e4c..0x40029000 span. A function with no
external callers cannot be the whole story, so either the span is two
functions and the second calls the first, or the entry is reached by
falling through from the routine above it. Untangling that is where the
hunt is.

The encoder -> cell -> parameter path is STILL not found. Four probes and
several traces in, the honest summary is that the display tables are fully
mapped and the edit path is not, and estimates offered so far for closing
that gap have all been wrong.

## THE ADDRESS FORMULA, from code (28 Sep 2026)

The Digitakt II research named the missing idea: a *descriptor* binding a
displayed parameter to a storage offset. Looking for a RULE instead of a
TABLE found it immediately, and then the draw routine confirmed it in code.

At 0x4003665c the NOTE SETUP renderer builds the address of a cell's value:

    movea.l (0x2c,%a7),%a0        | part*0x18b2 + track*0x24, built at
                                  | 0x40036614: lsl.l #5 + lea (A1,D3.l*4)
                                  | is track*0x24; muls.l #0x18b2 is the
                                  | part stride (RAM; the FILE stride is
                                  | 0x18bb, and ot_project.py already says
                                  | RAM's is 9 less)
    adda.l 0x46c82456,%a0         | + the loaded project buffer
    adda.l %d4,%a0                | + the CELL INDEX, 0..5, added raw
    adda.l #0x8f262,%a0           | + the MIDI-row parameter base
    mvs.b  (%a0),%d0              | the value

So:

    value = *(0x46c82456) + 0x8f262 + part*0x18b2 + track*0x24 + cell

The six cells of a SETUP row are six CONSECUTIVE bytes. That is why no
offset table was ever found: there isn't one, the offset is the cell index.

It also confirms the earlier empirical mapping. CHAN is cell 0 and TEST01
showed block +0x00 holding 01 and 02 on tracks 1 and 2 -- MIDI channels 1
and 2. So the NOTE SETUP row is cells 0..5 = CHAN, BANK, PROG, **free**,
SBNK, **free**, and the two empty cells are **+0x03 and +0x05**, both in the
measured never-nonzero list. The storage exists and is free.

And the mask handling is confirmed too: the renderer passes both mask longs
and 0x18 to 0x400a6994, which is a 64-bit shift helper -- the 16-nibble
mask shifted right 24 bits, six nibbles, to reach row 2.

## The write machinery

0x4004af20 is a handler in this screen's sub-keymap at 0x400bc51e (records
of a key-code word plus a handler long: 0x3100 -> 0x4004af20, 0x3200 ->
0x4003d440, i.e. YES and NO). It edits a cell, and its setup names every
part needed to write one:

    0x4004af4a  adda.l 0x46c82456,%a0     the project buffer
    0x4004af50  adda.l #0x8f262,%a0       the same base
    0x4004af56  move.b (%a0),%d4          read current
    0x4004af6e  lea 0x40027e00,%a6        the accessor
    0x4004af74  lea 0x46c76de0,%a5        THE MIRROR + 0x20 -- the saved
                                          block inside the runtime block,
                                          independently confirming
                                          mirror+0x20 == saved block again
    0x4004af62  move.l #0x95048,%d5
    0x4004af68  move.l #0x9b332,%d6       the same constants the writer at
                                          0x400288f2/f8 uses

## What is still open

Where the ENCODER delta arrives. 0x4004af20 is a key handler, not the
encoder. Everything else is now measured: the address formula, the free
bytes, the read path, the write machinery, the mask, and all five display
tables. Writing a setter from the formula above is possible without the
stock encoder path at all -- the open question is only what to hook so the
knob reaches it.

## STAGE ONE WORKS (28 Sep 2026)

Build 12, `notescale`. The two empty MIDI NOTE SETUP cells are real
parameters: the knob writes, the value is per track, it survives a track
switch, and it survived a REBOOT WITHOUT SAVING -- so it reaches the
non-volatile store, not just RAM. The four dirty flags are what made the
difference, exactly as cc-map's README says.

One defect: the screen did not redraw on a knob turn. The value changed
underneath (visible by leaving the page and coming back) but the cell kept
its old text. cc-map omits the redraw deliberately -- a CC arrives with no
page in front of it -- and the recipe was copied including that omission.
Stock's own editor calls the draw routine at 0x40036548 explicitly once its
stores are done (0x4004b008), and writes the runtime lane too
(0x46c76de0 + track*0x44 + cell, at 0x4004aff8). Both are now in the cave.

Addresses confirmed by this run: the part store, the shadow at
0x100a53b0, all four dirty flags, the current track byte 0x100b14cc and
part byte 0x100b14cf, the cell indices 3 and 5, and the encoder handler
0x4003a8e8 with its (index, delta) arguments.

## The box on MIDI NOTE SETUP (build 17)

The page's six cells all live at x 53 and beyond: the row loop puts column c
at x = 53 + c*20, each 18 wide, and a solid divider runs down x 52. Left of
it, x 3..51 by y 3..53, nothing is drawn. That is where the scale now shows.

Measured, all of it off the page's own draw routine at 0x40036548:

  surface        *(0x400bc6c0) + 0x24        (0x40036550..0x4003655e)
  track, part    0x80000000, 0x80000003      the renderer's own two bytes,
                 not 0x100b14cc/0x100b14cf -- same values, but reading what
                 the renderer reads means the box can never disagree with
                 the number in the cell beside it
  rect           0x40012254(surface, x1, y1, x2, y2, mode)
                 mode < 0 EORs, mode & 1 ORs, otherwise it clears
                 (0x40012322 and the three loops after it)
  text           0x40012bd8(font, surface, x, y, -1, string)
                 a null string draws nothing -- tested at 0x40012be8
  width          0x40012f30(font, -1, string) -> %d0
  font           0x400ba876: default glyph 3 px, per-glyph table at +8,
                 presence table at +0xc, one pixel of spacing between
                 glyphs. Eleven characters measure 43 px; the box is 49.

The value comes from the part store, NOT from the live array at 0x460d5cb4.
That array holds the last edited value, and the renderer uses it only to
decide which cell to highlight; the number a cell DRAWS is the store's byte
(0x400366ac). Reading the array here would show a stale scale on a page
entered without touching a knob.

THE HOOK. 0x40036548 takes no arguments -- it ends `lea (0x34,%sp),%sp;
rts`, and its three callers (0x4004aee2, 0x4004b008, and the layer table
entry at 0x400bc6e4) push none. So the stub can BSR a replay trampoline and
get control back after the stock row has drawn. It has to be after: the
stock body's first act is 0x40012254(surface, 3, 3, 0x6e, 0x35, 0), which
clears the whole window interior.

NOT MEASURED: any of it running. Assembled on the Mac, not here -- there is
no m68k assembler in this VM and neither the container's apt nor the GNU
mirror will serve one, so a syntax slip surfaces at `make image`, before
anything is flashed.

## Two things build 17 got wrong on the hardware

**The y axis runs bottom-up.** Everything in the box came out mirrored: the
name lines under the keyboard, the root's tick above it, the black keys
hanging off the bottom. The proof was in the stock row the whole time --
row 0's name is drawn at y 48, the font is six pixels tall (0x400ba87a holds
0x00010006), and the window interior ends at 53. 48 + 5 = 53, so 48 is the
BOTTOM of those glyphs and the larger y is the higher line; row 0 is also
the upper of the two cell rows and carries the larger y. Two facts already
measured, and I read a downward axis into both.

**Solid keys are unreadable.** Filling the in-scale keys makes six adjacent
notes one blob, and a whole-tone scale is indistinguishable from a major at
a glance. Outlining all twelve instead is worse: at a six-pixel pitch, with
one-pixel borders, it is a lattice the eye cannot count.

What works is drawing a keyboard the way a keyboard is drawn -- one lit slab
x 7..47 by y 11..37, the white keys cut apart by a one-pixel gap on a
six-pixel pitch, the black keys cut out of it down to y 23 -- and marking
the scale with a dot: a three-by-three hole in a white key, a two-by-two lit
square in a black one. dn2_scales.py asserts every dot sits strictly inside
its own key, and tools/preview drawings of the four scales before flashing
are what caught the lattice.

## The NOTE knob: an extension point, not a detour

The main NOTE page is not a SETUP window and has no layer of its own. Every
encoder A..F is bound, in the base keymap layer's encoder table at
0x400c085a, to one handler: 0x40055008. That handler resolves the current
page's descriptor through 0x40031f28 -> 0x40031ee0 -> 0x40031da4, whose jump
table picks the descriptor by page for a MIDI track (the track index arrives
as track+8, which is how the audio and MIDI halves are told apart), and for
page 0 that descriptor is 0x400d3e3e.

The descriptor carries, at +0x12a, a per-cell STEP FUNCTION:

    f(encoder, delta, value) -> the new value          called at 0x40055360
    null -> 0x4003240c, the stock add-and-clamp

For this page that table is 0x400d3f68. Slot 0, NOTE, is null. Slot 2 is
not: LEN carries 0x40040770, the same contract doing the same job for a cell
whose values are not linear. So constraining the NOTE knob to the scale is
one pointer into a hole the firmware left open -- no detour, no displaced
bytes, and the caller still clamps the result to the cell's own minimum
(0x400d3ea8, zero) and maximum afterwards.

The step table and the cell-draw table are ADJACENT: draw is +0xfa with
twelve slots, 0x400d3f38..0x400d3f67, and step begins at the next long.
This module writes 0x400d3f5c and 0x400d3f64 (draw slots 9 and 11) and now
0x400d3f68 (step slot 0). Read the draw table as sixteen slots and slot 12
lands exactly on NOTE's stepper.

Two independent facts fix the descriptor at 0x400d3e3e: its +0x9a counts are
0x80 six times over for NOTE/VEL/LEN/NOT2..4, and its +0x18a/+0x18e are the
two enable-mask longs at 0x400d3fc8/0x400d3fcc that the SETUP row's draw
routine loads by absolute address.

## The chord cells, and what a MIDI parameter's three copies are

NOT2..NOT4 are not notes. The formatter at 0x4003ba68 takes the stored byte,
subtracts 64, and -- if what is left is not zero -- adds the track's own NOTE
and draws THAT as a note name (0x4003baa8). So they are offsets biased by 64,
and an offset of zero is the cell's OFF. Locking them to the scale means
snapping the note they SOUND, note = NOTE + value - 64, and leaving 64
reachable whatever the scale says. One function serves all four cells: the
NOTE cell is the same thing with a bias of zero and no OFF.

That same formatter gave the NOTE page's storage away, because it reads the
value it needs directly:

    part store   DBPTR + part*0x18b2 + 0x8f162    + track*32   + slot
    shadow              0x100a52b0   + part*0x18b2 + track*32  + slot
    runtime lane        0x46c76dc0                 + track*0x44 + slot

read off 0x4003ba98..0x4003baa6 for the first and the stock encoder handler's
own stores at 0x4005538a, 0x400553a2 and 0x400553e6 for the other two. Each
block sits immediately before the one this module already writes: 0x8f162 +
8*32 = 0x8f262, 0x100a52b0 + 8*32 = 0x100a53b0, and the lane's +0x20 is the
SETUP row -- which is why sc_decode finds SCL at (0x23,%a0). Thirty-two bytes
of NOTE-page parameters (five pages of six) then thirty-six of SETUP, 0x44 in
all, and three of those hundred addresses were already measured a week ago
from the other end.

## What re-snapping does and does not touch

When SCL or ROT changes, sc_resnap moves the track's NOTE and its three chord
offsets onto the new scale. Trigs already in the pattern are left alone: they
already SOUND in scale, because sc_lookup snaps every note at emit time, and
rewriting them would throw away the notes they were written with -- no change
of scale gives those back.

Known wart: the snap runs on every detent, so scrolling SCL across many
scales snaps repeatedly, and a note can walk a semitone or two by the time
the knob stops. The root never moves (bit 0 of every mask is set), so a note
sitting on the root is stable whatever is dialled past it.

## The ARP page's KEY selector

Gone, and it had to go: sc_decode replaced the decode at 0x4009fad2 that read
the arp key byte, so KEY changed nothing at all. ARP is MIDI page 2,
descriptor 0x400d3fd0 (0x40031da4's jump table: 0 NOTE, 1 LFO, 2 ARP, 3
CTRL1, 4 CTRL2), and KEY is slot 11 -- formatter 0x4003b790, the key-scale
formatter, which is referenced exactly once in the image. Its row neighbours
at slots 9 and 10 are already "-----", so the cell joins them: the name
becomes dashes and its nibble in the slots-8..15 mask at 0x400d415a goes to
zero.

## The cave is 4284 bytes and two modules share it

PassOS 1.0's first build died at the linker, not the assembler:

    NOTE SCALE: notescale 4062 B linked at 0x400d6b80
    STOP GUARD stopguard at 0x400d7b80 not free

The stock zero run this repository places code in is 0x400d6b20..0x400d7c3c,
and the units are laid down in order, each aligned up to 0x80. notescale at
4062 B left 188 usable bytes; stopguard is 406. "Not free" is the allocator
finding stock bytes under the tail it was about to write -- exactly the check
that should catch this, and it did.

What went was scale_nametab and the thirty-six full-name strings behind it:
600 bytes that nothing in the module reads. The cell draws the four-character
abbreviation and the box draws the two-line split; the full name only ever
existed as a comment on each table row. Nothing else was touched.

The lesson for the next module that wants this cave: notescale is now about
3.5 KB of the 4.3 KB, and most of that is the thirty-six scales themselves.
Adding a third module here means measuring first, not hoping.

## The cave's real ceiling is the chooser list, not the zero run

The second PassOS 1.0 build got both units placed and then died on the STOP
guard's first PERSONALIZE table at 0x400d7b80. The zero run ends at
0x400d7c3c, so the address looked free -- but this remix keeps all fourteen
stock effects in the FX chooser, which is more than the seven that fit at
NEW_LIST, so build_bus relocates the list to the tail of the run:
0x400d7bbc..0x400d7c3c (build_bus.py's LONG_LIST). The real ceiling is
0x400d7bbc, and the list is written before the caves are placed, which is
why the `any(img[...])` check caught it rather than something booting wrong.

So the budget is 0x400d6b80..0x400d7bbc, 4156 bytes, for: notescale, the
STOP guard's 406, and its three seventeen-entry tables -- each of which the
builder aligns to 0x80, so three 68-byte tables cost 0x180, not 0xcc.

Another 296 bytes came out of notescale, all of it pointer tables:

  scale_abbrtab   the abbreviations are four characters at most, so they are
                  a five-byte stride now: scale_abbr + 5*scale
  scale_roottab   the same, three bytes a root
  scale_l2tab     the box's second name line FOLLOWS the first, so the draw
                  walks past the first line's terminator instead of reading
                  a second table

That is 336 bytes of pointers traded for about 24 bytes of code, and it
leaves 120 bytes between the last table and the chooser list.

## The boot screen's font has no lowercase

PassOS 1.0 flashed and booted, and the panel drew:

    P <blob> <dot> <dot> OS 1.0

which is "PassOS 1.0" with one piece of junk per lowercase letter -- P, then
a, s, s unmapped, then OS 1.0. The container field itself was right: the
tool's set_version accepts spaces and the ten characters fit exactly. It is
the font the boot screen draws with that carries no lowercase glyphs, which
is presumably why Elektron's own string is OS1.40C.

So the on-device version is upper case, PASSOS 1.0. The file name keeps the
mixed case (TAG), since nothing on the unit reads it.
