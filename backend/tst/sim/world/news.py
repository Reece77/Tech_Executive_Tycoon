"""World news (docs/formulas.md 41.7): one feed of the world's moves, kept for
`world.news_months` months, each item linked to its companies, region and good."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from tst.sim.state import GameState
from tst.sim.world.models import NewsKind, WorldNews


@dataclass(frozen=True, slots=True)
class Item:
    """A news item before it gets its id."""

    kind: NewsKind
    message: str
    company_id: int | None = None
    other_id: int | None = None
    region: str | None = None
    good: str | None = None


def publish(state: GameState, items: Sequence[Item], keep_months: int) -> GameState:
    """Add this month's items (ids follow the last) and drop those older than the window."""
    if not items and not state.world_news:
        return state
    next_id = max((n.id for n in state.world_news), default=0) + 1
    new = [
        WorldNews(
            id=next_id + i,
            turn=state.turn,
            kind=x.kind,
            message=x.message,
            company_id=x.company_id,
            other_id=x.other_id,
            region=x.region,
            good=x.good,
        )
        for i, x in enumerate(items)
    ]
    kept = tuple(n for n in (*state.world_news, *new) if n.turn > state.turn - keep_months)
    return replace(state, world_news=kept)
