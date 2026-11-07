"""Valuation of every company (docs/formulas.md 28.1, M14 sub-task 2): V_f from completed
months (25.3's multiple, or the acqui-hire value below $1M ARR), listed rivals' market cap
V_f x S, and private companies' off-centre value ranges. Read-only, except listed rivals'
monthly sentiment step (phase 7, stream market_sentiment keyed by the rival's stable key),
which no other draw shares."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.finance import macro
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.markets_public import formulas as pf
from tst.sim.markets_public.public import sentiment_draws
from tst.sim.markets_public.value import growth_of, margin_of
from tst.sim.mna import formulas as mf
from tst.sim.mna.draws import fixed_draws
from tst.sim.mna.models import RivalListing
from tst.sim.rivals.models import ENTRANT_KEY, INCUMBENT_KEY, stream_key
from tst.sim.rng import RngFactory
from tst.sim.state import (
    CompanyState,
    GameState,
    public_of,
    rival_listing,
    with_rival_listing,
)

MONTHS_A_YEAR = 12  # tunable-exempt: calendar
FIRST_YEAR = 2010  # tunable-exempt: turn 0 is January 2010
RANGE_TAG = 0  # tunable-exempt: stream mna sub-key of the value-range offset
BUILDER = "builder"


def listed_from(company: CompanyState, data: GameData) -> tuple[int, int] | None:
    """The data's listing month for an incumbent or a named entrant (28.1); None for a
    startup, a legacy rival or the player (whose listing is M13's)."""
    key = company.rival_key
    if len(key) == 2 and key[0] == INCUMBENT_KEY and key[1] < len(data.incumbents):
        return data.incumbents[key[1]].listed_from
    if len(key) == 2 and key[0] == ENTRANT_KEY and key[1] < len(data.entrants):
        return data.entrants[key[1]].listed_from
    return None


def is_listed(state: GameState, company_id: int, data: GameData) -> bool:
    """A company whose shares trade (28.1): the player after its IPO (25), a rival from its
    `listed_from` month while it is independent (a kept brand is not listed)."""
    company = state.company(company_id)
    if company.is_player:
        return public_of(state, company_id) is not None
    if company.parent_id is not None or not company.alive:
        return False
    since = listed_from(company, data)
    if since is None:
        return False
    year, month = since
    turn_listed = (year - FIRST_YEAR) * MONTHS_A_YEAR + (month - 1)
    return state.turn >= turn_listed


def builders(state: GameState, company_id: int, data: GameData) -> float:
    """Builders on staff: the builder pool plus key people in builder roles (28.1)."""
    pool = sum(p.headcount for p in state.company_pools(company_id) if p.function == BUILDER)
    people = sum(
        1 for e in state.staff(company_id) if data.role(e.role).product_function == BUILDER
    )
    return pool + people


def fundamental_value_cents(
    state: GameState,
    company_id: int,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> int:
    """V_f from the last completed month (28.1): ARR x m with the company's trailing growth
    and margin, the base rate and the venture climate (25.3); below mna.min_arr_cents ARR,
    cash + builders x mna.min_value_per_builder_cents (acqui-hire value)."""
    company = state.company(company_id)
    revenue = company.mrr_history[-1] if company.mrr_history else 0
    arr = revenue * MONTHS_A_YEAR
    if arr < balance.mna.min_arr_cents:
        cash = account_balance(balances, company_id, CASH)
        return mf.acquihire_value_cents(cash, builders(state, company_id, data), balance.mna)
    op = company.op_history[-1] if company.op_history else 0
    before = replace(
        company, mrr_history=company.mrr_history[:-1], op_history=company.op_history[:-1]
    )
    m = pf.multiple(
        growth_of(before, revenue),
        margin_of(before, revenue, op),
        macro.base_rate(state, data),
        macro.venture_climate(state, data),
        balance.public.multiple,
    )
    return pf.fundamental_value_cents(arr, m)


def market_cap_cents(
    state: GameState,
    company_id: int,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> int | None:
    """A listed company's market cap (public, 28.1): a rival's V_f x S, the player's share
    price x shares outstanding; None for a private company."""
    if not is_listed(state, company_id, data):
        return None
    public = public_of(state, company_id)
    if public is not None:
        from tst.sim.markets_public.public import outstanding_shares

        return public.price_cents * outstanding_shares(state, company_id)
    listing = rival_listing(state, company_id)
    sentiment = listing.sentiment if listing is not None else 1.0
    return round(fundamental_value_cents(state, company_id, balances, balance, data) * sentiment)


def range_draw(state: GameState, company: CompanyState) -> float:
    """The target's fixed value-range offset uniform (28.1): stream mna at turn 0, keyed by
    its stable rival key, so it never changes and no other draw moves it."""
    gen = fixed_draws(
        state.save_meta.master_seed, *stream_key(company.id, company.rival_key), RANGE_TAG
    )
    return float(gen.random())


def value_range_cents(
    state: GameState,
    company_id: int,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
    *,
    diligenced: bool = False,
) -> tuple[int, int]:
    """A private company's displayed value range (28.1): V_f x (1 +- mna.range), +-10% after
    diligence (28.2), off-centre by the target's fixed draw."""
    company = state.company(company_id)
    value = fundamental_value_cents(state, company_id, balances, balance, data)
    half = balance.mna.diligence.range if diligenced else balance.mna.range
    return mf.displayed_range(mf.value_range_cents(value, range_draw(state, company), half))


def listed_rivals_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> GameState:
    """Phase 7: each listed rival's sentiment steps (25.3's AR(1), stream market_sentiment
    keyed by its stable key); a rival listing for the first time starts at 1."""
    for company in state.rivals():
        if not is_listed(state, company.id, data):
            continue
        listing = rival_listing(state, company.id) or RivalListing(company.id)
        gen = sentiment_draws(rng, state.turn, *stream_key(company.id, company.rival_key))
        z = float(gen.standard_normal())
        sentiment = pf.sentiment_step(listing.sentiment, z, balance.public.sentiment)
        state = with_rival_listing(state, replace(listing, sentiment=sentiment))
    return state
