"""Driver breakdowns for tooltips (M7b sub-task 4; spec 13: "every number has a tooltip
explaining its drivers"). Built here from stored rows and the state; the front end only
displays them. Every item is a number the player can already see somewhere (ADR-0007)."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from tst.api.schemas.common import BreakdownItemOut, BreakdownOut
from tst.db.models import AccountRow, LedgerEntryRow, LedgerLineRow, ProductMonthRow
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.errors import UnknownPersonError
from tst.sim.finance.statements import projected_net_burn
from tst.sim.hiring.phases import monthly_costs
from tst.sim.ledger import CASH
from tst.sim.money import Cents, format_money
from tst.sim.products.models import Product
from tst.sim.research.levels import IDENTITY, TechFactor
from tst.sim.state import GameState

EVENT_MEMO = "Event:"  # memo prefix of event cash effects (tst.sim.events.effects)
REVENUE = ("4000_revenue_subscriptions", "4100_revenue_licenses", "4200_revenue_services")
PAYROLL = ("6000_salaries", "6010_benefits", "2100_accrued_payroll")
MARKETING = ("6400_marketing",)
FINANCING = ("2500_debt", "2600_safes", "3000_common_equity", "3100_preferred_equity")
CASH_ORDER = ("Revenue", "Payroll", "Marketing", "Other costs", "Financing", "Event effects")


PERCENT = 100  # tunable-exempt: a fraction in percent


def _money(label: str, cents: float) -> BreakdownItemOut:
    return BreakdownItemOut(label=label, amount=round(cents), unit="cents")


def _category(account: str, memo: str) -> str:
    if memo.startswith(EVENT_MEMO):
        return "Event effects"
    if account in REVENUE:
        return "Revenue"
    if account in PAYROLL:
        return "Payroll"
    if account in MARKETING:
        return "Marketing"
    if account in FINANCING:
        return "Financing"
    return "Other costs"


def cash_effects(session: Session, company_id: int, turn: int) -> list[tuple[str, str, str, int]]:
    """Each non-cash line of a cash-moving entry in one turn, as its effect on cash:
    (account code, account name, memo, cents in). The effects sum to the change in cash."""
    rows = session.execute(
        select(
            LedgerEntryRow.id,
            LedgerEntryRow.memo,
            LedgerLineRow.account_code,
            AccountRow.name,
            LedgerLineRow.amount_cents,
        )
        .join(LedgerLineRow.entry)
        .join(AccountRow, AccountRow.code == LedgerLineRow.account_code)
        .where(LedgerEntryRow.company_id == company_id, LedgerEntryRow.turn == turn)
        .order_by(LedgerEntryRow.id, LedgerLineRow.id)
    ).all()
    by_entry: dict[int, list[tuple[str, str, str, int]]] = defaultdict(list)
    for entry, memo, code, name, amount in rows:
        by_entry[entry].append((str(code), str(name), str(memo or ""), int(amount)))
    out = []
    for lines in by_entry.values():
        if not any(code == CASH for code, _, _, _ in lines):
            continue  # no cash moved (e.g. a SAFE converting to shares)
        out += [(code, name, memo, -amount) for code, name, memo, amount in lines if code != CASH]
    return out


def cash_change(session: Session, state: GameState) -> BreakdownOut:
    """Last month's change in cash by revenue, payroll, marketing, other costs, financing and
    event effects."""
    played = state.turn - 1
    if played < 0:
        return BreakdownOut(items=[], note="No month has closed yet.")
    totals: dict[str, int] = defaultdict(int)
    for code, _, memo, cents in cash_effects(session, state.player.id, played):
        totals[_category(code, memo)] += cents
    total = sum(totals.values())
    return BreakdownOut(
        items=[_money(k, totals[k]) for k in CASH_ORDER if totals.get(k)],
        note=f"Cash {'rose' if total >= 0 else 'fell'} {format_money(abs(total))} in "
        f"{format_turn(played)}.",
    )


def burn(session: Session, state: GameState) -> BreakdownOut:
    """Last month's burn by cost line, less revenue and event gains: net cash used before
    financing (14.1; M8r). Investor and loan money is left out."""
    played = state.turn - 1
    if played < 0:
        return BreakdownOut(items=[], note="No month has closed yet.")
    lines: dict[str, int] = defaultdict(int)
    for code, name, memo, cents in cash_effects(session, state.player.id, played):
        category = _category(code, memo)
        if category == "Financing":
            continue  # burn is before financing (M8r)
        label = name if category in ("Payroll", "Marketing", "Other costs") else category
        lines[label] -= cents  # burn counts money out as positive
    total = sum(lines.values())
    items = sorted(lines.items(), key=lambda kv: (-kv[1], kv[0]))
    note = (
        "Burn is the net cash the business used over the month, before financing: revenue "
        "and event gains count against it; investor and loan money does not."
        if total > 0
        else "The business did not use cash last month (before financing), so there was no burn."
    )
    return BreakdownOut(items=[_money(k, v) for k, v in items if v], note=note)


def runway(state: GameState, cash: Cents, data: LoadedData) -> BreakdownOut:
    """Runway = cash / this month's projected net burn (formulas.md 14.1)."""
    net = projected_net_burn(state, state.player.id, data.balance, data.game_data)
    costs = sum(
        a for _, _, a in monthly_costs(state, state.player.id, data.balance, data.game_data)
    )
    items = [
        _money("Cash", cash),
        _money("Projected costs this month", costs),
        _money("Projected revenue this month", costs - net),
        _money("Projected net burn", net),
    ]
    if net <= 0:
        return BreakdownOut(
            items=items, note="Not burning: this month's revenue covers its projected costs."
        )
    return BreakdownOut(items=items, note="Runway is cash divided by the projected net burn.")


