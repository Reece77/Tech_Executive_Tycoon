"""Stream `pharma` (id 67, ADR-0013): the one place pharmaceuticals draw.

Keys: `(0, programme id)` a molecule's hidden efficacy and safety;
`(1, programme id, stage index, attempt)` a stage's readout; `(2, review id, k)` a review, k =
LENGTH (its months, priority and advisory committee, at filing), DECISION (its outcome),
RELIANCE + region index (a relying region's registration); `(3, programme id, region index)`
generic or biosimilar entry at loss of exclusivity; `(4, company id, year)` a rival's approvals
after 2025; `(5, year)` seeded rules after 2025; `(6, year, k)` the k-th asset listed for licence
that January, its hidden values included; `(7,
INSPECT, company id, regulator index)` an inspection, `(7, RECALL, programme id)` a recall
signal; `(8, programme id, region index)` an HTA's length. Draws are never stored before they
act (55.7), except a molecule's hidden values, which are its nature."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.rng import RngFactory

# tunable-exempt: key families
FAMILIES = range(9)  # tunable-exempt: key families
MOLECULE, READOUT, REVIEW, GENERIC, RIVALS, RULES, ASSETS, SUPPLY, HTA = FAMILIES
LENGTH, DECISION, ADCOM, RELIANCE = 0, 1, 2, 3  # tunable-exempt: a review's draws
INSPECT, RECALL = 0, 1  # tunable-exempt: SUPPLY's two kinds
STREAM: Final = "pharma"


def gen(rng: RngFactory, turn: int, family: int, *key: int) -> np.random.Generator:
    return rng.stream(turn, "pharma", family, *key)
