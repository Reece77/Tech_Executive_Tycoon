"""Quarterly reports from seat holders (docs/formulas.md 24.3, M10c; rebuilt in M13b, 27.2).

At the end of each quarter (every `exec_authority.report_months` months), each filled seat's
holder reports, in four parts: what I did (the quarter's decisions, grouped by product, with
where the product stands now), what I'm pitching (or why not) and how earlier pitches turned
out, what worries me (concerns tied to a number), and the numbers (the function's KPIs against
last quarter and the target). The wording follows the executive's voice (exec_voices.yaml),
chosen from their displayed personality. Only what the company can see goes in (24.4). The CEO
writes a company letter to the Chair instead (`ceo_letter`). The template text is the report;
the LLM may rewrite it later from the same lines (write_pending), never adding facts.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.finance.statements import projected_runway
from tst.sim.log import LogItem, inbox_item
from tst.sim.modes.models import QuarterMark
from tst.sim.money import Cents, format_money
from tst.sim.org.divisions import support_pools
from tst.sim.org.executives import seats_in_play
from tst.sim.org.models import SEATS, ExecDecision
from tst.sim.org.rules import org_view
from tst.sim.org.voice_data import Voice
from tst.sim.org.voices import voice_for
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
            concerns += [
                f"{p.name} has nobody working on it (quality {p.quality:.0f})"
                for p in products
                if p.rotting
            ]
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
                concerns.append(
                    f"we spend nothing on marketing for {_n(len(live), 'live product')}"
                )
        case "coo":
            pools = support_pools(state, org_view(state, company), balance, data)
            central = pools.get(None)
            heads = sum(1 for e in state.staff(company) if e.status == "active")
            kpis.append(f"{heads:,} staff")
            if central is not None:
                kpis.append(f"support {central.support} of {central.need} needed")
            concerns += [
                f"support is short{'' if key is None else ' in a division'}: "
                f"{pool.support} of {pool.need} needed"
                for key, pool in pools.items()
                if pool.need > 0 and pool.support < pool.need
            ]
        case "cfo":
            runway = projected_runway(state, company, cash, balance, data)
            debt = sum(loan.balance_cents for loan in state.company_loans(company) if loan.active)
            kpis.append(f"cash {format_money(cash)}; debt {format_money(debt)}")
            limit = balance.exec_authority.defaults["cfo"]["runway_months"]
            a = state.authority(company, "cfo")
            if a is not None:
                limit = a.number("runway_months")
            kpis.append(
                "profitable"
                if runway is None
                else f"runway {_n(runway, 'month')} against a target of {float(limit):g}"
            )
            if runway is not None and runway < float(limit):
                concerns.append(f"runway is under {limit} months")
    return kpis, concerns


def _did(state: GameState, decisions: list[ExecDecision]) -> str:
    """The quarter's decisions grouped by the product each names, newest first, each group
    with where that product stands now (27.2)."""
    products = [p for p in state.company_products(state.player.id) if p.status != "retired"]
    groups: dict[str, list[str]] = {}
    for d in sorted(decisions, key=lambda d: (-d.turn, -d.id))[: DONE_LISTED * 2]:
        named = next((p for p in products if p.name in d.text), None)
        groups.setdefault(named.name if named else "", []).append(d.text)
    parts = []
    for name, texts in groups.items():
        part = "; ".join(texts[:DONE_LISTED])
        product = next((p for p in products if p.name == name), None)
        if product is not None:
            customers = round(_customers(state, product.id))
            mark = next((m for m in state.quarter_marks if m.product_id == product.id), None)
            if mark is not None:  # the quarter's start and now (M15b)
                now = (
                    f"quality {mark.quality:.0f} -> {product.quality:.0f}, "
                    f"{round(mark.customers):,} -> {_n(customers, 'customer')}"
                )
            else:
                now = f"quality now {product.quality:.0f}, {_n(customers, 'customer')}"
            part += f" ({product.name}'s {now})"
        parts.append(part)
    return "; ".join(parts)


def _customers(state: GameState, product_id: int) -> float:
    return sum(s.customers for s in state.segments_of(product_id)) + sum(
        s.customers for s in state.regional_segments_of(product_id)
    )


def mark_quarter(state: GameState, balance: Balance) -> GameState:
    """In a report month, after the reports: every selling product's quality and customers,
    the next reports' starting values."""
    if not is_report_month(state.turn, balance):
        return state
    marks = tuple(
        QuarterMark(p.id, state.turn, p.quality, _customers(state, p.id))
        for p in state.company_products(state.player.id)
        if p.status != "retired"
    )
    return replace(state, quarter_marks=marks)


