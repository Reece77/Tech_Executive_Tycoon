"""Standards wars (docs/formulas.md 44.7).

History (platforms.yaml): USB-C over Lightning and Qi over PMA, tipped on their dates; no
product carries their formats, so they change no demand. From 2026, each December brings
Poisson(`standards.rate`) contests (stream `platforms` key (3, 0, year), then (3, 1, n) for
the contest's category and each product's first format) in one of `standards.categories`.
Products in the category take a format; new products join the larger one. Each month adoption
(the customer-weighted share on the first format) moves toward the current mix with
`inertia`; at `tip_share` (or 1 - it) the contest tips. A product left on the losing format
loses `penalty` feature points until it adopts the winner, which takes `adopt_months` (rivals
adopt at once when it tips; the player by the AdoptStandard action).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.log import LogItem, inbox_item
from tst.sim.platforms import data as pdata
from tst.sim.platforms import draws
from tst.sim.platforms.data import EVEN
from tst.sim.platforms.models import ProductStandard, Standard
from tst.sim.products.models import SELLING
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def penalties(state: GameState, balance: Balance, data: GameData) -> dict[tuple[int, str], float]:
    """Feature points off products on a tipped contest's losing format, in every region."""
    out: dict[tuple[int, str], float] = {}
    tipped = {s.id: s for s in state.standards if s.winner is not None}
    for ps in state.product_standards:
        s = tipped.get(ps.standard_id)
        if s is None or ps.format == s.winner:
            continue
        for region in data.region_keys:
            out[(ps.product_id, region)] = (
                out.get((ps.product_id, region), 0.0) + balance.platforms.standards.penalty
            )
    return out


def _customers(state: GameState, product_id: int) -> float:
    return sum(s.customers for s in state.segments_of(product_id)) + sum(
        r.customers for r in state.regional_segments_of(product_id)
    )


def standards_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    if not pdata.enabled(data) or pdata.in_history(state.turn, data):
        return state, []
    sb = balance.platforms.standards
    logs: list[LogItem] = []
    if state.turn % MONTHS_PER_YEAR == MONTHS_PER_YEAR - 1:
        state = _new_contests(state, rng, balance)
    rows = list(state.product_standards)
    contests = []
    for s in state.standards:
        if s.historical or s.winner is not None:
            contests.append(s)
            continue
        mine = [ps for ps in rows if ps.standard_id == s.id]
        have = {ps.product_id for ps in mine}
        bigger = s.formats[0] if s.adoption >= EVEN else s.formats[1]
        for p in state.products:  # new products join the larger format
            if p.category == s.category and p.status != "retired" and p.id not in have:
                rows.append(ProductStandard(p.id, s.id, bigger))
        mine = [ps for ps in rows if ps.standard_id == s.id]
        weights = {f: 0.0 for f in s.formats}
        for ps in mine:
            product = state.product(ps.product_id)
            if product is not None and product.status in SELLING:
                weights[ps.format] += max(_customers(state, ps.product_id), 1.0)
        total = sum(weights.values())
        mix = weights[s.formats[0]] / total if total > 0 else s.adoption
        adoption = sb.inertia * s.adoption + (1 - sb.inertia) * mix
        winner = (
            s.formats[0]
            if adoption >= sb.tip_share
            else s.formats[1]
            if adoption <= 1 - sb.tip_share
            else None
        )
        s = replace(s, adoption=adoption)
        if winner is not None:
            s = replace(s, winner=winner, tipped_turn=state.turn)
            player_ids = {c.id for c in state.companies if c.is_player}
            for i, ps in enumerate(rows):
                if ps.standard_id != s.id or ps.format == winner:
                    continue
                product = state.product(ps.product_id)
                if product is not None and product.company_id not in player_ids:
                    rows[i] = replace(ps, format=winner)  # rivals adopt the winner at once
            logs.append(
                inbox_item(
                    state.turn,
                    state.player.id,
                    "standard_tipped",
                    link_kind="platforms",
                    link_id=s.id,
                    standard=s.label,
                    winner=winner,
                )
            )
        contests.append(s)
    for i, ps in enumerate(rows):  # adoptions that finish this month
        if ps.adopting_until is not None and ps.adopting_until <= state.turn:
            s = next(x for x in contests if x.id == ps.standard_id)
            rows[i] = replace(ps, format=s.winner or ps.format, adopting_until=None)
    return replace(state, standards=tuple(contests), product_standards=tuple(rows)), logs


def _new_contests(state: GameState, rng: RngFactory, balance: Balance) -> GameState:
    sb = balance.platforms.standards
    year = pdata.year_of(state.turn)
    n = int(draws.gen(rng, state.turn, draws.STANDARDS, 0, year).poisson(sb.rate))
    contests = list(state.standards)
    rows = list(state.product_standards)
    for k in range(n):
        sid = max([-1, *(s.id for s in contests)]) + 1
        gen = draws.gen(rng, state.turn, draws.STANDARDS, 1, sid)
        category = sb.categories[int(gen.integers(len(sb.categories)))]
        label = f"{category.replace('_', ' ').capitalize()} format {year}-{k + 1}"
        formats = (f"{label} A", f"{label} B")
        contests.append(
            Standard(
                id=sid,
                key=f"seeded_{sid}",
                category=category,
                label=label,
                formats=formats,
                sponsors=(None, None),
                adoption=EVEN,
                started_turn=state.turn,
            )
        )
        for p in state.products:
            if p.category == category and p.status != "retired":
                rows.append(ProductStandard(p.id, sid, formats[int(gen.integers(2))]))
    return replace(state, standards=tuple(contests), product_standards=tuple(rows))
