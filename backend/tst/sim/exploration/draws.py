"""M18's two streams, each from one call site (ADR-0013; tests/unit/test_rng_call_sites.py):
`geology` for the hidden truths drawn as at turn 0, `exploration` for every later draw. Each
key begins with a tag naming its use (ADR-0013's table)."""

from __future__ import annotations

import numpy as np

from tst.sim.rng import RngFactory

GEOLOGY_TURN = 0  # tunable-exempt: deposits are drawn as at January 2010 whatever the start


def geology_draws(rng: RngFactory, *key: int) -> np.random.Generator:
    return rng.stream(GEOLOGY_TURN, "geology", *key)


def exploration_draws(rng: RngFactory, turn: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "exploration", *key)
