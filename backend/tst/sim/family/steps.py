"""The founder_step stats of data/events/family.yaml (M36, formulas.md 45). Constants only,
so the events schema can import them without a cycle."""

from __future__ import annotations

from typing import Final

FAMILY_STEPS: Final = (
    "family_more_time",  # 45.2: the strain event
    "family_counselling",
    "family_carry_on",
    "family_marry",  # 45.1
    "family_not_yet",
    "family_school_standard",  # 45.3: education at 12, 18 and 22
    "family_school_elite",
    "family_uni_standard",
    "family_uni_top",
    "family_uni_none",
    "family_mba",
    "family_step_back",  # 45.5: a health event
    "family_delay",
    "family_heir",  # 45.5: the succession choice
    "family_ceo",
)
