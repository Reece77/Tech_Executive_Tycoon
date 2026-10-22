"""Game creation: the initial state and the turn-0 starting cash entry (formulas.md 8a)."""

from __future__ import annotations

from typing import Final

from tst.sim.data_models import Balance, Scenario
from tst.sim.errors import (
    InvalidCompanyNameError,
    ScenarioUnavailableError,
    UnknownDifficultyError,
    UnknownScenarioError,
)
from tst.sim.ledger import CASH, LedgerEntry
from tst.sim.money import Cents, pct_of
from tst.sim.state import CompanyState, GameState, SaveMeta

PLAYER_COMPANY_ID: Final = 1
START_TURN: Final = 0
START_STAGE: Final = 0  # solo founder (spec section 3)
MAX_COMPANY_NAME: Final = 80  # tunable-exempt: column width of company.name


def starting_cash_cents(balance: Balance, scenario_id: str, difficulty: str) -> Cents:
    scenario = balance.scenario.get(scenario_id)
    if scenario is None:
        raise UnknownScenarioError(f"unknown scenario {scenario_id!r}")
    level = balance.difficulty.get(difficulty)
    if level is None:
        raise UnknownDifficultyError(f"unknown difficulty {difficulty!r}")
    return pct_of(scenario.starting_cash_cents, level.starting_cash_mult_bp)


def new_game(
    *,
    save_name: str,
    master_seed: int,
    scenario: Scenario,
    difficulty: str,
    company_name: str,
    balance: Balance,
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    """Return the turn-0 state and the opening ledger entries. The caller persists both."""
    if not scenario.selectable:
        raise ScenarioUnavailableError(
            f"scenario {scenario.id!r} unlocks in {scenario.available_in}"
        )
    name = company_name.strip()
    if not name or len(name) > MAX_COMPANY_NAME:
        raise InvalidCompanyNameError(f"company name must be 1..{MAX_COMPANY_NAME} characters")

    cash = starting_cash_cents(balance, scenario.id, difficulty)
    state = GameState(
        save_meta=SaveMeta(
            name=save_name,
            master_seed=master_seed,
            scenario_id=scenario.id,
            difficulty=difficulty,
        ),
        turn=START_TURN,
        companies=(
            CompanyState(
                id=PLAYER_COMPANY_ID,
                name=name,
                is_player=True,
                stage=START_STAGE,
                founded_turn=START_TURN,
            ),
        ),
    )
    entries: tuple[LedgerEntry, ...] = ()
    if cash:
        entries = (
            LedgerEntry.transfer(
                turn=START_TURN,
                company_id=PLAYER_COMPANY_ID,
                memo="Starting cash",
                debit=CASH,
                credit=scenario.starting_equity_account,
                amount=cash,
            ),
        )
    return state, entries
