"""The dynasty legacy (docs/formulas.md 45.7): each generation's legacy is 32.6's score for
their years (the best company score reached in them, their giving and their persona, plus
37.5's wealth term while they lead); the dynasty score sums them, adds
`dynasty_points x log10(1 + family-held value / unit)` and takes off control_loss_points for
each loss of family control."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.family import rules
from tst.sim.founder.legacy import CENTS_A_DOLLAR, founder_companies, legacy_parts
from tst.sim.founder.wealth import legacy_wealth
from tst.sim.ledger import LedgerBalances
from tst.sim.state import GameState, foundation_of, life_of, listed_id


@dataclass(frozen=True, slots=True)
class GenerationScore:
    person_id: int
    name: str
    from_turn: int
    to_turn: int | None
    legacy: int
    how: str | None


@dataclass(frozen=True, slots=True)
class Dynasty:
    generations: tuple[GenerationScore, ...]
    legacies: int
    family_value_cents: int
    value_points: float
    control_losses: int
    loss_points: float
    total: int


def generation_legacy(state: GameState, person_id: int, balance: Balance) -> int:
    """32.6 for one head's years: scores while they led, their foundation's grants (and
    shares given, 45.6), their persona and wealth."""
    family = state.family
    start = 0
    if family is not None:
        for g in family.generations:
            if g.person_id == person_id:
                start = g.from_turn
    ids = set(founder_companies(state))
    scored = [s for s in state.scores if s.company_id in ids and s.turn >= start]
    best = max((s.score for s in scored), default=0)
    foundation = foundation_of(state, person_id)
    grants = foundation.grants_cents if foundation is not None else 0
    if family is not None and family.head_id == person_id:
        grants += family.foundation_share_cents
    life = life_of(state, person_id)
    pb = balance.persona.start
    traits = (
        (life.visionary, life.ruthless, life.beloved, life.reckless)
        if life is not None
        else (pb, pb, pb, pb)
    )
    giving, persona = legacy_parts(best, grants, traits, balance)
    points = [w for w in state.wealth_points if w.person_id == person_id]
    wealth = legacy_wealth(points[-1].total_cents, balance) if points else 0.0
    return round(best + giving + persona + wealth)


def family_value_cents(
    state: GameState, balances: LedgerBalances | None, balance: Balance, data: GameData
) -> int:
    """The family's shares (its people and the trust) at the share price (45.6's)."""
    from tst.sim.family.estate import share_price
    from tst.sim.finance.captable import fd_shares

    cid = listed_id(state)
    fd = fd_shares(state, cid)
    if fd <= 0:
        return 0
    held = Fraction(rules.family_bp(state, cid) * fd, 10_000)  # tunable-exempt: bp
    return int(held * share_price(state, cid, balances, balance, data))


def dynasty(
    state: GameState, balances: LedgerBalances | None, balance: Balance, data: GameData
) -> Dynasty | None:
    family = state.family
    if family is None:
        return None
    fb = balance.family
    gens = []
    for g in family.generations:
        legacy = (
            g.legacy if g.legacy is not None else generation_legacy(state, g.person_id, balance)
        )
        gens.append(
            GenerationScore(
                g.person_id,
                rules.full_name(state.person(g.person_id)),
                g.from_turn,
                g.to_turn,
                legacy,
                g.how,
            )
        )
    value = family_value_cents(state, balances, balance, data)
    unit = fb.dynasty_unit_dollars * CENTS_A_DOLLAR
    # money-exact: ratio: value in score units, a score
    value_points = fb.dynasty_points * dmath.log10(1 + max(0, value) / unit)
    loss = fb.control_loss_points * family.control_losses
    legacies = sum(g.legacy for g in gens)
    return Dynasty(
        generations=tuple(gens),
        legacies=legacies,
        family_value_cents=value,
        value_points=value_points,
        control_losses=family.control_losses,
        loss_points=loss,
        total=round(legacies + value_points - loss),
    )
