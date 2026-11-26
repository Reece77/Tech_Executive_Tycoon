"""The Bank, Payments, Insurance and Currency screens' view (M54, docs/formulas.md 64): the player's
banks, networks, insurer and currency exposure. Public figures only (64.5): no run chance (a band),
no stress shock or catastrophe before it happens, no index beyond this month."""

from __future__ import annotations

from tst.api.schemas.finserv import (
    BankLoanOut,
    BankMonthOut,
    BankRunOut,
    BankScreenOut,
    BankStressOut,
    CatastropheOut,
    CurrencyRegionOut,
    CurrencyScreenOut,
    FinRegionOptionOut,
    FinservScreenOut,
    HedgeOut,
    InsuranceLicenceOut,
    InsuranceScreenOut,
    LineMonthOut,
    NetworkOut,
    OwnBankOut,
    PaymentsRegionOut,
    PaymentsScreenOut,
    ProgrammeOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.finserv import banks, insurance, payments, regulation
from tst.sim.finserv.actions import charter_months
from tst.sim.finserv.data import PCT, file, in_history, year_at
from tst.sim.finserv.models import Bank
from tst.sim.fx import hedges, rates
from tst.sim.fx.cfo import foreign_share
from tst.sim.fx.config import INDEX_SCALE
from tst.sim.money import BP_DENOMINATOR, times
from tst.sim.products.models import SELLING
from tst.sim.state import GameState

FINTECH = "fintech"
YEAR = 12


def _ids(state: GameState) -> set[int]:
    return {c.id for c in state.companies if c.is_player}


def _has(state: GameState, ids: set[int], categories: tuple[str, ...]) -> bool:
    return any(
        p.company_id in ids and p.category in categories and p.status != "retired"
        for p in state.products
    )


def _bank_out(state: GameState, bank: Bank, b: Balance, d: GameData) -> OwnBankOut:
    f = file(d).banking
    r_pct = banks.rate_fraction(state, bank.region, b, d) * PCT
    months = [m for m in state.finserv.bank_months if m.bank_id == bank.id]
    last = months[-YEAR:]
    assets = sum(m.loans_cents + m.securities_cents + m.reserves_cents for m in last)
    nim = sum(m.nii_cents for m in last) * YEAR / assets if assets > 0 else None
    rwa = banks.rwa_cents(bank, d)
    live = bank.status == "chartered"
    chance = banks.run_chance(bank, r_pct, state.turn, b, d) if live else 0.0
    return OwnBankOut(
        id=bank.id,
        region=bank.region,
        label=d.region(bank.region).label,
        status=bank.status,
        regulator=file(d).regulators.bank[bank.region].name,
        charter_month=format_turn(bank.charter_turn)
        if bank.status == "applying" and bank.charter_turn is not None
        else None,
        beta=bank.beta,
        loan_to_deposit=bank.loan_to_deposit,
        securities_share=bank.securities_share,
        duration=bank.duration,
        deposits_cents=bank.deposits_cents,
        consumer_deposits_cents=bank.consumer_deposits_cents,
        business_deposits_cents=bank.business_deposits_cents,
        loans_cents=bank.loans_cents,
        loans=[
            BankLoanOut(
                kind=k.key,
                label=k.label,
                balance_cents=bank.loan(k.key),
                risk_weight=k.risk_weight,
                yield_rate=max(0.0, r_pct + k.spread),
                loss_rate=banks.loss_rate(k.key, state.turn, state, b, d) * PCT,
            )
            for k in f.loan_kinds
        ],
        securities_cents=bank.securities_cents,
        securities_value_cents=banks.securities_value_cents(bank, r_pct, state.turn),
        unrealised_loss_cents=banks.unrealised_loss_cents(bank, r_pct, state.turn),
        reserves_cents=bank.reserves_cents,
        cet1_cents=bank.equity_cents if live or bank.status == "applying" else 0,
        rwa_cents=rwa,
        ratio=bank.equity_cents / rwa if rwa > 0 and live else None,
        requirement=banks.requirement(bank, state.turn, d, b),
        minimum=banks.minimum(state.turn, d),
        nim=nim,
        policy_rate=r_pct,
        deposit_rate=max(0.0, r_pct * bank.beta),
        market_deposit_rate=max(0.0, r_pct * b.finserv.bank.market_beta),
        uninsured_share=banks.uninsured_share(bank, d),
        insured_limit_cents=round(f.limit_at(bank.region, state.turn)),
        run_risk=banks.risk_band(chance),
        restricted=bank.restricted,
        dividends_frozen_until=format_turn(bank.frozen_until)
        if bank.frozen_until is not None and bank.frozen_until >= state.turn
        else None,
        capital_in_cents=bank.capital_in_cents,
        stress=[
            BankStressOut(month=format_turn(x.turn), ratio_after=x.ratio_after, passed=x.passed)
            for x in bank.stress
        ],
        runs=[
            BankRunOut(
                month=format_turn(x.turn),
                withdrawn_cents=x.withdrawn_cents,
                realised_loss_cents=x.realised_loss_cents,
                failed=x.failed,
            )
            for x in bank.runs
        ],
        months=[
            BankMonthOut(
                month=format_turn(m.turn),
                deposits_cents=m.deposits_cents,
                loans_cents=m.loans_cents,
                nii_cents=m.nii_cents,
                profit_cents=m.profit_cents,
                nim=m.nim,
                ratio=m.ratio,
                policy_rate=m.policy_rate,
                deposit_rate=m.deposit_rate,
            )
            for m in months
        ],
    )


def _regions(state: GameState, kind: str, b: Balance, d: GameData) -> list[FinRegionOptionOut]:
    regs = file(d).regulators
    out = []
    for r in d.region_keys:
        if kind == "bank":
            name, months = regs.bank[r].name, charter_months(state, r, b, d)
        else:
            name, months = regs.insurance[r].name, regs.insurance[r].licence_months
        out.append(
            FinRegionOptionOut(
                region=r,
                label=d.region(r).label,
                regulator=name,
                months=months,
                strict=regulation.strict(state, r, kind, b, d),
            )
        )
    return out


def bank_out(state: GameState, ids: set[int], b: Balance, d: GameData) -> BankScreenOut:
    bb = b.finserv.bank
    return BankScreenOut(
        can_charter=_has(state, ids, (FINTECH, b.finserv.banking_category)),
        has_banking_line=_has(state, ids, (b.finserv.banking_category,)),
        charter_capital_cents=bb.charter_capital_cents,
        charter_fee_cents=bb.charter_fee_cents,
        beta_range=[bb.beta_range.lo, bb.beta_range.hi],
        duration_range=[bb.duration_years.lo, bb.duration_years.hi],
        reserve_min=bb.reserve_min,
        partner_share=bb.partner_share,
        regions=_regions(state, "bank", b, d),
        banks=[_bank_out(state, x, b, d) for x in state.finserv.banks if x.company_id in ids],
        charters=[f"{c.name}: {c.kind} ({c.month})" for c in file(d).banking.charters],
    )


def payments_out(state: GameState, ids: set[int], b: Balance, d: GameData) -> PaymentsScreenOut:
    pdata = file(d).payments
    fb = b.finserv
    home = home_region_of(state, b, d)
    rows = {
        (m.company_id, m.region): m for m in state.finserv.payments_months if m.turn == state.turn
    }
    revenue: dict[str, int] = {}
    for p in state.products:
        if p.company_id not in ids or p.category != fb.payments_category or p.status not in SELLING:
            continue
        for s in state.segments_of(p.id):
            revenue[home] = revenue.get(home, 0) + times(s.price_cents or 0, s.customers)
        for rs in state.regional_segments_of(p.id):
            revenue[rs.region] = revenue.get(rs.region, 0) + times(
                rs.price_cents or 0, rs.customers
            )
    year = year_at(state.turn) if in_history(state.turn, b) else 2025.0
    regions = []
    from tst.sim.finserv.demand import rails_share

    for r in d.region_keys:
        acquired = sum(m.acquired_cents for (c, reg), m in rows.items() if reg == r and c in ids)
        carried = acquired + sum(
            m.network_volume_cents for (c, reg), m in rows.items() if reg == r and c in ids
        )
        rev = revenue.get(r, 0)
        regions.append(
            PaymentsRegionOut(
                region=r,
                label=d.region(r).label,
                acquired_cents=acquired,
                revenue_cents=rev,
                take_rate=rev / carried if carried > 0 else None,
                interchange_cents=sum(
                    m.interchange_cents for (c, reg), m in rows.items() if reg == r and c in ids
                ),
                fraud_cents=sum(
                    m.fraud_cents for (c, reg), m in rows.items() if reg == r and c in ids
                ),
                interchange_bp=payments.interchange_bp(r, state.turn, d),
                rails_share=rails_share(state, r, b, d),
                networks={
                    n.name: n.share_at(r, year) for n in pdata.networks if n.share_at(r, year) > 0
                },
            )
        )
    nets = []
    for n in state.finserv.networks:
        if n.company_id not in ids:
            continue
        row = rows.get((n.company_id, n.region))
        nets.append(
            NetworkOut(
                id=n.id,
                region=n.region,
                label=d.region(n.region).label,
                since=format_turn(n.turn),
                acceptance=n.acceptance,
                share=payments.network_share(state, n.company_id, n.region, b, d),
                volume_cents=row.network_volume_cents if row else 0,
            )
        )
    return PaymentsScreenOut(
        can_launch=_has(state, ids, (fb.payments_category,)),
        network_cost_cents=fb.payments.network_cost_cents,
        network_fee_bp=pdata.network_fee_bp,
        fraud_bp=pdata.fraud_bp,
        networks=nets,
        regions=regions,
    )


def insurance_out(state: GameState, ids: set[int], b: Balance, d: GameData) -> InsuranceScreenOut:
    ib = b.finserv.insurance
    ins = next((i for i in state.finserv.insurers if i.company_id in ids), None)
    by_line: dict[str, int] = {}
    if ins is not None:
        for _, seg, _, price, n in insurance._lines(state, ins.company_id, b, d):
            line = insurance.line_of(seg)
            by_line[line] = by_line.get(line, 0) + times(price, n)
    required = insurance.required_cents(state, ins, b, d) if ins else 0
    return InsuranceScreenOut(
        can_apply=_has(state, ids, (b.finserv.insurance_category,)),
        licence_capital_cents=ib.licence_capital_cents,
        licence_fee_cents=ib.licence_fee_cents,
        regions=_regions(state, "insurance", b, d),
        has_insurer=ins is not None,
        licences=[
            InsuranceLicenceOut(
                region=x.region,
                label=d.region(x.region).label,
                status=x.status,
                decided=format_turn(x.active_turn) if x.active_turn is not None else None,
            )
            for x in (ins.licences if ins else ())
        ],
        investments_cents=ins.investments_cents if ins else 0,
        float_cents=ins.reserves_cents if ins else 0,
        own_funds_cents=ins.own_funds_cents if ins else 0,
        required_cents=required,
        solvent=bool(ins and ins.own_funds_cents >= required),
        premiums_by_line=by_line,
        months=[
            LineMonthOut(
                month=format_turn(m.turn),
                premiums_cents=m.premiums_cents,
                claims_cents=m.claims_cents,
                combined_ratio=m.combined_ratio,
                investment_income_cents=m.investment_income_cents,
                float_cents=m.float_cents,
                own_funds_cents=m.own_funds_cents,
                required_cents=m.required_cents,
                catastrophe=m.catastrophe,
            )
            for m in state.finserv.insurance_months
            if m.company_id in ids
        ],
        catastrophes=[
            CatastropheOut(
                month=format_turn(c.turn), region=c.region, label=d.region(c.region).label
            )
            for c in state.finserv.world.cats
            if c.turn <= state.turn
        ],
    )


def _basket(region: str, d: GameData) -> str:
    f = d.fx
    if f is None:
        return "USD"
    weights = f.regions[region].weights
    return " / ".join(f"{k} {v:.0%}" if len(weights) > 1 else k for k, v in weights.items())


def currency_out(state: GameState, ids: set[int], b: Balance, d: GameData) -> CurrencyScreenOut:
    xb = b.fx
    months = [m for m in state.fx.months if m.company_id in ids and m.turn == state.turn]
    regions = []
    for r in d.region_keys:
        if r == xb.home:
            continue
        now = rates.index_at(state, r, state.turn, b, d)
        before = (
            rates.index_at(state, r, state.turn - YEAR, b, d) if state.turn - YEAR >= -24 else None
        )
        rows = [m for m in months if m.region == r]
        rev = sum(m.revenue_cents for m in rows)
        cost = sum(m.cost_cents for m in rows)
        net = rev - cost
        exposure = max(0, net) * YEAR
        hedged = sum(hedges.open_notional(state, c, r) for c in ids)
        regions.append(
            CurrencyRegionOut(
                region=r,
                label=d.region(r).label,
                currency=_basket(r, d),
                index=now / INDEX_SCALE,
                change_12m=(now / before - 1) if before else None,
                policy_rate=rates.policy_rate(state, r, b, d),
                revenue_cents=rev,
                untranslated_revenue_cents=sum(m.untranslated_revenue_cents for m in rows),
                cost_cents=cost,
                net_cents=net,
                exposure_cents=exposure,
                hedged_cents=hedged,
                unhedged_share=max(0.0, 1 - hedged / exposure) if exposure > 0 else None,
                what_if_cents=-times(net * YEAR, xb.what_if_move / (1 + xb.what_if_move)),
                forward_12m_index=hedges.forward_index(state, r, YEAR, b, d) / INDEX_SCALE
                if d.fx
                else None,
                spread_bp=xb.spread_bp[r],
            )
        )
    hs = []
    for h in state.fx.hedges:
        if h.company_id not in ids:
            continue
        hs.append(
            HedgeOut(
                id=h.id,
                region=h.region,
                label=d.region(h.region).label,
                notional_cents=h.notional_cents,
                bought=format_turn(h.turn),
                settles=format_turn(h.settle_turn),
                spot_index=h.spot_index / INDEX_SCALE,
                forward_index=h.forward_index / INDEX_SCALE,
                value_cents=h.value_cents,
                status=h.status,
                settled_cents=h.settled_cents,
                programme=h.programme,
            )
        )
    prog = next((p for p in state.fx.programmes if p.company_id in ids), None)
    result = sum(
        m.hedge_cents for m in state.fx.months if m.company_id in ids and m.turn > state.turn - YEAR
    )
    share = max((foreign_share(state, c) for c in ids), default=0.0)
    return CurrencyScreenOut(
        month=format_turn(state.turn),
        what_if_move=xb.what_if_move,
        term_range=[int(xb.term_months.lo), int(xb.term_months.hi)],
        max_hedge_share=xb.max_hedge_share,
        foreign_share=share,
        regions=regions,
        hedges=hs,
        programme=ProgrammeOut(share=prog.share, term_months=prog.term_months, by_cfo=prog.by_cfo)
        if prog
        else None,
        fx_result_12m_cents=result,
    )


def finserv_out(state: GameState, loaded: LoadedData) -> FinservScreenOut:
    b, d = loaded.balance, loaded.game_data
    ids = _ids(state)
    return FinservScreenOut(
        month=format_turn(state.turn),
        history=in_history(state.turn, b),
        bank=bank_out(state, ids, b, d),
        payments=payments_out(state, ids, b, d),
        insurance=insurance_out(state, ids, b, d),
        currency=currency_out(state, ids, b, d),
    )


_ = BP_DENOMINATOR
