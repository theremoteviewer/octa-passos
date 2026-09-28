"""the-passenger -- Jesse's own Octatrack firmware: the passenger mod.

PassOS 1.0. Stock 1.40C, the scale system, and the STOP guard.

Every one of the fourteen stock FX2 effects, unchanged, and nothing placed
on the DSP: the unit sounds and behaves exactly as it always did. What is
different:

  MIDI NOTE SETUP's two empty cells become SCL and ROT -- the Digitone II's
  thirty-six scales against twelve roots -- and the blank box beside them
  draws the scale's name over a keyboard with a dot on every note of it and
  a tick under the root. The NOTE page's four note cells then only reach
  notes of that scale, and every note the track emits is snapped to it.

  The ARP page's KEY selector goes: the decode it fed is now reading SCL and
  ROT, so the selector changed nothing, and a control that changes nothing
  is worse than no control.

  PERSONALIZE gains RiDylan mode. Ticked, with this unit running as the
  clock master, STOP and PLAY ask before they stop the sequencer. The
  setting survives a power cycle.

NOTE SCALE replaces ARP SCALES rather than joining it -- both answer the
same question, and both want 0x4009fad2. The ledger refuses the pair, which
is correct.

Both modules are ColdFire caves and a handful of asserted rewrites, and they
share no site. Nothing here touches the DSP, so the whole ROM cave budget is
theirs.
"""

from remix.schema import Remix

REMIX = Remix(
    name="the-passenger",
    doc="PassOS: stock 1.40C + the scale system + the STOP guard.",
    modules=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV",
             "NOTE SCALE", "STOP GUARD"),
    fallback="NONE",
)
