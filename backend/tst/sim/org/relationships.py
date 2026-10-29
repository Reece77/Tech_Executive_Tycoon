"""Relationships in phase 8 (docs/formulas.md 16.7): pairs of unit-mates and of managers
and their reports in the player's company, tag pushes from true tags, drift, and the values
W_rel reads. Rivals' people have no relationships (M6 decision: they are not in events).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, RelationshipsBalance
from tst.sim.org.rules import OrgView, org_view, teammates
from tst.sim.people.relationships import (
    Relationship,
    pair_key,
    relationship_start,
    relationship_step,
)
from tst.sim.state import GameState

TEMPERAMENT: Final = "temperament"
AMBITION: Final = "ambition"
POLITICIAN: Final = "politician"


def tracked_pairs(
    state: GameState, company_id: int
) -> tuple[set[tuple[int, int]], dict[int, tuple[int, ...]]]:
    """The pairs tracked for one company (16.7): every two members of a unit (the company
    root included) and each manager with each report. Also returns each staff member's
    unit-mates."""
    view = org_view(state, company_id)
    pairs: set[tuple[int, int]] = set()
    mates: dict[int, tuple[int, ...]] = {}
    for members in view.members.values():
        for i, x in enumerate(members):
            mates[x] = tuple(m for m in members if m != x)
            for y in members[i + 1 :]:
                pairs.add(pair_key(x, y))
    for person_id, manager_id in view.manager_of.items():
        if manager_id is not None and manager_id != person_id:
            pairs.add(pair_key(person_id, manager_id))
    return pairs, mates


def tag_pushes(
    state: GameState, mates: dict[int, tuple[int, ...]], cfg: RelationshipsBalance
) -> dict[tuple[int, int], float]:
    """This month's behaviour-tag pushes on unit-mate pairs (16.7), from true tags: each
    holder pushes the pair with every unit-mate; a politician only those with ambition at
    least politician_ambition_at."""
    pushes: dict[tuple[int, int], float] = {}
    for holder_id in sorted(mates):
        holder = state.person(holder_id)
        for tag in holder.tags:
            push = cfg.tag_push.get(tag)
            if not push:
                continue
            for mate in mates[holder_id]:
                if tag == POLITICIAN and (
                    state.person(mate).personality[AMBITION] < cfg.politician_ambition_at
                ):
                    continue
                key = pair_key(holder_id, mate)
                pushes[key] = pushes.get(key, 0.0) + push
    return pushes


def relationships_month(state: GameState, balance: Balance) -> GameState:
    """Phase 8 (16.7), the player's company: pairs that are no longer unit-mates or a
    manager link end; new pairs start from temperament; existing pairs take the month's
    tag pushes and drift 10% back toward their start."""
    cfg = balance.relationships
    company_id = state.player.id
    pairs, mates = tracked_pairs(state, company_id)
    pushes = tag_pushes(state, mates, cfg)
    before = state.relationship_map()
    out: list[Relationship] = []
    for key in sorted(pairs):
        old = before.get(key)
        if old is None:
            a, b = state.person(key[0]), state.person(key[1])
            start = relationship_start(a.personality[TEMPERAMENT], b.personality[TEMPERAMENT], cfg)
            out.append(Relationship(key[0], key[1], start, start, state.turn))
        else:
            value = relationship_step(old.value, old.start, pushes.get(key, 0.0), cfg)
            out.append(replace(old, value=value))
    return replace(state, relationships=tuple(out))  # only the player has pairs


def unit_mate_values(state: GameState, view: OrgView, person_id: int) -> list[float]:
    """The person's relationships with each unit-mate that has one (for W_rel)."""
    rels = state.relationship_map()
    values = []
    for mate in teammates(view, person_id):
        rel = rels.get(pair_key(person_id, mate))
        if rel is not None:
            values.append(rel.value)
    return values
