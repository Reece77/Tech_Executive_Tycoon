"""Pharmaceutical rivals (docs/formulas.md 55.5): their revenue, costs and pipelines.

**To 2025** a rival's monthly revenue is its reported pharmaceutical revenue (pharma.yaml, linear
between years' mid-points) x pharma.scale / 12, less what the modelled molecules (the player's)
take from its key drugs: a key drug's revenue x the modelled molecules' world share of patients
in its indication. A company without pharma therefore leaves every rival's books as history had
them.

**After 2025** it is the rest of its 2025 portfolio (its revenue less its key drugs), losing
`rivals.rest_decay` a year, plus its key drugs (held at their last year, growing with their
indication, until US exclusivity ends, then the modality's cliff; the IRA's discount on the
Medicare share of US sales from the January the data says), plus its seeded approvals: each
January, Poisson(`approvals_per_b` x last year's revenue in $B) drugs in its focus areas, each
with a lognormal peak reached over `ramp_years` and exclusivity for `exclusivity_years` (stream
pharma (4, company id, year)). Generic makers grow their base and sell generics of every modelled
molecule past its exclusivity, in proportion to their 2025 size.

Costs: `rivals.cost_shares` (generic makers' `generics_cost_shares`) of revenue each month. Rivals
make no product decisions (rivals.holds)."""

from __future__ import annotations

from dataclasses import replace

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, COMMON_EQUITY, DRUG_SALES, LedgerEntry
from tst.sim.pharma import data as pd
from tst.sim.pharma import draws
from tst.sim.pharma.config import AREAS, MODALITIES, PharmaRival, RivalDrug
from tst.sim.pharma.models import SeededDrug
from tst.sim.rng import RngFactory
from tst.sim.state import CompanyState, GameState


def companies(state: GameState, data: GameData) -> dict[int, PharmaRival]:
    """Rival companies with a pharmaceutical business, by company id."""
    if not pd.enabled(data):
        return {}
    pf = pd.file(data)
    out: dict[int, PharmaRival] = {}
    for c in state.rivals():
        r = pf.rival(c.name)
        if r is not None:
            out[c.id] = r
    return out


def holds(state: GameState, company: CompanyState, balance: Balance, data: GameData) -> bool:
    """A pharma rival makes no generic product decisions and never fails (its business is
    pharma.yaml's)."""
    if not pd.enabled(data) or company.is_player:
        return False
    return pd.file(data).rival(company.name) is not None


def _yearly(points: dict[int, float], t: float) -> float:
    return pd.series_at(points, t, 0.0, max(points))


def us_share(data: GameData, area: str) -> float:
    """The US part of an area's sales (patients x price index)."""
    a = pd.area(data, area)
    total = sum(s * pd.price_index(data, r) for r, s in a.region_share.items())
    return a.region_share[pd.US_REGION] * pd.price_index(data, pd.US_REGION) / total


def _ira_factor(d: RivalDrug, t: float, data: GameData) -> float:
    if d.ira_year is None or t < d.ira_year:
        return 1.0
    pf = pd.file(data)
    rnd = next((r for r in pf.ira.rounds if r.year == d.ira_year), pf.ira.rounds[-1])
    ind = pd.indication(data, d.indication)
    return 1 - us_share(data, ind.area) * ind.medicare_share * rnd.discount


def key_drug_b(d: RivalDrug, t: float, data: GameData) -> float:
    """A key drug's revenue a year (real $B) at fractional year t (55.5)."""
    mid = 0.5  # tunable-exempt: a year's value sits at its middle
    if t < d.approved:
        return 0.0
    points = dict(d.revenue)
    first = min(points)
    if d.approved < first:
        points.setdefault(d.approved, 0.0)
    last = max(points)
    mod = pd.modality(data, d.modality)
    if t <= last + mid:
        value = _yearly(points, t)
    else:
        base = points[last]
        months_now = (t - d.loe_us) * pd.MONTHS
        if d.loe_us <= last:
            then = (last + mid - d.loe_us) * pd.MONTHS
            value = base * pd.retained(mod, months_now) / pd.retained(mod, then)
        else:
            g = pd.indication(data, d.indication).growth_after
            grow_to = min(t, float(d.loe_us))
            value = base * dmath.pow(1 + g, grow_to - last - mid)
            if t >= d.loe_us:
                value *= pd.retained(mod, months_now)
    return value * _ira_factor(d, t, data)


