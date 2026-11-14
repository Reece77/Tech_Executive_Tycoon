"""The family's one-offs (docs/formulas.md 45.2-45.6, M36): family time, education,
mentoring, a job in the group, succession, gifts, the trust and shares for the foundation.
Immediate actions (ADR-0014); only the family head (the founder) takes them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.family import adviser, answers, estate, succession
from tst.sim.ledger import LedgerBalances
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class SetFamilyTime:
    actor_id: int
    energy: int  # 0 to family.max_time a month
    kind: Literal["set_family_time"] = "set_family_time"


@dataclass(frozen=True, slots=True)
class EducateChild:
    actor_id: int
    person_id: int
    stage: str  # school, university or mba
    tier: str  # school: standard, elite; university: none, standard, top; mba: mba
    degree: str | None = None  # university: engineering, business, design, science, medicine
    kind: Literal["educate_child"] = "educate_child"


@dataclass(frozen=True, slots=True)
class SetMentoring:
    actor_id: int
    person_id: int
    on: bool
    kind: Literal["set_mentoring"] = "set_mentoring"


@dataclass(frozen=True, slots=True)
class OfferFamilyJob:
    actor_id: int
    person_id: int
    company_id: int
    role: str
    level: str
    kind: Literal["offer_family_job"] = "offer_family_job"


@dataclass(frozen=True, slots=True)
class NameSuccessor:
    """45.5: hand over to an heir (the player then plays them), or appoint a professional CEO
    (`ceo_person_id`, or None with `professional` for the best insider or a search)."""

    actor_id: int
    heir_id: int | None = None
    ceo_person_id: int | None = None
    professional: bool = False
    kind: Literal["name_successor"] = "name_successor"


@dataclass(frozen=True, slots=True)
class GiftShares:
    actor_id: int
    heir_id: int
    shares: int
    kind: Literal["gift_shares"] = "gift_shares"


@dataclass(frozen=True, slots=True)
class FundTrust:
    actor_id: int
    shares: int
    kind: Literal["fund_trust"] = "fund_trust"


@dataclass(frozen=True, slots=True)
class GiveSharesToFoundation:
    actor_id: int
    shares: int
    kind: Literal["give_shares_to_foundation"] = "give_shares_to_foundation"


@dataclass(frozen=True, slots=True)
class RetireAdviser:
    actor_id: int
    kind: Literal["retire_adviser"] = "retire_adviser"


type FamilyAction = (
    SetFamilyTime
    | EducateChild
    | SetMentoring
    | OfferFamilyJob
    | NameSuccessor
    | GiftShares
    | FundTrust
    | GiveSharesToFoundation
    | RetireAdviser
)

FAMILY_ACTION_TYPES: dict[str, type[FamilyAction]] = {
    "set_family_time": SetFamilyTime,
    "educate_child": EducateChild,
    "set_mentoring": SetMentoring,
    "offer_family_job": OfferFamilyJob,
    "name_successor": NameSuccessor,
    "gift_shares": GiftShares,
    "fund_trust": FundTrust,
    "give_shares_to_foundation": GiveSharesToFoundation,
    "retire_adviser": RetireAdviser,
}


def _head(state: GameState, actor_id: int) -> None:
    family = state.family
    if family is None:
        raise InvalidActionError("this game has no family (Family was set to none)")
    acting_company(state, actor_id)
    if family.head_id != actor_id:
        raise InvalidActionError("only the head of the family can do that")


def apply_family(
    state: GameState,
    action: FamilyAction,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    _head(state, action.actor_id)
    fb = balance.family
    match action:
        case SetFamilyTime():
            return Outcome(answers.set_family_time(state, action.energy, balance))
        case EducateChild():
            state, log = answers.educate(
                state, action.person_id, action.stage, action.tier, action.degree, balance
            )
            return Outcome(state, (), (log,))
        case SetMentoring():
            return Outcome(answers.set_mentoring(state, action.person_id, action.on))
        case OfferFamilyJob():
            state, log = answers.offer_job(
                state,
                action.person_id,
                action.company_id,
                action.role,
                action.level,
                balance,
                data,
            )
            return Outcome(state, (), (log,))
        case NameSuccessor():
            family = state.family
            assert family is not None
            how = family.succession_open or "choice"
            if action.heir_id is not None:
                state, logs = succession.hand_to_heir(
                    state, action.heir_id, how, rng, balances, balance, data
                )
            elif action.professional or action.ceo_person_id is not None:
                state, logs = succession.appoint_professional(
                    state, action.ceo_person_id, how, rng, balance, data
                )
            else:
                raise InvalidActionError("name an heir or a professional CEO")
            return Outcome(state, (), tuple(logs))
        case GiftShares():
            state = spend_energy(state, action.actor_id, action.kind, balance, cost=fb.gift_energy)
            state, log = estate.gift_shares(
                state, action.heir_id, action.shares, balances, balance, data
            )
            return Outcome(state, (), (log,))
        case FundTrust():
            state = spend_energy(
                state, action.actor_id, action.kind, balance, cost=fb.trust_energy
            )
            state, log = estate.fund_trust(state, action.shares, balance)
            return Outcome(state, (), (log,))
        case GiveSharesToFoundation():
            state, log = estate.give_to_foundation(state, action.shares, balances, balance, data)
            return Outcome(state, (), (log,))
        case RetireAdviser():
            state, logs = adviser.retire(state, balance)
            return Outcome(state, (), tuple(logs))
