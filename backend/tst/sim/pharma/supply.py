"""Manufacturing, quality, inspections and recalls (docs/formulas.md 55.5; 50.5 reused).

Own plants: an API plant or a biologics plant costs its capex (at pharma.scale) to PP&E when
ordered, makes nothing until ready, then runs at `fixed_month` x the quality level's
`quality_cost_share` (the part above standard to quality and regulatory) and depreciates over
`depreciation_years`. A company's quality for a kind of drug is the worst of its ready plants of
that kind and its contract manufacturer's.

Inspections and recalls reuse M41's rules and data (medical.yaml's finding shares and quality
multipliers, balance.yaml medical.inspection's consequences): each month a drug regulator that
has approved a company's drug inspects it with `supply.inspection_chance_year` / 12 x its
strictness; a warning letter holds that regulator's decisions, an import ban or consent decree
stops sales in its part, and a consent decree fines a share of the year's drug revenue. Each
marketed drug may be recalled (`supply.recall_chance_year` by quality): a recall costs a share of
a month's revenue and stops shipments for `recall_block_months`."""

from __future__ import annotations

from dataclasses import replace
from typing import Final, Literal

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import (
    ACCUMULATED_DEPRECIATION,
    CASH,
    COGS,
    DEPRECIATION,
    FINES,
    PPE,
    QUALITY_REGULATORY,
    RECALLS,
    LedgerEntry,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.medical import data as md
from tst.sim.medical.config import FINDINGS
from tst.sim.money import exact
from tst.sim.pharma import data as pd
from tst.sim.pharma import draws
from tst.sim.pharma.demand import KINDS
from tst.sim.pharma.models import Finding, Inspection, Plant, Programme, Recall
from tst.sim.regulation import data as rdata
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

type Level = Literal["low", "standard", "high"]
ORDER: Final = ("low", "standard", "high")


def build(
    state: GameState, company_id: int, kind: str, region: str, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    from tst.sim.errors import PharmaRuleError

    if region not in data.region_keys:
        raise PharmaRuleError(f"unknown region {region!r}")
    spec = pd.file(data).plant(kind)
    pid = max((p.id for p in state.pharma_plants), default=0) + 1
    capex = pd.cents(spec.capex, balance)
    plant = Plant(
        id=pid,
        company_id=company_id,
        kind=spec.kind,
        region=region,
        ordered_turn=state.turn,
        ready_turn=state.turn + spec.build_months,
        capex_cents=capex,
    )
    state = replace(state, pharma_plants=(*state.pharma_plants, plant))
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=company_id,
        memo=f"{spec.label} ({region})",
        debit=PPE,
        credit=CASH,
        amount=capex,
    )
    log = inbox_item(
        state.turn,
        company_id,
        "pharma_plant_ordered",
        link_kind="pharma",
        link_id=pid,
        plant=spec.label,
        months=spec.build_months,
    )
    return state, [entry], [log]


def level(state: GameState, company_id: int, kind: str, data: GameData) -> Level:
    """The worst quality among the company's ready plants of the kind and its CMO's."""
    from tst.sim.pharma.demand import _cmo

    levels: list[Level] = [
        p.quality
        for p in state.pharma_plants
        if p.company_id == company_id
        and p.kind == kind
        and not p.closed
        and p.ready_turn <= state.turn
    ]
    cmo = next(c for c in pd.file(data).cmos if c.name == _cmo(state, company_id, kind, data))
    levels.append(cmo.quality)
    return min(levels, key=ORDER.index)


def drug_level(state: GameState, p: Programme, data: GameData) -> Level:
    return level(state, p.company_id, KINDS[p.modality], data)


def plant_entries(state: GameState, balance: Balance, data: GameData) -> list[LedgerEntry]:
    entries: list[LedgerEntry] = []
    sb = balance.pharma.supply
    for p in sorted(state.pharma_plants, key=lambda q: q.id):
        if p.closed or state.turn < p.ready_turn:
            continue
        spec = pd.file(data).plant(p.kind)
        base = pd.cents(spec.fixed_month, balance)
        extra = round(base * (exact(sb.quality_cost_share[p.quality]) - 1))
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=p.company_id,
                memo=f"{spec.label}: running",
                debit=COGS,
                credit=CASH,
                amount=base + min(0, extra),
            )
        )
        if extra > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=p.company_id,
                    memo=f"{spec.label}: quality",
                    debit=QUALITY_REGULATORY,
                    credit=CASH,
                    amount=extra,
                )
            )
        dep = p.capex_cents // (sb.depreciation_years * pd.MONTHS)
        if dep > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=p.company_id,
                    memo=f"{spec.label}: depreciation",
                    debit=DEPRECIATION,
                    credit=ACCUMULATED_DEPRECIATION,
                    amount=dep,
                )
            )
    return entries


