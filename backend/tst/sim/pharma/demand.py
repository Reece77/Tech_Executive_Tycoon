"""Revenue, pricing and the cliff (docs/formulas.md 55.4), and supply (55.5).

For an indication and region each month, every marketed molecule m has a weight

    w_m = exp(e x (efficacy - soc)) x exp(-s x (1 - safety)) x ramp(months since launch there)
          x (floor + (1 - floor) x min(1, support)) x (reference list / list)^elasticity (US)

against the standard of care's weight (the indication's `brands`), so its patients are

    P_m = treated x w_m / (brands + sum of w) x access (the share of the region it is approved
          in) x (1, or medical.coverage.no_coverage_share without HTA coverage)

and after exclusivity ends there the brand keeps `retained(months)` of them (the modality's
erosion); the rest buy generics or biosimilars at the erosion's `price_share` of the brand's net
price, sold by the generic makers in proportion to their size. A brand's revenue is its patients x
its net price there (the US list less the area's gross-to-net, x the region's price index; the
Medicare share of US patients at the IRA's negotiated price once selected) x pharma.scale / 12.
Patients are real people; money is the game's.

Supply: own plants (by kind: API for small molecules, biologics otherwise) make what they can at
the modality's `cogs_share`; the chosen contract manufacturer makes the rest at `cmo_share`, up to
its capacity. Commercial support costs `support x the area's sales_cents x scale` a month in each
region a drug sells in. Rivals' key drugs lose the player's share of their indication
(rivals.py)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, COGS, DRUG_SALES, MARKETING, LedgerEntry
from tst.sim.money import times
from tst.sim.pharma import approval, ceilings
from tst.sim.pharma import data as pd
from tst.sim.pharma.models import Drug, DrugMonth, IraPick, Programme
from tst.sim.state import GameState

NOT_BLOCKED: Final = -1  # tunable-exempt: DrugRegion.blocked_until's default (no recall)

KINDS: Final = {"small_molecule": "api", "biologic": "biologics", "cell_and_gene": "biologics"}
THOUSAND: Final = 1000  # tunable-exempt: capacities are thousand patient-years


@dataclass(slots=True)
class Month:
    """What demand computed this month: revenue a company (for MRR), patients by molecule and
    world share by indication (rivals read it), and generic revenue by indication."""

    revenue: dict[int, int] = field(default_factory=dict)
    patients: dict[int, float] = field(default_factory=dict)
    share: dict[str, float] = field(default_factory=dict)  # the modelled molecules' world share
    generic_cents: int = 0


def marketed(state: GameState) -> list[Programme]:
    return [p for p in state.pharma_programmes if p.status == "marketed"]


def drug_of(state: GameState, programme_id: int) -> Drug | None:
    return next((d for d in state.pharma_drugs if d.programme_id == programme_id), None)


def launched_in(state: GameState, p: Programme, region: str) -> int | None:
    return min(
        (
            a.from_turn
            for a in state.pharma_authorisations
            if a.programme_id == p.id and a.region == region and a.from_turn <= state.turn
        ),
        default=None,
    )


def weight(
    state: GameState, p: Programme, drug: Drug, region: str, balance: Balance, data: GameData
) -> float:
    """w_m before access (55.4); 0 before launch in the region or while a recall stops it."""
    start = launched_in(state, p, region)
    # blocked_until -1 is "never recalled" (M50: a 2008 game's months are below it)
    if start is None or (drug.blocked_until != NOT_BLOCKED and state.turn < drug.blocked_until):
        return 0.0
    db = balance.pharma.demand
    ind = pd.indication(data, p.indication)
    w = dmath.exp(db.efficacy_weight * (p.efficacy - ind.soc))
    w *= dmath.exp(-db.safety_weight * (1 - p.safety))
    w *= 1 - dmath.exp(-(state.turn - start + 1) / db.ramp_months)
    w *= db.support_floor + (1 - db.support_floor) * min(1.0, drug.support)
    if region == pd.US_REGION:
        ref = ind.price_year * pd.CENTS
        # money-exact: ratio: a price against its reference
        w *= dmath.pow(ref / max(1, drug.list_cents), db.price_elasticity)
    return w


def ira_discount(state: GameState, programme_id: int) -> float:
    year = pd.year_of(state.turn)
    picks = [i for i in state.pharma_ira if i.programme_id == programme_id and i.year <= year]
    return max((i.discount for i in picks), default=0.0)


def net_cents_year(
    state: GameState, p: Programme, drug: Drug, region: str, data: GameData
) -> float:
    """Real cents a patient-year the brand nets in the region (the IRA in the US)."""
    ind = pd.indication(data, p.indication)
    net = pd.net_price(data, ind, drug.list_cents, region) * pd.CENTS
    if region == pd.US_REGION:
        net *= 1 - ind.medicare_share * ira_discount(state, p.id)
    return net


def loe_months(state: GameState, p: Programme, region: str, data: GameData) -> float:
    """Months since exclusivity ended in the region (negative before)."""
    loe = pd.loe_turn(state, p, region, data)
    if loe is None:
        return -1.0
    return float(state.turn - loe)


def _capacity(state: GameState, company_id: int, kind: str, data: GameData) -> float:
    """Own plants' real patients of a kind (a patient-year a year supplies one patient)."""
    cap = sum(
        pd.file(data).plant(pl.kind).capacity
        for pl in state.pharma_plants
        if pl.company_id == company_id
        and pl.kind == kind
        and not pl.closed
        and pl.ready_turn <= state.turn
    )
    return cap * THOUSAND


