# the-passenger-md — PassOS with the drum machine and USB audio

Jesse's own Octatrack firmware with two things added. Everything PassOS 1.0
does is unchanged; the subtractions are SPRING REV and DARK REV.

## From PassOS 1.0 (`the-passenger`)

- **NOTE SCALE** — MIDI NOTE SETUP's two empty cells become **SCL** and
  **ROT**: the Digitone II's thirty-six scales against twelve roots, with the
  scale drawn over a keyboard in the blank box beside them, a dot on every note
  of the scale and a tick under the root. The NOTE page's four note cells then
  only reach notes of that scale, and every note the track emits is snapped to
  it — the arpeggiator's per-step offsets included, because the quantiser is
  the MIDI note-trig emitter for all eight tracks and runs whether or not ARP
  MODE is on. The ARP page's KEY selector is retired: it fed the same decode,
  which now reads SCL and ROT, and a control that changes nothing is worse than
  no control.
- **STOP GUARD** — PERSONALIZE gains RiDylan mode. Ticked, with this unit as
  clock master, STOP and PLAY ask before they stop the sequencer. Survives a
  power cycle.

## Added

- **ANALOG BD** (repeat98) — a native source machine on any FLEX track,
  upstream of stock AMP and both FX slots, with its own SRC and SRC SETUP pages
  and an engine browser (RIGHT on the machine chooser, or a double-tap on the
  track). **Seven machines on two voices:** the 808 and 909 bass drums on the
  body oscillator, and TRX CH, TRX OH, EFM HH, TRX CY and TRX MA on core B's
  noise voice — noise through a resonant band-pass, where PITCH is the band
  centre and WIDTH its Q
  ([DSPNOISE.md](../../modules/analog-bassdrum/DSPNOISE.md)).
- **USB MIDI + USB AUDIO OUT TRACKS MAIN CUE** (markandrus; MAIN/CUE Bryan T) —
  a class-compliant MIDI port and twenty 24-bit channels at 44.1 kHz into a
  computer: the eight tracks' L/R post-FX pre-fader on 1–16, MAIN on 17–18, CUE
  on 19–20.

## The two subtractions

**SPRING REV and DARK REV.** SPRING's 1,063 words alone do not hold the noise
voice, so DARK goes too — 2,037 words of ground on each payload, 1,138 used.
The other eleven stock effects, PLATE REV included, are untouched.

⚠️ **2,037, not 2,130.** PLATE REV is kept, and PLATE calls a 93-word routine
that lives at the **top of DARK's span** (`stock.CROSS_ENTRIES`, DARK +0x3ce;
A P:0x1a47, B P:0x1807). Those words stay exactly where stock linked them and
the ground stops below them. `stock.py` had said no effect's span was entered
from outside, citing a reachability sweep that cannot see a span boundary;
placing the engines over PLATE's tail left PLATE rendering 328 instructions
short of stock (3 Oct 2026). `tools/verify/verify_stock_spans.py` re-derives
the real map from the user's own image now.

The 35-word helper inside SPRING that this remix used to copy out and retarget
is simply dropped: all seven of its callers are in SPRING or DARK.

**Both given-up ids dispatch to the null stub**, DARK's as well as SPRING's.
Off both choosers neither can be picked, but a Part saved before this build
still names its id and the loader dispatches whatever the Part names — so a
track still set to either passes audio through dry. `verify_analog_bd_reverbs`
holds PLATE to stock on both cores, checks the reserved words are stock bytes,
and checks both stubs.

## Why these four compose

They spend different budgets. The scale system and the STOP guard are ColdFire
**ROM caves**; the USB units are ColdFire patches on the **DRAM platform**; only
ANALOG BD places **DSP** words. The build's ledger refuses two modules that
claim the same site, and it did not — but see the budget note below.

```
NOTE SCALE: notescale 3148 B linked at 0x400d6b80
STOP GUARD: stopguard  406 B linked at 0x400d7800
analog bd A/B: glue + 808/909/core B 1138 words at SPRING+DARK's ground (2037, 93 reserved)
cave: 0x400d7b44..0x400d7bbc, 120 B of cave left
```

⚠️ **120 bytes of ROM cave left.** That is the binding budget for this
selection, not DSP words. Another ColdFire module does not fit without moving
something.

## Status

**Unflashed as a combination.** Each part has run on hardware:

| part | where |
|---|---|
| NOTE SCALE + STOP GUARD | ⚠️ **disputed — see below** |
| ANALOG BD | the same MK1, as an octamod.app build |
| USB AUDIO OUT TRACKS MAIN CUE | Sam's MKII (image 64), Tim's MKI (OCTATRICK9) |
| ANALOG BD + USB together | Jesse's MK1 as `md-kit`, 2 Oct 2026 — kicks confirmed |

