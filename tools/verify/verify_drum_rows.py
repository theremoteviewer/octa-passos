#!/usr/bin/env python3
"""Every browser row plays the engine it is named after.

⚠️ WHY THIS EXISTS. `ab_engine_select` is called with the browser ROW INDEX and
stores that as the model id -- the thunk table is `handlers[row]` and the row is
the only thing the stock list controller knows. So a row whose stored id is not
its own index plays a DIFFERENT MACHINE, silently, and nothing downstream can
tell: the DSP faithfully runs the engine the id names.

Rows and ids coincided until TRX OH was given id 8 and PL FM id 9 to keep the
Machinedrum hats together in the table (test 02, 5 Oct 2026). Six of ten rows
then played the row below, and Jesse's report was that shift, six for six:

    005 PL HAT -> id 4 -> the snare      "pl hat is snare"
    006 PL SNR -> id 5 -> the clap       "snare is clap"
    007 PL CLP -> id 6 -> a body at 180  "clap is tom"
    008 PL FM  -> id 7 -> a body at 310  "FM i'm not sure"
    009 PL TOM -> id 8 -> band-passed noise  "tom is like noise shot"
    010 PL CNG -> id 9 -> the FM engine  "cong is cool"

What is checked, from the sources rather than from a list written here:

  1. every row's defaults[6] equals its own index -- the invariant the
     select/open pair depends on
  2. every id appears exactly once
  3. the voice field in control.c agrees with dsp808.MACHINE_ENGINE: voice 2
     means the noise family and the id must be in dspnoise.BASES; voice 0 or 1
     means a body and the id must NOT be
  4. a body row with its own base frequency has a dsp808.MACHINE_BASE_HZ entry,
     and every MACHINE_BASE_HZ entry belongs to a body row
  5. the id fits the four bits the engine masks it to

    python3 tools/verify/verify_drum_rows.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "modules/analog-bassdrum"))
import dsp808  # noqa: E402
import dspnoise  # noqa: E402

CONTROL = ROOT / "modules/analog-bassdrum/control.c"
ROW = re.compile(r'\{"(\d\d\d [^"]+)",\s*\{([^}]*)\},\s*(\d+),\s*\{([^}]*)\}\}')


def rows():
    """[(label, voice, defaults)] in browser order, parsed from control.c."""
    text = CONTROL.read_text()
    out = []
    for label, names, voice, defaults in ROW.findall(text):
        vals = [int(v.strip()) for v in defaults.split(",")]
        knobs = [n.strip().strip('"') for n in names.split('","')]
        out.append((label, int(voice), vals, knobs))
    want = int(re.search(r"^#define AB_MODELS (\d+)", text, re.M)[1])
    if len(out) != want:
        sys.exit(f"control.c declares AB_MODELS {want} but its table has {len(out)} rows")
    return out


def main():
    table = rows()
    bad = []
    seen = {}
    for i, (label, voice, defaults, knobs) in enumerate(table):
        mid = defaults[6]
        note = []
        if mid != i:
            note.append(f"stored id {mid} is not its row index {i} -- it would "
                        f"play row {mid}'s engine")
        if mid in seen:
            note.append(f"id {mid} is also {seen[mid]}'s")
        seen[mid] = label
        if mid > 0xF:
            note.append(f"id {mid} does not fit the four bits the engine masks to")
        family = dsp808.MACHINE_ENGINE.get(mid)
        if voice == 2:
            if family != 2:
                note.append("control.c routes it to the noise family and "
                            "dsp808.MACHINE_ENGINE does not")
            if mid not in dspnoise.BASES:
                note.append("no dspnoise.BASES row, so it has no renderer or numbers")
        else:
            if family == 2:
                note.append("control.c routes it to a body and "
                            "dsp808.MACHINE_ENGINE sends it to the noise family")
            if mid in dspnoise.BASES:
                note.append("it is a body row and also has a dspnoise.BASES row")
        eng = (dspnoise.ENGINE_NAME[dspnoise.BASES[mid][0]] if mid in dspnoise.BASES
               else f"body, base {dsp808.MACHINE_BASE_HZ.get(mid, 0.0):.0f} Hz")
        named = [k for k in knobs[:6] if k and not k.startswith("-")]
        # ⚠️ SIX, AND NOT BECAUSE SIX IS TIDY. Jesse, 5 Oct 2026: "not all of
        # the parameters work. In fact I'd like each of the drums to have 6
        # parameters." Six rows named three and drew "--" for the rest. This
        # refuses the count; `tools/harness/bdnoise.py` refuses a knob that is
        # named and does nothing, which is the half of it a name cannot show.
        if len(named) != 6:
            note.append(f"names {len(named)} of its six knobs: "
                        f"{', '.join(knobs[:6])}")
        if len(set(named)) != len(named):
            note.append(f"two knobs share a name: {', '.join(named)}")
        for k in named:
            if len(k) > 5:
                note.append(f"knob name {k!r} is {len(k)} characters and the "
                            f"descriptor field holds five plus a terminator")
        print(f"  row {i} id {mid:2d}  {label:<12} {eng:<26} "
              f"{len(named)} named knobs"
              + ("   FAIL: " + "; ".join(note) if note else ""))
        if note:
            bad.append((label, note))
    # ⚠️ AND THE ENGINE FIELD AS THE DSP READS IT, NOT AS PYTHON WOULD. It is
    # the top three bits of a 24-bit word, so engine 4 and up set the sign bit;
    # before the engine masked them, ENG_FM decoded as -4 and the dispatch
    # chain's unconditional last arm swallowed it -- correctly, by accident,
    # until a sixth engine moved that arm and PL FM began rendering a
    # resonator bank. dspnoise.engine_of models sign, shift and mask together.
    for mid, want, got in dspnoise.engine_check():
        bad.append((f"model {mid}", [f"dspnoise.BASES says engine {want} and "
                                     f"the packed word decodes to {got}"]))
    for mid in sorted(dsp808.MACHINE_BASE_HZ):
        if mid not in seen:
            bad.append((f"base {mid}", ["a base frequency for an id no row uses"]))
    for mid in sorted(dspnoise.BASES):
        if mid not in seen:
            bad.append((f"BASES {mid}", ["a renderer row for an id no browser row uses"]))
    if bad:
        print()
        for what, note in bad:
            print(f"FAIL {what}: " + "; ".join(note))
        sys.exit(1)
    print(f"PASS drum rows: {len(table)} rows, every stored id is its own index, "
          f"every routing agrees between control.c, dsp808 and dspnoise")


if __name__ == "__main__":
    main()
