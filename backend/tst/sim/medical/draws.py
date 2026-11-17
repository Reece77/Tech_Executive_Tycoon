"""Stream `medical` (id 64, ADR-0013): the one place medical devices draw.

Keys: `(0, study id)` a study's readout; `(1, submission id, k)` a filing's draws, k = REVIEW
(its length and whether more information is asked, at filing), DECISION (its outcome, at the
decision), RELIANCE + region index (a relying region's registration length); `(2, company id,
regulator index)` a month's inspection and its finding; `(3, product id)` a month's recall
signal, its class and whether surveillance caught it; `(3, product id, region index)` a coverage
request's length and decision; `(4, regulator index)` a year's review drift after 2025. Draws
are never stored before they act (50.7)."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

STUDY, SUBMISSION, INSPECTION, PRODUCT, DRIFT = 0, 1, 2, 3, 4  # tunable-exempt: key families
REVIEW, DECISION, RELIANCE = 0, 1, 2  # tunable-exempt: a submission's draws (RELIANCE + region)
STREAM: Final = "medical"


def gen(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "medical", family, *key)
