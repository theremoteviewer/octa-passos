# The percussion engines — mechanisms, not settings

Five renderers beside the band-passed-noise one, each a different way of making
a sound. `bdperc.asm` holds four (hat, snare, clap, FM) and `bdring.asm` the
modal resonator bank; `dspperc.py` and `dspring.py` are their constants, and
they share `bdnoise.asm`'s LCG, state-variable filter, knob decode and clamp —
and the 909's voice block, overlaid, because a track runs one engine and never
two.

## Six parameters per row

> *"not all of the parameters work. In fact I'd like each of the drums to have
> 6 parameters."* — Jesse, 5 Oct 2026

Each renderer's own fixed constants became knobs 3 and 4, with knob 5 as DRIVE
on every row. Eleven of the fifteen cost **nothing per sample**: they are
decode-time, and the decode runs once per block per track.

| row | 3 | 4 | 5 | per-sample cost |
|---|---|---|---|---:|
| TRX CH/OH | SWEEP (the band glides to) | ATK (bipolar transient) | DRIVE | 29 |
| PL HAT | SPRD (oscillator spacing) | RES (band-pass Q) | DRIVE | 3 |
| PL SNR | RATIO (body 2) | NDEC (the wires) | DRIVE | 3 |
| PL CLP | SPRD (burst gap) | REPS (how many) | DRIVE | 3 |
| PL FM | INDEX | IDEC (its own fall) | DRIVE | 10 |
| PL RNG | BRITE | POS | DRIVE | 3 |

⚠️ **Knobs 3 and 4 are neutral at 64 and DRIVE is unity at 0, and that is a
correctness property.** A row's defaults apply only to a *new* assignment, so a
track that existed before these knobs arrived carries 64, 64 and 0 — the values
`control.c`'s table happens to hold in those slots. Anything else would mean a
build that only *added* parameters detuned every stored Part. So each one is
centred on the constant it replaced: SPRD at 64 is exactly the 808's ratio set,
RATIO at 64 is 1.83 to within five cents, and DRIVE at 0 multiplies by one.

⚠️ **DRIVE costs three instructions, and the clipper is the output store's own
limiter.** The decode folds the knob into GAIN as 1/8…1 and the sample loop
ends with three `asl a`, so the signal is multiplied by 1×…8× and `move
a,x:(r0)+` clamps what runs past full scale. At knob 0 the two are exact
inverses — `mpy` keeps 48 bits before the store truncates — so an untouched
Part renders the same words it did before.

⚠️ **And a named knob is not a working knob.** `tools/harness/bdnoise.py`
renders every named knob at 20 and at 110 with everything else at its stored
default and refuses one whose output does not move, on either side — so a knob
that saturates a third of the way up fails as well as one that is read by
nothing. It immediately caught the FM engine's IDEC moving the output by 0.01
of peak: the shared decode was overwriting the slot it kept its state in, every
block. See AGENTS.md.

## Why they exist

The Machinedrum set was **one renderer** — noise through a band-pass — at
different table indices. Four separate defects were found on hardware and
fixed (`remixes/the-passenger-md/README.md` has the register), and after all
four the set still sounded like one machine, because the parameters were never
the problem:

> *"The different decay times are cool, but I'm looking for each sound to be
> different."* — Jesse, 5 Oct 2026

`tools/harness/bdnoise.py` could prove the five rows differed in band and
decay at **every** knob position, exhaustively, and he could still hear one
machine. **A parameter is not a mechanism.** So a row now names its renderer,
in `dspnoise.BASES`'s engine field, and the separation gate counts a different
renderer as absolute: no knob setting turns six oscillators into a noise burst.

## Credit and provenance

The model set — analog kick, analog snare, analog hi-hat — is the one Mutable
Instruments' **Plaits** offers, which is why Jesse asked for it. Plaits is
MIT-licensed, © Émilie Gillet.

⚠️ **This is not a port of Plaits and is not matched to it.** The Plaits
sources could not be fetched in the session that wrote this: GitHub is
unreachable from that sandbox and the session had no API access to the
repository, and routing around a blocked fetch is not allowed. There is also no
Plaits hardware or emulator in this container to capture reference audio from —
so there was nothing to port from *and* nothing to measure against, and the
second would have been true even with the source in hand.

Every algorithm here is written from published circuit behaviour: the TR-808's
six-oscillator hi-hat, a two-mode snare shell over a bed of wires, a clap's
burst train. What these claim is **structural** — each is a different
mechanism, each lands where its own constants ask, each stops — never "within
x% of a real Plaits". The Machinedrum engines, which do have measured targets
from emulator captures, keep them, and `bdnoise.py`'s target table marks which
numbers are which so the two can never be confused.

