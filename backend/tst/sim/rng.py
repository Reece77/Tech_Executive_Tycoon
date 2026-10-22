"""Derived, seeded random streams (ADR-0002).

Each save stores one 64-bit master seed. A generator for a given turn and subsystem is
derived from it on demand, so no generator state is ever persisted, and adding a stream
never changes the draws of an existing one.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

import numpy as np

from tst.sim.errors import InvalidSeedError, UnknownStreamError

# Append-only. Never renumber or reuse an id: that would change every save's outcomes.
STREAM_IDS: Final = MappingProxyType(
    {
        "people_gen": 1,
        "hiring": 2,
        "morale": 3,
        "market": 4,
        "rivals": 5,
        "events": 6,
        "misc": 99,
    }
)

MAX_SEED: Final = 2**64 - 1


class RngFactory:
    """Hands out independent generators keyed by (turn, stream name)."""

    __slots__ = ("_master_seed",)

    def __init__(self, master_seed: int) -> None:
        if isinstance(master_seed, bool) or not isinstance(master_seed, int):
            raise InvalidSeedError(f"master seed must be an int, got {type(master_seed).__name__}")
        if not 0 <= master_seed <= MAX_SEED:
            raise InvalidSeedError(f"master seed must be in 0..2**64-1, got {master_seed}")
        self._master_seed = master_seed

    @property
    def master_seed(self) -> int:
        return self._master_seed

    def stream(self, turn: int, name: str) -> np.random.Generator:
        if name not in STREAM_IDS:
            raise UnknownStreamError(f"unknown RNG stream {name!r}; add it to STREAM_IDS")
        if turn < 0:
            raise InvalidSeedError(f"turn must be >= 0 for an RNG stream, got {turn}")
        seq = np.random.SeedSequence(entropy=self._master_seed, spawn_key=(turn, STREAM_IDS[name]))
        return np.random.Generator(np.random.PCG64(seq))
