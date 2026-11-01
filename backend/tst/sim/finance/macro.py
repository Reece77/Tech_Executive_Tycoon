"""The macro layer (docs/formulas.md 20.1, M10): the base rate, the venture climate, consumer
confidence and the AI compute index, set in phase 1 each month.

Through 2025 every indicator is history (`macro_history.yaml`, `compute_index.yaml`), the same
on every seed. From January 2026 each moves by an AR(1) step on stream `macro`, key
`(indicator_index,)`: one generator per indicator a month, one standard-normal draw each (the
AI index's is used only in January, when its yearly change steps), plus one uniform draw on
key `(99,)` for downturns. Draws happen every month in that order whether used or not.

`current` is the month the player is in: history while there is history (it is public), else
the last month phase 1 set. Nothing here ever looks ahead (20.4).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Final

import numpy as np

from tst.sim.calendar import MONTHS_PER_YEAR, turn_to_ym
from tst.sim.data_models import Ar1Balance, Balance, GameData, MacroBalance, MacroHistory
from tst.sim.rng import RngFactory

if TYPE_CHECKING:  # state.py imports MacroMonth from here
    from tst.sim.state import GameState

RATE, CLIMATE, CONFIDENCE, AI = 0, 1, 2, 3  # stream keys (indicator_index,)
DOWNTURN_KEY: Final = 99
CONFIDENCE_SCALE: Final = 100.0  # tunable-exempt: the index's definition (100 = base years)
FIRST_MONTH = 1  # tunable-exempt: January, when the AI index's yearly change steps


@dataclass(frozen=True, slots=True)
class MacroMonth:
    """One month's indicators (formulas.md 20.1). `ai_change` is the AI index's change over
    the year before (it steps each January); `downturn_turn` is the start of the latest
    downturn, carried forward, or None if none has started."""

    turn: int
    base_rate: float  # % a year
    climate: float  # multiplier
    confidence: float  # index, 100 = the 2010-2019 average
    ai_index: float  # multiplier on 2010
    ai_change: float  # fraction
    downturn_turn: int | None = None

    def in_downturn(self, months: int) -> bool:
        return self.downturn_turn is not None and self.turn < self.downturn_turn + months


# --- History -----------------------------------------------------------------------------------


def _history(data: GameData) -> MacroHistory:
    if data.macro_history is None:
        raise RuntimeError("macro_history.yaml is not loaded")
    return data.macro_history


def last_history_turn(data: GameData) -> int:
    """The last turn with history (December 2025)."""
    h = _history(data)
    return (h.last_year - h.first_year + 1) * MONTHS_PER_YEAR - 1


def rescaled_confidence(raw: float, history: MacroHistory) -> float:
    """The raw survey value as an index with the base years' average at 100 (20.1)."""
    return CONFIDENCE_SCALE * raw / history.confidence_base


def history_month(turn: int, data: GameData) -> MacroMonth | None:
    """The indicators for `turn` from history, or None after the history ends."""
    h = _history(data)
    year, month = turn_to_ym(turn)
    if not h.first_year <= year <= h.last_year:
        return None
    ai = data.compute_index.of(year)
    return MacroMonth(
        turn=turn,
        base_rate=h.base_rate[year][month - 1],
        climate=h.climate[year],
        confidence=rescaled_confidence(h.confidence[year][month - 1], h),
        ai_index=ai,
        ai_change=ai / data.compute_index.of(year - 1) - 1,
    )


# --- After the history: AR(1) and downturns ---------------------------------------------------


def ar1_step(x: float, mean: float, phi: float, shock: float) -> float:
    """mean + phi (x - mean) + shock (20.1; 20.6 worked example), unclamped."""
    return mean + phi * (x - mean) + shock


def ar1(x: float, a: Ar1Balance, z: float) -> float:
    """One AR(1) step with a standard-normal draw `z`, clamped to the indicator's bounds."""
    return min(a.bounds.hi, max(a.bounds.lo, ar1_step(x, a.mean, a.phi, a.shock_sd * z)))


def downturn_starts(prev: MacroMonth, turn: int, u: float, mb: MacroBalance) -> bool:
    """A downturn starts with probability `downturn.monthly` if no downturn month fell in the
    last `gap_months` months (20.1)."""
    d = mb.downturn
    if prev.downturn_turn is not None and turn - (prev.downturn_turn + d.months) < d.gap_months:
        return False
    return u < d.monthly


