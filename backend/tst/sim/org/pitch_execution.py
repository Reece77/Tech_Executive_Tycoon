"""How an approved pitch is carried out (docs/formulas.md 27.1, M13b; product manager's ruling
2026-11-04): the executing executive's seat factor (18.3) on the move itself, for the
pitch's record window. A new product's team pace follows the CPO's factor (1 + 0.15 e); a
region launch's sales ramp there follows the CRO's (1 + 0.20 e); e from the executive's true
seat score in the engine, from the displayed score for the API (18.8). The CEO executes with
its own score and the seat's coefficient."""

from __future__ import annotations

from tst.sim.data_models import Balance
from tst.sim.markets_public.formulas import ceo_score
from tst.sim.org.executives import displayed_score, true_score
from tst.sim.org.formulas import seat_effect, seat_multiplier
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState

KIND_SEAT = {"new_product": "cpo", "region": "cro"}  # the seat whose coefficient applies


def _score(
    state: GameState, company: int, person_id: int, seat: str, b: Balance, estimate: bool
) -> float:
    if seat != "ceo":
        if estimate:
            return displayed_score(state, company, person_id, seat, b)
        return true_score(state, person_id, seat, b)
    person = state.person(person_id)
    if not estimate:
        return ceo_score(person.skills.as_dict(), b.ceo.weights)
    reveal = state.reveal(company, person_id)
    if reveal is None:
        return b.exec_seats.score_mid
    weights = b.ceo.weights
    total = sum(weights.values())
    shown = 0.0
    for k, w in weights.items():
        lo, hi = revealed_range(person, reveal, k)
        shown += w * (lo + hi) / 2
    return shown / total if total else b.exec_seats.score_mid


def execution_factor(
    state: GameState,
    kind: str,
    product_id: int,
    balance: Balance,
    region: str | None = None,
    *,
    estimate: bool = False,
) -> float:
    """The seat factor of the executive who carries out an approved pitch of this kind on
    this product (and region), while its record window runs; 1 otherwise."""
    if not state.pitches:
        return 1.0
    for p in state.pitches:
        if p.kind != kind or not p.approved or p.resolved_turn is None:
            continue
        if not p.resolved_turn <= state.turn < p.resolved_turn + balance.pitch.record_months:
            continue
        target = p.target_id
        if kind == "region":
            if (
                dict(p.params).get("product_id") != product_id
                or dict(p.params).get("region") != region
            ):
                continue
        elif target != product_id:
            continue
        seat = KIND_SEAT[kind]
        score = _score(state, p.company_id, p.person_id, p.seat, balance, estimate)
        e = seat_effect(score, balance.exec_seats)
        return seat_multiplier(e, balance.exec_seats.seats[seat].effect)
    return 1.0
