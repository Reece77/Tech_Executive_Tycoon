"""Stream `space` (id 68, ADR-0013): the one place M40 draws.

Keys (families): `(0, year)` rivals' growth a year after 2025 (drawn at `space.start`'s turn, a
year ahead) and `(0, 0)` the debris rule's month (drawn once at `space.start`); `(1, product_id,
flight)` a flight's failure (a vehicle line's nth flight) and `(1, 0, constellation_id, n)` a
bought launch's (n the constellation's own launch this month); `(2, region_index, company_id)` a
licence's decision in a month; `(3, n)` the grounding's length after a failure (n the vehicle's
failures) and an event answer's draw."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

WORLD, FLIGHT, LICENCE, AFTER = 0, 1, 2, 3  # tunable-exempt: key families
STREAM: Final = "space"


def gen(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "space", family, *key)
