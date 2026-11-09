"""M22 (formulas.md 39): rules on their dates, tension history then seeded escalations and
détentes, selling restrictions (licences, variants, quotas), buying restrictions, the entity
list's ownership rule, tariffs and their posting, and licence approval with influence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tst.balance import m12b, m22
from tst.balance.game import start_game
from tst.sim.calendar import ym_to_turn
from tst.sim.commodities.models import CommodityDeal
from tst.sim.facilities.config import month_to_turn
from tst.sim.founder.models import Influence
from tst.sim.geopolitics import listing, sales, supply, tariffs, tension, world
from tst.sim.geopolitics import rules as gr
from tst.sim.geopolitics.actions import LaunchVariant, RequestLicence, approval_chance, decide
from tst.sim.geopolitics.models import EntityListing, Licence, Variant
from tst.sim.group.models import Ownership
from tst.sim.ledger import CASH, TARIFFS
from tst.sim.rng import RngFactory
from tst.sim.state import with_influence, with_licence, with_ownership, with_variant

PLAYER = 1


def _data():  # type: ignore[no-untyped-def]
    return m22.loaded()


# --- rules and tension ------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(1, 11))
def test_every_rule_takes_effect_on_its_date(seed: int) -> None:
    data = _data()
    d = data.game_data
    state = start_game(data, seed, "funded_spinout").state
    assert d.controls is not None
    for r in d.controls.rules:
        start = r.start_turn
        assert r.key not in {a.key for a in gr.in_force(state, d, start - 1)}, r.key
        if gr.suspension(state, d, r.key, start) is None:
            assert r.key in {a.key for a in gr.in_force(state, d, start)}, r.key
        if r.end_turn is not None:
            assert r.key not in {a.key for a in gr.in_force(state, d, r.end_turn + 1)}


def test_busan_suspends_for_a_year_and_the_ban_returns() -> None:
    data = _data()
    d = data.game_data
    state = start_game(data, 1, "funded_spinout").state
    ban = "cn_ga_ge_us_ban_2024"
    keys = lambda t: {a.key for a in gr.biting(state, d, t)}  # noqa: E731
    assert ban in keys(ym_to_turn(2025, 10))
    assert ban not in keys(ym_to_turn(2025, 11))
    assert ban not in keys(ym_to_turn(2026, 10))
    assert ban in keys(ym_to_turn(2026, 11))


def test_rules_are_visible_only_from_their_announcement() -> None:
    data = _data()
    d = data.game_data
    state = start_game(data, 1, "funded_spinout").state
    at = lambda t: {a.key for a in gr.visible(replace(state, turn=t), d)}  # noqa: E731
    assert "us_oct_2022" not in at(ym_to_turn(2022, 9))
    assert "us_oct_2022" in at(ym_to_turn(2022, 10))
    assert "nl_duv_2023" in at(ym_to_turn(2023, 3))  # announced March, in force September
    assert "nl_duv_2023" not in {a.key for a in gr.in_force(state, d, ym_to_turn(2023, 3))}
    assert not any(a.seeded for a in gr.visible(replace(state, turn=ym_to_turn(2039, 1)), d))


@pytest.mark.parametrize("seed", [1, 5])
def test_tension_follows_history_to_2025(seed: int) -> None:
    data = _data()
    d = data.game_data
    state = start_game(data, seed, "funded_spinout").state
    assert d.countries is not None
    for month, value in d.countries.tension_history:
        assert tension.tension_at(state, d, month_to_turn(month)) == value
    assert tension.tension_at(state, d, ym_to_turn(2018, 3)) == 27
    assert tension.tension_at(state, d, ym_to_turn(2022, 10)) == 75


def test_a_seeded_escalation_adds_a_rule_and_a_detente_suspends_one() -> None:
    data = _data()
    b, d = data.balance, data.game_data
    found: dict[str, tuple[int, str]] = {}
    for seed in range(1, 11):
        state = replace(start_game(data, seed, "funded_spinout").state, turn=ym_to_turn(2025, 12))
        rng = RngFactory(seed)
        while state.turn < ym_to_turn(2039, 12) and len(found) < 2:
            before = state
            state, kind, key = tension.next_month(state, rng, b, d)
            nxt = state.turn + 1
            if kind == "escalation" and key and "escalation" not in found:
                assert key in {a.key for a in gr.biting(state, d, nxt)}
                assert key not in {a.key for a in gr.biting(before, d, nxt)}
                assert state.tension[-1].value >= 0
                found["escalation"] = (nxt, key)
            if kind == "detente" and key and "detente" not in found:
                assert key in {a.key for a in gr.biting(before, d, nxt)}
                months = b.geopolitics.detente.suspend_months
                assert gr.suspension(state, d, key, nxt) == (nxt, nxt + months - 1)
                assert key not in {a.key for a in gr.biting(state, d, nxt + months - 1)}
                found["detente"] = (nxt, key)
            state = replace(state, turn=nxt)
        if len(found) == 2:
            break
    assert set(found) == {"escalation", "detente"}


def test_tension_draws_are_seeded() -> None:
    data = _data()
    b, d = data.balance, data.game_data
    s0 = replace(start_game(data, 3, "funded_spinout").state, turn=ym_to_turn(2027, 1))
    a, _, _ = tension.next_month(s0, RngFactory(3), b, d)
    c, _, _ = tension.next_month(s0, RngFactory(3), b, d)
    e, _, _ = tension.next_month(s0, RngFactory(4), b, d)
    assert a.tension == c.tension and a.tension != e.tension


# --- selling ----------------------------------------------------------------------------------


def _accel(turn: int):  # type: ignore[no-untyped-def]
    return m22.accelerator_company(1, _data(), turn)


def test_october_2022_closes_china_and_a_variant_reopens_it() -> None:
    data = _data()
    b, d = data.balance, data.game_data
    g, pid = _accel(ym_to_turn(2022, 9))
    product = g.state.product(pid)
    assert product is not None
    assert sales.access(g.state, product, "east_asia", b, d).free  # before the rules
    g.state = replace(g.state, turn=ym_to_turn(2022, 10))
    a = sales.access(g.state, product, "east_asia", b, d)
    assert a.blocked == pytest.approx(0.55) and a.variant == 0
    assert sales.access(g.state, product, "north_america", b, d).free
    state = with_variant(g.state, Variant(pid, g.state.turn))
    a = sales.access(state, product, "east_asia", b, d)
    keep = b.geopolitics.variant.keep
    assert a.variant == pytest.approx(0.55 * keep) and a.blocked == pytest.approx(0.55 * (1 - keep))
    # October 2023's update voids variants launched before it
    later = replace(state, turn=ym_to_turn(2023, 10))
    assert sales.access(later, product, "east_asia", b, d).blocked == pytest.approx(0.55)
    # a low-quality chip is under the threshold
    weak = replace(product, quality=40.0)
    assert sales.access(g.state, weak, "east_asia", b, d).free


def test_a_software_product_is_never_restricted() -> None:
    data = _data()
    b, d = data.balance, data.game_data
    g, pid = _accel(ym_to_turn(2023, 1))
    product = g.state.product(pid)
    assert product is not None
    soft = replace(product, category="b2b_saas")
    for region in d.region_keys:
        assert sales.access(g.state, soft, region, b, d).free


def test_a_licence_request_and_its_decision() -> None:
    data = _data()
    b, d = data.balance, data.game_data
    g, pid = _accel(ym_to_turn(2022, 10))
    assert g.act(RequestLicence(g.founder_id, pid, "china"))
    pending = [x for x in g.state.licences if x.status == "pending"]
    assert [x.rule_key for x in pending] == ["us_oct_2022"]
    assert pending[0].decide_turn == g.state.turn + b.geopolitics.licence.decision_months
    state = replace(g.state, turn=pending[0].decide_turn)
    # a draw under the chance approves; the approved licence opens China
    chance = approval_chance(state, pending[0], b, d)
    assert chance == pytest.approx(0.25)
    decided, logs = decide(state, RngFactory(1), b, d)
    x = next(x for x in decided.licences if x.id == pending[0].id)
    assert x.status in ("approved", "denied") and logs
    if x.status == "approved":
        product = decided.product(pid)
        assert product is not None
        assert sales.access(decided, product, "east_asia", b, d).blocked == pytest.approx(0.0)


def test_influence_raises_the_approval_chance() -> None:
    data = _data()
    b, d = data.balance, data.game_data
    g, pid = _accel(ym_to_turn(2022, 10))
    x = Licence(1, PLAYER, pid, "us_oct_2022", "china", g.state.turn, g.state.turn)
    base = approval_chance(g.state, x, b, d)
    state = with_influence(g.state, Influence(PLAYER, "north_america", 80.0))
    assert approval_chance(state, x, b, d) == pytest.approx(base * (1 + 0.3 * 0.8))
    assert approval_chance(state, x, b, d) / base >= 1.2  # 39.4 target 4


def test_a_variant_needs_a_controlled_chip() -> None:
    g, pid = _accel(ym_to_turn(2022, 10))
    assert g.act(LaunchVariant(g.founder_id, pid))
    assert any(v.product_id == pid for v in g.state.variants)
    assert not g.act(LaunchVariant(g.founder_id, pid))  # once a month


def test_blocked_customers_leave_at_the_exit_rate() -> None:
    data = _data()
    b, d = data.balance, data.game_data
    g, pid = _accel(ym_to_turn(2022, 10))
    seg = g.state.regional_segments_of(pid, "east_asia")[0]
    out = sales.exits(g.state, b, d)
    x = out.exits[0]
    first = seg.customers * 0.55
    assert x.remaining == pytest.approx(first * (1 - b.geopolitics.exit_rate))
    after = out.regional_segments_of(pid, "east_asia")[0].customers
    assert after == pytest.approx(seg.customers - first * b.geopolitics.exit_rate)


# --- buying -----------------------------------------------------------------------------------


def _offtake(supplier: str) -> CommodityDeal:
    return CommodityDeal(
        id=1,
        company_id=PLAYER,
        kind="offtake",
        good="gallium",
        signed_turn=0,
        end_turn=10_000,
        volume_year=1e9,
        signing_price=1.0,
        floor=0.0,
        ceiling=1e9,
        supplier=supplier,
    )


def test_gallium_licensing_then_the_us_ban() -> None:
    data = _data()
    b, d = data.balance, data.game_data
    g, _ = _accel(ym_to_turn(2023, 7))
    s = g.state
    assert supply.exposure(s, PLAYER, "gallium", b, d, 1.0).share == 0  # before August 2023
    lic = supply.exposure(replace(s, turn=ym_to_turn(2024, 1)), PLAYER, "gallium", b, d, 1.0)
    assert lic.share == pytest.approx(0.99) and lic.allowed == b.geopolitics.buy.licence_allowed
    ban = supply.exposure(replace(s, turn=ym_to_turn(2025, 1)), PLAYER, "gallium", b, d, 1.0)
    assert ban.allowed == 0 and ban.premium == b.geopolitics.buy.premium["ban"]
    dowa = replace(s, turn=ym_to_turn(2025, 1), commodity_deals=(_offtake("dowa"),))
    assert supply.exposure(dowa, PLAYER, "gallium", b, d, 1.0).share == 0
    chalco = replace(s, turn=ym_to_turn(2025, 1), commodity_deals=(_offtake("chalco"),))
    assert supply.exposure(chalco, PLAYER, "gallium", b, d, 1.0).share == 1.0


def test_a_gallium_ban_raises_a_chips_cost() -> None:
    data = _data()
    b, d = data.balance, data.game_data
    g, pid = _accel(ym_to_turn(2024, 11))
    from tst.sim.chips import chips

    product = g.state.product(pid)
    assert product is not None
    before = chips.unit_cost_cents(g.state, product, b, d)
    during = chips.unit_cost_cents(replace(g.state, turn=ym_to_turn(2024, 12)), product, b, d)
    assert during > before


def test_a_listed_company_gets_no_wafers_from_the_listing_bloc() -> None:
    data = _data()
    b, d = data.balance, data.game_data
    g, _ = _accel(ym_to_turn(2023, 1))
    assert supply.wafer_share(g.state, PLAYER, "ai_accelerator", "tsmc", b, d) == 1.0
    listed = replace(
        g.state, entity_listings=(EntityListing(PLAYER, "us_aligned", g.state.turn, "t"),)
    )
    assert supply.wafer_share(listed, PLAYER, "ai_accelerator", "tsmc", b, d) == 0.0


# --- the entity list's ownership rule ----------------------------------------------------------


def _owned(stake_bp: int, turn: int):  # type: ignore[no-untyped-def]
    data = _data()
    g, _ = _accel(turn)
    state = g.state
    rival = next(c for c in state.companies if c.is_rival and c.alive)
    state = with_ownership(
        state,
        Ownership(id=0, company_id=rival.id, owner_id=PLAYER, from_turn=0, stake_bp=stake_bp),
    )
    state = replace(state, entity_listings=(EntityListing(PLAYER, "us", turn, "test"),))
    return state, rival.id, data


@pytest.mark.parametrize(("stake_bp", "listed"), [(6000, True), (5000, True), (4000, False)])
def test_affiliates_of_a_listed_company_are_listed(stake_bp: int, listed: bool) -> None:
    state, rid, data = _owned(stake_bp, ym_to_turn(2025, 9))  # the affiliates rule bites
    owners = list(world.owners(state, state.company(rid), 0.5))
    assert bool(owners) == listed
    assert listing.owner_actors(state, rid, data.balance) == (["us"] if listed else [])
    assert listing.affiliates_rule(state, data.game_data, "us")


# --- tariffs ----------------------------------------------------------------------------------


def _device(year: int):  # type: ignore[no-untyped-def]
    data = _data()
    m12b._loaded = lambda: data  # type: ignore[assignment]
    g, pid = m12b.device_company(1, own_chip=False, start=ym_to_turn(year, 1))
    g.turn()
    return g, pid


def test_tariffs_post_to_5100_against_cash() -> None:
    data = _data()
    b, d = data.balance, data.game_data
    g, pid = _device(2020)
    state = g.state
    row = state.production_of(pid)
    assert row is not None and row.units > 0
    product = state.product(pid)
    assert product is not None
    made = tariffs.made_in(state, product, b, d)
    assert made == {"china": pytest.approx(1.0)}  # Foxconn in Shenzhen
    sold = tariffs.sold_in(state, product, b, d)
    assert sold["us"] == pytest.approx(0.88)
    entries = tariffs.tariffs_month(replace(state, turn=ym_to_turn(2020, 1)), b, d)
    assert len(entries) == 1
    lines = {line.account: line.amount for line in entries[0].lines}
    expected = round(0.15 * 0.88 * row.cogs_cents)
    assert lines[TARIFFS] == expected and lines[CASH] == -expected


def test_no_tariffs_before_section_301() -> None:
    data = _data()
    g, _ = _device(2017)
    assert tariffs.tariffs_month(g.state, data.balance, data.game_data) == []


# --- events -----------------------------------------------------------------------------------


def test_october_2022_is_a_critical_chip_event_for_a_china_seller() -> None:
    from tst.sim.geopolitics import events as ge

    data = _data()
    b, d = data.balance, data.game_data
    g, _ = _accel(ym_to_turn(2022, 9))
    rule = d.controls.rule("us_oct_2022")  # type: ignore[union-attr]
    assert ge.template_for(g.state, rule, b, d, ym_to_turn(2022, 10)) == ge.CHIPS_HIT


def test_a_software_company_hears_nothing() -> None:
    from tst.sim.geopolitics import events as ge

    data = _data()
    b, d = data.balance, data.game_data
    state = replace(start_game(data, 1, "funded_spinout").state, turn=ym_to_turn(2022, 9))
    for r in d.controls.rules:  # type: ignore[union-attr]
        assert ge.template_for(state, r, b, d, r.start_turn) is None


def test_grey_route_risks_listing() -> None:
    data = _data()
    b, d = data.balance, data.game_data
    g, pid = _accel(ym_to_turn(2022, 10))
    state = with_licence(
        g.state, Licence(1, PLAYER, pid, "us_oct_2022", "china", g.state.turn, g.state.turn, "grey")
    )
    product = state.product(pid)
    assert product is not None
    assert sales.access(state, product, "east_asia", b, d).free
    hits = 0
    for seed in range(1, 201):
        _, new = listing.listing_month(state, RngFactory(seed), b, d)
        hits += bool(new)
    assert 0 < hits < 40  # about grey_monthly (0.04) of 200