def _cmo(state: GameState, company_id: int, kind: str, data: GameData) -> str:
    chosen = next(
        (
            s.cmo
            for s in state.pharma_supply
            if s.company_id == company_id and s.kind == kind and s.ended_turn is None
        ),
        None,
    )
    if chosen is not None:
        return chosen
    return next(c.name for c in pd.file(data).cmos if kind in c.kinds)


def cmo_capacity(data: GameData, name: str, kind: str) -> float:
    cmo = next(c for c in pd.file(data).cmos if c.name == name)
    return sum(c for k, c in cmo.capacity.items() if k == kind) * THOUSAND


def month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], Month]:
    """Every marketed drug's month: patients, revenue, cost of goods and commercial support."""
    out = Month()
    entries: list[LedgerEntry] = []
    drugs = marketed(state)
    if not drugs:
        return state, entries, out
    turn = state.turn
    scale = balance.pharma.scale
    no_cover = balance.medical.coverage.no_coverage_share
    by_ind: dict[str, list[Programme]] = {}
    for p in drugs:
        by_ind.setdefault(p.indication, []).append(p)
    brand: dict[int, dict[str, float]] = {}  # programme -> region -> patients
    generic_cents = 0.0
    world: dict[str, float] = {}
    for key in sorted(by_ind):
        ind = pd.indication(data, key)
        progs = sorted(by_ind[key], key=lambda q: q.id)
        for region in data.region_keys:
            lvl = ceilings.level(state, pd.area(data, ind.area).category, region)
            treated = pd.treated(data, ind, region, turn, lvl)
            world[key] = world.get(key, 0.0) + treated
            ws = {}
            for p in progs:
                drug = drug_of(state, p.id)
                ws[p.id] = weight(state, p, drug, region, balance, data) if drug else 0.0
            total = ind.brands + sum(ws.values())
            for p in progs:
                if ws[p.id] <= 0:
                    continue
                drug = drug_of(state, p.id)
                assert drug is not None
                n = treated * ws[p.id] / total * pd.access(state, p.id, region, data)
                if not approval.covered(state, p.id, region, data):
                    n *= no_cover
                out.share[key] = out.share.get(key, 0.0) + n
                m = loe_months(state, p, region, data)
                kept = pd.retained(pd.modality(data, p.modality), m) if m >= 0 else 1.0
                lost = n * (1 - kept)
                if lost > 0:
                    e = pd.modality(data, p.modality).erosion
                    generic_cents += (
                        # money-exact: rate: float cents accumulated, rounded once where posted
                        lost * net_cents_year(state, p, drug, region, data) * e.price_share
                    )
                brand.setdefault(p.id, {})[region] = n * kept
    for key, n in out.share.items():
        out.share[key] = n / world[key] if world.get(key) else 0.0
    # supply, revenue and costs by company
    by_company: dict[int, list[Programme]] = {}
    for p in drugs:
        by_company.setdefault(p.company_id, []).append(p)
    months: list[DrugMonth] = []
    for cid in sorted(by_company):
        progs = sorted(by_company[cid], key=lambda q: q.id)
        for kind in ("api", "biologics"):
            mine = [p for p in progs if KINDS[p.modality] == kind and p.id in brand]
            if not mine:
                continue
            need = sum(sum(brand[p.id].values()) for p in mine)
            own = _capacity(state, cid, kind, data)
            cmo = cmo_capacity(data, _cmo(state, cid, kind, data), kind)
            made = min(need, own + cmo)
            cut = made / need if need > 0 else 1.0
            own_part = min(own, made) / made if made > 0 else 0.0
            for p in mine:
                drug = drug_of(state, p.id)
                assert drug is not None
                mod = pd.modality(data, p.modality)
                cents = 0.0
                us = 0.0
                patients = 0.0
                for region, n in sorted(brand[p.id].items()):
                    n *= cut
                    patients += n
                    # money-exact: rate: float cents accumulated, rounded once where posted
                    c = n * net_cents_year(state, p, drug, region, data) * scale / pd.MONTHS
                    cents += c
                    if region == pd.US_REGION:
                        us += c
                revenue = round(cents)
                out.patients[p.id] = patients
                if revenue > 0:
                    out.revenue[cid] = out.revenue.get(cid, 0) + revenue
                    entries.append(
                        LedgerEntry.transfer(
                            turn=turn,
                            company_id=cid,
                            memo=f"{p.name}: drug sales",
                            debit=CASH,
                            credit=DRUG_SALES,
                            amount=revenue,
                        )
                    )
                    share = own_part * mod.cogs_share + (1 - own_part) * mod.cmo_share
                    cogs = times(revenue, share)
                    if cogs > 0:
                        entries.append(
                            LedgerEntry.transfer(
                                turn=turn,
                                company_id=cid,
                                memo=f"{p.name}: cost of goods",
                                debit=COGS,
                                credit=CASH,
                                amount=cogs,
                            )
                        )
                support = _support_cents(state, p, drug, balance, data)
                if support > 0:
                    entries.append(
                        LedgerEntry.transfer(
                            turn=turn,
                            company_id=cid,
                            memo=f"{p.name}: medical affairs and sales",
                            debit=MARKETING,
                            credit=CASH,
                            amount=support,
                        )
                    )
                generic = any(loe_months(state, p, r, data) >= 0 for r in brand[p.id])
                months.append(DrugMonth(turn, p.id, cid, patients, revenue, round(us), generic))
    keep = turn - balance.pharma.history_months
    recent = tuple(m for m in state.pharma_months if m.turn > keep)
    state = replace(state, pharma_months=(*recent, *months))
    # money-exact: rate: the month's pool, rounded once here
    out.generic_cents = round(generic_cents * scale / pd.MONTHS)
    return state, entries, out


def _support_cents(
    state: GameState, p: Programme, drug: Drug, balance: Balance, data: GameData
) -> int:
    if drug.support <= 0:
        return 0
    regions = sum(1 for r in data.region_keys if pd.access(state, p.id, r, data) > 0)
    # money-exact: rate: real cents a month, scaled and rounded once below
    real = drug.support * pd.area(data, p.area).sales_cents * regions
    return round(real * balance.pharma.scale)


def us_revenue_year(state: GameState, programme_id: int) -> int:
    """The drug's US revenue over the last 12 months (game cents): the IRA's ranking."""
    return sum(
        m.us_cents
        for m in state.pharma_months
        if m.programme_id == programme_id and m.turn > state.turn - pd.MONTHS
    )


def with_ira(state: GameState, picks: list[IraPick]) -> GameState:
    return replace(state, pharma_ira=(*state.pharma_ira, *picks))
