"""Chinese chipmakers under export rules (docs/formulas.md 41.5).

A Chinese foundry's research lag after 2025 is a number of generations behind the leading
node. Each month it grows by the generations the leader gained and shrinks by `china_catchup`
/ 12 while an equipment control binds (a biting export rule on `china_control_goods` to China,
to every destination, or to the foundry by name), or by `china_free_pace` / 12 without one (a
follower buying tools on the open market). When its generation (the leader's less the lag)
reaches a node it has not, it reaches that node that month, whatever nodes.yaml's EUV gate
says: under controls by its own state-funded programme, without them with bought tools. While
controls bind it spends `china_subsidy` x its plant's capex a year, as research funded by an
equal state grant (both in its books, neutral to its cash).

Through December 2025 nothing changes (the history's dates; 41.8 target 1); the reach after
2025 replaces the seeded `lag` for these foundries (tst.sim.fabs.market.timeline).
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.fabs import nodes as nd
from tst.sim.geopolitics import rules as gr
from tst.sim.geopolitics.config import EntityTarget
from tst.sim.ledger import OTHER_INCOME, RESEARCH, LedgerEntry, LedgerLine
from tst.sim.state import GameState
from tst.sim.world import query as wq
from tst.sim.world.models import ChinaLag
from tst.sim.world.news import Item

MONTHS: Final = 12  # tunable-exempt: calendar
EPS: Final = 1e-9  # tunable-exempt: float tolerance on a whole generation
CHINA_TARGETS: Final = ("china", "all")  # tunable-exempt: destinations that cover China


def binding(state: GameState, data: GameData, balance: Balance, foundry_name: str) -> bool:
    """Whether an equipment control binds the foundry this month."""
    if data.controls is None:
        return False
    goods = set(balance.world.china_control_goods)
    for active in gr.biting(state, data):
        if not goods & set(active.rule.goods):
            continue
        for to in active.rule.to:
            if isinstance(to, EntityTarget):
                if to.entity.casefold() == foundry_name.casefold():
                    return True
            elif to in CHINA_TARGETS:
                return True
    return False


def china_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[Item]]:
    if not state.china_lags or data.nodes is None:
        return state, [], []
    wb = balance.world
    turn = state.turn
    base = nd.timeline(state.save_meta.master_seed, data.nodes, balance.fab)
    lead_now = base.generation(base.leading(turn))
    lead_before = base.generation(base.leading(turn - 1))
    entries: list[LedgerEntry] = []
    news: list[Item] = []
    out: list[ChinaLag] = []
    for lag in state.china_lags:
        rec = wq.chain_by_key(state, lag.foundry)
        if rec is None or not state.company(rec.company_id).alive:
            out.append(lag)
            continue
        name = state.company(rec.company_id).name
        binds = binding(state, data, balance, name)
        pace = wb.china_catchup if binds else wb.china_free_pace
        behind = max(0.0, lag.behind + (lead_now - lead_before) - pace / MONTHS)
        reached = dict(lag.reached)
        own = {k for k in base.keys if base.foundry_has(lag.foundry, k, nd.HISTORY_END)}
        best = max((base.generation(k) for k in (*own, *reached)), default=0)
        can = math.floor(lead_now - behind + EPS)
        for g in range(best + 1, min(can, len(base.keys) - 1) + 1):
            node = base.keys[g]
            if base.arrival[node] > turn:  # never ahead of the first to a node
                break
            reached[node] = turn
            news.append(
                Item(
                    "china",
                    f"{name} reaches {node} {'under export controls' if binds else ''}".strip(),
                    rec.company_id,
                    region=rec.region,
                    good="foundry_wafer",
                )
            )
        if binds:
            plant = sum(
                f.capex_cents for f in state.world_facilities if f.company_id == rec.company_id
            )
            spend = round(plant * wb.china_subsidy / MONTHS)
            if spend > 0:
                entries.append(
                    LedgerEntry(
                        turn,
                        rec.company_id,
                        f"{name}: state-funded catch-up research (41.5)",
                        (LedgerLine(RESEARCH, spend), LedgerLine(OTHER_INCOME, -spend)),
                    )
                )
        out.append(
            replace(
                lag,
                turn=turn,
                behind=behind,
                reached=tuple(sorted(reached.items(), key=lambda kv: kv[1])),
                binding=binds,
            )
        )
    state = replace(state, china_lags=tuple(out))
    return state, entries, news


def lag_generations(state: GameState, foundry: str) -> float | None:
    lag = next((x for x in state.china_lags if x.foundry == foundry), None)
    return None if lag is None else lag.behind
