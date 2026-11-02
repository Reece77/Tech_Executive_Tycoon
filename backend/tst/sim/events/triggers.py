"""Triggers (docs/formulas.md 16.2): what is happening in the player's company this month,
computed from true state in phase 12. True values are allowed here and never leave the
engine: the hits name only who and what an event is about, not why.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from tst.sim.data_models import Balance, GameData, TriggerBalance
from tst.sim.events.formulas import below_strength, clamp01
from tst.sim.finance.board import average_confidence
from tst.sim.finance.statements import projected_runway
from tst.sim.money import Cents
from tst.sim.org.executives import acting_seats
from tst.sim.org.morale import market_mid_for
from tst.sim.org.rules import org_view
from tst.sim.people.models import current_ability
from tst.sim.rivals.models import RivalMove
from tst.sim.state import GameState

ENTERPRISE = "enterprise"  # categories.yaml segment: the first such customer is a milestone
MONTHS_PER_YEAR = 12  # tunable-exempt: calendar
POLITICIAN = "politician"
PRICE_CUT = "price_cut"
NOT_MOVES = frozenset({"founded", "launched", "funded", "failed"})  # startup news, not actions


@dataclass(frozen=True, slots=True)
class TriggerHit:
    trigger: str
    strength: float
    person_ids: tuple[int, ...] = ()
    unit_id: int | None = None
    product_id: int | None = None
    segment: str | None = None
    rival_id: int | None = None
    months: int | None = None
    critical_ok: bool = False


def _fixed(cfg: TriggerBalance) -> float:
    return float(cfg.strength) if isinstance(cfg.strength, (int, float)) else 0.0


def triggers(
    state: GameState,
    start: GameState,
    balance: Balance,
    data: GameData,
    cash: Cents,
    rival_moves: tuple[RivalMove, ...],
) -> list[TriggerHit]:
    """Every trigger that holds for the player this month, in 16.2 table order, each
    trigger's hits by person, unit, pair or product id. `start` is the state at the start
    of the turn (for milestones)."""
    t = balance.events.trigger
    company = state.player
    cid = company.id
    view = org_view(state, cid)
    founder = state.founder_of(cid)
    founder_id = founder.id if founder else None
    staff = [
        e
        for e in sorted(state.staff(cid), key=lambda e: e.person_id)
        if e.person_id != founder_id and e.status == "active"
    ]
    morale = {e.person_id: state.person_state(e.person_id).morale for e in staff}
    hits: list[TriggerHit] = []

    for e in staff:  # low_morale
        m = morale[e.person_id]
        s = None if m is None else below_strength(m, t["low_morale"])
        if s is not None:
            hits.append(TriggerHit("low_morale", s, (e.person_id,), view.unit_of[e.person_id]))

    by_unit: dict[int | None, list[float]] = {}
    for e in staff:  # unhappy_unit
        m = morale[e.person_id]
        if m is not None:
            by_unit.setdefault(view.unit_of[e.person_id], []).append(m)
    for unit_id in sorted(by_unit, key=lambda u: -1 if u is None else u):
        values = by_unit[unit_id]
        if len(values) < 2:  # tunable-exempt: a unit is at least two people
            continue
        s = below_strength(sum(values) / len(values), t["unhappy_unit"])
        if s is not None:
            hits.append(TriggerHit("unhappy_unit", s, (), unit_id))

    for e in staff:  # underpaid
        mid = market_mid_for(state, e, balance, data)
        s = below_strength(e.salary_cents / mid, t["underpaid"]) if mid else None
        if s is not None:
            hits.append(TriggerHit("underpaid", s, (e.person_id,), view.unit_of[e.person_id]))

    star = t["star_performer"]  # top 10% of CA among employees, tenure >= 12 months
    ranked = sorted(
        staff, key=lambda e: (-current_ability(state.person(e.person_id), data), e.person_id)
    )
    top = ranked[: max(1, math.ceil(len(ranked) * float(star.top_fraction or 0)))] if ranked else []
    for e in sorted(top, key=lambda e: e.person_id):
        if state.turn - e.start_turn >= (star.tenure_months or 0):
            hits.append(
                TriggerHit(
                    "star_performer", _fixed(star), (e.person_id,), view.unit_of[e.person_id]
                )
            )

    active = {e.person_id for e in staff}
    rels = [r for r in state.relationships if r.a in active and r.b in active]
    clash, bond = t["team_clash"], t["team_bond"]
    for r in rels:  # team_clash: same unit
        if view.unit_of[r.a] == view.unit_of[r.b] and r.value <= float(clash.at_most or 0):
            s = clamp01((float(clash.at_most or 0) - r.value) / float(clash.span or 1))
            hits.append(TriggerHit("team_clash", s, (r.a, r.b), view.unit_of[r.a]))
    for r in rels:  # team_bond
        if r.value >= float(bond.at_least or 0):
            hits.append(TriggerHit("team_bond", _fixed(bond), (r.a, r.b), view.unit_of[r.a]))

    politics = t["office_politics"]
    for e in staff:
        unit_id = view.unit_of[e.person_id]
        if POLITICIAN in state.person(e.person_id).tags and len(view.members.get(unit_id, ())) >= (
            politics.unit_size or 0
        ):
            hits.append(TriggerHit("office_politics", _fixed(politics), (e.person_id,), unit_id))

    for e in staff:  # tag_noticed: the player noticed a tag this month
        reveal = state.reveal(cid, e.person_id)
        if reveal is not None and any(turn == state.turn for _, turn in reveal.revealed_tags):
            hits.append(
                TriggerHit(
                    "tag_noticed",
                    _fixed(t["tag_noticed"]),
                    (e.person_id,),
                    view.unit_of[e.person_id],
                )
            )

    for e in staff:  # anniversary
        tenure = state.turn - e.start_turn
        if tenure > 0 and tenure % MONTHS_PER_YEAR == 0:
            hits.append(
                TriggerHit(
                    "anniversary",
                    _fixed(t["anniversary"]),
                    (e.person_id,),
                    view.unit_of[e.person_id],
                )
            )

    products = [p for p in state.company_products(cid) if p.status != "retired"]
    for p in products:
        if p.launched_turn == state.turn:
            hits.append(
                TriggerHit("product_launched", _fixed(t["product_launched"]), product_id=p.id)
            )
    for p in products:
        if p.rotting and p.launched_turn is not None:
            hits.append(
                TriggerHit("product_slipping", _fixed(t["product_slipping"]), product_id=p.id)
            )

    mine = {(p.category, s.segment): p.id for p in products for s in state.segments_of(p.id)}
    for kind in ("price_war", "rival_move"):
        seen: set[tuple[int, int, str]] = set()
        for move in rival_moves:
            if move.action in NOT_MOVES or move.product_id is None or move.segment is None:
                continue
            if kind == "price_war" and move.action != PRICE_CUT:
                continue
            theirs = state.product(move.product_id)
            mine_id = mine.get((theirs.category, move.segment)) if theirs else None
            key = (move.company_id, mine_id or 0, move.segment)
            if mine_id is None or key in seen:
                continue
            seen.add(key)
            hits.append(
                TriggerHit(
                    kind,
                    _fixed(t[kind]),
                    product_id=mine_id,
                    segment=move.segment,
                    rival_id=move.company_id,
                )
            )

    for a in state.approaches:  # poached: joined a rival this month
        if a.status == "joined" and a.resolved_turn == state.turn:
            hits.append(TriggerHit("poached", _fixed(t["poached"]), rival_id=a.rival_id))

    before = {p.id: p for p in start.company_products(cid)}
    for p in products:  # customer_milestone
        now = {s.segment: s.customers for s in state.segments_of(p.id)}
        then = {s.segment: s.customers for s in start.segments_of(p.id)} if p.id in before else {}
        total_now, total_then = sum(now.values()), sum(then.values())
        first_enterprise = now.get(ENTERPRISE, 0.0) >= 1 > then.get(ENTERPRISE, 0.0)
        tens = total_now >= 10 and math.floor(math.log10(total_now)) > (  # tunable-exempt: 16.2
            math.floor(math.log10(total_then)) if total_then >= 1 else 0
        )
        if first_enterprise or tens:
            segment = ENTERPRISE if first_enterprise else max(now, key=lambda k: now[k])
            hits.append(
                TriggerHit(
                    "customer_milestone",
                    _fixed(t["customer_milestone"]),
                    product_id=p.id,
                    segment=segment,
                )
            )

    runway = projected_runway(state, cid, cash, balance, data)
    rs = t["runway_short"]
    limits, strengths = rs.months or [], rs.strength if isinstance(rs.strength, list) else []
    if runway is not None and limits and runway < limits[0]:
        critical = runway < limits[1]
        hits.append(
            TriggerHit(
                "runway_short",
                strengths[1] if critical else strengths[0],
                months=runway,
                critical_ok=critical,
            )
        )

    if any(r.company_id == cid and r.closed_turn == state.turn for r in state.rounds):
        hits.append(TriggerHit("funding_closed", _fixed(t["funding_closed"])))

    confidence = average_confidence(state, cid)
    s = None if confidence is None else below_strength(confidence, t["board_unhappy"])
    if s is not None:
        hits.append(TriggerHit("board_unhappy", s))

    hits += _executive_hits(state, balance, runway)

    own = state.company_products(cid)
    if not any(p.status == "live" for p in own):  # early_days (M7a): nothing to sell yet
        building = next((p.id for p in own if p.status == "in_development"), None)
        hits.append(TriggerHit("early_days", _fixed(t["early_days"]), product_id=building))

    if not hits:
        hits.append(TriggerHit("quiet_month", _fixed(t["quiet_month"])))
    return hits


def _executive_hits(state: GameState, balance: Balance, runway: int | None) -> list[TriggerHit]:
    """M10c (24.3): each seat holder with authority can raise their function's event; the
    CFO warns when runway is below their own guardrail; two seat holders clash when their
    relationship is low."""
    t = balance.events.trigger
    cid = state.player.id
    hits: list[TriggerHit] = []
    acting = acting_seats(state, cid)
    for a, holder in acting:
        if a.seat in ("cto", "cro", "cmo"):
            key = f"exec_{a.seat}"
            hits.append(TriggerHit(key, _fixed(t[key]), (holder,)))
        elif a.seat == "cfo" and runway is not None and runway < a.number("runway_months"):
            hits.append(TriggerHit("exec_cfo", _fixed(t["exec_cfo"]), (holder,), months=runway))
    holders = {h for h in (state.seat_holder(cid, s.seat) for s in state.exec_seats) if h}
    holders = {h for h in holders if (e := state.employment_of(h)) and e.company_id == cid}
    clash = t["exec_clash"]
    for r in state.relationships:
        if r.a in holders and r.b in holders and r.value <= float(clash.at_most or 0):
            s = clamp01((float(clash.at_most or 0) - r.value) / float(clash.span or 1))
            hits.append(TriggerHit("exec_clash", s, (r.a, r.b)))
    return hits


# --- Crises (M10b, 23.3) -------------------------------------------------------------------

SECURITY = "security"  # skills.yaml key
EXIT_REASONS = ("resigned", "poached")


def key_people(state: GameState, data: GameData, balance: Balance) -> set[int]:
    """Seat holders, division presidents and the top share of staff by current ability."""
    cid = state.player.id
    staff = [e for e in state.staff(cid) if not state.person(e.person_id).is_founder]
    ranked = sorted(
        staff, key=lambda e: (-current_ability(state.person(e.person_id), data), e.person_id)
    )
    share = balance.events.crisis.key_exit_top_fraction
    top = {e.person_id for e in ranked[: math.ceil(len(ranked) * share)]} if ranked else set()
    seats = {s.person_id for s in state.exec_seats if s.company_id == cid and s.person_id}
    presidents = {
        u.leader_id
        for u in state.active_units(cid)
        if u.kind == "division" and u.leader_id is not None
    }
    return top | seats | presidents


def security_coverage(state: GameState, product_id: int, balance: Balance, data: GameData) -> float:
    """The product team's mean security skill / security_full_at, at most 1 (23.3)."""
    from tst.sim.products.phases import team_of

    product = state.product(product_id)
    if product is None:
        return 0.0
    team = team_of(state, org_view(state, product.company_id), product, balance, data)
    ids = [*(b.person_id for b in team.builders), *(s.person_id for s in team.sellers)]
    ids += [m.person_id for m in team.marketers]
    if not ids:
        return 0.0
    mean = sum(state.person(p).skills[SECURITY] for p in ids) / len(ids)
    return min(1.0, mean / balance.events.crisis.security_full_at)


