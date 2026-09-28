"""stopguard -- stock 1.40C, plus a confirmation on the panel's STOP key.

Every one of the fourteen stock FX2 effects, exactly as `restock` lists
them, and nothing placed on the DSP at all. The only change to the running
firmware is the STOP key and a new PERSONALIZE row, CONFIRM STOP (MST).

This remix carries the module alone, so a failure is the module's rather
than a neighbour's. `the-passenger` is the one to flash: it carries this and
the scales together.
"""

from remix.schema import Remix

REMIX = Remix(
    name="stopguard",
    doc="Stock 1.40C + a YES/NO guard on the STOP key while master.",
    modules=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV",
             "STOP GUARD"),
    fallback="NONE",
)
