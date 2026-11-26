"""Reading finance_services.yaml for the engine (docs/formulas.md 64): whether the finance markets
run, the fractional year a month reads its yearly points at, and the history's lookups."""

from __future__ import annotations

from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.finserv.config import FinRivalDef, FinservFile, NetworkDef, series_at
from tst.sim.products.models import Product
from tst.sim.state import CompanyState, GameState

MONTHS: Final = 12  # tunable-exempt: calendar
MILLION: Final = 1_000_000  # tunable-exempt: accounts are millions
BILLION: Final = 1_000_000_000  # tunable-exempt: volumes and premiums are $ billion
TRILLION: Final = 1_000_000_000_000  # tunable-exempt: deposits are $ trillion
PCT: Final = 100.0  # tunable-exempt: % to a fraction
TINY: Final = 1e-9  # tunable-exempt: float tolerance
LAST_YEAR: Final = 2025  # tunable-exempt: the data's last year
FIRST_YEAR: Final = 2010  # tunable-exempt: the balance series' base year


def file(data: GameData) -> FinservFile:
    assert data.finserv is not None
    return data.finserv


def year_at(turn: int) -> float:
    """A month's fractional year (mid-year points: January 2015 reads 2015 + 0/12)."""
    year, month = turn_to_ym(turn)
    return year + (month - 1) / MONTHS


def history_year(turn: int, balance: Balance) -> float:
    """The year the data is read at: the month's to `finserv.start`, then December 2025's."""
    if turn < balance.finserv.start_turn:
        return year_at(turn)
    return float(LAST_YEAR)


def enabled(state: GameState, balance: Balance, data: GameData) -> bool:
    """The finance markets run in this save: the data has them and the save has the banking
    market (a save made before M54 has none, like M53's telecom)."""
    if data.finserv is None:
        return False
    cat = balance.finserv.banking_category
    return any(m.category == cat for m in state.markets) or any(
        m.category == cat for m in state.regional_markets
    )


def in_history(turn: int, balance: Balance) -> bool:
    return turn < balance.finserv.start_turn


def is_finance(product: Product, balance: Balance) -> bool:
    return product.category in balance.finserv.categories


def rival_def(company: CompanyState, data: GameData) -> FinRivalDef | NetworkDef | None:
    if data.finserv is None:
        return None
    f = file(data)
    return f.rival(company.name) or f.payments.network(company.name)


def is_finance_rival(company: CompanyState, data: GameData) -> bool:
    """A finance incumbent (a bank, card network, acquirer or insurer in finance_services.yaml)."""
    return not company.is_player and rival_def(company, data) is not None


def region_index(region: str, data: GameData) -> int:
    return data.region_keys.index(region)


def in_finance(state: GameState, company_id: int, balance: Balance) -> bool:
    """The company has a finance line, a bank, a network or an insurer."""
    cats = balance.finserv.categories
    if any(p.company_id == company_id and p.category in cats for p in state.products):
        return True
    fs = state.finserv
    return (
        any(b.company_id == company_id for b in fs.banks)
        or any(n.company_id == company_id for n in fs.networks)
        or any(i.company_id == company_id for i in fs.insurers)
    )


def nim_at(data: GameData, year: float) -> float:
    """US banks' net interest margin, a fraction a year, at a fractional year (held at the
    ends)."""
    return series_at(file(data).banking.nim, year) / PCT