def crisis_hits(
    state: GameState, gen: np.random.Generator, balance: Balance, data: GameData
) -> list[TriggerHit]:
    """23.3, in fixed order: key exits this month (by person id), then for each live
    product by id a breach draw (1,000+ customers) and an outage draw (5,000+ customers and
    quality under 45). `gen` is the director's events stream, right after the count."""
    cfg = balance.events.crisis
    cid = state.player.id
    hits: list[TriggerHit] = []
    key = key_people(state, data, balance)
    view = org_view(state, cid)
    for e in sorted(state.staff(cid), key=lambda e: e.person_id):
        if (
            e.status == "notice"
            and e.end_turn == state.turn + 1
            and e.end_reason in EXIT_REASONS
            and e.person_id in key
        ):
            hits.append(
                TriggerHit(
                    "key_exit", 1.0, (e.person_id,), view.unit_of.get(e.person_id), critical_ok=True
                )
            )
    for p in sorted(state.company_products(cid), key=lambda p: p.id):
        if p.status != "live":
            continue
        segs = state.segments_of(p.id)
        customers = sum(s.customers for s in segs)
        top = max(segs, key=lambda s: s.customers).segment if segs else None
        if customers >= cfg.breach_min_customers:
            chance = cfg.breach_chance * (1 - security_coverage(state, p.id, balance, data))
            draw = float(gen.random())
            if draw < chance:
                hits.append(
                    TriggerHit(
                        "security_breach", 1.0, product_id=p.id, segment=top, critical_ok=True
                    )
                )
        if customers >= cfg.outage_min_customers and p.quality < cfg.outage_max_quality:
            draw = float(gen.random())
            if draw < cfg.outage_chance:
                hits.append(
                    TriggerHit("outage", 1.0, product_id=p.id, segment=top, critical_ok=True)
                )
    return hits
