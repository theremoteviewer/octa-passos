# PassOS

Custom firmware for the Octatrack MK1 — the passenger mod. Built on
[octabam](https://github.com/sambanks/octabam), which composes a card image
out of your own copy of Elektron's OS 1.40C.

**PassOS 1.0** — stock 1.40C, a scale system, and a STOP guard. Every one of
the fourteen stock FX2 effects is untouched and nothing is placed on the DSP,
so the unit sounds exactly as it always did.

## Two rules

**No one gets a built image.** An image contains Elektron's OS. Share this
repository; everyone builds their own from a copy of 1.40C they downloaded
themselves. That is the whole design of octabam and it is not negotiable
here either.

**No Elektron byte in the repository.** No image, no slice, no `.syx`, in a
commit or on an issue. `out/` and `downloads/` are gitignored for this
reason — check before you add anything.

## What it does

### The scale system

MIDI NOTE SETUP's two empty cells become **SCL** and **ROT**: the Digitone
II's thirty-six scales against twelve roots, in Appendix E order, with
CHROMATIC at 0 as the off state. The blank box to the left of the row draws
the scale's name over a keyboard, a dot on every note of the scale and a tick
under the root.

The NOTE page's four note cells then reach only notes of that scale. NOT2–4
are offsets biased by 64 from the track's own NOTE, so they snap the note
they *sound*, and an offset of zero stays reachable as OFF. Changing SCL or
ROT moves those four onto the new scale.

Every note the track emits is snapped at emit time as well, so trigs written
before the scale was chosen play in it without being rewritten — their stored
notes are left alone on purpose, because no change of scale could give them
back.

The ARP page's KEY selector is switched off: the decode it fed now reads SCL
and ROT, so it changed nothing, and a control that changes nothing is worse
than no control.

Scale derivations are checked against the Digitone II's own behaviour by
`modules/scales/dn2_scales.py --check`, which asserts mode-family closure for
every family and, note for note, nine scales read off a real DN2.

### RiDylan mode

A new PERSONALIZE row. Ticked, with this unit running as clock master, STOP
and PLAY ask before they stop the sequencer. The setting survives a power
cycle.

## Building

You need your own 1.40C, the toolchain, and a CompactFlash card. See
`docs/remixer/FLASHING.md` and the octabam README first — then:

    make setup
    make os
    make image REMIX=the-passenger BUILD=<n>

which writes `out/OCTATRACK_PassOS1.0.bin` and the matching `.syx`. The panel
reads `PASSOS 1.0`; the boot font carries no lowercase glyphs, which is why
the on-device string is upper case while the file name is not.

Read `docs/remixer/FLASHING.md` before you write either to hardware, and have
a **5-pin DIN MIDI interface** working before you flash anything. USB-MIDI to
the Octatrack's own port does not work for OS upgrades, and it is the only
recovery path if a flash goes wrong.

## Credit

octabam is sambanks'. The arpeggiator research that started the scale work is
Maxolydian's (octamax); nothing here is copied from it — octamax carries no
licence at all, so every fact used was reimplemented from documented
behaviour. `modules/scales/NOTES.md` is the running research record,
including the measurements that turned out to be wrong and why.
