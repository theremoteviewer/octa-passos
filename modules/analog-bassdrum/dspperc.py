"""The percussion engines: constants and source for bdperc.asm.

Three renderers that share bdnoise.asm's LCG, state-variable filter, knob
decode and clamp. What each one is, and why it is a separate engine rather
than another set of table indices, is in bdperc.asm's header.

⚠️ CREDIT AND PROVENANCE. The model set -- analog kick, analog snare, analog
hi-hat -- is the one Mutable Instruments' Plaits offers, and Plaits is the
reason Jesse asked for these; it is MIT-licensed, (c) Emilie Gillet. This is
NOT a port of it. The Plaits sources could not be fetched in the session that
wrote this (GitHub is unreachable from that sandbox and the session had no API
access to the repository), and no Plaits hardware or emulator exists in this
container to capture reference audio from, so there was nothing to port from
and nothing to measure against. Every algorithm here is written from published
circuit behaviour: the TR-808's six-oscillator hi-hat, a two-mode snare shell
over a noise bed, a clap's burst train. The claim these make is structural --
each is a different mechanism, each lands where its own numbers say -- never
"within x% of a Plaits".
"""
import math

import dsp909
import dspnoise

RATE = dspnoise.RATE

# ---- ENG_HAT: the six oscillators -----------------------------------------
# The TR-808's hi-hat and cymbal share six square oscillators at these
# frequencies, in Hz. Documented in the service notes and reproduced by every
# clone since; they are deliberately mutually inharmonic, which is what a
# band-pass on noise can never be -- noise has no partials.
HAT_HZ = (205.3, 304.4, 369.6, 522.7, 540.0, 800.0)
# As ratios of the TOP oscillator, so every one is <= 1 and fits a Q23
# multiplier. The top one needs no multiply at all.
HAT_RATIOS = tuple(f / max(HAT_HZ) for f in HAT_HZ[:-1])
# ⚠️ 2/pi, NOT 1/pi: THE PHASE SPANS [-1, 1), WHICH IS TWO, NOT ONE. A 24-bit
# two's-complement phase walks 0 -> 0x7fffff -> 0x800000 -> 0xffffff -> 0 in one
# cycle, so a cycle is a traversal of 2.0 and the increment for f is 2f/SR, not
# f/SR. N_F holds sin(pi*fc/SR) ~= pi*fc/SR, so inc = 2*N_F/pi.
#
# With 1/pi every oscillator ran an OCTAVE LOW: the FM carrier measured 517 Hz
# against the 996 its own constants ask for, and the hat's six oscillators sat
# at 102-398 Hz instead of 205-800. The hat still sounded like a hat, because
# its band-pass picks harmonics and halving the fundamentals only changes which
# ones land in the band -- the inharmonic RATIOS were right either way, which
# is exactly why nothing caught it until an engine arrived whose pitch is the
# point. Found 5 Oct 2026 by comparing the FM engine's measured peak against
# the frequency its table index names.
TWO_OVER_PI = 2.0 / math.pi
# ⚠️ +-1/12, NOT +-1/6. Six squares at a sixth sum to +-1.0 exactly, which
# leaves a resonant band-pass no headroom at all -- its states can exceed the
# input and a Q of 2 does. Half that, and ACCNT puts the level back.
HAT_WEIGHT = 1.0 / 12.0
# A fixed moderate Q for the hat's band-pass: a hi-hat does not want a knob
# that can ring it into a tone. damp = 1/Q, stored halved like N_DAMP.
HAT_Q = 2.0
# ⚠️ HAT_Q IS NOW ONLY THE DOCUMENTED STARTING POINT. RES (knob 4) reads the
# family's own width curve absolutely, so knob 64 lands on Q 3.4 rather than
# this 2.0; the constant stays because it is what the engine was fitted and
# measured at, and HATDAMP is no longer substituted into the source.
# SPRD (knob 3) blends the six ratios toward unison: ratio_eff = 1 - w*(1-r),
# w = knob/64, capped at 1.25. Past w = 1.345 the lowest ratio goes NEGATIVE,
# which is an oscillator running backwards at a frequency the knob no longer
# sets -- a different machine, not a wider one.
HAT_SPREAD_MAX = 1.25


# ---- ENG_SNARE: two shell modes over a bed of wires -----------------------
# A snare shell has two strong modes about 1.83 apart (roughly 180 and 330 Hz
# on a 14-inch drum). Each is a state-variable filter at a very high Q, struck
# with an impulse and left to ring, with an amplitude envelope doing the decay
# -- a resonator whose damping sets its decay cannot offer pitch and decay as
# separate controls, and this engine needs both.
SNARE_RATIO = 1.83
SNARE_Q = 60.0           # essentially "rings forever"; the envelope decides
SNARE_HIT = 0.45         # the impulse that strikes a body
# RATIO (knob 3) around that: ratio/4 = SNARE_BASE + (knob/128)*SNARE_SPAN, so
# knob 64 is 1.83 to within 5 cents and the travel is 1.03 .. 3.62. A QUARTER,
# not a half: `move a,y0` limits at 1.0, so a half-ratio stops moving at 2.0
# and the top two thirds of the knob would be dead.
SNARE_SPAN = 0.4
SNARE_BASE = SNARE_RATIO / 4.0 - 0.5 * SNARE_SPAN
# The wires: wideband noise with a little resonance, and their own slower fall.
SNARE_WIRES_HZ = 2500.0
SNARE_WIRES_Q = 1.0
SNARE_WIRES_MS = 180.0


