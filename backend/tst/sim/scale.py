"""Attribute and ability scales (formulas.md section 0). Definitions, not tunables."""

from __future__ import annotations

from typing import Final

ATTR_MIN: Final = 1.0  # attribute scale floor (skills, personality, hidden traits)
ATTR_MAX: Final = 20.0  # tunable-exempt: attribute scale ceiling (formulas.md section 0)
ABILITY_PER_ATTR: Final = 10  # tunable-exempt: CA = 10 x weighted mean skill (formulas.md 1)
ABILITY_MIN: Final = ATTR_MIN * ABILITY_PER_ATTR  # 10
ABILITY_MAX: Final = ATTR_MAX * ABILITY_PER_ATTR  # 200
PRIMARY_WEIGHT: Final = 3  # tunable-exempt: primary skills weigh 3 in CA (formulas.md 1)
SECONDARY_WEIGHT: Final = 1  # secondary skills weigh 1 in CA
PROFESSIONALISM_DIVISOR: Final = 10  # tunable-exempt: growth term professionalism / 10 (3)
SALARY_LEVEL_DIVISOR: Final = 100  # salary term (CA - level mean) / 100 (formulas.md 2.8)


def clamp_attr(value: float) -> float:
    """Clamp a skill, personality or hidden trait to [1.0, 20.0]."""
    return min(max(value, ATTR_MIN), ATTR_MAX)


def clamp_ability(value: float) -> float:
    """Clamp a current or potential ability to [10, 200]."""
    return min(max(value, ABILITY_MIN), ABILITY_MAX)


ATTR_NEUTRAL: Final = 10  # tunable-exempt: neutral trait value in (10 - risk_appetite) / 10 (7)
MORALE_MIN: Final = 0  # morale scale floor (formulas.md section 0)
MORALE_MAX: Final = 100  # morale scale ceiling


def clamp_morale(value: float) -> float:
    return min(max(value, MORALE_MIN), MORALE_MAX)
