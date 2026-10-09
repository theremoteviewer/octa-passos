"""passos-pl -- PassOS with a drum machine of six mechanisms, and USB audio.

Jesse's own Octatrack firmware (`the-passenger`, PassOS 1.0) with repeat98's
ANALOG BD grown into a six-row drum machine, plus markandrus's USB MIDI and
USB AUDIO OUT TRACKS MAIN CUE. What PassOS 1.0 does is unchanged:

  MIDI NOTE SETUP's two empty cells are SCL and ROT -- the Digitone II's
  thirty-six scales against twelve roots -- with the scale drawn over a
  keyboard beside them. The NOTE page's four note cells only reach notes of
  that scale, and every note the track emits is snapped to it, the
  arpeggiator's per-step offsets included.

  PERSONALIZE's RiDylan mode: as clock master, STOP and PLAY ask first.

What is different from passos-md
--------------------------------
⚠️ SIX MECHANISMS, NOT ONE ENGINE AT SIX SETTINGS. The Machinedrum set was
one renderer -- noise through a band-pass -- at different table indices, and
Jesse's verdict after flashing it twice was "the different decay times are
cool, but I'm looking for each sound to be different" (5 Oct 2026). He was
right, and no distinctness gate could have told me: they all measured
PARAMETERS, and a parameter is not a mechanism.

So the browser is eleven rows over eight different ways of making a sound:

  001 808      a body oscillator with a pitch sweep        (bit-identical)
  002 909      a body plus its own noise and desk          (bit-identical)
  003 TRX CH   band-passed noise, closed -- measured against the real machine
  004 TRX OH   the same engine, open
  005 PL HAT   six square oscillators at inharmonic ratios, band-passed
  006 PL SNR   two rung shell modes over a bed of wires
  007 PL CLP   five noise bursts 5.8 ms apart, then a wash
  008 PL FM    two-operator FM with a falling index: bells, zaps, woodblocks
  009 PL TOM   the body engine at a 180 Hz base
  010 PL CNG   the body engine at 310 Hz, shorter
  011 PL RNG   six tuned two-pole resonators struck by a noise burst

SIX PARAMETERS ON EVERY ROW, AND EVERY ONE OF THEM MEASURED TO DO SOMETHING.
Jesse, 5 Oct 2026: "not all of the parameters work. In fact I'd like each of
the drums to have 6 parameters." Six rows named three knobs and drew "--" for
the other three; one of the three that WAS named had been dead for two builds.
So each renderer's own fixed constants became knobs:

  003/004 TRX CH/OH   PITCH DECAY WIDTH | SWEEP the band glides to, ATK a
                      bipolar transient shaper, DRIVE
  005 PL HAT          PITCH DECAY METAL | SPRD how far apart the six
                      oscillators sit, RES the band-pass Q, DRIVE
  006 PL SNR          PITCH DECAY SNAP  | RATIO where body 2 sits, NDEC how
                      long the wires ring on, DRIVE
  007 PL CLP          PITCH DECAY ROOM  | SPRD the gap between bursts, REPS
                      how many, DRIVE
  008 PL FM           PITCH DECAY RATIO | INDEX how much modulation, IDEC how
                      fast it falls, DRIVE
  011 PL RNG          PITCH DECAY STRUC | BRITE the strike, POS which partials
                      are emphasised, DRIVE. STRUC blends the partials from the
                      harmonic series to a free bar's modes; the ring is 32 ms
                      to 4.75 s

Eleven of the fifteen new ones cost NOTHING per sample: they are decode-time,
and the decode runs once per block per track. DRIVE costs three instructions
-- it folds into GAIN as 1/8..1 and three `asl` give 1x..8x with the output
store's own limiter as the clipper -- and it is unity at its stored default of
zero, so a Part saved before this build renders the same words it did.

⚠️ AND EVERY KNOB IS GATED, not just named. `tools/harness/bdnoise.py` renders
each of the six at 20 and at 110 with everything else at its STORED default
and refuses a knob whose output does not move, on either side. That gate found
the FM engine's IDEC moving the output by 0.01 of peak: the shared decode was
overwriting the slot it kept its state in, every block (AGENTS.md).

  Twenty 24-bit channels at 44.1 kHz into a computer over USB: the eight
  tracks' L/R post-FX pre-fader on 1-16, MAIN on 17-18, CUE on 19-20.

The model set is the one Mutable Instruments' Plaits offers -- analog kick,
analog snare, analog hi-hat -- which is what Jesse asked for, and PL RNG is
the modal resonator Rings is built on, which he asked about next ("Also
interested in the rings algo", 5 Oct 2026). Both are MIT-licensed, (c) Emilie
Gillet, and credited as the reference for WHICH models are worth having.

⚠️ NOT A PORT OF PLAITS OR RINGS, AND NOT MATCHED TO EITHER. Neither set of
sources could be fetched in the session that wrote this (GitHub is unreachable
from that sandbox and it had no API access to the repository, and routing
around a blocked fetch is not allowed), and no Plaits or Rings hardware or
emulator exists in the container to capture reference audio from -- so there
was nothing to port from and nothing to measure against. Every engine is
written from published circuit behaviour and the gates are STRUCTURAL: it
sounds, it fills the whole stereo block, it stops, it survives retriggering,
and no two rows share a mechanism or a reachable parameter. Nothing here
claims to be within a given percentage of a real Plaits. The Machinedrum
engines, which DO have measured targets, keep them.

What it costs
-------------
Six stock effects are given up -- SPRING REV, DARK REV, COMPRESSOR, LO-FI,
DJ EQ and COMB FILTER -- which is one contiguous run of 3,469 words, less the
93 that PLATE REV calls into inside DARK's span (stock.CROSS_ENTRIES): 3,376
words of ground on each DSP payload. 2,542 are used, leaving 834. Toms and
congas cost nothing at all: the body engine's per-machine base frequency
(dsp808.MACHINE_BASE_HZ) has existed unused since it was written, and a row
there is one already-allocated X word.

⚠️ AND THE SIX ARE ONE RUN ONLY BECAUSE PLATE'S TAIL IS RELOCATED. PLATE's
93-word tail sits at the TOP of DARK's span, between DARK's body and
COMPRESSOR, so keeping PLATE used to SPLIT the ground into 2,037 words below
the tail and 1,339 above -- and a module is one code stream, which can only
use one run. The build now COPIES that routine to the top of the engine,
fixes the one absolute address inside it and retargets PLATE's own call
(tools/build/ab_image.py's RELOC), so the run continues through all four
effects above it. That is what turned 2,037 words into 3,376 without giving up
a reverb, and `tools/harness/verify_analog_bd_reverbs.py` checks the copy word
by word with its fixup applied, that every live caller points at the copy and
none at the original, and that all thirteen stock effects with DSP code either
match stock exactly or dispatch to the null stub.

Jesse's limits, 5 Oct 2026: keep ONE reverb and keep CHORUS. PLATE is the one
to keep -- it is cheaper in both words (594 against DARK's 1,067) and cycles
(183.9 against 193.2 instructions per sample) AND it gives more ground, because
keeping DARK instead would mean preserving the 35-word helper DARK calls three
times inside SPRING's span.

Kept: FILTER, SPATIALIZER, EQUALIZER, PHASER, FLANGER, CHORUS, PLATE REV, and
DELAY -- which costs no DSP words at all, because it runs on the ColdFire.

⚠️ AND OFF BOTH CHOOSERS, NOT JUST FX2. The four effects above the tail are
overwritten by drum engines, so the remix names its FX1 list explicitly: a
remix that leaves that field empty gets the STOCK FX1 chooser, which would
have offered COMPRESSOR, LO-FI, DJ EQ and COMB FILTER on every FX1 slot with
a bass drum behind each one. AGENTS.md, "an FX2 id is also an FX1 id".

Every given-up id dispatches to the null stub, so a Part saved before this
build that still names one passes audio through dry rather than jumping into
the middle of a drum voice.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="passos-pl",
    family="mods", proof=Proof.PORT,
    proof_note="unflashed. PassOS 1.0 (NOTE SCALE + STOP GUARD) ran on Jesse's MK1, "
               "28 Sep 2026; ANALOG BD's 808/909 and the Machinedrum hats ran on the "
               "same MK1 as passOS MD test 03-05, 3-5 Oct 2026; USB AUDIO OUT TRACKS "
               "MAIN CUE on Sam's MKII (image 64) and Tim's MKI (OCTATRICK9). The "
               "percussion engines and the resonator bank are unflashed and have no "
               "matched reference",
    doc="PassOS (36-scale note quantiser + STOP guard) + an eleven-row drum machine of "
        "six mechanisms, six working parameters each + USB MIDI + 20-channel USB audio, "
        "on the stock effects less SPRING, DARK, COMPRESSOR, LO-FI, DJ EQ and COMB.",
    modules=("NOTE SCALE", "STOP GUARD",
             "ANALOG BD",
             "USB MIDI", "USB AUDIO OUT TRACKS MAIN CUE",
             "FILTER", "SPATIALIZER", "EQUALIZER", "PHASER", "FLANGER", "CHORUS",
             "DELAY", "PLATE REV"),
    # ⚠️ AND THE FX1 CHOOSER HAS TO SAY SO TOO. Leaving this empty means "the
    # stock FX1 list", which carries COMPRESSOR, LO-FI, DJ EQ and COMB FILTER
    # -- four effects this remix OVERWRITES with drum engines. The build
    # harvested them either way (their words are the ground it needs), so the
    # unit would have offered four FX1 entries whose code is now a bass drum:
    # AGENTS.md's "an FX2 id is also an FX1 id", which is how Rungs and Nimbus
    # sat on EQUALIZER and DJ EQ in every local image for four days. Caught by
    # the selftest's derived-harvest gate, which asks the two choosers and the
    # placer the same question and refuses an answer that differs.
    fx1=("FILTER", "SPATIALIZER", "EQUALIZER", "PHASER", "FLANGER", "CHORUS"),
    fallback="NONE",
)
