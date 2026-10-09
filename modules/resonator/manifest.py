"""RESONATOR -- a bank of eight tuned filters anything can ring through.

Jesse, 5 Oct 2026: "possibly to have the rings algo as an assignable effect so
any sound could ring through its resonator?" This is that: the drum machine's
PL RNG row turned inside out, with the TRACK's audio as the exciter instead of
a noise burst. On an FX1 slot it rings the track and PLATE REV still has FX2.

⚠️ NOT A PORT OF MUTABLE INSTRUMENTS' RINGS, AND NOT MATCHED TO IT. Rings is
MIT-licensed, (c) Emilie Gillet, and is the reason Jesse asked for this; its
sources could not be fetched in the session that wrote this file (GitHub is
unreachable from that sandbox, it has no API access to the repository, and
routing around a blocked fetch is not allowed) and there is no Rings in the
container to capture reference audio from. Every number here is this module's
own, and what it claims is structural.

⚠️ A STATE-VARIABLE FILTER PER PARTIAL, NOT THE TWO-POLE DIRECT FORM THE DRUM
ROW USES, AND THE REASON IS GAIN. A two-pole resonator's impulse gain is
1/sin(w) -- twelve times larger at 563 Hz than at 5.9 kHz -- so a bank of them
fed one signal is a fundamental with faint overtones unless every partial
carries its own compensating weight, which costs a word of state and a
multiply each (modules/analog-bassdrum/bdring.asm says what that cost did to
the drum row's headroom). An SVF's band-pass peak gain is its Q, which is the
SAME at every frequency, so the bank needs no weights at all -- and its decay
time is 2Q/w, so at one Q the high partials ring SHORTER, which is what a
struck object does and what the drum row has to fake with per-partial offsets.
The price is twenty instructions a sample against nine.
"""
import math

from remix.schema import (Gate, Category, Proof, BusRole, Claims, DspSection,
                          Formatter, Harness, Kind, MenuEntry, Module, Param, YBase)

RATE = 44100
PARTIALS = 8

# ---- the two curves, as this module's own P table -------------------------
# ⚠️ ITS OWN, NOT THE DRUM MACHINE'S. modules/analog-bassdrum keeps N_F and
# N_DE in ITS private X region; an insert that read them would be depending on
# another module being in the remix, at an address that module's own layout
# decides. A P table is the facility for this (schema.DspSection.ptable, read
# with `move p:(rn)`), and 128 words is cheap against the ground this remix has.
#
# The frequency curve is the drum machine's, to the entry: 200 Hz * 80^(i/127)
# at even i, as 2*sin(pi*fc/SR)/2 -- so a RATIO is a fixed index OFFSET, which
# is what makes the partial spacing an add instead of a multiply.
_BAND = [200.0 * (16000.0 / 200.0) ** (i / 127) for i in range(128)]


def _q24(v):
    return min(0x7FFFFF, max(-0x800000, round(v * (1 << 23)))) & 0xFFFFFF


F_TABLE = tuple(_q24(2.0 * math.sin(math.pi * min(_BAND[2 * i], RATE * 0.45) / RATE) / 2.0)
                for i in range(64))
# Q from 2 (a tap) to 1200 (a long bell). An SVF's -30 dB time is
# Q*ln(10^1.5)/(pi*f), so Q 1200 is 3.3 s at 500 Hz and 0.4 s at 4 kHz -- the
# spread across the partials IS the sound of a struck object.
Q_MIN, Q_MAX = 2.0, 1200.0
_Q = [Q_MIN * (Q_MAX / Q_MIN) ** (i / 63) for i in range(64)]
D_TABLE = tuple(_q24(min(1.0 / q, 1.9) / 2.0) for q in _Q)

# Where each partial sits, in index steps: the harmonic series at STRUC 0 and
# a free bar's modes at STRUC 127, blended linearly. Same construction as the
# drum row (modules/analog-bassdrum/dspring.py) and for the same reason -- a
# constant ratio between partials is the one spacing a struck object never has.
_BAR = (1.0, 2.756, 5.404, 8.933, 13.344, 18.638, 24.814, 31.872)


