"""The one call site of stream `mna` (id 37; ADR-0013): every M&A draw is keyed by the
target's stable rival key (or the player's id) and a tag. Fixed per-target draws (value
range offset, hidden problems) use turn 0 of the master seed."""

from __future__ import annotations

import numpy as np

from tst.sim.rng import RngFactory


def mna_draws(rng: RngFactory, turn: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "mna", *key)


def fixed_draws(master_seed: int, *key: int) -> np.random.Generator:
    """A target's draws that never change: turn 0 of the master seed."""
    return mna_draws(RngFactory(master_seed), 0, *key)
