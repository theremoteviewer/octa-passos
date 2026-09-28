"""notescale -- stock 1.40C plus SCALE and ROOT on MIDI NOTE SETUP.

Deliberately without the arp scale expansion and without the STOP guard:
this remix carries the one module, so a failure is its own.
"""

from remix.schema import Remix

REMIX = Remix(
    name="notescale",
    doc="Stock 1.40C + SCALE and ROOT on the two empty NOTE SETUP cells.",
    modules=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV",
             "NOTE SCALE"),
    fallback="NONE",
)
