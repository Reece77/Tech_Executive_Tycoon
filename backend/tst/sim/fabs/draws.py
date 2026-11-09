"""M21's stream, from one call site (ADR-0013; tests/unit/test_rng_call_sites.py): `fab` (id
54), each key a leading tag. Future nodes' months use stream `era_window` (id 31) at turn 0,
key (FUTURE_NODE_KEY + j,): appended after eras' indices so adding an era or a node moves no
other's month (38.1)."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

OVERRUN: Final = 0  # tunable-exempt: stream key tags (ADR-0013's table)
YIELD: Final = 1  # tunable-exempt: a stream key tag
FUTURE: Final = 2  # tunable-exempt: a stream key tag
LAG: Final = 3  # tunable-exempt: a stream key tag
GROWTH: Final = 4  # tunable-exempt: a stream key tag
FUTURE_NODE_KEY: Final = 1000  # tunable-exempt: era_window keys of future nodes start here


def fab_draws(rng: RngFactory, turn: int, tag: int, *keys: int) -> np.random.Generator:
    return rng.stream(turn, "fab", tag, *keys)


def node_window_draw(rng: RngFactory, j: int) -> float:
    """Future node j's one uniform: stream era_window at turn 0 (38.1, as 26.4), drawn by the
    eras' own call site at key FUTURE_NODE_KEY + j."""
    from tst.sim.research.levels import _window_draw

    return _window_draw(rng, FUTURE_NODE_KEY + j)
