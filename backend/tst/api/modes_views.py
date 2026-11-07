"""M15b views (docs/formulas.md 30)."""

from __future__ import annotations

import math

from tst.api.schemas.modes import ScoreOut
from tst.loader import LoadedData
from tst.sim import score as sc
from tst.sim.ledger import LedgerBalances
from tst.sim.state import GameState


def score_out(
    state: GameState,
    company_id: int,
    balances: LedgerBalances,
    data: LoadedData,
    markets: dict[sc.Market, dict[int, float]] | None = None,
) -> ScoreOut:
    b = data.balance
    s = sc.company_score(state, company_id, balances, b, data.game_data, markets)
    sb = b.score
    decades = math.log10(max(s.value_cents / sc.CENTS, sb.value_floor_dollars)) - math.log10(
        sb.value_floor_dollars
    )
    last = sc.latest_score(state, company_id)
    return ScoreOut(
        score=s.score,
        value_points=round(sb.weight_value * min(max(decades / sb.value_span_decades, 0), 1), 1),
        growth_points=round(sb.weight_growth * s.growth, 1),
        profit_points=round(sb.weight_profit * s.profit, 1),
        leadership_points=round(sb.weight_leadership * s.leadership, 1),
        reputation_points=round(sb.weight_reputation * s.reputation, 1),
        estimate_cents=s.value_cents,
        last_december=last.score if last is not None else None,
    )
