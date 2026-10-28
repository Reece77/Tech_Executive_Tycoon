"""The cap table at game start (docs/formulas.md 14.2): the founder's common, the option
pool, other common holders, and the funded spinout's closed seed with its board seat."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData, Scenario
from tst.sim.finance.board import seat_board
from tst.sim.finance.models import POOL_NAME, CapEntry, FundingRound
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_cap_entry, with_round


def _entry(state: GameState, **fields: object) -> GameState:
    entry_id, ids = state.next_ids.take("cap_entry")
    entry = CapEntry(id=entry_id, acquired_turn=state.turn, **fields)  # type: ignore[arg-type]
    return with_cap_entry(replace(state, next_ids=ids), entry)


def initial_cap_table(
    state: GameState,
    company_id: int,
    founder_id: int,
    scenario: Scenario,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> GameState:
    """Holdings from scenarios.yaml; they sum to finance.initial_fd_shares (checked at load)."""
    cap = scenario.cap_table
    state = _entry(
        state,
        company_id=company_id,
        holder_kind="person",
        share_class="common",
        shares=cap.founder,
        person_id=founder_id,
    )
    state = _entry(
        state,
        company_id=company_id,
        holder_kind="pool",
        share_class="option_pool",
        shares=cap.pool,
        name=POOL_NAME,
    )
    for group in cap.others:
        state = _entry(
            state,
            company_id=company_id,
            holder_kind="group",
            share_class="common",
            shares=group.shares,
            name=group.name,
        )
    if cap.seed is None:
        return state
    seed = cap.seed
    fd_before = cap.total - seed.shares
    round_id, ids = state.next_ids.take("round")
    state = replace(state, next_ids=ids)
    # Pre-money at the seed's price per share: amount / shares x shares before the round.
    pre_money = seed.amount_cents * fd_before // seed.shares
    state = with_round(
        state,
        FundingRound(
            id=round_id,
            company_id=company_id,
            series="seed",
            status="closed",
            target_cents=seed.amount_cents,
            opened_turn=state.turn,
            expires_turn=state.turn,
            closed_turn=state.turn,
            lead_firm=seed.lead,
            pre_money_cents=pre_money,
            amount_cents=seed.amount_cents,
            fd_before=fd_before,
            pool_shares=0,
            safe_shares=0,
            new_shares=seed.shares,
            fd_pre=fd_before,
        ),
    )
    state = _entry(
        state,
        company_id=company_id,
        holder_kind="firm",
        share_class="preferred_seed",
        shares=seed.shares,
        firm=seed.lead,
        round_id=round_id,
    )
    state, _ = seat_board(
        state, company_id, "seed", seed.lead, round_id, rng, balance, data, founder_id=founder_id
    )
    return state  # a seed board has no nominee seat
