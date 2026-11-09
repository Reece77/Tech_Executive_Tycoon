"""Which export controls apply when (docs/formulas.md 39.2).

A historical rule applies from its month to its `end` (if any), except in the months a
détente suspends it: export_controls.yaml's historical détentes, then the seeded ones in
`GameState.suspensions`. A seeded rule (an escalation after 2025, `GameState.seeded_rules`)
applies from the escalation's month. `news` rules and those whose effect is M19's (`via`)
are shown but change nothing here.

Nothing about a rule leaves the engine before its announced month (`visible`): seeded rules
exist in the state only from the month they are announced, which is the month they apply.
"""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.data_models import GameData
from tst.sim.geopolitics.config import ExportControlsFile, RuleDef
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class ActiveRule:
    rule: RuleDef
    start_turn: int
    end_turn: int | None
    seeded: bool = False

    @property
    def key(self) -> str:
        return self.rule.key

    @property
    def bites(self) -> bool:
        """Whether the engine applies it (not news, not M19's)."""
        return not self.rule.news and self.rule.via is None


def controls_of(data: GameData) -> ExportControlsFile:
    assert data.controls is not None
    return data.controls


def all_rules(state: GameState, data: GameData) -> tuple[ActiveRule, ...]:
    """Every historical rule, then the seeded ones in the order they arrived."""
    controls = controls_of(data)
    out = [ActiveRule(r, r.start_turn, r.end_turn) for r in controls.rules]
    out += [
        ActiveRule(controls.rule(s.rule_key), s.start_turn, s.end_turn, seeded=True)
        for s in state.seeded_rules
    ]
    return tuple(out)


def suspension(state: GameState, data: GameData, key: str, turn: int) -> tuple[int, int] | None:
    """The (first, last) months of the suspension covering `turn`, if any."""
    for d in controls_of(data).detentes:
        if key in d.suspends and d.start_turn <= turn < d.start_turn + d.months:
            return d.start_turn, d.start_turn + d.months - 1
    for s in state.suspensions:
        if s.rule_key == key and s.start_turn <= turn <= s.end_turn:
            return s.start_turn, s.end_turn
    return None


def applies(state: GameState, data: GameData, active: ActiveRule, turn: int) -> bool:
    if turn < active.start_turn:
        return False
    if active.end_turn is not None and turn > active.end_turn:
        return False
    return suspension(state, data, active.key, turn) is None


def in_force(state: GameState, data: GameData, turn: int | None = None) -> tuple[ActiveRule, ...]:
    """Rules applying in `turn` (default: the state's), biting or not."""
    t = state.turn if turn is None else turn
    return tuple(a for a in all_rules(state, data) if applies(state, data, a, t))


def biting(state: GameState, data: GameData, turn: int | None = None) -> tuple[ActiveRule, ...]:
    return tuple(a for a in in_force(state, data, turn) if a.bites)


def announced_turn(active: ActiveRule) -> int:
    return active.start_turn if active.seeded else active.rule.announced_turn


def visible(state: GameState, data: GameData) -> tuple[ActiveRule, ...]:
    """Rules announced by the state's month: the only ones the API may show (39.3)."""
    return tuple(a for a in all_rules(state, data) if announced_turn(a) <= state.turn)


def announced_in(state: GameState, data: GameData, turn: int) -> tuple[ActiveRule, ...]:
    """Historical rules announced in `turn` (seeded ones are announced as they arrive)."""
    return tuple(a for a in all_rules(state, data) if not a.seeded and announced_turn(a) == turn)
