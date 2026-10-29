"""Rival responses built from the live state as the player sees it (M5, formulas.md 15.5).

Public scores, prices and customers are shown as they are (11.13); a rival's money is only a
label, its staff an estimate, its key people the player's ranges, an approach only a band.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from tst.api.schemas.people import AttributeOut, RangeOut
from tst.api.schemas.rivals import (
    ApproachOut,
    KeyPersonOut,
    NewsMonthOut,
    RivalMoveOut,
    RivalProfileOut,
    RivalRowOut,
    RivalSegmentOut,
    RivalsOut,
)
from tst.api.views import person_name, role_label
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.hiring.formulas import energy_cost
from tst.sim.ledger import AccountCode
from tst.sim.money import Cents
from tst.sim.people.formulas import potential_phrase
from tst.sim.people.models import PA_KEY
from tst.sim.people.reveal import revealed_range
from tst.sim.products import formulas as pf
from tst.sim.products.models import SELLING
from tst.sim.rivals import formulas as rf
from tst.sim.rivals.decisions import cash_months
from tst.sim.rivals.models import PoachApproach, RivalMove
from tst.sim.rivals.poaching import approach_probability
from tst.sim.state import CompanyState, GameState, with_employment

PERSONALITY_LABELS = {
    "aggressive": "Aggressive",
    "fast_follower": "Fast follower",
    "premium": "Premium",
    "cost_leader": "Cost leader",
}
STYLE_TEXT = {
    "aggressive": "Cuts prices and enters new segments quickly; poaches hard when you gain.",
    "fast_follower": "Copies features that work and keeps pace on price.",
    "premium": "Competes on quality and brand; raises prices when it leads.",
    "cost_leader": "Answers share losses with lower prices and keeps costs down.",
}
MOVE_TAGS = {
    "price_cut": "Price",
    "price_rise": "Price",
    "feature_push": "Push",
    "quality_push": "Push",
    "brand_push": "Push",
    "enter_segment": "Enter",
    "cut_costs": "Cut",
    "poach": "Approach",
    "launched": "Launch",
    "funded": "Funding",
    "founded": "Founded",
    "failed": "Failed",
}
RUNNING_WORDS = {
    "feature_push": "Feature push",
    "quality_push": "Quality push",
    "brand_push": "Brand push",
    "cut_costs": "Cost cut",
    "builder_left": "Lost a key builder",
}
TOP_SKILLS = 3  # tunable-exempt: skills shown per key person


type Balances = Mapping[tuple[int, AccountCode], Cents]


def player_segments(state: GameState) -> set[tuple[str, str]]:
    out = set()
    for p in state.company_products(state.player.id):
        if p.status in SELLING:
            out |= {(p.category, s.segment) for s in state.segments_of(p.id)}
    return out


def rival_segments(state: GameState, company_id: int) -> set[tuple[str, str]]:
    out = set()
    for p in state.company_products(company_id):
        if p.status in SELLING:
            out |= {(p.category, s.segment) for s in state.segments_of(p.id)}
    return out


def staff_estimate(state: GameState, company_id: int, data: LoadedData) -> int:
    heads = len(state.staff(company_id)) + sum(p.headcount for p in state.company_pools(company_id))
    return rf.rounded_headcount(heads, data.balance.rivals)


def stance(state: GameState, company_id: int, data: LoadedData) -> tuple[str, str]:
    """responding (acted in a player segment within 6 months), watching (shares a segment),
    or not competing (15.5)."""
    mine = player_segments(state)
    since = state.turn - data.balance.rivals.stance_turns
    products = {p.id: p for p in state.products}
    for m in reversed(state.rival_moves):
        if m.company_id != company_id or m.turn <= since:
            continue
        product = products.get(m.product_id or -1)
        if m.action == "poach" or (
            product is not None and m.segment and (product.category, m.segment) in mine
        ):
            return "responding", f"{m.detail} ({format_turn(m.turn)})"
    shared = mine & rival_segments(state, company_id)
    if shared:
        labels = ", ".join(sorted(data.game_data.segment(s).label for _, s in shared))
        return "watching", f"Sells where you sell: {labels}"
    return "not competing", "No segment in common with you"


def money(
    state: GameState, company: CompanyState, balances: Balances, data: LoadedData
) -> str | None:
    if company.is_startup:
        return None  # 15.5: nothing is shown for a startup's money
    months = cash_months(state, company.id, balances, data.balance, data.game_data)
    return rf.money_label(months, data.balance.rivals)


def move_out(m: RivalMove) -> RivalMoveOut:
    return RivalMoveOut(
        turn=m.turn,
        date_label=format_turn(m.turn),
        tag=MOVE_TAGS.get(m.action, "News"),
        detail=m.detail,
        approach=m.action == "poach",
    )


def rivals_out(
    state: GameState, balances: Balances, data: LoadedData, moves: list[RivalMove], view: str
) -> RivalsOut:
    mine = player_segments(state)
    rows = []
    rivals = [c for c in state.companies if not c.is_player]
    for company in rivals:
        shared = sorted(
            data.game_data.segment(s).label for _, s in mine & rival_segments(state, company.id)
        )
        if view == "markets" and not shared:
            continue
        if view == "startups" and not company.is_startup:
            continue
        last = next((m for m in reversed(moves) if m.company_id == company.id), None)
        rows.append(
            RivalRowOut(
                company_id=company.id,
                name=company.name,
                is_startup=company.is_startup,
                personality=company.personality or "",
                personality_label=PERSONALITY_LABELS.get(company.personality or "", ""),
                competes_in=shared,
                staff_estimate=staff_estimate(state, company.id, data),
                money_label=None if company.failed_turn else money(state, company, balances, data),
                stance=stance(state, company.id, data)[0]
                if company.failed_turn is None
                else "not competing",
                last_move=last.detail if last else None,
                last_move_date_label=format_turn(last.turn) if last else None,
                failed=company.failed_turn is not None,
            )
        )
    return RivalsOut(
        established=sum(1 for c in rivals if not c.is_startup),
        startups_alive=sum(1 for c in rivals if c.is_startup and c.failed_turn is None),
        startups_failed=sum(1 for c in rivals if c.is_startup and c.failed_turn is not None),
        rivals=rows,
    )


def _skills(state: GameState, person_id: int, data: LoadedData) -> list[AttributeOut]:
    reveal = state.reveal(state.player.id, person_id)
    person = state.person(person_id)
    if reveal is None:
        return []
    out = []
    for skill in data.game_data.skills:
        lo, hi = revealed_range(person, reveal, skill.key)
        out.append(
            AttributeOut(
                key=skill.key,
                label=skill.label,
                short_label=skill.short_label,
                group=skill.group,
                range=RangeOut(min=lo, max=hi),
            )
        )
    out.sort(key=lambda a: (-(a.range.min + a.range.max), a.range.max - a.range.min, a.label))
    return out[:TOP_SKILLS]


def rival_profile(
    state: GameState,
    company: CompanyState,
    balances: Balances,
    data: LoadedData,
    moves: list[RivalMove],
) -> RivalProfileOut:
    mine = player_segments(state)
    gd = data.game_data
    turn = max(state.turn - 1, 0)
    running = {
        (e.product_id, e.kind): e
        for e in state.rival_effects
        if e.company_id == company.id and e.end_turn >= state.turn
    }
    segments = []
    shared_revenue = 0
    for p in state.company_products(company.id):
        if p.status == "retired":
            continue
        feature = (
            p.held_feature
            if p.held_feature is not None
            else pf.feature_score(p.feature_points, gd.category(p.category), turn)
        )
        effect = next((e for (pid, _), e in running.items() if pid in (p.id, None)), None)
        for seg in state.segments_of(p.id):
            shared = (p.category, seg.segment) in mine
            if shared:
                shared_revenue += round(seg.customers * (seg.price_cents or 0))
            segments.append(
                RivalSegmentOut(
                    product_id=p.id,
                    product_name=p.name,
                    category_label=gd.category(p.category).label,
                    segment=seg.segment,
                    segment_label=gd.segment(seg.segment).label,
                    quality=p.quality,
                    feature_score=feature,
                    brand=p.brand,
                    price_cents=seg.price_cents,
                    customers=seg.customers,
                    shared_with_player=shared,
                    running=RUNNING_WORDS.get(effect.kind) if effect else None,
                    running_until_label=format_turn(effect.end_turn) if effect else None,
                )
            )
    total_staff = staff_estimate(state, company.id, data)
    all_segments = rival_segments(state, company.id)
    share_mine = len(mine & all_segments) / len(all_segments) if all_segments else 0.0
    bounds = data.balance.reveal.pa_phrase_bounds
    people = []
    for e in sorted(state.staff(company.id), key=lambda e: e.person_id):
        person = state.person(e.person_id)
        reveal = state.reveal(state.player.id, person.id)
        phrase = ""
        if reveal is not None:
            phrase = potential_phrase(*revealed_range(person, reveal, PA_KEY), bounds)
        people.append(
            KeyPersonOut(
                person_id=person.id,
                name=person_name(person),
                role=e.role,
                role_label=role_label(e.role, data) or e.role,
                level=e.level,
                top_skills=_skills(state, person.id, data),
                potential_phrase=phrase,
            )
        )
    stance_now, reason = stance(state, company.id, data)
    return RivalProfileOut(
        company_id=company.id,
        name=company.name,
        is_startup=company.is_startup,
        personality=company.personality or "",
        personality_label=PERSONALITY_LABELS.get(company.personality or "", ""),
        style_text=STYLE_TEXT.get(company.personality or "", ""),
        founded_label=format_turn(company.founded_turn),
        staff_estimate=total_staff,
        staff_in_your_markets=rf.rounded_headcount(total_staff * share_mine, data.balance.rivals),
        revenue_in_your_markets_cents=shared_revenue,
        money_label=None if company.failed_turn else money(state, company, balances, data),
        stance=stance_now if company.failed_turn is None else "not competing",
        stance_reason=reason if company.failed_turn is None else "Closed",
        failed=company.failed_turn is not None,
        segments=segments,
        key_people=people,
        recent_moves=[move_out(m) for m in reversed(moves) if m.company_id == company.id],
        poach_energy=energy_cost("poach_search", data.balance),
    )


def news_months(moves: list[RivalMove]) -> list[NewsMonthOut]:
    by_turn: dict[int, list[RivalMove]] = {}
    for m in moves:
        by_turn.setdefault(m.turn, []).append(m)
    return [
        NewsMonthOut(turn=t, date_label=format_turn(t), moves=[move_out(m) for m in by_turn[t]])
        for t in sorted(by_turn, reverse=True)
    ]


def band(
    state: GameState, approach: PoachApproach, data: LoadedData, salary: int | None = None
) -> str:
    """The band from what the player knows: true salary, offer and options, the displayed
    loyalty midpoint, morale exactly (15.6). Never the probability."""
    employment = state.employment_of(approach.person_id)
    person = state.person(approach.person_id)
    reveal = state.reveal(state.player.id, person.id)
    loyalty = None
    if reveal is not None:
        lo, hi = revealed_range(person, reveal, "loyalty")
        loyalty = (lo + hi) / 2
    view = state
    if salary is not None and employment is not None:
        view = with_employment(state, replace(employment, salary_cents=salary))
    p = approach_probability(view, approach, data.balance, known_loyalty=loyalty)
    return rf.poach_band(p, data.balance.rivals.poach)


def approach_out(state: GameState, approach: PoachApproach, data: LoadedData) -> ApproachOut:
    employment = state.employment_of(approach.person_id)
    person = state.person(approach.person_id)
    grant = state.grant_for(employment.id) if employment is not None else None
    return ApproachOut(
        approach_id=approach.id,
        person_id=person.id,
        name=person_name(person),
        role_label=role_label(employment.role if employment else person.role, data) or "",
        rival_id=approach.rival_id,
        rival_name=state.company(approach.rival_id).name,
        offer_cents=approach.offer_cents,
        salary_cents=employment.salary_cents if employment else 0,
        unvested_options=grant.unvested if grant else 0,
        band=band(state, approach, data),
        made_date_label=format_turn(approach.made_turn),
        answer_date_label=format_turn(approach.made_turn + 1),
    )
