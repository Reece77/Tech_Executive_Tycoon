"""Ask my COO: who answers and the briefing (docs/formulas.md 17.3; M7b).

Pure and read-only: it never changes state or costs energy. The briefing uses only what the
player can see: runway, open events, products' status, shown morale, span counts (as the
Overview's Org tile), open searches, board confidence and rival news.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tst.sim.data_models import LEVELS, Balance, GameData
from tst.sim.finance.board import average_confidence
from tst.sim.finance.statements import projected_runway
from tst.sim.money import Cents
from tst.sim.org.formulas import span_limit
from tst.sim.org.rules import LEADERSHIP, org_view
from tst.sim.people.models import Employment
from tst.sim.state import GameState

COO_ROLE = "operations_manager"
PRICE_CUT = "price_cut"
URGENT: tuple[Literal["critical", "major"], ...] = ("critical", "major")

type LinkKind = Literal[
    "finance", "event", "product", "person", "org", "recruitment", "board", "rival"
]


@dataclass(frozen=True, slots=True)
class Issue:
    key: str  # runway | event | rotting | morale | span | role_open | board | price_cut
    text: str
    link_kind: LinkKind
    link_id: int | None = None


def coo_of(state: GameState) -> int | None:
    """Who answers (17.3): the highest-level active operations manager; else the
    highest-level non-founder employee; ties go to the longest tenure. None: the founder's
    notebook."""
    staff = [
        e
        for e in state.staff(state.player.id)
        if e.status == "active" and not state.person(e.person_id).is_founder
    ]

    def rank(e: Employment) -> tuple[int, int, int]:
        level = LEVELS.index(e.level) if e.level in LEVELS else 0
        return (-level, e.start_turn, e.person_id)

    ops = [e for e in staff if e.role == COO_ROLE]
    pool = ops or staff
    return min(pool, key=rank).person_id if pool else None


def briefing(state: GameState, cash: Cents, balance: Balance, data: GameData) -> tuple[Issue, ...]:
    """Up to `coo.max_issues` issues, most urgent first; () means nothing urgent."""
    keys = balance.coo
    company = state.player.id
    issues: list[Issue] = []
    runway = projected_runway(state, company, cash, balance, data)
    if runway is not None and runway < keys.runway_months:
        issues.append(
            Issue("runway", f"Runway is down to {runway} months at this month's costs.", "finance")
        )
    for severity in URGENT:
        for event in state.open_events(company):
            if event.status == "open" and event.severity == severity:
                issues.append(
                    Issue(
                        "event",
                        f"A {severity} event needs your answer: {event.title or 'untitled'}.",
                        "event",
                        event.id,
                    )
                )
    for product in state.company_products(company):
        if product.rotting:
            issues.append(
                Issue(
                    "rotting",
                    f"Nobody is working on {product.name}, so its quality is falling.",
                    "product",
                    product.id,
                )
            )
    for e in state.staff(company):
        person = state.person(e.person_id)
        morale = state.person_state(e.person_id).morale
        if not person.is_founder and morale is not None and morale < keys.morale_below:
            issues.append(
                Issue(
                    "morale",
                    f"{person.first_name} {person.last_name}'s morale is {round(morale)}.",
                    "person",
                    person.id,
                )
            )
    view = org_view(state, company)
    over = [
        m
        for m, reports in sorted(view.reports.items())
        if len(reports) > span_limit(state.person(m).skills[LEADERSHIP], balance.org)
    ]
    for m in over:
        manager = state.person(m)
        issues.append(
            Issue(
                "span",
                f"{manager.first_name} {manager.last_name} manages more people than they "
                "handle well.",
                "org",
            )
        )
    for search in state.open_searches(company):
        months = state.turn - search.opened_turn
        if months > keys.role_open_months:
            role = data.role(search.role).label
            issues.append(
                Issue(
                    "role_open",
                    f"The {role} search has been open {months} months.",
                    "recruitment",
                    search.id,
                )
            )
    board = average_confidence(state, company)
    if board is not None and board < keys.board_below:
        issues.append(Issue("board", f"The board's confidence is down to {round(board)}.", "board"))
    mine = {
        (product.category, seg.segment)
        for product in state.company_products(company)
        for seg in state.segments_of(product.id)
    }
    for move in state.rival_moves:
        if move.turn != state.turn - 1 or move.action != PRICE_CUT or move.product_id is None:
            continue
        rival_product = state.product(move.product_id)
        if rival_product is None or (rival_product.category, move.segment) not in mine:
            continue
        rival = state.company(move.company_id)
        issues.append(
            Issue(
                "price_cut",
                f"{rival.name} cut prices in one of your markets last month.",
                "rival",
                rival.id,
            )
        )
    return tuple(issues[: keys.max_issues])
