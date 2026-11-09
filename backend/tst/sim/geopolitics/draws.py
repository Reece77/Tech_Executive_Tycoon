"""Stream `geopolitics` (id 55, ADR-0013): the one call site. Key families: (0,) the month's
tension draws after 2025; (1, licence id) a licence decision; (2, company id) entity listing;
(3, company id) a listing appeal (docs/formulas.md 39)."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

TENSION: Final = 0  # tunable-exempt: key family
LICENCE: Final = 1  # tunable-exempt: key family
LISTING: Final = 2  # tunable-exempt: key family
APPEAL: Final = 3  # tunable-exempt: key family


def geo_draws(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "geopolitics", family, *key)
