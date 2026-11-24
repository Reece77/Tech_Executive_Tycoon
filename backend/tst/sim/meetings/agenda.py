"""Opening a meeting (docs/formulas.md 59.1-59.3): when each kind is held, who speaks, and the
agenda built from the engine's displayed facts. The speakers' priorities and receptiveness are
drawn here (stream `meetings`, key (kind index, meeting turn); ADR-0013) and kept HIDDEN.

A director's priorities come from their personality (true values, the engine's only: growth
from ambition, margin from professionalism, risk from caution, governance from integrity),
moved by the meeting's draw. An analyst weighs its public focus double. Askers are chosen by
the draw, never by the priorities, so who asks reveals nothing hidden."""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from typing import Final

import numpy as np

from tst.sim import dmath
from tst.sim.calendar import format_turn, turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import MeetingRuleError
from tst.sim.finance.board import actual_growth, average_confidence
from tst.sim.finance.captable import last_round
from tst.sim.finance.statements import projected_runway
from tst.sim.markets_public import formulas as pf
from tst.sim.markets_public.ipo import quarter_start
from tst.sim.markets_public.public import consensus
from tst.sim.meetings.config import (
    MEETING_KINDS,
    TOPICS,
    MeetingKind,
    MeetingsBalance,
    PlanKind,
    Topic,
)
from tst.sim.meetings.models import Figure, Item, Meeting, MeetingHidden, Plan, Speaker
from tst.sim.modes.models import world_start_turn
from tst.sim.negotiation.deals import negotiator
from tst.sim.people.generator import draw_name
from tst.sim.press.moments import credibility
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, guidance_for, public_of

QUARTER: Final = 3  # tunable-exempt: months in a quarter (25.4)
QUARTERS: Final = 4  # tunable-exempt: quarters in a year
MONTHS_A_YEAR: Final = 12
ANALYST_FOCUS: Final[tuple[Topic, ...]] = ("growth", "margin", "risk")
FOCUS_WEIGHT: Final = 2.0  # tunable-exempt: an analyst weighs its focus double the rest
ATTR_MAX: Final = 20.0  # tunable-exempt: the attribute scale (1-20)
TRAIT_FLIP: Final = ATTR_MAX + 1  # a reversed trait: 21 - value
TRAIT_MID: Final = ATTR_MAX / 2
FALL_FLOOR: Final = -0.5  # tunable-exempt: a plan never assumes revenue falling faster
UNITS: Final = ((10**9, "B"), (10**6, "M"), (10**3, "K"))  # tunable-exempt: number units
SHORT_RUNWAY: Final = 6  # tunable-exempt: 14.6's runway band below which the board worries
RESULT_WORDS: Final = {"beat": "a beat", "inline": "in line", "miss": "a miss"}


def meeting_gen(rng: RngFactory, turn: int, *key: int) -> np.random.Generator:
    """The one call site of stream `meetings` (ADR-0013, formulas.md 59)."""
    return rng.stream(turn, "meetings", *key)


def kind_index(kind: MeetingKind) -> int:
    return MEETING_KINDS.index(kind)


def money_words(cents: int) -> str:
    """$12.3M, $450.0K, $8,200: a round figure for questions and facts."""
    sign = "-" if cents < 0 else ""
    dollars = Fraction(abs(cents), 100)
    for size, unit in UNITS:
        if dollars >= size:
            return f"{sign}${float(dollars / size):,.1f}{unit}"
    return f"{sign}${float(dollars):,.0f}"


def pct_words(bp: int) -> str:
    return f"{bp / 100:.1f}%"


# --- When -----------------------------------------------------------------------------------


def board_problem(state: GameState, balance: Balance) -> str | None:
    """A quarterly board meeting is held in the month after a meeting month (14.6's summary),
    for a company with voting directors."""
    cid = state.player.id
    if not any(s.votes and s.person_id is not None for s in state.board(cid)):
        return "there is no board with voting directors yet"
    # M50: no month has passed in the game's first month (-24 in a 2008 game, 0 in a 2010 one)
    if (
        state.turn <= world_start_turn(state.mode)
        or turn_to_ym(state.turn - 1)[1] not in balance.board.meeting_months
    ):
        return "the board meets in the month after each quarter's end"
    return None


