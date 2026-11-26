"""M53 (formulas.md 62.1-62.4): networks and generations, spectrum auctions and licences, equipment
and bans, regulation, and the gates the player's lines sell through."""

from __future__ import annotations

from dataclasses import replace

import pytest

import tst.sim.actions  # noqa: F401
from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.errors import TelecomRuleError
from tst.sim.facilities.models import Facility
from tst.sim.ledger import CASH, SPECTRUM
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_facility, with_product, with_segments
from tst.sim.telecom import equipment as eq
from tst.sim.telecom import networks as nw
from tst.sim.telecom import regulation, services, spectrum
from tst.sim.telecom.actions import (
    BidSpectrum,
    BuildTowers,
    ReplaceRadios,
    apply_telecom,
    generation_open,
)
from tst.sim.telecom.data import in_telecom
from tst.sim.telecom.models import Auction, RadioNetwork, SpectrumLicence

PLAYER = 1
NA = "north_america"


def _facility(fid: int, kind: str, capacity: int, region: str = NA, ready: int = 0) -> Facility:
    return Facility(
        id=fid,
        company_id=PLAYER,
        kind=kind,
        region=region,
        capacity=capacity,
        on_time=capacity,
        ordered_turn=0,
        ready_turn=ready,
        late_turn=ready,
        capex_cents=0,
        input_index=1.0,
        capex_paid_cents=0,
        status="live",
    )


def _licence(
    lid: int, band: str = "low", mhz: float = 20.0, area: str = "united_states", turn: int = 0
) -> SpectrumLicence:
    return SpectrumLicence(lid, PLAYER, NA, area, band, mhz, 0, 10**9, turn, turn + 180)  # type: ignore[arg-type]


def _network(
    state: GameState, sites: int, gen: str = "g4", vendor: str = "ericsson", fid: int = 8001
) -> GameState:
    state = with_facility(state, _facility(fid, "tower", sites))
    rec = RadioNetwork(fid, PLAYER, NA, gen, vendor)
    return replace(state, telecom=replace(state.telecom, radios=(*state.telecom.radios, rec)))


def _mobile(state: GameState, pid: int = 9001) -> GameState:
    p = Product(
        id=pid,
        company_id=PLAYER,
        category="mobile",
        name="Nova Mobile",
        status="live",
        quality=60.0,
        feature_points=0.0,
        brand=50.0,
        marketing_budget_cents=0,
        created_turn=0,
        launched_turn=0,
    )
    state = with_product(state, p)
    return with_segments(state, [ProductSegment(pid, "telecom_consumer", 4000, 1000.0)], [])


def _at(loaded: LoadedData, year: int, month: int = 1) -> GameState:
    return replace(fresh_game(loaded), turn=ym_to_turn(year, month))


# --- 62.1 networks -------------------------------------------------------------------------------


