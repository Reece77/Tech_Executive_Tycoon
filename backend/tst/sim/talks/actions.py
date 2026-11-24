"""The immediate action a talk ends with (docs/formulas.md 61; ADR-0014): `TalkOutcome`
applies a finished talk's effects, which the talks engine computed within its bounds. Set only
by the talks service; replays apply it from the decision log like any action, so a game replay
never reads a conversation. A skipped talk has no action: skip is today's game (61.3 target 1).

- An interview (or a press crisis) answers its press event with the tone its answers add up
  to, through the event's own choice (29.1's effects as today), then adds the coverage's
  brand and credibility change and, where one was made, its promise through 29.2's rules.
- A crisis conference moves the brand target and credibility, Beloved or Ruthless (32.4), and
  a deflection on a class I recall may bring a for-cause inspection (draw: stream `talks`).
- A one-to-one moves the person's morale, loyalty and stress, may keep them from a rival's
  approach (draw: stream `talks`), reveals their interests on `listen`, gives a raise through
  `give_raise` and options from the pool, and records a promised promotion (61.2).

The action re-checks every bound, so even a hand-made outcome cannot move more than 61 allows.
Its fields are JSON-plain, as the decision log stores them."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import TalkRuleError
from tst.sim.ledger import LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import times
from tst.sim.press import moments
from tst.sim.press.models import Promise
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    with_approach,
    with_person,
    with_person_state,
    with_promise,
    with_reveal,
)
from tst.sim.talks.config import CRISIS_SOURCES, TALK_KINDS, TONE_CHOICE, TOPICS
from tst.sim.talks.models import Talk
from tst.sim.talks.opening import LADDER, kind_index, source_index, talk_gen

EPS: Final = 1e-9  # tunable-exempt: float tolerance on a bound
RETAIN_KEY: Final = 1  # tunable-exempt: the stream key's tag for a closing draw (0: the opening)
STRESS_MAX: Final = 100  # tunable-exempt: the stress scale
SOURCES: Final = (*CRISIS_SOURCES, "person")
TRAITS: Final = ("beloved", "ruthless")
CAUSES: Final = {
    "interview": "an interview",
    "crisis": "a press conference",
    "one_to_one": "a one-to-one",
}


@dataclass(frozen=True, slots=True)
class TalkOutcome:
    actor_id: int
    talk_kind: str  # interview, crisis or one_to_one
    period_turn: int  # the month the talk was held
    source: str  # press, recall, robotaxi or person
    subject_key: int  # the moment, recall, incident or person
    event_id: int | None = None  # the press event the talk answers
    choice: str = ""  # its choice (A measured, B bold, C deflect)
    brand_pct: float = 0.0  # % on every product's brand target
    brand_months: int = 0
    credibility: float = 0.0
    persona: Sequence[Any] | None = None  # (trait, points)
    inspection_chance: float = 0.0
    product_id: int | None = None  # the recalled device (an inspection's subject)
    person_id: int | None = None
    morale: float = 0.0
    loyalty: float = 0.0
    stress: float = 0.0
    approach_id: int | None = None
    retain_chance: float = 0.0
    raise_salary_cents: int = 0  # the new salary, through give_raise
    equity_bp: int = 0
    reveal: bool = False
    promise: Sequence[Any] | None = None  # (kind, product id, person id, months)
    delegate_id: int | None = None  # a seat holder who held the one-to-one
    summary: str = ""
    kind: Literal["talk_outcome"] = "talk_outcome"


ACTION_TYPES: Final[dict[str, type]] = {"talk_outcome": TalkOutcome}


def _check(state: GameState, a: TalkOutcome, balance: Balance) -> None:
    tb = balance.talks
    if a.talk_kind not in TALK_KINDS or a.source not in SOURCES:
        raise TalkRuleError(f"unknown talk {a.talk_kind!r}")
    if a.period_turn != state.turn:
        raise TalkRuleError("a talk's outcome is applied in the month it is held")
    press = a.talk_kind in ("interview", "crisis")
    if press:
        cfg = tb.interview if a.talk_kind == "interview" else tb.crisis
        audience = moments.audience(state, state.player.id, balance)
        if abs(a.brand_pct) > cfg.brand_step * audience + EPS:
            raise TalkRuleError("the brand change is out of bounds")
        if abs(a.credibility) > cfg.cred_step * audience + EPS:
            raise TalkRuleError("the credibility change is out of bounds")
        if a.brand_months not in (0, cfg.brand_months):
            raise TalkRuleError("the brand change runs the talk's months")
        if a.choice and a.choice not in TONE_CHOICE.values():
            raise TalkRuleError("an interview answers with a tone")
        if a.persona is not None:
            trait, points = a.persona
            if a.talk_kind != "crisis" or trait not in TRAITS:
                raise TalkRuleError("only a crisis conference moves the persona")
            if not 0 <= float(points) <= tb.crisis.persona_points + EPS:
                raise TalkRuleError("the persona change is out of bounds")
        if not 0 <= a.inspection_chance <= tb.crisis.deflect_inspection + EPS:
            raise TalkRuleError("the inspection chance is out of bounds")
        if a.person_id is not None or a.morale or a.loyalty or a.raise_salary_cents:
            raise TalkRuleError("a press talk moves no one's morale")
        return
    o = tb.one_to_one
    if a.person_id is None:
        raise TalkRuleError("a one-to-one is with a person")
    if abs(a.morale) > o.morale_step + EPS or abs(a.loyalty) > o.loyalty_step + EPS:
        raise TalkRuleError("the morale or loyalty change is out of bounds")
    if not 0 <= a.retain_chance <= o.retain_cap + EPS:
        raise TalkRuleError("the retention chance is out of bounds")
    if not 0 <= a.stress <= o.push_stress * len(TOPICS) + EPS:
        raise TalkRuleError("the stress change is out of bounds")
    if a.equity_bp not in (0, o.equity_bp):
        raise TalkRuleError("the options offered are out of bounds")
    if a.brand_pct or a.credibility or a.choice or a.persona is not None:
        raise TalkRuleError("a one-to-one moves no brand or credibility")


def _press(
    state: GameState,
    a: TalkOutcome,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    from tst.sim.events.effects import apply_choice

    cid = state.player.id
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    if a.event_id is not None:
        event = state.event(a.event_id)
        if event is None or event.company_id != cid:
            raise TalkRuleError(f"no press event {a.event_id}")
        if event.status != "open" or event.turn > state.turn:
            raise TalkRuleError("the press event has been answered")
        if not a.choice or event.choice(a.choice) is None:
            raise TalkRuleError("the interview answers the press event with a tone")
        # the event's own answer, as when the player picks the tone (29.1): today's effects
        state = spend_energy(state, a.actor_id, "choose_event", balance)
        state, e, lg = apply_choice(state, event, a.choice, balance, data, auto=False)
        entries += e
        logs += lg
    if a.brand_pct:
        state = moments.brand_modifier(state, cid, float(a.brand_pct), int(a.brand_months))
    state = moments.adjust_credibility(
        state, cid, float(a.credibility), CAUSES[a.talk_kind], balance
    )
    if a.persona is not None:
        from tst.sim.founder.persona import raise_trait
        from tst.sim.founder.stress import new_life
        from tst.sim.state import life_of, with_life

        trait, points = str(a.persona[0]), float(a.persona[1])
        founder = state.founder_of(cid)
        if founder is not None:
            life = life_of(state, founder.id) or new_life(founder.id, balance)
            why = "candour in a crisis" if trait == "beloved" else "deflecting in a crisis"
            state = with_life(state, raise_trait(life, trait, points, why, state.turn, balance))
    if a.inspection_chance and a.product_id is not None:
        from tst.sim.medical import data as md
        from tst.sim.medical.quality import inspect

        gen = talk_gen(
            rng,
            state.turn,
            kind_index("crisis"),
            source_index(a.source),
            a.subject_key,
            RETAIN_KEY,
        )
        if float(gen.random()) < a.inspection_chance and md.cleared(
            state, a.product_id, md.FDA, state.turn
        ):
            state, found, logged = inspect(
                state, cid, md.FDA, float(gen.random()), balance, data, True
            )
            entries += found
            logs += logged
    if a.promise is not None:
        from tst.sim.press import promises

        kind, product_id, _person, _months = a.promise
        state, promise = promises.make(
            state,
            cid,
            str(kind),
            balance,
            data,
            product_id=None if product_id is None else int(product_id),
        )
        state = spend_energy(
            state, a.actor_id, "make_promise", balance, cost=balance.promise.energy
        )
        words = promises.promise_words(state, promise, data)
        logs.append(inbox_item(state.turn, cid, "promise_made", promise=words))
    return state, entries, logs


def _grant(state: GameState, person_id: int, equity_bp: int) -> GameState:
    """Options of `equity_bp` of FD from the unallocated pool, vesting from this month (14.2's
    grant record; only for someone without a grant, and never more than the pool holds)."""
    from tst.sim.finance.captable import pool_entry
    from tst.sim.finance.models import OptionGrant
    from tst.sim.finance.options import offer_shares
    from tst.sim.state import with_cap_entry, with_grant

    e = state.employment_of(person_id)
    if e is None or state.grant_for(e.id) is not None:
        raise TalkRuleError("they already hold options")
    pool = pool_entry(state, e.company_id)
    shares = min(offer_shares(state, e.company_id, equity_bp), pool.shares if pool else 0)
    if pool is None or shares <= 0:
        raise TalkRuleError("the option pool has no room")
    gid, ids = state.next_ids.take("grant")
    state = with_cap_entry(replace(state, next_ids=ids), replace(pool, shares=pool.shares - shares))
    return with_grant(
        state,
        OptionGrant(
            id=gid,
            company_id=e.company_id,
            person_id=person_id,
            employment_id=e.id,
            granted=shares,
            start_turn=state.turn,
        ),
    )


def _one_to_one(
    state: GameState, a: TalkOutcome, rng: RngFactory, balance: Balance
) -> tuple[GameState, list[LogItem]]:
    from tst.sim.actions.org import GiveRaise, bump_morale, give_raise

    tb = balance.talks
    cid = state.player.id
    assert a.person_id is not None
    pid = a.person_id
    e = state.employment_of(pid)
    if e is None or e.company_id != cid or e.status != "active":
        raise TalkRuleError("a one-to-one is with one of the company's people")
    logs: list[LogItem] = []
    person = state.person(pid)
    name = f"{person.first_name} {person.last_name}"
    if a.raise_salary_cents:
        expected = times(e.salary_cents, 1 + tb.one_to_one.raise_share)
        if int(a.raise_salary_cents) != expected:
            raise TalkRuleError("the raise offered is out of bounds")
        state = give_raise(state, GiveRaise(a.actor_id, pid, expected), balance).state
    if a.equity_bp:
        state = _grant(state, pid, int(a.equity_bp))
    state = bump_morale(state, pid, float(a.morale))
    if a.loyalty:
        person = state.person(pid)
        loyalty = person.personality["loyalty"] + float(a.loyalty)
        state = with_person(
            state, replace(person, personality=person.personality.updated({"loyalty": loyalty}))
        )
    ps = state.person_state(pid)
    if a.stress and ps.stress is not None:
        stress = max(0.0, min(float(STRESS_MAX), ps.stress + float(a.stress)))
        state = with_person_state(state, replace(ps, stress=stress))
    if a.reveal:
        reveal = state.reveal(cid, pid)
        if reveal is not None and reveal.profile_revealed_turn is None:
            state = with_reveal(state, replace(reveal, profile_revealed_turn=state.turn))
    if a.approach_id is not None and a.retain_chance:
        approach = next((x for x in state.approaches if x.id == a.approach_id), None)
        if approach is None or approach.person_id != pid or approach.status != "pending":
            raise TalkRuleError("no rival approach to answer")
        gen = talk_gen(
            rng,
            state.turn,
            kind_index("one_to_one"),
            source_index("person"),
            pid,
            RETAIN_KEY,
        )
        if float(gen.random()) < float(a.retain_chance):
            state = with_approach(
                state, replace(approach, status="declined", resolved_turn=state.turn)
            )
            rival = state.company(approach.rival_id).name
            logs.append(
                inbox_item(
                    state.turn,
                    cid,
                    "talk_retained",
                    link_kind="person",
                    link_id=pid,
                    name=name,
                    rival=rival,
                )
            )
    if a.promise is not None:
        kind, _product, person_id, months = a.promise
        if str(kind) != "promotion" or person_id is None or int(person_id) != pid:
            raise TalkRuleError("a one-to-one promises a promotion")
        if int(months) != tb.promises.months or e.level not in LADDER[:-1]:
            raise TalkRuleError("that promotion cannot be promised")
        prid, ids = state.next_ids.take("promise")
        state = with_promise(
            replace(state, next_ids=ids),
            Promise(
                id=prid,
                company_id=cid,
                kind="promotion",
                made_turn=state.turn,
                deadline_turn=state.turn + tb.promises.months,
                level=pid,
                baseline=LADDER.index(e.level),
            ),
        )
    return state, logs


def apply_talk(
    state: GameState, a: TalkOutcome, rng: RngFactory, balance: Balance, data: GameData
) -> Outcome:
    cid = acting_company(state, a.actor_id)
    founder = state.founder_of(cid)
    if founder is None or founder.id != a.actor_id:
        raise TalkRuleError("the founder speaks for the company")
    _check(state, a, balance)
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    if a.delegate_id is None:
        state = spend_energy(
            state, a.actor_id, a.kind, balance, cost=balance.talks.energy[a.talk_kind]
        )
    elif a.talk_kind != "one_to_one" or not _holds_seat(state, a.delegate_id):
        raise TalkRuleError("a seat holder holds one-to-ones with their reports")
    if a.talk_kind == "one_to_one":
        state, logs = _one_to_one(state, a, rng, balance)
    else:
        state, entries, logs = _press(state, a, rng, balance, data)
    logs.append(
        inbox_item(
            state.turn,
            cid,
            "talk_held",
            link_kind="person" if a.person_id is not None else None,
            link_id=a.person_id,
            talk=CAUSES[a.talk_kind],
            summary=a.summary,
        )
    )
    return Outcome(state, tuple(entries), tuple(logs))


def _holds_seat(state: GameState, person_id: int) -> bool:
    cid = state.player.id
    return any(s.person_id == person_id and s.company_id == cid for s in state.exec_seats)


def summary_words(talk: Talk) -> str:
    """The inbox's line, from the engine's effects only (public words)."""
    from tst.sim.talks.opening import subject_title

    e = talk.effects
    assert e is not None
    parts: list[str] = []
    if e.tone:
        parts.append(f"a {e.tone} answer")
    if e.brand_pct:
        parts.append(f"brand target {e.brand_pct:+.1f}% for {e.brand_months} months")
    if e.credibility:
        parts.append(f"credibility {e.credibility:+.1f}")
    if e.persona is not None:
        parts.append(f"{e.persona[0]} {e.persona[1]:+.1f}")
    if e.morale:
        parts.append(f"morale {e.morale:+.1f}")
    if e.offer_raise:
        parts.append("a raise")
    if e.equity_bp:
        parts.append("options")
    if e.promise is not None:
        parts.append(f"you promised {e.promise.words}")
    text = "; ".join(parts) or "nothing moved"
    return f"{subject_title(talk)}: {text}."


def outcome_action(talk: Talk, actor_id: int, salary_cents: int, raise_share: float) -> TalkOutcome:
    """The finished talk's effects as the action that applies them."""
    e = talk.effects
    if talk.status != "done" or e is None:
        raise TalkRuleError("only a finished talk has an outcome")
    s = talk.subject
    promise = (
        (e.promise.kind, e.promise.product_id, e.promise.person_id, e.promise.months)
        if e.promise is not None
        else None
    )
    return TalkOutcome(
        actor_id=actor_id,
        talk_kind=talk.kind,
        period_turn=talk.opened_turn,
        source=s.source,
        subject_key=s.key,
        event_id=s.event_id,
        choice=TONE_CHOICE[e.tone] if e.tone else "",
        brand_pct=e.brand_pct,
        brand_months=e.brand_months if e.brand_pct else 0,
        credibility=e.credibility,
        persona=e.persona,
        inspection_chance=e.inspection_chance,
        product_id=s.product_id if s.medical else None,
        person_id=talk.counterpart.person_id,
        morale=e.morale,
        loyalty=e.loyalty,
        stress=e.stress,
        approach_id=s.approach_id if e.retain_chance else None,
        retain_chance=e.retain_chance,
        raise_salary_cents=times(salary_cents, 1 + raise_share) if e.offer_raise else 0,
        equity_bp=e.equity_bp,
        reveal=e.reveal,
        promise=promise,
        delegate_id=talk.delegate_id,
        summary=summary_words(talk),
    )
