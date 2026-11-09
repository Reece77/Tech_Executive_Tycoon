"""M20's stream, from one call site (ADR-0013; tests/unit/test_rng_call_sites.py): `refining`
(id 51), each key a leading tag and the facility id."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

OVERRUN: Final = 0  # tunable-exempt: stream key tags (ADR-0013's table)
INCIDENT: Final = 1  # tunable-exempt: a stream key tag
CURB: Final = 2  # tunable-exempt: a stream key tag
LEGAL: Final = 3  # tunable-exempt: a stream key tag


def refining_draws(rng: RngFactory, turn: int, tag: int, facility_id: int) -> np.random.Generator:
    return rng.stream(turn, "refining", tag, facility_id)
