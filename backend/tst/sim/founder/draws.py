"""The one call site of stream `personal` (id 53; ADR-0013, M26): every draw about the
founder's own investments, keyed by a tag and the record it is about."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

TRADE: Final = 0  # tunable-exempt: key (0, trade id): an insider trade's investigation
CONFLICT: Final = 1  # tunable-exempt: key (1, stake id): a concealed conflict's discovery
OFFICE: Final = 2  # tunable-exempt: key (2,): the family office's monthly noise
MANAGER: Final = 3  # tunable-exempt: key (3,): the family office's manager


def personal_draws(rng: RngFactory, turn: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "personal", *key)
