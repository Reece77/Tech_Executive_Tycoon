"""Relationships in phase 8 (docs/formulas.md 16.7): pairs of unit-mates and of managers
and their reports in the player's company, tag pushes from true tags, drift, and the values
W_rel reads. Rivals' people have no relationships (M6 decision: they are not in events).
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Mapping
from dataclasses import replace
from heapq import merge
from itertools import pairwise
from operator import attrgetter
from typing import Final

from tst.sim.data_models import Balance, RelationshipsBalance
from tst.sim.org.rules import OrgView, org_view
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
    pairs, mates, _ = _tracked(state, company_id)
    return set(pairs), dict(mates)


def _tracked(
    state: GameState, company_id: int
) -> tuple[frozenset[tuple[int, int]], Mapping[int, tuple[int, ...]], list[tuple[int, int]]]:
    """`tracked_pairs`, and the pairs in key order, remembered for the last org seen (M14
    turn time: a 200-person unit has 18,000 pairs, and most months its org is unchanged).
    Members are listed in ascending id, so (x, y) with x before y is already a pair key."""
    view = org_view(state, company_id)
    signature = (
        tuple(sorted(view.members.items(), key=lambda kv: (kv[0] is not None, kv[0] or 0))),
        tuple(sorted(view.manager_of.items())),
    )
    if _PAIRS and _PAIRS[0][0] == signature:  # the same units and managers as last time
        return _PAIRS[0][1], _PAIRS[0][2], _PAIRS[0][3]
    pairs: set[tuple[int, int]] = set()
    mates: dict[int, tuple[int, ...]] = {}
    for members in view.members.values():
        for i, x in enumerate(members):
            mates[x] = members[:i] + members[i + 1 :]
            pairs.update((x, y) for y in members[i + 1 :])
    for person_id, manager_id in view.manager_of.items():
        if manager_id is not None and manager_id != person_id:
            pairs.add(pair_key(person_id, manager_id))
    frozen = frozenset(pairs)
    _PAIRS[:] = [(signature, frozen, mates, sorted(frozen))]
    return frozen, mates, _PAIRS[0][3]


# _tracked's memo: one entry, the last org it saw
_PAIRS: list[
    tuple[
        object,
        frozenset[tuple[int, int]],
        dict[int, tuple[int, ...]],
        list[tuple[int, int]],
    ]
] = []


def tag_pushes(
    state: GameState, mates: Mapping[int, tuple[int, ...]], cfg: RelationshipsBalance
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
    tag pushes and drift 10% back toward their start.

    M14 turn time: a pair at its start value with no push stays as it is (the step returns
    the start), so when the tracked pairs are the ones held, only pushed or drifting pairs
    are stepped."""
    cfg = balance.relationships
    company_id = state.player.id
    tracked, mates, keys = _tracked(state, company_id)
    pushes = tag_pushes(state, mates, cfg)
    held = state.relationships
    lo, hi = cfg.range.lo, cfg.range.hi
    known = _MOVING[0] if _MOVING and _MOVING[0][0] is held else None
    if known is None and not _in_key_order(held):  # never expected: kept in key order
        return _rebuilt(state, keys, pushes, cfg)

    def at_rest(r: Relationship) -> bool:
        return r.value == r.start and lo <= r.start <= hi

    # pairs off their start value: carried from last month's result, else found once
    moving = known[1] if known is not None else {r.key for r in held if not at_rest(r)}
    before = state.relationship_map()
    ended = before.keys() - tracked
    added = tracked - before.keys()
    kept = [r for r in held if r.key not in ended] if ended else list(held)
    fresh: list[Relationship] = []
    for key in sorted(added):  # new pairs start from temperament, unstepped this month
        a, b = state.person(key[0]), state.person(key[1])
        start = relationship_start(a.personality[TEMPERAMENT], b.personality[TEMPERAMENT], cfg)
        fresh.append(Relationship(key[0], key[1], start, start, state.turn))
    stepped = False
    still: set[tuple[int, int]] = set()
    for key in sorted((moving | pushes.keys()) - ended - added):
        i = bisect_left(kept, key, key=_KEY)
        old = kept[i]  # a held pair that did not end (pushes are between unit-mates)
        if old.key != key:
            raise AssertionError(f"relationship {key} is not held")
        value = relationship_step(old.value, old.start, pushes.get(key, 0.0), cfg)
        if value != old.value:
            old = kept[i] = replace(old, value=value)
            stepped = True
        if not at_rest(old):
            still.add(key)
    still |= {r.key for r in fresh if not at_rest(r)}
    if not (ended or fresh or stepped):
        _MOVING[:] = [(held, frozenset(still))]
        return state  # as it was: keep the tuple for caches and the save
    out = tuple(merge(kept, fresh, key=_KEY)) if fresh else tuple(kept)
    _MOVING[:] = [(out, frozenset(still))]
    return replace(state, relationships=out)  # only the player has pairs


