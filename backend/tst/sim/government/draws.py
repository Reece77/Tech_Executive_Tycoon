"""Stream `defence` (id 69, ADR-0013): the one place M44 draws.

Keys (families): `(0, government_index, year)` a government's seeded budget growth and tenders for
a year (drawn in January); `(1, tender_id, round)` rivals' bids, award tie-breaks and protests at
an award; `(2, person_id)` a staff clearance at its request, `(2, 0, facility_id)` a facility's;
`(3, contract_id, month)` a contract's overrun and task orders in a month; `(4, company_id, turn)`
staff reactions to a defence award."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

BUDGET, AWARD, CLEARANCE, DELIVERY, REACTION = 0, 1, 2, 3, 4  # tunable-exempt: key families
STREAM: Final = "defence"


def gen(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "defence", family, *key)
