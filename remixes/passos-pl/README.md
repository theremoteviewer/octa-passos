# passos-pl — PassOS, and a drum machine of six mechanisms

Everything PassOS 1.0 does, unchanged: the 36-scale note quantiser on **SCL**
and **ROT**, and **RiDylan mode** in PERSONALIZE, where STOP and PLAY ask first
while this unit is clock master. Plus USB MIDI and 20 channels of USB audio.

What is new is the drum machine. Eleven rows, **six different ways of making a
sound**, and **six working parameters on every one of them**:

| row | mechanism |
|---|---|
| 001 808 | a body oscillator with a pitch sweep — bit-identical to stock |
| 002 909 | a body plus its own noise and desk — bit-identical |
| 003 TRX CH | band-passed noise, closed — **measured** against the real machine |
| 004 TRX OH | the same engine, open |
| **005 PL HAT** | six square oscillators at inharmonic ratios, band-passed |
| **006 PL SNR** | two rung shell modes over a bed of wires |
| **007 PL CLP** | five noise bursts 5.8 ms apart, then a wash |
| **008 PL FM** | two-operator FM with a falling index: bells, zaps, woodblocks |
| **009 PL TOM** | the body engine at a 180 Hz base |
| **010 PL CNG** | the body engine at 310 Hz, shorter |
| **011 PL RNG** | six tuned two-pole resonators struck by a noise burst, 32 ms to 4.75 s |

Eight mechanisms across eleven rows.

## Six parameters, and every one of them measured

> *"not all of the parameters work. In fact I'd like each of the drums to have
> 6 parameters."* — Jesse, 5 Oct 2026

Six rows named three knobs and drew `--` for the other three. So each
renderer's own fixed constants became knobs:

| row | 0–2 | 3 | 4 | 5 |
|---|---|---|---|---|
| TRX CH / OH | PITCH DECAY WIDTH | **SWEEP** the band glides to | **ATK** a bipolar transient shaper | **DRIVE** |
| PL HAT | PITCH DECAY METAL | **SPRD** how far apart the six oscillators sit | **RES** the band-pass Q | **DRIVE** |
| PL SNR | PITCH DECAY SNAP | **RATIO** where body 2 sits | **NDEC** how long the wires ring on | **DRIVE** |
| PL CLP | PITCH DECAY ROOM | **SPRD** the gap between bursts | **REPS** how many | **DRIVE** |
| PL FM | PITCH DECAY RATIO | **INDEX** how much modulation | **IDEC** how fast it falls | **DRIVE** |
| PL RNG | PITCH DECAY STRUC | **BRITE** the strike | **POS** which partials are emphasised | **DRIVE** |

Eleven of the fifteen new ones cost **nothing per sample** — they are
decode-time, and the decode runs once per block per track. DRIVE costs three
instructions: it folds into GAIN as 1/8…1 and three `asl` give 1×…8×, with the
output store's own limiter as the clipper.

⚠️ **Every knob 3 and 4 is neutral at 64, and DRIVE is unity at 0.** A row's
defaults apply only to a *new* assignment, so a track that existed before this
build arrives holding exactly those bytes — anything else would mean a build
that only *added* parameters detuned every stored Part.

⚠️ **And every knob is gated, not just named.** `tools/harness/bdnoise.py`
renders each of the six at 20 and at 110, everything else at its stored
default, and refuses a knob whose output does not move — on either side, so a
knob that saturates a third of the way up fails too. That gate caught the FM
engine's IDEC moving the output by 0.01 of peak: the shared decode was
overwriting the slot it kept its state in, every block (AGENTS.md).

## Why mechanisms and not settings

The Machinedrum set (`the-passenger-md`) was **one renderer** — noise through a
band-pass — at different table indices. It passed every distinctness gate in
the tree, twice, and Jesse's verdict after flashing it was still *"the
different decay times are cool, but I'm looking for each sound to be
different"* (5 Oct 2026).

