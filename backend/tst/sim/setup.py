"""Game creation: the initial state and the turn-0 starting cash entry (formulas.md 8a)."""

from __future__ import annotations

from typing import Final

from tst.sim.data_models import Balance, GameData, Scenario
from tst.sim.errors import (
    InvalidCompanyNameError,
    ScenarioUnavailableError,
    UnknownDifficultyError,
    UnknownScenarioError,
)
from tst.sim.ledger import CASH, LedgerEntry
from tst.sim.money import Cents, pct_of
from tst.sim.people.founder import FounderSpec, build_founder
from tst.sim.people.models import FOUNDER_ROLE, Employment
from tst.sim.people.reveal import new_reveal_state
from tst.sim.rng import RngFactory
from tst.sim.state import CompanyState, GameState, SaveMeta

PLAYER_COMPANY_ID: Final = 1
FOUNDER_PERSON_ID: Final = 1
FOUNDER_EMPLOYMENT_ID: Final = 1
FOUNDER_LEVEL: Final = "exec"
DEFAULT_FOUNDER: Final = FounderSpec(background="engineer")  # CLI and API default
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
    founder: FounderSpec,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    """Return the turn-0 state and the opening ledger entries. The caller persists both.

    The state holds the player company, its founder (formulas.md section 5), the founder's
    employment (role founder, level exec, salary 0, equity 0) and the company's exact
    knowledge of its founder.
    """
    if not scenario.selectable:
        raise ScenarioUnavailableError(
            f"scenario {scenario.id!r} unlocks in {scenario.available_in}"
        )
    name = company_name.strip()
    if not name or len(name) > MAX_COMPANY_NAME:
        raise InvalidCompanyNameError(f"company name must be 1..{MAX_COMPANY_NAME} characters")

    cash = starting_cash_cents(balance, scenario.id, difficulty)
    rng = RngFactory(master_seed)
    person = build_founder(founder, rng, data, balance, START_TURN, person_id=FOUNDER_PERSON_ID)
    employment = Employment(
        id=FOUNDER_EMPLOYMENT_ID,
        person_id=person.id,
        company_id=PLAYER_COMPANY_ID,
        role=FOUNDER_ROLE,
        level=FOUNDER_LEVEL,
        salary_cents=0,
        equity_bp=0,
        start_turn=START_TURN,
        end_turn=None,
        status="active",
    )
    reveal = new_reveal_state(
        observer_company_id=PLAYER_COMPANY_ID,
        person=person,
        turn=START_TURN,
        rng=rng,
        data=data,
        balance=balance,
        knows_exactly=True,
    )
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
        people=(person,),
        employments=(employment,),
        reveals=(reveal,),
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
