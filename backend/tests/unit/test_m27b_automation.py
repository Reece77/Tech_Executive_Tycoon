"""M27b automation for the chain (docs/formulas.md 40.7): subsidiaries on the Automation screen
(sub-task 1), the chain's areas (sub-tasks 2-8), headcount targets (9), limits and one-offs
(property tests, target (c)) and what must not move (40.9)."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.conftest import DATA_DIR
from tst.balance.game import PLAYER, Game, start_game
from tst.balance.m27b import add_staff_at
from tst.loader import load_all
from tst.sim.actions.authority import AnswerProposal
from tst.sim.automation import owners, scope
from tst.sim.automation.actions import SetAreaOwner, SetAreaSettings, TakeBackArea
from tst.sim.automation.models import AreaOwner
from tst.sim.automation.run import AutoRun, automation_month
from tst.sim.errors import OrgRuleError
from tst.sim.exploration.pipeline import StartDeskStudy
from tst.sim.ledger import CASH
from tst.sim.mining.actions import FoundSubsidiary
from tst.sim.rng import RngFactory
from tst.sim.state import with_area_owner, with_person_state

LOADED = load_all(DATA_DIR)
B = LOADED.balance
SUB_CENTS = 50_000_000_000  # $500M: the subsidiary's capital
LIMIT = 100_000_000  # $1M


def _energy(game: Game) -> None:
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))


def _stage3(game: Game) -> None:
    player = game.state.player
    companies = tuple(
        replace(c, stage=max(3, c.stage)) if c.id == player.id else c for c in game.state.companies
    )
    game.state = replace(game.state, companies=companies)


def _group(seed: int = 1) -> tuple[Game, int, int]:
    """A stage-3 game with a subsidiary whose CEO (its leader) and a geologist are on staff:
    (game, subsidiary id, CEO id)."""
    game = start_game(LOADED, seed)
    game.balances[(PLAYER, CASH)] = game.balances.get((PLAYER, CASH), 0) + 2 * SUB_CENTS
    _stage3(game)
    _energy(game)
    before = {c.id for c in game.state.companies}
    assert game.act(FoundSubsidiary(game.founder_id, "Minerals", "oceania", SUB_CENTS)), dict(
        game.refused
    )
    (sub,) = {c.id for c in game.state.companies} - before
    (ceo,) = add_staff_at(game, sub, "operations_manager", "exec", 1, skill=16.0)
    add_staff_at(game, sub, "geologist", "senior", 1, skill=12.0)
    _energy(game)
    return game, sub, ceo


# --- Sub-task 1: subsidiaries ---------------------------------------------------------------


def test_new_areas_are_appended_after_m27a_s_twelve() -> None:
    keys = owners.area_keys(B)
    assert keys[:12] == (
        "hiring",
        "engineering",
        "products",
        "pricing",
        "marketing",
        "support",
        "treasury",
        "research",
        "regions",
        "cloud",
        "press",
        "events",
    )
    assert keys[12:] == (
        "production",
        "supply",
        "exploration",
        "mines",
        "fabs",
        "government",
        "corp_dev",
    )


def test_a_subsidiary_s_ceo_may_own_its_chain_areas_but_not_the_player_s_seat_areas() -> None:
    game, sub, ceo = _group()
    state = game.state
    assert scope.companies(state) == [PLAYER, sub]
    assert scope.subsidiary_ceo(state, sub) == ceo
    for area in ("hiring", "production", "supply", "exploration", "mines", "fabs", "corp_dev"):
        assert owners.owner_kind(state, sub, area, ceo, B) == "subsidiary_ceo", area
    for area in ("pricing", "engineering", "regions", "press"):
        assert owners.owner_kind(state, sub, area, ceo, B) is None, area
        assert "run by the group" in (
            owners.cant_automate(state, sub, area, B, LOADED.game_data) or ""
        )
    # the player's company: the subsidiary's CEO is nobody there
    assert owners.owner_kind(state, PLAYER, "mines", ceo, B) is None


def test_the_founder_gives_a_subsidiary_s_area_to_its_ceo_and_takes_it_back() -> None:
    game, sub, ceo = _group()
    assert game.act(SetAreaOwner(game.founder_id, "exploration", ceo, company_id=sub)), dict(
        game.refused
    )
    owner = game.state.area_owner(sub, "exploration")
    assert owner is not None and owner.person_id == ceo
    assert game.state.area_owner(PLAYER, "exploration") is None
    _energy(game)
    assert game.act(
        SetAreaSettings(game.founder_id, "exploration", company_id=sub, budget_cents=10**9)
    )
    assert game.state.area_owner(sub, "exploration").budget_cents == 10**9  # type: ignore[union-attr]
    _energy(game)
    assert game.act(TakeBackArea(game.founder_id, "exploration", company_id=sub))
    assert game.state.area_owner(sub, "exploration") is None


def test_only_the_group_s_own_subsidiaries_can_be_automated() -> None:
    game, _sub, ceo = _group()
    rival = next(c.id for c in game.state.companies if c.is_rival and c.alive)
    from tst.sim.actions import apply_action

    with pytest.raises(OrgRuleError, match="subsidiaries"):
        apply_action(
            game.state,
            SetAreaOwner(game.founder_id, "exploration", ceo, company_id=rival),
            RngFactory(1),
            B,
            LOADED.game_data,
            game.balances,
            seq=0,
        )


def _run(game: Game, owner: AreaOwner) -> AutoRun:
    return AutoRun(
        state=game.state,
        balances=dict(game.balances),
        rng=RngFactory(game.state.save_meta.master_seed),
        balance=B,
        data=LOADED.game_data,
        owner=owner,
        area_index=owners.area_index(B, owner.area),
    )


def test_a_subsidiary_s_area_decisions_post_to_its_own_ledger() -> None:
    game, sub, ceo = _group()
    owner = AreaOwner(sub, "exploration", ceo, LIMIT, 0, game.state.turn, budget_cents=10**9)
    run = _run(game, owner)
    founder_energy = game.state.person_state(game.founder_id).energy
    action = StartDeskStudy(ceo, "oceania", "lithium_carbonate", company_id=sub)
    assert run.attempt(sub, action)
    assert run.entries
    assert {entry.company_id for entry in run.entries} == {sub}
    assert run.balances[(sub, CASH)] < game.balances[(sub, CASH)]
    assert run.balances.get((PLAYER, CASH)) == game.balances.get((PLAYER, CASH))
    # carried out in the founder's name (the group's exploration), at the owner's workload
    assert run.state.person_state(game.founder_id).energy == founder_energy


def test_a_one_off_inside_a_subsidiary_reaches_the_player_as_a_proposal() -> None:
    from tst.sim.mining.actions import BuildMine

    game, sub, ceo = _group()
    owner = AreaOwner(sub, "exploration", ceo, LIMIT, 0, game.state.turn)
    run = _run(game, owner)
    run.text = "build a mine"
    assert not run.attempt(sub, BuildMine(ceo, 999, 1000.0))  # a one-off: never carried out
    (proposal,) = run.state.pending_proposals(PLAYER)
    assert proposal.kind == "auto" and proposal.person_id == ceo
    assert scope.acting_for(proposal) == sub
    assert "Minerals" in proposal.text
    assert any(i.template == "exec_proposal" and i.company_id == PLAYER for i in run.logs)
    # the group's mines are the founder's to act on; anything else runs as the proposer
    assert scope.proposal_actor(run.state, proposal, game.founder_id) == game.founder_id
    other = replace(
        proposal,
        params=tuple(
            (k, json.dumps({**json.loads(str(v)), "kind": "create_plan"}) if k == "action" else v)
            for k, v in proposal.params
        ),
    )
    assert scope.proposal_actor(run.state, other, game.founder_id) == ceo


def test_the_mandate_s_capex_limit_is_the_subsidiary_s_guardrail() -> None:
    from tst.sim.group.models import Mandate
    from tst.sim.state import with_mandate

    game, sub, ceo = _group()
    state = with_mandate(game.state, Mandate(sub, "grow", 0, capex_limit_cents=LIMIT // 4))
    owner = AreaOwner(sub, "exploration", ceo, LIMIT, 0, state.turn)
    assert scope.guarded(state, owner).limit_cents == LIMIT // 4
    assert scope.guarded(game.state, owner).limit_cents == LIMIT
    player_owner = replace(owner, company_id=PLAYER)
    assert scope.guarded(state, player_owner).limit_cents == LIMIT


def test_a_subsidiary_s_month_runs_in_its_own_name_and_the_digest_names_it() -> None:
    from tst.sim.automation import digest

    game, sub, ceo = _group()
    state = with_area_owner(game.state, AreaOwner(sub, "hiring", ceo, LIMIT, 0, game.state.turn))
    out, _, _, _ = automation_month(state, RngFactory(1), B, LOADED.game_data, game.balances)
    lines = [d for d in out.area_decisions if d.turn == state.turn]
    assert lines and {d.company_id for d in lines} == {sub}
    d = digest.build(out, state.turn, B, LOADED.game_data)
    assert d is not None
    assert d.areas[0].label.startswith(game.state.company(sub).name)
    assert d.areas[0].company_id == sub


def test_approving_a_subsidiary_proposal_runs_as_its_owner() -> None:
    from tst.sim.actions import CreatePlan

    game, sub, ceo = _group()
    owner = AreaOwner(sub, "hiring", ceo, 1, 0, game.state.turn)  # a $0.01 limit: all proposals
    run = _run(game, owner)
    run.text = "open a plan"
    plan = CreatePlan(ceo, ceo, "geologist", 1, "any", B.delegates.max_ratio_bp, 0, None)
    assert not run.attempt(sub, plan)
    (proposal,) = run.state.pending_proposals(PLAYER)
    game.state = run.state
    _energy(game)
    assert game.act(AnswerProposal(game.founder_id, proposal.id, True)), dict(game.refused)
    (made,) = [p for p in game.state.plans if p.company_id == sub]
    assert made.role == "geologist"


# --- Sub-tasks 2-8: the chain's areas -------------------------------------------------------


def _chain_run(state, balances, owner: AreaOwner, seed: int = 1) -> AutoRun:  # type: ignore[no-untyped-def]
    return AutoRun(
        state=state,
        balances=dict(balances),
        rng=RngFactory(seed),
        balance=B,
        data=LOADED.game_data,
        owner=owner,
        area_index=owners.area_index(B, owner.area),
    )


def _kinds(run: AutoRun) -> list[str]:
    return [k for k, *_ in run.decisions]


@pytest.fixture(scope="module")
def device_game() -> Game:
    """M12b's device company on a 1,000-unit contract (demand well above it), a month played,
    with a senior manufacturing engineer and a procurement manager at skill 20."""
    from tst.balance import m12b

    game, _ = m12b.device_company(1, own_chip=False, units=1000)
    game.turn()
    add_staff_at(game, PLAYER, "manufacturing_engineer", "senior", 1, skill=20.0)
    add_staff_at(game, PLAYER, "procurement_manager", "senior", 1, skill=20.0)
    add_staff_at(game, PLAYER, "public_policy_manager", "senior", 1, skill=20.0)
    return game


def _lead(game: Game, role: str) -> int:
    return next(e.person_id for e in game.state.staff(PLAYER) if e.role == role)


def test_device_production_orders_cover_below_the_guardrail(device_game: Game) -> None:
    from tst.sim.automation import chain

    game = device_game
    (pid,) = chain.device_products(game.state, PLAYER, B)
    demand, supply = chain.device_cover(game.state, pid, B, game.state.turn + 1)
    weeks = chain.cover_weeks(demand, supply)
    assert weeks is not None and weeks < 4
    owner = AreaOwner(PLAYER, "production", _lead(game, "manufacturing_engineer"), 10**13, 0, 0)
    run = _chain_run(game.state, game.balances, owner)
    chain.production(run, owner, LOADED.game_data)
    assert _kinds(run)[0] in ("decision", "mistake")
    signed = [
        c
        for c in run.state.production_contracts
        if c.product_id == pid and c.signed_turn == game.state.turn
    ]
    assert len(signed) == 1
    _, after = chain.device_cover(run.state, pid, B, game.state.turn + 1)
    target = B.automation.areas["production"].guardrails["order_weeks"]
    if _kinds(run)[0] == "decision":
        assert chain.cover_weeks(demand, after) == pytest.approx(target, abs=0.01)
    # the order commits its take-or-pay over the term, under the limit
    assert run.decisions[0][2] > 0


def test_device_production_s_order_over_the_limit_is_a_proposal(device_game: Game) -> None:
    from tst.sim.automation import chain

    game = device_game
    owner = AreaOwner(PLAYER, "production", _lead(game, "manufacturing_engineer"), 1_000, 0, 0)
    run = _chain_run(game.state, game.balances, owner)
    chain.production(run, owner, LOADED.game_data)
    assert "proposal" in _kinds(run)
    assert len(run.state.production_contracts) == len(game.state.production_contracts)


def test_supply_covers_each_input_below_the_band_best_terms_first(device_game: Game) -> None:
    from tst.sim.automation import chain

    game = device_game
    needs = chain.supply_needs(game.state, PLAYER, B, LOADED.game_data)
    assert needs and all(n.cover < 0.6 for n in needs)
    owner = AreaOwner(PLAYER, "supply", _lead(game, "procurement_manager"), 10**13, 0, 0)
    run = _chain_run(game.state, game.balances, owner)
    chain.supply(run, owner, LOADED.game_data)
    acted = [d for d in run.decisions if d[0] in ("decision", "mistake")]
    assert acted
    deals = [d for d in run.state.commodity_deals if d.company_id == PLAYER]
    assert deals
    after = {n.good: n.cover for n in chain.supply_needs(run.state, PLAYER, B, LOADED.game_data)}
    for d in deals:
        assert after[d.good] >= 0.6 - 1e-6
    # the ranking: allied suppliers before the rest, then price; never a termination
    good = needs[0].good
    options = chain.supply_options(game.state, PLAYER, good, 1.0, B, LOADED.game_data)
    keys = [o[0] for o in options]
    assert keys == sorted(keys)


def test_exploration_is_off_until_the_player_sets_a_budget() -> None:
    from tst.balance import m19
    from tst.sim.automation import chain

    run = m19.miner(LOADED, 1)
    geologist = next(e.person_id for e in run.state.staff(PLAYER) if e.role == "geologist")
    assert run.act(StartDeskStudy(run.founder, "oceania", "lithium_carbonate")) is not None
    study = run.state.desk_studies[-1]
    state = replace(
        run.state,
        desk_studies=tuple(
            replace(s, done_turn=run.state.turn, bands=("high",) * 60) if s.id == study.id else s
            for s in run.state.desk_studies
        ),
    )
    off = AreaOwner(PLAYER, "exploration", geologist, 10**12, 0, 0)
    auto = _chain_run(state, run.balances, off)
    chain.exploration(auto, off, LOADED.game_data)
    assert auto.decisions == [] and auto.state == state
    on = replace(off, budget_cents=10**10)
    auto = _chain_run(state, run.balances, on)
    chain.exploration(auto, on, LOADED.game_data)
    assert [k for k in _kinds(auto)] in (["decision"], ["mistake"])
    assert len([p for p in auto.state.projects if p.company_id == PLAYER]) == 1


def test_a_permitted_project_s_mine_is_a_one_off_with_its_study_npv() -> None:
    from tst.balance import m19
    from tst.sim.automation import chain

    run = m19.miner(LOADED, 1)
    project = m19.permitted_project(run, "copper")
    geologist = next(e.person_id for e in run.state.staff(PLAYER) if e.role == "geologist")
    owner = AreaOwner(PLAYER, "exploration", geologist, 10**15, 0, 0, budget_cents=10**10)
    auto = _chain_run(run.state, run.balances, owner)
    chain.exploration(auto, owner, LOADED.game_data)
    assert not auto.state.mines  # never built by the owner
    (proposal,) = auto.state.pending_proposals(PLAYER)
    params = dict(proposal.params)
    assert json.loads(str(params["action"]))["kind"] == "build_mine"
    assert int(params["central_cents"]) == project.npv_mid_cents


def test_mines_are_staffed_routed_to_the_group_and_kept_at_the_safety_guardrail() -> None:
    from tst.balance import m19
    from tst.sim.automation import chain
    from tst.sim.mining.actions import BuildMine

    run = m19.miner(LOADED, 1)
    p = m19.permitted_project(run, "copper")
    assert run.act(BuildMine(run.founder, p.id)) is not None
    mine = run.state.mines[-1]
    from tst.sim.mining import formulas as mf

    need = mf.staff_needed(mine.capacity_t, B.mining.staff_per_kt)
    uid = m19.add_engineers(run, need, 12.0)
    lead = next(e.person_id for e in run.state.staff(PLAYER) if e.unit_id == uid)
    state = run.state
    state = replace(
        state, mines=tuple(replace(m, safety="low") if m.id == mine.id else m for m in state.mines)
    )
    owner = AreaOwner(PLAYER, "mines", lead, 10**12, 0, 0)
    auto = _chain_run(state, run.balances, owner)
    chain.mines(auto, owner, LOADED.game_data)
    assert auto.state.facility(mine.id).unit_id == uid  # type: ignore[union-attr]
    assert auto.state.mine(mine.id).safety == "normal"  # type: ignore[union-attr]
    # founder-only actions in the founder's name: the founder's energy is as it was
    assert auto.state.person_state(run.founder).energy == state.person_state(run.founder).energy


def test_fab_spare_starts_go_under_contract_at_the_best_price_above_the_margin() -> None:
    from tst.balance import m21
    from tst.sim.automation import chain
    from tst.sim.fabs import foundry as fc

    game = m21.game_at(1, m21.ym_to_turn(2018, 1))
    fid = m21.build(game, "n28", "east_asia", 10_000)
    m21.play(game, 2)
    m21.keep_staffed(game)
    (lead,) = add_staff_at(game, PLAYER, "fab_manager", "senior", 1, skill=20.0)
    owner = AreaOwner(PLAYER, "fabs", lead, 10**13, 0, 0)
    auto = _chain_run(game.state, game.balances, owner)
    chain.fabs(auto, owner, LOADED.game_data)
    contracts = fc.running(auto.state, fid)
    signed = [c for c in contracts if c.signed_turn == game.state.turn]
    fab = auto.state.fabs[-1]
    assert fab.month is not None
    cap = auto.state.facility(fid).capacity  # type: ignore[union-attr]
    assert sum(c.monthly_starts for c in contracts) <= cap * 0.8 + 1e-6
    assert signed  # spare starts at the slot price, well above the cash cost a start
    for c in signed:
        assert c.price_millicents / 1000 >= chain.cash_cost_per_start(fab.month) * 1.2 - 1


def test_corporate_development_screens_then_pitches_a_bid_as_a_proposal() -> None:
    from tst.sim.automation import chain
    from tst.sim.mna.models import TargetFile
    from tst.sim.state import target_file, with_target_file

    game, _, _ = _group()
    (lead,) = add_staff_at(game, PLAYER, "corporate_development_manager", "senior", 1, skill=20.0)
    from tests.helpers import with_product

    state = replace(game.state, turn=game.state.turn + (-game.state.turn) % 3)
    categories = sorted(
        {
            p.category
            for p in state.products
            if p.company_id != PLAYER
            and p.status == "live"
            and state.company(p.company_id).is_rival
        }
    )
    state = with_product(state, category=categories[0], prices={}, root=False)
    game.balances[(PLAYER, CASH)] = game.balances[(PLAYER, CASH)] + 10**15
    ranked = chain.corp_targets(state, PLAYER, game.balances, B, LOADED.game_data)
    assert ranked
    owner = AreaOwner(PLAYER, "corp_dev", lead, 10**15, 0, 0, budget_cents=10**10)
    auto = _chain_run(state, game.balances, owner)
    chain.corp_dev(auto, owner, LOADED.game_data)
    started = [t for t in state.companies if target_file(auto.state, PLAYER, t.id) is not None]
    assert started  # diligence began on the best (or, a misstep, the second) target
    tid = started[0].id
    done = replace(
        target_file(auto.state, PLAYER, tid) or TargetFile(PLAYER, tid),
        diligence_turn=state.turn,
        diligence_done_turn=state.turn,
    )
    later = with_target_file(auto.state, done)
    auto = _chain_run(later, game.balances, owner)
    chain.corp_dev(auto, owner, LOADED.game_data)
    bids = [
        p
        for p in auto.state.pending_proposals(PLAYER)
        if json.loads(str(dict(p.params)["action"]))["kind"] == "bid_for_company"
    ]
    assert len(bids) == 1 and "displayed value" in bids[0].text
    assert not any(d.target_id == tid for d in auto.state.deals)  # a bid is never the owner's


def test_government_lobbies_within_the_yearly_budget_and_never_takes_a_grey_route(
    device_game: Game,
) -> None:
    from tst.sim.automation import chain
    from tst.sim.state import influence_of

    game = device_game
    lead = _lead(game, "public_policy_manager")
    owner = AreaOwner(PLAYER, "government", lead, 10**12, 0, 0, budget_cents=12 * 5_000_000)
    auto = _chain_run(game.state, game.balances, owner)
    chain.government(auto, owner, LOADED.game_data)
    home = B.founder.default_region
    record = influence_of(auto.state, PLAYER, home)
    assert record is not None and record.spend_cents == 5_000_000
    assert all(a.kind != "set_grey_route" for _, a in auto.taken)


# --- Limits and one-offs over the chain (property tests; target (c)) -------------------------

CHAIN_AREAS = {
    "production": "manufacturing_engineer",
    "supply": "procurement_manager",
    "government": "public_policy_manager",
}


@settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    limit=st.integers(min_value=1, max_value=10**12),
    seed=st.integers(min_value=1, max_value=10_000),
    areas=st.lists(st.sampled_from(sorted(CHAIN_AREAS)), min_size=1, max_size=3, unique=True),
    budget=st.integers(min_value=0, max_value=10**9),
)
def test_no_chain_owner_commits_at_or_above_its_limit_or_runs_a_one_off(
    device_game: Game, limit: int, seed: int, areas: list[str], budget: int
) -> None:
    from tst.sim.automation.config import NEVER_ACTIONS, ONE_OFF_ACTIONS

    game = device_game
    state = game.state
    for i, area in enumerate(areas):
        lead = _lead(game, CHAIN_AREAS[area])
        state = with_area_owner(
            state, AreaOwner(PLAYER, area, lead, limit, i, 0, budget_cents=budget)
        )
    out, _, _, taken = automation_month(state, RngFactory(seed), B, LOADED.game_data, game.balances)
    assert len(out.area_owners) == len(areas)  # every owner still valid: all of them ran
    for _, action in taken:
        assert action.kind not in ONE_OFF_ACTIONS
        assert action.kind not in NEVER_ACTIONS
    lines = [
        d for d in out.area_decisions if d.turn == state.turn and d.kind in ("decision", "mistake")
    ]
    for d in lines:
        assert d.commitment_cents < limit or d.commitment_cents == 0
    by_area: dict[str, int] = {}
    for d in lines:
        by_area[d.area] = by_area.get(d.area, 0) + d.commitment_cents
    for total in by_area.values():
        assert total <= B.automation.monthly_limit_mult * limit


def test_no_owner_ever_terminates_a_contract_or_takes_the_grey_route() -> None:
    """Target (c): both are one-offs; and even past that test the runner refuses them."""
    from tst.sim.automation import limits
    from tst.sim.contracts.termination import TerminateContract
    from tst.sim.geopolitics.actions import SetGreyRoute

    game, _sub, ceo = _group()
    for action in (TerminateContract(ceo, "commodity", 1), SetGreyRoute(ceo, 1, "china")):
        assert limits.is_one_off(game.state, PLAYER, action, B)
        run = _run(game, AreaOwner(PLAYER, "supply", ceo, LIMIT, 0, 0))
        assert not run.attempt(PLAYER, action)
        assert run.taken == []


# --- Sub-task 9: headcount targets ----------------------------------------------------------


def test_hiring_fills_the_headcount_target_the_player_set_per_unit(device_game: Game) -> None:
    from tst.sim.actions import CreateUnit
    from tst.sim.automation import rules
    from tst.sim.automation.actions import SetHeadcountTarget

    game = _fork_game(device_game)
    _energy(game)
    uid = game.state.next_ids.unit
    assert game.act(CreateUnit(game.founder_id, "team", "Plant crew")), dict(game.refused)
    assert game.act(SetHeadcountTarget(game.founder_id, uid, "manufacturing_engineer", 5))
    assert rules.target_gaps(game.state, PLAYER) == [(uid, "manufacturing_engineer", 5)]
    (recruiter,) = add_staff_at(game, PLAYER, "recruiter", "senior", 1, skill=20.0)
    owner = AreaOwner(PLAYER, "hiring", recruiter, 10**12, 0, 0)
    run = _chain_run(game.state, game.balances, owner)
    rules.hiring(run, owner, LOADED.game_data)
    plans = [p for p in run.state.plans if p.unit_id == uid]
    if _kinds(run) == ["mistake"]:
        assert plans == []
    else:
        (plan,) = plans
        assert (plan.role, plan.target, plan.owner_id) == ("manufacturing_engineer", 5, recruiter)
        assert rules.target_gaps(run.state, PLAYER) == []
    assert game.act(SetHeadcountTarget(game.founder_id, uid, "manufacturing_engineer", 0))
    assert game.state.headcount_targets == ()


def test_a_headcount_target_needs_a_unit_of_the_company() -> None:
    from tst.sim.actions import apply_action
    from tst.sim.automation.actions import SetHeadcountTarget
    from tst.sim.errors import InvalidActionError

    game = start_game(LOADED, 1)
    with pytest.raises(InvalidActionError, match="no unit"):
        apply_action(
            game.state,
            SetHeadcountTarget(game.founder_id, 9_999, "recruiter", 2),
            RngFactory(1),
            B,
            LOADED.game_data,
            game.balances,
            seq=0,
        )


def _fork_game(game: Game) -> Game:
    from tst.balance.m27b import _fork

    return _fork(game)
