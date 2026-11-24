"""What talks there are this month, and a talk's opening (docs/formulas.md 61.1-61.2): its
counterpart, its questions from the engine's displayed facts, and its hidden draws.

- **Interviews** answer the press moment whose event is shown this month (29.1): the player
  may take it as a live interview instead of picking a tone. A breach or an outage is a
  **crisis conference** on the same event.
- **Crisis conferences** without a press moment: a class I recall (50) or a robotaxi incident
  (49.4, 53.3) the company had last month.
- **One-to-ones** with any of the company's people, once a month each.

Draws (stream `talks` 72, key (kind index, source index, subject id) at the opening month):
the journalist's name, outlet and stance, the number of questions, the other side's
receptiveness at each question, and a delegate's quality. Skipping a talk, or never opening
one, draws nothing and changes nothing (61.3 target 1)."""

from __future__ import annotations

from typing import Final

import numpy as np

from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import TalkRuleError
from tst.sim.events.models import GameEvent
from tst.sim.people.generator import draw_name
from tst.sim.press import moments
from tst.sim.press.config import PROMISE_KINDS
from tst.sim.press.models import PressMoment
from tst.sim.press.names import rival_ceo_name
from tst.sim.press.promises import open_promises
from tst.sim.rng import RngFactory
from tst.sim.scale import ATTR_MAX
from tst.sim.state import GameState
from tst.sim.talks.config import CRISIS_SOURCES, TALK_KINDS, TalkKind, TalksBalance
from tst.sim.talks.models import Counterpart, PromiseOffer, Question, Subject, Talk, TalkHidden

PRESS_CRISES: Final = ("breach", "outage")  # press moments taken as crisis conferences (61.1)
PRESS_PREFIX: Final = "press_"
LADDER: Final = ("junior", "mid", "senior", "staff", "principal")  # 13.8's (org.PROMOTION_LADDER)
STANCES: Final = ("friendly", "neutral", "sceptical")
MID_TRAIT: Final = (ATTR_MAX + 1) / 2  # 10.5: a trait's middle
TRAIT_SPAN: Final = (ATTR_MAX - 1) / 2  # 9.5
TRIGGER_WORDS: Final = {
    "launch": "the launch of {product}",
    "earnings": "the quarter's results",
    "era": "a new era the company brought about",
    "outage": "an outage at the company's data centres",
    "breach": "a security breach at the company",
    "layoffs": "the company's layoffs",
    "acquisition": "the company's acquisition",
    "jab": "a rival chief executive's remarks",
    "rivalry": "the feud with {rival}",
    "reminder": "a promise the company made",
}


def talk_gen(rng: RngFactory, turn: int, *key: int) -> np.random.Generator:
    """The one call site of stream `talks` (ADR-0013, formulas.md 61)."""
    return rng.stream(turn, "talks", *key)


def kind_index(kind: TalkKind) -> int:
    return TALK_KINDS.index(kind)


def source_index(source: str) -> int:
    return (*CRISIS_SOURCES, "person").index(source)


def skill_factor(skills: dict[str, float], tb: TalksBalance) -> float:
    """The founder's (or a delegate's) weighted communication and leadership, onto the band."""
    score = sum(skills.get(k, 1.0) * w for k, w in tb.skill.weights.items())
    lo, hi = tb.skill.band.lo, tb.skill.band.hi
    return lo + (hi - lo) * (min(max(score, 1.0), ATTR_MAX) - 1.0) / (ATTR_MAX - 1.0)


# --- What there is to talk about --------------------------------------------------------------


def press_event(state: GameState) -> tuple[GameEvent, PressMoment] | None:
    """The press moment whose event is shown this month and still waits for an answer."""
    for e in state.events:
        if (
            e.company_id == state.player.id
            and e.turn == state.turn
            and e.status == "open"
            and e.template_id.startswith(PRESS_PREFIX)
        ):
            m = moments.moment_for_event(state, e)
            if m is not None and m.status == "queued":
                return e, m
    return None


