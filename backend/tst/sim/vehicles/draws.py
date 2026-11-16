"""Stream `vehicles` (id 63, ADR-0013): the one place M38 draws.

Keys (families): `(0, region_index)` a region's EV-share speed (at `vehicles.start`) and, each
December from it, `(0, region_index, 1 + level_index)` its approval of a level; `(0, n_regions)`
the game-wide learning rate (drawn once, at `vehicles.start`); `(1, product_id)` a product's
autonomy incidents in a month; `(2, facility)` a cell plant's overrun at its order and its yield
noise in later months; `(3, *rival key)` a rival's December model refresh."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

WORLD, INCIDENT, CELL_PLANT, RIVAL = 0, 1, 2, 3  # tunable-exempt: key families (ADR-0013)
STREAM: Final = "vehicles"


def gen(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, STREAM, family, *key)
