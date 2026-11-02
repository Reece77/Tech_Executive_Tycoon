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
        "founder": 7,  # no key: founder build at game start (M1a)
        "growth": 8,  # key (person_id,): monthly skill growth noise (M1a)
        "reveal": 9,  # key (observer_company_id, person_id): range centre offsets (M1a)
        "tags": 10,  # key (person_id,): monthly tag reveal rolls (M1b)
        "resign": 11,  # key (person_id,): monthly resignation roll (M1b)
        "retire": 12,  # key (person_id,): monthly retirement roll (M1b)
        "actions": 13,  # key (action_seq,): randomness inside a player action (M1b)
        "delegate": 14,  # key (person_id, n): randomness inside a delegate's action (M2a)
        "product_dev": 15,  # key (product_id,): monthly development noise (M3, ADR-0017)
        "finance": 16,  # key (safe_id,) or (round_id, firm_index): investors' answers (M4)
        "board": 17,  # key (seat_id,): generating a director (M4)
        "rival_spawn": 18,  # key (category_index,): founding rival startups (M5, 15.4)
        # key (approach_id,): an employee's answer to a rival approach (M5, 15.6);
        # (approach_id, 1): whom a new approach targets (M10d, product manager 2026-11-02)
        "poach": 19,
        "entrants": 20,  # key (entrant_index,): a scheduled entrant's people (M8, 18.7)
        "macro": 21,  # key (indicator_index,), (99,) for downturns: indicators after 2025 (M10)
        "rival_region": 22,  # key (startup_id,): a rival startup's founding region (M9, 19.6)
        "misc": 99,
    }
)

MAX_SEED: Final = 2**64 - 1


class RngFactory:
    """Hands out independent generators keyed by (turn, stream name, *entity keys).

    ADR-0013: every call site uses its own stream name, and draws that belong to one entity
    pass that entity's id as a key, so they do not depend on iteration order.
    """

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

    def stream(self, turn: int, name: str, *key: int) -> np.random.Generator:
        if name not in STREAM_IDS:
            raise UnknownStreamError(f"unknown RNG stream {name!r}; add it to STREAM_IDS")
        if turn < 0:
            raise InvalidSeedError(f"turn must be >= 0 for an RNG stream, got {turn}")
        for part in key:
            if isinstance(part, bool) or not isinstance(part, int) or part < 0:
                raise InvalidSeedError(f"stream keys must be non-negative ints, got {key!r}")
        seq = np.random.SeedSequence(
            entropy=self._master_seed, spawn_key=(turn, STREAM_IDS[name], *key)
        )
        return np.random.Generator(np.random.PCG64(seq))
