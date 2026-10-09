"""Core B coefficient tables: the noise/metallic voice (hats, cymbals, maracas).

The structure and every number here come from measuring the real machines in an
emulator and fitting the band and Q to their spectral descriptors, not from a
circuit model -- out/md-machines/NOTES.md sections 11.3 and 15. The float
reference this is generated against is tools/trxnoise.py.

A machine on this voice is a pair of knob defaults (band, decay) plus a width;
no new DSP code per machine, which is the whole point of the family split.
"""
import math
import re
from pathlib import Path

import dsp909

HERE = Path(__file__).resolve().parent
RATE = 44100

# Voice state. Its own block, so the slots are free -- unlike the 808's, whose
# embedded 909 desk block fills every word (3 Oct 2026, the hard way).
# ⚠️ THESE SLOTS OVERLAP THE 909'S, DELIBERATELY. Core B has no voice block of
# its own: a track runs one engine or the other, never both, so it borrows the
# 909's -- which is also the only way it gets the knob block at +0x30 that every
# voice needs. The consequence is that BAND, LOW and ENV hold whatever the 909
# left behind, so the trigger zeroes them before the first sample. That is the
# "a persistent slot init does not clear" trap, met head-on.
# ⚠️ ONE POOL, ALIASED PER ENGINE. Slots 0..9 are the shared decode's (every
# renderer reads F, DE, DAMP, GAIN and SEG); 10..23 are a pool each renderer
# names for itself, because a track runs ONE engine and never two. Overlaying
# costs nothing and buying 14 more words per voice was not on offer: these
# blocks are the 909's, 64 words with 48 of state and 13 of knobs.
#
# ⚠️ AND EVERY RENDERER'S TRIGGER MUST ZERO WHAT IT READS. What is in these
# words is whatever the 909, or another percussion engine, left there -- six
# stale oscillator phases or a filter mid-swing. That is AGENTS.md's "a
# persistent slot init does not clear", and the only reason sharing is safe.
OFF = dict(
    # ---- the shared decode's own words, 0..12 -----------------------------
    # ⚠️ HPK, MIX AND BGN BELONG HERE, AND PUTTING THEM IN THE POOL COST A
    # SESSION. They are written by zn01 EVERY BLOCK, for every renderer, so a
    # renderer that names slot 16 for itself has that word overwritten sixteen
    # samples into every note. MIX was 16 and the FM engine's index envelope
    # and the ring engine's second resonator y[n-2] were both 16: the FM's
    # IDEC knob could only act for one block at a time, and the resonator was
    # handed 0.5 four thousand times a second -- which is not a resonator that
    # rings for 400 ms, it is an oscillator that never stops, bounded only by
    # the store's limiter. It measured as a 1-second decay that did not change
    # when the strike was made forty times quieter, which is what gave it away.
    # SHARED below is the list, and the assertion under it is the gate.
    LCG=0, BAND=1, LOW=2, ENV=3, F=4, DAMP=5, DE=6, GAIN=7, SEG=8, ENG=9,
    HPK=10, MIX=11, BGN=12,
    # ---- and a pool each renderer names for itself, from 13 --------------
    # ENG_HAT: six phases, six increments, a spare pole and the spread scratch
    P0=13, P1=14, P2=15, P3=16, P4=17, P5=18,
    I0=19, I1=20, I2=21, I3=22, I4=23, I5=24,
    HPL=25, HPM=26,
    # ENG_SVF: the sweep's target band, the distance to it, the glide's own
    # state, and the transient shaper's envelope and signed depth
    FT=13, ANV=14, ASC=15, FG=16, FD=17,
    # ENG_SNARE: body 1 rings in BAND/LOW, body 2 and the wires get their own
    B2B=13, B2L=14, NB=15, NL=16, F2=17, ENV2=18, NDE2=19,
    # ENG_CLAP: the burst counter, the next burst's boundary, the slow tail,
    # and the gap / count / fired tally the two new knobs set
    CNT=13, NXT=14, TAIL=15, CGAP=16, CREP=17, CBN=18,
    # ENG_FM: two phases, two increments, the index, its amount, its own
    # envelope and that envelope's rate
    FPC=13, FPM=14, FIC=15, FIM=16, FIX=17, FIA=18, FIE=19, FIR=20,
    # ENG_RING: SIX two-pole resonators (y1, y2, both coefficients, a weight)
    # plus the exciter's one-pole state, its corner and its own envelope, and
    # two scratch words the decode needs across all six partials.
    # ⚠️ SIX, AND THE CEILING IS THE VOICE BLOCK, NOT THE CYCLES. Four partials
    # read as a tom (Jesse, 5 Oct 2026: "the rings emulator. It just sounds
    # like a bass drum") and eight would be better still -- 8 x 5 words plus
    # the exciter is 43, and the pool is 35. The insert version of this engine
    # (modules/resonator) has a 132-word instance block and no such limit,
    # which is the right place for a denser bank.
    RY1=13, RY2=14, RA1=15, RA2=16, RG1=17,
    RY3=18, RY4=19, RA3=20, RA4=21, RG2=22,
    RY5=23, RY6=24, RA5=25, RA6=26, RG3=27,
    RY7=28, RY8=29, RA7=30, RA8=31, RG4=32,
    RY9=33, RY10=34, RA9=35, RA10=36, RG5=37,
    RY11=38, RY12=39, RA11=40, RA12=41, RG6=42,
    RXL=43, RXC=44, RXE=45, RS1=46, RS2=47,
)
# Every word zn01 writes before it dispatches -- grep its stores, there are
# nine sites and GAIN is two of them.
SHARED = ('LCG', 'BAND', 'LOW', 'ENV', 'F', 'DAMP', 'DE', 'GAIN', 'SEG',
          'ENG', 'HPK', 'MIX', 'BGN')
