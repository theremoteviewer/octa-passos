#!/usr/bin/env python3
"""Analog BD DSP 808/909 engines in an OT image (modules/analog-bassdrum/DSP909.md).

build_bus.py calls integrate() last, when the remix carries ANALOG BD, after
every DSP pass has written both payloads. For each payload it

  1. assembles ab_glue.asm with both bass-drum engines behind it at the harvested SPRING
     REV's P address (the remix does not list SPRING REV, so its code is on
     neither chooser: stock.harvested) and checks the bytes by disassembly
     (dsp909.assemble); the code is written over SPRING's own P words, in
     place, after checking they are still stock. A shared stock reverb helper
     is copied to the reserved end of the region and its external callers
     are retargeted before replacing the donor;
  2. points SPRING's dispatch (id 0x15, X:0x22a/0x24a) at the null stub, so a
     Part that still names SPRING REV runs a passthrough, not our code;
  3. patches the source seam, `move a,x:>$20e` (A P:0x39c, B P:0x1a2), into
     a jsr to the glue;
  4. builds the payload's upload with one more X record: the 909's tables at
     X:0x2840 and four voice blocks after them, in private X that both
     cores' measured memory ledgers mark free. Not the shared window: stock PLATE and DARK write
     14,335 and 15,778 words into a 16K FX2 slot there, and the window runs
     code at one wait state.

The two uploads go in as PRE-BOOT payloads of octabam's loader, with the
pokes that point the DSP boot's two uploads at them.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "modules/analog-bassdrum"))
sys.path.insert(0, str(ROOT / "tools/build"))
import dsp808
import dspnoise  # noqa: E402  (the noise family: LCG, SVF, decode)
import dspperc  # noqa: E402  (the percussion renderers: hat, snare, clap)
import dspring  # noqa: E402  (the modal resonator bank)
import dsp909  # noqa: E402
import ab_records  # noqa: E402  (stock DSP upload record helpers)

BASE = ab_records.BASE
UNCACHED = ab_records.UNCACHED
GLUE = ROOT / "modules/analog-bassdrum/ab_glue.asm"
OUT = ROOT / "out/analog-bassdrum/image"

SPRING_ID = 0x15
PAY = {
    #    payload (va, len), upload pointer, SPRING's P, null stub, seam, continue
    "A": dict(payload=ab_records.PAYLOAD_A, pointer=0x40001E8E, spring=0x01252,
              null=(0x7C8, 0x7C9), seam=0x39C, cont=0x426),
    "B": dict(payload=ab_records.PAYLOAD_B, pointer=ab_records.B_POINTER, spring=0x01012,
              null=(0x588, 0x589), seam=0x1A2, cont=0x221),
}
DARK_ID = 0x16


def _harvested():
    """The stock effects this remix gives up, read from the remix itself.

    A KeyError on REMIX means something imported this module outside a build
    (a doc tool, a REPL); the SPRING-only ground is then the honest answer and
    an engine that needs more fails the size check in assemble() by name.
    """
    import os
    import pathlib as _pl
    import sys as _sys
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
    from remix import registry, stock
    try:
        name = os.environ["REMIX"]
    except KeyError:
        return frozenset({"SPRING REV"})
    r = registry.remix(name)
    return stock.harvested(set(r.modules) | set(r.fx1 or ()))


def _ground():
    """(free words above SPRING's base, {host: words relocated}, (effects taken,)).

    The engines take every harvested span contiguous with SPRING's base, and a
    routine a KEPT effect calls inside one of those spans is MOVED above the
    engines rather than worked around (RELOC). The ground is the run, less the
    words those copies occupy.

    ⚠️ RELOCATING RATHER THAN RESERVING IS WHAT MADE THE HARVEST PAY. PLATE's
    93-word tail sits at the TOP of DARK's span, so reserving it in place split
    the run into 2,037 words below and 1,339 above -- and a module is one code
    stream, which can use only one. Jesse harvested six effects in passos-pl
    and got the room for two. The tail is called from ONE site per payload and
    holds one absolute address, which is exactly the shape of the SPRING helper
    the build had relocated since the beginning.
    """
    import pathlib as _pl
    import sys as _sys
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
    from remix import stock
    harvest = _harvested()
    words, taken, moved = None, None, {}
    for tag, c in PAY.items():
        sp = stock.p_spans(tag)
        top, covered = c["spring"], []
        for a, n, k in sorted((a, n, k) for k, (a, n) in sp.items() if k in harvest):
            if a < c["spring"]:
                continue                  # below the engines' base: not ours
            if a != top:
                break                     # a gap: one stream needs one run
            top, _ = a + n, covered.append(k)
        # every routine a kept effect calls inside what we just claimed
        mv = {}
        for host, entries in sorted(stock.CROSS_ENTRIES.items()):
            if host not in covered or host not in RELOC:
                continue
            if all(caller in harvest for _off, callers in entries for caller in callers):
                continue                  # every caller is dead: nothing to keep
            mv[host] = RELOC[host][1]
        have = top - c["spring"] - sum(mv.values())
        if words is not None and (have != words or mv != moved):
            die(f"payload {tag} offers {have} words and the other offers {words}; "
                f"one source is assembled into both, so the ground has to match")
        words, taken, moved = have, tuple(covered), mv
    return words, moved, taken


def _span(image, recs, key, tag):
    """(address, words) of a stock effect's code in this payload."""
    import pathlib as _pl
    import sys as _sys
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
    from remix import stock
    return stock.p_spans(tag)[key]


def _retarget(img, recs, stock_img, srecs, tag, old, new, host, log):
    """Retarget every LIVE two-word `jsr`/`jmp` at `old`; return the live count.

    ⚠️ FOUND, NOT WRITTEN DOWN. The old code carried the three caller addresses
    of SPRING's helper as a constant, which was right until a second routine
    needed the same treatment. Scanning means a firmware whose callers differ
    raises instead of being half-patched, and the count is the assertion that
    makes that true.

    ⚠️ AND LIVE MEANS IN A SPAN WE ARE KEEPING. DARK's tail is called TWICE --
    once from PLATE, which is kept, and once from DARK itself, which is about
    to become a drum voice. Counting both made the census say 2 against the 1
    this was written for; retargeting dead code would also have been harmless
    and silent, which is worse. Only a caller whose own effect survives counts.
    """
    import pathlib as _pl
    import sys as _sys
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
    from remix import stock
    spans = stock.p_spans(tag)
    live = 0
    for space, base, cnt, _off in sorted(recs, key=lambda m: m[1]):
        if space != 0:
            continue
        for a in range(base, base + cnt - 1):
            o0 = ab_records.word_at(recs, 0, a)
            if ab_records.rd(img, o0) not in (0x0bf080, 0x0af080):
                continue
            o1 = ab_records.word_at(recs, 0, a + 1)
            if ab_records.rd(img, o1) != old:
                continue
            owner = next((k for k, (sa, sn) in spans.items() if sa <= a < sa + sn), None)
            if owner in HARVEST:
                log.append(f"    P:{a:05x} calls {host}'s routine from {owner}, "
                           f"which this remix gives up -- left alone")
                continue
            ab_records.wr(img, o1, new)
            log.append(f"    P:{a:05x} {ab_records.rd(img, o0):06x} {old:06x} -> "
                       f"{new:06x}  {tag} {host}'s routine, called from "
                       f"{owner or 'outside every effect'}")
            live += 1
    return live


def _stub_ids():
    """The FX2 ids of every effect the engines overwrite, in address order.

    ⚠️ ONE STUB PER OVERWRITTEN EFFECT, DERIVED. Off both choosers an effect
    cannot be PICKED, but a Part saved while it existed still names its id and
    the loader dispatches whatever the Part names ("a part saved under an older
    slot layout feeds the new layout its old bytes", AGENTS.md) -- so an
    unstubbed entry whose code is now a drum voice is a jump into the middle of
    one. This was SPRING and DARK, hardcoded, which was right for exactly the
    two-effect harvest it was written for.
    """
    import pathlib as _pl
    import sys as _sys
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
    from remix import stock
    return tuple(stock.BY_KEY[k].menu.fx2_id for k in TAKEN)


def die(msg):
    sys.exit(f"ab-image: {msg}")


TABLES = 0x2840                 # X: the tables, then the voice blocks
VOICE_STRIDE = 0x40             # 2 * x:$418 (0/$20/$40/$60)
KNOBS = 0x30                    # the knob block inside a voice block
TABLES808 = 0x3200
VOICES808 = 0x3780   # was 0x3600: M_ENGINE, B_RATIO and M_BASE added three 128-word tables
# The percussion family's own curves. It has NO voice blocks of its own: a
# track runs one engine or the other, never both, so it shares the 909's --
# which also means it inherits the knob block at +0x30 that any voice needs.
# Each engine's trigger zeroes the state words it reads, because what is in
# them is whatever the 909, or another percussion engine, left there.
TABLESNZ = 0x3880
# Derived, never a literal: the family grew from two curves to three the moment
# it got its own decay table, and a hardcoded 128 put the third past the end of
# the word array (caught by the assert in x_image, which is why it is one).
NZWORDS = 64 * len(dspnoise.tables())
X_TOP = 0x3940                  # the lower of the two ledgers' free tops
# Pre-boot destination and staging buffers for each DSP upload.
PRE = {"A": (0x40B00000, 0x40B80000), "B": (0x40B40000, 0x40BC0000)}


# ---- routines a KEPT effect calls inside ground we want to take ----------
# {host effect: (offset into its span, words, (indices of words holding an
#               absolute address,), expected caller count, sha of the
#               NORMALISED words or None to use TAIL_SHA256)}
#
# Both of these are the same problem and share one mechanism: a stock routine
# sitting in a span we want, called from code we keep. Copy it above the
# engines, fix the absolute addresses inside it, retarget every caller, and the
# host's whole span becomes placeable.
#
# ⚠️ THE SECOND ONE IS WHAT UNFRAGMENTS THE GROUND. PLATE's 93-word tail sits
# at the TOP of DARK's span, between DARK's body and COMPRESSOR, so leaving it
# where stock put it split the harvest into 2,037 words below and 1,339 above
# -- and a module is one code stream. Relocating it the way SPRING's helper was
# always relocated makes SPRING through COMB FILTER one run.
#
# The sha is over the words with every absolute address made RELATIVE to the
# routine's base, so the pin does not depend on where stock linked it.
# dsp_disasm_all.py found the fixups: SPRING's word 6 is a `do` endpoint and so
# is DARK +0x3ce's word 83 (`do n7,>$1aa3`). Everything else in both is a
# relative branch or a call into FILTER, which is kept and does not move.
RELOC = {
    "SPRING REV": (0x334, 35, (6,), 3,
                   "c411c03ac315959374f7f16b8cc3558f65dbcd60dcdaa912ff0a39dcea53752a"),
    "DARK REV": (0x3ce, 93, (83,), 1, None),
}
# ⚠️ PINNED PER PAYLOAD, BECAUSE THE TAIL IS NOT PAYLOAD-IDENTICAL. Besides the
# `do` endpoint it carries a ONE-WORD absolute `jsr` into FILTER -- 0d09ad in A,
# 0d076d in B -- and FILTER is kept, so that word needs no fixup but does make
# the two copies differ. A single shared digest was the first attempt and A and
# B disagreed, which is the check doing its job.
TAIL_SHA256 = {
    "A": "a0357a05725b763f6e845ebf5d64dcb3201cb230a262b544819e61e47b77b28a",
    "B": "d75fb03067c53c05f1ff893bcc13dce4d2139b892ec113c73f761056e901609c",
}
# ⚠️ RESOLVED AT integrate() TIME, not at import: _ground() reads the remix and
# the stock image's own spans, so importing this file for its constants must
# not depend on $REMIX.
SPRING_WORDS: int | None = None         # free words above SPRING's base
MOVED: dict | None = None               # {host effect: words relocated above us}
HARVEST: frozenset | None = None
TAKEN: tuple | None = None              # the harvested effects actually overwritten


def _resolve():
    """Settle the ground once per build. Idempotent, called by integrate()."""
    global SPRING_WORDS, MOVED, HARVEST, TAKEN
    if SPRING_WORDS is None:
        HARVEST = _harvested()
        SPRING_WORDS, MOVED, TAKEN = _ground()
    return SPRING_WORDS, MOVED


def layout():
    lay = dsp909.default_layout(TABLES)
    end = max(a + n for a, n in ((lay[k], len(v)) for k, v in
                                  list(dsp909.tables()[0].items()) + list(dsp909.tables()[2].items())))
    vbase = (end + 0x3F) & ~0x3F
    # ⚠️ CORE B'S PER-MACHINE TABLE LIVES IN THE 909 TABLES' ALIGNMENT PAD.
    # The voice blocks are 0x40-aligned, which leaves 47 words above the last
    # 909 table doing nothing; core B needs 8. Everything else between TABLES
    # and the measured free top X:0x3940 is allocated to the last word -- the
    # three 64-entry curves end exactly ON it -- so this pad is the only free
    # private X there is, and it is derived from the 909's own layout rather
    # than written down, so a table added there moves this with it.
    lay['NZ_BASE'] = end
    if end + dspnoise.NBASE > vbase:
        die(f"core B's {dspnoise.NBASE}-word machine table does not fit the "
            f"{vbase - end} words of alignment pad at X:{end:05x}")
    if dsp909.SWORDS > KNOBS or KNOBS + 13 > VOICE_STRIDE:
        die(f"a voice block holds {dsp909.SWORDS} state words and 13 knob words: "
            f"stride {VOICE_STRIDE:#x} is too small")
    if vbase + 4 * VOICE_STRIDE > X_TOP:
        die(f"tables and voices end at X:{vbase + 4 * VOICE_STRIDE:05x}, past the free top {X_TOP:05x}")
    return lay, vbase


def x_image(lay, vbase):
    """The X record: tables, then four voice blocks as zq02 leaves them."""
    words = [0] * (TABLESNZ + NZWORDS - TABLES)
    assert vbase + 4 * VOICE_STRIDE <= TABLES808
    assert VOICES808 + 4 * VOICE_STRIDE <= X_TOP
    for name, vals in dsp808.tables().items():
        start = dsp808.layout(TABLES808)[name]
        assert start + len(vals) <= VOICES808
        for i, v in enumerate(vals):
            words[start - TABLES + i] = dsp909.q24(v)
    tab, _, lists, _ = dsp909.tables()
    for name, vals in list(tab.items()) + list(lists.items()):
        for i, v in enumerate(vals):
            words[lay[name] - TABLES + i] = dsp909.q24(v)
    for k in range(4):
        b = vbase - TABLES + k * VOICE_STRIDE
        words[b + dsp909.OFF["C"]] = 0x7FFFFF
        words[b + dsp909.OFF["KLPF"]] = 0x7FFFFF
        words[b + dsp909.OFF["LCG"]] = dsp909.SEED
    for k in range(4):
        words[VOICES808 - TABLES + k * VOICE_STRIDE + 0x16] = 0x7fffff
    # core B's tables and its four voice blocks, each seeded like the 909's
    for name, vals in dspnoise.tables().items():
        start = dspnoise.layout(TABLESNZ)[name]
        assert start + len(vals) <= TABLESNZ + NZWORDS, f"core B table {name} overruns"
        for i, v in enumerate(vals):
            words[start - TABLES + i] = dsp909.q24(v)
    assert TABLESNZ + NZWORDS <= X_TOP, "core B's tables run past the measured free top"
    # the per-machine table: band<<16 | decay<<8 | width, one word per model
    for i, w in enumerate(dspnoise.base_words()):
        words[lay['NZ_BASE'] - TABLES + i] = w
    # Every core B model dsp808 routes to this voice must have a row, or the
    # engine would read a zero word and run a machine nobody specified.
    for _m, _e in dsp808.MACHINE_ENGINE.items():
        if _e == 2 and _m not in dspnoise.BASES:
            die(f"model {_m} runs core B's voice and has no dspnoise.BASES row")
    return words


def assemble(org, cont, lay, vbase, tag):
    glue = GLUE.read_text().replace("@VBASE@", f"${vbase:x}").replace("@CONT@", f"${cont:x}")
    glue = glue.replace("@V808@", f"${VOICES808:x}")
    # M_ENGINE lives with the 808's tables; the glue needs its address too.
    _l808 = dsp808.layout(TABLES808)
    glue = glue.replace("@M_ENGINE@", f"${_l808['M_ENGINE']:x}")
    glue = glue.replace("@M_BASE@", f"${_l808['M_BASE']:x}")
    glue = glue.replace("@MIDNZ@", f"${dsp909.q24(0.375):06x}")
    _l808 = dsp808.layout(TABLES808)
    _shared = dict(lay); _shared.update(B_DE=_l808["B_DE"], B_VEL=_l808["B_VEL"])
    src = (glue + "\n" + dsp909.source(lay) + "\n" + dsp808.source(_l808, lay)
           + "\n" + dspnoise.source(dspnoise.layout(TABLESNZ), _shared,
                                      nzbase=lay['NZ_BASE'])
           + "\n" + dspperc.source(dspnoise.OFF, dspnoise.layout(TABLESNZ), _shared)
           + "\n" + dspring.source(dspnoise.OFF, dspnoise.layout(TABLESNZ), _shared))
    OUT.mkdir(parents=True, exist_ok=True)
    binf = OUT / f"ab_{tag}.bin"
    syms, _ = dsp909.assemble(org, lay, binf, src)
    blob = binf.read_bytes()
    words = [blob[i] | blob[i + 1] << 8 | blob[i + 2] << 16 for i in range(0, len(blob), 3)]
    room = SPRING_WORDS - (0 if "DARK REV" in HARVEST else SHARED_WORDS)
    if len(words) > room:
        die(f"payload {tag}: glue + engine are {len(words)} words; the region "
            f"offers {room} (ground {SPRING_WORDS}"
            + ("" if "DARK REV" in HARVEST else f", less {SHARED_WORDS} for the kept helper") + ")")
    return words, syms


def integrate(img, stock_img):
    """Patch both payloads in `img` (bytearray); return ([pre-boot dicts], [pokes], log).
    `stock_img` is the pristine image: SPRING's words are checked against it."""
    from remix import runtime_build, platform_build
    _resolve()
    lay, vbase = layout()
    xwords = x_image(lay, vbase)
    dark = "DARK REV" in HARVEST
    pres, pokes, log = [], [], []
    for tag, c in PAY.items():
        recs, term = ab_records.records(img, *c["payload"])
        srecs, _ = ab_records.records(stock_img, *c["payload"])
        words, syms = assemble(c["spring"], c["cont"], lay, vbase, tag)
        # ---- move every routine a KEPT effect calls out of our way --------
        # One mechanism for both: copy the words above the engines, make the
        # absolute addresses inside them point at the copy, and retarget every
        # caller. The callers are FOUND in the image rather than written down,
        # and the count is checked -- a routine with an unexpected number of
        # callers is one whose census no longer describes the firmware.
        at = c["spring"] + SPRING_WORDS
        for host in sorted(MOVED):
            off_in, n, fixups, want_calls, pin = RELOC[host]
            src = _span(stock_img, srecs, host, tag)[0] + off_in
            body = [ab_records.rd(stock_img, ab_records.word_at(srecs, 0, src + i))
                    for i in range(n)]
            norm = body.copy()
            for ix in fixups:
                norm[ix] -= src
            digest = hashlib.sha256(b"".join((w & 0xffffff).to_bytes(3, "big")
                                             for w in norm)).hexdigest()
            want = pin if pin is not None else TAIL_SHA256[tag]
            if digest != want:
                die(f"payload {tag}: the {n} words at P:{src:05x} ({host} "
                    f"+0x{off_in:x}) that a kept effect calls are not the "
                    f"routine this build pinned (got {digest[:16]})")
            for i, w in enumerate(body):
                w = (norm[i] + at) if i in fixups else w
                o = ab_records.word_at(recs, 0, at + i)
                if ab_records.rd(img, o) != ab_records.rd(
                        stock_img, ab_records.word_at(srecs, 0, at + i)):
                    die(f"payload {tag}: relocation destination P:{at + i:05x} is not stock")
                ab_records.wr(img, o, w)
            hits = _retarget(img, recs, stock_img, srecs, tag, src, at, host, log)
            if hits != want_calls:
                die(f"payload {tag}: {host} +0x{off_in:x} has {hits} live callers, "
                    f"not the {want_calls} this build was written against")
            log.append(f"  analog bd {tag}: {host} +0x{off_in:x} ({n} words a kept "
                       f"effect calls) MOVED P:{src:05x} -> P:{at:05x}; "
                       f"{hits} caller{'s' if hits != 1 else ''} retargeted")
            at += n
        # 1. the code over SPRING's words, which must still be stock
        for i, w in enumerate(words):
            off = ab_records.word_at(recs, 0, c["spring"] + i)
            soff = ab_records.word_at(srecs, 0, c["spring"] + i)
            if ab_records.rd(img, off) != ab_records.rd(stock_img, soff):
                die(f"payload {tag}: P:{c['spring'] + i:05x} is no longer SPRING REV's stock word; "
                    f"something else was placed in its region")
            ab_records.wr(img, off, w)
        # 2. the given-up reverbs' dispatch -> the null stub
        # ⚠️ DARK'S TWO ENTRIES AS WELL, and for the same reason as SPRING's:
        # off both choosers it cannot be PICKED, but a Part saved while it
        # existed still carries its id, and the loader dispatches whatever the
        # Part names ("a part saved under an older slot layout feeds the new
        # layout its old bytes", AGENTS.md). Its own code survives -- the engine
        # is 1,138 words and stops below it -- but the 35-word helper it calls
        # three times does not, so an old Part naming DARK REV would run stock
        # reverb code into the middle of a bass drum. Jesse has projects older
        # than this build. The stub is also what makes dropping that helper safe.
        for eid in _stub_ids():
            for table, stub in ((0x215, c["null"][0]), (0x235, c["null"][1])):
                off = ab_records.word_at(recs, 1, table + eid)
                got = ab_records.rd(img, off)
                if not (c["spring"] <= got < c["spring"] + SPRING_WORDS or got == stub):
                    die(f"payload {tag}: X:{table + eid:05x} holds {got:06x}, not "
                        f"the entry of a reverb this remix gives up")
                ab_records.wr(img, off, stub)
        # 3. the seam
        ab_records.patch(img, recs, 0, c["seam"], (0x567000, 0x00020E), (0x0BF080, syms["zg01"]),
                       f"{tag} source seam -> jsr the Analog BD glue", log)
        # 4. the upload: the payload's records, the X record, its terminator
        p0 = c["payload"][0] - BASE
        raw = bytes(img[p0:term]) + ab_records.ot_record(1, TABLES, xwords) + \
            bytes(img[term:p0 + c["payload"][1]])
        packed = runtime_build.PACKED_MAGIC + len(raw).to_bytes(4, "big") + \
            runtime_build.pack(raw, platform_build.MAX_CANDIDATES)
        dst, stage = PRE[tag]
        if len(raw) > 0x40000 or 4 + len(packed) > 0x40000:
            die(f"payload {tag}'s upload ({len(raw):,} B, packed {len(packed):,}) outgrows its scratch")
        pres.append(dict(name=f"analog bd payload {tag}", blob=platform_build.SIGNATURE + packed,
                         stage=stage + UNCACHED, dst=dst + UNCACHED, rawlen=len(raw),
                         rhash=platform_build.roll(raw)))
        pokes.append((c["pointer"], c["payload"][0].to_bytes(4, "big"), (dst + UNCACHED).to_bytes(4, "big"),
                      f"DSP boot: payload {tag}'s upload reads the Analog BD's"))
        _ids = "/".join(f"0x{e:02x}" for e in _stub_ids())
        log.append(f"  analog bd {tag}: glue + 808/909{'/core B' if dark else ''} {len(words)} words "
                   f"at P:{c['spring']:05x} "
                   f"({'SPRING+DARK' if dark else 'SPRING REV'}'s ground, {SPRING_WORDS} words"
                   f"{f', {sum(MOVED.values())} relocated above it' if MOVED else ''}); "
                   f"id {_ids} -> null stub "
                   f"{c['null'][0]:05x}/{c['null'][1]:05x}; X:{TABLES:05x}..{TABLES + len(xwords) - 1:05x} "
                   f"tables + voices (voice 0 at {vbase:05x}); upload {len(raw):,} B, packed {len(packed):,}")
        (OUT / f"upload_{tag}.bin").write_bytes(raw)
        (OUT / f"ab_{tag}.sym").write_text("".join(f"{k} {v:06x}\n" for k, v in sorted(syms.items(), key=lambda kv: kv[1])))
    return pres, pokes, log