## ENG_HAT — six square oscillators

```
6 squares at inharmonic ratios -> resonant band-pass -> VCA
```

The TR-808's hi-hat and cymbal share six square oscillators at 205.3, 304.4,
369.6, 522.7, 540.0 and 800.0 Hz. Summed, they give a dense cluster of mutually
inharmonic partials — and that is the whole reason this engine exists beside
the band-passed noise one: **noise has no partials to be inharmonic.**

PITCH transposes the set (the top oscillator takes the band curve's frequency,
the other five follow as fixed ratios), DECAY is the VCA's fall, **METAL** is
the band-pass centre.

Two things went wrong on the way, both measured:

- **A high-pass, then two.** A hat is the oscillators' harmonics heard above a
  high corner, so a high-pass looked right. One pole left the fundamentals only
  6 dB/octave down and the spectral peak landed on one of them at **947 Hz** —
  a bass note. Two poles put the peak at **16,365 Hz** with the level down
  37 dB: a hard square is not band-limited, so high-passing it does not reveal
  metal, it reveals **aliasing**. The 808 puts its oscillators through a
  band-pass around the bright register, and the family's own SVF does it in ten
  instructions — fewer than the two poles it replaced. Peak now 7.5 kHz.
- **`move a1,y1` is the wrap, and it is not optional.** A phase accumulating in
  a 56-bit accumulator does not wrap at 24 bits, and `move a,x:(...)`
  *saturates* — the oscillator would clamp at full scale and stop oscillating
  within a few hundred samples. Taking a1 through a register discards the
  extension byte, which is modulo 1.0, and a register store does not limit.

The trigger spreads the six phases rather than zeroing them: six oscillators
starting in phase give one click and no cluster.

## ENG_SNARE — two rung bodies over a bed of wires

```
2 high-Q SVFs struck with an impulse -> amp envelope   }
LCG noise -> wide SVF -> its own envelope              }  mixed by SNAP
```

A snare shell has two strong modes about 1.83 apart — roughly 246 and 450 Hz
as shipped, the ratio a 14-inch drum has. Each is a state-variable filter at
very high Q, struck with an impulse and left to ring.

⚠️ **The decay is the envelope's, not the Q's.** A resonator whose damping sets
its decay cannot offer pitch and decay as separate controls — raise the Q to
lengthen the ring and the tone narrows with it. So the Q is fixed and very high
and an amplitude envelope does the decaying.

⚠️ **A snare shell is LOW.** Band 64 puts body 1 at 1,834 Hz and body 2 at
3,356 — measured, and nothing like a snare. The band curve starts at 200 Hz, so
a shell sits near its bottom.

**SNAP** is a real dry/wet: measured peak 345 Hz at 0 (shell alone), 3,488 Hz
at 127 (wires).

## ENG_CLAP — three bursts then a wash

```
LCG noise -> band-pass -> (3 restarted fast envelopes) + a slow tail
```

Three bursts 11.6 ms apart and then a slow tail, which is the ~23 ms attack the
real machines measure — the thing one amplitude envelope could not reproduce,
and why claps were left out of the Machinedrum set.

⚠️ **The boundary is tested once per block, not per sample.** A block is 16
samples, 0.36 ms, against bursts 11.6 ms apart: block granularity is inaudible
and it keeps every branch out of the sample loop. The alternative was two
conditions ANDed per sample — three branches inside a `do` loop for a timing
resolution nothing can hear.

⚠️ **Each burst must FALL before the next.** At a 6 ms burst decay the train
read as one long noise; at 3 ms the measured envelope is 0.35 → 0.16 → **0.46**
→ 0.07 → **0.38** in 2 ms windows. Three claps.

**ROOM** is how much wash. The trigger clears the counter and the boundary too:
leave them and the second hit of a pattern has no bursts at all.

## ENG_FM — two-operator FM

```
modulator -> phase-modulates a carrier, index falling with the envelope
```

A carrier phase-modulated by a second oscillator, with the modulation index
falling as the note decays. The oscillators here are **pitched** and the
inharmonicity comes from the ratio between them — where the hat's comes from
six fixed detunings and the snare's from two resonances. Bright and metallic at
a high ratio, a woodblock at a low one, a synthetic tom when the index falls
fast. PITCH is the carrier, WIDTH is the ratio **and** the index together.

⚠️ **No sine table, and none to spare.** Free private X ends exactly on the
measured free top, so a 256-word sine was never available. A parabola does it
in three instructions: for a phase p in −1..1, `4p(1−|p|)` is a sine to within
about 2% — a fifth of the harmonic error the hat's squares put out on purpose.

