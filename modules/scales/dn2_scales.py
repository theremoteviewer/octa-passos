#!/usr/bin/env python3
"""The Digitone II's thirty-six keyboard scales, for the-passenger mod.

NAMES AND ORDER are transcribed from APPENDIX E: KEYBOARD SCALES of the
Digitone II User Manual, read column by column as the manual prints it.
That is the parity requirement: the same scales, the same order, so the
two machines can be set to the same thing by eye.

INTERVALS are NOT in the manual -- it prints names only -- so every row
below is derived from the name and then cross-checked. Where a name has
more than one accepted form in the wild, `AMBIGUOUS` says so and says
which reading was taken. One row, COMBO MINOR, is Elektron's own coinage
and is a guess; see UNRESOLVED.

Two checks make the derivation more than an assertion:

  * the seven modes of DOUBLE HARMONIC MAJOR all appear in the list
    (itself, LYDIAN #2 #6, ULTRAPHRYGIAN, HUNGARIAN MINOR, ORIENTAL,
    IONIAN #2 #5, LOCRIAN bb3 bb7) and each derived row must equal the
    rotation of the parent that its name describes;
  * four modes of MELODIC MINOR likewise (DORIAN b2, LYDIAN AUGMENTED,
    LYDIAN DOMINANT, SUPER LOCRIAN);
  * IWATO must be a rotation of HIRAJOSHI;
  * and every scale in MEASURED must match what the Digitone actually
    played, note for note.

If a name were read wrong, those families would stop closing. They close.

    python3 dn2_scales.py            # self-check, then the .inc on stdout
    python3 dn2_scales.py --check    # self-check only, exit 1 on failure
"""

import sys

# (manual name, 4-char panel abbreviation, semitones from the root)
#
# Index 0 is CHROMATIC, which is the Octatrack's OFF: every note passes
# through untouched. Keeping it at 0 means the stored value matches the
# Digitone's own list position AND means "no scale" is the zero state.
SCALES = [
    ("CHROMATIC",              "CHRO", list(range(12))),
    ("IONIAN (MAJOR)",         "MAJ",  [0, 2, 4, 5, 7, 9, 11]),
    ("DORIAN",                 "DOR",  [0, 2, 3, 5, 7, 9, 10]),
    ("PHRYGIAN",               "PHR",  [0, 1, 3, 5, 7, 8, 10]),
    ("LYDIAN",                 "LYD",  [0, 2, 4, 6, 7, 9, 11]),
    ("MIXOLYDIAN",             "MIX",  [0, 2, 4, 5, 7, 9, 10]),
    ("AEOLIAN (MINOR)",        "MIN",  [0, 2, 3, 5, 7, 8, 10]),
    ("LOCRIAN",                "LOC",  [0, 1, 3, 5, 6, 8, 10]),
    ("PENTATONIC MINOR",       "PMIN", [0, 3, 5, 7, 10]),
    ("PENTATONIC MAJOR",       "PMAJ", [0, 2, 4, 7, 9]),
    ("MELODIC MINOR",          "MELO", [0, 2, 3, 5, 7, 9, 11]),
    ("HARMONIC MINOR",         "HARM", [0, 2, 3, 5, 7, 8, 11]),
    ("WHOLE TONE",             "WHOL", [0, 2, 4, 6, 8, 10]),
    ("BLUES",                  "BLUE", [0, 3, 5, 6, 7, 10]),
    ("COMBO MINOR",            "CMIN", [0, 2, 3, 5, 7, 8, 10, 11]),
    ("PERSIAN",                "PERS", [0, 1, 4, 5, 6, 8, 11]),
    ("IWATO",                  "IWA",  [0, 1, 5, 6, 10]),
    ("IN-SEN",                 "INSN", [0, 1, 5, 7, 10]),
    ("HIRAJOSHI",              "HIRA", [0, 2, 3, 7, 8]),
    ("PELOG",                  "PELO", [0, 1, 3, 7, 8]),
    ("PHRYGIAN DOMINANT",      "PHRD", [0, 1, 4, 5, 7, 8, 10]),
    ("WHOLE-HALF DIMINISHED",  "WHDI", [0, 2, 3, 5, 6, 8, 9, 11]),
    ("HALF-WHOLE DIMINISHED",  "HWDI", [0, 1, 3, 4, 6, 7, 9, 10]),
    ("SPANISH",                "SPAN", [0, 1, 3, 4, 5, 6, 8, 10]),
    ("MAJOR LOCRIAN",          "MLOC", [0, 2, 4, 5, 6, 8, 10]),
    ("SUPER LOCRIAN",          "ALT",  [0, 1, 3, 4, 6, 8, 10]),
    ("DORIAN b2",              "DOR2", [0, 1, 3, 5, 7, 9, 10]),
    ("LYDIAN AUGMENTED",       "LYDA", [0, 2, 4, 6, 8, 9, 11]),
    ("LYDIAN DOMINANT",        "LYDD", [0, 2, 4, 6, 7, 9, 10]),
    ("DOUBLE HARMONIC MAJOR",  "DHRM", [0, 1, 4, 5, 7, 8, 11]),
    ("LYDIAN #2 #6",           "LY26", [0, 3, 4, 6, 7, 10, 11]),
    ("ULTRAPHRYGIAN",          "ULPH", [0, 1, 3, 4, 7, 8, 9]),
    ("HUNGARIAN MINOR",        "HUNG", [0, 2, 3, 6, 7, 8, 11]),
    ("ORIENTAL",               "ORIE", [0, 1, 4, 5, 6, 9, 10]),
    ("IONIAN #2 #5",           "IO25", [0, 3, 4, 5, 8, 9, 11]),
    ("LOCRIAN bb3 bb7",        "LOBB", [0, 1, 2, 5, 6, 8, 9]),
]