He was right, and the gates could not have told me. They all measured
**parameters**. A parameter is not a mechanism: band-passed noise with a long
decay is band-passed noise. So a row now names its renderer
(`dspnoise.BASES`'s engine field, read by the DSP from the model id) and the
separation gate counts a different renderer as **absolute** — no knob setting
turns six oscillators into a noise burst.

Every knob is named per engine for the same reason: **METAL** on the hat is a
filter corner, **SNAP** on the snare is a dry/wet mix, **ROOM** on the clap is
how much wash. A knob called WIDTH that means five things is how a user learns
to distrust the labels.

## The model set, and what is and is not claimed

The set — analog kick, analog snare, analog hi-hat — is the one Mutable
Instruments' **Plaits** offers, which is what Jesse asked for, and **PL RNG**
is the modal resonator **Rings** is built on, which he asked about next
(*"Also interested in the rings algo"*). Both are MIT-licensed, © Émilie
Gillet, and credited as the reference for *which* models are worth having.

⚠️ **These are not a port of Plaits or Rings and are not matched to either.**
Neither set of sources could be fetched in the session that wrote them (GitHub
is unreachable from that sandbox, it had no API access to the repository, and
routing around a blocked fetch is not allowed), and no Plaits or Rings hardware
or emulator exists in the container to capture reference audio from — so there
was nothing to port from and nothing to measure against. Each engine is written
from published behaviour: the TR-808's six-oscillator hi-hat, a two-mode snare
shell over a noise bed, a clap's burst train, a bank of tuned resonators struck
by a burst.

The gates are therefore **structural**, not comparative: each engine sounds,
fills the whole interleaved stereo block, lands where its own constants ask,
stops, survives retriggering, and shares neither a mechanism nor a reachable
parameter with any other row. The Machinedrum engines, which *do* have measured
targets from emulator captures, keep them —
`tools/harness/bdnoise.py` marks which numbers are which.

## What it costs

| | |
|---|---|
| given up | **SPRING REV, DARK REV, COMPRESSOR, LO-FI, DJ EQ, COMB FILTER** |
| ground | 3,376 words per payload (3,469 less PLATE's 93-word tail, relocated) |
| used | 2,542, leaving 834 |
| X | the 909 tables' alignment pad holds the 16-word machine table; no new curves |
| cycles | CLP 72, CH/OH 81, FM 82, HAT 117, SNR 124, RNG 156 instructions/sample — the 808 is 219 |

### Jesse's two limits, and the answer to his question

> *"is Plate ver less 'expensive' than dark verb? Keep the one that gives us
> more options. I also want to keep chorus, so those are our limits."*

**PLATE, and it is not close.** It is cheaper in words (594 against DARK's
1,067) and in cycles (183.9 against 193.2 instructions per sample) **and** it
gives more ground, because keeping DARK instead would mean preserving the
35-word helper DARK calls three times inside SPRING's span. CHORUS is kept.

### Why six effects are one run

**PLATE's 93-word tail sits at the top of DARK's span**, between DARK's body
and COMPRESSOR, so keeping PLATE used to *split* the ground into 2,037 words
below the tail and 1,339 above — and a module is one code stream, which can use
only one run. The build now **copies** that routine to the top of the engine,
fixes the one absolute address inside it and retargets PLATE's own call
(`tools/build/ab_image.py`'s `RELOC`), so the run continues through all four
effects above it. 2,037 words became 3,376 without giving up a reverb.

`tools/harness/verify_analog_bd_reverbs.py` checks the copy word by word with
its fixup applied, that every live caller points at the copy and none at the
original, and that all thirteen stock effects with DSP code either match stock
exactly on both cores or dispatch to the null stub and render a passthrough.

Kept: FILTER, SPATIALIZER, EQUALIZER, PHASER, FLANGER, CHORUS, PLATE REV and
DELAY — which costs no DSP words because it runs on the ColdFire.

⚠️ **Off both choosers, not just FX2.** The four effects above the tail are
overwritten by drum engines, so the remix names its FX1 list explicitly. A
remix that leaves that field empty gets the *stock* FX1 chooser, which would
have offered COMPRESSOR, LO-FI, DJ EQ and COMB FILTER on every FX1 slot with a
bass drum behind each one — AGENTS.md, "an FX2 id is also an FX1 id". The
selftest's derived-harvest gate caught exactly that in this remix.

Every given-up id dispatches to the null stub, so a Part saved before this
build that still names one passes audio through dry instead of jumping into the
middle of a drum voice.

## Status

| | |
|---|---|
| NOTE SCALE + STOP GUARD | Jesse's MK1, 28 Sep 2026 (PassOS 1.0) |
| ANALOG BD 808/909 | the same MK1, passOS MD test 03–05 |
| TRX OH | the same MK1, test 05 |
| USB AUDIO OUT TRACKS MAIN CUE | Sam's MKII (image 64), Tim's MKI (OCTATRICK9) |
| **PL HAT / PL SNR / PL CLP / PL FM / PL RNG** | **unflashed, and no matched reference exists** |
| the six-parameter work | **unflashed** — gated by `bdnoise.py`'s knob check |

`make check REMIX=passos-pl` is the floor; the ColdFire-port gate needs a
Python package the build sandbox cannot install, so it is the one check that
does not run there.
