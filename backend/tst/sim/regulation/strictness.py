"""A regulator's strictness after the history (docs/formulas.md 48.1; M35b): the data's index to
`history_end` (regulation.yaml), then a seeded yearly path moved by politics and by 32.5's
influence, within `regulation.strictness.bounds`.

- **The path** (hidden, 48.6: never in the API or a prompt): from the history's last year each
  January adds a drift `u x sd x sqrt(3)` (u uniform in [-1, 1]: a yearly step of sd `sd`)
  and, in an election year, a political swing uniform in `swing`; clamped to `bounds` each
  year. Elections come every `election_years`, the first in a seeded year of the first cycle.
  Stream `regulation` key (3, regulator index, year - 2010): uniform draws only (no libm call,
  so the path is the same on every platform: M35a).
- **Influence:** the path x (1 - `influence_cut` x I / 100), I the most influence any company
  holds in the regulator's region (32.5, public), then clamped to `bounds` again.

Before the history's end it is the data's index exactly (48.5 target 1: history holds).
"""

from __future__ import annotations

from functools import cache
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.regulation import data as rdata
from tst.sim.regulation import draws
from tst.sim.regulation.config import RegulatorDef, StrictnessBalance
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

PATH: Final = 3  # tunable-exempt: the draws module's key family for the strictness path
SQRT3: Final = 1.7320508075688772  # tunable-exempt: a uniform's sd is half-width / sqrt(3)
PCT: Final = 100.0  # tunable-exempt: influence is 0-100


def _clamp(x: float, bounds: tuple[float, float]) -> float:
    return min(bounds[1], max(bounds[0], x))


@cache
def _path(
    seed: int, index: int, start_value: float, first_year: int, year: int, sb: StrictnessBalance
) -> float:
    """The drawn path's value in `year` (> first_year), before influence."""
    rng = RngFactory(seed)
    phase = draws.gen(rng, 0, PATH, index, 0)
    first_election = first_year + 1 + int(phase.integers(0, sb.election_years))
    value = start_value
    for y in range(first_year + 1, year + 1):
        g = draws.gen(rng, 0, PATH, index, y - rdata.FIRST_YEAR)
        u, w = (float(x) for x in g.random(2))
        value += (2 * u - 1) * sb.sd * SQRT3
        if y >= first_election and (y - first_election) % sb.election_years == 0:
            lo, hi = sb.swing
            value += lo + (hi - lo) * w
        value = _clamp(value, sb.bounds)
    return value


def strictness(
    state: GameState, reg: RegulatorDef, balance: Balance, data: GameData, turn: int | None = None
) -> float:
    """The regulator's strictness this month (module docstring)."""
    turn = state.turn if turn is None else turn
    f = rdata.file(data)
    last = rdata.year_of(f.history_end_turn)
    year = rdata.year_of(turn)
    base = rdata.strictness(reg, turn)
    if year <= last:
        return base
    sb = balance.regulation.strictness
    index = rdata.regulator_index(data, reg.key)
    path = _path(state.save_meta.master_seed, index, reg.strictness_in(last), last, year, sb)
    most = max((i.value for i in state.influence if i.region == reg.region), default=0.0)
    return _clamp(path * (1 - sb.influence_cut * most / PCT), sb.bounds)


def merger_factor(
    state: GameState, acquirer_id: int, region: str, balance: Balance, data: GameData
) -> float:
    """28.4's antitrust review reads the region's regulators (M35b): its block probability x the
    strictest regulator's strictness over its value at the history's end (1 to December 2025),
    x `regulation.merger_review.open_case` while one of them has an open case on the acquirer.
    1 when regulation is not in the data or not yet running."""
    if not rdata.active(state.turn, balance, data):
        return 1.0
    regs = rdata.regulators_in(data, region)
    if not regs:
        return 1.0
    last = rdata.year_of(rdata.file(data).history_end_turn)
    ratio = max(
        (
            strictness(state, r, balance, data) / r.strictness_in(last)
            if r.strictness_in(last)
            else 1.0
        )
        for r in regs
    )
    keys = {r.key for r in regs}
    open_case = any(
        c.company_id == acquirer_id and c.regulator in keys and c.outcome == "open"
        for c in state.reg_cases
    )
    return ratio * (balance.regulation.merger_review.open_case if open_case else 1.0)
