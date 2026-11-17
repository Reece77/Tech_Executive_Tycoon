"""Stream `robotics` (id 66, ADR-0013): the one place M39 draws.

Keys (families): `(0, region_index, year)` a region's installations growth for a year after 2025
(drawn each January from `robotics.start`), and `(0, n_regions)` the home humanoid window (drawn
once, at the era's arrival); `(1, zone_id, city_index)` a robotaxi zone's incidents in a month;
`(2, region_index, zone_id)` a zone's permit decision in a month; `(3, operator_index)` a rival
operator's December entry into a new city (2026+)."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

WORLD, INCIDENT, APPROVAL, RIVAL = 0, 1, 2, 3  # tunable-exempt: key families
STREAM: Final = "robotics"


def gen(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, STREAM, family, *key)