def _steps(r):
    return int(round(127 * math.log(r) / math.log(80.0)))


RSH = tuple(_steps(k + 1) for k in range(PARTIALS))
RSD = tuple(_steps(_BAR[k]) - RSH[k] for k in range(PARTIALS))
# interleaved, in the order the decode's `do` loop reads them with p:(r2)+
PARTIAL_TABLE = tuple(v for k in range(PARTIALS)
                      for v in (RSH[k], _q24(RSD[k] / 128.0)))

_BLANK = Param(b"", 0)

MODULE = Module(
    name="resonator", key="RESONATOR", kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="repeat98", author_url="https://github.com/repeat98",
    proof=Proof.RENDER,
    proof_note="unflashed; `make verify-resonator`. No Rings reference exists in the "
               "container, so every claim is structural",
    doc="Eight tuned filters the track's own audio rings through: a modal "
        "resonator on an FX slot, assignable to FX1 or FX2.",
    menu=MenuEntry(fx2_id=0x18, replaces="COMPRESSOR", donor_desc=0x400d5a4a,
                   abbr=b"RESO", fullname=b"Resonator", build_tag=False),
    # ⚠️ COMPRESSOR IS THE DONOR BECAUSE ALL SIX OF ITS PAGE-1 SLOTS ARE PLAIN
    # 0..127. A cloned descriptor inherits every field the clone does not
    # write, and some of them outrank the ones it does (AGENTS.md): COMB
    # FILTER's slot 0 has count 108 and a note-name renderer, which would draw
    # a PITCH knob as something else entirely while every field this file sets
    # was correct.
    params=(
        Param(b"PITCH", 48, active=True, formatter=Formatter.PLAIN,
              doc="the fundamental, 200 Hz to 16 kHz over the knob"),
        Param(b"STRUC", 0, active=True, formatter=Formatter.PLAIN,
              doc="partial spacing: 0 the harmonic series, 127 a free bar's modes"),
        Param(b"DECAY", 80, active=True, formatter=Formatter.PLAIN,
              doc="Q, 2 to 1200; the high partials ring shorter at any setting"),
        Param(b"BRITE", 96, active=True, formatter=Formatter.PLAIN,
              doc="the exciter's one-pole corner: how much of the input reaches "
                  "the high partials"),
        Param(b"TILT", 64, active=True, formatter=Formatter.BIPOLAR,
              doc="per-partial Q, drawn -64..+63: below 64 the high partials die "
                  "sooner, above it they ring on. 64 is the physical case"),
        Param(b"MIX", 48, active=True, formatter=Formatter.PLAIN,
              doc="dry/wet; 0 dry, 127 wet"),
        *(_BLANK for _ in range(6)),
    ),
    dsp=DspSection(
        asm="modules/resonator/resonator.asm",
        ptable=F_TABLE + D_TABLE + PARTIAL_TABLE,
        priority=16,                  # after every existing module
        bus_role=BusRole.NONE,        # an insert: no bus role, no registration
        ybase=YBase.NEVER,            # owns no buffers: all state is in r7
        r7_latch_slot=None,
        gate_label=None,
    ),
    # ⚠️ NO `fx1_only` AND NO BUFFER, WHICH IS WHY IT MAY TAKE AN FX1 ROW AT
    # ALL. state.fx1_hazard() refuses three classes: a module that reads the
    # host's allocator (an FX1 slot is 3,072 words against FX2's 16,384), a
    # module with fixed buffers in the FX2 region, and a bus server. Eight
    # two-pole filters are 32 words of the per-instance r7 block, which is the
    # same size in both slots -- so this one instance of code runs identically
    # wherever it is selected, and Jesse can put it on FX1 with PLATE on FX2.
    claims=Claims(),
    harness=Harness(layout_char="8", is_server=False),
    gates=(Gate('tools/verify/verify_resonator.py', stage='image'),),
    dear={'DECAY': 120, 'MIX': 127, 'BRITE': 127},
)