def seeded_b(s: SeededDrug, turn: int, balance: Balance, data: GameData) -> float:
    if turn < s.approved_turn:
        return 0.0
    years = (turn - s.approved_turn) / pd.MONTHS
    value = s.peak_cents * min(1.0, years / balance.pharma.rivals.ramp_years)
    if turn >= s.loe_turn:
        value *= pd.retained(pd.modality(data, s.modality), turn - s.loe_turn)
    return value  # game cents a year


def monthly_cents(
    state: GameState,
    company_id: int,
    r: PharmaRival,
    share: dict[str, float],
    generic_pool: float,
    balance: Balance,
    data: GameData,
) -> int:
    """A rival's pharmaceutical revenue this month (game cents)."""
    turn = state.turn
    t = pd.year_frac(turn)
    end = pd.history_end_turn(data)
    scale = balance.pharma.scale
    per_month = pd.BILLION * pd.CENTS * scale / pd.MONTHS
    loss = sum(key_drug_b(d, t, data) * share.get(d.indication, 0.0) for d in r.drugs)
    if turn <= end:
        return round((_yearly(r.revenue, t) - loss) * per_month)
    t_end = pd.year_frac(end)
    rb = balance.pharma.rivals
    years = (turn - end) / pd.MONTHS
    if r.generics:
        base = _yearly(r.revenue, t_end) * dmath.pow(1 + rb.generics_base_growth, years)
        return round(base * per_month + generic_pool * generic_weight(r, data))
    rest = _yearly(r.revenue, t_end) - sum(key_drug_b(d, t_end, data) for d in r.drugs)
    rest = max(0.0, rest) * dmath.pow(1 - rb.rest_decay, years)
    keys = sum(key_drug_b(d, t, data) for d in r.drugs)
    seeded = sum(
        seeded_b(s, turn, balance, data) for s in state.pharma_seeded if s.company_id == company_id
    )
    return round((rest + keys - loss) * per_month + seeded / pd.MONTHS)


def generic_weight(r: PharmaRival, data: GameData) -> float:
    makers = [x for x in pd.file(data).rivals if x.generics]
    total = sum(_yearly(x.revenue, max(x.revenue)) for x in makers)
    return _yearly(r.revenue, max(r.revenue)) / total if total > 0 else 0.0


def rival_generic_pool(state: GameState, balance: Balance, data: GameData) -> float:
    """Game cents this month of generics of rivals' key and seeded drugs past exclusivity
    (after 2025; before, the history's generic makers' revenue already holds them)."""
    turn = state.turn
    if turn <= pd.history_end_turn(data):
        return 0.0
    t = pd.year_frac(turn)
    per_month = pd.BILLION * pd.CENTS * balance.pharma.scale / pd.MONTHS
    pool = 0.0
    for r in pd.file(data).rivals:
        for d in r.drugs:
            if t < d.loe_us or d.loe_us <= pd.last_data_year(data):
                continue
            mod = pd.modality(data, d.modality)
            kept = pd.retained(mod, (t - d.loe_us) * pd.MONTHS)
            before = key_drug_b(d, t, data) / kept if kept > 0 else 0.0
            pool += before * (1 - kept) * mod.erosion.price_share * per_month
    for s in state.pharma_seeded:
        if turn < s.loe_turn:
            continue
        mod = pd.modality(data, s.modality)
        kept = pd.retained(mod, turn - s.loe_turn)
        before = seeded_b(s, turn, balance, data) / kept if kept > 0 else 0.0
        pool += before * (1 - kept) * mod.erosion.price_share / pd.MONTHS
    return pool


def rb_share(balance: Balance) -> float:
    return balance.pharma.rivals.generics_share


