# Core B — the noise/metallic voice (hats, cymbals, maracas)

The second of the two signal paths the TRX/EFM family splits into. Core A is a
body oscillator (`DSP808.md`, `DSP909.md`): tuned, with a pitch sweep, and
bass-drum-shaped by construction. **No knob setting on a body oscillator makes
a hi-hat**, which is why every machine in the browser before this one was a
variation on a kick however it was labelled.

    24-bit LCG noise -> resonant state-variable band-pass -> amp envelope -> gain

`bdnoise.asm` is the engine, `dspnoise.py` its tables, `tools/harness/bdnoise.py`
the renderer that runs it on the real DSP, and `tools/trxnoise.py` the float
reference it is fitted against. The structure and every number come from
measuring the machines in an emulator and fitting the band and width to their
spectral descriptors — not from a circuit model.

## What it costs

| | |
|---|---|
| P words | 102, inside the glue + 808 + 909 stream (1,138 total) |
| X words | 192: three 64-entry tables at X:0x3880..0x393f |
| voice blocks | **none of its own** — it borrows the 909's |
| cycles | two multiplies and two adds per sample for the filter, plus the LCG |

The borrowed voice block is the whole reason it fits. A track runs one engine
or the other, never both, so the 909's block is free whenever a core B machine
is on the track — and it carries the knob block at +0x30 that every voice
needs and that a block of its own could not have afforded.

⚠️ **The trigger zeroes BAND, LOW and ENV before the first sample**, because
what is in them is whatever the 909 left. A track that was a 909 and is now a
hat hands this engine a filter mid-swing, and a resonator started from a large
state rings on its own. That is AGENTS.md's "a persistent slot init does not
clear" met head-on, and it is the one line of this engine that exists for a
reason you cannot hear in a clean render.

## Where it stands, measured through the DSP

A machine is **one packed X word** -- `band<<16 | decay<<8 | width`, in
`dspnoise.BASES`, read by the engine from the model id -- and no per-machine
code. Each knob is a **±16-step trim** around that base, not a full-range
sweep, and the span is a correctness property: see "the trim" below. `tools/harness/bdnoise.py` renders each one through the real DSP with
**identical neutral knobs** and holds it to five things: it sounds, it fills
the whole stereo block, it lands on its band, it stops, and it is
distinguishable from every other row.

| machine | −30 dB: real / engine | band: real / engine | tail after 3 s |
|---|---:|---:|---:|
| TRX CH | 114.0 / 121.9 ms | 5046 / 4608 Hz | −200 dB |
| TRX OH | 536.4 / 516.6 ms | 5046 / 4608 Hz | −200 dB |
| EFM HH | 43.5 / 46.4 ms | 4294 / 4565 Hz | −200 dB |
| TRX CY | 787.8 / 777.9 ms | 2374 / 2110 Hz | −200 dB |
| TRX MA | 21.1 / 23.2 ms | 7098 / 7709 Hz | −200 dB |

Every decay within 10 %, every band within 13 %, and all ten pairs separated
by either band or decay. `python3 tools/harness/bdnoise.py` reproduces the
table; it runs in `make check`.

Cost: **49.8 instructions/sample at peak**, a quarter of the 808's (`CPU.md`).

## Two mistakes worth keeping written down

**A decay table the engine did not read.** `knob_for_decay` mapped against the
808's shared curve while the engine read its own, and every envelope came out
wrong with nothing pointing at the mismatch. Then the 808's curve turned out
not to reach a 21 ms maraca or a 43 ms closed hat at all — it bottoms out at
57 ms, so both pinned to knob 0. Core B has its own 64-entry `N_DE`, 8 ms to
1.2 s, for 64 words.

**"86 % of energy above 5 kHz" read as "high-pass it".** Blending a high-pass
in pushed TRX CH's centroid to 10,916 Hz against a measured 6,312. That 86 %
is what a band-pass at ~5.9 kHz *produces*; it is not something to add on top.
Removing the stage and fitting band and width to the measured centroid,
rolloff and high-band share took CH from +0.35 to +0.88 in the float model.

## Where the words came from

Core B does not fit in SPRING REV's 1,063 words with the two body engines, so
the remix gives up DARK REV as well — 2,037 words of ground.

⚠️ **NOT 2,130.** PLATE REV calls a 93-word routine that lives at the top of
DARK's span (`stock.CROSS_ENTRIES`, DARK +0x3ce; A P:0x1a47, B P:0x1807), and
PLATE is kept. Placing the engines over it left PLATE rendering 328
instructions short of stock. `stock.py` had said no effect's span was entered
from outside, citing a reachability sweep that cannot see a span boundary.
`tools/verify/verify_stock_spans.py` re-derives the real map now;
`tools/harness/verify_analog_bd_reverbs.py` holds PLATE to stock and the
given-up ids to the null stub.

## What is not here

Snares and claps. TRX SD needs a second oscillator — body plus noise, summed —
and the claps are burst trains whose 26 ms attack this envelope does not
reproduce. Both are float models scored against captures, not running code.

