"""M55 (formulas.md 65): the media engine's rules, one by one, on a fresh game's state."""

from __future__ import annotations

from dataclasses import replace

import pytest

import tst.sim.actions  # noqa: F401
from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.actions import GreenlightTitle, OverruleLead, SetMediaLine, apply_action
from tst.sim.calendar import ym_to_turn
from tst.sim.errors import MediaRuleError
from tst.sim.media import ads, draws, social, streaming, talent, titles
from tst.sim.media.models import CreativeLead, LeadOffer, Title
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_product, with_segments

PLAYER = 1


def _title(state: GameState, loaded: LoadedData, kind: str = "series", **kw: object) -> Title:
    k = loaded.balance.media.kind(kind)
    return Title(
        id=kw.pop("id", 1),  # type: ignore[arg-type]
        company_id=PLAYER,
        name="T",
        kind=kind,
        genre="drama",
        budget_cents=titles.typical_budget_cents(k, loaded.balance),
        greenlit_turn=state.turn,
        dev_months=k.dev_months,
        release_turn=state.turn + k.dev_months,
        **kw,  # type: ignore[arg-type]
    )


def _run_to_release(state: GameState, loaded: LoadedData, seed: int) -> tuple[GameState, list[int]]:
    rng = RngFactory(seed)
    calls: list[int] = []
    real = draws.gen

    def spy(rng_: RngFactory, turn: int, family: int, *key: int):  # type: ignore[no-untyped-def]
        if family == draws.AUDIENCE:
            calls.append(turn)
        return real(rng_, turn, family, *key)

    titles.draws.gen = spy  # type: ignore[assignment]
    try:
        for _ in range(40):  # tunable-exempt: past any kind's development
            state = replace(state, turn=state.turn + 1)
            state, _, _ = titles.month(state, rng, loaded.balance, loaded.game_data)
    finally:
        titles.draws.gen = real  # type: ignore[assignment]
    return state, calls


def test_audience_is_drawn_once_at_release_and_seeded(loaded: LoadedData) -> None:
    state = fresh_game(loaded, seed=3)
    state = replace(state, media=replace(state.media, titles=(_title(state, loaded),)))
    a, calls = _run_to_release(state, loaded, 7)
    t = a.media.title(1)
    assert t is not None and t.released_turn is not None
    assert calls == [t.released_turn]
    b, _ = _run_to_release(state, loaded, 7)
    c, _ = _run_to_release(state, loaded, 8)
    tb, tc = b.media.title(1), c.media.title(1)
    assert tb is not None and tc is not None
    assert tb.audience == t.audience
    assert tc.audience != t.audience


def test_quality_follows_lead_budget_and_franchise(loaded: LoadedData) -> None:
    b = loaded.balance
    state = fresh_game(loaded, seed=3)
    base = _title(state, loaded)
    q0 = titles.quality(base, state, b, loaded.game_data)
    assert q0 == pytest.approx(b.media.quality.no_lead * b.media.quality.no_team)
    rich = replace(base, budget_cents=base.budget_cents * 2)
    assert titles.quality(rich, state, b, loaded.game_data) > q0
    assert titles.quality(rich, state, b, loaded.game_data) < 2 * q0  # diminishing
    hit = replace(base, id=2, stage="released", released_turn=state.turn, audience=40.0)
    state2 = replace(state, media=replace(state.media, titles=(hit,)))
    sequel = replace(base, id=3, sequel_of=2)
    assert titles.quality(sequel, state2, b, loaded.game_data) > q0


def test_hit_draw_is_mean_one_lognormal(loaded: LoadedData) -> None:
    state = fresh_game(loaded, seed=3)
    t = _title(state, loaded)
    rng = RngFactory(1)
    out = [titles.draw_audience(rng, 0, replace(t, id=i), 1.0, loaded.balance) for i in range(2000)]
    assert sum(out) / len(out) == pytest.approx(1.0, rel=0.1)
    assert sorted(out)[len(out) // 2] < 1.0  # most titles underperform


def test_att_cuts_targeting_on_ios_only(loaded: LoadedData) -> None:
    state = fresh_game(loaded, seed=3)
    b, d = loaded.balance, loaded.game_data
    before = replace(state, turn=ym_to_turn(2021, 3))
    after = replace(state, turn=ym_to_turn(2021, 4))
    for region in ("north_america", "south_southeast_asia"):
        t0 = ads.targeting(70.0, PLAYER, region, before, b, d)
        t1 = ads.targeting(70.0, PLAYER, region, after, b, d)
        ios = d.media.ads.ios_share[region]  # type: ignore[union-attr]
        assert t1 == pytest.approx(t0 * (1 - 0.30 * ios))  # tunable-exempt: media.yaml's ATT cut


def test_the_price_a_thousand_follows_spend_over_impressions(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded, seed=3), turn=b.media.start_turn)
    hist = ads._history_cpm(state, "europe", b, d)
    cal = ads.calibrate(state, b, d)
    assert ads.cpm_cents(cal, "europe", b, d) == pytest.approx(hist, rel=1e-9)


def _social(state: GameState, loaded: LoadedData, users: float) -> tuple[GameState, Product]:
    p = Product(
        id=9001,
        company_id=PLAYER,
        category=loaded.balance.media.social,
        name="Net",
        status="live",
        quality=60.0,
        feature_points=0.0,
        brand=40.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
    )
    state = with_product(state, p)
    state = with_segments(state, [ProductSegment(p.id, "users", 100, users)], [])
    return state, p


def test_small_networks_are_worth_less(loaded: LoadedData) -> None:
    b = loaded.balance
    a_small, c_small = social.network_mults(0.02, b)
    a_big, c_big = social.network_mults(0.30, b)
    assert a_small < 1 < a_big
    assert c_small > 1 > c_big or c_big == b.media.social_network.churn_range.lo


