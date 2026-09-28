"""NOTE SCALE -- SCALE and ROOT on the two empty MIDI NOTE SETUP cells.

The two empty cells become real parameters: SCL picks one of the Digitone
II's thirty-six scales, ROT its root. They store, they survive a track
switch, they save with the project, and the note quantiser reads them. The
blank box to the left of the row -- everything at x 3..51, which this page
never draws into -- shows the scale's name over a keyboard, with a dot on
every note of the scale and a tick under the root.

The NOTE page's four note cells then only reach notes of that scale: NOTE
directly, NOT2..NOT4 through the note they sound, since they are offsets
biased by 64 from NOTE and an offset of zero is their OFF. Changing SCL or
ROT moves those four onto the new scale. Trigs already in the pattern are
not rewritten -- they already sound in scale, and rewriting them would
destroy the notes they were written with.

The ARP page's KEY selector is switched off in the same breath: the decode
it fed now reads SCL and ROT, so it changed nothing.

WHAT IT CHANGES
  0x400d3fc8   the row's 16-nibble enable mask: slots 9 and 11 switched on.
               Without this the cells draw as dashes whatever else is set.
  0x400d3e8a   slot 9's name, ---- -> SCL, and its count 128 -> 37.
  0x400d3e96   slot 11's name, ---- -> ROT, and its count 128 -> 12.
  0x400d3f2c   slot 9 and slot 11 formatters, NULL -> the stock 0..127
  0x400d3f34   number, and their cell-draw entries, NULL -> the shared
  0x400d3f5c   wrapper 0x400467a4 the other ten cells use.
  0x400d3f64
  0x40036548   the row's own draw routine. It takes no arguments, so the
               stub calls the stock body through a replay trampoline with
               BSR and gets control back to fill the blank box afterwards.
               Afterwards matters: the stock body's first act is to clear
               the window interior.
  0x4003a8e8   the SETUP row's shared encoder handler. All six encoders
               name it in the window layer's encoder table at 0x400bc60a,
               so one detour covers the row. Eight bytes displaced (the
               prologue is 4+4), replayed by the stub, which returns to
               0x4003a8f0.

WHY IT WAS INERT BEFORE
  Four probes gave those cells a name, a count, a formatter, a cell-draw
  routine and the mask. They drew, their knobs turned, and nothing stored:
  the panel's keymap layer carries a SEPARATE encoder table, and
  docs/firmware/PANEL.md says plainly that "a null encoder handler swallows
  the turn". The display tables were never the binding.

WHERE THE VALUE LIVES
  There is no offset table -- the renderer at 0x4003665c adds the cell
  index RAW:
      *(0x46c82456) + 0x8f262 + part*0x18b2 + track*0x24 + cell
  so a row's six cells are six consecutive bytes. This row is CHAN, BANK,
  PROG, ----, SBNK, ---- , putting the empty pair at +3 and +5. Both are
  zero in all 16 banks x 4 parts x 8 tracks of a real project, and neither
  is read from A0-A6 anywhere in 0x40098000..0x400a6000.

  Two independent measurements agree that the saved block is the runtime
  block plus 0x20: the file's KEY is at +0x11 and the mirror's at +0x31,
  and the editor loads 0x46c76de0 = mirror + 0x20 for its lane write.

MEASURED, against the user's own 1.40C and his own bank01.work: every
`expect` below, the address formula (read off the renderer), the store
recipe (read off this row's YES handler at 0x4004af94..0x4004afe4), the
encoder table and the handler's (index, delta) arguments, the current
track and part bytes, and the free cells. The store recipe is cc-map's --
its README is where "without the dirty flags the Part store is inert" is
written down, and this module makes the same stores in the same order.

NOT MEASURED: any of it running. No hardware and no emulator pass.
"""

from remix.schema import Detour, Kind, Linked, Module, Poke, SymbolRef

H = bytes.fromhex

NAMES = 0x400D3E54       # slot 0's name; stride 6
COUNTS = 0x400D3ED8      # slot 0's enum count; stride 4
FMTS = 0x400D3F08        # slot 0's formatter; stride 4
DRAW = 0x400D3F38        # slot 0's cell-draw routine; stride 4
MASK_HI = 0x400D3FC8     # slots 8..15, one nibble each, LSB first
STEP = 0x400D3F68        # the per-cell step function, descriptor 0x400d3e3e
                         # + 0x12a; slot 0 is NOTE, slot 2 is LEN's own
NUMERIC = 0x4003BB28     # the stock 0..127 number formatter
CELLDRAW = 0x400467A4    # the wrapper the other ten cells use
DASHES = H("2d2d2d2d0000")


def wake(slot, name, count):
    assert len(name) <= 4
    return (
        Poke(NAMES + 6 * slot, expect=DASHES,
             write=name.encode().ljust(6, b"\0"),
             note=f"MIDI NOTE slot {slot}: ---- -> {name}"),
        Poke(COUNTS + 4 * slot, expect=H("00000080"),
             write=count.to_bytes(4, "big"),
             note=f"MIDI NOTE slot {slot}: count 128 -> {count}"),
        Poke(DRAW + 4 * slot, expect=H("00000000"),
             write=CELLDRAW.to_bytes(4, "big"),
             note=f"MIDI NOTE slot {slot}: cell draw -> the shared wrapper"),
    )