## What Jesse's MK1 found that no gate here could see (4 Oct 2026)

Three reports, one root cause and one that measurement then exposed.

**"TRX CH on track 2, and when a note was applied it affected the 808 on track
1 in a kind of ring mod way, giving it a low bit rate sound." / "CY and MA both
just rung out a continuous high pitched noise when the trigger was hit. I took
away the trig and it kept ringing until I stopped the Octa."**

One bug: **the engine wrote one word per sample into an interleaved stereo
block.** 16 frames is 32 words and `bd909.asm` writes every sample twice; this
wrote 16. The upper half of every block therefore kept whatever was in
X:$10..$1f -- the previous track's source samples (the 808 on T1, interleaved
with the hat at half rate: ring modulation and a decimated, low-bit sound), or
this track's own previous frame (the loudest 16 words of the attack repeating
at the 2,756 Hz block rate: a continuous high tone that outlives the trig and
stops only when the sequencer does). The envelope was decaying correctly the
whole time.

⚠️ **`tools/harness/bdnoise.py` could not have found it, because it read
`a[::2]`.** The harness assumed the stock block's two-word stride, so half the
samples it measured were stale words from the previous block -- and the result
still looked like a hi-hat with a plausible envelope. Peak, RMS and a −30 dB
point all passed. A measurement that MODELS the output block cannot see the
output block being wrong; this is AGENTS.md's instrument-blindness rule applied
to a stride. The harness now pre-loads every word of the block with a marker
and refuses any word the engine did not write, plus a tail gate and a
four-trig retrigger gate -- the two faults in the form a gate can see.

**"TRX OH and HH sounded the same as CH and are therefore not useful to have as
separate engines."** They were not separate engines. A row's identity was its
three knob DEFAULTS, and `ab_engine_select` writes only the model id -- stored
patches keep their bytes, which is the 808/909 contract -- so on a track that
already existed all five rows ran the same three numbers. The defining numbers
moved into the engine (`BASES`, above); the knobs became offsets around 64. The
harness now runs every machine with identical neutral knobs, which is the only
way a sameness bug is visible.

**And what fixing those exposed:** with the output finally correct, every band
measured at 0.55–0.59 of its target (CH 2,912 Hz against 5,046) and every Q at
double. `f` and `damp` are stored halved because 2·sin(π·fc/SR) reaches 1.82 and
1/Q reaches 1.9, neither of which fits Q23 -- and the engine never restored
them. Its own comment said "the engine's `mac` restores it", which is precisely
the belief AGENTS.md's trap refutes: `mpy`/`mac` align the Q46 product into
Q47, so the high word is the plain product and nothing doubles. Each product is
now doubled with `asl` -- the increment, not the accumulated state. That is why
five machines with five different numbers had all sounded like one ringy hat.

## The trim, and why 16 and not 64

PITCH, DECAY and WIDTH are offsets around 64 from the machine's own base. The
first version used the full ±64, clamped into the table -- which looks generous
and destroys the family. A track carries 127 in a knob the moment anyone turns
it up, and at 127:

| | band | decay | width |
|---|---:|---:|---:|
| TRX CH | 127 | 127 | 127 |
| TRX OH | 127 | 127 | 127 |
| TRX CY | 127 | 127 | 127 |
| EFM HH | 127 | 105 | 69 |
| TRX MA | 127 | 87 | 115 |

Three rows became one machine and all five shared a band. Jesse, 5 Oct 2026,
having already reported the same symptom once: *"All of them work but other
than the 808 and 909 they all do and sound the same."* The first time, the
cause was the stereo write and the knob defaults; this was the half underneath
it, and the ±64 span was mine.

At ±16 every PAIR is separated in at least one parameter at EVERY one of the
128 knob positions -- `dspnoise.separations()` walks them all and the gate
refuses an empty separation, so adding a machine that collides fails the build
rather than the ear:

```
TRX CH vs TRX OH     always differs in decay
TRX CH vs EFM HH     always differs in width
TRX CH vs TRX CY     always differs in decay, width
TRX CH vs TRX MA     always differs in decay
TRX OH vs EFM HH     always differs in decay, width
TRX OH vs TRX CY     always differs in width
TRX OH vs TRX MA     always differs in decay
EFM HH vs TRX CY     always differs in decay, width
EFM HH vs TRX MA     always differs in width
TRX CY vs TRX MA     always differs in band, decay, width
```

16 steps is still a wide trim -- ×1.74 on the band (about nine semitones each
way), ×1.88 on the decay, ×1.48 on the width -- and the gate now also renders
every machine at the stored 127 that broke them, where they measure 203 / 900 /
76 / 1120 / 41 ms and 7235 / 7235 / 6029 / 3402 / 8829 Hz. Five machines.

⚠️ The lesson is not "pick a smaller number". It is that **a parameter range is
part of a machine's identity**, and a gate that only ever runs the neutral
position cannot see a range that lets two machines coincide. Everything above
this section tested at 64/64/64, where the trim is exactly zero.
