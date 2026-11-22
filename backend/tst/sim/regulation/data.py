"""Regulation's data lookups (docs/formulas.md 48, regulation.yaml): regulators and their
strictness, regimes, history's designations and cases (data, never state), currency, and the
precedents a structural remedy reads (48.4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.money import exact, times
from tst.sim.regulation.config import CaseDef, RegimeDef, RegulationFile, RegulatorDef
from tst.sim.state import GameState, derived

FIRST_YEAR: Final = 2010  # tunable-exempt: turn 0's year
BILLION: Final = 1_000_000_000  # tunable-exempt: thresholds are in billions
CENTS: Final = 100  # tunable-exempt: cents a unit


def enabled(data: GameData) -> bool:
    return data.regulation is not None


def file(data: GameData) -> RegulationFile:
    assert data.regulation is not None
    return data.regulation


def year_of(turn: int) -> int:
    return FIRST_YEAR + turn // MONTHS_PER_YEAR


def in_history(turn: int, data: GameData) -> bool:
    return turn <= file(data).history_end_turn


def active(turn: int, balance: Balance, data: GameData) -> bool:
    """The model acts (on the player and rivals alike) from `regulation.start` (48.5 target 1)."""
    return enabled(data) and turn >= balance.regulation.start_turn


def strictness(reg: RegulatorDef, turn: int) -> float:
    """The regulator's strictness: the data's index by year, flat after the history (A)."""
    return reg.strictness_in(year_of(turn))


def regulator_index(data: GameData, key: str) -> int:
    return next(i for i, r in enumerate(file(data).regulators) if r.key == key)


def regulators_in(data: GameData, region: str) -> tuple[RegulatorDef, ...]:
    return tuple(r for r in file(data).regulators if r.region == region)


def regime_of(data: GameData, regulator: str) -> RegimeDef | None:
    return next((g for g in file(data).regimes if g.regulator == regulator), None)


def part_share(data: GameData, reg: RegulatorDef) -> float:
    """The regulator's share of its region (platforms.yaml's region_parts; whole = 1)."""
    if reg.part is None or data.platforms is None:
        return 1.0
    return data.platforms.part_share(reg.region, reg.part)


def usd_cents(amount: float, currency: str, balance: Balance) -> int:
    """An amount in a currency as US cents (regulation.fx, A)."""
    return round(exact(amount) * exact(balance.regulation.fx[currency]) * CENTS)


def threshold_cents(billions: float | None, currency: str, balance: Balance) -> int | None:
    """A legal threshold as US cents, at real-world scale (shown on screen)."""
    return None if billions is None else usd_cents(billions * BILLION, currency, balance)


def game_threshold_cents(billions: float | None, currency: str, balance: Balance) -> int | None:
    """The same threshold in the game's economy (`economy_scale.money`): what the tests read."""
    real = threshold_cents(billions, currency, balance)
    return None if real is None else times(real, balance.economy_scale.money)


def game_users_share(share: float, balance: Balance) -> float:
    """A users threshold in the game's economy (`economy_scale.users`)."""
    return share * balance.economy_scale.users


def company_ids(state: GameState) -> dict[str, int]:
    return {c.name: c.id for c in state.companies}


# --- History to 2025 (data, never state) -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class HistoryDesignation:
    regime: str
    company_id: int | None
    label: str
    platform_key: str | None
    from_turn: int
    services: tuple[str, ...]
    source: str


def history_designations(
    state: GameState, data: GameData, turn: int
) -> tuple[HistoryDesignation, ...]:
    """History's designations in force by `turn`, kept once per state, turn and data (M36p:
    the month's investigation odds ask for them for every group and regulator)."""
    kept: tuple[GameData, tuple[HistoryDesignation, ...]] = derived(
        state,
        ("regulation.history_designations", turn, id(data)),
        lambda: (data, _history_designations(state, data, turn)),
    )
    if kept[0] is data:
        return kept[1]
    return _history_designations(state, data, turn)


def _history_designations(
    state: GameState, data: GameData, turn: int
) -> tuple[HistoryDesignation, ...]:
    ids = company_ids(state)
    return tuple(
        HistoryDesignation(
            d.regime,
            ids.get(d.company) if d.company else None,
            d.label,
            d.platform,
            d.from_turn,
            d.services,
            d.source,
        )
        for d in file(data).designations
        if d.from_turn <= turn
    )


def history_cases(data: GameData, turn: int) -> tuple[CaseDef, ...]:
    """Cases opened by `turn`, as the data records them (stages after `turn` are hidden by the
    reader: future rulings are never shown before they happen, 48.6)."""
    return tuple(c for c in file(data).cases if c.opened_turn <= turn)


def history_rulings(
    state: GameState, data: GameData, company_id: int, regulator: str, turn: int
) -> list[int]:
    """Months of rulings against the company by the regulator in the data (precedents for 48.4)."""
    ids = company_ids(state)
    out = []
    for c in file(data).cases:
        if c.regulator != regulator or c.company is None or ids.get(c.company) != company_id:
            continue
        ruled = c.ruled_against_turn()
        if ruled is not None and ruled <= turn:
            out.append(ruled)
    return out


def designated_in_history(
    state: GameState, data: GameData, company_id: int, regime: str, turn: int
) -> HistoryDesignation | None:
    return next(
        (
            d
            for d in history_designations(state, data, turn)
            if d.company_id == company_id and d.regime == regime
        ),
        None,
    )