def month(
    state: GameState,
    share: dict[str, float],
    generic_cents: int,
    balance: Balance,
    data: GameData,
) -> tuple[list[LedgerEntry], dict[int, int]]:
    """Every pharma rival's month: revenue (and MRR) and its costs."""
    entries: list[LedgerEntry] = []
    revenue: dict[int, int] = {}
    turn = state.turn
    pool = (generic_cents + rival_generic_pool(state, balance, data)) * rb_share(balance)
    rb = balance.pharma.rivals
    for cid, r in sorted(companies(state, data).items()):
        cents = monthly_cents(state, cid, r, share, pool, balance, data)
        if cents <= 0:
            continue
        revenue[cid] = cents
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=cid,
                memo="Drug sales",
                debit=CASH,
                credit=DRUG_SALES,
                amount=cents,
            )
        )
        shares = rb.generics_cost_shares if r.generics else rb.cost_shares
        for account, s in sorted(shares.items()):
            cost = round(cents * s)
            if cost > 0:
                entries.append(
                    LedgerEntry.transfer(
                        turn=turn,
                        company_id=cid,
                        memo="Pharmaceutical costs",
                        debit=account,
                        credit=CASH,
                        amount=cost,
                    )
                )
    return entries, revenue


def january(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """Seeded approvals after 2025 (55.5), each January, for every non-generic rival: the rate
    is per $B of its last 12 months' revenue (real equivalent)."""
    turn = state.turn
    year = pd.year_of(turn)
    if turn % pd.MONTHS != 0 or turn <= pd.history_end_turn(data):
        return state
    rb = balance.pharma.rivals
    rows = list(state.pharma_seeded)
    next_id = max((s.id for s in rows), default=0) + 1
    per_b = pd.BILLION * pd.CENTS * balance.pharma.scale
    for cid, r in sorted(companies(state, data).items()):
        if r.generics:
            continue
        last_b = sum(state.company(cid).mrr_history[-pd.MONTHS :]) / per_b
        g = draws.gen(rng, turn, draws.RIVALS, cid, year)
        n = int(g.poisson(rb.approvals_per_b * max(0.0, last_b)))
        focus = r.focus or AREAS
        weights = [rb.modality_weights.get(m, 0.0) for m in MODALITIES]
        total = sum(weights)
        for k in range(n):
            area = focus[int(g.integers(len(focus)))]
            u = float(g.random()) * total
            modality = MODALITIES[-1]
            for m, w in zip(MODALITIES, weights, strict=True):
                if u < w:
                    modality = m
                    break
                u -= w
            peak_b = rb.peak_median_b * dmath.exp(rb.peak_sd * float(g.standard_normal()))
            month = int(g.integers(pd.MONTHS))
            approved = turn + month
            rows.append(
                SeededDrug(
                    id=next_id,
                    company_id=cid,
                    name=f"{_initials(r.company)}-{year % 100:02d}{k + 1:02d}",
                    area=area,
                    modality=modality,  # type: ignore[arg-type]
                    approved_turn=approved,
                    peak_cents=round(peak_b * pd.BILLION * pd.CENTS * balance.pharma.scale),
                    loe_turn=approved + round(rb.exclusivity_years * pd.MONTHS),
                )
            )
            next_id += 1
    return replace(state, pharma_seeded=tuple(rows))


def _initials(name: str) -> str:
    letters = "".join(w[0] for w in name.replace("&", " ").split() if w[0].isalpha())
    return letters.upper()[:3]  # tunable-exempt: a name


def opening_cash(state: GameState, balance: Balance, data: GameData) -> tuple[LedgerEntry, ...]:
    """New game: each pharma rival opens with `cash_months` of its revenue (incumbents.yaml)."""
    entries = []
    months = {i.name: i.cash_months for i in data.incumbents}
    for cid, r in sorted(companies(state, data).items()):
        c = state.company(cid)
        cents = monthly_cents(state, cid, r, {}, 0.0, balance, data)
        amount = round(cents * months.get(c.name, 0.0))
        if amount > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=cid,
                    memo="Opening capital of the drug business",
                    debit=CASH,
                    credit=COMMON_EQUITY,
                    amount=amount,
                )
            )
    return tuple(entries)
