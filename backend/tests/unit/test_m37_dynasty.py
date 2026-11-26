"""M37 (formulas.md 52): dynasty mode. Sub-task 1: the data, the setting, the standard end."""

from __future__ import annotations

import itertools
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from tst.loader import DataLoadError, LoadedData, load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.dynasty import mode
from tst.sim.dynasty import nodes as dn
from tst.sim.errors import CampaignEndError, InvalidActionError
from tst.sim.fabs import nodes as fnodes
from tst.sim.modes.models import GameMode
from tst.sim.research import levels
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import GameState

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
JAN_2040 = ym_to_turn(2040, 1)


def _copy(tmp_path: Path) -> Path:
    import shutil

    target = tmp_path / "data"
    shutil.copytree(DATA_DIR, target)
    return target


def _edit_balance(path: Path, change) -> None:  # type: ignore[no-untyped-def]
    file = path / "balance.yaml"
    raw = yaml.safe_load(file.read_text())
    change(raw)
    file.write_text(yaml.safe_dump(raw))


def _game(loaded: LoadedData, seed: int = 1) -> GameState:
    scenario = loaded.game_data.scenario("ex_big_tech_founders")
    assert scenario is not None
    state, _ = new_game(
        save_name="t",
        master_seed=seed,
        scenario=scenario,
        difficulty="standard",
        company_name="Co",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
    )
    return state


# --- Sub-task 1: data and the mode ---------------------------------------------------------


def test_dynasty_keys_load(loaded: LoadedData) -> None:
    d = loaded.balance.dynasty
    assert (d.start_year, d.end_year) == (2040, 2069)
    assert mode.start_turn(loaded.balance) == JAN_2040 == 360
    assert mode.final_turn(loaded.balance) == 720
    assert d.mortality.base(74) == 0 and d.mortality.base(83) == d.mortality.by_age[80]
    assert d.markets.mature("no_such_category") == d.markets.mature_growth["default"]


def test_loader_rejects_successor_shares_that_do_not_sum_to_one(tmp_path: Path) -> None:
    path = _copy(tmp_path)
    _edit_balance(path, lambda raw: raw["dynasty"]["rivals"]["successor"].update(heir=0.9))
    with pytest.raises(DataLoadError, match="sum to 1"):
        load_all(path)


def test_loader_rejects_an_end_before_the_start(tmp_path: Path) -> None:
    path = _copy(tmp_path)
    _edit_balance(path, lambda raw: raw["dynasty"].update(end_year=2030))
    with pytest.raises(DataLoadError, match="end_year"):
        load_all(path)


def test_dynasty_eras_have_windows_from_2040_and_stay_out_before(loaded: LoadedData) -> None:
    b = loaded.balance
    # M52 (66.3): the third wave (windows from 2070) is tests/unit/test_m52_sandbox.py's
    late = [
        e
        for e in loaded.game_data.eras.eras
        if e.window is not None
        and b.dynasty.start_year <= e.window[0][0] < b.dynasty.beyond.start_year
    ]
    assert len(late) >= 6
    for era in late:
        start, n = levels.window_span(era)
        assert start >= JAN_2040 and start + n - 1 <= ym_to_turn(2065, 12)
        assert not levels.in_play(era, JAN_2040 - 1, b) and levels.in_play(era, JAN_2040, b)
    first = loaded.game_data.eras.eras[0]
    assert levels.in_play(first, 0, b)


