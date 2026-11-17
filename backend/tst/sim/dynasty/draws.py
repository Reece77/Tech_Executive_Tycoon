"""M37's stream, from one call site (ADR-0013; tests/unit/test_rng_call_sites.py): `dynasty`
(id 65), each key a leading family tag. Every draw is at January 2040 or later, so no game to
December 2039 ever makes one (formulas.md 52.5 target 1)."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

SERIES: Final = 0  # tunable-exempt: stream key tags (ADR-0013's table)
LEADER: Final = 1  # tunable-exempt: a stream key tag
MORTALITY: Final = 2  # tunable-exempt: a stream key tag
ENTRANT: Final = 3  # tunable-exempt: a stream key tag
# SERIES's second key part: which data series continues (52.2)
NODES: Final = 0  # tunable-exempt: a series tag (process-node successors)
CARBON: Final = 1  # tunable-exempt: a series tag (carbon's long-run level)


def gen(rng: RngFactory, turn: int, family: int, *keys: int) -> np.random.Generator:
    return rng.stream(turn, "dynasty", family, *keys)
