"""Reading telecom.yaml for the engine (docs/formulas.md 62): whether the telecom markets run, the
fractional year a month reads its year-end points at, and the history's lookups."""

from __future__ import annotations

from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.products.models import Product
from tst.sim.state import CompanyState, GameState
from tst.sim.telecom.config import TelecomFile

MONTHS: Final = 12  # tunable-exempt: calendar
MILLION: Final = 1_000_000  # tunable-exempt: telecom.yaml subscriptions are millions
THOUSAND: Final = 1_000  # tunable-exempt: fibre's capacity is thousands of homes
TINY: Final = 1e-9  # tunable-exempt: float tolerance
LAST_YEAR: Final = 2025  # tunable-exempt: telecom.yaml's last data year


def file(data: GameData) -> TelecomFile:
    assert data.telecom is not None
    return data.telecom


def end_year_at(turn: int) -> float:
    """The fractional year a year-end point is read at: December reads its own year's value,
    January mostly the year before's (subscriptions are counted at year end)."""
    year, month = turn_to_ym(turn)
    return year + (month - MONTHS) / MONTHS


def enabled(state: GameState, balance: Balance, data: GameData) -> bool:
    """The telecom markets run in this save: the data has them and the save has the mobile
    market (a save made before M53 has none, like M40's space)."""
    if data.telecom is None:
        return False
    cat = balance.telecom.mobile
    return any(m.category == cat for m in state.markets) or any(
        m.category == cat for m in state.regional_markets
    )


def in_history(turn: int, balance: Balance) -> bool:
    return turn < balance.telecom.start_turn


def is_telecom(product: Product, balance: Balance) -> bool:
    return product.category in balance.telecom.categories


def is_service(product: Product, balance: Balance) -> bool:
    """A network service line (mobile, fixed or wholesale), not equipment."""
    tb = balance.telecom
    return product.category in (tb.mobile, tb.fixed, tb.wholesale)


def demand_categories(balance: Balance) -> tuple[str, str, str]:
    """The categories whose addressable market telecom.yaml sets each month."""
    tb = balance.telecom
    return (tb.mobile, tb.fixed, tb.wholesale)


def is_telecom_rival(company: CompanyState, data: GameData) -> bool:
    """A telecom incumbent (an operator or an equipment vendor in telecom.yaml)."""
    if data.telecom is None:
        return False
    f = file(data)
    return bool(f.operators_of(company.name)) or f.vendor_of(company.name) is not None


def region_index(region: str, data: GameData) -> int:
    return data.region_keys.index(region)


def in_telecom(state: GameState, company_id: int, balance: Balance) -> bool:
    """The company has a telecom line, a network or a licence, or has registered for an auction:
    only such a company hears of auctions and bans (a company without telecom plays exactly as
    before, 62.5 target 1)."""
    cats = balance.telecom.categories
    if any(p.company_id == company_id and p.category in cats for p in state.products):
        return True
    t = state.telecom
    return (
        any(r.company_id == company_id for r in t.radios)
        or any(x.company_id == company_id for x in t.fibres)
        or any(x.company_id == company_id for x in t.cables)
        or any(x.company_id == company_id for x in t.licences)
        or any(a.bid_company_id == company_id for a in t.auctions)
    )
