"""Quarterly reports from seat holders (docs/formulas.md 24.3, M10c).

At the end of each quarter (every `exec_authority.report_months` months), each filled seat's
holder reports: their function's KPIs, what they did with their authority this quarter, and one
or two concerns. Only what the company can see goes in (24.4): headcounts, customers, revenue,
spend, cash, coverage, and the flags the product screens already show. The template text is the
report; the LLM may rewrite it later from the same lines (write_pending), never adding facts.
"""

from __future__ import annotations

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.finance.statements import projected_runway
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import Cents, format_money
from tst.sim.org.divisions import support_pools
from tst.sim.org.executives import seats_in_play
from tst.sim.org.models import SEATS
from tst.sim.org.rules import org_view
from tst.sim.state import GameState

EXEC_REPORT = "exec_report"
MONTHS_PER_QUARTER = 3  # tunable-exempt: calendar
DONE_LISTED = 3  # tunable-exempt: decisions named in a report, newest first
CONCERNS = 2  # tunable-exempt: "one or two concerns" (24.3)
BUILDER = "builder"
SELLER = "seller"


def _n(count: int, word: str) -> str:
    return f"{count:,} {word}{'' if count == 1 else 's'}"


def is_report_month(turn: int, balance: Balance) -> bool:
    """The last month of each reporting period (March, June, ... with report_months 3)."""
    return (turn + 1) % balance.exec_authority.report_months == 0


def quarter_label(turn: int) -> str:
    year, month = turn_to_ym(turn)
    return f"Q{(month - 1) // MONTHS_PER_QUARTER + 1} {year}"


def _function_count(state: GameState, company: int, function: str, data: GameData) -> int:
    return sum(
        1
        for e in state.staff(company)
        if e.status == "active"
        and not state.person(e.person_id).is_founder
        and data.role(e.role).product_function == function
    )


def _kpis_and_concerns(
    state: GameState, seat: str, cash: Cents, balance: Balance, data: GameData
) -> tuple[list[str], list[str]]:
    company = state.player.id
    products = [p for p in state.company_products(company) if p.status != "retired"]
    live = [p for p in products if p.status == "live"]
    segments = [(p, s) for p in live for s in state.segments_of(p.id)]
    customers = round(sum(s.customers for _, s in segments))
    history = state.player.mrr_history
    mrr = history[-1] if history else 0
    then = history[-(MONTHS_PER_QUARTER + 1)] if len(history) > MONTHS_PER_QUARTER else 0
    kpis: list[str] = []
    concerns: list[str] = []
    match seat:
        case "cto" | "cpo":
            builders = _function_count(state, company, BUILDER, data)
            kpis.append(
                f"{_n(builders, 'builder')} on {_n(len(products), 'product')} ({len(live)} live, "
                f"{len(products) - len(live)} in development)"
            )
            concerns += [f"{p.name} has nobody working on it" for p in products if p.rotting]
        case "cro":
            sellers = _function_count(state, company, SELLER, data)
            kpis.append(f"{_n(sellers, 'seller')}; {_n(customers, 'customer')}")
            kpis.append(f"monthly revenue {format_money(mrr)}, from {format_money(then)}")
            concerns += [
                f"sellers are the limit for {p.name} in {data.segment(s.segment).label}"
                for p, s in segments
                if s.capacity_limited
            ]
        case "cmo":
            spend = sum(p.marketing_budget_cents for p in live)
            kpis.append(f"marketing {format_money(spend)} a month; {_n(customers, 'customer')}")
            if live and spend == 0:
                concerns.append("we spend nothing on marketing")
        case "coo":
            pools = support_pools(state, org_view(state, company), balance, data)
            central = pools.get(None)
            heads = sum(1 for e in state.staff(company) if e.status == "active")
            kpis.append(f"{heads:,} staff")
            if central is not None:
                kpis.append(f"support {central.support} of {central.need} needed")
            concerns += [
                "support is short" + ("" if key is None else " in a division")
                for key, pool in pools.items()
                if pool.need > 0 and pool.support < pool.need
            ]
        case "cfo":
            runway = projected_runway(state, company, cash, balance, data)
            debt = sum(loan.balance_cents for loan in state.company_loans(company) if loan.active)
            kpis.append(f"cash {format_money(cash)}; debt {format_money(debt)}")
            kpis.append("profitable" if runway is None else f"runway {runway} months")
            limit = balance.exec_authority.defaults["cfo"]["runway_months"]
            a = state.authority(company, "cfo")
            if a is not None:
                limit = a.number("runway_months")
            if runway is not None and runway < float(limit):
                concerns.append(f"runway is under {limit} months")
    return kpis, concerns


def report_text(
    state: GameState, seat: str, holder: int, cash: Cents, balance: Balance, data: GameData
) -> str:
    """One holder's quarterly report (24.3): KPIs, what they did, one or two concerns."""
    company = state.player.id
    kpis, concerns = _kpis_and_concerns(state, seat, cash, balance, data)
    since = state.turn - balance.exec_authority.report_months
    done = [
        d
        for d in state.exec_decisions
        if d.company_id == company and d.person_id == holder and d.seat == seat and d.turn > since
    ]
    a = state.authority(company, seat)
    if a is None or not a.enabled:
        did = "I had no authority this quarter, so I advised and you decided."
    elif not done:
        did = "With my authority I saw nothing that needed a change."
    else:
        newest = sorted(done, key=lambda d: (-d.turn, -d.id))[:DONE_LISTED]
        slips = sum(1 for d in done if d.mistake)
        did = (
            f"I made {_n(len(done), 'decision')}: "
            + "; ".join(d.text for d in newest)
            + "."
            + (f" In hindsight {slips} of them could have been better." if slips else "")
        )
    worry = (
        "Concerns: " + "; ".join(concerns[:CONCERNS]) + "." if concerns else "No pressing concerns."
    )
    head = f"{quarter_label(state.turn)}: " + "; ".join(kpis) + "." if kpis else ""
    return " ".join(x for x in (head, did, worry) if x)


def quarterly_reports(
    state: GameState, cash: Cents, balance: Balance, data: GameData
) -> tuple[LogItem, ...]:
    """Every filled seat's report in the last month of a quarter; () otherwise."""
    company = state.player.id
    if not is_report_month(state.turn, balance) or not seats_in_play(state, company, balance):
        return ()
    out = []
    for seat in SEATS:
        holder = state.seat_holder(company, seat)
        employment = state.employment_of(holder) if holder is not None else None
        if holder is None or employment is None or employment.company_id != company:
            continue
        person = state.person(holder)
        out.append(
            inbox_item(
                state.turn,
                company,
                EXEC_REPORT,
                link_kind="person",
                link_id=holder,
                seat=seat.upper(),
                name=f"{person.first_name} {person.last_name}",
                report=report_text(state, seat, holder, cash, balance, data),
            )
        )
    return tuple(out)
