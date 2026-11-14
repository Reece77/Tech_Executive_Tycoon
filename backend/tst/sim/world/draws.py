"""Stream `world` (id 57, ADR-0013): the one place the living world draws.

Keys: `(0, *rival_key)` a chain company's December capex; `(1, region_index)` a region's cycle;
`(2,)` the global shock; `(3, *rival_key, 0)` a rival's quarter of deals and
`(3, *rival_key, 1)` its month's bid for the player; `(4, *rival_key, 0)` a chain company's
executives' names and `(4, *rival_key, 1)` its CEO changing."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

CAPEX, CYCLE, GLOBAL, DEALS, PEOPLE = 0, 1, 2, 3, 4  # tunable-exempt: key families (ADR-0013)
DEAL_TAG, BID_TAG = 0, 1  # tunable-exempt: the last key part of family 3
STREAM: Final = "world"


def gen(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "world", family, *key)