def _finding(u: float, mult: float, data: GameData) -> Finding:
    out = md.file(data).inspections.outcomes  # M41's finding shares (50.5)
    edge = 0.0
    for f in reversed(FINDINGS):  # the gravest first
        edge += out[f] * mult
        if u < edge:
            return f
    return "none"


def year_revenue(state: GameState, company_id: int) -> int:
    return sum(
        m.revenue_cents
        for m in state.pharma_months
        if m.company_id == company_id and m.turn > state.turn - pd.MONTHS
    )


def month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    entries = plant_entries(state, balance, data)
    logs: list[LogItem] = []
    players = {c.id for c in state.companies if c.is_player}
    marketed = [p for p in state.pharma_programmes if p.status == "marketed"]
    companies = sorted({p.company_id for p in marketed if p.company_id in players})
    sb = balance.pharma.supply
    ib = balance.medical.inspection
    levels = md.file(data).quality.levels
    turn = state.turn
    for cid in companies:
        for i, reg in enumerate(pd.regulators(data)):
            mine = [
                p
                for p in marketed
                if p.company_id == cid and pd.authorised(state, p.id, reg.key, turn)
            ]
            if not mine:
                continue
            g = draws.gen(rng, turn, draws.SUPPLY, draws.INSPECT, cid, i)
            if float(g.random()) >= sb.inspection_chance_year / pd.MONTHS * rdata.strictness(
                reg, turn
            ):
                continue
            worst = min((drug_level(state, p, data) for p in mine), key=ORDER.index)
            finding = _finding(float(g.random()), levels[worst].inspection, data)
            until, fine = turn, 0
            if finding == "warning_letter":
                until = turn + balance.medical.review.warning_hold_months
            elif finding == "import_ban":
                until = turn + ib.import_ban_months
            elif finding == "consent_decree":
                until = turn + ib.consent_decree_months
                fine = round(year_revenue(state, cid) * ib.consent_fine_share)
            iid = max((x.id for x in state.pharma_inspections), default=0) + 1
            rec = Inspection(iid, cid, reg.key, turn, finding, until, fine)
            state = replace(state, pharma_inspections=(*state.pharma_inspections, rec))
            if fine > 0:
                entries.append(
                    LedgerEntry.transfer(
                        turn=turn,
                        company_id=cid,
                        memo=f"Consent decree: {reg.name}",
                        debit=FINES,
                        credit=CASH,
                        amount=fine,
                    )
                )
            logs.append(
                inbox_item(
                    turn,
                    cid,
                    f"pharma_inspection_{finding}",
                    link_kind="pharma",
                    regulator=reg.name,
                    months=max(0, until - turn),
                    fine_cents=fine,
                )
            )
    for p in sorted(marketed, key=lambda q: q.id):
        if p.company_id not in players:
            continue
        g = draws.gen(rng, turn, draws.SUPPLY, draws.RECALL, p.id)
        if float(g.random()) >= sb.recall_chance_year[drug_level(state, p, data)] / pd.MONTHS:
            continue
        last = next(
            (m.revenue_cents for m in reversed(state.pharma_months) if m.programme_id == p.id), 0
        )
        cost = round(last * sb.recall_cost_share)
        block = turn + sb.recall_block_months
        rid = max((r.id for r in state.pharma_recalls), default=0) + 1
        state = replace(
            state, pharma_recalls=(*state.pharma_recalls, Recall(rid, p.id, turn, cost, block))
        )
        state = replace(
            state,
            pharma_drugs=tuple(
                replace(d, blocked_until=block) if d.programme_id == p.id else d
                for d in state.pharma_drugs
            ),
        )
        if cost > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=p.company_id,
                    memo=f"Recall: {p.name}",
                    debit=RECALLS,
                    credit=CASH,
                    amount=cost,
                )
            )
        logs.append(
            inbox_item(
                turn,
                p.company_id,
                "pharma_recall",
                link_kind="pharma",
                link_id=p.id,
                name=p.name,
                months=sb.recall_block_months,
            )
        )
    return state, entries, logs
