"""The CFO delegate's hedging programme (docs/formulas.md 64.4 and 40): a CFO with authority runs a
rolling hedge of its `hedge_pct` guardrail (capped at `fx.cfo_limit_share`) of each month's net
foreign revenue, as far ahead as a forward runs (`fx.term_months`' longest; 24 months from M57's
ADR-0025 amendment), once at least `fx.unlock_share` of the company's revenue is
foreign. It never replaces a programme the player set; a guardrail of 0 (the default) ends its own
programme."""

from __future__ import annotations

from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.fx.actions import SetHedgeProgramme
from tst.sim.org.models import Authority
from tst.sim.state import GameState

PCT: Final = 100.0  # tunable-exempt: a percent


def foreign_share(state: GameState, company_id: int) -> float:
    """Foreign revenue over all revenue last month (0 without either)."""
    last = max((m.turn for m in state.fx.months if m.company_id == company_id), default=None)
    foreign = sum(
        m.revenue_cents for m in state.fx.months if m.company_id == company_id and m.turn == last
    )
    company = state.company(company_id)
    total = company.mrr_history[-1] if company is not None and company.mrr_history else 0
    return foreign / total if total > 0 else 0.0  # money-exact: ratio


def programme_action(
    state: GameState, authority: Authority, holder: int, balance: Balance, data: GameData
) -> SetHedgeProgramme | None:
    if data.fx is None:
        return None
    company = authority.company_id
    term = int(balance.fx.term_months.hi)  # 64.6 target 5's rolling hedge
    want = min(
        float(dict(authority.guardrails).get("hedge_pct", 0)) / PCT,  # type: ignore[arg-type]
        balance.fx.cfo_limit_share,
    )
    existing = state.fx.programme(company)
    if existing is not None and not existing.by_cfo:
        return None
    if want <= 0:
        return SetHedgeProgramme(holder, 0.0, term, by_cfo=True) if existing else None
    if foreign_share(state, company) < balance.fx.unlock_share:
        return None
    if existing is not None and existing.share == want:
        return None
    return SetHedgeProgramme(holder, want, term, by_cfo=True)
