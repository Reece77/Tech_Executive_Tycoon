"""M22 (formulas.md 39.3): the ledger balances with tariffs. For any start year, contract size and
number of months, a China-assembled device company's books move cash by exactly its postings,
its tariffs are never negative, and every tariff equals the schedule's rate on the cost of the
units made in China and sold in the taxing market.

M23a (Codex review 5 finding 12): the expected tariff is computed here, independently of the
engine, from tariffs.yaml's steps and countries.yaml's demand shares read raw; a month with
production after the first step must post a positive tariff (an empty list no longer passes), and
months before it must post none. Own-fab and mixed-origin chips are in test_m23a_group.py's
`test_own_fab_chips_pay_their_fabs_countrys_tariff`."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from tst.balance import m12b, m22
from tst.sim.calendar import ym_to_turn
from tst.sim.decisions import Decisions
from tst.sim.ledger import CASH, TARIFFS, apply_entries
from tst.sim.rng import RngFactory
from tst.sim.turn import advance_turn

PLAYER = 1
DATA = Path(__file__).resolve().parents[2] / "data"
RAW = yaml.safe_load((DATA / "tariffs.yaml").read_text(encoding="utf-8"))
COUNTRIES = yaml.safe_load((DATA / "countries.yaml").read_text(encoding="utf-8"))
US_SHARE = next(c["demand_share"] for c in COUNTRIES["countries"] if c["key"] == "us")


def _month(ym: str) -> int:
    year, month = (int(x) for x in ym.split("-"))
    return ym_to_turn(year, month)


def devices_rate(turn: int) -> float:
    """China-made devices sold in the US: the summed schedules' step in force at `turn`."""
    total = 0.0
    for s in RAW["schedules"]:
        if s["origin"] != "china" or s["market"] != "us" or "devices" not in s["goods"]:
            continue
        rate = 0.0
        for ym, r in s["steps"]:
            if _month(ym) <= turn:
                rate = r
        total += rate
    return total


@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    year=st.integers(min_value=2016, max_value=2025),
    units=st.integers(min_value=2_000, max_value=60_000),
    months=st.integers(min_value=1, max_value=4),
)
@example(year=2020, units=20_000, months=1)  # Codex's case: China to the US, tariff-bearing
@example(year=2016, units=20_000, months=1)  # before Section 301: none
def test_tariffs_keep_the_ledger_balanced(year: int, units: int, months: int) -> None:
    data = m22.loaded()
    m12b._loaded = lambda: data  # type: ignore[assignment]
    g, pid = m12b.device_company(3, own_chip=False, start=ym_to_turn(year, 1), units=units)
    for _ in range(months):
        result = advance_turn(
            g.state, Decisions(), RngFactory(3), data.balance, data.game_data, g.balances
        )
        for e in result.ledger_entries:
            assert sum(line.amount for line in e.lines) == 0
        cash = sum(
            line.amount
            for e in result.ledger_entries
            if e.company_id == PLAYER
            for line in e.lines
            if line.account == CASH
        )
        before = g.balances.get((PLAYER, CASH), 0)
        g.balances = apply_entries(g.balances, result.ledger_entries)
        assert g.balances.get((PLAYER, CASH), 0) - before == cash
        taxed = [
            line.amount
            for e in result.ledger_entries
            if e.company_id == PLAYER
            for line in e.lines
            if line.account == TARIFFS
        ]
        assert all(x > 0 for x in taxed)
        settled = replace(result.new_state, turn=g.state.turn)  # the month's production rows
        row = next((r for r in settled.production if r.product_id == pid), None)
        assert row is not None
        # every unit is assembled in Shenzhen (China) and sold to North American customers
        home = {s.segment for s in settled.segments_of(pid) if s.customers > 0}
        rate = devices_rate(g.state.turn)
        if rate > 0 and row.units > 0 and row.cogs_cents > 0 and home:
            expected = round(row.cogs_cents * US_SHARE * rate)
            assert taxed and abs(sum(taxed) - expected) <= 1
        else:
            assert taxed == []
        g.state = result.new_state
