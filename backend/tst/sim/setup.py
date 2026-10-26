"""Game creation: the initial state and the turn-0 starting cash entry (formulas.md 8a)."""

from __future__ import annotations

from typing import Final

from tst.sim.data_models import Balance, GameData, Scenario
from tst.sim.errors import (
    InvalidCompanyNameError,
    InvalidMissionError,
    ScenarioUnavailableError,
    UnknownDifficultyError,
    UnknownScenarioError,
)
from tst.sim.hiring.models import NextIds, PersonState
from tst.sim.ledger import CASH, LedgerEntry
from tst.sim.money import Cents, pct_of
from tst.sim.people.founder import FounderSpec, build_founder
from tst.sim.people.models import FOUNDER_ROLE, Employment, Person
from tst.sim.people.reveal import new_reveal_state
from tst.sim.products.setup import initial_market
from tst.sim.rng import RngFactory
from tst.sim.state import CompanyState, GameState, SaveMeta

PLAYER_COMPANY_ID: Final = 1
FOUNDER_PERSON_ID: Final = 1
FOUNDER_EMPLOYMENT_ID: Final = 1
FOUNDER_LEVEL: Final = "exec"
MISSION_SIZE: Final = 2  # interests in a company mission (formulas.md section 7)
DEFAULT_FOUNDER: Final = FounderSpec(background="engineer")  # CLI and API default
START_TURN: Final = 0
START_STAGE: Final = 0  # solo founder (spec section 3)
FIRST_PRODUCT_ID: Final = 1  # incumbents' products take the first ids (ADR-0017)
MAX_COMPANY_NAME: Final = 80  # tunable-exempt: column width of company.name


def company_mission(
    mission: tuple[str, ...] | None, founder: Person, data: GameData
) -> tuple[str, ...]:
    """Two mission interests (formulas.md section 7).

    Omitted: the founder's first two interests, ordered as in interests.yaml. Given: exactly
    two distinct, valid interest keys.
    """
    if mission is None:
        order = {key: i for i, key in enumerate(data.interest_keys)}
        return tuple(sorted(founder.interests, key=lambda k: order[k])[:MISSION_SIZE])
    if len(mission) != MISSION_SIZE or len(set(mission)) != MISSION_SIZE:
        raise InvalidMissionError(f"mission must be exactly {MISSION_SIZE} different interests")
    unknown = sorted(set(mission) - set(data.interest_keys))
    if unknown:
        raise InvalidMissionError(f"unknown mission interests {unknown}")
    return tuple(mission)


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
    mission: tuple[str, ...] | None = None,
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    """Return the turn-0 state and the opening ledger entries. The caller persists both.

    The state holds the player company, its founder (formulas.md section 5), the founder's
    employment (role founder, level exec, salary 0, equity 0), the company's exact
    knowledge of its founder, and the 2010 market with its incumbents (11.1, 11.9).
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
    market = initial_market(
        data,
        turn=START_TURN,
        first_company_id=PLAYER_COMPANY_ID + 1,
        first_product_id=FIRST_PRODUCT_ID,
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
                mission=company_mission(mission, person, data),
            ),
            *market.companies,
        ),
        people=(person,),
        employments=(employment,),
        reveals=(reveal,),
        person_states=(PersonState(person_id=person.id, energy=balance.founder.energy_per_month),),
        products=market.products,
        product_segments=market.product_segments,
        markets=market.markets,
        next_ids=NextIds(
            person=FOUNDER_PERSON_ID + 1,
            search=1,
            offer=1,
            employment=FOUNDER_EMPLOYMENT_ID + 1,
            product=market.next_product_id,
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