def call_problem(state: GameState) -> str | None:
    """An earnings call follows each quarterly report once listed (25.4)."""
    cid = state.player.id
    public = public_of(state, cid)
    if public is None:
        return "earnings calls start once the company is listed"
    begun = state.turn > world_start_turn(state.mode)  # M50: no quarter before the first month
    g = guidance_for(state, cid, quarter_start(state.turn - 1)) if begun else None
    if g is None or not g.reported or state.turn % QUARTER:
        return "an earnings call follows a quarterly report, in the quarter's first month"
    if not public.analysts:
        return "no analyst covers the company yet"
    return None


def day_problem(state: GameState) -> str | None:
    if public_of(state, state.player.id) is None:
        return "investor days are for a listed company"
    return None


def problem(state: GameState, kind: MeetingKind, balance: Balance) -> str | None:
    if kind == "board":
        return board_problem(state, balance)
    if kind == "call":
        return call_problem(state)
    return day_problem(state)


# --- Facts (displayed values only) -----------------------------------------------------------


def quarter_revenue(state: GameState, cid: int) -> int:
    return sum(state.company(cid).mrr_history[-QUARTER:])


def quarter_margin_bp(state: GameState, cid: int) -> int:
    company = state.company(cid)
    return pf.margin_bp(sum(company.op_history[-QUARTER:]), quarter_revenue(state, cid))


def _year_margin_bp(state: GameState, cid: int) -> int | None:
    company = state.company(cid)
    ops = company.op_history[-MONTHS_A_YEAR:]
    if not ops:
        return None
    return pf.margin_bp(sum(ops), sum(company.mrr_history[-len(ops) :]))


def plan_revenue(state: GameState, cid: int, balance: Balance) -> int | None:
    """Next quarter's plan figure: the analysts' consensus once listed, else last quarter's
    revenue grown at the last six months' annual rate for a quarter."""
    if public_of(state, cid) is not None:
        return consensus(state, cid)[0] or None
    last = quarter_revenue(state, cid)
    if last <= 0:
        return None
    g = actual_growth(state, cid, balance) or 0.0
    quarterly = dmath.pow(1 + max(g, FALL_FLOOR), 1 / QUARTERS) - 1
    return max(1, round(Fraction(last) * (1 + Fraction(quarterly))))


def facts(
    state: GameState, cid: int, cash_cents: int, balance: Balance, data: GameData
) -> dict[str, str]:
    """The displayed facts a meeting may cite, by name: what the player's own screens show."""
    out: dict[str, str] = {}
    out["revenue"] = f"revenue last quarter was {money_words(quarter_revenue(state, cid))}"
    g = actual_growth(state, cid, balance)
    latest = last_round(state, cid)
    if g is not None:
        moved = f"grew {g:.0%}" if g >= 0 else f"fell {-g:.0%}"
        words = f"revenue {moved} a year over the last six months"
        if latest is not None:
            words += f", against the {balance.board.expected_growth[latest.series]:.0%} expected"
        out["growth"] = words
    margin = _year_margin_bp(state, cid)
    if margin is not None:
        out["margin"] = f"operating margin over the last year was {pct_words(margin)}"
    runway = projected_runway(state, cid, cash_cents, balance, data)
    out["runway"] = (
        "the company is profitable" if runway is None else f"cash lasts about {runway} months"
    )
    out["cash"] = f"cash is {money_words(cash_cents)}"
    out["credibility"] = f"credibility is {credibility(state, cid, balance):.0f} out of 100"
    avg = average_confidence(state, cid)
    if avg is not None:
        out["board"] = f"the board's average confidence is {avg:.0f}"
    public = public_of(state, cid)
    if public is not None and state.turn:
        g_last = guidance_for(state, cid, quarter_start(state.turn - 1))
        if g_last is not None and g_last.reported and g_last.actual_revenue_cents is not None:
            out["result"] = (
                f"last quarter's revenue was {money_words(g_last.actual_revenue_cents)} against "
                f"{money_words(g_last.revenue_cents)} guided: "
                f"{RESULT_WORDS[g_last.result or 'inline']}"
            )
            if g_last.actual_margin_bp is not None:
                out["quarter_margin"] = (
                    f"last quarter's operating margin was {pct_words(g_last.actual_margin_bp)} "
                    f"against {pct_words(g_last.margin_bp)} guided"
                )
        rev_c, margin_c = consensus(state, cid)
        out["consensus"] = (
            f"the consensus for this quarter is revenue of {money_words(rev_c)} at a "
            f"{pct_words(margin_c)} margin"
        )
        if public.miss_streak:
            out["misses"] = f"{public.miss_streak} misses in a row"
        if public.last_activist_turn is not None:
            out["activist"] = (
                "an activist investor has built a stake "
                f"(since {format_turn(public.last_activist_turn)})"
            )
    return out


