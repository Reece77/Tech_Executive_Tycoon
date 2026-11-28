"""M57r-A sub-task 5 (review 10 items 13-18): finance and media timing and pricing."""

from __future__ import annotations

from dataclasses import replace

import tst.sim.actions  # noqa: F401
from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.finserv import demand
from tst.sim.finserv import phase as finserv_phase
from tst.sim.ledger import LedgerEntry
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

LATAM = "latin_america"


def _networks(state: GameState) -> float:
    return sum(
        m.addressable
        for m in state.regional_markets
        if m.region == LATAM and m.segment == "pay_networks"
    )


def test_a_new_rails_first_month_sells_against_the_new_market(loaded: LoadedData) -> None:
    """Codex R10-12: Pix's first month (November 2020) sold against October's card volume."""
    b, d = loaded.balance, loaded.game_data
    opening = ym_to_turn(2020, 11)
    base = fresh_game(loaded)
    october = finserv_phase.open_month(replace(base, turn=opening - 1), RngFactory(1), b, d)
    assert demand.rails_share(october, LATAM, b, d) == 0
    before_sales = finserv_phase.open_month(replace(october, turn=opening), RngFactory(1), b, d)
    assert demand.rails_share(before_sales, LATAM, b, d) > 0
    # phase 5 opens the month with its own market: what the allocator sees has already fallen
    assert 0 < _networks(before_sales) < _networks(october)
    assert _networks(demand.set_demand(before_sales, b, d)) == _networks(before_sales)


def test_no_ad_sellers_at_calibration_keeps_a_price(loaded: LoadedData) -> None:
    """Fable 7: with nobody selling ads at media.start the reference was 1e-9 impressions, so
    every later line earned the 1-cent floor."""
    from tst.sim.media import ads

    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=b.media.start_turn)
    social = {p.id for p in state.products if p.category == b.media.social}
    state = replace(state, products=tuple(p for p in state.products if p.id not in social))
    calibrated = ads.calibrate(state, b, d)
    assert calibrated.media.ad_refs == ()  # nobody to calibrate on: no reference yet
    for region in d.region_keys:
        cpm = ads.cpm_cents(calibrated, region, b, d)
        assert cpm == ads._history_cpm(calibrated, region, b, d) > 1


def test_att_weighs_ios_users_the_company_does_not_own(loaded: LoadedData) -> None:
    """Codex R10-11: a 20% Android share wiped out ATT's cut on a 20% iOS share; GDPR cut
    own-platform users too."""
    from tst.sim.media import ads

    d = loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2022, 1))
    region = "north_america"
    ios = ads._ios_users(state, 1, region, d)
    android = next(
        (p for p in state.platforms if p.key != ads.IOS_KEY and p.kind == "device"), None
    )
    if android is not None:  # the player owning Android leaves iOS's users exposed
        owned = replace(
            state,
            platforms=tuple(
                replace(p, owner_id=1) if p.id == android.id else p for p in state.platforms
            ),
        )
        assert ads._ios_users(owned, 1, region, d) == ios
        assert ads.own_platform_share(owned, 1, region) > 0
    rule = next(r for r in ads.file(d).ads.privacy if not r.ios_only)
    assert ads._privacy_cut(rule, rule.regions[0], 1.0 - 0.4) == rule.cut * 0.6


def test_a_charter_moves_with_a_sold_bank_line(loaded: LoadedData) -> None:
    """Fable 31: M34's ordered sale moved the banking line and left the Bank and its books."""
    from tst.sim.finserv import charters
    from tst.sim.finserv.models import Bank

    from .test_m54_banks import BANK_LINE, banking_line

    b, d = loaded.balance, loaded.game_data
    state = banking_line(replace(fresh_game(loaded), turn=ym_to_turn(2019, 1)), 10.0, 1.0)
    bank = Bank(
        1, 1, "north_america", "chartered", 0, consumer_deposits_cents=10**9,
        reserves_cents=3 * 10**8, loans=(("mortgage", 8 * 10**8),),
    )  # fmt: skip
    state = replace(state, finserv=replace(state.finserv, banks=(bank,)))
    line = state.product(BANK_LINE)
    assert line is not None
    moved = replace(
        state,
        products=tuple(
            replace(p, company_id=2) if p.id == BANK_LINE else p for p in state.products
        ),
    )
    out, entries = charters.on_sale(moved, 1, [line], b, d)
    assert out.finserv.banks == ()
    assert len(entries) == 1 and sum(x.amount for x in entries[0].lines) == 0


def test_an_integrated_bank_line_arrives_with_a_partner_bank(loaded: LoadedData) -> None:
    from tst.sim.finserv import charters

    from .test_m54_banks import BANK_LINE, banking_line

    b, d = loaded.balance, loaded.game_data
    state = banking_line(replace(fresh_game(loaded), turn=ym_to_turn(2019, 1)), 10.0, 1.0)
    line = state.product(BANK_LINE)
    assert line is not None
    out = charters.on_integrate(state, 1, [line], b, d)
    (bank,) = out.finserv.banks
    assert bank.status == "partner" and bank.company_id == 1


def test_the_editor_refuses_customers_behind_a_gate(loaded: LoadedData) -> None:
    """Fable 30: mobile, bank, insurance and payments lines earned from inherited customers."""
    from tst.sim.modes import custom
    from tst.sim.modes.config import ProductSpec, SegmentSpec

    b, d = loaded.balance, loaded.game_data
    spec = custom.from_historical(d.historical_scenario("ev_maker"))  # type: ignore[arg-type]
    for category in (b.telecom.mobile, b.finserv.banking_category, b.finserv.insurance_category):
        seg = d.category(category).markets[0].segment
        line = ProductSpec(
            name="Gated", category=category, quality=50, features=0, brand=50,
            segments={seg: SegmentSpec(price_dollars=10, customers=1000)},
        )  # fmt: skip
        edited = spec.model_copy(update={"products": (*spec.products, line)})
        assert any("starts without customers" in r for r in custom.refusals(edited, b, d))
        empty = line.model_copy(
            update={"segments": {seg: SegmentSpec(price_dollars=10, customers=0)}}
        )
        edited = spec.model_copy(update={"products": (*spec.products, empty)})
        assert not any("starts without customers" in r for r in custom.refusals(edited, b, d))


def test_game_store_fees_go_to_the_stores_owner(loaded: LoadedData) -> None:
    """Fable 28 (ruling 5): game fees were a flat 30% to cash, even on the player's own store."""
    from fractions import Fraction

    from tst.sim.media import titles
    from tst.sim.media.models import Title

    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2022, 1))
    title = Title(1, 1, "Game", titles.GAME, "action", 10**9, 0, 24, 24)
    stores = titles._mobile_stores(title, state, b, d)
    if stores:  # M31's platforms: each owner's user-weighted rate
        assert all(0 <= r <= 1 for r in stores.values())
        owners = {p.owner_id for p in state.platforms if p.kind == "device"}
        mine = replace(state, platforms=tuple(replace(p, owner_id=1) for p in state.platforms))
        fees: titles.Fees = {}
        titles._add_fees(fees, Fraction(1000), titles.MOBILE, title, mine, b, d)
        assert fees == {}  # all on its own store: internal, nothing paid
        assert owners
    fees = {}
    titles._add_fees(fees, Fraction(1000), titles.PC, title, state, b, d)
    entries: list[LedgerEntry] = []
    paid = titles._fee_entries(title, fees, state, entries)
    assert paid == 300 and all(sum(x.amount for x in e.lines) == 0 for e in entries)
