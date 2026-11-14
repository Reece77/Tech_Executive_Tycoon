"""M27b automation for the chain (docs/formulas.md 40.7): subsidiaries on the Automation screen
(sub-task 1), the chain's areas (sub-tasks 2-8), headcount targets (9), limits and one-offs
(property tests, target (c)) and what must not move (40.9)."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

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
        assert "run by the group" in (owners.cant_automate(state, sub, area, B, LOADED.game_data) or "")
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
    game, sub, ceo = _group()
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
    state = with_area_owner(
        game.state, AreaOwner(sub, "hiring", ceo, LIMIT, 0, game.state.turn)
    )
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