def _pick(f: dict[str, str], *names: str) -> tuple[str, ...]:
    return tuple(f[n] for n in names if n in f)


# --- Speakers and draws ------------------------------------------------------------------------


def _weights(
    raw: Sequence[float], gen: np.random.Generator, mb: MeetingsBalance
) -> tuple[float, ...]:
    moved = [max(v, 0.0) * (1 + mb.priority_noise * (2 * float(gen.random()) - 1)) for v in raw]
    total = sum(moved) or 1.0
    return tuple(v / total for v in moved)


def _director_raw(state: GameState, person_id: int | None, mb: MeetingsBalance) -> list[float]:
    if person_id is None:
        return [1.0] * len(TOPICS)
    values = dict(state.person(person_id).personality.items)
    out = []
    for topic in TOPICS:
        trait = mb.priority_traits[topic]
        if trait.startswith("-"):
            out.append(TRAIT_FLIP - values.get(trait[1:], TRAIT_MID))
        else:
            out.append(values.get(trait, TRAIT_MID))
    return out


def founder_factor(skills: dict[str, float], mb: MeetingsBalance) -> float:
    """59.1: the founder's weighted communication and leadership (1-20), onto the band."""
    score = sum(skills.get(k, 1.0) * w for k, w in mb.skill.weights.items())
    lo, hi = mb.skill.band.lo, mb.skill.band.hi
    return lo + (hi - lo) * (min(max(score, 1.0), ATTR_MAX) - 1.0) / (ATTR_MAX - 1.0)