def test_successor_nodes_slow_down_and_start_in_2040(loaded: LoadedData) -> None:
    nf = loaded.game_data.nodes
    # M52 (66.3): dynasty.beyond.nodes more after 2069, by the same rule
    rule = loaded.balance.dynasty
    assert nf is not None and len(nf.dynasty_future) == rule.nodes.count + rule.beyond.nodes
    mids = [n.start_turn + n.months // 2 for n in nf.dynasty_future]
    gaps = [b - a for a, b in itertools.pairwise(mids)]
    assert all(later > earlier for earlier, later in itertools.pairwise(gaps))
    assert all(n.start_turn >= JAN_2040 for n in nf.dynasty_future)
    tl = fnodes.timeline(7, nf, loaded.balance.fab)
    for n in nf.dynasty_future:
        assert tl.arrival[n.key] >= JAN_2040
        assert all(t >= JAN_2040 for (_, k), t in tl.reach.items() if k == n.key)


def test_successors_leave_every_earlier_node_alone(loaded: LoadedData) -> None:
    nf = loaded.game_data.nodes
    assert nf is not None
    bare = nf.model_copy(update={"dynasty_future": (), "dynasty_rule": None})
    for seed in (1, 2, 3):
        with_them = fnodes.build(seed, nf, loaded.balance.fab)
        without = fnodes.build(seed, bare, loaded.balance.fab)
        for key in without.keys:
            assert with_them.arrival[key] == without.arrival[key]
            assert with_them.wafer_cents[key] == without.wafer_cents[key]
        assert {k: t for k, t in with_them.reach.items() if k[1] in without.keys} == without.reach


def test_successors_are_seeded(loaded: LoadedData) -> None:
    nf = loaded.game_data.nodes
    assert nf is not None
    assert dn.successors(5, nf) == dn.successors(5, nf)
    assert dn.successors(5, nf) != dn.successors(6, nf)
    gains = [s.density_gain for s in dn.successors(5, nf)]
    assert all(b < a for a, b in itertools.pairwise(gains))


def test_frontier_and_growth_unchanged_to_2039(loaded: LoadedData) -> None:
    raw = load_all(DATA_DIR)  # the same files: the continuation rates start in 2040
    g = raw.game_data
    for d in g.tech.domains if g.tech else ():
        rates = {y: r for y, r in d.baseline.per_year.items() if y < 2040}
        assert rates and all(y >= 2040 for y in set(d.baseline.per_year) - set(rates))
        assert levels.accrued(d, JAN_2040) == pytest.approx(
            levels.accrued(
                d.model_copy(
                    update={"baseline": d.baseline.model_copy(update={"per_year": rates})}
                ),
                JAN_2040,
            ),
            abs=0,
        )
    for c in g.categories:
        for year in (2010, 2025, 2039):
            plain = c.model_copy(
                update={
                    "growth_by_year": {
                        y: r for y, r in (c.growth_by_year or {}).items() if y < 2040
                    }
                    or None
                }
            )
            assert c.growth_in(year) == plain.growth_in(year)
        assert c.growth_in(2069) <= c.growth_in(2039)


def test_a_standard_campaign_waits_at_its_end(loaded: LoadedData) -> None:
    b = loaded.balance
    state = replace(_game(loaded), turn=JAN_2040 - 1)
    assert not mode.at_standard_end(state, b)
    at_end = replace(state, turn=JAN_2040)
    assert mode.at_standard_end(at_end, b) and mode.outcome(at_end, b) == "campaign_end"
    with pytest.raises(CampaignEndError):
        mode.check_can_play(at_end, b)
    ended = mode.end_campaign(at_end, b)
    assert ended.save_meta.game_state == "campaign_end" and ended.save_meta.ended_turn == 359
    on = mode.continue_dynasty(at_end, b)
    assert on.mode == GameMode(kind="campaign", length="dynasty")
    assert not mode.at_standard_end(on, b)
    with pytest.raises(InvalidActionError):
        mode.continue_dynasty(on, b)
    with pytest.raises(InvalidActionError):
        mode.end_campaign(state, b)


def test_a_dynasty_game_closes_after_december_2069(loaded: LoadedData) -> None:
    b = loaded.balance
    state = mode.continue_dynasty(_game(loaded), b)
    assert mode.close_at_final(replace(state, turn=719), b).save_meta.game_state == "active"
    final = mode.close_at_final(replace(state, turn=720), b)
    assert final.save_meta.game_state == "dynasty_end" and final.save_meta.ended_turn == 719


def test_only_a_campaign_has_a_dynasty_mode(loaded: LoadedData) -> None:
    state = replace(_game(loaded), mode=GameMode(kind="sandbox"))
    with pytest.raises(InvalidActionError):
        mode.continue_dynasty(state, loaded.balance)
    assert not mode.at_standard_end(replace(state, turn=400), loaded.balance)


# --- Sub-task 4: rivals age ----------------------------------------------------------------


def _at_2040(loaded: LoadedData, seed: int = 1) -> GameState:
    return replace(mode.continue_dynasty(_game(loaded, seed), loaded.balance), turn=JAN_2040)


def test_rival_leaders_do_nothing_before_2040(loaded: LoadedData) -> None:
    from tst.sim.dynasty import rivals
    from tst.sim.rng import RngFactory

    state = replace(_game(loaded), turn=JAN_2040 - 12)  # January 2039
    rng = RngFactory(1)
    same, logs = rivals.leaders_month(state, rng, loaded.balance, loaded.game_data)
    assert same is state and logs == ()
    same2, entries, moves = rivals.entrants_month(state, rng, loaded.balance, loaded.game_data)
    assert same2 is state and entries == () and moves == ()


def test_rival_leaders_hand_over_seeded(loaded: LoadedData) -> None:
    from tst.sim.dynasty import rivals
    from tst.sim.press.names import rival_ceo_id
    from tst.sim.rng import RngFactory

    state = _at_2040(loaded)
    a, logs = rivals.leaders_month(state, RngFactory(1), loaded.balance, loaded.game_data)
    b, _ = rivals.leaders_month(state, RngFactory(1), loaded.balance, loaded.game_data)
    assert a.dynasty == b.dynasty and a.dynasty is not None
    changes = a.dynasty.leader_changes
    assert changes and len(logs) == len(changes)  # leaders aged 30 years hand over
    hows = {c.how for c in changes}
    assert hows <= {"heir", "insider", "outside"} and len(hows) >= 2
    for c in changes:
        assert rival_ceo_id(a, c.company_id) == c.new_person_id
        old = a.employment_of(c.old_person_id)
        assert old is None or old.status != "active"
        if c.how == "heir":
            assert a.person(c.new_person_id).last_name == a.person(c.old_person_id).last_name
    c, _ = rivals.leaders_month(state, RngFactory(2), loaded.balance, loaded.game_data)
    assert c.dynasty != a.dynasty


def test_retire_chance_rises_with_age_and_losses(loaded: LoadedData) -> None:
    from tst.sim.dynasty.rivals import retire_chance

    b = loaded.balance
    r = b.dynasty.rivals
    assert retire_chance(r.retire_age - 1, False, b) == 0
    assert retire_chance(r.retire_age + 5, False, b) > retire_chance(r.retire_age, False, b)
    assert retire_chance(40, True, b) == pytest.approx(r.loss_rate)


def test_short_markets_get_entrants_in_every_category(loaded: LoadedData) -> None:
    from tst.sim.dynasty import rivals
    from tst.sim.rng import RngFactory
    from tst.sim.state import group_companies

    b = loaded.balance
    want = 6
    many = b.model_copy(
        update={
            "dynasty": b.dynasty.model_copy(
                update={"rivals": b.dynasty.rivals.model_copy(update={"min_active": want})}
            )
        }
    )
    state = _at_2040(loaded)
    out, entries, moves = rivals.entrants_month(state, RngFactory(1), many, loaded.game_data)
    assert len(moves) == len(entries) > 0
    mine = {c.id for c in group_companies(out, out.player.id)}
    for c in loaded.game_data.categories:
        if c.markets:
            assert rivals.active_rivals(out, c.key, mine) >= want, c.key
    for c in out.companies:
        if c.rival_key[:1] == (rivals.DYNASTY_KEY,):
            (product,) = out.company_products(c.id)
            assert product.status == "live"
    again, _, _ = rivals.entrants_month(state, RngFactory(1), many, loaded.game_data)
    assert again.companies == out.companies


# --- Sub-task 5: the founder's lifetime ----------------------------------------------------


def _certain_death(loaded: LoadedData):  # type: ignore[no-untyped-def]
    b = loaded.balance
    from tst.sim.dynasty.config import MortalityRule

    m = MortalityRule.model_validate(
        {"from_age": 75, "by_age": {75: 1.0}, "wealth": 1.0, "stress": [1, 1], "family_time": 1.0}
    )
    return b.model_copy(update={"dynasty": b.dynasty.model_copy(update={"mortality": m})})


def test_death_chance_from_75_only(loaded: LoadedData) -> None:
    from tests.m36_helpers import family_game
    from tst.sim.dynasty.lifetime import death_chance

    b = loaded.balance
    young = replace(family_game(loaded, age=30).state, turn=JAN_2040)  # 60 in 2040
    assert death_chance(young, young.family.head_id, b) == 0  # type: ignore[union-attr]
    old = replace(family_game(loaded, age=50).state, turn=JAN_2040)  # 80 in 2040
    q = death_chance(old, old.family.head_id, b)  # type: ignore[union-attr]
    assert 0 < q < b.dynasty.mortality.base(80)  # wealth lowers it


def test_a_founder_without_a_family_dies_and_the_game_ends(loaded: LoadedData) -> None:
    from tst.sim.dynasty.lifetime import lifetime_month
    from tst.sim.people.founder import FounderSpec
    from tst.sim.rng import RngFactory

    scenario = loaded.game_data.scenario("ex_big_tech_founders")
    state, _ = new_game(
        save_name="t", master_seed=1, scenario=scenario, difficulty="standard",  # type: ignore[arg-type]
        company_name="Co", founder=FounderSpec(background="engineer", age=50),
        balance=loaded.balance, data=loaded.game_data,
    )  # fmt: skip
    b = _certain_death(loaded)
    before, _ = lifetime_month(replace(state, turn=JAN_2040 - 12), RngFactory(1), None, b,
                               loaded.game_data)  # fmt: skip
    assert before.save_meta.game_state == "active" and before.dynasty is None
    after, logs = lifetime_month(replace(state, turn=JAN_2040), RngFactory(1), None, b,
                                 loaded.game_data)  # fmt: skip
    assert after.save_meta.game_state == "founder_died"
    assert after.dynasty is not None and after.dynasty.deaths[0].role == "head"
    assert logs[0].template == "founder_died_no_family"


def test_a_death_hands_over_to_the_heir_and_settles_the_estate(loaded: LoadedData) -> None:
    from tests.m36_helpers import family_game, hire_child, with_cash
    from tst.sim.dynasty.lifetime import lifetime_month
    from tst.sim.family import rules
    from tst.sim.rng import RngFactory

    game = family_game(loaded, age=50, child_ages=(26, 22))
    kids = [m.person_id for m in rules.children(game.state)]
    hire_child(game, kids[0])
    old = game.state.family.head_id  # type: ignore[union-attr]
    game.state = with_cash(replace(game.state, turn=JAN_2040), old, 10**12)
    b = _certain_death(loaded)
    after, logs = lifetime_month(game.state, RngFactory(3), game.balances, b, loaded.game_data)
    assert after.save_meta.game_state == "active"
    founder = after.founder_of(after.player.id)
    assert founder is not None and founder.id == kids[0]  # the eldest, in the group
    assert after.family.head_id == founder.id and after.family.adviser_id is None  # type: ignore[union-attr]
    assert after.family.estate_tax_cents > 0  # type: ignore[union-attr]
    assert not any(s.person_id == old for s in after.seats)
    assert {log.template for log in logs} >= {"founder_died", "estate_settled", "succession_heir"}


def test_with_no_heir_ready_the_board_appoints_a_ceo(loaded: LoadedData) -> None:
    from tests.m36_helpers import family_game
    from tst.sim.dynasty.lifetime import lifetime_month
    from tst.sim.rng import RngFactory
    from tst.sim.state import ceo_of

    game = family_game(loaded, age=50, child_ages=(20,))  # 50 in 2040, not in the group
    state = replace(game.state, turn=JAN_2040)
    after, _ = lifetime_month(state, RngFactory(3), game.balances, _certain_death(loaded),
                              loaded.game_data)  # fmt: skip
    assert after.save_meta.game_state == "active"
    assert after.family.head_mode == "family_head"  # type: ignore[union-attr]
    assert ceo_of(after, after.player.id) is not None


def test_a_founder_without_a_family_may_retire_in_dynasty_years(loaded: LoadedData) -> None:
    from tst.sim.dynasty.lifetime import retire_founder

    state = _game(loaded)
    with pytest.raises(InvalidActionError):
        retire_founder(state, loaded.balance)
    done = retire_founder(replace(state, turn=JAN_2040), loaded.balance)
    assert done.save_meta.game_state == "founder_retired"
