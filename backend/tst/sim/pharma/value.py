"""Explain: a programme's chance to approval and its expected value, rNPV (docs/formulas.md
55.1, 55.7). Public inputs only: the efficacy estimate's range (never the hidden value), the
shown chances, the stages' planned costs and months, the indication's market and prices.

chance to approval = the product of each remaining stage's shown chance and the submission's;
rNPV = P(approval) x the present value of sales to `demand.horizon_years` after launch (patients
at the estimate's share of the indication in every region, ramping, at the reference price, less
cost of goods through a contract manufacturer), less each remaining stage's cost x the chance of
reaching it, all discounted at `discount_rate`. Low and high read the estimate's range."""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.pharma import ceilings
from tst.sim.pharma import data as pd
from tst.sim.pharma import pipeline as pl
from tst.sim.pharma.config import TRIALS
from tst.sim.pharma.models import Programme
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class Value:
    chance_lo: float
    chance_hi: float
    rnpv_lo_cents: int
    rnpv_hi_cents: int
    peak_lo_cents: int  # a year
    peak_hi_cents: int
    cost_left_cents: int
    years_to_launch: float


def remaining(p: Programme) -> list[str]:
    if p.status == "marketed":
        return []
    order = ["preclinical", *TRIALS]
    if p.stage in ("submission", "approved"):
        return []
    if p.stage == "discovery":
        return order
    i = order.index(p.stage)
    return order[i + 1 :] if p.status == "ready" else order[i:]


def _chance(
    p: Programme, eff: float, balance: Balance, data: GameData
) -> tuple[float, list[float]]:
    """The chance through the remaining stages at an efficacy estimate (and each step's)."""
    probe = _at(p, eff, balance)
    steps = [
        pl.sigmoid(
            pl._logit(
                probe,
                s,
                "standard",
                eff,
                probe.obs_safety or balance.pharma.safety.mean,
                balance,
                data,
            )
        )
        for s in remaining(p)
    ]
    if p.status != "marketed":
        ab = balance.pharma.approval
        ind = pd.indication(data, p.indication)
        x = pl.logit(pd.area(data, p.area).transitions.submission)
        x += ab.efficacy_weight * (eff - ind.soc) / balance.pharma.efficacy.sd
        steps.append(pl.sigmoid(x))
    c = 1.0
    for s in steps:
        c *= s
    return c, steps


def _at(p: Programme, eff: float, balance: Balance) -> Programme:
    """A copy carrying only public values (the estimate in place of the hidden ones)."""
    from dataclasses import replace

    return replace(p, efficacy=eff, safety=p.obs_safety or balance.pharma.safety.mean)


def peak_cents(
    p: Programme, eff: float, balance: Balance, data: GameData, state: GameState | None = None
) -> float:
    """Game cents a year at peak: every region's treated patients at the estimate's share."""
    db = balance.pharma.demand
    ind = pd.indication(data, p.indication)
    w = dmath.exp(db.efficacy_weight * (eff - ind.soc))
    share = w / (ind.brands + w)
    mod = pd.modality(data, p.modality)
    total = 0.0
    turn = max(p.due_turn, p.start_turn)
    for region in data.region_keys:
        lvl = (
            1.0
            if state is None
            else ceilings.level(state, pd.area(data, ind.area).category, region)
        )
        n = pd.treated(data, ind, region, turn, lvl) * share
        price = pd.net_price(data, ind, round(ind.price_year * pd.CENTS), region) * pd.CENTS
        # money-exact: estimate: a float estimate compared or ranked, never posted
        total += n * price * (1 - mod.cmo_share)
    return total * balance.pharma.scale


def explain(
    p: Programme, balance: Balance, data: GameData, state: GameState | None = None
) -> Value:
    lo, hi = pl.estimate_range(p, balance)
    stages = remaining(p)
    months = sum(pl.stage_months(p, s, "standard", balance, data) for s in stages)
    months += round(sum(pd.review_def(data, pd.us_regulator(data).key).standard_months) / 2)
    years = months / pd.MONTHS
    rate = balance.pharma.discount_rate
    disc = 1 / dmath.pow(1 + rate, years)
    cost_left = 0
    for s in stages:
        n = pl.stage_patients(s, "standard", data) if s in TRIALS else 0
        cost_left += pl.stage_cost_cents(
            p, s, n, pl.stage_months(p, s, "standard", balance, data), balance, data
        )
    out: list[tuple[float, float, float]] = []
    for eff in (lo, hi):
        c, steps = _chance(p, eff, balance, data)
        peak = peak_cents(p, eff, balance, data, state)
        pv = 0.0
        for y in range(balance.pharma.demand.horizon_years):
            ramp = 1 - dmath.exp(-(y + 1) * pd.MONTHS / balance.pharma.demand.ramp_months)
            pv += peak * ramp / dmath.pow(1 + rate, y + 1)
        reach = 1.0
        spend = 0.0
        for s, step in zip(stages, steps, strict=False):
            n = pl.stage_patients(s, "standard", data) if s in TRIALS else 0
            # money-exact: estimate: rNPV, shown as a range, never posted
            spend += reach * pl.stage_cost_cents(
                p, s, n, pl.stage_months(p, s, "standard", balance, data), balance, data
            )
            reach *= step
        out.append((c, c * pv * disc - spend, peak))
    (c_lo, v_lo, pk_lo), (c_hi, v_hi, pk_hi) = out
    return Value(
        chance_lo=min(c_lo, c_hi),
        chance_hi=max(c_lo, c_hi),
        rnpv_lo_cents=round(min(v_lo, v_hi)),
        rnpv_hi_cents=round(max(v_lo, v_hi)),
        peak_lo_cents=round(min(pk_lo, pk_hi)),
        peak_hi_cents=round(max(pk_lo, pk_hi)),
        cost_left_cents=cost_left,
        years_to_launch=years,
    )
