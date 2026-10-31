"""Executive seats (docs/formulas.md 18.3): seat scores from true skills, effects, vacancy
penalties and k_COO. The API shows only estimates from displayed ranges (18.8)."""

from __future__ import annotations

from collections.abc import Mapping

from tst.sim.data_models import LEVELS, Balance
from tst.sim.org.formulas import coo_factor, seat_effect, seat_multiplier, seat_score
from tst.sim.org.models import SEATS
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState

COO = "coo"
CFO = "cfo"
CTO = "cto"
CPO = "cpo"
CMO = "cmo"
CRO = "cro"


def seats_in_play(state: GameState, company_id: int, balance: Balance) -> bool:
    """Seats count (filled or vacant) for the player's company from stage 3 (18.3)."""
    company = state.company(company_id)
    return company.is_player and company.stage >= balance.exec_seats.stage


def level_allowed(level: str, balance: Balance) -> bool:
    """Senior or above (18.3)."""
    return level in LEVELS and LEVELS.index(level) >= LEVELS.index(balance.exec_seats.min_level)


def true_score(state: GameState, person_id: int, seat: str, balance: Balance) -> float:
    """s from the holder's true skills. Never shown (18.8)."""
    weights = balance.exec_seats.seats[seat].weights
    return seat_score(state.person(person_id).skills.as_dict(), weights)


def effect_of(state: GameState, company_id: int, seat: str, balance: Balance) -> float:
    """e for one seat: 0 before stage 3, the vacancy penalty for an empty seat (18.3)."""
    if not seats_in_play(state, company_id, balance):
        return 0.0
    holder = state.seat_holder(company_id, seat)
    if holder is None or state.employment_of(holder) is None:
        return balance.exec_seats.vacant_effect
    return seat_effect(true_score(state, holder, seat, balance), balance.exec_seats)


def effects(state: GameState, company_id: int, balance: Balance) -> Mapping[str, float]:
    return {seat: effect_of(state, company_id, seat, balance) for seat in SEATS}


def multiplier(state: GameState, company_id: int, seat: str, balance: Balance) -> float:
    """1 + coefficient x e for the CTO, CPO, CMO, CRO and CFO (18.3)."""
    coefficient = balance.exec_seats.seats[seat].effect
    return seat_multiplier(effect_of(state, company_id, seat, balance), coefficient)


def k_coo(state: GameState, company_id: int, balance: Balance) -> float:
    """k_COO = 1 - 0.5 e; 1 when seats are not in play (18.3)."""
    e = effect_of(state, company_id, COO, balance)
    return coo_factor(e, balance.exec_seats.seats[COO].effect)


def cfo_confidence(state: GameState, company_id: int, balance: Balance) -> float:
    """Each director's extra monthly confidence: 0.5 e (18.3)."""
    return balance.exec_seats.seats[CFO].confidence * effect_of(state, company_id, CFO, balance)


def side_factor(state: GameState, company_id: int, seat: str, key: str, balance: Balance) -> float:
    """1 + coefficient x e for a seat's second effect (18.3, redesigned 2026-10-31): `key` is
    qcap, brand, awareness or pricing; churn falls instead (see churn_factor)."""
    coefficient = float(getattr(balance.exec_seats.seats[seat], key))
    return seat_multiplier(effect_of(state, company_id, seat, balance), coefficient)


def churn_factor(state: GameState, company_id: int, balance: Balance) -> float:
    """CPO: base churn x (1 - 0.15 e) (18.3)."""
    coefficient = balance.exec_seats.seats[CPO].churn
    return 1 - coefficient * effect_of(state, company_id, CPO, balance)


def displayed_score(
    state: GameState, company_id: int, person_id: int, seat: str, b: Balance
) -> float:
    """s from the company's displayed ranges' midpoints (18.8): what the player can judge."""
    reveal = state.reveal(company_id, person_id)
    if reveal is None:
        return b.exec_seats.score_mid
    person = state.person(person_id)
    total = 0.0
    for key, w in b.exec_seats.seats[seat].weights.items():
        lo, hi = revealed_range(person, reveal, key)
        total += w * (lo + hi) / 2
    return total