def _svf_f(hz):
    """The SVF frequency coefficient as the family stores it: halved, because
    2*sin(pi*fc/SR) does not fit Q23 at the top of the range."""
    return 2.0 * math.sin(math.pi * min(hz, RATE * 0.45) / RATE) / 2.0


def _rate(ms):
    """An envelope's per-sample fall, matching dspnoise's own mapping."""
    tau = (max(ms, 0.5) / 1000.0) / (30 / 8.6858896)
    return -math.expm1(-1.0 / (RATE * max(tau, 1e-6)))


# ---- ENG_CLAP: three bursts then a wash -----------------------------------
# A clap is several hands slightly out of time, then the room. Three sharp
# repeats 11.6 ms apart and then a slow tail gives the ~23 ms attack the
# measurements of the real machines showed -- the thing one amplitude envelope
# could not reproduce, which is why claps were left out of the Machinedrum set.
CLAP_GAP = 512           # samples between bursts: 11.6 ms
CLAP_BURSTS = 3
CLAP_BURST_MS = 3.0      # each burst must FALL before the next, or the
                         # train reads as one long noise instead of claps


def q(v):
    """Q23, saturating just short of 1.0 the way dsp909 does."""
    return dsp909.q24(v)


def subs():
    """Every @NAME@ bdperc.asm needs that is not a state slot."""
    out = {
        'RECIPPI': f'${q(TWO_OVER_PI):06x}',
        'WPLUS': f'${q(HAT_WEIGHT):06x}',
        'WMINUS': f'${q(-HAT_WEIGHT) & 0xffffff:06x}',
        'SPRDMAX': f'${q(HAT_SPREAD_MAX / 2.0):06x}',
        'SNRSPAN': f'${q(SNARE_SPAN):06x}',
        'SNRBASE': f'${q(SNARE_BASE):06x}',
        'SNRDAMP': f'${q(1.0 / SNARE_Q / 2.0):06x}',
        'SNRHIT': f'${q(SNARE_HIT):06x}',
        'SNRNF': f'${q(_svf_f(SNARE_WIRES_HZ)):06x}',
        'SNRNDMP': f'${q(1.0 / SNARE_WIRES_Q / 2.0):06x}',
        'SNRDE2': f'${q(_rate(SNARE_WIRES_MS)):06x}',
        # the counter and the boundary are SAMPLE COUNTS, not fractions: they
        # are compared against a counter, so they go in as plain integers
        'CLAPGAP': f'${CLAP_GAP:06x}',
        'CLAPEND': f'${CLAP_GAP * CLAP_BURSTS:06x}',
        'CLAPDE': f'${q(_rate(CLAP_BURST_MS)):06x}',
    }
    # ⚠️ 1 - ratio, NOT the ratio. SPRD computes 1 - w*(1 - ratio), so the
    # constant the engine multiplies is the DISTANCE from unison; at w = 1 it
    # gives the ratio back exactly, which is what makes knob 64 the 808's set.
    for i, r in enumerate(HAT_RATIOS):
        out[f'OMR{i}'] = f'${q(1.0 - r):06x}'
    return out


def source(off, lay=None, shared=None):
    """bdperc.asm with its state slots, table addresses and constants in.

    ⚠️ THE TABLE ADDRESSES ARE NOT OPTIONAL ANY MORE. Until the voicing knobs
    landed, every renderer here read its coefficients from a slot the shared
    decode had already filled, so `off` alone was enough. RES, NDEC and IDEC
    each read a CURVE directly (N_DAMP, N_DE, N_VEL), and those addresses are
    payload-relative -- the build passes the same layout bdnoise.asm gets.
    """
    import re
    from pathlib import Path
    text = (Path(__file__).resolve().parent / 'bdperc.asm').read_text()
    table = {k: f'${v:x}' for k, v in off.items()}
    for k, v in (lay or {}).items():
        table[k] = f'${v:x}'
    if shared and 'B_VEL' in shared:
        table['N_VEL'] = f"${shared['B_VEL']:x}"
    # the LCG constants are the family's, imported rather than copied: if the
    # 909's generator is ever revoiced these follow it (dspnoise's own note)
    table['LCGK'] = f'${dspnoise.LCG_K:06x}'
    table['LCGC'] = f'${dspnoise.LCG_C:06x}'
    table.update(subs())
    missing = sorted({m for m in re.findall(r'@([A-Z0-9_]+)@', text)
                      if m not in table})
    if missing:
        raise KeyError(f'bdperc.asm references {missing} and nothing supplies them')
    return re.sub(r'@([A-Z0-9_]+)@', lambda m: table[m[1]], text)