def step_month(
    prev: MacroMonth, turn: int, z: tuple[float, float, float, float], u: float, mb: MacroBalance
) -> MacroMonth:
    """The month after `prev` from four standard-normal draws (rate, climate, confidence, AI)
    and the downturn uniform (20.1). A running downturn pushes before the AR(1) step."""
    started = downturn_starts(prev, turn, u, mb)
    downturn_turn = turn if started else prev.downturn_turn
    rate, climate, confidence = prev.base_rate, prev.climate, prev.confidence
    d = mb.downturn
    if downturn_turn is not None and turn < downturn_turn + d.months:
        rate += d.rate
        climate += d.climate
        confidence += d.confidence
    ai, change = prev.ai_index, prev.ai_change
    if turn_to_ym(turn)[1] == FIRST_MONTH:
        change = ar1(prev.ai_change, mb.ai_change, z[AI])
        ai = prev.ai_index * (1 + change)
    return MacroMonth(
        turn=turn,
        base_rate=ar1(rate, mb.rate, z[RATE]),
        climate=ar1(climate, mb.climate, z[CLIMATE]),
        confidence=ar1(confidence, mb.confidence, z[CONFIDENCE]),
        ai_index=ai,
        ai_change=change,
        downturn_turn=downturn_turn,
    )


def draws(rng: RngFactory, turn: int) -> tuple[tuple[float, float, float, float], float]:
    """This month's draws on stream `macro`: one standard normal per indicator, then the
    downturn uniform."""

    def normal(key: int) -> float:
        gen: np.random.Generator = rng.stream(turn, "macro", key)
        return float(gen.standard_normal())

    z = (normal(RATE), normal(CLIMATE), normal(CONFIDENCE), normal(AI))
    u = float(rng.stream(turn, "macro", DOWNTURN_KEY).random())
    return z, u


def month_for(
    turn: int, prev: MacroMonth | None, rng: RngFactory, balance: Balance, data: GameData
) -> MacroMonth:
    """The indicators for `turn`: history, else one step from the month before. A save that
    has no month before (it was made before M10) steps from the last month of history."""
    known = history_month(turn, data)
    if known is not None:
        return known
    if prev is None or prev.turn != turn - 1:
        last = last_history_turn(data)
        prev = prev if prev is not None and prev.turn < turn else history_month(last, data)
        assert prev is not None
        prev = replace(prev, turn=turn - 1)
    z, u = draws(rng, turn)
    return step_month(prev, turn, z, u, balance.macro)


# --- Reading the macro state ------------------------------------------------------------------


def current(macro: MacroMonth | None, turn: int, data: GameData) -> MacroMonth:
    """The month the player is in: history while there is history, else the latest month
    phase 1 set (never a month ahead, 20.4)."""
    known = history_month(turn, data)
    if known is not None:
        return known
    if macro is not None:
        return macro
    last = history_month(min(turn, last_history_turn(data)), data)
    assert last is not None
    return last


def confidence_factor(confidence: float, exponent: float) -> float:
    """(cc / 100)^exponent: 81 gives 0.90 at exponent 0.5 (20.6)."""
    return float((confidence / CONFIDENCE_SCALE) ** exponent)


def now(state: GameState, data: GameData) -> MacroMonth:
    return current(state.macro, state.turn, data)


def venture_climate(state: GameState, data: GameData) -> float:
    """`v`: replaces M4's climate(year) everywhere (14.3, 14.5, 15.4; 20.1)."""
    return now(state, data).climate


def base_rate(state: GameState, data: GameData) -> float:
    """`r`, % a year: debt prices off it (20.3)."""
    return now(state, data).base_rate


def ai_index(state: GameState, data: GameData) -> float:
    """`ai`: M8's AI hosting index, continued after 2025 (18.6, 20.1)."""
    return now(state, data).ai_index


def adoption_factor(state: GameState, segment_key: str, balance: Balance) -> float:
    """The one hook for consumer confidence on adoption (20.1): (cc / 100)^0.5 in consumer and
    SMB segments, 1 elsewhere. The market phase calls it once where adoption is used; M9's
    regional markets call the same function. It reads the month phase 1 set (1 before any)."""
    mb = balance.macro
    if segment_key not in mb.confidence_segments or state.macro is None:
        return 1.0
    return confidence_factor(state.macro.confidence, mb.confidence_exponent)


def macro_phase(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """Phase 1: this month's indicators (20.1)."""
    return replace(state, macro=month_for(state.turn, state.macro, rng, balance, data))