def test_the_newest_format_has_an_advantage_for_its_window(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded, seed=3), turn=ym_to_turn(2019, 1))
    state, p = _social(state, loaded, 1000.0)
    on_new = replace(
        state,
        media=replace(state.media, settings=(talent_setting(p.id, "short_video"),)),
    )
    on_old = replace(state, media=replace(state.media, settings=(talent_setting(p.id, "feed"),)))
    assert social.format_mult(p, on_new, b, d) == (b.media.social_network.format_advantage, True)
    old, adv = social.format_mult(p, on_old, b, d)
    assert old < 1 and not adv
    late = replace(on_new, turn=ym_to_turn(2023, 1))
    assert social.format_mult(p, late, b, d) == (1.0, False)


def talent_setting(pid: int, fmt: str):  # type: ignore[no-untyped-def]
    from tst.sim.media.models import LineSetting

    return LineSetting(product_id=pid, format=fmt)


def test_engagement_moves_appeal_and_churn(loaded: LoadedData) -> None:
    b = loaded.balance
    a_lo, c_lo = streaming.multipliers(0.1, b)
    a_hi, c_hi = streaming.multipliers(3.0, b)
    assert a_lo < 1 < a_hi and c_lo > 1 > c_hi


def _with_lead(
    state: GameState, loaded: LoadedData, ego: float, loyalty: float
) -> tuple[GameState, int]:
    offer = LeadOffer(year=2010, n=0, turn=state.turn)
    state = replace(state, media=replace(state.media, offers=(offer,)))
    state, _, lead = talent.sign(
        state, offer, PLAYER, 3, RngFactory(1), loaded.balance, loaded.game_data
    )
    lead = replace(lead, ego=ego, loyalty=loyalty)
    state = talent.with_lead(state, lead)
    return state, lead.person_id


def test_overrules_cost_morale_by_ego_and_can_make_a_lead_walk(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    base = fresh_game(loaded, seed=3)
    walks = 0
    for seed in range(1, 21):  # tunable-exempt: twenty seeds
        state, pid = _with_lead(base, loaded, 20.0, 1.0)
        t = _title(state, loaded, lead_person_id=pid)
        state = replace(state, media=replace(state.media, titles=(t,)))
        m0 = state.person_state(pid).morale or 0.0
        rng = RngFactory(seed)
        for n in range(2):  # tunable-exempt: twice
            t = replace(state.media.title(1), events=n + 1)  # type: ignore[arg-type]
            state, _ = talent.react(state, t, "overrule", rng, b, d)
        lead = state.media.lead(pid)
        assert lead is not None
        assert (state.person_state(pid).morale or 0.0) <= m0 - b.media.talent.overrule_morale
        walks += lead.company_id is None
    assert 0 < walks < 20  # tunable-exempt: some walk, not all
    calm, pid = _with_lead(base, loaded, 1.0, 20.0)
    t = _title(calm, loaded, lead_person_id=pid)
    calm = replace(calm, media=replace(calm.media, titles=(t,)))
    m0 = calm.person_state(pid).morale or 0.0
    calm, _ = talent.react(calm, t, "overrule", RngFactory(1), b, d)
    assert (calm.person_state(pid).morale or 0.0) > m0 - b.media.talent.overrule_morale / 10


def test_a_lead_on_offer_is_the_same_each_read(loaded: LoadedData) -> None:
    offer = LeadOffer(year=2012, n=3, turn=24)
    a = talent.candidate(offer, RngFactory(5), loaded.balance, loaded.game_data)
    b = talent.candidate(offer, RngFactory(5), loaded.balance, loaded.game_data)
    assert a == b
    assert 1.0 <= a.ego <= 20.0 and 1.0 <= a.creative <= 20.0  # tunable-exempt: the scale


def test_greenlight_refuses_out_of_range_budgets_and_consumer_ad_pricing_waits(
    loaded: LoadedData,
) -> None:
    b, d = loaded.balance, loaded.game_data
    state = fresh_game(loaded, seed=3)
    founder = _founder(state)
    ledger = {(PLAYER, "1000_cash"): 10**12}

    def act(s: GameState, action: object) -> object:
        return apply_action(s, action, RngFactory(1), b, d, ledger, seq=1)  # type: ignore[arg-type]

    with pytest.raises(MediaRuleError):
        act(state, GreenlightTitle(founder, "X", "series", 1))
    with pytest.raises(MediaRuleError):
        act(state, OverruleLead(founder, 99))
    app = Product(
        id=9002,
        company_id=PLAYER,
        category="consumer_apps",
        name="App",
        status="live",
        quality=60.0,
        feature_points=0.0,
        brand=40.0,
        marketing_budget_cents=0,
        created_turn=0,
        launched_turn=0,
    )
    state = with_product(state, app)
    with pytest.raises(MediaRuleError):
        act(
            replace(state, turn=b.media.start_turn - 1),
            SetMediaLine(founder, app.id, ad_pricing=True),
        )
    out = act(
        replace(state, turn=b.media.start_turn), SetMediaLine(founder, app.id, ad_pricing=True)
    )
    setting = out.new_state.media.setting(app.id)  # type: ignore[attr-defined]
    assert setting is not None and setting.ad_pricing


def _founder(state: GameState) -> int:
    return next(e.person_id for e in state.staff(PLAYER) if e.role == "founder")


def test_lead_profiles_are_hidden_from_the_creative_lead_dataclass_names() -> None:
    """ego and loyalty live on CreativeLead only (the API never reads them: see the API test)."""
    assert {"ego", "loyalty"} <= set(CreativeLead.__dataclass_fields__)