⚠️ **The two PassOS modules' proof is weaker than it first looked.** Both
manifests say in their own docstrings "NOT MEASURED: any of it running. No
hardware and no emulator pass", and stop-guard adds "the popup has not been
drawn. Treat this as a first draft that assembles." A session note records
PassOS 1.0 being flashed and called a stable 1.0 on Jesse's MK1 on 28 Sep 2026,
which would make them HARDWARE. **The two disagree.** The docstring is the
module's primary source, so both are declared `Proof.CHECK` here and the
contradiction is written into each `proof_note` rather than resolved by
guessing. Their author is the one who can settle it.

`make check REMIX=the-passenger-md`: 222 gates pass. The cycle registry reports
**blocked** rather than a number, because ANALOG BD declares `pressure_blocker`
— the registry sees it as a ColdFire module and misses the DSP source engines.
Its own benchmarks are in [CPU.md](../../modules/analog-bassdrum/CPU.md), in
executed instructions, which must not be added to the cycle budget.

## Not in this yet

**Snares and claps.** Seven machines run as code — the two bass drums on the
body oscillator and five hats, cymbals and maracas on core B. TRX SD needs a
second oscillator (body plus noise, summed) and the claps are burst trains
whose measured 26 ms attack core B's envelope does not reproduce; both are
still float reference models scored against emulator captures, with no DSP
assembly written. `out/md-machines/NOTES.md` sections 11–15 has the
measurements and what remains.

Core B's five are verified as DSP output against measured targets (−30 dB
points within 12 %, spectral-envelope correlation +0.20 to +0.66), which is an
implementation check, not an authenticity score. EFM HH is the weakest: right
envelope, and a spectrum one band cannot hold.

NOTE SCALE replaces ARP SCALES rather than joining it: both answer the same
question and both want `0x4009fad2`, and the ledger refuses the pair, which is
correct.

## Where this got to, and why the work moved on (5 Oct 2026)

Closed, not abandoned. Five images went to Jesse's MK1 from this remix; this
is the record of what each one taught, because the engines and the gates are
still here and a later session may want them.

| build | on the unit |
|---|---|
| test 01 | the scale system, the STOP guard and the popup all worked; 808 and 909 kicks confirmed |
| test 02 | the scroll bug Jesse found with ten rows, fixed; hats not yet in |
| test 03 | hats in. A hat on T2 **ring-modded the 808 on T1**; CY and MA **rang continuously after the trig was removed**; OH and HH **sounded the same as CH** |
| test 04 | all five worked and stopped. "Other than the 808 and 909 they all do and sound the same" |
| test 05 | still the same as each other — the knob trim, fixed. "The different decay times are cool, but I'm looking for each sound to be different" |

Four defects, each found on hardware and none visible to any gate in the tree
at the time:

1. **The engine wrote one word per sample into an interleaved stereo block.**
   One bug, three symptoms: the ring modulation (the stale half held the other
   track's kick), the tone that outlived the trig (the stale half of its own
   attack, repeating at the 2,756 Hz block rate), and much of the sameness. The
   harness had rendered it clean five times because it read `a[::2]` — it
   modelled the stride instead of reading the block.
2. **The coefficients were at half scale.** `f` and `damp` are stored halved
   because they do not fit Q23, and the engine never restored them — its own
   comment claimed the multiply did, which is the belief AGENTS.md's trap
   refutes. Every band came out at 0.57× and every Q at double, which is why
   five different machines all sounded like one ringy hat.
3. **A row's identity was its knob defaults**, and selecting a row writes only
   the model id. On an existing track all five rows ran the same numbers.
4. **The knob trim was ±64 and clamped**, so a Part holding 127 put three of
   the five on identical indices.

⚠️ **And the thing that was still true after all four were fixed:** the set was
ONE renderer. Every fix above made the parameters more correct and more
distinct, and the parameters were never the problem. `tools/harness/bdnoise.py`
could prove the five differed in band and decay at every knob position, and
Jesse could still hear one machine. **A parameter is not a mechanism.** That is
what moved the work to `remixes/passos-pl`, where a row names its renderer.

What is worth keeping from here: the five Machinedrum machines have **measured
targets** from emulator captures of the real hardware (−30 dB point and band
per machine, `out/md-machines/NOTES.md` section 15), which none of the
percussion engines have. TRX OH is carried into `passos-pl` for exactly that
reason. The other four — TRX CH, EFM HH, TRX CY, TRX MA — are one line each in
`dspnoise.BASES` and can come back whenever a band-passed noise hat is wanted
beside the mechanisms.
