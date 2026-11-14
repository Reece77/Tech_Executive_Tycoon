"""M36 (formulas.md 45): the family, children growing up, heirs, succession, estate planning
and the dynasty score."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from tests.m36_helpers import family_game, hire_child, with_cash
from tst.loader import DataLoadError, LoadedData, load_all
from tst.sim.errors import InvalidActionError, InvalidFamilyError
from tst.sim.family import answers, dynasty, estate, rules, succession
from tst.sim.family.models import EX_PARTNER, TRUST_HOLDER
from tst.sim.family.phase import bond_delta, step_back_chance
from tst.sim.family.setup import FamilySpec, check_spec
from tst.sim.finance.captable import fd_shares, person_shares
from tst.sim.founder.personal import cash_cents
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import family_partner, life_of, listed_id

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


# --- Sub-task 1: data ------------------------------------------------------------------------


def test_balance_keys_load(loaded: LoadedData) -> None:
    fb = loaded.balance.family
    assert fb.calm == 6 and fb.bond == 2 and fb.inherit == 0.5 and fb.divorce_share == 0.5
    assert set(loaded.balance.estate_tax) == set(loaded.game_data.region_keys)
    us = loaded.balance.estate_tax["north_america"]
    assert us.rate == 0.40 and us.gift_tax


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


def test_loader_rejects_a_missing_region(tmp_path: Path) -> None:
    path = _copy(tmp_path)
    _edit_balance(path, lambda raw: raw["estate_tax"].pop("oceania"))
    with pytest.raises(DataLoadError, match="estate_tax must cover"):
        load_all(path)


def test_loader_rejects_an_unknown_skill(tmp_path: Path) -> None:
    path = _copy(tmp_path)
    _edit_balance(path, lambda raw: raw["family"].update(mentor_skills=["juggling"]))
    with pytest.raises(DataLoadError, match="juggling"):
        load_all(path)


def test_loader_rejects_a_history_that_does_not_end_at_the_rate(tmp_path: Path) -> None:
    path = _copy(tmp_path)
    _edit_balance(path, lambda raw: raw["estate_tax"]["europe"].update(rate=0.2))
    with pytest.raises(DataLoadError, match="last history row"):
        load_all(path)


# --- Sub-task 2: the family ------------------------------------------------------------------


def test_family_none_adds_nothing(loaded: LoadedData) -> None:
    scenario = loaded.game_data.scenario("funded_spinout")
    assert scenario is not None
    kw = dict(
        save_name="x", master_seed=4, scenario=scenario, difficulty="standard",
        company_name="X", founder=DEFAULT_FOUNDER, balance=loaded.balance, data=loaded.game_data,
    )  # fmt: skip
    plain, e1 = new_game(**kw)  # type: ignore[arg-type]
    none, e2 = new_game(**kw, family=FamilySpec("none"))  # type: ignore[arg-type]
    assert plain == none and e1 == e2
    assert plain.family is None and plain.family_members == ()


def test_the_same_seed_gives_the_same_family(loaded: LoadedData) -> None:
    a = family_game(loaded, 11).state
    b = family_game(loaded, 11).state
    c = family_game(loaded, 12).state
    assert a.family == b.family and a.family_members == b.family_members
    ids = [m.person_id for m in a.family_members]
    assert [a.person(i) for i in ids] == [b.person(i) for i in ids]
    assert [a.person(i) for i in ids] != [c.person(i) for i in ids]


def test_a_partner_and_children(loaded: LoadedData) -> None:
    state = family_game(loaded, 5, child_ages=(1, 6)).state
    partner = family_partner(state)
    assert partner is not None and state.family is not None
    assert state.family.relationship == loaded.balance.family.relationship_start
    kids = rules.children(state)
    assert [state.person(k.person_id).age(0) for k in kids] == [6, 1]
    founder = state.person(state.family.head_id)
    for k in kids:
        child = state.person(k.person_id)
        assert child.last_name == founder.last_name
        assert k.parent_ids == (founder.id, partner.person_id)
        for key, value in child.personality.items:  # 45.1's blend stays on the 1-20 scale
            assert 1.0 <= value <= 20.0, key
    # This month's family time is taken from the founder's energy (45.2).
    energy = state.person_state(founder.id).energy
    assert energy == loaded.balance.founder.energy_per_month - loaded.balance.family.default_time


def test_setup_rules(loaded: LoadedData) -> None:
    b = loaded.balance
    with pytest.raises(InvalidFamilyError):
        check_spec(FamilySpec("children"), 30, b)  # no children
    with pytest.raises(InvalidFamilyError):
        check_spec(FamilySpec("partner", (3,)), 30, b)
    with pytest.raises(InvalidFamilyError):
        check_spec(FamilySpec("children", (15,)), 30, b)  # older than the founder allows
    with pytest.raises(InvalidFamilyError):
        check_spec(FamilySpec("children", (41,)), 60, b)  # older than the founder allows
    with pytest.raises(InvalidFamilyError):
        check_spec(FamilySpec("dynasty"), 30, b)


def test_life_events_bring_children(loaded: LoadedData) -> None:
    from tst.sim.family.phase import _life_events

    game = family_game(loaded, 2, setting="partner")
    sure = loaded.balance.model_copy(
        update={"family": loaded.balance.family.model_copy(update={"child_rate": 12.0})}
    )
    state, logs = _life_events(game.state, RngFactory(2), sure, loaded.game_data)
    assert len(rules.children(state)) == 1 and logs[0].template == "family_child_born"
    assert state.person(rules.children(state)[0].person_id).age(state.turn) == 0


# --- Sub-task 3: family time and the relationship --------------------------------------------


def test_bond_delta(loaded: LoadedData) -> None:
    b = loaded.balance
    assert bond_delta(8, False, b) == 0
    assert bond_delta(0, False, b) == -2 and bond_delta(20, False, b) == 2
    assert bond_delta(12, False, b) == 1
    assert bond_delta(8, True, b) == -3


def test_family_time_holds_the_relationship_and_eases_stress(loaded: LoadedData) -> None:
    game = family_game(loaded, 6)
    start = game.state.family.relationship  # type: ignore[union-attr]
    game.state = answers.set_family_time(game.state, 16, loaded.balance)
    for _ in range(6):
        game.turn()
    family = game.state.family
    assert family is not None and family.relationship > start
    life = life_of(game.state, family.head_id)
    assert life is not None
    assert any(why == "time with the family" for _, _, why in life.causes)


def test_neglect_brings_strain_then_divorce(loaded: LoadedData) -> None:
    game = family_game(loaded, 6)
    game.state = answers.set_family_time(game.state, 0, loaded.balance)
    family = game.state.family
    assert family is not None
    game.state = replace(game.state, family=replace(family, relationship=32.0))
    templates = []
    for _ in range(14):
        game.turn()  # critical events are answered with their first choice ("more time")
        templates += [e.template_id for e in game.state.events if e.turn == game.state.turn]
    assert "family_strain" in templates
    # Carrying on instead: below 15 for six months brings divorce.
    game = family_game(loaded, 6)
    game.state = answers.set_family_time(game.state, 0, loaded.balance)
    family = game.state.family
    assert family is not None
    game.state = replace(game.state, family=replace(family, relationship=14.0, strain_turn=0))
    partner = family_partner(game.state)
    assert partner is not None
    for _ in range(7):
        game.turn()
    after = rules.member_of(game.state, partner.person_id)
    assert after.relation == EX_PARTNER and family_partner(game.state) is None


# --- Sub-task 4: children growing up ---------------------------------------------------------


def test_education_and_closeness_lift_development(loaded: LoadedData) -> None:
    from tst.sim.family.people import develop

    game = family_game(loaded, 8, child_ages=(12,), age=40)
    kid = rules.children(game.state)[0]
    person = game.state.person(kid.person_id)
    elite = replace(kid, school="elite")
    standard = replace(kid, school="standard")
    a, b = person, person
    for t in range(game.state.turn, game.state.turn + 72):
        a = develop(a, elite, t, None, 90.0, loaded.balance, loaded.game_data)
        b = develop(b, standard, t, None, 20.0, loaded.balance, loaded.game_data)
    assert sum(v for _, v in a.skills.items) > sum(v for _, v in b.skills.items)


def test_educate_pays_and_narrows_the_view(loaded: LoadedData) -> None:
    game = family_game(loaded, 8, child_ages=(18,), age=45)
    kid = rules.children(game.state)[0]
    head = game.state.family.head_id  # type: ignore[union-attr]
    with pytest.raises(InvalidActionError, match="personal cash"):
        answers.educate(game.state, kid.person_id, "university", "top", "science", loaded.balance)
    state = with_cash(game.state, head, 1_000_000_00)
    before = state.reveal(1, kid.person_id)
    state, _ = answers.educate(state, kid.person_id, "university", "top", "science", loaded.balance)
    after = state.reveal(1, kid.person_id)
    assert before is not None and after is not None
    assert all(
        ra.hw < rb.hw for (_, ra), (_, rb) in zip(after.attributes, before.attributes, strict=True)
    )
    cost = loaded.balance.family.education.cents["uni_top"]
    assert cash_cents(state, head) == 1_000_000_00 - cost
    assert rules.member_of(state, kid.person_id).university == "top"


def test_a_childs_potential_never_narrows_to_exact(loaded: LoadedData) -> None:
    from tst.sim.family.people import narrow_view
    from tst.sim.people.models import PA_KEY

    game = family_game(loaded, 8)
    kid = rules.children(game.state)[0]
    state = game.state
    for _ in range(200):
        state = narrow_view(state, kid.person_id, 0.5, loaded.balance)
    rev = state.reveal(1, kid.person_id)
    assert rev is not None
    assert rev.record(PA_KEY).hw >= loaded.balance.family.pa_hw_floor


# --- Sub-task 5: heirs in the company --------------------------------------------------------


def _heir_game(loaded: LoadedData, seed: int = 9):  # type: ignore[no-untyped-def]
    game = family_game(loaded, seed, age=60, child_ages=(30, 27))
    kids = rules.children(game.state)
    for k in kids:
        hire_child(game, k.person_id)
    game.turn()  # the founder's life starts in the first month (32)
    return game, [k.person_id for k in kids]


def test_heirs_have_readiness_bands(loaded: LoadedData) -> None:
    game, kids = _heir_game(loaded)
    for pid in kids:
        band = rules.readiness(game.state, rules.member_of(game.state, pid), loaded.balance)
        assert band in ("not_ready", "developing", "ready", "strong")
    assert rules.eligible_heirs(game.state, loaded.balance)  # both are 25 or older


def test_a_childs_offer_turned_down_with_low_closeness(loaded: LoadedData) -> None:
    game = family_game(loaded, 9, age=60, child_ages=(30,))
    kid = rules.children(game.state)[0]
    game.state = replace(
        game.state,
        family_members=tuple(
            replace(m, closeness=10.0) if m.person_id == kid.person_id else m
            for m in game.state.family_members
        ),
    )
    state, log = answers.offer_job(
        game.state, kid.person_id, 1, "product_manager", "senior", loaded.balance, loaded.game_data
    )
    assert log.template == "family_job_declined" and state.employment_of(kid.person_id) is None


def test_mentoring_costs_energy_and_grows_leadership(loaded: LoadedData) -> None:
    game, kids = _heir_game(loaded)
    game.state = answers.set_mentoring(game.state, kids[0], True)
    assert answers.family_energy(game.state, loaded.balance) == 10 + 3
    before = game.state.person(kids[0]).skills["leadership"]
    for _ in range(3):
        game.turn()
    assert game.state.person(kids[0]).skills["leadership"] > before


# --- Sub-task 6: succession ------------------------------------------------------------------


def test_succession_to_an_heir(loaded: LoadedData) -> None:
    game, kids = _heir_game(loaded)
    old = game.founder_id
    old_life = life_of(game.state, old)
    heir = kids[0]
    rng = RngFactory(game.state.save_meta.master_seed)
    state, logs = succession.hand_to_heir(
        game.state, heir, "choice", rng, game.balances, loaded.balance, loaded.game_data
    )
    assert state.founder_of(1) is not None and state.founder_of(1).id == heir  # type: ignore[union-attr]
    assert not state.person(old).is_founder
    life = life_of(state, heir)
    assert life is not None and life.stress == loaded.balance.family.heir_stress
    assert old_life is not None
    assert life.visionary == pytest.approx(20 + 0.25 * old_life.visionary)
    family = state.family
    assert family is not None and family.head_id == heir and family.adviser_id == old
    assert any(s.person_id == old for s in state.board(1))
    assert any(s.person_id == heir for s in state.board(1))
    assert [g.person_id for g in family.generations] == [old, heir]
    assert family.generations[0].legacy is not None
    assert logs[-1].template == "succession_heir"
    # The game plays on with the heir.
    game.state = state
    game.turn()
    assert game.founder_id == heir


def test_succession_needs_an_eligible_heir(loaded: LoadedData) -> None:
    game = family_game(loaded, 9, age=40, child_ages=(10,))
    kid = rules.children(game.state)[0]
    rng = RngFactory(1)
    with pytest.raises(InvalidActionError):
        succession.hand_to_heir(
            game.state, kid.person_id, "choice", rng, None, loaded.balance, loaded.game_data
        )


def test_a_professional_ceo_makes_the_family_head(loaded: LoadedData) -> None:
    game, _ = _heir_game(loaded)
    rng = RngFactory(game.state.save_meta.master_seed)
    state, _logs = succession.appoint_professional(
        game.state, None, "choice", rng, loaded.balance, loaded.game_data
    )
    from tst.sim.state import ceo_of

    ceo = ceo_of(state, 1)
    assert ceo is not None and state.family is not None
    assert state.family.head_mode == "family_head"
    assert ceo.person_id not in rules.family_people(state)
    assert state.founder_of(1).id == game.founder_id  # type: ignore[union-attr]


def test_health_step_back_chance(loaded: LoadedData) -> None:
    assert step_back_chance(69, loaded.balance) == 0
    assert step_back_chance(70, loaded.balance) == pytest.approx(0.05)
    assert step_back_chance(75, loaded.balance) == pytest.approx(0.30)


def test_board_removal_opens_succession_not_game_over(loaded: LoadedData) -> None:
    game, _kids = _heir_game(loaded)
    assert succession.can_succeed_on_removal(game.state, loaded.balance) == bool(
        rules.eligible_heirs(game.state, loaded.balance, "developing")
    )
    state, _logs = succession.on_removal(game.state, loaded.balance)
    assert state.family is not None and state.family.succession_open == "board"
    assert any(q.template_id == "family_succession" for q in state.queued)
    assert not state.ended


# --- Sub-task 7: estate planning and tax -----------------------------------------------------


def test_estate_rules_by_year(loaded: LoadedData) -> None:
    from tst.sim.calendar import ym_to_turn

    b = loaded.balance
    assert estate.rule(b, "north_america", ym_to_turn(2012, 6)).exemption_cents == 512_000_000
    assert estate.rule(b, "north_america", ym_to_turn(2030, 1)).exemption_cents == 1_500_000_000
    assert estate.rule(b, "east_asia", ym_to_turn(2014, 1)).rate == 0.50
    assert estate.rule(b, "oceania", ym_to_turn(2020, 1)).rate == 0.0


def test_estate_quote_and_settlement(loaded: LoadedData) -> None:
    game, kids = _heir_game(loaded)
    state = game.state
    old = game.founder_id
    q = estate.quote(state, old, game.balances, loaded.balance, loaded.game_data)
    expected_tax = round(max(0, q.estate_cents - q.exemption_cents) * q.rate)
    assert q.tax_cents == pytest.approx(expected_tax, abs=1)
    cid = listed_id(state)
    total = fd_shares(state, cid)
    held = person_shares(state, cid, old)
    state, _ = estate.settle(state, old, kids[0], game.balances, loaded.balance, loaded.game_data)
    assert fd_shares(state, cid) == total  # shares move, never appear or vanish
    assert person_shares(state, cid, old) == 0
    assert person_shares(state, cid, kids[0]) == held - q.shares_to_sell + person_shares(
        game.state, cid, kids[0]
    )
    assert state.family is not None and state.family.estate_tax_cents == q.tax_cents


def test_gifts_use_the_exemption_then_pay_tax(loaded: LoadedData) -> None:
    game, kids = _heir_game(loaded)
    head = game.founder_id
    state = with_cash(game.state, head, 10_000_000_00)
    cid = listed_id(state)
    shares = person_shares(state, cid, head) // 10
    state, _log = estate.gift_shares(
        state, kids[0], shares, game.balances, loaded.balance, loaded.game_data
    )
    assert person_shares(state, cid, kids[0]) == shares
    assert state.family is not None and state.family.lifetime_gifts_cents > 0


def test_a_trust_keeps_shares_in_the_family(loaded: LoadedData) -> None:
    game, _ = _heir_game(loaded)
    head = game.founder_id
    state = with_cash(game.state, head, 1_000_000_00)
    cid = listed_id(state)
    before = rules.family_bp(state)
    shares = person_shares(state, cid, head) // 2
    state, _ = estate.fund_trust(state, shares, loaded.balance)
    assert rules.family_bp(state) == before  # the trust's shares are still the family's
    trust = [e for e in state.company_cap(cid) if e.name == TRUST_HOLDER]
    assert sum(e.shares for e in trust) == shares
    q = estate.quote(state, head, game.balances, loaded.balance, loaded.game_data)
    assert q.shares == person_shares(state, cid, head)  # outside the estate
    assert cash_cents(state, head) == 1_000_000_00 - loaded.balance.family.trust_setup_cents


# --- Sub-task 8: the dynasty -----------------------------------------------------------------


def test_dynasty_score(loaded: LoadedData) -> None:
    game, _kids = _heir_game(loaded)
    d = dynasty.dynasty(game.state, game.balances, loaded.balance, loaded.game_data)
    assert d is not None and len(d.generations) == 1
    assert d.total == round(d.legacies + d.value_points - d.loss_points)
    family = game.state.family
    assert family is not None
    game.state = replace(game.state, family=replace(family, control_losses=2))
    d2 = dynasty.dynasty(game.state, game.balances, loaded.balance, loaded.game_data)
    assert d2 is not None and d2.loss_points == 100


def test_the_default_founder_can_start_with_a_partner(loaded: LoadedData) -> None:
    game = family_game(loaded, 1, age=28, setting="partner")
    assert family_partner(game.state) is not None and not rules.children(game.state)
