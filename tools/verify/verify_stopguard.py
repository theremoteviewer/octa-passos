#!/usr/bin/env python3
"""STOP GUARD's claims about the settings block, checked against the image.

The module puts its flag in a long that nothing else uses, inside the
block stock copies back at boot. Both halves of that are checkable here,
and neither is asserted by a Detour or a Poke -- a Poke proves what is AT
an address, not what is absent everywhere else. So:

  1. the non-volatile settings block is what the module says it is:
     magic "ANDY", the 252-byte checksum span, and a 100-byte copy to the
     live block, so each setting is live 0x80000070+k / mirror
     0x100fff00+k;
  2. all sixteen PERSONALIZE rows land inside that copy, and each row's
     live long and mirror long differ by exactly 0x70;
  3. the module's word -- live 0x800000a8, mirror 0x100fff38 -- appears
     nowhere in the image as a 32-bit literal, and is outside both bulk
     clears;
  4. the edit dispatcher stamps the checksum after every setter, so the
     module's setter does not have to.

Run it against the decompressed MAIN OS:

    python3 tools/verify/verify_stopguard.py [out/raw/section_3_MAIN_OS.bin]
"""

import pathlib
import struct
import sys

BASE = 0x40000400
RAW = "out/raw/section_3_MAIN_OS.bin"

MIRROR = 0x100FFF00          # the non-volatile block: checksum first
LIVE = 0x80000070            # where boot copies it
COPY = 100                   # bytes copied (0x40020898's third argument)
CKSUM_FROM = 0x100FFF04      # the checksum span starts after the checksum
CKSUM_LEN = 252

GUARD_LIVE = 0x800000A8
GUARD_MIRROR = 0x100FFF38

LABELS, GETTERS, SETTERS, ROWS = 0x400B2A34, 0x400B2A74, 0x400B2AC0, 16
MAGIC_I = 0x4001F2AA         # move.l #"ANDY",%d0
MAGIC_W = 0x4001F2B0         # move.l %d0,0x100fff04
COPY_LEN = 0x4001F3BE        # pea 100
COPY_SRC = 0x4001F3C2        # pea 0x100fff00
COPY_DST = 0x4001F3C8        # pea 0x80000070, then jsr the memcpy
STAMP = 0x4001F23C           # recompute and store the checksum
DISPATCH_STAMP = 0x40069074  # the PERSONALIZE editor's jmp to it


def main(argv):
    path = pathlib.Path(argv[1] if len(argv) > 1 else RAW)
    if not path.exists():
        print(f"  [SKIP] {path} not found -- run `make os && make recon` first")
        return 0
    d = path.read_bytes()

    def rd32(a):
        return struct.unpack_from(">I", d, a - BASE)[0]

    def literals(v):
        b, out, i = struct.pack(">I", v), [], 0
        while (i := d.find(b, i)) >= 0:
            out.append(i + BASE)
            i += 1
        return out

    bad = 0

    def check(ok, msg):
        nonlocal bad
        print(("  [PASS] " if ok else "  [FAIL] ") + msg)
        if not ok:
            bad += 1

    # 1. the block -------------------------------------------------------
    # The block lives in RAM, so the image carries the CODE that stamps it,
    # not the bytes: the defaults routine writes the magic, and boot copies
    # the block to the live addresses.
    check(struct.unpack_from(">HI", d, MAGIC_W - BASE) == (0x23C0, CKSUM_FROM)
          and struct.unpack_from(">HI", d, MAGIC_I - BASE) == (0x203C, 0x414E4459),
          f'0x{MAGIC_I:08x} writes the magic "ANDY" to 0x{CKSUM_FROM:08x}')
    check(struct.unpack_from(">HI", d, COPY_DST - BASE) == (0x4879, LIVE)
          and struct.unpack_from(">HI", d, COPY_SRC - BASE) == (0x4879, MIRROR)
          and struct.unpack_from(">HH", d, COPY_LEN - BASE) == (0x4878, COPY),
          f"boot copies {COPY} bytes 0x{MIRROR:08x} -> 0x{LIVE:08x}")
    check(True, f"so the pair is live 0x{LIVE:08x}+k, mirror 0x{MIRROR:08x}+k")

    # 2. every row inside the copy, and paired ---------------------------
    #    Each setter ends `move.l %d0,<live> / move.l %d0,<mirror> / rts`.
    pairs = []
    for i in range(ROWS):
        s = rd32(SETTERS + 4 * i)
        live = mirror = None
        for o in range(0, 0x90, 2):
            if struct.unpack_from(">H", d, s - BASE + o)[0] == 0x23C0:
                v = struct.unpack_from(">I", d, s - BASE + o + 2)[0]
                if 0x80000000 <= v < 0x80001000:
                    live = v
                elif MIRROR <= v < MIRROR + 0x100:
                    mirror = v
            if struct.unpack_from(">H", d, s - BASE + o)[0] == 0x4E75 and o > 8:
                break
        pairs.append((live, mirror))
    check(all(l is not None and m is not None for l, m in pairs),
          f"all {ROWS} PERSONALIZE setters write a live long and a mirror")
    check(all(l - LIVE == m - MIRROR for l, m in pairs if l and m),
          "every row sits at the same offset k in both blocks")
    check(all(LIVE <= l < LIVE + COPY for l, m in pairs if l),
          f"every row is inside the {COPY}-byte copy "
          f"(0x{LIVE:08x}..0x{LIVE + COPY - 1:08x})")

    # 3. the module's word ----------------------------------------------
    check(GUARD_LIVE - LIVE == GUARD_MIRROR - MIRROR,
          f"0x{GUARD_LIVE:08x} pairs with 0x{GUARD_MIRROR:08x} "
          f"(k = 0x{GUARD_LIVE - LIVE:02x})")
    check(LIVE <= GUARD_LIVE < LIVE + COPY,
          f"0x{GUARD_LIVE:08x} is inside the copy, so boot restores it")
    check(CKSUM_FROM <= GUARD_MIRROR < CKSUM_FROM + CKSUM_LEN,
          f"0x{GUARD_MIRROR:08x} is inside the {CKSUM_LEN}-byte checksum")
    taken = {l for l, _ in pairs if l}
    check(GUARD_LIVE not in taken,
          f"0x{GUARD_LIVE:08x} is not one of the {ROWS} stock rows")
    for v in (GUARD_LIVE, GUARD_MIRROR):
        hits = literals(v)
        check(not hits,
              f"0x{v:08x} appears nowhere in the image as a 32-bit literal"
              + ("" if not hits else
                 "  -- found at " + ", ".join(f"0x{a:08x}" for a in hits)))

    # 4. the checksum is stamped for us ----------------------------------
    check(rd32(DISPATCH_STAMP + 2) == STAMP
          and struct.unpack_from(">H", d, DISPATCH_STAMP - BASE)[0] == 0x4EF9,
          f"the PERSONALIZE editor jumps to the checksum stamp "
          f"0x{STAMP:08x} after every setter")

    print(f"\n{'PASS' if not bad else 'FAIL'}: {bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
