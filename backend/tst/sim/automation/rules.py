"""The area rules added in M27a (docs/formulas.md 40.6), plus Hiring's (40.1).

Every rule chooses from what the company can see (ADR-0015, ADR-0007) and acts through
`AutoRun.attempt` (limits and one-offs) or, for a move a seat would pitch (a region, a research
team, a data centre), through 27.1's pitch with the owner as the pitching executive: under the
limit and not a one-off it goes ahead at once ("auto_approved"); otherwise it waits for the
player. Each rule draws its quality from stream `automation` and states its mistake.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Final

import numpy as np

from tst.sim.actions import CreatePlan, SellCapacity, SetPrice, StopProject
from tst.sim.automation import owners
from tst.sim.automation.config import ONE_OFF_PITCHES
from tst.sim.automation.models import AreaOwner, DecisionKind
from tst.sim.automation.run import ACTION_KEY, AutoRun, automation_draws
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import SimError
from tst.sim.ledger import CASH, account_balance
from tst.sim.log import inbox_item
from tst.sim.org.formulas import decision_quality
from tst.sim.org.models import PitchKind
from tst.sim.products.models import SELLING
from tst.sim.state import GameState, with_pitch

PLAN_CHANNEL: Final = "any"
MONTHS_PER_QUARTER: Final = 3  # tunable-exempt: calendar
MONTHS_PER_YEAR: Final = 12  # tunable-exempt: calendar
BP: Final = 10_000  # tunable-exempt: basis points
PITCH_KEY: Final = 2_000  # tunable-exempt: stream-key offset for an approved pitch's actions


def _right(run: AutoRun, owner: AreaOwner) -> bool:
    b = run.balance
    score = owners.true_area_score(run.state, owner.company_id, owner.area, owner.person_id, b)
    return run.draw() < decision_quality(score, b.automation.quality)


def _quarter_start(turn: int) -> bool:
    return turn % MONTHS_PER_QUARTER == 0


# --- Hiring (40.1) -------------------------------------------------------------------------------


def hiring(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """Backfill: a hiring plan for each role and unit someone left last month or is leaving,
    with the owner as delegate (13.10). Mistake: waits a month. The headcount targets per unit
    the player sets are a follow-up; until then the target is the unit's headcount when the
    person left."""
    state = run.state
    company = owner.company_id
    leaving = sorted(
        {
            (e.role, e.unit_id)
            for e in state.employments
            if e.company_id == company
            and not state.person(e.person_id).is_founder
            and (
                e.status == "notice"
                or (e.status == "ended" and e.end_turn is not None and e.end_turn >= state.turn - 1)
            )
        },
        key=lambda t: (t[0], -1 if t[1] is None else t[1]),
    )
    if not leaving:
        return
    if not _right(run, owner):
        run.decisions.append(("mistake", "left a backfill for next month", 0, None))
        return
    ratio = run.balance.delegates.max_ratio_bp
    for role, unit in leaving:
        if any(
            p.company_id == company
            and p.status == "active"
            and p.role == role
            and p.unit_id == unit
            for p in state.plans
        ):
            continue
        label = data.role(role).label.lower()
        article = "an" if label[:1] in "aeiou" else "a"
        run.text = f"open a plan to replace {article} {label}"
        plan = CreatePlan(owner.person_id, owner.person_id, role, 1, PLAN_CHANNEL, ratio, 0, unit)
        if run.attempt(company, plan):
            run.decisions.append(
                ("decision", f"opened a plan to replace {article} {label}", run.last_cost, None)
            )


# --- Pricing for self-serve and devices (40.6) --------------------------------------------------


def segment_churns(
    state: GameState, category: str, segment: str, data: GameData, b: Balance
) -> dict[int, float]:
    """Shown churn of every product selling in one home segment (11.7, as the product screen)."""
    from tst.sim.products import formulas as f
    from tst.sim.products.phases import segment_appeal, shown_turn

    turn = shown_turn(state)
    products = {p.id: p for p in state.products}
    rows: list[tuple[int, float, float, bool]] = []
    for seg in state.product_segments:
        p = products.get(seg.product_id)
        if p is None or p.category != category or seg.segment != segment:
            continue
        if p.status not in SELLING or seg.price_cents is None:
            continue
        appeal = segment_appeal(p, seg, data, turn)
        if appeal is None:
            continue
        rows.append((p.id, appeal, p.quality, p.status == "sunset"))
    if not rows:
        return {}
    best = max((a for pid, a, _, _ in rows if products[pid].status == "live"), default=0.0)
    base = data.segment(segment).base_churn
    return {pid: f.churn_rate(base, best, a, q, sunset, b.market) for pid, a, q, sunset in rows}


def pricing(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """Each quarter, for each priced self-serve or device segment of a live product, within
    +-price_band of the anchor (the price when the area was given): 5% down if its shown churn
    is above the segment's average and its price above the displayed reference; 5% up if
    supply limits sales or shown churn is churn_low below the average. Mistake: no move."""
    state, b = run.state, run.balance
    if not _quarter_start(state.turn):
        return
    ab = b.automation
    company = owner.company_id
    anchors = {(pid, seg): c for pid, seg, c in run_anchors(state, owner)}
    for p in state.company_products(company):
        if p.status != "live":
            continue
        for seg in state.segments_of(p.id):
            if data.segment(seg.segment).reach == "sales" or seg.price_cents is None:
                continue
            churns = segment_churns(state, p.category, seg.segment, data, b)
            own = churns.get(p.id)
            if own is None:
                continue
            mean = sum(churns.values()) / len(churns)
            reference = data.category(p.category).market(seg.segment).reference_price_cents
            price = seg.price_cents
            anchor = anchors.get((p.id, seg.segment), price)
            if own > mean and price > reference:
                new, why = round(price * (1 - ab.price_step)), "churn above the market's"
            elif seg.capacity_limited or own <= mean * (1 - ab.churn_low):
                new, why = round(price * (1 + ab.price_step)), "demand allows it"
            else:
                continue
            new = max(
                round(anchor * (1 - ab.price_band)), min(round(anchor * (1 + ab.price_band)), new)
            )
            if new == price:
                continue
            label = data.segment(seg.segment).label
            if not _right(run, owner):
                run.decisions.append(("mistake", f"left {p.name}'s {label} price alone", 0, None))
                continue
            text = f"set {p.name}'s {label} price to ${new / 100:,.0f} ({why})"
            run.text = text
            if run.attempt(company, SetPrice(owner.person_id, p.id, seg.segment, new)):
                run.decisions.append(("decision", text, 0, None))


def run_anchors(state: GameState, owner: AreaOwner) -> tuple[tuple[int, str, int], ...]:
    """The anchors pricing moves around: the CRO record's, set when the area was given."""
    a = state.authority(owner.company_id, "cro")
    return a.price_anchors if a is not None else ()


