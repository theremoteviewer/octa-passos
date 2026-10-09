#!/usr/bin/env python3
"""The stock effects' spans are NOT self-contained: re-derive which ones another
effect calls into, and refuse any difference from stock.CROSS_ENTRIES.

Why this gate exists: `stock.py` claimed every one of the thirteen DSP effects
was self-contained, citing `tools/build/dsp_reach.py`. That tool measures
REACHABILITY -- whether each instruction is reached from some entry point -- and
a call that crosses a span boundary is reached like any other, so the sweep
could never have seen a boundary crossing. The claim cost a build in which
PLATE REV stopped matching stock, because PLATE calls a 93-word routine that
lives at the top of DARK REV's span and the engines were placed over it.

What is measured here, from the user's own image:
  - every jsr/jmp/jcc whose target is in a different effect's span than its site
  - the OFFSET of each target into its host span, in BOTH payloads

Both payloads must agree on the offsets (they are linked separately, so the
addresses differ and the offsets do not), and the result must equal
`stock.CROSS_ENTRIES` exactly. A firmware whose layout differs fails here
rather than being harvested into a crash.

    python3 tools/verify/verify_stock_spans.py
"""
import pathlib
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import dsp_modmap as dm  # noqa: E402
from remix import stock  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIS = ROOT / "vendor/dsp56300/build/source/disassemble/dsp56kDisassemble"
# A control transfer, as the vendored disassembler spells it. `do`/`rep` are
# deliberately absent: their operand is a loop END address, not a target, and
# PLATE's own `do #<$6,>$1267` is the false positive that reading it as a
# target would produce.
CALLISH = re.compile(r"^(jsr|bsr|jmp|bra|j[a-z]{2}|b[a-z]{2})\b", re.I)
TARGET = re.compile(r"func_([0-9a-f]{3,6})|>\$([0-9a-f]{3,6})")


def disassemble(tag):
    """{P address: text} for every P instruction of one stock payload."""
    img = dm.IMG.read_bytes()
    va, ln = [(v, l) for t, v, l in dm.PAYLOADS if t == tag][0]
    mods, blob = dm.modules(img, va, ln)
    out = {}
    with tempfile.TemporaryDirectory(prefix="spans") as tmp:
        scratch = pathlib.Path(tmp) / "m.bin"
        for space, addr, cnt, off in mods:
            if space != 0:
                continue
            scratch.write_bytes(blob[off:off + cnt * 3])
            r = subprocess.run([str(DIS), "-in", str(scratch), "-pc", f"{addr:x}", "-le"],
                              capture_output=True, text=True)
            for line in r.stdout.splitlines():
                m = re.match(r"^([0-9a-f]{6}):\s+(.*?)\s*;", line)
                if m:
                    out[int(m.group(1), 16)] = m.group(2).strip()
    return out


def crossings(tag):
    """{host effect: {offset into its span: frozenset(calling effects)}}."""
    spans = stock.p_spans(tag)

    def owner(a):
        for key, (base, words) in spans.items():
            if base <= a < base + words:
                return key
        return None

    found = {}
    for addr, text in disassemble(tag).items():
        if not CALLISH.match(text):
            continue
        for a, b in TARGET.findall(text):
            target = int(a or b, 16)
            host, site = owner(target), owner(addr)
            if host is None or host == site or site is None:
                continue
            off = target - spans[host][0]
            found.setdefault(host, {}).setdefault(off, set()).add(site)
    return {h: {o: frozenset(c) for o, c in e.items()} for h, e in found.items()}


def main():
    if not DIS.exists():
        sys.exit(f"missing {DIS} -- run 'make setup'")
    per = {tag: crossings(tag) for tag in ("A", "B")}
    if per["A"] != per["B"]:
        sys.exit("payload A and B disagree on where control crosses a span:\n"
                 f"  A {per['A']}\n  B {per['B']}\n"
                 "The offsets are the same routine in two separately linked "
                 "payloads; a difference means the spans are mis-identified.")
    want = {h: {o: frozenset(c) for o, c in e} for h, e in stock.CROSS_ENTRIES.items()}
    got = per["A"]
    if got != want:
        for host in sorted(set(got) | set(want)):
            if got.get(host) != want.get(host):
                print(f"  {host}: measured {got.get(host)} , stock.py says {want.get(host)}")
        sys.exit("stock.CROSS_ENTRIES does not match this image. Every entry is "
                 "a routine one effect calls inside another's span, so "
                 "harvesting the host breaks the caller: update the table AND "
                 "stock.reserved_spans' callers before building.")
    for host, entries in sorted(got.items()):
        for off, callers in sorted(entries.items()):
            a_addr = stock.p_spans("A")[host][0] + off
            b_addr = stock.p_spans("B")[host][0] + off
            print(f"PASS {host} +0x{off:03x} (A P:{a_addr:05x}, B P:{b_addr:05x}) "
                  f"<- {', '.join(sorted(callers))}")
    # The reservation the build actually uses, for the harvest this matters to.
    for harvest, note in ((frozenset({"SPRING REV", "DARK REV"}), "SPRING+DARK, PLATE kept"),
                          (frozenset(stock.CONSUMED), "all three reverbs")):
        res = stock.reserved_spans(harvest)
        print(f"  harvest {note}: reserved "
              f"{ {k: (f'{a:05x}', n) for k, (a, n) in res.items()} or 'nothing'}")
    print(f"PASS {len(got)} hosts, both payloads agree, stock.CROSS_ENTRIES matches")


if __name__ == "__main__":
    main()
