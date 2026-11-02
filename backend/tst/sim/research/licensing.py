"""Licensing and leaks (docs/formulas.md 21.5).

Licensing in buys part of a rival's lead once; licensing out grants part of the player's
lead for a royalty on the licensee's revenue in the domain's categories. Rivals answer by a
rule, not a draw. A researcher who leaves a project for a rival takes some of the lead.
"""

from __future__ import annotations

from collections.abc import Mapping

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, LICENSE_REVENUE, RESEARCH, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.products.models import SELLING
from tst.sim.research import levels
from tst.sim.research.formulas import royalty_cents
from tst.sim.research.projects import add_lead
from tst.sim.state import GameState

DIRECT_COMPETITOR = "a direct competitor"


def selling_segments(state: GameState, company_id: int, category: str) -> set[str]:
    """Segments a company sells in a category, at home or abroad."""
    out: set[str] = set()
    for p in state.company_products(company_id):
        if p.category != category or p.status not in SELLING:
            continue
        out |= {s.segment for s in state.segments_of(p.id)}
        out |= {s.segment for s in state.regional_segments_of(p.id)}
    return out


def competes(state: GameState, data: GameData, a: int, b: int, domain: str) -> bool:
    """`a` and `b` share a segment in a category the domain feeds (21.5)."""
    return any(
        selling_segments(state, a, c) & selling_segments(state, b, c)
        for c in levels.feeds(data, domain)
    )


def license_in_limit(
    state: GameState, balance: Balance, licensee: int, licensor: int, domain: str
) -> float:
    """Most points the licensee can license in: it may come within rnd.license.margin of
    the licensor's lead, never closer (21.5); 0 when the gap is not above the margin."""
    gap = state.research_lead(licensor, domain) - state.research_lead(licensee, domain)
    return max(0.0, gap - balance.rnd.license.margin)


def refusal(
    state: GameState, data: GameData, balance: Balance, licensee: int, licensor: int, domain: str
) -> str | None:
    """Why a licensor says no, or None: it is a direct competitor in a category the domain
    feeds, or its lead is not more than the margin ahead (21.5)."""
    if license_in_limit(state, balance, licensee, licensor, domain) <= 0:
        margin = balance.rnd.license.margin
        return f"its lead is not more than {margin:g} points ahead of yours"
    if competes(state, data, licensee, licensor, domain):
        return DIRECT_COMPETITOR
    return None


def arr_cents(state: GameState, company_id: int) -> int:
    history = state.company(company_id).mrr_history
    return (history[-1] if history else 0) * 12  # tunable-exempt: months in a year


def price_entries(
    turn: int, licensee: int, licensor: int, price: int, label: str
) -> tuple[LedgerEntry, ...]:
    """The licensee pays (R&D) and the licensor books licence revenue (21.5)."""
    return (
        LedgerEntry.transfer(
            turn=turn,
            company_id=licensee,
            memo=f"Licence in: {label}",
            debit=RESEARCH,
            credit=CASH,
            amount=price,
        ),
        LedgerEntry.transfer(
            turn=turn,
            company_id=licensor,
            memo=f"Licence out: {label}",
            debit=CASH,
            credit=LICENSE_REVENUE,
            amount=price,
        ),
    )


def royalties(
    state: GameState, revenue: Mapping[int, int], balance: Balance, data: GameData
) -> tuple[LedgerEntry, ...]:
    """Phase 5, after revenue: each licensee with a running royalty pays royalty_bp of the
    month's revenue in the domain's categories to its licensor (21.5). `revenue` is the
    month's revenue by product id."""
    out: list[LedgerEntry] = []
    for lic in state.licenses:
        if not lic.royalty_bp or lic.royalty_end_turn is None:
            continue
        if not lic.turn <= state.turn <= lic.royalty_end_turn:
            continue
        if not state.company(lic.licensee_id).alive:
            continue
        cats = set(levels.feeds(data, lic.domain))
        base = sum(
            amount
            for pid, amount in revenue.items()
            if (p := state.product(pid)) is not None
            and p.company_id == lic.licensee_id
            and p.category in cats
        )
        amount = royalty_cents(base, balance)
        if amount <= 0:
            continue
        label = levels.domain_def(data, lic.domain).label
        out += [
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=lic.licensee_id,
                memo=f"Royalty: {label}",
                debit=RESEARCH,
                credit=CASH,
                amount=amount,
            ),
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=lic.licensor_id,
                memo=f"Royalty: {label}",
                debit=CASH,
                credit=LICENSE_REVENUE,
                amount=amount,
            ),
        ]
    return tuple(out)


def leaks(
    before: GameState, after: GameState, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Phase 1, after people join rivals: a researcher who was on one of the player's
    projects gives the rival min(cap, share x the player's lead) in its domain (21.5)."""
    was = {a.id: a.status for a in before.approaches}
    state = after
    logs: list[LogItem] = []
    for a in after.approaches:
        if a.status != "joined" or was.get(a.id) == "joined":
            continue
        ended = [
            e
            for e in after.employments
            if e.person_id == a.person_id and e.end_reason == "poached" and e.status == "ended"
        ]
        if not ended:
            continue
        last = max(ended, key=lambda e: e.id)
        if last.unit_id is None or data.role(last.role).product_function != "builder":
            continue
        project = state.unit_project(last.unit_id)
        if project is None or project.company_id != last.company_id:
            continue
        lead = state.research_lead(last.company_id, project.domain)
        gain = min(balance.rnd.leak.cap, balance.rnd.leak.share * lead)
        if gain <= 0:
            continue
        state = add_lead(state, a.rival_id, project.domain, gain)
        person = state.person(a.person_id)
        logs.append(
            inbox_item(
                state.turn,
                last.company_id,
                "research_leak",
                link_kind="person",
                link_id=person.id,
                rival=state.company(a.rival_id).name,
                domain=levels.domain_def(data, project.domain).label,
                name=f"{person.first_name} {person.last_name}",
                points=f"{gain:.0f}",
            )
        )
    return state, tuple(logs)
