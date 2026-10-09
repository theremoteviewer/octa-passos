"""ENG_RING: constants and source for bdring.asm -- a modal resonator bank.

Six tuned two-pole resonators struck by a short noise burst. What it is and
why it is a separate mechanism rather than another set of coefficients is in
bdring.asm's header, along with the credit: Jesse asked for "the rings algo"
and linked pichenettes/eurorack. Mutable Instruments' Rings is MIT-licensed,
(c) Emilie Gillet, and this is NOT a port of it -- the sources could not be
fetched in the session that wrote it and there is no Rings in this container to
measure against, so every number here is this engine's own.

⚠️ THE FIRST VERSION SOUNDED LIKE A BASS DRUM, and Jesse said so on the flash
(5 Oct 2026). Three reasons, all of them here rather than in the assembly:

  * FOUR partials, spaced GEOMETRICALLY. A constant ratio between partials is
    the one arrangement a struck object never has, and four of them at 1 :
    2.17 : 4.7 : 10.2 is not a bank, it is a fundamental with three sparse
    overtones -- i.e. a tom. Now six, and the ratios come from a blend between
    the HARMONIC series (a string) and a free bar's modes (a bell), so
    STRUCTURE sweeps between two real objects instead of stretching one.
  * The decay was the DECAY curve's own, which tops out at 1.2 s because it
    was fitted to drum envelopes. A ring is the pole radius, not an envelope,
    so it costs nothing to make it four times longer: 32 ms to 4.75 s.
  * The guard envelope was 24 index steps slower than the longest partial,
    which is only 2.6x -- audible as a cut. It is now derived from the same
    number the partials use, two shifts further down.
"""
import math

import dsp909
import dspnoise

RATE = dspnoise.RATE

# ---- how the partials are spaced ------------------------------------------
# A frequency RATIO is a fixed offset along the band curve, which is
# exponential: 200 Hz * 80^(i/127), so one index step is 80^(1/127) and a
# ratio r is 127*ln(r)/ln(80) steps. That is the whole reason this engine
# needs no new table -- "the third harmonic" is "+32".
PARTIALS = 6


def _steps(ratio):
    return int(round(127 * math.log(ratio) / math.log(80.0)))


# STRUC 0: the harmonic series -- a plucked string, a tube, anything with a
# pitch you can name.
HARMONIC = tuple(float(k) for k in range(1, PARTIALS + 1))
# STRUC 127: the modes of a free bar, which are what a bell or a marimba has.
# Each gap is WIDER than the last, which is exactly what the geometric stack
# the first version used could not do.
BAR = (1.0, 2.756, 5.404, 8.933, 13.344, 18.638)
RSH = tuple(_steps(r) for r in HARMONIC)        # 0, 20, 32, 40, 47, 52
RSD = tuple(_steps(b) - _steps(h) for b, h in zip(BAR, HARMONIC))

# A higher partial of a struck object dies sooner. Five index steps along the
# decay curve is about 1.22x shorter per partial.
RSC = (0, 5, 9, 12, 15, 17)

# ⚠️ THE RING IS FOUR TIMES THE CURVE, BY A SHIFT. N_DE was fitted to drum
# envelopes and tops out at a 1.2 s -30 dB point; a resonator's decay is its
# pole radius, so r = 1 - de/4 costs one instruction and buys 32 ms .. 4.75 s,
# which is the range a bell or a string actually needs.
DECAY_SHIFT = 2
# And the guard envelope is the same number two shifts further down -- twice
# the longest partial's own fall, where the first version's fixed 24-step
# offset was 2.6x and cut the tail audibly. See bdring.asm.
GUARD_SHIFT = DECAY_SHIFT + 1

# POS (knob 4) tilts the weights from the low partials to the high ones. They
# sum to 0.69 at either end, which keeps the bank inside full scale without a
# divide; the six resonators rarely peak together, and the state store limits
# if they do.
RGL = (0.22, 0.16, 0.12, 0.09, 0.06, 0.04)
RGH = tuple(reversed(RGL))

