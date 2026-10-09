# Remixes

A remix is a named selection of modules; `make image REMIX=<name> BUILD=<n>` builds it into a card-flashable image from your own OS 1.40C. Each remix is a directory here: `remix.py` is the selection, `README.md` says what is in it, where it has run and how to flash it. This index is rendered from the selections (`make docs`).

- What to install first (the Xcode Command Line Tools, Homebrew, Python 3.10+, `cmake`, `uv`) and every step to a flashed unit: [BUILDING.md](../docs/guide/BUILDING.md).
- Composing your own: [REMIXER.md](../docs/guide/REMIXER.md).
- The remixes that carry one module for its gates: [test/](test/README.md).

## The rig

| remix | contains | proof |
|---|---|---|
| [`bottleservice`](bottleservice/README.md) | The rig + USB MIDI + USB AUDIO OUT MASTER (T8 to the computer) + USB AUDIO IN CD (the computer onto inputs C/D) + Octakit. | on hardware: Sam's MKII, image 88, 27 Sep 2026 |

## Firmware mods on the stock effects

| remix | contains | proof |
|---|---|---|
| [`analog-bassdrum`](analog-bassdrum/README.md) | Analog BD source machine, switchable 808/909, stock AMP and FX. | port-gated: source/UI under the port; earlier ANALOGBD1 auditioned on MK1, current revision unflashed |
| [`md-kit`](md-kit/README.md) | ANALOG BD (808/909 source machine) + USB MIDI + USB AUDIO OUT TRACKS MAIN CUE, on the stock effects less SPRING REV. | port-gated: unflashed; built and gated under the port, 2 Oct 2026. ANALOG BD ran on Jesse's MK1 as an octamod.app build; USB AUDIO OUT TRACKS MAIN CUE on Sam's MKII (image 64) and Tim's MKI (OCTATRICK9) |
| [`octatrick`](octatrick/README.md) | SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP + TUNER + USB MIDI + USB AUDIO (20 channels out, 4 in onto A-D) on the stock effects less SPATIALIZER. | on hardware: Tim's MKI, test build 3.0 b40 (this selection at BUILD 40), 29 Sep 2026: USB AUDIO IN brings the Mac's audio onto the inputs in a one-minute check (long runs not yet tested). The same four modules with the 26 Sep USB AUDIO (out only) ran on the same MKI through the 2.9 test builds; the tuner works on test build 3.0 b40 (UP + TEMPO); the last two 2.9 fixes are not yet confirmed on hardware |
| [`ok-ms`](ok-ms/README.md) | Octakit + MIDI SCENES on the stock effects: the two mods alone. | on hardware: midisc's author's unit, 14 Sep 2026 (OKMS2) |
| [`passos-pl`](passos-pl/README.md) | PassOS (36-scale note quantiser + STOP guard) + an eleven-row drum machine of six mechanisms, six working parameters each + USB MIDI + 20-channel USB audio, on the stock effects less SPRING, DARK, COMPRESSOR, LO-FI, DJ EQ and COMB. | port-gated: unflashed. PassOS 1.0 (NOTE SCALE + STOP GUARD) ran on Jesse's MK1, 28 Sep 2026; ANALOG BD's 808/909 and the Machinedrum hats ran on the same MK1 as passOS MD test 03-05, 3-5 Oct 2026; USB AUDIO OUT TRACKS MAIN CUE on Sam's MKII (image 64) and Tim's MKI (OCTATRICK9). The percussion engines and the resonator bank are unflashed and have no matched reference |
| [`the-passenger-md`](the-passenger-md/README.md) | PassOS (36-scale note quantiser + STOP guard) + ANALOG BD + USB MIDI + 20-channel USB audio, on the stock effects less SPRING REV. | port-gated: unflashed as a combination. PassOS 1.0 (NOTE SCALE + STOP GUARD) ran on Jesse's MK1, 28 Sep 2026; ANALOG BD ran on the same MK1 as an octamod.app build; USB AUDIO OUT TRACKS MAIN CUE on Sam's MKII (image 64) and Tim's MKI (OCTATRICK9); ANALOG BD + USB together as md-kit on Jesse's MK1, 2 Oct 2026 |

Never share a built image: it contains Elektron's OS.