def revenue_by_product(session: Session, state: GameState, annual: bool) -> BreakdownOut:
    """MRR (or ARR = 12 x MRR) at the last month end, by product."""
    played = state.turn - 1
    own = {p.id: p.name for p in state.company_products(state.player.id)}
    totals: dict[int, int] = defaultdict(int)
    if own and played >= 0:
        for pid, cents in session.execute(
            select(ProductMonthRow.product_id, ProductMonthRow.revenue_cents).where(
                ProductMonthRow.turn == played, ProductMonthRow.product_id.in_(list(own))
            )
        ):
            totals[int(pid)] += int(cents)
    factor = 12 if annual else 1
    items = [_money(own[pid], factor * c) for pid, c in sorted(totals.items()) if c]
    note = (
        "ARR is 12 times last month's recurring revenue."
        if annual
        else "Revenue from every segment in the last closed month."
    )
    return BreakdownOut(items=items, note=note if items else "No product earned revenue yet.")


def headcount_by_unit(state: GameState) -> BreakdownOut:
    staff = state.staff(state.player.id)
    names = {u.id: u.name for u in state.units if u.company_id == state.player.id}
    counts: dict[str, int] = defaultdict(int)
    for e in staff:
        counts[
            names.get(e.unit_id, "Company root") if e.unit_id is not None else "Company root"
        ] += 1
    notice = sum(1 for e in staff if e.status == "notice")
    return BreakdownOut(
        items=[
            BreakdownItemOut(label=k, amount=v, unit="count")
            for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        note=f"Everyone on the staff, the founder included; {notice} on notice."
        if notice
        else "Everyone on the staff, the founder included.",
    )


def average_morale(state: GameState, data: LoadedData, cash: Cents) -> BreakdownOut:
    """The company-wide average of each morale term (formulas.md 9, 13.11): what pulls the
    average target up or down. Morale closes part of the gap to its target each month."""
    from tst.api.org_views import morale_breakdown  # org_views -> views -> this module

    company = state.player.id
    projected = sum(a for _, _, a in monthly_costs(state, company, data.balance, data.game_data))
    sums: dict[str, float] = defaultdict(float)
    labels: dict[str, str] = {}
    order: list[str] = []
    people = 0
    for e in state.staff(company):
        if state.person(e.person_id).is_founder:
            continue
        try:
            terms = morale_breakdown(state, company, e.person_id, data, cash, projected).terms
        except UnknownPersonError:
            continue
        people += 1
        for t in terms:
            if t.key not in labels:
                labels[t.key] = t.label
                order.append(t.key)
            sums[t.key] += t.value
    if not people:
        return BreakdownOut(items=[], note="No employees yet: the founder has no morale.")
    return BreakdownOut(
        items=[
            BreakdownItemOut(label=labels[k], amount=round(sums[k] / people, 1), unit="points")
            for k in order
        ],
        note=f"Average of {people} employees' morale terms; together they give the average "
        "target that morale moves toward each month.",
    )


def product_quality(
    product: Product,
    history_quality: list[float],
    pace: str,
    rotting: bool,
    tech: TechFactor = IDENTITY,
) -> BreakdownOut:
    """Quality as §11 shows it in words: where it stands, last month's change, the pace; and
    the tech factor (M11, 21.2): the company's research lead in the category, the lift it
    gives the quality cap and features, and a first mover's head start."""
    items = [BreakdownItemOut(label="Quality now", amount=round(product.quality, 1), unit="points")]
    if len(history_quality) >= 2:
        items.append(
            BreakdownItemOut(
                label="Change last month",
                amount=round(history_quality[-1] - history_quality[-2], 1),
                unit="points",
            )
        )
    if not tech.is_identity:
        items += [
            BreakdownItemOut(
                label="Research lead in this market", amount=round(tech.lead, 1), unit="points"
            ),
            BreakdownItemOut(
                label="Tech factor on what the team can reach",
                amount=round((tech.cap_mult - 1) * PERCENT, 1),
                unit="percent",
            ),
            BreakdownItemOut(
                label="Tech factor on features",
                amount=round((tech.feature_mult - 1) * PERCENT, 1),
                unit="percent",
            ),
        ]
        if tech.cap_points:
            items.append(
                BreakdownItemOut(
                    label="First-mover head start", amount=tech.cap_points, unit="points"
                )
            )
    note = (
        "Nobody works on it, so quality is falling."
        if rotting
        else f"Development pace: {pace}. More and better builders raise quality toward what "
        "the team can reach."
    )
    if not tech.is_identity:
        note += " Research raises what the team can reach (see Research)."
    return BreakdownOut(items=items, note=note)


def market_share(
    appeal: float | None,
    price_score: float | None,
    product: Product,
    feature_score: float,
    weights: dict[str, float],
    share: float,
) -> BreakdownOut:
    """Share of a segment's served customers and the appeal inputs behind it (11.6, 11.7)."""
    items = [
        BreakdownItemOut(
            label="Share of served customers", amount=round(share * 100, 1), unit="percent"
        )
    ]
    if appeal is not None:
        items.append(BreakdownItemOut(label="Appeal", amount=round(appeal, 1), unit="points"))
    items += [
        BreakdownItemOut(label="Quality", amount=round(product.quality, 1), unit="points"),
        BreakdownItemOut(label="Brand", amount=round(product.brand, 1), unit="points"),
        BreakdownItemOut(label="Feature score", amount=round(feature_score, 1), unit="points"),
    ]
    if price_score is not None:
        items.append(
            BreakdownItemOut(label="Price score", amount=round(price_score, 1), unit="points")
        )
    weight_text = ", ".join(f"{k} {round(v * 100)}%" for k, v in weights.items())
    return BreakdownOut(
        items=items,
        note=f"Customers choose by appeal against rivals and buying nothing; this segment "
        f"weighs {weight_text}.",
    )


def salary(salary_cents: int, market_cents: int | None) -> BreakdownOut | None:
    """Salary against the role's market rate, when the player can see the rate."""
    if not market_cents:
        return None
    gap = salary_cents - market_cents
    pct = gap / market_cents
    return BreakdownOut(
        items=[
            _money("Salary", salary_cents),
            _money("Market rate", market_cents),
            _money("Difference", gap),
        ],
        note=f"{abs(pct):.0%} {'above' if gap >= 0 else 'below'} the market rate for the role "
        "and level; pay below it weighs on morale.",
    )
