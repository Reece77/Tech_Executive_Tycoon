"""Stream `power` (id 60, ADR-0013): the one place M32 draws.

Keys (families): `(0, region_index, 0)` a region's grid outage this month and `(0, region_index,
1)` its yearly path (January after 2025); `(1, facility)` a plant's overrun in its order month
and its forced-outage draw in later months; `(2, entry)` a queued project's connection; `(3,
type_index)` the game-wide learning rates and SMR era; `(4, chain index)` a rival foundry's
December plant decision."""

from __future__ import annotations

import numpy as np

from tst.sim.rng import RngFactory


def gen(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "power", family, *key)