_shared_slots = {OFF[k] for k in SHARED}
_clash = sorted(k for k, v in OFF.items() if k not in SHARED and v in _shared_slots)
assert not _clash, (f'{_clash} name a slot the shared decode overwrites every '
                    f'block: {sorted(_shared_slots)}')
SWORDS = max(OFF.values()) + 1
# ⚠️ THE KNOBS START AT +0x30, AND THIS POOL GROWS EVERY TIME A RENDERER GAINS
# A PARAMETER. The 909's block is 64 words: 48 of state and 13 of knobs from
# +0x30, so slot 47 is the last one that is not somebody's knob. Derived rather
# than written down, because the ring engine added 26 slots in one go.
assert SWORDS <= 48, f'{SWORDS} state slots would overrun the knob block at +0x30'

# The 909's LCG constants, imported rather than copied: if its generator is
# ever revoiced this voice follows it instead of keeping a stale pair.
# dsp909 asserts the full-period conditions (c odd, M = 1 mod 4).
LCG_K, LCG_C = dsp909.LCG_K, dsp909.LCG_C


def _f_of(hz):
    """Chamberlin SVF frequency coefficient, 2*sin(pi*fc/SR), halved so the
    fixed-point value stays inside Q23 and the engine's `mac` restores it."""
    return 2.0 * math.sin(math.pi * min(hz, RATE * 0.45) / RATE) / 2.0


def _rate(ms):
    tau = (max(ms, 0.5) / 1000.0) / (30 / 8.6858896)
    return -math.expm1(-1.0 / (RATE * max(tau, 1e-6)))


def tables():
    # PITCH sweeps the band exponentially from 200 Hz to 16 kHz: the measured
    # family spans 746 Hz (EFM CP) to 13.6 kHz (EFM CY), so the knob has to
    # cover better than five octaves.
    band = [200.0 * (16000.0 / 200.0) ** (i / 127) for i in range(128)]
    # DECAY from 8 ms to 1.2 s: measured 21 ms (MA) to 788 ms (CY).
    dec = [8.0 * (1200.0 / 8.0) ** (i / 127) for i in range(128)]
    # TONE is the width: damp = 1/Q, Q from 0.7 (broad) to 16 (metallic).
    q = [0.7 * (16.0 / 0.7) ** (i / 127) for i in range(128)]
    # ⚠️ SIXTY-FOUR ENTRIES, NOT 128, and the decay and velocity curves are the
    # 808's rather than our own. Free private X is 193 words and a full set of
    # four 128-entry tables plus four voice blocks is 576; the knob is shifted
    # right by one in the engine. Band and width at 64 steps is musically fine,
    # and the 808's decay table already spans 57 ms to 1.17 s against a measured
    # family range of 21 to 788 ms, so a second copy would buy nothing.
    # ⚠️ ITS OWN DECAY TABLE AFTER ALL. Sharing the 808's looked like a free
    # 64 words until the mapping was done against the right curve: that table
    # bottoms out at a 57 ms -30 dB point, and a maraca is 21 ms and a closed
    # hat 43. Both pinned to knob 0. 8 ms to 1.2 s covers the measured family.
    return dict(
        N_F=[_f_of(band[2 * i]) for i in range(64)],
        N_DAMP=[min(1.0 / q[2 * i], 1.9) / 2.0 for i in range(64)],
        N_DE=[_rate(dec[2 * i]) for i in range(64)],
    )