MODULE = Module(
    name="note-scale",
    key="NOTE SCALE",
    kind=Kind.CF_PATCH,
    doc="SCALE and ROOT on the two empty MIDI NOTE SETUP cells.",

    linked=(
        Linked("notescale", "modules/note-scale/notescale.s",
               cpu="5475", dram=False),
    ),

    detours=(
        Detour(0x4003A8E8, H("4feffff048d70c0c"), "notescale", "sc_enc",
               "the SETUP row's shared encoder handler; the stub takes "
               "cells 3 and 5 and replays the prologue for the rest",
               pad_to=8),

        Detour(0x40036548, H("4fefffcc48d77cfc"), "notescale", "sc_draw",
               "the MIDI NOTE SETUP row draw; the stub runs the stock row "
               "through a replay trampoline and then fills the blank box "
               "at x 3..51 with the scale name and a keyboard",
               pad_to=8),

        # The scale lock itself. FUN_4009f794 is the MIDI note-trig emitter
        # for all eight tracks and runs whether or not the arp is on, so
        # these cover plain note trigs and the arp's per-step offsets alike.
        # Same two sites modules/arp-scales uses -- the ledger will refuse
        # the two modules in one image, which is correct: they are two
        # answers to the same question.
        Detour(0x4009FAD2, H("102800316606"), "notescale", "sc_decode",
               "the two-quality decode; reads SCL and ROT instead of the "
               "arp KEY byte, returns to 0x4009fb00"),
        Detour(0x4009FB74, H("41f9400d80a0"), "notescale", "sc_lookup",
               "the snap-table load, the add and the store; indexes the "
               "thirty-six-scale table, returns to 0x4009fb80"),
    ),

    # The formatters are this module's own code, so they are symbol refs
    # rather than pokes: the build fills in wherever the cave lands.
    symbol_refs=(
        SymbolRef(FMTS + 4 * 9, expect=0x00000000, unit="notescale",
                  symbol="sc_fmt_scale",
                  note="SCL draws the scale's name, not a number"),
        SymbolRef(FMTS + 4 * 11, expect=0x00000000, unit="notescale",
                  symbol="sc_fmt_root",
                  note="ROT draws the note name"),

        # The NOTE knob on the main page. Not a detour: a MIDI parameter
        # page's descriptor carries a per-cell step function at +0x12a, the
        # base layer's encoder handler 0x40055008 calls it as
        # f(encoder, delta, value) and falls back to 0x4003240c when the
        # entry is null. NOTE's entry IS null; LEN's, two slots along, is
        # 0x40040770 -- the same contract, doing the same job for a cell
        # whose values are not linear. Filling in the hole costs no bytes.
        SymbolRef(STEP + 4 * 0, expect=0x00000000, unit="notescale",
                  symbol="sc_step",
                  note="the NOTE knob steps scale notes, not semitones"),

        # NOT2..NOT4 are offsets biased by 64 from the track's own NOTE --
        # 0x4003baa8 adds them and draws the result as a note name -- so the
        # same function serves them, snapping the note they SOUND. An offset
        # of zero is the cell's OFF and stays reachable whatever the scale.
        SymbolRef(STEP + 4 * 3, expect=0x00000000, unit="notescale",
                  symbol="sc_step", note="NOT2 steps within the scale"),
        SymbolRef(STEP + 4 * 4, expect=0x00000000, unit="notescale",
                  symbol="sc_step", note="NOT3 steps within the scale"),
        SymbolRef(STEP + 4 * 5, expect=0x00000000, unit="notescale",
                  symbol="sc_step", note="NOT4 steps within the scale"),
    ),

    pokes=(
        Poke(MASK_HI, expect=H("00000101"), write=H("00001111"),
             note="MIDI NOTE slot mask: enable slots 9 and 11"),

        # The ARP page's KEY selector is dead once sc_decode is in: the
        # decode at 0x4009fad2 no longer reads the arp key byte, it reads
        # SCL and ROT. A selector that changes nothing is worse than no
        # selector, so the cell goes back to being one of that row's dashes.
        # ARP is MIDI page 2, descriptor 0x400d3fd0 (0x40031da4's jump
        # table); KEY is slot 11, formatter 0x4003b790, and its neighbours
        # 9 and 10 are already dashes.
        Poke(0x400D415A, expect=H("00001001"), write=H("00000001"),
             note="ARP slot mask: turn the dead KEY cell off"),
        Poke(0x400D4028, expect=b"KEY\0\0\0", write=b"-----\0",
             note="ARP slot 11: KEY -> the same dashes as slots 9 and 10"),
    ) + wake(9, "SCL", 36) + wake(11, "ROT", 12),
)
