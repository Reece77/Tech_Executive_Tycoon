"""M35b: the v4 balance pass's engine follow-ups (docs/tasks/M35b-v4-balance.md sub-task 4):
regulators' seeded strictness after 2025, the antitrust review reading the regulators, rival
foundries' EUV growth waiting on deliveries, the lithography gate read through the group, and
Google Play's regulated rates; and the v4 scripts' first years (tst.balance.strategies_v4)."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as hs

from tests.equipment_helpers import fresh
from tests.platform_helpers import START
from tests.regulation_helpers import owner_state
from tst.loader import LoadedData
from tst.sim.equipment import programme as ep
from tst.sim.equipment.models import Delivery
from tst.sim.fabs import market
from tst.sim.founder.models import Influence
from tst.sim.regulation import data as rdata
from tst.sim.regulation import strictness as strict
from tst.sim.regulation.models import Case
from tst.sim.state import with_company

YEAR = 12


def _reg(loaded: LoadedData, key: str = "eu_commission"):  # type: ignore[no-untyped-def]
    return rdata.file(loaded.game_data).regulator(key)


# --- strictness after the history -------------------------------------------------------------


def test_strictness_is_the_data_to_the_history_end(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _, _ = owner_state(loaded)
    for reg in rdata.file(d).regulators:
        for turn in range(0, rdata.file(d).history_end_turn + 1, 7):
            assert strict.strictness(state, reg, b, d, turn) == rdata.strictness(reg, turn)


def test_strictness_path_is_seeded_and_moves(loaded: LoadedData) -> None:
    """The same seed draws the same path; seeds differ; the path moves after 2025."""
    b, d = loaded.balance, loaded.game_data
    state, _, _ = owner_state(loaded)
    reg = _reg(loaded)
    later = [START + YEAR * k for k in range(1, 14)]
    a = [strict.strictness(state, reg, b, d, t) for t in later]
    again = [strict.strictness(state, reg, b, d, t) for t in later]
    other = replace(state, save_meta=replace(state.save_meta, master_seed=99))
    c = [strict.strictness(other, reg, b, d, t) for t in later]
    assert a == again
    assert a != c
    assert len(set(a)) > 1


@settings(max_examples=40, deadline=None)
@given(seed=hs.integers(0, 2**32), years=hs.integers(1, 14), influence=hs.floats(0, 100))
def test_strictness_stays_inside_its_bounds(
    loaded: LoadedData, seed: int, years: int, influence: float
) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _, _ = owner_state(loaded)
    state = replace(state, save_meta=replace(state.save_meta, master_seed=seed))
    state = replace(state, influence=(Influence(state.player.id, "europe", influence),))
    lo, hi = b.regulation.strictness.bounds
    for reg in rdata.file(d).regulators:
        s = strict.strictness(state, reg, b, d, START + YEAR * years)
        assert lo <= s <= hi


def test_influence_softens_the_regulator(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _, _ = owner_state(loaded)
    reg = _reg(loaded)
    t = START + 3 * YEAR
    plain = strict.strictness(state, reg, b, d, t)
    lobbied = replace(state, influence=(Influence(state.player.id, reg.region, 100.0),))
    assert strict.strictness(lobbied, reg, b, d, t) < plain
    elsewhere = replace(state, influence=(Influence(state.player.id, "oceania", 100.0),))
    assert strict.strictness(elsewhere, reg, b, d, t) == plain


# --- the antitrust review reads the regulators ------------------------------------------------


def test_merger_review_reads_strictness_and_open_cases(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state, _, _ = owner_state(loaded, turn=START + 2 * YEAR)
    me = state.player.id
    before, _, _ = owner_state(loaded, turn=START - 1)
    assert strict.merger_factor(before, me, "europe", b, d) == 1.0
    base = strict.merger_factor(state, me, "europe", b, d)
    reg = _reg(loaded)
    last = rdata.year_of(rdata.file(d).history_end_turn)
    assert base == strict.strictness(state, reg, b, d) / reg.strictness_in(last)
    case = Case(
        id=1, regulator=reg.key, company_id=me, conduct="self_preferencing", market="devices",
        opened_turn=state.turn, stage="inquiry", stage_turn=state.turn, due_turn=state.turn + 6,
    )  # fmt: skip
    open_ = replace(state, reg_cases=(case,))
    want = base * b.regulation.merger_review.open_case
    assert strict.merger_factor(open_, me, "europe", b, d) == want
    closed = replace(state, reg_cases=(replace(case, outcome="dismissed"),))
    assert strict.merger_factor(closed, me, "europe", b, d) == base


# --- rival foundries' EUV growth waits on deliveries ------------------------------------------


def test_rival_euv_growth_waits_on_deliveries(loaded: LoadedData) -> None:
    """From 2026 a foundry at an EUV-only node grows its EUV share only with delivered tools:
    no deliveries cut its growth by euv_share; full deliveries leave it as seeded."""
    b, d = loaded.balance, loaded.game_data
    state, _ = fresh(loaded, 1, turn=START + 6)
    base = market._china(state, b, d)
    none = replace(state, tool_deliveries=())
    gated = market.timeline(none, b, d)
    tsmc = ("tsmc", 2026)
    assert market.euv_ratios(none, base, b, d)[tsmc] == 0.0
    s = b.equipment.rival_growth.euv_share
    assert gated.growth[tsmc] == base.growth[tsmc] * (1 - s)
    lots = (Delivery(START, "tsmc", "euv_low", 10_000),)
    full = market.timeline(replace(state, tool_deliveries=lots), b, d)
    assert full.growth[tsmc] == base.growth[tsmc]
    early, _ = fresh(loaded, 1, turn=START - 1)
    assert market.timeline(replace(early, tool_deliveries=()), b, d).growth == base.growth


# --- the lithography gate reads the group's stage ---------------------------------------------


def test_lithography_opens_at_the_groups_stage_five(loaded: LoadedData) -> None:
    """A holding company is stage 5 (31.2); its operating company, with the chip and fab,
    stays at 4: the gate reads the group (M35b)."""
    state, _ = fresh(loaded, 1, turn=START)
    me = state.player
    assert ep.group_stage(state, me.id) == me.stage
    top = replace(me, id=9_999, name="Litho Holdings", stage=5, parent_id=None)
    state = with_company(
        replace(state, companies=(*state.companies, top)), replace(me, stage=4, parent_id=top.id)
    )
    assert ep.group_stage(state, me.id) == 5


# --- Google Play's regulated rates ------------------------------------------------------------


def test_google_play_regulated_rates_have_sources(loaded: LoadedData) -> None:
    rules = [
        r
        for r in loaded.game_data.platforms.fee_rules  # type: ignore[union-attr]
        if r.platform == "android_play" and r.kind == "regulated"
    ]
    parts = {(r.part, r.from_, r.rate) for r in rules}
    assert ("eu", "2024-03", 0.27) in parts
    assert ("united_states", "2025-10", 0.0) in parts
    assert all("http" in r.source for r in rules)
