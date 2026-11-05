"""Stream `press` (id 40, ADR-0013): the one call site (29.4). Keys: (company_id, n) for the
player's draws, a rival's stable key for a rival's statements."""

from __future__ import annotations

import numpy as np

from tst.sim.rng import RngFactory


def press_gen(rng: RngFactory, turn: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "press", *key)