# relationships_month's memo: the pairs it returned (in key order) and those off their start
# value, so next month steps only those and the pushed (M14 turn time)
_MOVING: list[tuple[tuple[Relationship, ...], frozenset[tuple[int, int]]]] = []


_KEY: Final = attrgetter("a", "b")


def _in_key_order(pairs: tuple[Relationship, ...]) -> bool:
    return all(x.key < y.key for x, y in pairwise(pairs))


def _rebuilt(
    state: GameState,
    keys: list[tuple[int, int]],
    pushes: Mapping[tuple[int, int], float],
    cfg: RelationshipsBalance,
) -> GameState:
    """The month's pairs built afresh in key order (the general rule, 16.7)."""
    before = state.relationship_map()
    built: list[Relationship] = []
    for key in keys:
        found = before.get(key)
        if found is None:
            a, b = state.person(key[0]), state.person(key[1])
            start = relationship_start(a.personality[TEMPERAMENT], b.personality[TEMPERAMENT], cfg)
            built.append(Relationship(key[0], key[1], start, start, state.turn))
            continue
        value = relationship_step(found.value, found.start, pushes.get(key, 0.0), cfg)
        built.append(found if value == found.value else replace(found, value=value))
    return replace(state, relationships=tuple(built))


def unit_mate_values(state: GameState, view: OrgView, person_id: int) -> list[float]:
    """The person's relationships with each unit-mate that has one (for W_rel), in the order
    of their unit-mates' ids. Only the player's company has relationships."""
    if not state.relationships or view.company_id != state.player.id:
        return []
    return list(_unit_mate_lists(state, view).get(person_id, ()))


def _unit_mate_lists(state: GameState, view: OrgView) -> Mapping[int, list[float]]:
    """Every staff member's unit-mate values in one pass over the pairs in key order, built
    once per (pairs, org view) (M14 turn time: per person it was all pairs of a unit). In
    key order a person's pairs (a, p) with a < p come first by a, then (p, b) by b: their
    unit-mates in ascending id, as `teammates` lists them, so sums match."""
    rels = state.relationship_map()
    if _MATES and _MATES[0][0] is state.relationships and _MATES[0][1] is view:
        return _MATES[0][2]
    unit_of = view.unit_of
    out: dict[int, list[float]] = {}
    pairs = state.relationships
    keys = [r.key for r in pairs]
    if keys != sorted(keys):  # kept in key order (loaded and written so); sort if not
        pairs = tuple(rels[k] for k in sorted(keys))
    for r in pairs:
        a, b = r.a, r.b
        if a in unit_of and b in unit_of and unit_of[a] == unit_of[b]:
            out.setdefault(a, []).append(r.value)
            out.setdefault(b, []).append(r.value)
    _MATES[:] = [(state.relationships, view, out)]
    return out


# _unit_mate_lists' memo: the pairs tuple and view it was built for, kept so ids stay unique
_MATES: list[tuple[tuple[Relationship, ...], OrgView, dict[int, list[float]]]] = []