def press_subject(state: GameState, data: GameData) -> tuple[TalkKind, Subject] | None:
    found = press_event(state)
    if found is None:
        return None
    event, m = found
    facts = dict(m.facts)
    product = state.product(m.product_id) if m.product_id is not None else None
    rival = state.company(m.rival_id).name if m.rival_id is not None else ""
    words = TRIGGER_WORDS.get(m.trigger, "the company").format(
        product=product.name if product is not None else "a product",
        rival=rival or "a rival",
    )
    kind: TalkKind = "crisis" if m.trigger in PRESS_CRISES else "interview"
    del facts
    return kind, Subject(
        key=m.id,
        source="press",
        words=words,
        event_id=event.id,
        product_id=m.product_id,
        rival_id=m.rival_id,
    )


def crisis_subjects(state: GameState, tb: TalksBalance) -> list[Subject]:
    """Class I recalls and robotaxi incidents the company had within the window (61.1)."""
    cid = state.player.id
    out: list[Subject] = []
    window = tb.crisis.window_months

    def recent(turn: int) -> bool:
        return 1 <= state.turn - turn <= window

    for r in state.med_recalls:
        if r.company_id == cid and r.klass == "I" and recent(r.turn):
            p = state.product(r.product_id)
            name = p.name if p is not None else "a device"
            out.append(
                Subject(
                    key=r.id,
                    source="recall",
                    words=f"the class I recall of {name}",
                    product_id=r.product_id,
                    medical=True,
                )
            )
    for i, inc in enumerate(state.robo_incidents):
        if inc.company_id == cid and recent(inc.turn):
            serious = "a serious robotaxi incident" if inc.serious else "a robotaxi incident"
            out.append(Subject(key=i, source="robotaxi", words=f"{serious} in {inc.city}"))
    return out


def person_subject(state: GameState, person_id: int) -> Subject:
    e = state.employment_of(person_id)
    if e is None or e.company_id != state.player.id or e.status != "active":
        raise TalkRuleError("a one-to-one is with one of the company's people")
    person = state.person(person_id)
    if person.is_founder:
        raise TalkRuleError("the founder does not hold a one-to-one with themselves")
    approach = next(
        (
            a
            for a in state.approaches
            if a.person_id == person_id and a.status == "pending" and a.made_turn < state.turn
        ),
        None,
    )
    grant = state.grant_for(e.id)
    return Subject(
        key=person_id,
        source="person",
        words=f"{person.first_name} {person.last_name}",
        rival_id=approach.rival_id if approach is not None else None,
        approach_id=approach.id if approach is not None else None,
        equity_ok=grant is None,
    )


# --- Opening --------------------------------------------------------------------------------


def _receptiveness(gen: np.random.Generator, n: int, tb: TalksBalance) -> tuple[float, ...]:
    lo, hi = tb.receptiveness.lo, tb.receptiveness.hi
    return tuple(lo + (hi - lo) * float(gen.random()) for _ in range(n))


def _count(gen: np.random.Generator, lo: float, hi: float) -> int:
    return int(gen.integers(int(lo), int(hi), endpoint=True))


def _founder_skill(state: GameState, tb: TalksBalance) -> float:
    founder = state.founder_of(state.player.id)
    if founder is None:
        raise TalkRuleError("the founder speaks for the company; there is none")
    return skill_factor(state.person(founder.id).skills.as_dict(), tb)


def _press_offer(state: GameState, m: PressMoment | None, balance: Balance) -> PromiseOffer | None:
    """The promise an interview could make (29.2's rules): no price rise at a launch, no
    layoffs after layoffs; none when three are already open or the moment has one."""
    if m is None:
        return None
    cid = state.player.id
    press_open = [p for p in open_promises(state, cid) if p.kind in PROMISE_KINDS]
    if len(press_open) >= balance.promise.max_open:
        return None
    if any(p.moment_id == m.id for p in state.promises):
        return None
    months = balance.promise.fixed_months
    if m.trigger == "launch" and m.product_id is not None:
        product = state.product(m.product_id)
        if product is not None and product.status == "live":
            return PromiseOffer(
                "no_price_rise",
                f"no price rise on {product.name} for {months} months",
                product_id=product.id,
                months=months,
            )
    if m.trigger == "layoffs":
        return PromiseOffer("no_layoffs", f"no more layoffs for {months} months", months=months)
    return None


