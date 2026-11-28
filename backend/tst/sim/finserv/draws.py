"""Stream `finserv` (id 74, ADR-0013): the one place M54 draws for financial services.

Keys (families, ADR-0013's table): `(0, *bank key, month)` a bank's run chance and its withdrawn
share; `(1, region key, year, month)` a region's catastrophe and its points; `(2, *bank key, year)`
a stress test's shock; `(4, region key, year)` a region's yearly growth after 2025; family 3 is
reserved (never drawn). Region keys are `text_key`s; a bank's key is `banks.bank_key` (M57r-A). Each is drawn
in the month it is needed and never stored before it happens."""

from __future__ import annotations

import numpy as np

from tst.sim.rng import RngFactory


def gen(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "finserv", family, *key)