⚠️ **The index falls with the envelope.** A fixed index is an FM *tone*, not a
drum: what makes a struck bell a bell is that it is bright for ten milliseconds
and pure afterwards. Measured: 32.6% of energy above 2.5 kHz in the first
93 ms, 9.1% in the next.

⚠️ **And the phase spans [−1, 1), which is two, not one.** A 24-bit two's
complement phase walks 0 → 0x7fffff → 0x800000 → 0xffffff → 0 in one cycle, so
the increment for *f* is 2*f*/SR. With `1/pi` instead of `2/pi` every
oscillator ran an **octave low**: the FM carrier measured 517 Hz against the
996 its own table index names, and the hat's six oscillators sat at 102–398 Hz
instead of 205–800. The hat still sounded like a hat, because its band-pass
picks harmonics and halving the fundamentals only changes which ones land in
the band — the inharmonic *ratios* were right either way, which is exactly why
nothing caught it until an engine arrived whose pitch is the point.

## The body engine's base frequencies — toms and congas for nothing

`dsp808.MACHINE_BASE_HZ` gives a model its own base frequency, and the 808's
voice then runs at base × the PITCH ratio instead of through the stock pitch
table. The path has existed unused since the engine was written. A tom costs
**one already-allocated X word and no P words at all**, which is why one voice
covers kick and tom on every drum machine ever built.

⚠️ **And nothing in this tree measured that path.** MB is written by the glue,
and no harness runs the glue: `verify_analog_bd_exact` drives the engine from
zeroed state, so MB is always 0 and the stock pitch path is always taken — by
construction, which is what keeps the 808 bit-identical. PL TOM and PL CNG
would have shipped verified only by having assembled. `bd808.py`'s
`base_machines()` now builds a four-word stub that writes MB and falls into the
voice, exactly as the glue does, and measures the pitch: 180 Hz → 172,
310 Hz → 301.

## ENG_RING — six tuned resonators struck by a burst

```
LCG noise -> one-pole (BRITE) -> 2 ms envelope
                                    |
   4 x  y[n] = a1*y[n-1] + a2*y[n-2] + x[n]      a1 = 2r*cos(w), a2 = -r^2
                                    |
                     weighted sum (POS) -> guard envelope -> VCA
```

Jesse asked about Rings on 5 Oct 2026. `bdring.asm` carries the credit and the
provenance in full; the short version is that it is a modal resonator bank
written from the published description of one, not a port, and not matched to
anything.

⚠️ **THE FIRST VERSION SOUNDED LIKE A BASS DRUM, AND NOTHING MEASURED IT.**
Jesse, on flashing test 03: *"all the drums are great except for the rings
emulator. It just sounds like a bass drum."* Every gate passed: each partial
landed on its own frequency, decayed for its own length, and the voice stopped.
Three separate causes, none visible in a per-partial measurement:

- **Four partials, spaced geometrically.** A constant ratio between partials is
  the one arrangement a struck object never has. Now six, and STRUCTURE blends
  between the **harmonic series** (a string) and a **free bar's modes** (a
  bell) — two real objects, rather than one stretched.
- **A two-pole resonator's gain is 1/sin(w)**, so with the same excitation and
  the same weight, a 563 Hz fundamental comes out **nine times** louder than a
  5.9 kHz sixth partial. The weight is now multiplied by `sin(theta)` — which
  `zr10` already computes on the way to `cos(w)` — and that cancels it exactly.
  ⚠️ And the weight is applied to the **strike, not the output**: a resonator
  is linear so the two give the same sound, but weighted on the output the low
  partials *ring* at `strike x 1/sin(w)` and their state saturates while the
  output is still a tenth of full scale. Measured: 0.064 peak at a 0.05 strike,
  0.192 at 0.4 — a 2.7x input for a 1.5x output, with no compressor anywhere in
  the path.
- **The exciter's one-pole was too dark.** A one-pole rolls off 6 dB an octave,
  so a 1.8 kHz corner at knob 64 delivered the sixth partial 10 dB down and the
  fundamental won *again*, equalised gains or not. BRITE is now offset 40 index
  steps up the curve: 64 lands near 7 kHz and still reaches 1 kHz at the bottom
  for a dull, wooden strike.

Measured after all three: the spectral peak moved from **560 Hz** (the
fundamental) to **2,239 Hz** (the third or fourth partial), and POS sweeps it
517 Hz → 4,479 Hz. That peak leaving the fundamental is the fix, so it is the
number the harness now holds.

