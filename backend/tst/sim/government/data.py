"""Reading government.yaml for the engine (docs/formulas.md 57): whether governments buy in this
game, budgets by government and year (data to 2025, then the seeded growth), areas' categories,
and a company's country and bloc."""

from __future__ import annotations

from typing import Final

from tst.sim.calendar import turn_to_ym, ym_to_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.geopolitics import world
from tst.sim.government.config import GovernmentDef, GovernmentFile
from tst.sim.government.models import Tender
from tst.sim.products.models import Product
from tst.sim.state import CompanyState, GameState

MONTHS: Final = 12  # tunable-exempt: calendar
PCT: Final = 100  # tunable-exempt: scores and influence are 0-100
SKILL_MAX: Final = 20  # tunable-exempt: skills are 1-20
TINY: Final = 1e-9  # tunable-exempt: float tolerance


def year_of(turn: int) -> int:
    return turn_to_ym(turn)[0]


def january(year: int) -> int:
    return ym_to_turn(year, 1)


def file(data: GameData) -> GovernmentFile:
    assert data.government is not None
    return data.government


def enabled(data: GameData) -> bool:
    """Governments buy in this game: the data has them (a save from before M44 starts drawing
    tenders from its next month; a company that never bids plays exactly as before, 57.6)."""
    return data.government is not None


def scale(balance: Balance) -> float:
    """Real 2010 cents -> the game's (54; M34's `economy_scale.money`)."""
    return balance.economy_scale.money


def budget_cents(
    state: GameState, gov: GovernmentDef, year: int, balance: Balance, *, civil: bool
) -> float:
    """A government's defence (or civil technology) budget for a year, real 2010 cents: the data
    to the year before `government.start`, then compounded by each later year's seeded growth."""
    last = year_of(balance.government.start_turn) - 1
    base = gov.civil_at(min(year, last)) if civil else gov.defence_at(min(year, last))
    for y in range(last + 1, year + 1):
        g = state.government_world.growth_of(gov.key, y)
        base *= 1 + (g if g is not None else balance.government.budgets.trend)
    return base


def area_of(product: Product, data: GameData) -> str | None:
    """The programme area a product bids in (57.1), or None."""
    for key, area in file(data).areas.items():
        if product.category in area.categories:
            return key
    return None


def is_large(tender: Tender, balance: Balance) -> bool:
    return tender.value_cents >= balance.government.tenders.large_cents


def company_bloc(state: GameState, company: CompanyState, balance: Balance, data: GameData) -> str:
    country = world.company_country(state, company, balance, data)
    return world.bloc_of(data, country, state.turn)


def gov_bloc(gov: GovernmentDef, data: GameData, turn: int) -> str:
    return world.bloc_of(data, gov.country, turn)


def gov_region(gov: GovernmentDef, data: GameData) -> str:
    return world.countries_of(data).country(gov.country).region


def domestic_countries(gov: GovernmentDef) -> tuple[str, ...]:
    return gov.domestic or (gov.country,)


def announced(tender: Tender, turn: int) -> bool:
    """Shown from its announcement month (57.7: never before)."""
    return tender.announce_turn <= turn


def tender_year(tender: Tender) -> int:
    return year_of(tender.announce_turn)
