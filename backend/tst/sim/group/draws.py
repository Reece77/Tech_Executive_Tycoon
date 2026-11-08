"""The one call site of stream `group` (45; ADR-0013): keyed by the company's stable key, then
a tag naming the draw (a capital request, a stake sale's buyer, a minority complaint)."""

from __future__ import annotations

import numpy as np

from tst.sim.rivals.models import player_key
from tst.sim.rng import RngFactory
from tst.sim.state import CompanyState


def group_draws(rng: RngFactory, turn: int, company: CompanyState, tag: int) -> np.random.Generator:
    return rng.stream(turn, "group", *player_key(company.id, company.rival_key), tag)
