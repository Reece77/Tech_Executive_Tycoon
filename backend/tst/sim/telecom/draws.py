"""Stream `telecom` (id 73, ADR-0013): the one place M53 draws.

Keys (families): `(0, 0, year, region_index)` a region's subscription growth for a year after 2025;
`(0, 1)` 6G's first month (drawn once at `telecom.start`); `(0, 2, area_index, n)` an area's nth
seeded auction (its month, band, blocks and bidders); `(0, 3, area_index)` a seeded ban; `(1,
auction_id)` an auction's rivals' values and demands when it runs (never stored); `(2, deal_id)`
nothing yet (merger reviews use M14's stream)."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

WORLD, AUCTION = 0, 1  # tunable-exempt: key families
GROWTH, G6, SCHEDULE, BAN = 0, 1, 2, 3  # tunable-exempt: WORLD's sub-families
STREAM: Final = "telecom"


def gen(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, STREAM, family, *key)