def test_coverage_follows_sites_and_is_capped_by_licensed_areas(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    full = d.telecom.region(NA).sites_full * b.telecom.scale  # type: ignore[union-attr]
    quarter = nw.site_coverage(full / 4, "low", NA, b, d)
    assert quarter == pytest.approx(0.5)  # a quarter of a grid covers half the people
    assert nw.site_coverage(full, "mid", NA, b, d) == pytest.approx((1 / 1.8) ** 0.5)
    state = _network(_at(loaded, 2016), round(full))
    assert nw.network(state, PLAYER, NA, b, d).coverage == 0.0  # no spectrum, no service
    state = replace(state, telecom=replace(state.telecom, licences=(_licence(1),)))
    net = nw.network(state, PLAYER, NA, b, d)
    assert net.coverage == pytest.approx(0.66)  # the US area's share of North America
    assert net.capacity_gb == pytest.approx(round(full) * nw.site_gb(20.0 * 0.66, 1.6, "low", b))


def test_without_spectrum_a_mobile_line_cannot_sell(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _mobile(_network(_at(loaded, 2016), 2500))
    fx = services.effects(None, state, b, d)
    assert fx is not None and fx.appeal(9001, NA) == 0.0
    state = replace(state, telecom=replace(state.telecom, licences=(_licence(1),)))
    fx = services.effects(None, state, b, d)
    assert fx is not None and 0.0 < fx.appeal(9001, NA) < 1.0
    assert fx.bonus(9001, NA) > 0  # 4G's feature points


def test_5g_needs_mid_band_for_its_points(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    full = round(d.telecom.region(NA).sites_full * b.telecom.scale)  # type: ignore[union-attr]
    state = _network(_at(loaded, 2021), full, gen="g5")
    low = replace(state, telecom=replace(state.telecom, licences=(_licence(1),)))
    mid = replace(
        state, telecom=replace(state.telecom, licences=(_licence(1), _licence(2, "mid", 100.0)))
    )
    p_low = nw.feature_points(nw.network(low, PLAYER, NA, b, d), b, d)
    p_mid = nw.feature_points(nw.network(mid, PLAYER, NA, b, d), b, d)
    assert p_low == pytest.approx(8.0)  # low-band 5G gives 4G's points
    assert p_mid > 12  # mid-band reaches most of the covered people with 5G's 18


def test_generations_open_by_their_dates(loaded: LoadedData) -> None:
    d = loaded.game_data
    assert not generation_open(_at(loaded, 2019, 3), "g5", d)
    assert generation_open(_at(loaded, 2019, 4), "g5", d)
    assert not generation_open(_at(loaded, 2040), "g6", d)  # seeded: no month drawn yet


# --- 62.2 spectrum -------------------------------------------------------------------------------


def test_the_clock_stops_when_demand_fits() -> None:
    bidders = [
        spectrum.Bidder("A", None, 3, 150.0),
        spectrum.Bidder("B", None, 3, 120.0),
        spectrum.Bidder("C", None, 2, 105.0),
    ]
    rounds, price, won = spectrum.clock(bidders, 6, 100, 0.05, 400)
    assert price > 105 and price <= 120  # C dropped out; A and B fit the six blocks
    assert won == {0: 3, 1: 3}
    assert rounds >= 2


def test_a_dated_auction_without_the_player_clears_near_its_real_price(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    a = d.telecom.auction("us_cband_2021")  # type: ignore[union-attr]
    assert a is not None
    real = a.gross_cents * b.telecom.scale / a.blocks
    prices = []
    for seed in range(1, 8):
        state = _at(loaded, 2021)
        auction = replace(spectrum._from_def(a, 1, b.telecom.scale), turn=state.turn)
        state = replace(state, telecom=replace(state.telecom, auctions=(auction,)))
        state, entries, _ = spectrum.run_month(state, RngFactory(seed), b, d)
        assert entries == []  # no player, no books
        prices.append(state.telecom.auctions[0].price_cents)
    for p in prices:
        assert 0.95 * real <= p <= 1.10 * real


def test_the_player_wins_pays_and_holds_a_licence(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    a = d.telecom.auction("us_cband_2021")  # type: ignore[union-attr]
    assert a is not None
    state = _at(loaded, 2021)
    auction = replace(
        spectrum._from_def(a, 1, b.telecom.scale),
        turn=state.turn,
        bid_company_id=PLAYER,
        bid_blocks=2,
        bid_limit_cents=10**13,
    )
    state = replace(state, telecom=replace(state.telecom, auctions=(auction,)))
    state, entries, logs = spectrum.run_month(state, RngFactory(3), b, d)
    closed = state.telecom.auctions[0]
    lic = state.telecom.licences[0]
    assert lic.mhz == pytest.approx(280 * 2 / 14) and lic.band == "mid"
    assert lic.paid_cents == closed.price_cents * 2
    assert entries[0].lines[0].account == SPECTRUM and sum(x.amount for x in entries[0].lines) == 0
    assert any(x.account == CASH for x in entries[0].lines)
    assert any(log.template == "spectrum_auction_result" for log in logs)
    # amortized straight line over the term, the whole price by its end
    total = 0
    s = state
    for m in range(lic.expires_turn - lic.turn):
        s2 = replace(s, turn=lic.turn + m)
        s2, more, _ = spectrum.licences_month(s2, b, d)
        total += sum(
            line.amount
            for e in more
            for line in e.lines
            if line.account == SPECTRUM and e.memo == "Spectrum amortization"
        )
        s = s2
    assert -total == lic.paid_cents


def test_a_limit_below_the_rivals_wins_nothing(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    a = d.telecom.auction("us_cband_2021")  # type: ignore[union-attr]
    assert a is not None
    state = _at(loaded, 2021)
    auction = spectrum._from_def(a, 1, b.telecom.scale)
    auction = replace(
        auction,
        turn=state.turn,
        bid_company_id=PLAYER,
        bid_blocks=2,
        bid_limit_cents=auction.reserve_cents,
    )
    state = replace(state, telecom=replace(state.telecom, auctions=(auction,)))
    state, entries, _ = spectrum.run_month(state, RngFactory(3), b, d)
    assert entries == [] and state.telecom.licences == ()


def test_bids_are_refused_in_closed_areas_and_below_the_reserve(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _at(loaded, 2026)
    china = Auction(
        1, "x", "x", "east_asia", "china", "mid", 100.0, 4, 1000, state.turn + 2, 15, 0.0, 0, False
    )
    us = replace(china, id=2, region=NA, area="united_states")
    state = replace(state, telecom=replace(state.telecom, auctions=(china, us)))
    founder = state.founder_of(PLAYER).id  # type: ignore[union-attr]
    with pytest.raises(TelecomRuleError, match="administratively"):
        apply_telecom(state, BidSpectrum(founder, 1, 1, 5000), {}, b, d)
    with pytest.raises(TelecomRuleError, match="reserve"):
        apply_telecom(state, BidSpectrum(founder, 2, 1, 10), {}, b, d)


# --- 62.3 equipment and bans ---------------------------------------------------------------------


def test_bans_refuse_new_radios_and_switch_sites_off_after_the_deadline(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    assert eq.refusing_ban(_at(loaded, 2019, 4), NA, "huawei", b, d) is None
    assert eq.refusing_ban(_at(loaded, 2019, 5), NA, "huawei", b, d) is not None
    assert eq.refusing_ban(_at(loaded, 2021), "europe", "huawei", b, d) is None  # the UK is 9%
    state = _network(_at(loaded, 2026, 5), 1000, vendor="huawei")
    # Canada's 5G deadline (June 2024) owes its 8% of the region x the 5G layer's half
    assert eq.owed_sites(state, state.telecom.radios[0], d) == 40
    late = replace(state, turn=ym_to_turn(2026, 6))  # the US deadline (A): + 66%
    assert eq.owed_sites(late, late.telecom.radios[0], d) == 700  # Mexico has no ban
    late, logs = eq.dark_month(late, b, d)
    assert late.telecom.radios[0].dark == 700 and logs
    # replaced sites come back
    rec = replace(late.telecom.radios[0], replaced=400)
    late = replace(late, telecom=replace(late.telecom, radios=(rec,)))
    late, _ = eq.dark_month(late, b, d)
    assert late.telecom.radios[0].dark == 300


def test_rip_and_replace_orders_another_vendors_radios(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _network(_at(loaded, 2025), 1000, vendor="huawei")
    founder = state.founder_of(PLAYER).id  # type: ignore[union-attr]
    balances = {(PLAYER, CASH): 10**15}
    with pytest.raises(TelecomRuleError, match="another vendor"):
        apply_telecom(state, ReplaceRadios(founder, 8001, "huawei", 500), balances, b, d)
    with pytest.raises(TelecomRuleError):
        apply_telecom(state, ReplaceRadios(founder, 8001, "zte", 500), balances, b, d)  # banned too
    out = apply_telecom(state, ReplaceRadios(founder, 8001, "ericsson", 500), balances, b, d)
    new = out.state.telecom.radios[-1]
    assert new.replaces_facility_id == 8001 and new.overlay and new.vendor == "ericsson"
    with pytest.raises(TelecomRuleError, match="left to replace"):
        apply_telecom(out.state, ReplaceRadios(founder, 8001, "nokia", 1000), balances, b, d)


def test_towers_are_refused_for_a_banned_vendor_or_a_closed_generation(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _at(loaded, 2020)
    founder = state.founder_of(PLAYER).id  # type: ignore[union-attr]
    balances = {(PLAYER, CASH): 10**15}
    with pytest.raises(TelecomRuleError, match="no new radios"):
        apply_telecom(state, BuildTowers(founder, NA, 500, "g4", "huawei"), balances, b, d)
    with pytest.raises(TelecomRuleError, match="not commercial"):
        apply_telecom(state, BuildTowers(founder, NA, 500, "g6", "ericsson"), balances, b, d)
    out = apply_telecom(state, BuildTowers(founder, NA, 500, "g4", "ericsson"), balances, b, d)
    f = out.state.facility(out.state.telecom.radios[-1].facility_id)
    assert f is not None and f.kind == "tower" and f.capacity == 500
    want = 500 * (eq.civil_cents(state, d) + eq.radio_cents(state, PLAYER, "g4", "ericsson", b, d))
    assert f.capex_cents == round(want)


# --- 62.4 regulation -----------------------------------------------------------------------------


def test_a_missed_coverage_obligation_is_fined_then_revoked(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _network(_at(loaded, 2020), 100)
    lic = replace(_licence(1), obligation=0.9, obligation_turn=state.turn)
    state = replace(state, telecom=replace(state.telecom, licences=(lic,)))
    fines = 0
    for year in range(b.telecom.regulation.obligation_grace_years + 1):
        state = replace(state, turn=lic.obligation_turn + 12 * year)  # type: ignore[operator]
        state, entries, _ = regulation.obligations_month(state, b, d)
        fines += len([e for e in entries if e.memo.startswith("Coverage obligation fine")])
        for e in entries:
            assert sum(x.amount for x in e.lines) == 0
    assert fines == b.telecom.regulation.obligation_grace_years
    assert state.telecom.licences[0].status == "revoked"


def test_telecom_mergers_meet_a_stricter_review(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = _at(loaded, 2012)
    assert regulation.merger_factor(state, "b2b_saas", NA, b, d) == 1.0
    assert regulation.merger_factor(state, "mobile", NA, b, d) == pytest.approx(1.5 * 1.0)
    later = _at(loaded, 2018)
    assert regulation.merger_factor(later, "mobile", NA, b, d) == pytest.approx(1.5 * 0.85)
    assert regulation.merger_factor(later, "mobile", "europe", b, d) == pytest.approx(1.5 * 1.2)


def test_net_neutrality_follows_its_dates(loaded: LoadedData) -> None:
    d = loaded.game_data
    assert services.neutrality_in_force(_at(loaded, 2016), NA, d)
    assert services.neutrality_in_force(
        _at(loaded, 2019), NA, d
    )  # Canada's holds after the US repeal
    assert services.neutrality_in_force(_at(loaded, 2017), "europe", d)
    assert not services.neutrality_in_force(_at(loaded, 2012), "africa", d)


def test_a_company_without_telecom_hears_nothing(loaded: LoadedData) -> None:
    b = loaded.balance
    state = fresh_game(loaded)
    assert not in_telecom(state, PLAYER, b)
    state = _mobile(state)
    assert in_telecom(state, PLAYER, b)
