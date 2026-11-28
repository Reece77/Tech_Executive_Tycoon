"""Payments (docs/formulas.md 64.2). Amounts are integer cents.

**Acquiring.** A payments line's merchants (`pay_merchants`) each carry finance_services.yaml's
yearly volume; the line books its merchant discount as revenue (phase 5: price x merchants) and
pays, on that volume, the region's interchange (by date: the US debit cap from October 2011, the
EU's from December 2015) plus the network fee (Dr 5520, Cr cash), and fraud of `fraud_bp` x (1 -
`fraud_skill_cut` x its team's security skill) (Dr 5530). Rivals' acquiring lines pay the same
(with no team skill).

**Networks.** A company's network in a region carries its share of the region's card programmes
(its `pay_networks` customers / the market): its volume is that share of the region's network
volume (card volume less the rails'), and its fee is its line's price (phase 5). Its
`acceptance` (the share of merchants taking it) moves `acceptance_adjust` a month toward share **
`acceptance_exponent`; card programmes weigh it (tst.sim.finserv.gates): the two-sided effect.

**Issuing.** A chartered bank's card loans carry `card_turnover` of volume a month and earn the
region's interchange on it (tst.sim.finserv.banks).

**Rails** (UPI, Pix, FedNow) take their share of the region's volume from their dates at no
network fee (tst.sim.finserv.demand).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.finserv.data import MONTHS, file, team_skill
from tst.sim.finserv.demand import network_volume_dollars, rails_share
from tst.sim.finserv.models import PaymentsMonth
from tst.sim.ledger import CASH, LedgerEntry, LedgerLine
from tst.sim.money import BP_DENOMINATOR, times, times_over
from tst.sim.products.models import SELLING, Product
from tst.sim.state import GameState

INTERCHANGE_FEES: Final = "5520_interchange_fees"
FRAUD: Final = "5530_fraud_losses"
INTERCHANGE: Final = "4510_interchange"
MERCHANTS: Final = "pay_merchants"
NETWORKS: Final = "pay_networks"
CENTS: Final = 100  # tunable-exempt: cents a dollar
SECURITY: Final = ("security",)  # tunable-exempt: the fraud team's skill


def interchange_bp(region: str, turn: int, data: GameData) -> float:
    return file(data).payments.interchange_at(region, turn)


def _rows(state: GameState, p: Product, home: str) -> list[tuple[str, str, float]]:
    """(segment, region, customers) of a line's segments."""
    out = [(s.segment, home, s.customers) for s in state.segments_of(p.id)]
    out += [(r.segment, r.region, r.customers) for r in state.regional_segments_of(p.id)]
    return out


def acquired_cents(merchants: float, data: GameData) -> int:
    """A month's volume of `merchants` merchants (cents)."""
    per = round(file(data).payments.volume_per_merchant_cents)
    return times_over(per, MONTHS, merchants)


def network_share(
    state: GameState, company_id: int, region: str, balance: Balance, data: GameData
) -> float:
    """The company's share of the region's card programmes."""
    cat = balance.finserv.payments_category
    home = home_region_of(state, balance, data)
    mine = 0.0
    for p in state.company_products(company_id):
        if p.category != cat or p.status not in SELLING:
            continue
        mine += sum(n for seg, r, n in _rows(state, p, home) if seg == NETWORKS and r == region)
    if region == home:
        market = next(
            (m.addressable for m in state.markets if m.category == cat and m.segment == NETWORKS),
            0.0,
        )
    else:
        market = next(
            (
                m.addressable
                for m in state.regional_markets
                if m.category == cat and m.segment == NETWORKS and m.region == region
            ),
            0.0,
        )
    return mine / market if market > 0 else 0.0


