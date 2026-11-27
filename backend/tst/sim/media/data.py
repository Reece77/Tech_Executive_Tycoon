"""Reading media.yaml for the engine (docs/formulas.md 65): whether the media markets run, the
fractional year a month reads its year-end points at, and lookups."""

from __future__ import annotations

from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.media.config import MediaFile
from tst.sim.products.models import Product
from tst.sim.state import CompanyState, GameState

MONTHS: Final = 12  # tunable-exempt: calendar
TINY: Final = 1e-9  # tunable-exempt: float tolerance
LAST_YEAR: Final = 2025  # tunable-exempt: media.yaml's last data year
SELLING: Final = ("live", "sunset")


def file(data: GameData) -> MediaFile:
    assert data.media is not None
    return data.media


def end_year_at(turn: int) -> float:
    """The fractional year a year-end point is read at (as telecom's)."""
    year, month = turn_to_ym(turn)
    return year + (month - MONTHS) / MONTHS


def enabled(state: GameState, balance: Balance, data: GameData) -> bool:
    """The media markets run in this save: the data has them and the save has the streaming market
    (a save made before M55 has none, like M53's telecom)."""
    if data.media is None:
        return False
    cat = balance.media.streaming
    return any(m.category == cat for m in state.markets) or any(
        m.category == cat for m in state.regional_markets
    )


def in_history(turn: int, balance: Balance) -> bool:
    return turn < balance.media.start_turn


def is_media(product: Product, balance: Balance) -> bool:
    return product.category in balance.media.categories


def is_media_rival(company: CompanyState, data: GameData) -> bool:
    """A media incumbent (a company with lines in media.yaml)."""
    if data.media is None or company.is_player or company.is_startup:
        return False
    return bool(file(data).lines_of(company.name))


def region_index(region: str, data: GameData) -> int:
    return data.region_keys.index(region)


def in_media(state: GameState, company_id: int, balance: Balance) -> bool:
    """The company has a media line, a title or a creative lead (only such a company hears of
    strikes, eras and laws: a company without media plays exactly as before, 65.8 target 1)."""
    cats = balance.media.categories
    if any(p.company_id == company_id and p.category in cats for p in state.products):
        return True
    m = state.media
    return any(t.company_id == company_id for t in m.titles) or any(
        x.company_id == company_id for x in m.leads
    )


def selling(product: Product) -> bool:
    return product.status in SELLING
