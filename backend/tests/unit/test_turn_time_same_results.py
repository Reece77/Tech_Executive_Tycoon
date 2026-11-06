"""M14 turn time (product manager, 2026-11-06): the monthly relationships step, W_rel and the
teammate tag terms now do work proportional to what changes. These property tests pin them
to the rules as first written (the references below are the pre-M14 code, kept verbatim in
spirit): the same pairs, values, order and morale terms, month after month, while people move
between units, leave and join."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.test_org_rules import team
from tests.unit.test_relationships import _company, _person
from tst.loader import LoadedData
from tst.sim.data_models import MENTOR_TAG, ORG_TAGS, Balance
from tst.sim.org import relationships as rel
from tst.sim.org.rules import (
    OrgView,
    has_teammate_tag,
    org_view,
    teammate_tag_holders,
    teammate_terms,
    teammates,
)
from tst.sim.people.relationships import (
    Relationship,
    pair_key,
    relationship_start,
    relationship_step,
)
from tst.sim.state import GameState, with_employment, with_unit

TAGS = ("credit_taker", "culture_carrier", "politician", "toxic_high_performer", *ORG_TAGS)


def _reference_pairs(
    state: GameState, company_id: int
) -> tuple[set[tuple[int, int]], dict[int, tuple[int, ...]]]:
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


def _reference_month(state: GameState, balance: Balance) -> GameState:
    cfg = balance.relationships
    pairs, mates = _reference_pairs(state, state.player.id)
    pushes = rel.tag_pushes(state, mates, cfg)
    before = {r.key: r for r in state.relationships}
    out: list[Relationship] = []
    for key in sorted(pairs):
        old = before.get(key)
        if old is None:
            a, b = state.person(key[0]), state.person(key[1])
            start = relationship_start(
                a.personality["temperament"], b.personality["temperament"], cfg
            )
            out.append(Relationship(key[0], key[1], start, start, state.turn))
        else:
            value = relationship_step(old.value, old.start, pushes.get(key, 0.0), cfg)
            out.append(replace(old, value=value))
    return replace(state, relationships=tuple(out))


def _reference_mate_values(state: GameState, view: OrgView, person_id: int) -> list[float]:
    if not state.relationships or view.company_id != state.player.id:
        return []
    rels = {r.key: r for r in state.relationships}
    return [
        rels[pair_key(person_id, m)].value
        for m in teammates(view, person_id)
        if pair_key(person_id, m) in rels
    ]


@settings(max_examples=40, deadline=None)
@given(
    tags=st.lists(st.lists(st.sampled_from(TAGS), max_size=2, unique=True), min_size=3, max_size=9),
    moves=st.lists(
        st.lists(st.sampled_from([None, 1, 2, "leave"]), min_size=9, max_size=9),
        min_size=1,
        max_size=6,
    ),
)
def test_relationships_and_morale_terms_match_the_rules_as_written(
    loaded: LoadedData, tags: list[list[str]], moves: list[list[int | str | None]]
) -> None:
    people = [_person(loaded, 2 + i, 3 + 2 * i, tuple(t)) for i, t in enumerate(tags)]
    state = _company(loaded, people)
    state = with_unit(state, team(1, leader=people[0].id))
    state = with_unit(state, team(2, leader=None, parent=1))
    ours = theirs = state
    for month in moves:
        for person, where in zip(people, month, strict=False):
            employment = next((e for e in ours.staff(1) if e.person_id == person.id), None)
            if employment is None:
                continue
            if where == "leave":
                ended = replace(employment, status="ended", end_turn=ours.turn)
            else:
                ended = replace(employment, unit_id=where)  # type: ignore[arg-type]
            ours, theirs = with_employment(ours, ended), with_employment(theirs, ended)
        ours = rel.relationships_month(ours, loaded.balance)
        theirs = _reference_month(theirs, loaded.balance)
        assert ours.relationships == theirs.relationships  # same pairs, values and order
        view = org_view(ours, 1)
        for e in ours.staff(1):
            pid = e.person_id
            assert rel.unit_mate_values(ours, view, pid) == _reference_mate_values(
                theirs, view, pid
            )
            holders = teammate_tag_holders(ours, view, pid)
            assert [n for _, n, _ in teammate_terms(ours, view, pid, loaded.balance)] == [
                len(holders[t]) for t in ORG_TAGS
            ]
            assert has_teammate_tag(ours, view, pid, MENTOR_TAG) == bool(
                any(MENTOR_TAG in ours.person(p).tags for p in teammates(view, pid))
            )