# --- Pitched moves: regions, research teams, data centres (40.6) ---------------------------------


def _recently(
    state: GameState,
    company: int,
    kind: str,
    params: tuple[tuple[str, int | str], ...],
    months: int,
) -> bool:
    for p in state.pitches:
        if p.company_id != company or p.kind != kind or p.params != tuple(sorted(params)):
            continue
        if p.status == "pending":
            return True
        if p.status in ("declined", "lapsed") and (p.resolved_turn or p.turn) > state.turn - months:
            return True
    return False


def pitch_move(
    run: AutoRun,
    owner: AreaOwner,
    kinds: tuple[PitchKind, ...],
    data: GameData,
    *,
    fits: Callable[[object], bool] = lambda c: True,
) -> None:
    """The best candidate of these kinds (the second best on a mistake): under the limit and
    not a one-off it goes ahead; otherwise it waits for the player as a pitch (27.1, 40.2)."""
    from tst.sim.org import pitches

    state, b = run.state, run.balance
    company = owner.company_id
    cash = account_balance(run.balances, company, CASH)
    seat = owners.area_def(b, owner.area).seat or "cto"
    ranked = [
        c
        for c in pitches.candidates(state, company, kinds, cash, b, data, run.balances, seat=seat)
        if fits(c)
        and not _recently(state, company, c.kind, c.params, b.automation.repropose_months)
    ]
    if not ranked:
        return
    right = _right(run, owner)
    pick = ranked[0] if right or len(ranked) == 1 else ranked[1]
    mistake = not right and len(ranked) > 1
    pitch = pitches.make_pitch(state, company, seat, owner.person_id, pick, b)
    state = with_pitch(replace(state, next_ids=state.next_ids.take("pitch")[1]), pitch)
    run.state = state
    person = state.person(owner.person_id)
    name = f"{person.first_name} {person.last_name}"
    cost = pitch.cost_cents
    cap = b.automation.monthly_limit_mult * owner.limit_cents
    if pitch.kind in ONE_OFF_PITCHES or cost >= owner.limit_cents or run.committed + cost > cap:
        why = "it is a one-off" if pitch.kind in ONE_OFF_PITCHES else "it is at or above the limit"
        run.logs.append(pitches._item(state, pitch, name, ""))
        run.decisions.append(("proposal", f"pitched {pitch.title} ({why})", cost, pitch.id))
        return
    turn, key = state.turn, ACTION_KEY + PITCH_KEY + run.area_index

    def draws(n: int) -> Callable[[], np.random.Generator]:
        return lambda: automation_draws(run.rng, turn, owner.person_id, key, n)

    founder = state.founder_of(company)
    try:
        out = pitches.approve(
            state,
            pitch,
            founder.id if founder else owner.person_id,
            run.rng,
            b,
            data,
            run.balances,
            draws,
            status="auto_approved",
        )
    except SimError as exc:
        run.decisions.append(("decision", f"could not go ahead with {pitch.title}: {exc}", 0, None))
        return
    run.state, run.balances = out.state, out.balances
    run.entries += out.entries
    run.logs += [replace(i, in_digest=True) for i in out.logs]
    run.taken += [(company, a) for a in out.actions]
    run.committed += cost
    run.logs.append(
        replace(
            inbox_item(
                turn,
                company,
                "pitch_went_ahead",
                link_kind="person",
                link_id=owner.person_id,
                name=name,
                what=pitch.title,
                detail=pitches.pitch_text(out.state, pitch),
                cost_cents=cost,
            ),
            in_digest=True,
        )
    )
    kind: DecisionKind = "mistake" if mistake else "decision"
    run.decisions.append((kind, f"went ahead with {pitch.title}", cost, pitch.id))