# ---- what each machine IS -------------------------------------------------
# {model id: (band, decay, width)} as 0..127 knob positions. ⚠️ THIS, NOT THE
# KNOB DEFAULTS, IS WHAT MAKES A ROW A MACHINE. Selecting a row writes only the
# model id -- the Part keeps its stored knobs, which is the 808/909 contract --
# so a machine whose identity lived in its defaults was the same machine as
# every other one on any track that already existed. The engine reads this
# table and treats each knob as an offset around 64.
#
# Fitted to the measured band, -30 dB point and Q of each machine
# (out/md-machines/NOTES.md section 15), and re-measured through the real DSP
# by tools/harness/bdnoise.py after the coefficient scale was corrected.
# ⚠️ AND THE ENGINE FIELD IS WHAT MAKES IT A DIFFERENT SOUND. Rows 2.. used to
# be ONE renderer at different table indices, which is why "the different decay
# times are cool, but I'm looking for each sound to be different" (Jesse, 5 Oct
# 2026) was a fair complaint about a set that passed every distinctness gate I
# had: those gates proved the PARAMETERS differ, and a parameter is not a
# mechanism. A row now names its renderer.
ENG_SVF = 0        # band-passed noise -- the Machinedrum TRX/EFM hats
ENG_HAT = 1        # six square oscillators -> high-pass -> VCA (metallic)
ENG_SNARE = 2      # two rung resonator bodies + band-passed noise
ENG_CLAP = 3       # a burst train of noise into a longer tail
ENG_FM = 4         # two-operator FM with a falling index: bells, zaps, toms
ENG_RING = 5       # four tuned two-pole resonators struck by a noise burst
ENGINES = 6
ENGINE_NAME = {ENG_SVF: 'svf noise', ENG_HAT: 'six-oscillator metal',
               ENG_SNARE: 'bodies + wires', ENG_CLAP: 'burst train',
               ENG_FM: 'two-operator FM', ENG_RING: 'modal resonator bank'}

# ⚠️ THE KEY IS THE BROWSER ROW, AND IT HAS TO BE. `ab_engine_select` is called
# with the row index and stores THAT as the model id -- so a model id that is
# not its own row number plays a different machine. Giving TRX OH id 8 and PL
# FM id 9 (test 02) made six of ten rows play the row below: Jesse heard "pl
# hat is snare, snare is clap, clap is tom, tom is like noise shot", which is
# that shift exactly, six for six. `tools/verify/verify_drum_rows.py` now
# refuses any row whose stored id is not its index.
BASES = {
    # The two Machinedrum hats, the only engines in this file with MEASURED
    # targets: band and -30 dB point from emulator captures of the real
    # machine (out/md-machines/NOTES.md section 15).
    2: (ENG_SVF, 94, 68, 80),      # 003 TRX CH   5.0 kHz  114 ms  Q 5
    3: (ENG_SVF, 94, 106, 80),     # 004 TRX OH   5.0 kHz  536 ms  Q 5
    4: (ENG_HAT, 40, 40, 100),     # 005 PL HAT   six oscillators ~205-800 Hz
    # ⚠️ A SNARE SHELL IS LOW. Band 64 puts body 1 at 1,834 Hz and body 2 at
    # 3,356 -- measured, and nothing like a snare. The curve starts at 200 Hz,
    # so a shell sits near its bottom: 6 gives 246 Hz and 450 Hz.
    5: (ENG_SNARE, 6, 70, 64),     # 006 PL SNR   246/450 Hz shell + wires
    6: (ENG_CLAP, 56, 64, 40),     # 007 PL CLP   1.3 kHz bursts + a little wash
    7: (ENG_FM, 48, 56, 80),       # 008 PL FM    carrier ~1 kHz, ratio on WIDTH
    # ⚠️ ROW 10, NOT 8 OR 9: those are the two body rows (PL TOM, PL CNG) and
    # a body model never reaches this table. The id IS the browser row, always.
    10: (ENG_RING, 30, 100, 64),   # 011 PL RNG   ~530 Hz fundamental, 390 ms
}
NBASE = 16               # the engine masks the model to four bits
# ⚠️ THE KNOB IS A TRIM, NOT A SWEEP, AND THE SPAN IS A CORRECTNESS PROPERTY.
# The first version made each knob a +-64 offset around the machine's base and
# clamped the sum to the table. That looks generous and it destroys the family:
# with a Part holding 127 -- which is what a track carries after anyone turns a
# knob up -- CH, OH and CY all clamp to (127, 127, 127) and become ONE machine,
# and all five share a band. Jesse, 5 Oct 2026: "All of them work but other
# than the 808 and 909 they all do and sound the same." He had already told me
# the same thing about test 03 and I had fixed the wrong half of it.
#
# At +-16 index steps every PAIR of machines is separated in at least one
# parameter at EVERY knob position -- exhaustively, not by argument; see
# separations() and the gate that calls it. That is still a wide trim: 16 steps
# is x1.74 on the band (about nine semitones each way), x1.88 on the decay and
# x1.48 on the width.
TRIM = 16


