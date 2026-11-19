"""The conglomerate view (M43 sub-task 2): one screen across every industry the group is in.
Built from the group's ledger (tst.db.conglomerate, tst.sim.group.conglomerate) and the state's
displayed values: builds under way, mandates' capex limits and the proposals waiting. Read-only;
no hidden value is read."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tst.api.schemas.conglomerate import (
    AllocationOut,
    CapexOut,
    CapitalYearOut,
    CompanyFiguresOut,
    ConglomerateOut,
    FiguresOut,
    IndustryOut,
    IndustryYearOut,
    LetterOut,
    PlannedOut,
    WaitingProposalOut,
)
from tst.api.views import person_name
from tst.db.conglomerate import MONTHS_A_YEAR, Member, current_year, read_books
from tst.db.models import LLMTextRow
from tst.loader import LoadedData
from tst.sim.calendar import turn_to_ym
from tst.sim.group.conglomerate import CORPORATE, Books, Figures, growth, industry_maps, risk_word
from tst.sim.state import GameState, holding_of

LETTER = "letter"  # LLMTextRow kind of the January letters (M43)
CORPORATE_LABEL = "Corporate"


def figures_out(f: Figures) -> FiguresOut:
    return FiguresOut(
        revenue_cents=f.revenue,
        gross_margin=f.gross_margin,
        operating_profit_cents=f.operating_profit,
        operating_margin=f.operating_margin,
        capital_employed_cents=f.capital_employed,
        return_on_capital=f.return_on_capital,
    )


def shown_year(state: GameState, b: Books) -> tuple[int, int]:
    """(year, months): the last full year when one was played inside the books, else this year
    to date."""
    now, month = turn_to_ym(state.turn)
    if now - 1 in b.years:
        return now - 1, MONTHS_A_YEAR
    return now, month


def _months(state: GameState, year: int) -> int:
    now, month = turn_to_ym(state.turn)
    return month if year == now else MONTHS_A_YEAR


def labels(data: LoadedData) -> dict[str, str]:
    out = {i.key: i.label for i in data.balance.conglomerate.industries}
    out[CORPORATE] = CORPORATE_LABEL
    return out


def _industry_series(b: Books, key: str) -> list[tuple[int, Figures]]:
    return [(y, b.by_industry(y).get(key, Figures())) for y in b.years]


def _planned(
    state: GameState, group: list[Member], b: Books, data: LoadedData
) -> dict[str, list[int]]:
    """Next year's planned capital by industry: builds under way (capex still to pay) and the
    subsidiaries' yearly capex limits, each under the subsidiary's largest industry."""
    _, kinds, _, _, _ = industry_maps(data.balance.conglomerate)
    ids = {m.company_id for m in group}
    out: dict[str, list[int]] = {}
    for f in state.facilities:
        if f.company_id in ids and f.status == "building" and f.kind in kinds:
            row = out.setdefault(kinds[f.kind], [0, 0])
            row[0] += max(0, f.capex_cents - f.capex_paid_cents)
    year = b.years[-1] if b.years else current_year(state)
    for m in state.mandates:
        if m.company_id not in ids or m.capex_limit_cents <= 0:
            continue
        own = {
            k: f.revenue
            for (y, cid, k), f in b.cells.items()
            if y == year and cid == m.company_id and k != CORPORATE
        }
        key = max(own, key=lambda k: (own[k], k)) if own else CORPORATE
        out.setdefault(key, [0, 0])[1] += m.capex_limit_cents
    return out


def _proposals(state: GameState, ids: set[int]) -> list[WaitingProposalOut]:
    out: list[WaitingProposalOut] = []
    for p in state.pitches:
        if p.status == "pending" and p.company_id in ids:
            out.append(
                WaitingProposalOut(
                    kind="pitch",
                    company=state.company(p.company_id).name,
                    who=person_name(state.person(p.person_id)),
                    title=p.title,
                    amount_cents=p.cost_cents,
                    turn=p.turn,
                )
            )
    for g in state.group_pitches:
        if g.status == "pending" and g.company_id in ids:
            out.append(
                WaitingProposalOut(
                    kind="group_pitch",
                    company=state.company(g.company_id).name,
                    who=person_name(state.person(g.person_id)),
                    title=f"Capital for {state.company(g.company_id).name}",
                    amount_cents=g.amount_cents,
                    turn=g.turn,
                )
            )
    for x in state.proposals:
        if x.status == "pending" and x.company_id in ids:
            out.append(
                WaitingProposalOut(
                    kind="proposal",
                    company=state.company(x.company_id).name,
                    who=person_name(state.person(x.person_id)),
                    title=x.text,
                    amount_cents=None,
                    turn=x.turn,
                )
            )
    return sorted(out, key=lambda p: (p.turn, p.kind, p.title))


def letters(session: Session, company_id: int) -> list[LetterOut]:
    rows = session.scalars(
        select(LLMTextRow)
        .where(
            LLMTextRow.kind == LETTER,
            LLMTextRow.company_id == company_id,
            LLMTextRow.status == "written",
        )
        .order_by(LLMTextRow.turn.desc())
    ).all()
    return [
        LetterOut(year=int(r.ref_id or 0), turn=r.turn + 1, text=r.text, source=r.source)
        for r in rows
        if r.text
    ]


def _role(state: GameState, company_id: int) -> str:
    held = holding_of(state)
    if held is not None and held.company_id == company_id:
        return "holding"
    return "operating" if company_id == state.player.id else "subsidiary"


def conglomerate_out(session: Session, state: GameState, data: LoadedData) -> ConglomerateOut:
    b, group = read_books(session, state, data)
    names = labels(data)
    year, months = shown_year(state, b)
    cfg = data.balance.conglomerate
    by_ind = b.by_industry(year)
    total = b.group(year)
    trend_years = [y for y in b.years if y > year - cfg.trend_years or y > year]
    industries: list[IndustryOut] = []
    allocation: list[AllocationOut] = []
    planned = _planned(state, group, b, data)
    for ind in cfg.industries:
        series = _industry_series(b, ind.key)
        if not any(f.revenue or f.operating_costs or f.capital_employed for _, f in series):
            continue
        f = by_ind.get(ind.key, Figures())
        full = [s.revenue for y, s in series if y <= year]
        g = growth(full[-2:]) if len(full) >= 2 else []  # tunable-exempt: this year on last
        risk = risk_word(full, cfg)
        industries.append(
            IndustryOut(
                key=ind.key,
                label=ind.label,
                figures=figures_out(f),
                share_of_revenue=f.revenue / total.revenue if total.revenue > 0 else 0.0,
                growth=g[0] if g else None,
                risk=risk,
                trend=[
                    IndustryYearOut(
                        year=y,
                        months=_months(state, y),
                        revenue_cents=s.revenue,
                        operating_profit_cents=s.operating_profit,
                        capital_employed_cents=s.capital_employed,
                        capex_cents=s.capex,
                    )
                    for y, s in series
                    if y in trend_years
                ],
            )
        )
        plan = planned.get(ind.key, [0, 0])
        allocation.append(
            AllocationOut(
                key=ind.key,
                label=ind.label,
                return_on_capital=f.return_on_capital,
                growth=g[0] if g else None,
                risk=risk,
                planned=PlannedOut(
                    key=ind.key, label=ind.label, committed_cents=plan[0], limits_cents=plan[1]
                ),
            )
        )
    corp = by_ind.get(CORPORATE)
    companies = []
    for m in group:
        if m.end is not None or not state.company(m.company_id).alive:
            continue  # companies the group holds now; what left keeps its part of the past
        own = b.company.get((m.company_id, year), Figures())
        inds = sorted(
            {
                k
                for (y, cid, k), f in b.cells.items()
                if y == year and cid == m.company_id and k != CORPORATE and f.revenue > 0
            }
        )
        internal = b.intercompany.get((m.company_id, year), 0)
        companies.append(
            CompanyFiguresOut(
                company_id=m.company_id,
                name=state.company(m.company_id).name,
                role=_role(state, m.company_id),
                industries=[names[k] for k in inds],
                figures=figures_out(own),
                intercompany_cents=internal,
            )
        )
    capital = [
        CapitalYearOut(
            year=y,
            capex=[
                CapexOut(key=k, label=names.get(k, k), cents=v)
                for k, v in sorted(u.capex.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
            acquisitions_cents=u.stakes,
            returned_cents=u.returned,
        )
        for y, u in sorted(b.uses.items())
        if y in trend_years
    ]
    ids = {m.company_id for m in group}
    return ConglomerateOut(
        year=year,
        months=months,
        group=figures_out(total),
        industries=industries,
        corporate=figures_out(corp) if corp is not None else None,
        companies=companies,
        capital=capital,
        allocation=allocation,
        proposals=_proposals(state, ids),
        letters=letters(session, state.player.id),
    )