# ---- the exciter ----------------------------------------------------------
RX_MS = 2.0              # how long the strike lasts
# ⚠️ BRITE IS OFFSET UP THE CURVE SO THAT 64 IS BRIGHT. A one-pole rolls off
# 6 dB an octave; read straight, knob 64 is a 1.8 kHz corner and the sixth
# partial arrives 10 dB down, which puts the fundamental back on top however
# well the resonator gains are equalised. 40 steps up is a ~7 kHz corner at 64,
# and the knob still reaches 1 kHz at the bottom for a dull, wooden strike.
BRITE_OFFSET = 40
# ⚠️ NOT FULL SCALE. A two-pole resonator's impulse response is about 1/sin(w)
# times its input -- 13x at the 563 Hz this machine's base asks for -- and a
# noise burst keeps exciting it for every sample it lasts, so a full-scale
# strike clips the bank on its own attack. Measured through the real DSP by
# tools/harness/bdnoise.py: 0.25 peaks at 0.73 and still moves with every
# knob, where 0.3 reads 0.83 at EVERY setting -- the output limiter, not the
# engine. A peak that stops responding to the controls is the measurement
# that says a level is too hot.
RX_HIT = 0.25


def _glide(ms):
    return -math.expm1(-1.0 / (RATE * (ms / 1000.0)))


def q(v):
    return dsp909.q24(v)


def subs():
    """Every @NAME@ bdring.asm needs that is not a state slot or a table."""
    out = {
        'RXDE': f'${q(_glide(RX_MS)):06x}',
        'RXHIT': f'${q(RX_HIT):06x}',
        'DECSH': f'${DECAY_SHIFT:x}',
        'BRTOFF': f'${BRITE_OFFSET:06x}',
        'GRDSH': f'${GUARD_SHIFT:x}',
        'LCGK': f'${dspnoise.LCG_K:06x}',
        'LCGC': f'${dspnoise.LCG_C:06x}',
    }
    for i in range(PARTIALS):
        out[f'RSH{i}'] = f'${RSH[i]:06x}'
        # the blend weight as knob/128 does: the engine multiplies struc/128
        # by this and shifts right 16, which is (struc * RSD) / 128 exactly
        out[f'RSD{i}'] = f'${q(RSD[i] / 128.0):06x}'
        out[f'RSC{i}'] = f'${RSC[i]:06x}'
        out[f'RGL{i}'] = f'${q(RGL[i]):06x}'
        out[f'RDG{i}'] = f'${q(RGH[i] - RGL[i]) & 0xffffff:06x}'
    return out


def offsets(struc=64):
    """The six index offsets a STRUC knob position asks for, modelled exactly
    as the engine computes them: floor((struc * RSD) / 128) + RSH."""
    return tuple(RSH[k] + (struc * RSD[k]) // 128 for k in range(PARTIALS))


def ratios(struc=64):
    """Those offsets as frequency ratios -- for the docs and the harness."""
    return tuple(80.0 ** (o / 127.0) for o in offsets(struc))


def decay_ms(index):
    """The -30 dB time of a partial whose decay index is `index`, with the
    shift applied. Models the engine, not the table."""
    de = dsp909.q24(dspnoise.tables()['N_DE'][max(0, min(127, index)) >> 1])
    r = (q(0.99999988) - (de >> DECAY_SHIFT)) / 8388608.0
    return -3.4536 / math.log(r) / RATE * 1000.0


def source(off, lay=None, shared=None):
    """bdring.asm with its state slots, table addresses and constants in."""
    import re
    from pathlib import Path
    text = (Path(__file__).resolve().parent / 'bdring.asm').read_text()
    table = {k: f'${v:x}' for k, v in off.items()}
    for k, v in (lay or {}).items():
        table[k] = f'${v:x}'
    if shared and 'B_VEL' in shared:
        table['N_VEL'] = f"${shared['B_VEL']:x}"
    table.update(subs())
    missing = sorted({m for m in re.findall(r'@([A-Z0-9_]+)@', text)
                      if m not in table})
    if missing:
        raise KeyError(f'bdring.asm references {missing} and nothing supplies them')
    return re.sub(r'@([A-Z0-9_]+)@', lambda m: table[m[1]], text)