def _analysts(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> list[Speaker]:
    public = public_of(state, state.player.id)
    assert public is not None
    firms = balance.public.analysts.firms
    out = []
    for a in public.analysts:
        # an analyst's name and focus are theirs for the listing: key (call, 0, index)
        gen = meeting_gen(rng, public.listed_turn, kind_index("call"), 0, a.index)
        first, last = draw_name(gen, balance.founder.default_region, data)
        focus = ANALYST_FOCUS[int(gen.integers(0, len(ANALYST_FOCUS)))]
        out.append(
            Speaker(
                key=f"analyst:{a.index}",
                kind="analyst",
                name=f"{first} {last}",
                role="equity analyst",
                organisation=firms[a.index % len(firms)],
                analyst_index=a.index,
                focus=focus,
                rating=a.rating,
                target_cents=a.target_cents,
            )
        )
    return out


def _directors(state: GameState) -> list[Speaker]:
    out = []
    for seat in state.board(state.player.id):
        if not seat.votes or seat.confidence is None or seat.person_id is None:
            continue
        person = state.person(seat.person_id)
        out.append(
            Speaker(
                key=f"seat:{seat.id}",
                kind="director",
                name=f"{person.first_name} {person.last_name}",
                role="investor director" if seat.kind == "investor" else "independent director",
                organisation=seat.firm or "independent",
                seat_id=seat.id,
                confidence=round(seat.confidence, 1),
            )
        )
    return out


def _investors(
    gen: np.random.Generator, mb: MeetingsBalance, balance: Balance, data: GameData
) -> list[Speaker]:
    firms = list(mb.investor_day.firms)
    order = [int(i) for i in gen.permutation(len(firms))][: mb.investor_day.questions]
    out = []
    for i in order:
        first, last = draw_name(gen, balance.founder.default_region, data)
        out.append(
            Speaker(
                key=f"investor:{i}",
                kind="investor",
                name=f"{first} {last}",
                role="portfolio manager",
                organisation=firms[i],
            )
        )
    return out


def _askers(gen: np.random.Generator, speakers: int, items: int) -> list[int]:
    """Who asks each item: a shuffled round of the speakers, repeated (the draw only)."""
    out: list[int] = []
    while len(out) < items:
        out += [int(i) for i in gen.permutation(speakers)]
    return out[:items]


# --- Agendas ------------------------------------------------------------------------------------


def _board_items(
    state: GameState,
    speakers: list[Speaker],
    f: dict[str, str],
    gen: np.random.Generator,
    balance: Balance,
    runway: int | None,
) -> list[Item]:
    from tst.sim.finance.board import growth_term

    cid = state.player.id
    mb = balance.meetings
    public = public_of(state, cid)
    g_last = guidance_for(state, cid, quarter_start(state.turn - 1)) if public else None
    missed = g_last is not None and g_last.result == "miss"
    drafts: list[tuple[Topic, str, str, tuple[str, ...], bool, Figure | None]] = []
    drafts.append(
        (
            "growth",
            "Results against plan",
            "How did the quarter go against what you told us to expect?",
            _pick(f, "revenue", "growth", "result"),
            growth_term(state, cid, balance) < 0 or missed,
            None,
        )
    )
    plan = plan_revenue(state, cid, balance)
    drafts.append(
        (
            "growth",
            "Next quarter's plan",
            "What revenue will you deliver next quarter, and how?"
            if plan is not None
            else "When does revenue start, and what has to happen first?",
            _pick(f, "revenue", "growth", "margin", "consensus"),
            False,
            Figure(
                "revenue",
                plan,
                f"revenue of at least {money_words(plan)} in the quarter to "
                f"{format_turn(state.turn + QUARTER - 1)}",
            )
            if plan is not None
            else None,
        )
    )
    drafts.append(
        (
            "risk",
            "Cash and runway",
            "How long does the cash last, and what is the plan if it runs short?",
            _pick(f, "runway", "cash"),
            runway is not None and runway < SHORT_RUNWAY,
            None,
        )
    )
    worried = [s for s in speakers if (s.confidence or 0) < mb.board.concern_below]
    if worried or missed or "activist" in f:
        drafts.append(
            (
                "governance",
                "A director's concern",
                "Frankly, some of us are worried. Why should we keep backing this plan?",
                _pick(f, "board", "credibility", "result", "activist"),
                True,
                None,
            )
        )
    drafts = drafts[: mb.board.items]
    askers = _askers(gen, len(speakers), len(drafts))
    if worried and drafts[-1][0] == "governance":  # the lowest-confidence director asks it
        low = min(worried, key=lambda s: (s.confidence or 0, s.key))
        askers[-1] = speakers.index(low)
    return [
        Item(n, askers[n], topic, title, q, fs, prob, fig)
        for n, (topic, title, q, fs, prob, fig) in enumerate(drafts)
    ]


def _call_items(
    state: GameState, speakers: list[Speaker], f: dict[str, str], balance: Balance
) -> tuple[list[Item], tuple[int, int]]:
    cid = state.player.id
    cb = balance.meetings.call
    public = public_of(state, cid)
    assert public is not None
    g_last = guidance_for(state, cid, quarter_start(state.turn - 1))
    assert g_last is not None
    missed = g_last.result == "miss"
    now = guidance_for(state, cid, state.turn)
    base = (now.revenue_cents, now.margin_bp) if now is not None else consensus(state, cid)
    items = [
        Item(
            0,
            0,
            "growth",
            "Guidance",
            "What is your guidance for this quarter?",
            _pick(f, "result", "consensus", "revenue"),
            missed,
            Figure(
                "revenue",
                base[0],
                f"revenue of at least {money_words(base[0])} in the quarter to "
                f"{format_turn(state.turn + QUARTER - 1)}",
            ),
            True,
        )
    ]
    margin_low = g_last.actual_margin_bp is not None and g_last.actual_margin_bp < g_last.margin_bp
    for i, s in enumerate(speakers[1 : cb.questions], start=1):
        if s.focus == "margin":
            items.append(
                Item(
                    i,
                    i,
                    "margin",
                    "Margins",
                    "Where are costs going, and when do margins improve?",
                    _pick(f, "quarter_margin", "margin"),
                    margin_low,
                    Figure(
                        "margin",
                        base[1],
                        f"an operating margin of at least {pct_words(base[1])} this quarter",
                    ),
                )
            )
        elif s.focus == "risk":
            risky = missed or "activist" in f or public.miss_streak > 0
            items.append(
                Item(
                    i,
                    i,
                    "risk",
                    "Risks",
                    "What is the biggest risk to the plan, and what are you doing about it?",
                    _pick(f, "runway", "misses", "activist", "credibility"),
                    risky,
                )
            )
        else:
            items.append(
                Item(
                    i,
                    i,
                    "growth",
                    "Growth",
                    "What drove revenue last quarter, and does it last?",
                    _pick(f, "result", "growth", "revenue"),
                    missed,
                )
            )
    return items, (base[0], base[1])


def _day_items(
    speakers: list[Speaker], plan: Plan, f: dict[str, str], balance: Balance, cred: float
) -> list[Item]:
    mb = balance.meetings
    drafts: list[tuple[Topic, str, str, tuple[str, ...], bool]] = [
        (
            "margin",
            "The economics",
            f"Walk us through the economics of {plan.subject}. Why will it earn its capital?",
            plan.facts,
            plan.economics < 0,
        ),
        (
            "risk",
            "Execution",
            "What gives us confidence you can execute this?",
            _pick(f, "credibility", "runway", "result"),
            cred <= mb.credibility.half_at,
        ),
        (
            "growth",
            "Growth",
            "What does this do to growth over the next three years?",
            _pick(f, "growth", "revenue", "margin"),
            False,
        ),
    ]
    drafts = drafts[: mb.investor_day.questions]
    return [
        Item(n, n % len(speakers), t, title, q, fs, prob)
        for n, (t, title, q, fs, prob) in enumerate(drafts)
    ]


def open_meeting(
    state: GameState,
    kind: MeetingKind,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    cash_cents: int,
    plan: Plan | None = None,
) -> Meeting:
    """59: the meeting this month, its speakers' hidden priorities and its agenda."""
    why = problem(state, kind, balance)
    if why is not None:
        raise MeetingRuleError(why)
    mb = balance.meetings
    cid = state.player.id
    gen = meeting_gen(rng, state.turn, kind_index(kind), state.turn)
    f = facts(state, cid, cash_cents, balance, data)
    cred = credibility(state, cid, balance)
    guidance_base: tuple[int, int] | None = None
    if kind == "board":
        speakers = _directors(state)
        people = {seat.id: seat.person_id for seat in state.board(cid)}
        raws = [_director_raw(state, people.get(s.seat_id or -1), mb) for s in speakers]
        subject = f"Board meeting, {format_turn(state.turn)}"
    elif kind == "call":
        speakers = _analysts(state, rng, balance, data)
        raws = [[FOCUS_WEIGHT if t == s.focus else 1.0 for t in TOPICS] for s in speakers]
        subject = f"Earnings call, {format_turn(state.turn)}"
    else:
        if plan is None:
            raise MeetingRuleError("an investor day presents a plan")
        speakers = _investors(gen, mb, balance, data)
        raws = [[1.0] * len(TOPICS) for _ in speakers]
        subject = f"Investor day: {plan.subject}"
    if not speakers:
        raise MeetingRuleError("no one to meet")
    priorities = tuple(_weights(r, gen, mb) for r in raws)
    lo, hi = mb.receptiveness.lo, mb.receptiveness.hi
    receptiveness = tuple(lo + (hi - lo) * float(gen.random()) for _ in speakers)
    if kind == "board":
        runway = projected_runway(state, cid, cash_cents, balance, data)
        items = _board_items(state, speakers, f, gen, balance, runway)
    elif kind == "call":
        items, guidance_base = _call_items(state, speakers, f, balance)
    else:
        assert plan is not None
        items = _day_items(speakers, plan, f, balance, cred)
    skills, persona = negotiator(state, balance)
    return Meeting(
        kind=kind,
        company_id=cid,
        subject=subject,
        opened_turn=state.turn,
        period_turn=state.turn,
        speakers=tuple(speakers),
        items=tuple(items),
        hidden=MeetingHidden(priorities, receptiveness, founder_factor(skills, mb)),
        persona=persona,
        credibility=round(cred, 1),
        guidance_base=guidance_base,
        plan=plan,
    )


def plan_for(
    kind: PlanKind,
    subject: str,
    facts_shown: tuple[str, ...],
    roc: float | None,
    mb: MeetingsBalance,
) -> Plan:
    """An investor day's plan, its economics scored from the displayed return on capital
    (the conglomerate view's, M43): (roc - hurdle) / span, within -1..1; 0 with none."""
    if not subject.strip():
        raise MeetingRuleError("name the plan")
    d = mb.investor_day
    score = 0.0 if roc is None else max(-1.0, min(1.0, (roc - d.hurdle) / d.span))
    return Plan(kind, subject.strip(), facts_shown, score)
