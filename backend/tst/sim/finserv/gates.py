"""Where the player's finance lines may win customers (docs/formulas.md 64.1-64.3), read before the
markets through M31's `Effects`, for the player's own lines only (rivals' lines follow the engine
and, to 2025, the history):

- **Banking:** a line wins accounts in a region only where its company's bank is chartered or a
  partner bank holds its deposits, and not while the regulator restricts the bank; elsewhere its
  appeal is 0 (existing accounts churn away).
- **Payments:** a line sells card programmes (`pay_networks`) only where its company runs a
  network, at appeal x clamp((acceptance / acceptance_ref) ** acceptance_k, appeal_range) (the
  two-sided effect); merchant acquiring (`pay_merchants`) needs nothing.
- **Insurance:** a line writes policies only where its insurer holds an active licence and its own
  funds cover the solvency rules (otherwise no new business: appeal 0).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.finserv import insurance
from tst.sim.platforms.phase import NO_EFFECTS, Effects
from tst.sim.products.models import SELLING
from tst.sim.state import GameState

OFF: Final = 0.0  # tunable-exempt: a closed market's appeal multiplier
NETWORKS: Final = "pay_networks"


def network_appeal(acceptance: float, balance: Balance) -> float:
    pb = balance.finserv.payments
    floor = 1e-6  # tunable-exempt: acceptance's floor (pow of 0)
    raw = dmath.pow(max(acceptance, floor) / pb.acceptance_ref, pb.acceptance_k)
    return min(pb.appeal_range.hi, max(pb.appeal_range.lo, raw))


def effects(
    base: Effects | None, state: GameState, balance: Balance, data: GameData
) -> Effects | None:
    fb = balance.finserv
    players = {c.id for c in state.companies if c.is_player}
    home = home_region_of(state, balance, data)
    appeal: dict[tuple[int, str], float] = {}
    seg_appeal: dict[tuple[int, str, str], float] = {}
    fs = state.finserv
    for p in state.products:
        if (
            p.company_id not in players
            or p.status not in SELLING
            or p.category not in fb.categories
        ):
            continue
        regions = {home, *(r.region for r in state.regional_segments_of(p.id))}
        for region in sorted(regions):
            key = (p.id, "" if region == home else region)
            if p.category == fb.banking_category:
                bank = fs.bank_in(p.company_id, region)
                live = bank is not None and bank.status in ("chartered", "partner")
                if not live or (bank is not None and bank.restricted):
                    appeal[key] = OFF
                    if region == home:
                        appeal[(p.id, region)] = OFF
            elif p.category == fb.payments_category:
                net = fs.network_in(p.company_id, region)
                k3 = (p.id, "" if region == home else region, NETWORKS)
                seg_appeal[k3] = OFF if net is None else network_appeal(net.acceptance, balance)
                if region == home:
                    seg_appeal[(p.id, region, NETWORKS)] = seg_appeal[k3]
            else:
                ins = fs.insurer_of(p.company_id)
                ok = (
                    ins is not None
                    and ins.licensed(region)
                    and insurance.solvent(state, ins, balance, data)
                )
                if not ok:
                    appeal[key] = OFF
                    if region == home:
                        appeal[(p.id, region)] = OFF
    if not appeal and not seg_appeal:
        return base
    out = base if base is not None else NO_EFFECTS
    merged_appeal = dict(out.appeal_mult)
    for k, v in appeal.items():
        merged_appeal[k] = merged_appeal.get(k, 1.0) * v
    merged_seg = dict(out.segment_appeal)
    for k3, v in seg_appeal.items():
        merged_seg[k3] = merged_seg.get(k3, 1.0) * v
    return replace(out, appeal_mult=merged_appeal, segment_appeal=merged_seg)
