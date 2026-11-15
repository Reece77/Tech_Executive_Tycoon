"""Stream `equipment` (id 61, ADR-0013): the one place M33 draws.

Keys: `(0, generation index)` a quarter's allocation jitter, one uniform an open order in id
order; `(1, company id, stage index, attempt)` a programme stage's draws at its start (work,
overrun, success) and at success (throughput, yield cut); `(2, foundry index)` a Chinese
foundry's own EUV-class tools' month, drawn once at turn 0."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

ALLOCATION, PROGRAMME, CHINA = 0, 1, 2  # tunable-exempt: key families (ADR-0013)


def gen(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "equipment", family, *key)


STREAM: Final = "equipment"
