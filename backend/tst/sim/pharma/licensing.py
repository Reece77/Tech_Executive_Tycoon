"""Licensing and partnering (docs/formulas.md 55.5) and the AI platform licence (55.2).

- **Assets for licence:** each January, once the player's group has come to pharma (data.engaged),
  `rivals.assets_a_year` biotech programmes are listed to the next January (stream pharma (6,
  year, k): indication, modality, stage, hidden efficacy and safety from the same prior as a new
  molecule, and for a clinical asset its past readouts' observed efficacy). Terms are
  pharma.yaml's by stage, at pharma.scale.
- **In-license:** pay the upfront; milestones in three equal parts on reaching Phase II, Phase III
  and approval; royalties on sales. **Acquire:** (upfront + milestones) x `acquire_mult` at once,
  no royalty. Both post to research and development (acquired in-process R&D).
- **Out-license** a programme to a rival at its stage's terms: the rival pays upfront and
  milestones and then runs the programme (pipeline's rival step), paying royalties on its sales.
- **Co-develop** with a rival: it pays half the upfront and its share of every stage's cost
  (pipeline) and takes its share of sales.
- **AI platform licence** (55.2): a rival pays `ai.platform_fee_cents` a month for
  `ai.platform_months`."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, LICENSE_REVENUE, RESEARCH, ROYALTIES, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import times
from tst.sim.pharma import data as pd
from tst.sim.pharma import draws
from tst.sim.pharma import pipeline as pl
from tst.sim.pharma.config import MODALITIES, STAGES, TRIALS
from tst.sim.pharma.models import Asset, Deal, DrugMonth, Programme, ProgrammeStatus
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

MILESTONES: Final = 3  # tunable-exempt: paid at Phase II, Phase III and approval
BIOTECH: Final = "a biotech"  # tunable-exempt: an outside counterparty's name


def terms_cents(stage: str, balance: Balance, data: GameData) -> tuple[int, int, float]:
    t = pd.file(data).licensing.at(stage)
    return pd.cents(t.upfront, balance), pd.cents(t.milestones, balance), t.royalty


def january(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """This January's assets for licence (last year's lapse)."""
    turn = state.turn
    if turn % pd.MONTHS != 0 or not pd.engaged(state, data):
        return state
    year = pd.year_of(turn)
    rb = balance.pharma.rivals
    stages = sorted(rb.asset_stages)
    weights = [rb.asset_stages[s] for s in stages]
    total = sum(weights)
    inds = pd.file(data).indications
    rows = [a for a in state.pharma_assets if a.taken_by is not None]
    next_id = max((a.id for a in state.pharma_assets), default=0) + 1
    for k in range(rb.assets_a_year):
        g = draws.gen(rng, turn, draws.ASSETS, year, k)
        ind = inds[int(g.integers(len(inds)))]
        modality = MODALITIES[int(g.integers(len(MODALITIES)))]
        u = float(g.random()) * total
        stage = stages[-1]
        for s, w in zip(stages, weights, strict=True):
            if u < w:
                stage = s
                break
            u -= w
        eff, saf = pl.draw_molecule(
            turn, rng, draws.ASSETS, (year, k, 1), ai=False, lead=0.0, balance=balance
        )
        n = sum(1 for t in TRIALS if STAGES.index(t) < STAGES.index(stage))
        obs = eff
        if n:
            noise = balance.pharma.readout.noise[TRIALS[n - 1]]
            obs = pl.clamp01(eff + noise * float(g.standard_normal()))
        up, ms, royalty = terms_cents(stage, balance, data)
        rows.append(
            Asset(
                id=next_id,
                name=f"BT-{year % 100:02d}{k + 1:02d}",
                indication=ind.key,
                area=ind.area,
                modality=modality,  # type: ignore[arg-type]
                stage=stage,  # type: ignore[arg-type]
                efficacy=eff,
                safety=saf,
                obs_n=n,
                obs_eff=obs if n else 0.0,
                upfront_cents=up,
                milestones_cents=ms,
                royalty=royalty,
                listed_turn=turn,
                until_turn=turn + pd.MONTHS,
            )
        )
        next_id += 1
    return replace(state, pharma_assets=tuple(rows))


def _deal_id(state: GameState) -> int:
    return max((d.id for d in state.pharma_deals), default=0) + 1


def take_asset(
    state: GameState,
    company_id: int,
    asset_id: int,
    acquire: bool,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    from tst.sim.errors import PharmaRuleError

    a = next((x for x in state.pharma_assets if x.id == asset_id), None)
    if a is None or a.taken_by is not None or state.turn >= a.until_turn:
        raise PharmaRuleError(f"asset {asset_id} is not available")
    pid = pl.next_id(state)
    status: ProgrammeStatus = "ready" if a.stage != "discovery" else "active"
    p = Programme(
        id=pid,
        company_id=company_id,
        name=a.name,
        indication=a.indication,
        area=a.area,
        modality=a.modality,
        stage=a.stage,
        start_turn=state.turn,
        due_turn=state.turn,
        efficacy=a.efficacy,
        safety=a.safety,
        status=status,
        origin="acquire" if acquire else "in_license",
        obs_n=a.obs_n,
        obs_eff=a.obs_eff,
        obs_safety=balance.pharma.safety.mean if a.obs_n else 0.0,
        patent_turn=state.turn if a.stage != "discovery" else None,
        ind_turn=state.turn if a.stage in ("phase2", "phase3") else None,
    )
    mult = pd.file(data).licensing.acquire_mult
    upfront = times(a.upfront_cents + a.milestones_cents, mult) if acquire else a.upfront_cents
    deal = Deal(
        id=_deal_id(state),
        kind="acquire" if acquire else "in_license",
        company_id=company_id,
        counterparty_id=None,
        counterparty=BIOTECH,
        turn=state.turn,
        programme_id=pid,
        upfront_cents=upfront,
        milestones_cents=0 if acquire else a.milestones_cents,
        royalty=0.0 if acquire else a.royalty,
    )
    state = replace(
        state,
        pharma_programmes=(*state.pharma_programmes, p),
        pharma_assets=tuple(
            replace(x, taken_by=company_id) if x.id == a.id else x for x in state.pharma_assets
        ),
        pharma_deals=(*state.pharma_deals, deal),
    )
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=company_id,
        memo=f"{'Acquired' if acquire else 'In-licensed'} {a.name}",
        debit=RESEARCH,
        credit=CASH,
        amount=upfront,
    )
    log = inbox_item(
        state.turn,
        company_id,
        "pharma_in_licensed",
        link_kind="pharma",
        link_id=pid,
        name=a.name,
    )
    return state, [entry], [log]


def out_license(
    state: GameState,
    p: Programme,
    rival_id: int,
    co_develop: bool,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """A rival takes the programme (out-licence) or shares it (co-development)."""
    from tst.sim.errors import PharmaRuleError

    rival = state.company(rival_id)
    if rival.is_player or pd.file(data).rival(rival.name) is None:
        raise PharmaRuleError("license to one of the pharmaceutical rivals")
    if p.status in ("stopped", "withdrawn", "out") or p.partner_id is not None:
        raise PharmaRuleError(f"{p.name} cannot be licensed now")
    stage = "approved" if p.status == "marketed" else p.stage
    up, ms, royalty = terms_cents(stage, balance, data)
    share = balance.pharma.co_develop_share if co_develop else 0.0
    if co_develop:
        up = round(up * share)
        ms = 0
        royalty = 0.0
    deal = Deal(
        id=_deal_id(state),
        kind="co_develop" if co_develop else "out_license",
        company_id=p.company_id,
        counterparty_id=rival_id,
        counterparty=rival.name,
        turn=state.turn,
        programme_id=p.id,
        upfront_cents=up,
        milestones_cents=ms,
        royalty=royalty,
        share=share,
    )
    player = p.company_id
    if co_develop:
        p2 = replace(p, partner_id=rival_id, partner_share=share)
    else:
        p2 = replace(p, company_id=rival_id)
    state = pl.with_programme(replace(state, pharma_deals=(*state.pharma_deals, deal)), p2)
    entries = _pay(state.turn, rival_id, player, up, f"{deal.kind.replace('_', ' ')}: {p.name}")
    log = inbox_item(
        state.turn,
        player,
        "pharma_out_licensed",
        link_kind="pharma",
        link_id=p.id,
        name=p.name,
        partner=rival.name,
    )
    return state, entries, [log]


def platform(
    state: GameState, company_id: int, rival_id: int, balance: Balance, data: GameData
) -> GameState:
    from tst.sim.errors import PharmaRuleError

    rival = state.company(rival_id)
    if rival.is_player or pd.file(data).rival(rival.name) is None:
        raise PharmaRuleError("license the platform to one of the pharmaceutical rivals")
    if not pl.ai_ready(state, company_id, balance, data):
        raise PharmaRuleError("an AI discovery platform needs AI discovery")
    if any(
        d.kind == "platform" and d.counterparty_id == rival_id and (d.until_turn or 0) > state.turn
        for d in state.pharma_deals
    ):
        raise PharmaRuleError(f"{rival.name} already licenses the platform")
    ab = balance.pharma.ai
    deal = Deal(
        id=_deal_id(state),
        kind="platform",
        company_id=company_id,
        counterparty_id=rival_id,
        counterparty=rival.name,
        turn=state.turn,
        # money-exact: rate: real cents to dollars, scaled and rounded once
        fee_cents=pd.cents(ab.platform_fee_cents / pd.CENTS, balance),
        until_turn=state.turn + ab.platform_months,
    )
    return replace(state, pharma_deals=(*state.pharma_deals, deal))


def _pay(turn: int, payer: int, payee: int | None, amount: int, memo: str) -> list[LedgerEntry]:
    """A licence payment: the payer's R&D (or royalties) to the payee's licence revenue."""
    if amount <= 0:
        return []
    out = [
        LedgerEntry.transfer(
            turn=turn, company_id=payer, memo=memo, debit=RESEARCH, credit=CASH, amount=amount
        )
    ]
    if payee is not None:
        out.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=payee,
                memo=memo,
                debit=CASH,
                credit=LICENSE_REVENUE,
                amount=amount,
            )
        )
    return out


def _royalty(turn: int, payer: int, payee: int | None, amount: int, memo: str) -> list[LedgerEntry]:
    if amount <= 0:
        return []
    out = [
        LedgerEntry.transfer(
            turn=turn, company_id=payer, memo=memo, debit=ROYALTIES, credit=CASH, amount=amount
        )
    ]
    if payee is not None:
        out.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=payee,
                memo=memo,
                debit=CASH,
                credit=LICENSE_REVENUE,
                amount=amount,
            )
        )
    return out


def _reached(state: GameState, p: Programme) -> int:
    """Milestones reached: Phase II and Phase III started (or passed), and approval."""
    order = STAGES.index(p.stage)
    n = int(order >= STAGES.index("phase2")) + int(order >= STAGES.index("phase3"))
    n += int(p.approved_turn is not None)
    return min(MILESTONES, n)


def month(
    state: GameState, months: tuple[DrugMonth, ...], balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Milestones, royalties, co-development shares of sales and platform fees."""
    del balance, data
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    turn = state.turn
    revenue = {m.programme_id: m.revenue_cents for m in months if m.turn == turn}
    deals = list(state.pharma_deals)
    for i, d in enumerate(deals):
        p = next((q for q in state.pharma_programmes if q.id == d.programme_id), None)
        if d.kind == "platform":
            if d.until_turn is not None and turn < d.until_turn and d.counterparty_id is not None:
                entries += _pay(
                    turn, d.counterparty_id, d.company_id, d.fee_cents, "AI platform licence"
                )
            continue
        if p is None:
            continue
        reached = _reached(state, p)
        if d.milestones_cents > 0 and reached > d.milestones_paid:
            each = d.milestones_cents // MILESTONES
            amount = each * (reached - d.milestones_paid)
            if d.kind == "in_license":
                entries += _pay(turn, d.company_id, None, amount, f"Milestone: {p.name}")
            elif d.kind == "out_license" and d.counterparty_id is not None:
                entries += _pay(
                    turn, d.counterparty_id, d.company_id, amount, f"Milestone: {p.name}"
                )
            deals[i] = replace(d, milestones_paid=reached)
        sales = revenue.get(p.id, 0)
        if sales <= 0:
            continue
        if d.kind == "in_license":
            entries += _royalty(
                turn, d.company_id, None, times(sales, d.royalty), f"Royalty: {p.name}"
            )
        elif d.kind == "out_license" and d.counterparty_id is not None:
            entries += _royalty(
                turn,
                d.counterparty_id,
                d.company_id,
                times(sales, d.royalty),
                f"Royalty: {p.name}",
            )
        elif d.kind == "co_develop" and d.counterparty_id is not None:
            entries += _royalty(
                turn,
                p.company_id,
                d.counterparty_id,
                times(sales, d.share),
                f"Partner's share: {p.name}",
            )
    return replace(state, pharma_deals=tuple(deals)), entries, logs
