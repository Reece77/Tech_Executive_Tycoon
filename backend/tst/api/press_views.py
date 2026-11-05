"""Press, promises, credibility, rival CEOs and Replace (M14b, formulas.md 29.6): displayed
values only."""

from __future__ import annotations

from tst.api.schemas.press import (
    CauseOut,
    CredibilityOut,
    FeudOut,
    MomentOut,
    OptionOut,
    PressOut,
    PromiseFormOut,
    PromiseOut,
    ReplaceableOut,
    RivalLeaderOut,
    StatementOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.hiring.recruit import REPLACEABLE, leaver, replace_problem
from tst.sim.press import promises
from tst.sim.press.models import Cause, Promise
from tst.sim.press.names import rival_ceo_id, rival_ceo_name
from tst.sim.press.shares import shown_lead, shown_prices, shown_quality
from tst.sim.state import GameState, credibility_of, feud_of

TRIGGER_LABELS = {
    "launch": "Launch",
    "earnings": "Earnings",
    "era": "Era",
    "outage": "Outage",
    "breach": "Security breach",
    "layoffs": "Layoffs",
    "acquisition": "Acquisition",
    "jab": "Rival's jab",
    "rivalry": "Rivalry",
    "reminder": "Reminder",
}


def _causes(items: tuple[Cause, ...]) -> list[CauseOut]:
    return [
        CauseOut(turn=t, label=format_turn(t), change=round(d, 1), cause=c) for t, d, c in items
    ]


def progress(state: GameState, p: Promise) -> str:
    """Where a promise stands, in displayed values (29.2)."""
    product = state.product(p.product_id) if p.product_id is not None else None
    match p.kind:
        case "ship":
            return f"{product.name}: {product.status.replace('_', ' ')}" if product else "cancelled"
        case "beat":
            rival = state.product(p.rival_product_id) if p.rival_product_id else None
            ours = shown_quality(state, product.id) if product else 0
            theirs = shown_quality(state, rival.id) if rival else 0
            return f"quality {ours} against {rival.name if rival else 'the rival'}'s {theirs}"
        case "research":
            return f"lead {shown_lead(state, p.company_id, p.domain or '')} of {p.level}"
        case "no_layoffs":
            return "no layoffs so far" if p.open else ""
    if product is None:
        return ""
    now = shown_prices(state, product.id)
    raised = [seg for seg, cents in p.prices if now.get(seg, cents) > cents]
    return "a price was raised" if raised else "no price raised so far"


def press_out(state: GameState, data: LoadedData) -> PressOut:
    b = data.balance
    cid = state.player.id
    cred = credibility_of(state, cid)
    mine = [p for p in state.promises if p.company_id == cid]
    answered = next(
        (
            m
            for m in state.press_moments
            if m.company_id == cid
            and m.answered_turn == state.turn
            and m.tone in ("bold", "measured")
            and not any(p.moment_id == m.id for p in state.promises)
        ),
        None,
    )
    products = state.company_products(cid)
    live = [p for p in products if p.status in ("live", "sunset")]
    categories = {p.category for p in live}
    rivals = [
        p
        for p in state.products
        if p.company_id != cid and p.category in categories and p.status in ("live", "sunset")
    ]
    tech = data.game_data.tech
    domains = [
        OptionOut(id=d.key, name=f"{d.label} (lead {shown_lead(state, cid, d.key)})")
        for d in (tech.domains if tech else ())
    ]
    return PressOut(
        credibility=CredibilityOut(
            value=round(cred.value if cred else b.press.cred_start, 1),
            history=_causes(cred.history if cred else ()),
        ),
        promises=[
            PromiseOut(
                promise_id=p.id,
                kind=p.kind,
                words=promises.promise_words(state, p, data.game_data),
                made=format_turn(p.made_turn),
                deadline=format_turn(p.deadline_turn),
                months_left=max(0, p.deadline_turn - state.turn),
                status=p.status,
                progress=progress(state, p),
            )
            for p in sorted(mine, key=lambda p: (p.status != "open", -p.id))
        ],
        moments=[
            MomentOut(
                moment_id=m.id,
                trigger=m.trigger,
                label=TRIGGER_LABELS.get(m.trigger, m.trigger),
                shown=format_turn(m.event_turn) if m.event_turn is not None else None,
                status=m.status,
                tone=m.tone,
                can_promise=answered is not None and answered.id == m.id,
            )
            for m in sorted(state.press_moments, key=lambda m: -m.id)
            if m.company_id == cid and m.status != "pending"
        ][:12],  # tunable-exempt: a year's worth on the panel
        form=PromiseFormOut(
            moment_id=answered.id if answered else None,
            open_count=len(promises.open_promises(state, cid)),
            max_open=b.promise.max_open,
            energy=b.promise.energy,
            months=list(b.promise.months),
            in_development=[
                OptionOut(id=p.id, name=p.name) for p in products if p.status == "in_development"
            ],
            live=[OptionOut(id=p.id, name=p.name) for p in live],
            rival_products=[
                OptionOut(id=p.id, name=f"{p.name} ({state.company(p.company_id).name})")
                for p in rivals
            ],
            domains=domains,
        ),
    )


def feud_out(state: GameState, rival_id: int, data: LoadedData) -> FeudOut:
    cid = state.player.id
    feud = feud_of(state, cid, rival_id)
    return FeudOut(
        rival_id=rival_id,
        rival=state.company(rival_id).name,
        ceo=rival_ceo_name(state, rival_id),
        score=round(feud.score, 1) if feud else 0.0,
        rivalry=bool(feud and feud.score >= data.balance.feud.rivalry),
        causes=_causes(feud.causes if feud else ()),
    )


def rival_leader_out(state: GameState, rival_id: int, data: LoadedData) -> RivalLeaderOut:
    return RivalLeaderOut(
        rival_id=rival_id,
        ceo=rival_ceo_name(state, rival_id),
        ceo_person_id=rival_ceo_id(state, rival_id),
        statements=[
            StatementOut(label=format_turn(s.turn), kind=s.kind, text=s.text)
            for s in sorted(state.statements, key=lambda s: -s.id)
            if s.rival_id == rival_id
        ][:10],  # tunable-exempt: the panel's length
        feud=feud_out(state, rival_id, data),
    )


def replaceable_out(state: GameState, data: LoadedData) -> list[ReplaceableOut]:
    """Resignations serving notice and departures of the last few months (29.5)."""
    cid = state.player.id
    ids = {d.person_id for d in state.departures if d.company_id == cid} | {
        e.person_id
        for e in state.staff(cid)
        if e.status == "notice" and e.end_reason in REPLACEABLE
    }
    out = []
    for pid in sorted(ids):
        left = leaver(state, cid, pid)
        if left is None:
            continue
        problem = replace_problem(state, cid, pid, data.balance)
        person = state.person(pid)
        out.append(
            ReplaceableOut(
                person_id=pid,
                name=f"{person.first_name} {person.last_name}",
                role=data.game_data.role(left.role).label,
                level=left.level,
                reason=left.reason,
                can_replace=problem is None,
                problem=problem,
            )
        )
    return out
