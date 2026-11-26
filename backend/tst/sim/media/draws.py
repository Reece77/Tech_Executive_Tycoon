"""Stream `media` (id 76, ADR-0013): the one place M55 draws.

Keys (families): `(0, title id)` a title's audience at release (never stored before it); `(1,
person id, title id, n)` a creative lead's reaction to a title's n-th overrule, cut or move; `(2,
region index, year)` a region's seeded strike and divest-or-ban law after 2025; `(3, 0, year)` a
format era's arrival, `(3, 1, year)` a console generation's, `(3, 2, year, category index, region
index)` a market's yearly growth, `(3, 3, year)` ad spend's; `(4, year, n)` the n-th creative lead
on offer that year; `(5, product id, year)` a rival social line's move to a new format."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

AUDIENCE, REACTION, REGION, WORLD, LEAD, RIVAL = 0, 1, 2, 3, 4, 5  # tunable-exempt: key families
ERA, GENERATION, GROWTH, ADS = 0, 1, 2, 3  # tunable-exempt: WORLD's sub-families
STREAM: Final = "media"


def gen(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, STREAM, family, *key)
