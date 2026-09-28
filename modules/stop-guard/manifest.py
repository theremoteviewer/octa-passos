"""STOP GUARD -- STOP and PLAY ask before they stop the sequencer.

A new PERSONALIZE row, RiDylan mode. Ticked, and with this unit running as
the clock master, pressing STOP -- or PLAY, which ends a set just as
surely -- while the sequencer plays draws the firmware's own YES/NO screen
instead: YES stops, NO leaves it playing. Unticked, or slaved to an
external clock, or already stopped, both keys behave exactly as stock.

Both keys share one answer handler, so a confirmed PLAY press STOPS rather
than doing whatever the stock PLAY handler would have done with the
modifier state as it stood at press time -- state the modal popup has
already outlived by the time anyone answers. The screen says STOP
PLAYBACK?, and that is what YES does.

WHAT IT CHANGES
  0x4004acce   the STOP key handler's press-only dispatch. Replaced; the
               stub replays stock's own two-way call when the guard does
               not apply and returns to 0x4004ace4 either way. The twenty-
               five OTHER callers of the stop routine are untouched.
  0x40061778   the PLAY key handler's first instruction, which both keymap
               tables name as key 0x28's press entry (0x400c0056 and
               0x400c063a; neither is rewritten). The stub replays the
               displaced jsr and jumps back to 0x4006177e.
  0x400b2a34   the PERSONALIZE label array, and the getter and setter
  0x400b2a74   arrays beside it: sixteen entries each, relocated to
  0x400b2ac0   seventeen by the build. The new row goes at index 15 and
               LED BRIGHTNESS moves to 16, because the screen draws the
               contiguous range 0..count-1 and one model's count hides the
               last row -- appended after LED BRIGHTNESS this row would be
               invisible there. Five reach sites are repointed; one of them
               is a `move.l #imm,%d5`, not a `lea`.
  0x40068fb2   the item count, `moveq #15` -> `moveq #16`. The model flag
               at 0x46c8d18c still adds its own one on top.

WHERE THE SETTING LIVES
  Live 0x800000a8, mirror 0x100fff38. Stock's non-volatile settings block
  at 0x100fff00 is magic + version + a 252-byte checksum, and 100 bytes of
  it are copied to 0x80000070 at boot (0x4001f340 -> 0x40020898), so every
  setting is one offset k in two blocks: live 0x80000070 + k, mirror
  0x100fff00 + k. That holds for all sixteen stock rows. 0x800000a8 is
  inside both the copy and the checksum and is referenced by NOTHING else
  in the image -- no literal anywhere in the 1,112,560 bytes, and outside
  both bulk clears. The checksum is restamped by stock: the PERSONALIZE
  edit dispatcher jumps to 0x4001f23c after calling any row's setter
  (0x40069074), so this row's write is stamped like every other.

  This is why 0x800000d4/d8/dc are the wrong place and were reported to
  fail on hardware: 0x80000070 + 100 = 0x800000d4, so they are one long
  PAST the copy. They are never restored, and a boot or any call to
  0x4001f340 overwrites whatever sits below them. A live word without its
  mirror has the same problem.

WHAT IS MEASURED AND WHAT IS NOT
  Measured, against the user's own 1.40C: every `expect` below, the three
  arrays and all five reach sites, the count expression and its model
  flag, the getter/setter contracts (taken from row 7, DIS. STOP-STOP ARM),
  the glyph pair, the popup's five arguments and its 0-means-yes handler
  (FORMAT CARD, 0x40069354), the popup busy guard, the transport long, the
  two CLOCK bits (named by the config writer at 0x400884a4), and the whole
  settings-block mechanism.

  Inferred, not measured: that 0x46c8d18c distinguishes MKI from MKII. It
  is set by a GPIO probe at 0x4001f8cc-0x4001f910 and its only effect here
  is which of the two counts a unit shows; the row order above keeps the
  hidden row hidden whichever way round it is.

  NOT measured: any of it running. No hardware, no emulator pass, and the
  popup has not been drawn. Treat this as a first draft that assembles.
"""

from remix.schema import Detour, Kind, Linked, Module, Poke, TableGrow

H = bytes.fromhex

# The stock PERSONALIZE row that must stay LAST in the relocated arrays, so
# that the model showing one row fewer hides it rather than this module's.
# stopguard.s names the same three addresses as absolute symbols; these
# assertions are what pins them.
LED_LABEL = 0x400B63F8
LED_GET = 0x40068C80
LED_SET = 0x4006907C

MODULE = Module(
    name="stop-guard",
    key="STOP GUARD",
    kind=Kind.CF_PATCH,
    doc="A PERSONALIZE row: STOP asks before it stops, while this unit "
        "is the clock master.",

    # About 300 bytes of code and text, plus the three relocated arrays the
    # build places beside it (17 longs each). A ROM cave: it is reached from
    # the panel's own arrays and from a key handler, and a DRAM unit would
    # cost 10 MiB of sample memory to carry a quarter of a kilobyte.
    linked=(
        Linked("stopguard", "modules/stop-guard/stopguard.s",
               cpu="5475", dram=False),
    ),

    detours=(
        Detour(0x4004ACCE, H("4ab9460d1aec"), "stopguard", "sg_key",
               "the STOP key's press-only dispatch; the stub replays it "
               "and returns to 0x4004ace4"),
        Detour(0x40061778, H("4eb94009b5c0"), "stopguard", "sg_play",
               "the PLAY key handler's first instruction; the stub replays "
               "it and jumps back to 0x4006177e"),
    ),

    # Sixteen stock entries, then this row, then LED BRIGHTNESS. `refs` are
    # the operands of the five reach sites, asserted against the stock array
    # address before they are repointed.
    tables=(
        TableGrow("perso_labels", old=0x400B2A34, count=15,
                  symbols=(("stopguard", "sg_label"),
                           ("stopguard", "led_label")),
                  refs=((0x40068EFE, 0x400B2A34),)),
        TableGrow("perso_getters", old=0x400B2A74, count=15,
                  symbols=(("stopguard", "sg_get"),
                           ("stopguard", "led_get")),
                  refs=((0x40068F0A, 0x400B2A74),)),
        TableGrow("perso_setters", old=0x400B2AC0, count=15,
                  symbols=(("stopguard", "sg_set"),
                           ("stopguard", "led_set")),
                  refs=((0x40069022, 0x400B2AC0),
                        (0x4006903E, 0x400B2AC0),
                        (0x40069056, 0x400B2AC0))),
    ),

    pokes=(
        Poke(0x40068FB2, expect=H("720f"), write=H("7210"),
             note="PERSONALIZE item count, 15 -> 16 (+1 more on the model "
                  "whose flag at 0x46c8d18c is set)"),

        # Assertions, not rewrites: the three stock pointers stopguard.s
        # carries as absolute symbols so the relocated arrays can put them
        # last. Writing them back unchanged is how this file pins them.
        Poke(0x400B2A70, expect=LED_LABEL.to_bytes(4, "big"),
             write=LED_LABEL.to_bytes(4, "big"),
             note="assert: PERSONALIZE label 15 is still LED BRIGHTNESS"),
        Poke(0x400B2AB0, expect=LED_GET.to_bytes(4, "big"),
             write=LED_GET.to_bytes(4, "big"),
             note="assert: PERSONALIZE getter 15 is still LED BRIGHTNESS's"),
        Poke(0x400B2AFC, expect=LED_SET.to_bytes(4, "big"),
             write=LED_SET.to_bytes(4, "big"),
             note="assert: PERSONALIZE setter 15 is still LED BRIGHTNESS's"),
    ),
)
