"""M15b views (docs/formulas.md 30)."""

from __future__ import annotations

import math

from tst.api.schemas.modes import RankingEntryOut, RankingListOut, RankingsOut, ScoreOut
from tst.loader import LoadedData
from tst.sim import score as sc
from tst.sim.data_models import Balance
from tst.sim.ledger import LedgerBalances
from tst.sim.modes.models import CompanyScore
from tst.sim.state import GameState


def score_points(s: CompanyScore, b: Balance) -> dict[str, float]:
    """The score's five parts in points, as the score card shows them (30.1; M51's results)."""
    sb = b.score
    decades = math.log10(max(s.value_cents / sc.CENTS, sb.value_floor_dollars)) - math.log10(
        sb.value_floor_dollars
    )
    return {
        "value": round(sb.weight_value * min(max(decades / sb.value_span_decades, 0), 1), 1),
        "growth": round(sb.weight_growth * s.growth, 1),
        "profit": round(sb.weight_profit * s.profit, 1),
        "leadership": round(sb.weight_leadership * s.leadership, 1),
        "reputation": round(sb.weight_reputation * s.reputation, 1),
    }


def score_out(
    state: GameState,
    company_id: int,
    balances: LedgerBalances,
    data: LoadedData,
    markets: dict[sc.Market, dict[int, float]] | None = None,
) -> ScoreOut:
    b = data.balance
    s = sc.company_score(state, company_id, balances, b, data.game_data, markets)
    p = score_points(s, b)
    last = sc.latest_score(state, company_id)
    return ScoreOut(
        score=s.score,
        value_points=p["value"],
        growth_points=p["growth"],
        profit_points=p["profit"],
        leadership_points=p["leadership"],
        reputation_points=p["reputation"],
        estimate_cents=s.value_cents,
        last_december=last.score if last is not None else None,
    )


def rankings_out(state: GameState, year: int | None = None) -> RankingsOut:
    from tst.sim.calendar import turn_to_ym
    from tst.sim.modes.rankings import LIST_LABELS

    years = sorted({turn_to_ym(r.turn)[0] for r in state.rankings}, reverse=True)
    pick = year if year in years else (years[0] if years else None)
    lists = []
    for kind in ("revenue", "places", "innovative"):
        entries = [
            RankingEntryOut(
                place=r.place,
                company_id=r.company_id,
                name=state.company(r.company_id).name,
                is_you=state.company(r.company_id).is_player,
                value_label=f"${round(r.value) // 100:,}"  # whole dollars (cents in)
                if kind == "revenue"
                else f"{r.value * 100:.0f}",
            )
            for r in sorted(state.rankings, key=lambda r: r.place)
            if r.kind == kind and turn_to_ym(r.turn)[0] == pick
        ]
        lists.append(RankingListOut(kind=kind, label=LIST_LABELS[kind], entries=entries))
    return RankingsOut(year=pick, lists=lists, years=years)
