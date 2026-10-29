"""Relationships (docs/formulas.md 16.7): pairs of unit-mates and of managers and their
reports, a start value from temperament, a monthly drift back toward it after behaviour-tag
pushes, the W_rel morale term and the labels the player sees.
"""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.data_models import RelationshipsBalance


@dataclass(frozen=True, slots=True)
class Relationship:
    """One pair, `a < b`. `value` is the true relationship; the player sees only a label."""

    a: int
    b: int
    value: float
    start: float
    since_turn: int

    @property
    def key(self) -> tuple[int, int]:
        return (self.a, self.b)

    def other(self, person_id: int) -> int:
        return self.b if person_id == self.a else self.a


def pair_key(x: int, y: int) -> tuple[int, int]:
    return (x, y) if x < y else (y, x)


def relationship_start(
    temperament_a: float, temperament_b: float, cfg: RelationshipsBalance
) -> float:
    """round(15 - 1.5 |temperament_a - temperament_b|), clamped to [-20, 15] (true values)."""
    raw = round(cfg.start_base - cfg.start_per_temperament * abs(temperament_a - temperament_b))
    return float(max(cfg.start_clamp.lo, min(cfg.start_clamp.hi, raw)))


def clamp_relationship(value: float, cfg: RelationshipsBalance) -> float:
    return max(cfg.range.lo, min(cfg.range.hi, value))


def relationship_step(value: float, start: float, push: float, cfg: RelationshipsBalance) -> float:
    """One month: tag pushes first, then 10% of the way back to the start value."""
    pushed = value + push
    return clamp_relationship(pushed + cfg.drift * (start - pushed), cfg)


def relationship_morale(values: list[float], cfg: RelationshipsBalance) -> float:
    """W_rel = clamp(0.1 x mean relationship with unit-mates, -5, +5); 0 with none."""
    if not values:
        return 0.0
    term = cfg.morale_weight * sum(values) / len(values)
    return max(-cfg.morale_cap, min(cfg.morale_cap, term))


LABELS = ("hostile", "strained", "neutral", "good", "close")


def relationship_label(value: float, cfg: RelationshipsBalance) -> str:
    """close (>= 60), good (20-59), neutral (-19-19), strained (-49 to -20), hostile (<= -50),
    on the rounded value."""
    v = round(value)
    hostile, strained, good, close = cfg.label_bounds
    if v <= hostile:
        return "hostile"
    if v <= strained:
        return "strained"
    if v < good:
        return "neutral"
    if v < close:
        return "good"
    return "close"
