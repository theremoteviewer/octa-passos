"""md-kit -- the Analog BD machine plus 20-channel USB audio out, on thirteen
of the fourteen stock effects.

repeat98's ANALOG BD (a native source machine, switchable 808/909, its own SRC
and SRC SETUP pages, upstream of stock AMP and both FX slots) with
markandrus's USB MIDI and USB AUDIO OUT TRACKS MAIN CUE (a class-compliant
MIDI port plus a 20-channel 44.1 kHz 24-bit audio input on the host: tracks
1-16, MAIN 17-18, CUE 19-20, post-FX pre-fader; MAIN/CUE Bryan T).

SPRING REV is the one thing given up. It is on neither chooser, so its 1,063
words on each payload are where the BD's engines are placed -- the build
reports which donor row it reached. The other thirteen stock effects,
PLATE REV and DARK REV among them, stay exactly as stock, on both choosers
where stock has them. The USB units are ColdFire patches on the DRAM
platform and cost the DSP nothing.

The starting point for the Machinedrum machine work: the drum machines go in
the same donor region, and this remix is the measurement of what one machine
costs with the effects otherwise untouched.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="md-kit",
    family="mods", proof=Proof.PORT,
    proof_note="unflashed; built and gated under the port, 2 Oct 2026. ANALOG BD "
               "ran on Jesse's MK1 as an octamod.app build; USB AUDIO OUT TRACKS "
               "MAIN CUE on Sam's MKII (image 64) and Tim's MKI (OCTATRICK9)",
    doc="ANALOG BD (808/909 source machine) + USB MIDI + USB AUDIO OUT TRACKS MAIN CUE, on the stock effects less SPRING REV.",
    modules=("ANALOG BD",
             "USB MIDI", "USB AUDIO OUT TRACKS MAIN CUE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "DARK REV"),
    fallback="NONE",
)
