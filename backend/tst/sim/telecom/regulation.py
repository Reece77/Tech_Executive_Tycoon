"""Telecom regulation (docs/formulas.md 62.4) through 48's regulators with a `telecom` kind
(regulation.yaml `telecom_regulators`):

- **Licence conditions:** a licence's coverage obligation is checked each year from its date: the
  band's site coverage in the region (tst.sim.telecom.networks) must reach the obligation, or the
  region's telecom regulator fines `regulation.obligation_fine_share` of the licence's price (6970)
  that year x its strictness; missed more than `obligation_grace_years` times, the licence is
  revoked and its book value written off (6760).
- **Merger review:** in a telecom market M14's block chance is x `regulation.merger_mult` x the
  region's telecom regulator's strictness (`merger_factor`), and a deal is reviewed from a combined
  share of `regulation.merger_share` (operator consolidation, telecom.yaml's precedents).
- **Net neutrality:** telecom.yaml's rules by area and date; while one is in force in a region, a
  line there cannot zero-rate (tst.sim.telecom.services, actions).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, FINES, SPECTRUM, SPECTRUM_AMORTIZATION, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import exact
from tst.sim.state import GameState
from tst.sim.telecom import networks as nw
from tst.sim.telecom.data import MONTHS


def strictness(state: GameState, region: str, data: GameData) -> float:
    """The region's telecom regulator's strictness this year (1.0 without one)."""
    reg = data.regulation
    if reg is None or not reg.telecom_regulators:
        return 1.0
    year = 2010 + state.turn // MONTHS  # tunable-exempt: turn 0 is January 2010
    values = [r.strictness_in(year) for r in reg.telecom_regulators if r.region == region]
    return max(values) if values else 1.0


def regulator_name(region: str, data: GameData) -> str:
    reg = data.regulation
    if reg is None:
        return "the regulator"
    names = [r.name for r in reg.telecom_regulators if r.region == region]
    return names[0] if names else "the regulator"


def merger_factor(
    state: GameState, category: str, region: str, balance: Balance, data: GameData
) -> float:
    """x M14's block chance for a deal whose blocking market is a telecom one (module docstring)."""
    if category not in balance.telecom.categories:
        return 1.0
    return balance.telecom.regulation.merger_mult * strictness(state, region, data)


def obligations_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    t = state.telecom
    due = [
        x
        for x in t.licences
        if x.status == "active"
        and x.obligation > 0
        and x.obligation_turn is not None
        and state.turn >= x.obligation_turn
        and (state.turn - x.obligation_turn) % MONTHS == 0
    ]
    if not due:
        return state, [], []
    rb = balance.telecom.regulation
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    changed = {}
    for lic in due:
        sites = sum(
            nw.working(state, r)
            for r in nw.radios_in(state, lic.company_id, lic.region)
            if not r.overlay
        )
        cov = nw.site_coverage(sites, lic.band, lic.region, balance, data)
        if cov + 1e-9 >= lic.obligation:  # tunable-exempt: float tolerance
            continue
        name = regulator_name(lic.region, data)
        fines = lic.fines + 1
        if fines > rb.obligation_grace_years:
            left = lic.paid_cents - lic.amortized_cents
            if left > 0:
                entries.append(
                    LedgerEntry.transfer(
                        turn=state.turn,
                        company_id=lic.company_id,
                        memo="Spectrum licence revoked",
                        debit=SPECTRUM_AMORTIZATION,
                        credit=SPECTRUM,
                        amount=left,
                    )
                )
            changed[lic.id] = replace(
                lic, status="revoked", fines=fines, amortized_cents=lic.paid_cents
            )
            logs.append(
                inbox_item(
                    state.turn,
                    lic.company_id,
                    "spectrum_revoked",
                    regulator=name,
                    region=data.region(lic.region).label,
                    band=lic.band,
                    coverage=f"{cov:.0%}",
                    owed=f"{lic.obligation:.0%}",
                )
            )
            continue
        fine = round(
            exact(lic.paid_cents)
            * exact(rb.obligation_fine_share)
            * exact(strictness(state, lic.region, data))
        )
        if fine > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=lic.company_id,
                    memo=f"Coverage obligation fine: {name}",
                    debit=FINES,
                    credit=CASH,
                    amount=fine,
                )
            )
        changed[lic.id] = replace(lic, fines=fines)
        logs.append(
            inbox_item(
                state.turn,
                lic.company_id,
                "spectrum_obligation_fine",
                regulator=name,
                region=data.region(lic.region).label,
                band=lic.band,
                coverage=f"{cov:.0%}",
                owed=f"{lic.obligation:.0%}",
                fine_cents=fine,
            )
        )
    licences = tuple(changed.get(x.id, x) for x in t.licences)
    return replace(state, telecom=replace(t, licences=licences)), entries, logs
