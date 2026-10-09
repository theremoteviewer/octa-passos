# md-kit — the drum machine plus USB audio out

The starting point for the Machinedrum machine work: repeat98's **ANALOG BD**
native source machine (switchable 808/909, its own SRC and SRC SETUP pages,
upstream of stock AMP and both FX slots) with markandrus's **USB MIDI** and
**USB AUDIO OUT TRACKS MAIN CUE** — twenty 24-bit channels at 44.1 kHz on the
host, tracks 1–16 post-FX pre-fader, MAIN 17–18, CUE 19–20 (MAIN/CUE Bryan T).

Thirteen of the fourteen stock effects are listed, on both choosers where
stock has them. **SPRING REV is the one thing given up**: it is on neither
chooser, so its 1,063 words on each payload are where the BD's engines are
placed. PLATE REV and DARK REV stay stock — including the 35-word helper they
share that lies inside SPRING's region, which the build copies from the user's
own image into the reserved end of the region and retargets
(`verify_analog_bd_reverbs.py`).

The USB units are ColdFire patches on the DRAM platform: they cost the DSP
nothing, which is why both fit alongside the machine without a second donor row.

Build: `make check REMIX=md-kit`, then `make image REMIX=md-kit BUILD=<n>`.

## What the build reports

```
analog bd A: glue + 808/909 1000 words at P:01252 (SPRING REV's region, 1063)
             X:02840..036ff tables + voices (voice 0 at 03100)
analog bd B: glue + 808/909 1000 words at P:01012 (SPRING REV's region, 1063)
```

One machine family = **1,000 P words = one SPRING REV**, on both payloads.
That is the unit the rest of the machine plan is costed in
(`out/md-machines/NOTES.md` section 8).

## Status

**Unflashed.** Built and gated under the port, 2 Oct 2026. The two halves have
each run on hardware separately — ANALOG BD on Jesse's MK1 as an octamod.app
build, USB AUDIO OUT TRACKS MAIN CUE on Sam's MKII (image 64) and Tim's MKI
(OCTATRICK9) — but this combination has not. The cycle registry cannot price
it: ANALOG BD declares `pressure_blocker` because the registry sees it as a
ColdFire module and misses the DSP source engines, so acceptance reports
**blocked** rather than a misleading N/A. Its own benchmarks are in
[the module's CPU.md](../../modules/analog-bassdrum/CPU.md), in executed
instructions, which must not be added to the cycle budget.
