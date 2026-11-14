"""Stream `platforms` (id 58, ADR-0013): the one place the platforms draw.

Keys: `(0, platform id, region index)` developers' attractiveness noise; `(1, platform id,
product id)` a gatekeeper's monthly review of a product, `(..., 1)` an appeal's or regulator's
answer and `(..., 2)` an appeal's length; `(2, platform id)` a rival owner's fee move and
`(2, platform id, region index)` a rival store opening; `(3, 0, year)` December's standards
contests and `(3, 1, standard id)` a contest's category and formats; `(4, company id, product
id)` a rival OEM's December platform choice."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

NOISE, REVIEW, OWNER, STANDARDS, OEM = 0, 1, 2, 3, 4  # tunable-exempt: key families (ADR-0013)
ANSWER, LENGTH = 1, 2  # tunable-exempt: the last key part of family 1
STREAM: Final = "platforms"


def gen(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "platforms", family, *key)
