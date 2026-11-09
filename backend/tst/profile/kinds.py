"""The achievement condition kinds (M25): one per field of Facts. A number is earned at or
above its threshold, a flag when true, a set when it holds the achievement's param."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Facts:
    products_launched: int = 0
    customers: int = 0
    headcount: int = 0
    arr_cents: int = 0
    cash_cents: int = 0
    stage: int = 0
    months_running: int = 0
    company_score: int = 0
    market_cap_cents: int = 0
    eras_caused: int = 0
    datacentre_use: float = 0.0  # fraction: the busiest live data centre's use
    acquisitions: int = 0
    clean_integrations: int = 0
    subsidiaries: int = 0
    exits: int = 0
    promises_kept: int = 0
    foundation_grant_cents: int = 0  # the foundation's last (yearly) grant
    profitable_in_first_year: bool = False
    listed: bool = False
    own_chip_in_own_device: bool = False
    refounded: bool = False
    downturn_without_layoffs: bool = False
    burnout_recovered: bool = False
    rounds_closed: frozenset[str] = field(default_factory=frozenset)
    scenario_won: frozenset[str] = field(default_factory=frozenset)
