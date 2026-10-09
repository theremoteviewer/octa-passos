#!/usr/bin/env python3
"""The reverbs this remix KEEPS stay bit-identical to stock; the ones it gives
up run the null stub, not stock code and not ours.

Two separate properties, and the second one is why the first keeps breaking:

  1. A kept reverb renders exactly what stock renders, on both cores, with
     fixed and with moving controls. PLATE REV is the one every ANALOG BD remix
     keeps, and it is not independent of the engines: PLATE calls a 93-word
     routine that lives at the TOP of DARK REV's span (stock.CROSS_ENTRIES,
     +0x3ce), so a remix that gives up DARK is placing code next to PLATE's own
     tail. On 3 Oct 2026 it placed code OVER it -- PLATE rendered 328
     instructions short of stock -- which is the failure this gate exists for.

  2. A given-up reverb's dispatch points at the null stub. Off both choosers it
     cannot be PICKED, but a Part saved while it existed still names its id and
     the loader dispatches whatever the Part names (AGENTS.md, "a part saved
     under an older slot layout"). Its code is partly overwritten and the
     helper it calls is gone, so an unstubbed entry is a jump into a bass drum.
     The stub is also what makes dropping that 35-word helper legal at all.

Both are exercised at the hardware audio address X:0, through the real
dispatcher entry points, on both cores.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import benchmark_reverbs as br
import send_probe
from remix import registry, stock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
import ab_records  # noqa: E402

# ⚠️ EVERY STOCK EFFECT WITH DSP CODE, NOT JUST THE REVERBS. This was the three
# reverbs, which was right while they were the only harvest. passos-pl gives up
# COMPRESSOR, LO-FI, DJ EQ and COMB FILTER as well, and their dispatch stubs
# were unchecked by anything until this line stopped naming names.
import dsp_modmap  # noqa: E402  (payload map, for p_spans)
EFFECTS = tuple(stock.p_spans('A'))


def _reads(img, recs, a):
    """The word at P:a, or None where no record covers it."""
    try:
        return ab_records.rd(img, ab_records.word_at(recs, 0, a))
    except BaseException:
        return None


def main():
    root = Path(__file__).resolve().parents[2]
    br.OUT = root/'out/analog-bassdrum/reverb-identity'
    br.OUT.mkdir(parents=True, exist_ok=True)
    patched = root/'out/mainos_bus.bin'
    remix = registry.remix(__import__('os').environ.get('REMIX', 'the-passenger-md'))
    harvest = stock.harvested(set(remix.modules) | set(remix.fx1 or ()))
    kept = [k for k in EFFECTS if k not in harvest]
    given = [k for k in EFFECTS if k in harvest]
    print(f'remix {remix.name}: keeps {kept or ["(none)"]}, gives up {given or ["(none)"]}')

    mems = {}
    for name, image in [('stock', stock.STOCK_IMAGE), ('patched', patched)]:
        mems[name] = [send_probe.dump_mem(image, br.OUT/f'{name}_{p}.mem', p) for p in 'AB']
    # Stop setup just before the source seam; this gate calls FX directly.
    blocks = 2048
    inputs = [br.source(blocks, k) for k in range(2)]
    extra = ('-audio', '0', '-ctx', '372,39b,53e', '-ctxB', '17a,1a1,333')

    for key in kept:
        for moving in (False, True):
            audio = []
            for name in ('stock', 'patched'):
                _, samples = br.run(registry.by_key(key), mems[name], f'{name}-{moving}',
                                    blocks, 2, moving, inputs=inputs, positions=[0, 4],
                                    extra=extra)
                audio.append(samples)
            assert audio[0] == audio[1], (key, moving, 'kept reverb changed')
            assert any(v for track in audio[0] for v in track), (key, moving, 'silent comparison')
            print(f'PASS {key}, moving={moving}: both cores exactly match stock', flush=True)

    # ---- the routines a kept effect calls, which the build MOVES ---------
    # ⚠️ THIS USED TO ASSERT THEY WERE STILL STOCK WHERE STOCK PUT THEM, and
    # that check passed vacuously the moment the build started relocating them
    # instead of reserving them: the engine had not grown far enough to reach
    # the old address, so the original words were still sitting there unused.
    # What matters is that the COPY is right and the kept caller points at it.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
    import ab_image
    ab_image._resolve()
    img = bytearray(patched.read_bytes())
    st = bytearray(Path(stock.STOCK_IMAGE).read_bytes())
    for tag, pay in (('A', ab_records.PAYLOAD_A), ('B', ab_records.PAYLOAD_B)):
        recs, _ = ab_records.records(img, *pay)
        srecs, _ = ab_records.records(st, *pay)
        at = ab_image.PAY[tag]['spring'] + ab_image.SPRING_WORDS
        for host in sorted(ab_image.MOVED):
            off_in, n, fixups, want_calls, _pin = ab_image.RELOC[host]
            src = stock.p_spans(tag)[host][0] + off_in
            for i in range(n):
                got = ab_records.rd(img, ab_records.word_at(recs, 0, at + i))
                want = ab_records.rd(st, ab_records.word_at(srecs, 0, src + i))
                if i in fixups:
                    want = want - src + at
                assert got == want, (tag, host, f'copy word {i} at P:{at + i:05x}',
                                     f'{got:06x} != {want:06x}')
            callers = [k for _o, cs in stock.CROSS_ENTRIES[host] for k in cs
                       if k not in harvest]
            found = 0
            for a in range(0, 0x2200):
                try:
                    w0 = ab_records.rd(img, ab_records.word_at(recs, 0, a))
                    w1 = ab_records.rd(img, ab_records.word_at(recs, 0, a + 1))
                except BaseException:
                    continue
                if w0 in (0x0bf080, 0x0af080) and w1 == at:
                    owner = next((k for k, (sa, sn) in stock.p_spans(tag).items()
                                  if sa <= a < sa + sn), None)
                    if owner not in harvest:
                        found += 1
            assert found == want_calls, (tag, host, 'live callers pointing at the copy',
                                         found, want_calls)
            old_hits = sum(1 for a in range(0, 0x2200)
                           if _reads(img, recs, a) == src
                           and (lambda o: o is not None and o not in harvest)(
                               next((k for k, (sa, sn) in stock.p_spans(tag).items()
                                     if sa <= a - 1 < sa + sn), None)))
            assert old_hits == 0, (tag, host, 'a kept caller still points at the original')
            print(f'PASS payload {tag}: {host} +0x{off_in:x} ({n} words) copied to '
                  f'P:{at:05x} with {len(fixups)} address fixed, and all '
                  f'{want_calls} kept caller(s) ({", ".join(callers)}) point at the copy',
                  flush=True)
            at += n

    # Every given-up reverb dispatches to the null stub, on both cores.
    stubs = {'A': (0x7C8, 0x7C9), 'B': (0x588, 0x589)}
    for tag, pay in (('A', ab_records.PAYLOAD_A), ('B', ab_records.PAYLOAD_B)):
        recs, _ = ab_records.records(img, *pay)
        for key in given:
            eid = registry.by_key(key).menu.fx2_id
            for table, stub in ((0x215, stubs[tag][0]), (0x235, stubs[tag][1])):
                got = ab_records.rd(img, ab_records.word_at(recs, 1, table + eid))
                assert got == stub, (tag, key, f'X:{table + eid:05x}', f'{got:06x}',
                                     'a given-up reverb still dispatches at its own code')
            print(f'PASS payload {tag}: {key} (id 0x{eid:02x}) dispatches to the null stub '
                  f'{stub:05x} -- an old Part naming it runs a passthrough', flush=True)

    # And it BEHAVES as the stub: the same passthrough for every given-up id,
    # nothing like the reverb it replaced, and far too few instructions to be
    # either a reverb or one of our engines.
    #
    # ⚠️ THE STUB PASSES AUDIO, IT DOES NOT MUTE. "Renders nothing" was the
    # first thing this gate asserted and it is wrong -- 67 instructions per 16
    # samples is a copy, which is the point: an old Part naming SPRING REV
    # should sound dry, not silent.
    stubbed = {}
    for key in given:
        row, samples = br.run(registry.by_key(key), mems['patched'], f'stubbed-{key}',
                              blocks, 2, False, inputs=inputs, positions=[0, 4], extra=extra)
        _, was = br.run(registry.by_key(key), mems['stock'], f'stock-plain-{key}',
                        blocks, 2, False, inputs=inputs, positions=[0, 4], extra=extra)
        peak = max(c['peak_block'] for c in row['cores'])
        assert peak < 200, (key, peak, 'too much code for the null stub')
        assert samples != was, (key, 'this id still renders the stock reverb')
        assert any(v for track in samples for v in track), (key, 'the stub muted the track')
        stubbed[key] = samples
        print(f'PASS {key}: the stub passes audio in {peak} instructions/16 samples, '
              f'and is not the stock reverb', flush=True)
    if len(stubbed) > 1:
        first, *rest = stubbed
        for key in rest:
            assert stubbed[key] == stubbed[first], (key, first, 'two stubbed ids differ')
        print(f'PASS every given-up id renders the same passthrough', flush=True)


if __name__ == '__main__':
    main()
