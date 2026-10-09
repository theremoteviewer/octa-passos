#!/usr/bin/env python3
"""Render every core B row and every one of its six knobs to one WAV.

Not a gate -- `tools/harness/bdnoise.py` is the gate. This is what Jesse
listens to: each row's default hit, then each knob at its low and high end,
so "does this knob do anything" is answerable by ear as well as by the
0.02-of-peak bound the harness holds it to.

    python3 tools/scratch/pl_demo.py out.wav

The render is the engine's own output block -- the source seam, pre-FX and
pre-AMP -- through the same emulated DSP the gates use. It is not the unit's
output: no LPF, no track level, no effects.
"""
import struct
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/harness'))
import bdnoise as H                                            # noqa: E402

RATE = 44100
HIT = 0.42               # seconds per hit
GAP = 0.10


def hits(syms, knobs, tag, n=2):
    """`n` trigs, HIT seconds apart, as a mono float list."""
    nb = int(HIT * RATE / H.FRAMES)
    out = []
    for i in range(n):
        y, _ = H.render(syms, knobs, [0] + [None] * (nb - 1), f'{tag}_{i}')
        out += y
    return out


def main(dest):
    syms = H.build()
    pcm = []
    for name, _mid in H.ROWS:
        base = H.MACHINES[name]
        tag = name.replace(' ', '_')
        print(f'{name}: default', flush=True)
        pcm += hits(syms, base, f'd_{tag}')
        pcm += [0.0] * int(GAP * RATE)
        for i, label in enumerate(H.KNOBS[name]):
            for pos in (16, 112):
                k = list(base)
                k[i] = pos
                print(f'  {label} {pos}', flush=True)
                pcm += hits(syms, k, f'k_{tag}_{i}_{pos}', n=2)
                pcm += [0.0] * int(GAP * RATE)
        pcm += [0.0] * int(0.5 * RATE)
    peak = max(abs(v) for v in pcm) or 1.0
    # Normalise to -1 dBFS: the engines differ by 8 dB in level and the point
    # of the file is the knobs, not the balance.
    g = 0.891 / peak
    frames = b''.join(struct.pack('<hh', int(v * g * 32767), int(v * g * 32767))
                      for v in pcm)
    hdr = (b'RIFF' + struct.pack('<I', 36 + len(frames)) + b'WAVEfmt '
           + struct.pack('<IHHIIHH', 16, 1, 2, RATE, RATE * 4, 4, 16)
           + b'data' + struct.pack('<I', len(frames)))
    pathlib.Path(dest).write_bytes(hdr + frames)
    print(f'wrote {dest}: {len(pcm) / RATE:.1f} s, peak {peak:.3f} before '
          f'normalising')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'pl_demo.wav')