def acquiring_entries(
    state: GameState, balance: Balance, data: GameData
) -> tuple[list[LedgerEntry], dict[tuple[int, str], tuple[int, int, int]]]:
    """Every acquiring line's interchange, network fees and fraud this month (module docstring).
    Returns the entries and, for the player's companies, (company, region) -> (volume,
    interchange and fees, fraud)."""
    fb = balance.finserv
    pd = file(data).payments
    home = home_region_of(state, balance, data)
    ledger = {c.id: c for c in state.ledger_companies()}
    fees: dict[int, int] = {}
    fraud: dict[int, int] = {}
    shown: dict[tuple[int, str], tuple[int, int, int]] = {}
    for p in state.products:
        if (
            p.category != fb.payments_category
            or p.company_id not in ledger
            or p.status not in SELLING
        ):
            continue
        skill = team_skill(state, p, SECURITY, balance, data)
        cut = 1.0 - fb.payments.fraud_skill_cut * skill
        for seg, region, n in _rows(state, p, home):
            if seg != MERCHANTS or n <= 0:
                continue
            volume = acquired_cents(n, data)
            bp = interchange_bp(region, state.turn, data) + pd.network_fee_bp
            fee = times(volume, bp / BP_DENOMINATOR)
            loss = times(volume, pd.fraud_bp / BP_DENOMINATOR, cut)
            fees[p.company_id] = fees.get(p.company_id, 0) + fee
            fraud[p.company_id] = fraud.get(p.company_id, 0) + loss
            if ledger[p.company_id].is_player:
                v, f0, l0 = shown.get((p.company_id, region), (0, 0, 0))
                shown[(p.company_id, region)] = (v + volume, f0 + fee, l0 + loss)
    entries = []
    for cid in sorted(set(fees) | set(fraud)):
        lines = [
            LedgerLine(INTERCHANGE_FEES, fees.get(cid, 0)),
            LedgerLine(FRAUD, fraud.get(cid, 0)),
            LedgerLine(CASH, -(fees.get(cid, 0) + fraud.get(cid, 0))),
        ]
        rows = tuple(x for x in lines if x.amount)
        if rows:
            entries.append(
                LedgerEntry(
                    turn=state.turn,
                    company_id=cid,
                    memo="Interchange, network fees and fraud",
                    lines=rows,
                )
            )
    return entries, shown


def networks_month(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Each network's acceptance moves toward its share ** acceptance_exponent."""
    pb = balance.finserv.payments
    if not state.finserv.networks:
        return state
    out = []
    for n in state.finserv.networks:
        share = network_share(state, n.company_id, n.region, balance, data)
        target = dmath.pow(share, pb.acceptance_exponent) if share > 0 else 0.0
        out.append(
            replace(n, acceptance=n.acceptance + pb.acceptance_adjust * (target - n.acceptance))
        )
    return replace(state, finserv=replace(state.finserv, networks=tuple(out)))


def months(
    state: GameState,
    shown: dict[tuple[int, str], tuple[int, int, int]],
    balance: Balance,
    data: GameData,
) -> tuple[PaymentsMonth, ...]:
    """The player's payments months: acquiring by region, and its networks' volume and share."""
    rows: dict[tuple[int, str], PaymentsMonth] = {}
    for (cid, region), (volume, fee, loss) in shown.items():
        rows[(cid, region)] = PaymentsMonth(
            turn=state.turn,
            company_id=cid,
            region=region,
            network_volume_cents=0,
            acquired_cents=volume,
            share=0.0,
            acceptance=0.0,
            interchange_cents=fee,
            fraud_cents=loss,
            rails_share=rails_share(state, region, balance, data),
        )
    for n in state.finserv.networks:
        share = network_share(state, n.company_id, n.region, balance, data)
        dollars = network_volume_dollars(state, n.region, balance, data) * balance.finserv.scale
        volume = times_over(round(dollars * CENTS), MONTHS, share)  # money-exact: rate
        base = rows.get((n.company_id, n.region))
        row = PaymentsMonth(
            turn=state.turn,
            company_id=n.company_id,
            region=n.region,
            network_volume_cents=volume,
            acquired_cents=base.acquired_cents if base else 0,
            share=share,
            acceptance=n.acceptance,
            interchange_cents=base.interchange_cents if base else 0,
            fraud_cents=base.fraud_cents if base else 0,
            rails_share=rails_share(state, n.region, balance, data),
        )
        rows[(n.company_id, n.region)] = row
    return tuple(rows[k] for k in sorted(rows))