# ---- the three knobs that are NOT part of a machine's identity -------------
# ⚠️ KNOBS 3, 4 AND 5 ARE ABSOLUTE, NOT TRIMS AROUND A BASE, and that is safe
# for exactly one reason: separations() proves every PAIR of rows is separated
# by band, decay, width or renderer alone, so no setting of a voicing knob can
# collapse two rows into one. The identity trap ("a machine whose identity is
# its knob defaults is not a machine on an existing track") bites a knob that
# DEFINES the machine; these three only voice it, and the packed word has no
# room for three more fields anyway -- 3 engine + 3x7 parameter bits is 24.
#
# ⚠️ AND EVERY ONE OF THEM IS NEUTRAL AT ITS STORED DEFAULT. A row's defaults
# apply only to a NEW assignment, so a track that existed before this build
# arrives carrying 64, 64 and 0 in these three slots (control.c's table) --
# whatever the engine now reads there has to be the machine as measured, or
# every existing Part is detuned by a build that only ADDED parameters. So
# knob 3 and knob 4 are centred: 64 is the fixed constant each one replaced.
# Knob 5 is DRIVE on every renderer and 0 is unity gain.
DRIVE_MIN = 1.0 / 8.0            # knob 5 at 0: exactly today's level
DRIVE_MAX = 1.0                  # knob 5 at 127: 8x into the store's limiter
SWEEP_MS = 15.0                  # ENG_SVF: how fast the band reaches SWEEP
SWEEP_SPAN = 32                  # +-32 index steps, about +-1.6 octaves
ATK_MS = 8.0                     # ENG_SVF: the transient shaper's own fall


def _glide(ms):
    """A plain one-pole rate for a time constant in ms -- not _rate()'s -30 dB
    mapping, because these are glides and not decays."""
    return -math.expm1(-1.0 / (RATE * (ms / 1000.0)))


def voicing_subs():
    """The constants bdnoise.asm needs for knobs 3, 4 and 5."""
    return {
        'DRV1': f'${dsp909.q24(DRIVE_MIN):06x}',
        'DRV7': f'${dsp909.q24(DRIVE_MAX - DRIVE_MIN):06x}',
        'SWRATE': f'${dsp909.q24(_glide(SWEEP_MS)):06x}',
        'ATKDE': f'${dsp909.q24(_glide(ATK_MS)):06x}',
    }


