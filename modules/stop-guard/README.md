# STOP GUARD

A PERSONALIZE row — **RiDylan mode** — that makes the panel's STOP *and
PLAY* keys ask before they stop the sequencer.

Ticked, with the unit running as the clock master and the sequencer
playing, either key draws the firmware's own YES/NO screen:

```
        CONFIRM STOP
    OCTATRACK IS MASTER
    AND IS PLAYING.
    STOP PLAYBACK?
```

YES stops. NO leaves it playing. Unticked, slaved to an external clock, or
already stopped, the key is stock's.

The setting survives a power cycle.

## Where it sits

| what | where |
| --- | --- |
| the STOP key | `0x4004acce`, the STOP handler's press-only dispatch |
| the PLAY key | `0x40061778`, the PLAY handler's first instruction |
| the row | the three PERSONALIZE arrays, relocated 16 → 17 entries |
| the count | `0x40068fb2`, `moveq #15` → `moveq #16` |
| the setting | live `0x800000a8`, mirror `0x100fff38` |

### The key

`0x4004aca4` is the STOP key's handler. Both paths above `0x4004acce`
return on a key *release*, so `0x4004acce` is reached only on a press —
which is why the detour goes there and not at the stop routine itself. The
stop routine `0x400a10c8` has **twenty-six** callers (MIDI transport, the
loader, the recorder, the arranger); guarding it would guard all of them.
This guards one call site.

What the stub replaces is stock's two-way call:

```
4004acce  4ab9 460d1aec   tst.l   $460d1aec
4004acd4  6708            beq     $4004acde
4004acd6  4eb9 400a14a4   jsr     $400a14a4
4004acdc  6006            bra     $4004ace4
4004acde  4eb9 400a10c8   jsr     $400a10c8
4004ace4  ...             the handler continues, reading %d2
```

`sg_key` replays exactly that pair when the guard does not apply, and
returns to `0x4004ace4` in every case. `%d2` (the pressed flag) is not
touched.

### The row, and why it goes at index 15

PERSONALIZE draws a contiguous range `0..count-1` from three parallel
arrays of sixteen: labels `0x400b2a34`, getters `0x400b2a74`, setters
`0x400b2ac0`. The count is built at `0x40068fa8`:

```
tst.l 0x46c8d18c / sne %d0 / mvs.b %d0,%d0 / moveq #15,%d1 / sub.l %d0,%d1
```

— 15 with the flag clear, 16 with it set. That flag is written by a GPIO
probe at `0x4001f8cc`; the model with it clear therefore never sees the
*last* row, LED BRIGHTNESS.

So a seventeenth row appended after LED BRIGHTNESS would be invisible on
that model. The build's `TableGrow` copies the first **fifteen** stock
entries, then this row, then LED BRIGHTNESS — and the count becomes 16 or
17. Whichever model hides a row still hides LED BRIGHTNESS.

Five sites reach the arrays and all five are repointed. One of them is
`move.l #0x400b2a34,%d5`, not a `lea` — the repo's documented trap, and the
reason `TableGrow.refs` names operand addresses rather than instructions.

### Why the setting persists

This is the part worth reading, because it was the open question.

Stock's PERSONALIZE settings are longs in a live block at `0x80000070` and
copies in a non-volatile block at `0x100fff00`. Nothing reads the copies
back by literal address — which is what made the mechanism look untraced —
because the restore is a **bulk copy**:

* `0x4001f218` sums 252 sign-extended bytes from `0x100fff04`, each XORed
  with its one-based index, plus `0x202`. `0x4001f23c` stores that sum at
  `0x100fff00`.
* `0x100fff04` holds the magic `"ANDY"`; `0x100fff0e` a version, currently
  36.
* At boot `0x4001f340` recomputes the sum. On a match it calls
  `0x40020898(0x80000070, 0x100fff00, 100)` — a plain `memcpy`. On a
  mismatch `0x4001f298` erases `0x100fff04..0x10100003`, writes the
  defaults, restamps and copies.

So every setting is one offset `k` in two blocks — live `0x80000070 + k`,
mirror `0x100fff00 + k` — verified one setter at a time, all sixteen. Any
long inside *both* the 100-byte copy and the 252-byte checksum persists by
the same mechanism, and needs no new machinery.

