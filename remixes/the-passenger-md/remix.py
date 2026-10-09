"""the-passenger-md -- PassOS with the drum machine and USB audio.

Jesse's own Octatrack firmware (`the-passenger`, PassOS 1.0: the scale system
and the STOP guard) with repeat98's ANALOG BD source machine and markandrus's
USB MIDI + USB AUDIO OUT TRACKS MAIN CUE added. What PassOS 1.0 already does
is unchanged:

  MIDI NOTE SETUP's two empty cells are SCL and ROT -- the Digitone II's
  thirty-six scales against twelve roots -- with the scale drawn over a
  keyboard beside them. The NOTE page's four note cells only reach notes of
  that scale, and every note the track emits is snapped to it, the
  arpeggiator's per-step offsets included.

  PERSONALIZE's RiDylan mode: as clock master, STOP and PLAY ask first.

What is added:

  ANALOG BD on any FLEX track -- a native source machine upstream of stock AMP
  and both FX slots, with its own SRC and SRC SETUP pages and an engine
  browser. Seven machines on two voices: the 808 and 909 bass drums on the
  body oscillator, and TRX CH, TRX OH, EFM HH, TRX CY and TRX MA on core B's
  noise voice (modules/analog-bassdrum/DSPNOISE.md).

  Twenty 24-bit channels at 44.1 kHz into a computer over USB: the eight
  tracks' L/R post-FX pre-fader on 1-16, MAIN on 17-18, CUE on 19-20.

**SPRING REV and DARK REV are given up** -- the noise voice does not fit in
SPRING alone, and the two are the only difference from PassOS 1.0's effect
list. That is 2,037 words of ground on each payload, where the glue and all
three voices go (1,138 used).

⚠️ 2,037, NOT 2,130. PLATE REV is kept, and PLATE calls a 93-word routine that
lives at the TOP of DARK's span (stock.CROSS_ENTRIES, DARK +0x3ce). Those 93
words stay exactly where stock linked them; the ground stops below them. The
35-word helper inside SPRING that this remix used to copy out and retarget is
simply dropped now -- all seven of its callers are in SPRING or DARK.

Both given-up ids dispatch to the null stub, DARK's as well as SPRING's: off
both choosers neither can be picked, but a Part saved before this build still
names its id and the loader dispatches whatever the Part names.

The scale system and the STOP guard are ColdFire caves; the USB units are
ColdFire patches on the DRAM platform; only ANALOG BD places DSP words. So
the four additions do not compete for the same budget, which is why they
compose at all.

⚠️ "All of the machines" is NOT this yet. Seven run as code: the two bass
drums and core B's five hats, cymbals and maracas. Snares and claps do not --
TRX SD needs a second oscillator and the claps are burst trains whose measured
26 ms attack core B's envelope does not reproduce. Both are still float models
scored against emulator captures (out/md-machines/NOTES.md sections 13-15).
They land in this remix as they are written.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="the-passenger-md",
    family="mods", proof=Proof.PORT,
    proof_note="unflashed as a combination. PassOS 1.0 (NOTE SCALE + STOP GUARD) ran on "
               "Jesse's MK1, 28 Sep 2026; ANALOG BD ran on the same MK1 as an octamod.app "
               "build; USB AUDIO OUT TRACKS MAIN CUE on Sam's MKII (image 64) and Tim's MKI "
               "(OCTATRICK9); ANALOG BD + USB together as md-kit on Jesse's MK1, 2 Oct 2026",
    doc="PassOS (36-scale note quantiser + STOP guard) + ANALOG BD + USB MIDI + 20-channel USB audio, on the stock effects less SPRING REV.",
    modules=("NOTE SCALE", "STOP GUARD",
             "ANALOG BD",
             "USB MIDI", "USB AUDIO OUT TRACKS MAIN CUE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV"),
    fallback="NONE",
)