def _pitching(state: GameState, holder: int, voice: Voice, since: int) -> str:
    """What I'm pitching this quarter, or why not, and how earlier pitches turned out (27.2)."""
    from tst.sim.org.pitches import case_text

    mine = [p for p in state.pitches if p.person_id == holder]
    now = [p for p in mine if p.turn > since]
    if now:
        p = max(now, key=lambda p: p.id)
        line = voice.pitch.format(
            pitch=f"{p.title}, {case_text(p.unit, p.low)} to {case_text(p.unit, p.high)} "
            f"in 24 months ({p.status.replace('_', ' ')})."
        )
    else:
        line = voice.no_pitch
    scored = [p for p in mine if p.outcome is not None]
    if scored:
        hits = sum(1 for p in scored if p.outcome == "hit")
        misses = sum(1 for p in scored if p.outcome == "miss")
        early = len(scored) - hits - misses
        line += (
            f" Earlier pitches: {hits} hit, {misses} missed"
            + (f", {early} too early to tell" if early else "")
            + "."
        )
    tracking = sum(1 for p in mine if p.approved and p.outcome is None and p.turn <= since)
    if tracking:
        line += f" {_n(tracking, 'approved pitch')} still being tracked."
    return line


def report_text(
    state: GameState, seat: str, holder: int, cash: Cents, balance: Balance, data: GameData
) -> str:
    """One holder's quarterly report (24.3, 27.2) in their voice: what I did, what I'm
    pitching, what worries me, the numbers."""
    company = state.player.id
    voice = voice_for(state, company, holder, data.voices) if data.voices else None
    kpis, concerns = _kpis_and_concerns(state, seat, cash, balance, data)
    since = state.turn - balance.exec_authority.report_months
    done = [
        d
        for d in state.exec_decisions
        if d.company_id == company and d.person_id == holder and d.seat == seat and d.turn > since
    ]
    a = state.authority(company, seat)
    if voice is None:  # no voices loaded: M10c's plain wording
        return _plain(state, kpis, concerns, done, a is not None and a.enabled)
    quarter = quarter_label(state.turn)
    parts = [voice.opener.format(quarter=quarter)]
    if a is None or not a.enabled:
        parts.append("I had no authority this quarter, so I advised and you decided.")
    elif not done:
        parts.append(voice.nothing_done)
    else:
        slips = sum(1 for d in done if d.mistake)
        parts.append(voice.did.format(did=_did(state, done)))
        if slips:
            parts.append(f"In hindsight {slips} of those could have been better.")
    if a is not None and a.enabled:
        parts.append(_pitching(state, holder, voice, since))
    parts.append(
        voice.worry.format(worry="; ".join(concerns[:CONCERNS])) if concerns else voice.calm
    )
    if kpis:
        parts.append(voice.numbers.format(numbers="; ".join(kpis)))
    return " ".join(parts)


def _plain(
    state: GameState, kpis: list[str], concerns: list[str], done: list[ExecDecision], on: bool
) -> str:
    if not on:
        did = "I had no authority this quarter, so I advised and you decided."
    elif not done:
        did = "With my authority I saw nothing that needed a change."
    else:
        newest = sorted(done, key=lambda d: (-d.turn, -d.id))[:DONE_LISTED]
        did = f"I made {_n(len(done), 'decision')}: " + "; ".join(d.text for d in newest) + "."
    worry = (
        "Concerns: " + "; ".join(concerns[:CONCERNS]) + "." if concerns else "No pressing concerns."
    )
    head = f"{quarter_label(state.turn)}: " + "; ".join(kpis) + "." if kpis else ""
    return " ".join(x for x in (head, did, worry) if x)


def ceo_letter(
    state: GameState, ceo_id: int, scopes: tuple[str, ...], cash: Cents, b: Balance, data: GameData
) -> str:
    """The CEO's quarterly letter to the Chair (27.2): every function's numbers, what the CEO
    did, what they are pitching, and the company's worries."""
    company = state.player.id
    voice = voice_for(state, company, ceo_id, data.voices) if data.voices else None
    since = state.turn - b.exec_authority.report_months
    lines: list[str] = []
    worries: list[str] = []
    for seat in ("cro", "cto", "cmo", "coo", "cfo"):
        kpis, concerns = _kpis_and_concerns(state, seat, cash, b, data)
        lines += kpis[:1]
        worries += concerns[:1]
    done = [d for d in state.ceo_decisions if d.person_id == ceo_id and d.turn > since]
    did = "; ".join(d.text for d in sorted(done, key=lambda d: (-d.turn, -d.id))[:DONE_LISTED])
    quarter = quarter_label(state.turn)
    parts = [f"Dear Chair, {quarter}."]
    parts.append(
        f"I ran {', '.join(s.upper() if s != 'products' else 'products' for s in scopes)}."
    )
    parts.append(f"What I did: {did}." if did else "I made no changes this quarter.")
    if voice is not None:
        parts.append(_pitching(state, ceo_id, voice, since))
    parts.append(
        "What worries me: " + "; ".join(worries[:CONCERNS]) + "."
        if worries
        else "Nothing worries me."
    )
    parts.append("Across the company: " + "; ".join(lines) + ".")
    return " ".join(parts)


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