`tools/verify/verify_stopguard.py` checks all of that against the image,
including the part a `Poke` cannot: that `0x800000a8` and `0x100fff38`
appear nowhere in it.

The rows take live `0x8c 0x90 0x94 0x98 0x9c 0xa0 0xa4 0xac 0xb0 0xb8 0xbc
0xc0 0xc4 0xc8 0xcc 0xd0`; `0xb4` belongs to a seventeenth setting edited
from elsewhere (`0x400687f8`). **`0x800000a8` / `0x100fff38` is referenced
by nothing at all** — no literal anywhere in the image's 1,112,560 bytes,
and outside both bulk clears (one stops below `0x100fff00`, the other
starts above `0x100fff04`).

No checksum call is needed in the setter: the PERSONALIZE edit dispatcher
calls the row's setter and then jumps to `0x4001f23c` itself
(`0x40069074`), for every row.

**This also explains the old dispute.** `0x80000070 + 100 = 0x800000d4`, so
`0x800000d4`, `0xd8` and `0xdc` are one long *past* the copy: they are
never restored, and a boot — or any call to `0x4001f340`, which the panel
makes at `0x4004abf0` — overwrites the block below them. A live word
without its mirror has the same problem. The report that those words
"failed on HW" is consistent with that, and is not evidence against
`0x800000a8`, which is inside the copy and has a mirror.

### Master

`0x80000028` bit 0 is CLOCK RECEIVE and bit 1 is CLOCK SEND; `0x80000029`
is TRANSPORT RECEIVE and `0x8000002a` TRANSPORT SEND. Those four are named
by the firmware's own config writer at `0x400884a4`, which pushes each
value beside its `MIDI_CLOCK_SEND=%d` string — so this is read off the
image, not inferred from the panel.

The guard applies when **CLOCK RECEIVE is off**: the unit is not being
driven by anything else. TRANSPORT RECEIVE is deliberately not consulted;
if you want the guard while slaved, say so and it is one instruction.

## What is measured, and what is not

Measured, against the user's own 1.40C: every `expect` in `manifest.py`,
the three arrays and all five reach sites, the count expression, the
getter and setter contracts (taken instruction for instruction from row 7,
DIS. STOP-STOP ARM, `0x40068d50`/`0x40068d90`), the glyph pair
(`0x400b5e90` ticked, `0x400b5e8e` empty), the popup's five arguments and
its `0`-means-yes handler (FORMAT CARD, `0x40069354`), the popup's busy
guard, the transport long `0x800065b8`, the two clock bits, and the whole
settings-block mechanism above. Every instruction form used has precedent
in the stock image at the address named beside it in the source.

Inferred: that `0x46c8d18c` distinguishes MKI from MKII. It is a GPIO
probe and its only effect here is which of the two counts a unit shows;
the row order keeps the hidden row hidden whichever way round it is.

**Not measured: any of it running.** No hardware, no emulator pass, and
the popup has never been drawn. This is a first draft.

### PLAY

PLAY while the sequencer is stopped starts it, and is never guarded. PLAY
while it runs is the press that ends a set, so it asks.

Key `0x28`'s press entry is `0x40061778` in both keymap tables
(`0x400c0056` and `0x400c063a`), and neither table entry is rewritten —
the handler's own first instruction is the hook, so the stub also covers
anything else that calls it.

Both keys share one answer handler. A confirmed PLAY press therefore
**stops**, rather than reproducing whatever the stock PLAY handler would
have done with the modifier and latch state as it stood at press time —
state (`0x460d1726`, `0x460d172a`, `0x460d1de4`) that a modal popup has
already outlived by the time anyone answers. The screen says STOP
PLAYBACK?, and that is what YES does. Reproducing the stock branch exactly
would mean calling `0x40061778` again from the callback on a faked frame,
since it writes a command back into its own argument slot before
tail-jumping to `0x4007e998` — possible, but it would be reproducing stale
state rather than honest behaviour.

## Known edges

* With the guard on and a screen already up, STOP is swallowed rather than
  passed through. The guard is on; a second bump must not be the one that
  ends the set.
* The popup is the stock YES/NO screen, so NO — not "any other key" —
  dismisses it.
* A stop from MIDI, the arranger or the loader is not guarded. Only the
  two keys are.
* A confirmed PLAY press stops rather than pauses — see above.