def _press_questions(
    state: GameState,
    kind: TalkKind,
    subject: Subject,
    m: PressMoment | None,
    n: int,
    offer: PromiseOffer | None,
    gen: np.random.Generator,
    balance: Balance,
) -> tuple[Question, ...]:
    cid = state.player.id
    company = state.company(cid)
    cred = moments.credibility(state, cid, balance)
    facts = [f"{company.name}'s credibility with the press is {cred:.0f} out of 100"]
    if m is not None:
        for k, v in m.facts:
            if k in ("era", "result", "promise"):
                facts.append(f"the {k}: {v}")
    product = state.product(subject.product_id) if subject.product_id is not None else None
    if product is not None:
        facts.append(f"{product.name} is the product in question")
    rival = state.company(subject.rival_id).name if subject.rival_id is not None else ""
    rival_ceo = rival_ceo_name(state, subject.rival_id) if subject.rival_id is not None else None
    if rival_ceo:
        facts.append(f"{rival_ceo} runs {rival}")
    pool: list[Question] = []
    about = subject.words
    if kind == "crisis":
        pool += [
            Question(0, "harm", "What happened", f"What exactly happened with {about}?", ()),
            Question(
                0,
                "harm",
                "Who is responsible",
                "Who is responsible, and what will you do for the people affected?",
                (),
            ),
            Question(
                0,
                "future",
                "Will it happen again",
                "How can customers trust it won't happen again?",
                (),
                offer.words if offer else "",
            ),
        ]
    else:
        pool += [
            Question(0, "subject", "The news", f"What does {about} mean for the company?", ()),
            Question(
                0,
                "future",
                "What comes next",
                "What should customers expect from you over the next year?",
                (),
                offer.words if offer else "",
            ),
        ]
        if rival:
            pool.append(
                Question(0, "rival", "The rival", f"How do you answer {rival}?", (), rival=rival)
            )
        pool.append(
            Question(
                0,
                "subject",
                "The doubters",
                "Critics say you are overpromising. Are they wrong?",
                (),
            )
        )
    # the first question is always the news; the rest in a drawn order
    first, rest = pool[0], pool[1:]
    order = [int(i) for i in gen.permutation(len(rest))]
    chosen = [first, *(rest[i] for i in order)][: max(1, n)]
    if offer is not None and not any(q.offer for q in chosen):
        chosen[-1] = next(q for q in pool if q.offer)
    return tuple(
        Question(i, q.topic, q.title, q.question, tuple(facts), q.offer, q.rival)
        for i, q in enumerate(chosen)
    )


