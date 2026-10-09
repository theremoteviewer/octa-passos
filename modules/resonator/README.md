# RESONATOR — eight tuned filters anything can ring through

> *"possibly to have the rings algo as an assignable effect so any sound could
> ring through its resonator?"* — Jesse, 5 Oct 2026

The drum machine's PL RNG row turned inside out: the **track's own audio** is
the exciter instead of a noise burst. On an FX1 slot it rings the track and
PLATE REV still has FX2.

| knob | what it does |
|---|---|
| PITCH | the fundamental, 200 Hz to 16 kHz |
| STRUC | partial spacing: 0 the harmonic series, 127 a free bar's modes |
| DECAY | Q, 2 to 1200 — and the high partials ring shorter at any setting |
| BRITE | the exciter's one-pole corner: how much input reaches the high partials |
| TILT | per-partial Q, drawn −64…+63; 64 is the physical case |
| MIX | dry/wet |

## ⚠️ STATUS: WRITTEN, ASSEMBLED, NOT SHIPPED — THE COLDFIRE CAVE IS FULL

The DSP side is complete and the module composes: the build clones its
descriptor, repoints **both** FX1 tables (`id table 0x400d5fb8` and
`chooser row 0x400d6084`) and places the code. It is not in `passos-pl`
because of something on the other side of the chip entirely:

```
RESONATOR      id 0x18  clone P=0x400d6b20  knobs [0, 1, 2, 3, 4, 5]
...
STOP GUARD table perso_labels at 0x400d7b80 not free
```

The ROM **name cave** — the one 5,986-byte zero run near the page
descriptors — is what a cloned page descriptor, a linked ColdFire unit and a
repointed table all come out of, and in this remix it is already spent:

| | |
|---|---:|
| NOTE SCALE (PassOS's 36 scales) | 3,148 B |
| STOP GUARD (RiDylan mode) | 406 B |
| STOP GUARD's three repointed tables | 384 B |
| alignment and the rest | the remainder |
| **left** | **88 B** |

A cloned descriptor is **384 B**. So this is not a DSP-budget problem — the
drum machine leaves 834 words of ground spare, and the whole bank costs about
300 — it is 296 bytes of ColdFire address space.

### The three ways out, cheapest first

1. **Use a stock descriptor in place, no clone.** `COMB FILTER`'s own page is
   almost exactly right for a resonator: `PTCH` (count 108, drawn as a NOTE
   NAME — better than anything a clone would give a pitch knob), `TUNE`, `LP`,
   `FB`, `MIX`. Five apt knobs, no TILT, and **zero** cave. It needs a small
   additive build change: a `MenuEntry` flag that says "take this id, leave its
   descriptor alone", which stock rows already get (`STOCK_ROWS` in
   `build_bus.py`) but a module carrying a stock id does not. Default-off, so
   every existing remix's artifacts stay bit-identical and `refhash` stays
   valid.
2. **Build the descriptor in DRAM.** `modules/analog-bassdrum/control.c`
   already does this for eleven source-machine pages (`static uint8_t
   desc[AB_MODELS][DESC_SIZE]`, published through `ab_desc_p`), which proves
   the firmware reads a descriptor from the arena perfectly well. The arena has
   megabytes. This gets the real knob names AND costs no cave, but it is a
   larger build change: the clone has to be emitted into the platform runtime
   and `FX2_IDS`/the FX1 tables poked with its link-time address.
3. **Reclaim cave.** About 232 B is recoverable from alignment — STOP GUARD's
   three 17-entry tables are padded to 0x80 each (60 B wasted apiece) and
   NOTE SCALE's tail is padded 52 B. Still 64 B short of a clone, so this only
   helps alongside something else.

Nothing here is a reason to drop NOTE SCALE: PassOS's scales are the point of
the firmware.

## Why an SVF per partial, not the drum row's two-pole form

A two-pole direct-form resonator's impulse gain is `1/sin(w)` — twelve times
larger at 563 Hz than at 5.9 kHz. A bank of them fed **one** signal is a
fundamental with seven whispers behind it unless every partial carries a
compensating weight, and that weight costs a word of state and a multiply
each — and worse, weighted on the output the low partials' **state** saturates
while the output is still a tenth of full scale. That is measured, in the drum
row, and it is why `bdring.asm` weights its strike on the way in.

An SVF's band-pass peak gain is its **Q**, the same at every frequency, so this
bank needs no weights at all. Better: its ring time is `2Q/w`, so at one Q the
high partials ring **shorter** — which is what a struck object does, and what
the drum row has to fake with per-partial decay offsets. The price is twenty
instructions a sample against nine.

## What it costs

| | |
|---|---:|
| P words | ~300 including its own two 64-word curves |
| cycles | ~200 instructions/sample (the stock PLATE REV is 184) |
| r7 state | 32 words for the bank, 48 in all, of the 132-word instance block |
| allocator | none — which is why it may take an FX1 row at all |
| X / Y | none |

⚠️ **A high-Q resonator fed a sustained tone at its own frequency rings up by
Q, and nothing here prevents that.** Impulse gain is about `f` (0.08 at
563 Hz); sustained gain is Q (up to 1200). Eighty dB apart, which no single
input scale serves. The level is set for **transients** — a drum hit, a pluck,
a percussive loop, which is what the effect is for — and a sustained tone
drives the filter into the state store's limiter, i.e. into soft clipping
rather than into a number that wraps. A struck bowl does the same thing when
you play a loud sine at it.

## Credit

The model is the one Mutable Instruments' **Rings** is built on, which is why
Jesse asked for it. Rings is MIT-licensed, © Émilie Gillet.

⚠️ **Not a port, and not matched to it.** The sources could not be fetched in
the session that wrote this (GitHub is unreachable from that sandbox, it has no
API access to the repository, and routing around a blocked fetch is not
allowed), and there is no Rings in the container to capture reference audio
from. Every number here is this module's own and what it claims is structural.
