"""M14 sub-task 2 (formulas.md 28.1): valuation of every company. Read-only: a company that
never buys plays exactly as before (the golden snapshots check that)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, rival_cash
from tst.db.mna_io import from_data, to_data
from tst.loader import LoadedData
from tst.sim.ledger import CASH
from tst.sim.mna import valuation as v
from tst.sim.mna.models import AcquiredPerson, Acquisition, Deal, RivalListing, TargetFile
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, rival_listing, with_company


def _named(state: GameState, name: str) -> int:
    return next(c.id for c in state.companies if c.name == name)


def test_listed_from_follows_history(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    data = loaded.game_data
    facebook, zoho, salesforce = (_named(state, n) for n in ("Facebook", "Zoho", "Salesforce"))
    assert v.is_listed(state, salesforce, data)  # since 2004
    assert not v.is_listed(state, facebook, data)  # January 2010: not yet
    may_2012 = replace(state, turn=28)
    assert not v.is_listed(replace(state, turn=27), facebook, data)
    assert v.is_listed(may_2012, facebook, data)
    assert not v.is_listed(may_2012, zoho, data)  # private: no field
    assert not v.is_listed(state, state.player.id, data)  # the player lists through M13
    company = state.company(salesforce)
    brand = with_company(state, replace(company, parent_id=state.player.id))
    assert not v.is_listed(brand, salesforce, data)  # a kept brand is not listed


def test_value_from_completed_months(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    data, b = loaded.game_data, loaded.balance
    cid = _named(state, "Salesforce")
    balances = rival_cash(state, loaded)
    company = state.company(cid)
    monthly = 10_000_000_00  # $10M a month: ARR $120M
    grown = replace(company, mrr_history=(monthly,) * 13, op_history=(monthly // 10,) * 13)
    s = with_company(state, grown)
    value = v.fundamental_value_cents(s, cid, balances, b, data)
    assert value > 12 * monthly  # ARR x m with m > 1 (25.3)
    small = with_company(state, replace(company, mrr_history=(5_000_00,), op_history=()))
    acquihire = v.fundamental_value_cents(small, cid, balances, b, data)
    cash = balances[(cid, CASH)]
    assert acquihire == cash + round(v.builders(small, cid, data) * 150_000_00)


def test_value_range_is_fixed_and_contains_the_truth(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    data, b = loaded.game_data, loaded.balance
    balances = rival_cash(state, loaded)
    for name in ("Zoho", "GitHub", "Evernote"):
        cid = _named(state, name)
        value = v.fundamental_value_cents(state, cid, balances, b, data)
        wide = v.value_range_cents(state, cid, balances, b, data)
        assert wide == v.value_range_cents(state, cid, balances, b, data)  # one fixed draw
        assert wide[0] <= value <= wide[1]
        narrow = v.value_range_cents(state, cid, balances, b, data, diligenced=True)
        assert narrow[0] <= value <= narrow[1] and narrow[1] - narrow[0] < wide[1] - wide[0]


def test_listed_rivals_sentiment_is_seeded(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    data, b = loaded.game_data, loaded.balance
    one = v.listed_rivals_month(state, RngFactory(5), b, data)
    two = v.listed_rivals_month(state, RngFactory(5), b, data)
    assert one.rival_listings == two.rival_listings and one.rival_listings
    listed = {x.company_id for x in one.rival_listings}
    assert _named(state, "Salesforce") in listed and _named(state, "Facebook") not in listed
    lo, hi = b.public.sentiment.bounds.lo, b.public.sentiment.bounds.hi
    assert all(lo <= x.sentiment <= hi for x in one.rival_listings)
    cid = _named(state, "Salesforce")
    cap = v.market_cap_cents(one, cid, rival_cash(state, loaded), b, data)
    listing = rival_listing(one, cid)
    assert listing is not None and cap is not None
    value = v.fundamental_value_cents(one, cid, rival_cash(state, loaded), b, data)
    assert cap == round(value * listing.sentiment)
    assert v.market_cap_cents(one, _named(state, "Zoho"), {}, b, data) is None  # private


@pytest.mark.parametrize(
    "record",
    [
        RivalListing(4, 1.07),
        TargetFile(1, 5, ("tech_debt",), 3, 5, 0.31, 12_00, 20),
        Deal(2, 1, 5, 10_000_00, 0.5, 3, "review", False, 9, 8, 0.42, "b2b_saas/smb/x", 0.7, 6),
        Acquisition(
            2,
            1,
            5,
            "integrate",
            9,
            10_00,
            "harvest",
            0.4,
            1_00,
            3,
            4,
            5,
            1,
            (),
            (7, 8),
            (9,),
            (10, 11),
        ),
        AcquiredPerson(11, 2, 21, False, 2.0),
    ],
)
def test_records_round_trip_as_json(record: object) -> None:
    from dataclasses import fields

    keys = {f.name: getattr(record, f.name) for f in fields(record)}  # type: ignore[arg-type]
    data = to_data(record)
    assert from_data(type(record), data) == record
    assert set(data) == set(keys)