# MEASURED on Jesse's own Digitone II, 28 Sep 2026, by setting ROOT = C and
# walking the keys upward in KEYBOARD mode with each scale selected, reading
# the note names off the display. AEOLIAN (MINOR) was walked first as a
# control on the display convention and came back exactly as derived.
#
# Every scale whose interval content is disputed in the literature is in
# this list, so nothing ambiguous is left resting on a derivation. check()
# asserts the table against these note names, which makes them a gate and
# not a comment.
MEASURED = {
    "AEOLIAN (MINOR)": "C D D# F G G# A#",          # the control
    "COMBO MINOR":     "C D D# F G G# A# B",
    "HIRAJOSHI":       "C D D# G G#",
    "PELOG":           "C C# D# G G#",
    "BLUES":           "C D# F F# G A#",
    "SPANISH":         "C C# D# E F F# G# A#",
    "PERSIAN":         "C C# E F F# G# B",
    "IWATO":           "C C# F F# A#",
    "IN-SEN":          "C C# F G A#",
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Names with more than one accepted form in the literature. Each of these is
# now MEASURED above; what is kept here is which reading the machine turned
# out to use, because the wrong one would have been silent.
AMBIGUOUS = {
    "BLUES": "the hexatonic blues scale (minor pentatonic + b5), not the "
             "nine-note 'blues scale' some books give",
    "SPANISH": "the eight-note Spanish/Jewish scale. PHRYGIAN DOMINANT is "
               "listed separately at 21, so this is not that",
    "PERSIAN": "1 b2 3 4 b5 b6 7, the form usually printed as 'Persian'",
    "HIRAJOSHI": "1 2 b3 5 b6 -- the form that makes IWATO and IN-SEN its "
                 "own rotations, which the family check below enforces",
    "PELOG": "1 b2 b3 5 b6, the common five-note synth approximation of a "
             "tuning that is not twelve-tone at all",
    "IN-SEN": "1 b2 4 5 b7. NOT a mode of HIRAJOSHI, despite the two "
              "being cousins -- it belongs to the Kumoi family",
    "IWATO": "1 b2 4 b5 b7",
    "MELODIC MINOR": "ascending (jazz) melodic minor, the same seven notes "
                     "going up and down",
}

# Elektron's own coinage. Derived as Aeolian plus the leading tone -- natural
# and harmonic minor combined, 1 2 b3 4 5 b6 b7 7 -- and then MEASURED as
# exactly that. The competing reading folded melodic minor in as well and
# gave nine notes; the machine does not.
UNRESOLVED = {}


def delta_map(members, nearest):
    """Twelve signed deltas: offset -> how far to move onto a scale member.

    Seven notes or more snap DOWN, which is what stock does for major and
    minor. Five and six note scales snap to the NEAREST member, ties down:
    they have three- and four-semitone gaps, and snapping only downward
    through one collapses a run onto a single note.
    """
    out = []
    for c in range(12):
        if c in members:
            out.append(0)
            continue
        if nearest:
            cand = []
            down = max((m for m in members if m <= c), default=None)
            up = min((m for m in members if m >= c), default=None)
            if down is not None:
                cand.append((c - down, down - c))
            if up is not None:
                cand.append((up - c, up - c))
            cand.sort(key=lambda t: (t[0], t[1] > 0))
            out.append(cand[0][1])
        else:
            down = max((m for m in members if m <= c), default=None)
            assert down is not None, "0 is always a member"
            out.append(down - c)
    return out


# The box on the left of MIDI NOTE SETUP is 49 pixels wide (x 3..51; the
# solid divider is at 52), and the panel font measured out of its own struct
# at 0x400ba876 is three pixels a glyph plus one of spacing -- four to a
# character. Eleven characters is 43 pixels, which fits; twelve is the first
# that might not. So the full name goes on two lines of at most eleven
# characters, split at a space, balanced. Two names have no such split and
# are given one by hand.
BOX_LINE_CHARS = 11
BOX_OVERRIDE = {
    "DOUBLE HARMONIC MAJOR": ("DOUBLE HRM", "MAJOR"),
    "ULTRAPHRYGIAN":         ("ULTRA", "PHRYGIAN"),
}


def box_lines(name):
    """The scale name as two lines for the blank box, the second may be ''."""
    if name in BOX_OVERRIDE:
        return BOX_OVERRIDE[name]
    words = name.split()
    best = None
    for i in range(1, len(words) + 1):
        one, two = " ".join(words[:i]), " ".join(words[i:])
        if len(one) <= BOX_LINE_CHARS and len(two) <= BOX_LINE_CHARS:
            score = max(len(one), len(two))
            if best is None or score < best[0]:
                best = (score, one, two)
    assert best, "no split for %r -- add it to BOX_OVERRIDE" % name
    return best[1], best[2]


def rows():
    for name, abbr, members in SCALES:
        yield name, abbr, members, delta_map(members, len(members) <= 6)


def rotation(members, degree):
    """The mode of `members` that starts on its `degree`-th note."""
    root = members[degree]
    return sorted((m - root) % 12 for m in members)


def by_name(n):
    for name, _a, members in SCALES:
        if name == n:
            return members
    raise KeyError(n)


# Families that must close. Each entry: parent, and (degree, child) pairs.
FAMILIES = [
    ("DOUBLE HARMONIC MAJOR",
     [(1, "LYDIAN #2 #6"), (2, "ULTRAPHRYGIAN"), (3, "HUNGARIAN MINOR"),
      (4, "ORIENTAL"), (5, "IONIAN #2 #5"), (6, "LOCRIAN bb3 bb7")]),
    ("MELODIC MINOR",
     [(1, "DORIAN b2"), (2, "LYDIAN AUGMENTED"), (3, "LYDIAN DOMINANT"),
      (6, "SUPER LOCRIAN")]),
    ("IONIAN (MAJOR)",
     [(1, "DORIAN"), (2, "PHRYGIAN"), (3, "LYDIAN"), (4, "MIXOLYDIAN"),
      (5, "AEOLIAN (MINOR)"), (6, "LOCRIAN")]),
    # IN-SEN is deliberately NOT here. It is a rotation of Kumoi
    # [0,2,3,7,9], not of HIRAJOSHI -- asserting otherwise was this file's
    # first bug, caught by this check.
    ("HIRAJOSHI",
     [(1, "IWATO")]),
]


def check():
    bad = 0
    seen = set()
    for name, abbr, members, dm in rows():
        if len(abbr) > 4:
            print(f"  FAIL {name}: abbreviation {abbr!r} is {len(abbr)} "
                  f"characters, the panel field holds 4")
            bad += 1
        if abbr in seen:
            print(f"  FAIL {abbr}: duplicate abbreviation")
            bad += 1
        seen.add(abbr)
        if members[0] != 0:
            print(f"  FAIL {name}: the root is not a member")
            bad += 1
        if sorted(set(members)) != members:
            print(f"  FAIL {name}: intervals not sorted or not unique")
            bad += 1
        if not all(0 <= m <= 11 for m in members):
            print(f"  FAIL {name}: interval outside one octave")
            bad += 1
        for c, delta in enumerate(dm):
            if (c + delta) % 12 not in members:
                print(f"  FAIL {name}: offset {c} + {delta} is not a member")
                bad += 1
            if not 0 <= c + delta <= 11:
                print(f"  FAIL {name}: offset {c} + {delta} leaves the octave")
                bad += 1
            if c in members and delta:
                print(f"  FAIL {name}: offset {c} is a member but moves")
                bad += 1
        if len(members) >= 7 and any(x > 0 for x in dm):
            print(f"  FAIL {name}: a seven-note scale snapping upward")
            bad += 1

    # The families. This is the real check on the interval derivation.
    for parent, kids in FAMILIES:
        pm = by_name(parent)
        for degree, child in kids:
            want, got = rotation(pm, degree), by_name(child)
            if want != got:
                print(f"  FAIL {child}: is {got}, but mode {degree + 1} of "
                      f"{parent} is {want}")
                bad += 1

    # The measurements are the gate: every scale walked on the hardware must
    # come back out of this table note for note.
    for name, notes in MEASURED.items():
        want = [NOTE_NAMES.index(x) for x in notes.split()]
        got = by_name(name)
        if got != want:
            print(f"  FAIL {name}: table has {got}, the Digitone plays "
                  f"{want} ({notes})")
            bad += 1
    if len(SCALES) != 36:
        print(f"  FAIL {len(SCALES)} scales; Appendix E lists 36")
        bad += 1
    if SCALES[0][0] != "CHROMATIC":
        print("  FAIL index 0 must be CHROMATIC (the Octatrack's OFF)")
        bad += 1
    for name, _a, _m in SCALES:
        one, two = box_lines(name)
        if max(len(one), len(two)) > BOX_LINE_CHARS:
            print("  FAIL %s: box line too long" % name)
            bad += 1
        if "".join((one + two).split()) != "".join(name.split()) \
                and name not in BOX_OVERRIDE:
            print("  FAIL %s: box split loses characters" % name)
            bad += 1
    if any(d for d in delta_map(list(range(12)), False)):
        print("  FAIL CHROMATIC moves a note")
        bad += 1
    return bad


def emit():
    o = []
    a = o.append
    a("| Generated by dn2_scales.py -- do not edit by hand.")
    a("| The Digitone II's thirty-six keyboard scales, Appendix E order.")
    a("| Index 0 is CHROMATIC, which is this machine's OFF.")
    a("")
    a("        .set    SCALE_COUNT, %d" % len(SCALES))
    a("")
    a("| Twelve signed deltas per scale, scale-major.")
    a("        .align  2")
    a("scale_ut:")
    for name, abbr, members, dm in rows():
        a("        .byte   %s    | %-4s %s"
          % (", ".join("%4d" % x for x in dm), abbr, name))
    a("")
    a("| Twelve bits per scale, low bit = the root: what the keyboard draws.")
    a("        .align  2")
    a("scale_mask:")
    for name, abbr, members, _dm in rows():
        mask = sum(1 << m for m in members)
        a("        .short  0x%03x    | %-4s %s" % (mask, abbr, name))
    a("")
    # THE KEYBOARD. Drawn as a keyboard is drawn: a lit body with the black
    # keys and the white-key gaps cut out of it, not twelve hollow boxes --
    # at this size outlines turn into a lattice and the eye cannot count
    # them. A note in the scale gets a dot: dark on a white key, lit on a
    # black one.
    #
    # THE Y AXIS RUNS BOTTOM-UP. Measured off the stock row: row 0's name is
    # drawn at y 48 in a six-pixel font (0x400ba87a) and the window interior
    # ends at 53, so 48 is the BOTTOM of those glyphs and 53 the top of the
    # box. Row 0 is the upper of the two cell rows and carries the larger y.
    # Everything here is written that way.
    #
    # The box is x 3..51, y 3..53. The body is x 7..47 by y 11..37, centred
    # with four pixels either side. Seven white keys on a six-pixel pitch,
    # each five wide with the sixth column cut as the gap to its neighbour.
    # The black keys straddle five of those six gaps and stop at y 23. The
    # name sits above at y 48 and 41, the root's tick below at y 5..7.
    X0, PITCH, YBOT, YTOP, YBLK = 7, 6, 11, 37, 23
    white = [0, 2, 4, 5, 7, 9, 11]
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    seps = [X0 + (i + 1) * PITCH - 1 for i in range(6)]      # 12 18 24 30 36 42
    rects, dots, dotlit = {}, {}, {}
    for i, s_ in enumerate(white):
        x = X0 + i * PITCH
        rects[s_] = (x, YBOT, x + PITCH - 2, YTOP)           # five wide
        dots[s_] = (x + 1, YBOT + 2, x + 3, YBOT + 4)        # dark, 3 x 3
        dotlit[s_] = 0
    for i in (0, 1, 3, 4, 5):                                # C#, D#, F#, G#, A#
        s_ = white[i] + 1
        x = seps[i] - 2
        rects[s_] = (x, YBLK, x + 3, YTOP)                   # four wide
        dots[s_] = (x + 1, YBLK + 2, x + 2, YBLK + 3)        # lit, 2 x 2
        dotlit[s_] = 1
    a("| The keyboard, in the display's BOTTOM-UP y. kbd_body is the lit")
    a("| slab; kbd_sep cuts the white keys apart; the black entries of")
    a("| kbd_rect cut the black keys out of it; kbd_dot marks the scale.")
    a("        .align  2")
    a("kbd_body:")
    a("        .byte   %3d, %3d, %3d, %3d    | x1, y1, x2, y2"
      % (X0, YBOT, X0 + 7 * PITCH - 2, YTOP))
    a("kbd_sep:")
    a("        .byte   " + ", ".join("%3d" % x for x in seps))
    a("")
    a("        .align  2")
    a("kbd_rect:")
    for s_ in range(12):
        a("        .byte   %3d, %3d, %3d, %3d    | %-2s %s"
          % (rects[s_] + (names[s_], "black" if s_ not in white else "white")))
    a("")
    a("| The dot, and the mode it is drawn in: 0 clears, 1 lights.")
    a("        .align  2")
    a("kbd_dot:")
    for s_ in range(12):
        a("        .byte   %3d, %3d, %3d, %3d    | %-2s"
          % (dots[s_] + (names[s_],)))
    a("        .align  2")
    a("kbd_dotmode:")
    a("        .byte   " + ", ".join("%3d" % dotlit[s_] for s_ in range(12)))
    a("")
    # A dot has to sit strictly inside its own key, or a scale note reads as
    # a smudge on an edge. The white keys are measured against their own
    # five-wide column, the black ones against their solid bar.
    for s_ in range(12):
        kx1, ky1, kx2, ky2 = rects[s_]
        dx1, dy1, dx2, dy2 = dots[s_]
        assert kx1 <= dx1 <= dx2 <= kx2, "dot %d off its key in x" % s_
        assert ky1 < dy1 <= dy2 < ky2, "dot %d off its key in y" % s_
        if s_ in white:
            assert kx1 < dx1 and dx2 < kx2, "white dot %d touches an edge" % s_
    # No table of the full names: nothing reads one. The cell draws the
    # abbreviation and the box draws the two-line split, and the cave this
    # module lives in is 4284 bytes with the STOP guard sharing it -- 600
    # bytes of unread strings is what pushed the first PassOS 1.0 build over
    # the end of the stock zero run.
    a("| Pointers, indexed by scale, then by root.")
    a("        .align  2")
    a("scale_l1tab:")
    for i in range(len(SCALES)):
        a("        .long   scale_p%02da" % i)
    a("")
    a("| The abbreviations, five bytes each: no pointer table, the cell")
    a("| reaches one as scale_abbr + 5*scale. Four characters plus a NUL is")
    a("| the whole of the panel's cell anyway.")
    a("        .align  2")
    a("scale_abbr:")
    for i, (_n, abbr, _m, _d) in enumerate(rows()):
        assert len(abbr) <= 4, abbr
        a('        .asciz  "%s"%s| %02d' % (abbr, " " * (7 - len(abbr)), i))
        if len(abbr) < 4:
            a("        .space  %d" % (4 - len(abbr)))
    a("")
    a("| The same names again, split for the box: at most eleven characters.")
    a("| The second line FOLLOWS the first, so there is one pointer table and")
    a("| the drawing walks past the first line's terminator to reach it.")
    for i, (name, _a, _m, _d) in enumerate(rows()):
        one, two = box_lines(name)
        a('scale_p%02da: .asciz  "%s"' % (i, one))
        a('           .asciz  "%s"' % two)
    a("")
    a("")
    a("| The twelve roots, three bytes each: scale_root + 3*root.")
    a("        .align  2")
    a("scale_root:")
    for r in ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]:
        a('        .asciz  "%s"%s' % (r, "" if len(r) == 2 else "\n        .space  1"))
    a("        .align  2")
    return "\n".join(o) + "\n"


if __name__ == "__main__":
    bad = check()
    print("dn2_scales: %d scales, %d failure(s)" % (len(SCALES), bad),
          file=sys.stderr)
    if bad:
        sys.exit(1)
    if "--check" not in sys.argv:
        sys.stdout.write(emit())
