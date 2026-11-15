"""Stream `regulation` (id 62, ADR-0013): the one place regulation draws.

Keys: `(0, regulator index, *company stable key)` a regulator's monthly opening draw on a company;
`(1, case id, k)` a case's draws, `k` = STAGE_LENGTH (a stage's length, drawn when it starts),
OUTCOME (a ruling's or an appeal's outcome and the chance inside its shown range), FINE (the
fine's gravity), STRUCTURAL (whether a ruling is a structural order), RIVAL (a rival's answer);
`(2, order id, k)` a structural order's appeal length and outcome. Draws are never stored."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

OPEN, CASE, ORDER = 0, 1, 2  # tunable-exempt: key families (ADR-0013)
STAGE_LENGTH, OUTCOME, FINE, STRUCTURAL, RIVAL = 0, 1, 2, 3, 4  # tunable-exempt: last key parts
STREAM: Final = "regulation"


def gen(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "regulation", family, *key)