⚠️ **A two-pole direct form, not the family's SVF, and the reason is `cos(w)`.**
A resonator needs its pitch and its decay separate, which an SVF gives only by
holding the Q fixed and enveloping the output — what ENG_SNARE does. Here the
**pole radius** is the decay, which is what lets four partials ring for four
different lengths, and that needs `cos(w)`, which no table in this module
holds. It falls out of the one that does: `N_F` is `sin(pi*fc/SR) = sin(theta)`,
`w` is `2*theta`, and `cos(2*theta) = 1 - 2*sin^2(theta)`. One multiply, one
shift, one subtract; no new table and no X words to find.

⚠️ **And a frequency RATIO is an index OFFSET, because the band curve is
exponential.** `200 * 80^(i/127)` means one step is `80^(1/127)` and a ratio
`r` is `127*ln(r)/ln(80)` steps, so "the third harmonic" is `+32` and costs an
add. Each partial carries two constants — where the harmonic series puts it and
how much further a bar's modes do — and STRUC blends them:
`(struc * RSD) / 128`, computed as a fractional multiply and a right shift, so
the arithmetic is exact and `dspring.offsets()` models it to the step.

| STRUC | the six ratios |
|---|---|
| 0 | 1.00 1.99 3.02 3.98 5.06 6.01 — a string |
| 64 | 1.00 2.29 3.98 5.81 8.21 10.45 |
| 127 | 1.00 2.63 5.24 8.49 12.85 18.14 — a bar |

⚠️ **The ring is four times the curve, by a shift.** `N_DE` was fitted to drum
envelopes and tops out at a 1.2 s −30 dB point. A resonator's decay is its pole
radius, so `r = 1 − de/4` costs one instruction and buys **32 ms to 4.75 s**,
which is the range a bell or a string actually needs. The default is 1.07 s.

⚠️ **The amplitude envelope is a GUARD, not the decay.** The pole radius is the
decay, so an envelope at the DECAY knob's own rate would halve every ring. This
one is the same table word shifted one bit further — exactly twice the longest
partial's own fall — where the first version's fixed 24-step index offset was
2.6x and cut the tail audibly. It is still the thing that guarantees the voice
reaches zero: a 24-bit resonator at `r = 0.9998` can hold a one-LSB limit cycle
indefinitely, and *"I took away the trig and it kept ringing until I stopped
the octa"* is a report this family has already had once, from a different
cause. `bdnoise.py`'s tail gate holds it — **−200 dB after six seconds**, the
window widened for this row rather than the bound weakened, because a −60 dB
threshold is a statement about silence and not about speed.

⚠️ **The strike is 0.25, not full scale.** A two-pole resonator's impulse
response is about `1/sin(w)` times its input and a noise burst keeps exciting
it for every sample it lasts. Measured through the real DSP: 0.25 peaks at 0.73
and still moves with every knob, where 0.3 reads **0.83 at every setting** —
that is the output limiter, not the engine. A peak that stops responding to the
controls is the measurement that says a level is too hot.

## What they cost

| engine | instructions/sample |
|---|---:|
| ENG_CLAP | 72 |
| ENG_SVF (TRX CH/OH) | 81 |
| ENG_FM | 82 |
| ENG_HAT | 117 |
| ENG_SNARE | 124 |
| ENG_RING | 156 |
| (the 808, for scale) | 219 |

All six together are 2,542 P words with the glue and both body engines, inside
a 3,376-word ground — **834 spare**. The ground grew from 2,037 without giving
up a reverb: PLATE's 93-word tail inside DARK's span used to fragment the run,
and the build now relocates it (`tools/build/ab_image.py`'s `RELOC`) so the run
continues through COMPRESSOR, LO-FI, DJ EQ and COMB FILTER as well. No new X
tables: the per-machine table is 16 words in the 909 tables' alignment pad, the
voice state grew inside the 909's own 48-word block (48 of 48 used), and every
curve is one the family already had.

## Gates

`python3 tools/harness/bdnoise.py`, in `make check`. Per machine: it sounds, it
fills the whole interleaved stereo block (every word marker-checked), it lands
on its band, it stops 60 dB down, four trigs do not compound, and **every one
of its six named knobs changes the output at both ends of its travel**. Across
the set: `dspnoise.separations()` walks all 128 knob positions for every pair
and the gate refuses a pair that shares a mechanism *and* every reachable
parameter.

`python3 tools/verify/verify_drum_rows.py` is the cheap half, and it runs
without the DSP: every row's stored id is its own index, every id is unique and
fits four bits, the voice routing agrees between `control.c`, `dsp808` and
`dspnoise`, every row names six distinct knobs of five characters or fewer, and
**the engine field decodes to the engine it was packed as** — modelled through
sign, shift and mask (`dspnoise.engine_of`), because the top three bits of a
24-bit word are signed and `ENG_FM` came back as −4 for two builds.