def _moved_within(state: GameState, company: int, kind: str, months: int) -> bool:
    """A pitch of this kind (gone ahead, approved or waiting) within the last `months`."""
    return any(
        p.company_id == company
        and p.kind == kind
        and p.status in ("pending", "approved", "auto_approved", "modified")
        and p.turn > state.turn - months
        for p in state.pitches
    )


def regions(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """In a quarter's first month, at most once every regions_every_months, 27.1's CRO
    candidate: a launch under the limit goes ahead (40.6)."""
    every = run.balance.automation.regions_every_months
    if _quarter_start(run.state.turn) and not _moved_within(
        run.state, owner.company_id, "region", every
    ):
        pitch_move(run, owner, ("region",), data)


def research(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """Spending at most research_budget_bp of trailing revenue; each quarter the best research
    candidate that fits the budget; a project whose domain feeds no live product stops.
    Licensing deals are one-offs. Mistake: the second-best project."""
    from tst.sim.automation.kpis import _research_cents
    from tst.sim.research import levels

    state, b = run.state, run.balance
    company = owner.company_id
    live = {p.category for p in state.company_products(company) if p.status in SELLING}
    for project in state.active_projects(company):
        if project.unit_id is None or set(levels.feeds(data, project.domain)) & live:
            continue
        label = levels.domain_def(data, project.domain).label
        run.text = f"stop the {label} project (no live product draws on it)"
        if run.attempt(company, StopProject(owner.person_id, project.id)):
            run.decisions.append(("decision", f"stopped the {label} project", 0, None))
    every = b.automation.research_every_months
    if not _quarter_start(state.turn) or _moved_within(run.state, company, "research", every):
        return
    history = run.state.company(company).mrr_history[-MONTHS_PER_YEAR:]
    budget = sum(history) * b.automation.research_budget_bp // BP // MONTHS_PER_YEAR
    room = budget - _research_cents(run.state, company, data)
    pitch_move(
        run,
        owner,
        ("research",),
        data,
        fits=lambda c: getattr(c, "monthly_cents", 0) <= room,
    )


def cloud(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """Projected data-centre use between the guardrails (cloud_band): below the band, sell the
    spare capacity at spot; above it, pitch a data centre (a one-off) when 27.1's CTO test
    holds. Mistake: a month late."""
    from tst.sim.automation.kpis import _capacity, _dc_use
    from tst.sim.facilities import compute

    state, b = run.state, run.balance
    company = owner.company_id
    lo, hi = b.automation.cloud_band
    cap = _capacity(state, company, b)
    use = _dc_use(state, company, b, data) / 100 if cap > 0 else None
    if use is not None and use < lo and compute.capacity_product(state, company, data) is None:
        if not _right(run, owner):
            run.decisions.append(("mistake", "left spare capacity unsold this month", 0, None))
            return
        run.text = f"sell spare capacity at spot (use {use:.0%})"
        if run.attempt(company, SellCapacity(owner.person_id)):
            run.decisions.append(
                ("decision", f"began selling spare capacity (use {use:.0%})", 0, None)
            )
        return
    if use is None or use > hi:
        pitch_move(run, owner, ("data_centre",), data)


def answered_at_continue(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """Press and Routine events act at Continue (40.5; tst.sim.automation.events)."""


RULES: dict[str, Callable[[AutoRun, AreaOwner, GameData], None]] = {
    "hiring": hiring,
    "pricing": pricing,
    "research": research,
    "regions": regions,
    "cloud": cloud,
    "press": answered_at_continue,
    "events": answered_at_continue,
}