def open_press(
    state: GameState,
    kind: TalkKind,
    subject: Subject,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> Talk:
    """An interview or a crisis conference on this month's facts."""
    tb = balance.talks
    cid = state.player.id
    gen = talk_gen(rng, state.turn, kind_index(kind), source_index(subject.source), subject.key)
    outlet = tb.interview.outlets[int(gen.integers(0, len(tb.interview.outlets)))]
    first, last = draw_name(gen, balance.founder.default_region, data)
    stance = STANCES[int(gen.integers(0, len(STANCES)))]
    cfg = tb.interview if kind == "interview" else tb.crisis
    n = _count(gen, cfg.questions.lo, cfg.questions.hi)
    m = None
    if subject.source == "press":
        m = next((x for x in state.press_moments if x.id == subject.key), None)
    offer = _press_offer(state, m, balance) if kind == "interview" else None
    questions = _press_questions(state, kind, subject, m, n, offer, gen, balance)
    return Talk(
        kind=kind,
        company_id=cid,
        subject=subject,
        opened_turn=state.turn,
        counterpart=Counterpart(
            name=f"{first} {last}",
            role=f"{outlet.beat} reporter",
            organisation=outlet.name,
            beat=outlet.beat,
            stance=stance,
        ),
        questions=questions,
        hidden=TalkHidden(
            receptiveness=_receptiveness(gen, len(questions), tb),
            skill=_founder_skill(state, tb),
        ),
        audience=moments.audience(state, cid, balance),
        offer=offer,
    )


def _trait_factors(
    state: GameState, person_id: int, tb: TalksBalance
) -> tuple[tuple[str, float], ...]:
    """HIDDEN: each move's personality factor from the person's true ego, ambition, loyalty."""
    personality = state.person(person_id).personality
    lo, hi = tb.one_to_one.trait_band.lo, tb.one_to_one.trait_band.hi
    out = []
    for move, (trait, weight) in sorted(tb.one_to_one.trait_weight.items()):
        value = personality.as_dict().get(trait, MID_TRAIT)
        out.append((move, max(lo, min(hi, 1 + weight * (value - MID_TRAIT) / TRAIT_SPAN))))
    return tuple(out)


def open_one_to_one(
    state: GameState,
    person_id: int,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    *,
    morale_shown: int | None,
    causes: tuple[str, ...] = (),
    revealed_interests: tuple[str, ...] = (),
    delegate_id: int | None = None,
) -> Talk:
    """A one-to-one: topics from the engine's view of the person (61.2), worded from what the
    company can see (shown morale and its causes, revealed interests, a rival's approach)."""
    tb = balance.talks
    subject = person_subject(state, person_id)
    person = state.person(person_id)
    e = state.employment_of(person_id)
    assert e is not None
    role_label = next((r.label for r in data.roles if r.key == e.role), e.role)
    gen = talk_gen(rng, state.turn, kind_index("one_to_one"), source_index("person"), person_id)
    name = f"{person.first_name} {person.last_name}"
    mood = f"{name}'s morale shows as {morale_shown} out of 100" if morale_shown is not None else ""
    morale_facts = tuple(x for x in (mood, *causes) if x)
    questions: list[Question] = [
        Question(
            0,
            "morale",
            "How things are",
            f"How are things going for you, {person.first_name}?",
            morale_facts,
        ),
    ]
    up = LADDER[LADDER.index(e.level) + 1] if e.level in LADDER[:-1] else ""
    offer = (
        PromiseOffer(
            "promotion",
            f"a promotion to {up} within {tb.promises.months} months",
            person_id=person_id,
            months=tb.promises.months,
        )
        if up
        else None
    )
    interests = (f"their interests: {', '.join(revealed_interests)}",) if revealed_interests else ()
    questions.append(
        Question(
            0,
            "ambition",
            "Where they want to go",
            "Where do you see yourself going here?",
            (f"{name} is {e.level} {role_label}", *interests),
            offer.words if offer else "",
        )
    )
    if subject.approach_id is not None and subject.rival_id is not None:
        rival = state.company(subject.rival_id).name
        questions.append(
            Question(
                0,
                "approach",
                "The rival's approach",
                f"{rival} has been in touch with me. I'm thinking it over.",
                (f"{rival} has approached {name}",),
                offer.words if offer else "",
                rival,
            )
        )
    stress = state.person_state(person_id).stress
    if stress is not None and stress >= tb.one_to_one.burnout_from:
        questions.append(
            Question(
                0,
                "burnout",
                "Workload",
                "Honestly, I'm running on empty.",
                (f"{name} looks stretched",),
            )
        )
    questions = [
        Question(i, q.topic, q.title, q.question, q.facts, q.offer, q.rival)
        for i, q in enumerate(questions)
    ]
    if delegate_id is not None:
        holder = state.person(delegate_id)
        lo, hi = tb.skill.band.lo, tb.skill.band.hi
        # the delegate's quality draw (40): their skills, moved by up to delegate_noise x band
        noise = (hi - lo) * tb.delegate_noise * (2 * float(gen.random()) - 1)
        skill = skill_factor(holder.skills.as_dict(), tb) + noise
        skill = max(lo, min(hi, skill))
    else:
        skill = _founder_skill(state, tb)
    return Talk(
        kind="one_to_one",
        company_id=state.player.id,
        subject=subject,
        opened_turn=state.turn,
        counterpart=Counterpart(
            name=name,
            role=f"{e.level} {role_label}",
            organisation=state.company(state.player.id).name,
            person_id=person_id,
            morale=morale_shown,
        ),
        questions=tuple(questions),
        hidden=TalkHidden(
            receptiveness=_receptiveness(gen, len(questions), tb),
            skill=skill,
            traits=_trait_factors(state, person_id, tb),
        ),
        audience=1.0,
        offer=offer,
        delegate_id=delegate_id,
    )


def subject_title(talk: Talk) -> str:
    if talk.kind == "one_to_one":
        return f"One-to-one with {talk.counterpart.name}, {format_turn(talk.opened_turn)}"
    what = "Press conference" if talk.kind == "crisis" else "Interview"
    return f"{what}: {talk.subject.words}"