def index(base, knob):
    """The table index a machine's parameter lands on, for a stored knob.

    Must match bdnoise.asm exactly: subtract 64, arithmetic-shift right two
    (which floors, as Python's // does), add the base, clamp, and halve for
    the 64-entry curves.
    """
    return max(0, min(127, base + ((knob - 64) * TRIM) // 64)) >> 1


def separations(trim=None):
    """{(machine a, machine b): (parameters that can never coincide, ...)}.

    A pair with an empty tuple can be made into the same machine by some knob
    setting, which means they are not two machines.
    """
    global TRIM
    keep, TRIM = TRIM, trim if trim is not None else TRIM
    try:
        names = sorted(BASES)
        out = {}
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                sep = []
                if BASES[a][0] != BASES[b][0]:
                    # A different renderer is not a different parameter: no
                    # knob setting can turn one mechanism into another.
                    sep.append('ENGINE')
                for pos, pname in enumerate(('band', 'decay', 'width'), start=1):
                    ra = {index(BASES[a][pos], k) for k in range(128)}
                    rb = {index(BASES[b][pos], k) for k in range(128)}
                    if not ra & rb:
                        sep.append(pname)
                out[(a, b)] = tuple(sep)
        return out
    finally:
        TRIM = keep


def base_words():
    """The packed per-model table: engine<<21 | band<<14 | decay<<7 | width.

    Sixteen words, because the engine masks the model to four bits -- safe only
    for models that REACH this table, and a body model never does
    (dsp808.M_ENGINE sends it elsewhere). One word per machine because free
    private X is exactly full: the three 64-entry curves end on the measured
    free top, so this table lives in the 909 tables' alignment pad.
    """
    out = []
    for m in range(NBASE):
        e, b, d, w = BASES.get(m, (ENG_SVF, 64, 64, 64))
        assert 0 <= e < ENGINES, (m, e)
        for v in (b, d, w):
            assert 0 <= v <= 127, (m, v)
        out.append((e << 21) | (b << 14) | (d << 7) | w)
    return out


def engine_of(word):
    """The engine field as bdnoise.asm actually extracts it.

    ⚠️ THIS EXISTS BECAUSE THE OBVIOUS `word >> 21` WAS WRONG ON THE DSP AND
    RIGHT HERE. The field is bits 21..23 of a TWENTY-FOUR bit word, so every
    engine from 4 up sets the sign bit: the load sign-extends into A2, `asr`
    preserves it, and ENG_FM came back as -4. The engine masks to three bits
    now, and this models the whole sequence -- sign, shift, mask -- so a model
    whose engine the hardware would misread fails in Python.
    """
    signed = word - (1 << 24) if word & 0x800000 else word
    return (signed >> 21) & 0x7


def engine_check():
    """[(model, intended engine, what the engine would read)] for every row
    the DSP and this file disagree about. Empty is the only passing answer."""
    words = base_words()
    bad = []
    for m, (e, _b, _d, _w) in sorted(BASES.items()):
        got = engine_of(words[m])
        if got != e:
            bad.append((m, e, got))
    return bad


assert not engine_check(), engine_check()
assert ENGINES <= 8, 'the engine field is three bits'


def layout(base):
    return {k: base + 64 * i for i, k in enumerate(tables())}


def knob_for_band(hz):
    """The PITCH knob whose band is nearest `hz` -- how a measured machine
    becomes a default. Returns a 0..127 knob; the engine halves it."""
    t = [200.0 * (16000.0 / 200.0) ** (i / 127) for i in range(128)]
    return 2 * min(range(64), key=lambda i: abs(math.log2(t[2 * i] / hz)))


def knob_for_decay(ms):
    """Against core B's OWN curve -- the engine reads that one.

    An earlier version mapped against a table the engine did not use and every
    envelope came out wrong with nothing pointing at the mismatch.
    """
    t = [8.0 * (1200.0 / 8.0) ** (i / 127) for i in range(128)]
    return 2 * min(range(64), key=lambda i: abs(math.log2(t[2 * i] / max(ms, 1e-3))))


def knob_for_q(q):
    t = [0.7 * (16.0 / 0.7) ** (i / 127) for i in range(128)]
    return 2 * min(range(64), key=lambda i: abs(math.log2(t[2 * i] / q)))


def data_lines(lay, nzbase=None):
    out = ''.join('X %x ' % lay[k] + ' '.join('%06x' % dsp909.q24(v) for v in vs) + '\n'
                  for k, vs in tables().items())
    if nzbase is not None:
        out += 'X %x ' % nzbase + ' '.join('%06x' % w for w in base_words()) + '\n'
    return out


def source(lay, shared, nzbase=0):
    text = (HERE / 'bdnoise.asm').read_text()
    subs = {k: f'${v:x}' for k, v in {**OFF, **lay}.items()}
    subs['LCGK'] = f'${LCG_K:06x}'
    subs['LCGC'] = f'${LCG_C:06x}'
    subs['NZBASE'] = f'${nzbase:x}'
    subs.update(voicing_subs())
    # velocity is the 808's by address (i/127 is i/127); decay is our own
    subs['N_VEL'] = f"${shared['B_VEL']:x}" if 'B_VEL' in shared else '$0'
    return re.sub(r'@([A-Z0-9_]+)@', lambda m: subs[m[1]], text)
