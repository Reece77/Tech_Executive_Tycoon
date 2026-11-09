"""M19's two streams, each from one call site (ADR-0013; tests/unit/test_rng_call_sites.py):
`mining` for a mine's own draws, keyed by its facility id and a tag naming the use, and
`region_risk` for a region's nationalization and export-ban events after 2025, keyed by the
region's index."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

BUILD, OVERRUN, GRADE, ACCIDENT, CHOICE, BID = range(6)  # tunable-exempt: mining key tags
TAGS: Final = (BUILD, OVERRUN, GRADE, ACCIDENT, CHOICE, BID)


def mining_draws(
    rng: RngFactory, turn: int, facility_id: int, tag: int, *more: int
) -> np.random.Generator:
    """A mine's draws: key (facility id, tag); a rival's bid for a project uses the project's
    id with tag BID and a third key (0 project, 1 mine)."""
    return rng.stream(turn, "mining", facility_id, tag, *more)


def region_draws(rng: RngFactory, turn: int, region_index: int) -> np.random.Generator:
    return rng.stream(turn, "region_risk", region_index)
