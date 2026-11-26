"""Banks (docs/formulas.md 64.1). Every amount is integer cents; rates are floats only as the rates
they are, and money is multiplied by them through `times` (exact, rounded half to even once).

**Deposits.** A bank's accounts in its region are its company's banking lines' customers there
(consumer and business segments). A segment's deposits move each month by `bank.deposit_adjust`
toward

    accounts x the region's balance an account x clamp(1 + rate_elasticity x (r_bank - r_market)
    in points, rate_floor, rate_cap)

with r_bank = the region's policy rate x the bank's deposit beta and r_market = policy x
`bank.market_beta`. A balance an account is finance_services.yaml's 2010 balance x the region's
deposit index x (US deposits / North America's accounts) now over 2010's (held after 2025).

**Income.** Loans yield the policy rate + their kind's spread; securities their yield at purchase
(policy then + `term_premium` x duration); reserves the policy rate (interest on reserves).
Deposits cost r_bank. Charge-offs a month = balance x the kind's loss rate / 12: the year's FRED
rate to 2025 (it is the cycle), then the 2015-2019 mean x (1 + loss_cycle_k x (100 -
confidence) / 100).

**Balance sheet.** Repayments return balance / term a month; lots mature at par. New loans fill
the gap to loan_to_deposit x deposits (a deposit_adjust share a month) and new securities the
gap to securities_share x deposits, from reserves above `reserve_min` x deposits, only while
CET1 / RWA is at least the requirement (minimum + buffer + the size surcharge above
`gsib_assets_cents`) and the regulator has not restricted the bank. CET1 = reserves + loans +
securities (amortised cost) - deposits; RWA = loans x their risk weights (securities and reserves
0%). A lot's market value = amount x (1 - remaining duration x (r_now - r_bought) / 100).

**Rules.** CET1 below `intervene_share` x the minimum: the regulator intervenes (no growth until
the ratio is back at the requirement). Each June from the region's first stress year a bank above
`stress.size_cents` is stress-tested with a seeded shock (stream finserv (2, bank, year), drawn when
it runs): CET1 after a year's losses x loss_mult, the outflow's forced sales at the shocked
market value; below the minimum dividends freeze for `freeze_months`. Each December a bank above
its requirement pays `dividend_share` of its year's profit (at most its excess capital) to its
parent.

**Runs.** When unrealised securities losses exceed `run.unrealised_share` of CET1 and the
uninsured share of deposits exceeds `run.uninsured_min`, a month's run chance is run.chance x the
pressure (stream finserv (0, bank, month)). A run withdraws a drawn share of uninsured deposits:
reserves pay first, then securities are sold at market value (the loss realised in 4530). A run
that leaves CET1 at or below zero, or cannot be paid, fails the bank: its regulator takes it (its
books leave the company, 4930) and its lines' customers in the region go with it.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.finance import macro
from tst.sim.finserv.config import series_at
from tst.sim.finserv.data import FIRST_YEAR, LAST_YEAR, MONTHS, PCT, file, year_at
from tst.sim.finserv.models import Bank, BankMonth, RunRecord, SecurityLot, StressResult
from tst.sim.fx.rates import policy_rate
from tst.sim.geo.models import RegionalSegment
from tst.sim.ledger import CASH, DISPOSAL, LedgerEntry, LedgerLine
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import BP_DENOMINATOR, round_half_even, times
from tst.sim.products.models import SELLING, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_segments

RESERVES: Final = "1060_bank_reserves"
LOANS: Final = "1310_bank_loans"
SECURITIES: Final = "1320_bank_securities"
DEPOSITS: Final = "2310_deposits"
INTEREST_INCOME: Final = "4500_interest_income"
INTERCHANGE: Final = "4510_interchange"
SECURITIES_GAINS: Final = "4530_securities_gains"
DEPOSIT_INTEREST: Final = "5500_deposit_interest"
LOAN_LOSSES: Final = "6800_loan_losses"
CONSUMER: Final = "bank_consumer"
BUSINESS: Final = "bank_business"
RUN_KEY: Final = 0  # ADR-0013: finserv (0, bank id, month)
STRESS_KEY: Final = 2  # finserv (2, bank id, year)
CONFIDENCE_MID: Final = 100.0  # tunable-exempt: the confidence index's 2010-2019 mean
LIVE: Final = ("chartered", "partner")


def per_month(yearly_cents: int) -> int:
    """A year's amount / 12, rounded half to even (exact)."""
    return round_half_even(yearly_cents, MONTHS)


# --- the region's numbers -------------------------------------------------------------------------


def rate_fraction(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """The region's policy rate, a fraction a year (never below 0 for deposits)."""
    return policy_rate(state, region, balance, data) / PCT


def balance_per_account(
    state: GameState, segment: str, region: str, balance: Balance, data: GameData
) -> int:
    """A segment's average deposit balance an account in the region this month (cents)."""
    b = file(data).banking
    year = min(year_at(state.turn), float(LAST_YEAR) + 1 - 1 / MONTHS)
    na = "north_america"
    per = series_at(b.deposits_trn, year) / series_at(b.accounts[na], year)
    base = series_at(b.deposits_trn, float(FIRST_YEAR)) / series_at(
        b.accounts[na], float(FIRST_YEAR)
    )
    # money-exact: ratio (deposits a account now over 2010's, a growth ratio)
    growth = per / base if base > 0 else 1.0
    return times(round(b.balance_2010_cents[segment]), b.deposit_index[region], growth)


def requirement(bank: Bank, turn: int, data: GameData, balance: Balance) -> float:
    """CET1 / RWA the rules ask for: minimum + buffer (+ the size surcharge), a fraction."""
    rule = file(data).banking.rule_at(turn)
    big = bank.assets_cents > balance.finserv.bank.gsib_assets_cents
    return (rule.cet1_min + rule.buffer + (rule.surcharge if big else 0.0)) / PCT


def minimum(turn: int, data: GameData) -> float:
    return file(data).banking.rule_at(turn).cet1_min / PCT


def rwa_cents(bank: Bank, data: GameData) -> int:
    kinds = {k.key: k for k in file(data).banking.loan_kinds}
    return sum(times(v, kinds[k].risk_weight) for k, v in bank.loans)


def ratio(bank: Bank, data: GameData) -> float:
    rwa = rwa_cents(bank, data)
    if rwa <= 0:
        return float("inf") if bank.equity_cents > 0 else 0.0
    return bank.equity_cents / rwa  # money-exact: ratio


def remaining_duration(lot: SecurityLot, turn: int) -> float:
    life = lot.maturity_turn - lot.turn
    if life <= 0:
        return 0.0
    return lot.duration * max(0, lot.maturity_turn - turn) / life


def lot_value_cents(lot: SecurityLot, rate_pct: float, turn: int) -> int:
    """A lot's market value at a policy rate (% a year): amount x (1 - remaining duration x the
    rate's rise since purchase / 100), at least 0."""
    drop = remaining_duration(lot, turn) * (rate_pct - lot.rate) / PCT
    return max(0, times(lot.amount_cents, 1.0 - drop))


def securities_value_cents(bank: Bank, rate_pct: float, turn: int) -> int:
    return sum(lot_value_cents(x, rate_pct, turn) for x in bank.securities)


def unrealised_loss_cents(bank: Bank, rate_pct: float, turn: int) -> int:
    return max(0, bank.securities_cents - securities_value_cents(bank, rate_pct, turn))


def uninsured_share(bank: Bank, data: GameData) -> float:
    u = file(data).banking.uninsured_share
    total = bank.deposits_cents
    if total <= 0:
        return 0.0
    out = times(bank.consumer_deposits_cents, u[CONSUMER]) + times(
        bank.business_deposits_cents, u[BUSINESS]
    )
    return out / total  # money-exact: ratio


def loss_rate(kind: str, turn: int, state: GameState, balance: Balance, data: GameData) -> float:
    """A loan kind's yearly charge-off rate, a fraction (module docstring)."""
    k = file(data).banking.loan_kind(kind)
    bb = balance.finserv.bank
    year = turn_to_ym(turn)[0]
    if turn < balance.finserv.start_turn:
        return k.loss_at(year) / PCT
    lo, hi = int(bb.loss_base_years.lo), int(bb.loss_base_years.hi)
    base = sum(k.loss_at(y) for y in range(lo, hi + 1)) / (hi - lo + 1)
    confidence = macro.now(state, data).confidence
    return base / PCT * max(0.0, 1.0 + bb.loss_cycle_k * (CONFIDENCE_MID - confidence) / PCT)


def accounts(
    state: GameState, company_id: int, region: str, balance: Balance, data: GameData
) -> dict[str, float]:
    """The company's banking lines' customers in the region, by segment."""
    home = home_region_of(state, balance, data)
    cat = balance.finserv.banking_category
    out = {CONSUMER: 0.0, BUSINESS: 0.0}
    for p in state.company_products(company_id):
        if p.category != cat or p.status not in SELLING:
            continue
        if region == home:
            for s in state.segments_of(p.id):
                out[s.segment] = out.get(s.segment, 0.0) + s.customers
        for rs in state.regional_segments_of(p.id):
            if rs.region == region:
                out[rs.segment] = out.get(rs.segment, 0.0) + rs.customers
    return out


# --- a month ---------------------------------------------------------------------------------


def _entry(state: GameState, bank: Bank, memo: str, *lines: tuple[str, int]) -> LedgerEntry | None:
    rows = tuple(LedgerLine(a, v) for a, v in lines if v)
    if not rows:
        return None
    return LedgerEntry(turn=state.turn, company_id=bank.company_id, memo=memo, lines=rows)


def _deposit_targets(
    state: GameState, bank: Bank, r: float, balance: Balance, data: GameData
) -> dict[str, int]:
    bb = balance.finserv.bank
    gap_points = (r * bank.beta - r * bb.market_beta) * PCT
    pull = min(bb.rate_cap, max(bb.rate_floor, 1.0 + bb.rate_elasticity * gap_points))
    acc = accounts(state, bank.company_id, bank.region, balance, data)
    return {
        seg: times(balance_per_account(state, seg, bank.region, balance, data), n, pull)
        for seg, n in acc.items()
    }


def _move_deposits(
    state: GameState, bank: Bank, r: float, balance: Balance, data: GameData
) -> Bank:
    bb = balance.finserv.bank
    target = _deposit_targets(state, bank, r, balance, data)
    out = {}
    for seg, cur in (
        (CONSUMER, bank.consumer_deposits_cents),
        (BUSINESS, bank.business_deposits_cents),
    ):
        want = target.get(seg, 0)
        if bank.restricted:
            want = min(want, cur)
        out[seg] = max(0, cur + times(want - cur, bb.deposit_adjust))
    return replace(
        bank, consumer_deposits_cents=out[CONSUMER], business_deposits_cents=out[BUSINESS]
    )


def partner_month(
    state: GameState, bank: Bank, balance: Balance, data: GameData
) -> tuple[Bank, list[LedgerEntry]]:
    """A fintech's partner-bank programme: deposits move as a bank's; it keeps
    `partner_share` of their net interest at the year's US margin (no capital, no runs)."""
    r = rate_fraction(state, bank.region, balance, data)
    bank = _move_deposits(state, bank, r, balance, data)
    nim = series_at(file(data).banking.nim, year_at(state.turn)) / PCT
    fee = per_month(times(bank.deposits_cents, nim, balance.finserv.bank.partner_share))
    e = _entry(
        state, bank, "Partner bank: share of net interest", (CASH, fee), (INTEREST_INCOME, -fee)
    )
    return bank, [e] if e else []


def _split(amount: int, mix: dict[str, float]) -> list[tuple[str, int]]:
    """Integer shares of `amount` by `mix` (the last kind takes the remainder)."""
    keys = list(mix)
    out = []
    left = amount
    for k in keys[:-1]:
        v = times(amount, mix[k])
        out.append((k, v))
        left -= v
    out.append((keys[-1], left))
    return out


def chartered_month(
    state: GameState, bank: Bank, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[Bank, list[LedgerEntry], list[LogItem], BankMonth | None]:
    """One chartered bank's month (module docstring)."""
    bb = balance.finserv.bank
    b = file(data).banking
    kinds = {k.key: k for k in b.loan_kinds}
    turn = state.turn
    r = rate_fraction(state, bank.region, balance, data)
    r_pct = r * PCT
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []

    def post(memo: str, *lines: tuple[str, int]) -> None:
        e = _entry(state, bank, memo, *lines)
        if e is not None:
            entries.append(e)

    # deposits
    before = bank.deposits_cents
    bank = _move_deposits(state, bank, r, balance, data)
    moved = bank.deposits_cents - before
    bank = replace(bank, reserves_cents=bank.reserves_cents + moved)
    post("Bank deposits in and out", (RESERVES, moved), (DEPOSITS, -moved))
    # income and costs
    loan_income = sum(
        per_month(round_half_even(v * y, BP_DENOMINATOR))
        if (y := bank.fixed_yield(k)) is not None
        else per_month(times(v, max(0.0, r + kinds[k].spread / PCT)))
        for k, v in bank.loans
    )
    sec_income = sum(
        round_half_even(x.amount_cents * x.yield_bp, BP_DENOMINATOR * MONTHS)
        for x in bank.securities
    )
    reserve_income = per_month(times(bank.reserves_cents, max(0.0, r)))
    income = loan_income + sec_income + reserve_income
    deposit_rate = max(0.0, r * bank.beta)
    cost = per_month(times(bank.deposits_cents, deposit_rate))
    post("Bank interest income", (RESERVES, income), (INTEREST_INCOME, -income))
    # issuing (64.2): the bank's cards' volume earns the region's interchange
    card_volume = times(bank.loan("card"), balance.finserv.payments.card_turnover)
    swipe = times(
        card_volume, file(data).payments.interchange_at(bank.region, turn) / BP_DENOMINATOR
    )
    post("Interchange on the bank's cards", (RESERVES, swipe), (INTERCHANGE, -swipe))
    income += swipe
    post("Deposit interest", (DEPOSIT_INTEREST, cost), (RESERVES, -cost))
    # charge-offs and repayments
    charge = 0
    repaid = 0
    loans: dict[str, int] = dict(bank.loans)
    for k, v in bank.loans:
        c = per_month(times(v, loss_rate(k, turn, state, balance, data)))
        p = round_half_even(v - c, kinds[k].term_months)
        loans[k] = v - c - p
        charge += c
        repaid += p
    post("Loans charged off", (LOAN_LOSSES, charge), (LOANS, -charge))
    post("Loan repayments", (RESERVES, repaid), (LOANS, -repaid))
    matured = sum(x.amount_cents for x in bank.securities if x.maturity_turn <= turn)
    lots = tuple(x for x in bank.securities if x.maturity_turn > turn)
    post("Securities matured", (RESERVES, matured), (SECURITIES, -matured))
    bank = replace(
        bank,
        loans=tuple((k, loans[k]) for k in kinds if k in loans),
        securities=lots,
        reserves_cents=bank.reserves_cents + income - cost + repaid + matured,
        year_profit_cents=bank.year_profit_cents + income - cost - charge,
    )
    # the rules: intervention, then growth only above the requirement
    need = requirement(bank, turn, data, balance)
    now_ratio = ratio(bank, data)
    if not bank.restricted and now_ratio < bb.intervene_share * minimum(turn, data):
        bank = replace(bank, restricted=True)
        logs.append(_inbox(state, bank, "bank_restricted", data, ratio=f"{now_ratio:.1%}"))
    elif bank.restricted and now_ratio >= need:
        bank = replace(bank, restricted=False)
    if now_ratio >= need and not bank.restricted:
        spare = max(0, bank.reserves_cents - times(bank.deposits_cents, bb.reserve_min))
        gap = max(0, times(bank.deposits_cents, bank.loan_to_deposit) - bank.loans_cents)
        lend = min(spare, times(gap, bb.deposit_adjust))
        if lend > 0:
            loans = dict(bank.loans)
            yields = dict(bank.fixed_yields)
            for k, v in _split(lend, bb.loan_mix):
                if kinds[k].fixed and v > 0:  # the book's yield, weighted by balance
                    now_bp = round((max(0.0, r) + kinds[k].spread / PCT) * BP_DENOMINATOR)
                    old = loans.get(k, 0)
                    yields[k] = round_half_even(old * yields.get(k, now_bp) + v * now_bp, old + v)
                loans[k] = loans.get(k, 0) + v
            bank = replace(
                bank,
                loans=tuple((k, loans[k]) for k in kinds if k in loans),
                fixed_yields=tuple((k, yields[k]) for k in kinds if k in yields),
                reserves_cents=bank.reserves_cents - lend,
            )
            post("New loans", (LOANS, lend), (RESERVES, -lend))
            spare -= lend
        sec_gap = max(0, times(bank.deposits_cents, bank.securities_share) - bank.securities_cents)
        buy = min(spare, sec_gap)
        if buy > 0:
            lot = SecurityLot(
                amount_cents=buy,
                yield_bp=round((r + bb.term_premium * bank.duration / PCT) * BP_DENOMINATOR),
                rate=r_pct,
                duration=bank.duration,
                turn=turn,
                maturity_turn=turn + max(1, round(bank.duration * MONTHS)),
            )
            bank = replace(
                bank, securities=(*bank.securities, lot), reserves_cents=bank.reserves_cents - buy
            )
            post("Securities bought", (SECURITIES, buy), (RESERVES, -buy))
    # stress test, run, failure, dividends
    bank, stress_logs = _stress(state, bank, rng, r_pct, balance, data)
    logs += stress_logs
    bank, run_entries, run_logs = _run(state, bank, rng, r_pct, balance, data)
    entries += run_entries
    logs += run_logs
    if bank.status == "failed":
        return bank, entries, logs, None
    if turn_to_ym(turn)[1] == MONTHS:
        bank, div = _dividend(state, bank, balance, data)
        if div:
            post("Dividend from the bank", (CASH, div), (RESERVES, -div))
        bank = replace(bank, year_profit_cents=0)
    record = BankMonth(
        turn=turn,
        bank_id=bank.id,
        deposits_cents=bank.deposits_cents,
        loans_cents=bank.loans_cents,
        securities_cents=bank.securities_cents,
        securities_value_cents=securities_value_cents(bank, r_pct, turn),
        reserves_cents=bank.reserves_cents,
        cet1_cents=bank.equity_cents,
        rwa_cents=rwa_cents(bank, data),
        interest_income_cents=income,
        deposit_interest_cents=cost,
        charge_offs_cents=charge,
        policy_rate=r_pct,
        deposit_rate=deposit_rate * PCT,
        uninsured_share=uninsured_share(bank, data),
        requirement=requirement(bank, turn, data, balance),
    )
    return bank, entries, logs, record


def _inbox(state: GameState, bank: Bank, template: str, data: GameData, **params: Any) -> LogItem:
    return inbox_item(
        state.turn, bank.company_id, template, region=data.region(bank.region).label, **params
    )


def _dividend(state: GameState, bank: Bank, balance: Balance, data: GameData) -> tuple[Bank, int]:
    bb = balance.finserv.bank
    if bank.frozen_until is not None and state.turn <= bank.frozen_until:
        return bank, 0
    need = requirement(bank, state.turn, data, balance)
    excess = bank.equity_cents - times(rwa_cents(bank, data), need)
    div = min(excess, times(max(0, bank.year_profit_cents), bb.dividend_share), bank.reserves_cents)
    if div <= 0:
        return bank, 0
    return (
        replace(
            bank,
            reserves_cents=bank.reserves_cents - div,
            capital_in_cents=bank.capital_in_cents - div,
        ),
        div,
    )


def _stress(
    state: GameState, bank: Bank, rng: RngFactory, r_pct: float, balance: Balance, data: GameData
) -> tuple[Bank, list[LogItem]]:
    """June's stress test (module docstring); the shock is drawn now and never stored."""
    sb = balance.finserv.bank.stress
    year, month = turn_to_ym(state.turn)
    first = file(data).banking.stress_from[bank.region]
    if month != sb.month or year < first or bank.assets_cents <= sb.size_cents:
        return bank, []
    g = rng.stream(state.turn, "finserv", STRESS_KEY, bank.id, year)
    shock = sb.rate_shock.lo + (sb.rate_shock.hi - sb.rate_shock.lo) * float(g.random())
    mult = sb.loss_mult.lo + (sb.loss_mult.hi - sb.loss_mult.lo) * float(g.random())
    outflow = sb.deposit_outflow.lo + (sb.deposit_outflow.hi - sb.deposit_outflow.lo) * float(
        g.random()
    )
    year_losses = sum(
        times(v, loss_rate(k, state.turn, state, balance, data)) for k, v in bank.loans
    )
    extra_losses = times(year_losses, mult - 1.0)
    out = times(bank.deposits_cents, outflow)
    sold = max(0, out - bank.reserves_cents)
    book = bank.securities_cents
    shocked = securities_value_cents(bank, r_pct + shock, state.turn)
    loss_on_sale = 0
    if book > 0 and sold > 0:
        loss_on_sale = round_half_even(max(0, book - shocked) * min(sold, book), book)
    after = bank.equity_cents - extra_losses - loss_on_sale
    rwa = rwa_cents(bank, data)
    ratio_after = after / rwa if rwa > 0 else 0.0  # money-exact: ratio
    passed = ratio_after >= minimum(state.turn, data)
    frozen = bank.frozen_until
    if not passed:
        frozen = state.turn + sb.freeze_months
    bank = replace(
        bank,
        stress=(*bank.stress, StressResult(state.turn, ratio_after, passed)),
        frozen_until=frozen,
    )
    template = "bank_stress_passed" if passed else "bank_stress_failed"
    return bank, [_inbox(state, bank, template, data, ratio=f"{ratio_after:.1%}")]


def run_chance(bank: Bank, r_pct: float, turn: int, balance: Balance, data: GameData) -> float:
    """This month's run chance (module docstring): 0 unless both lines are crossed."""
    rb = balance.finserv.bank.run
    cet1 = bank.equity_cents
    if bank.status != "chartered" or cet1 <= 0:
        return 0.0
    unreal = unrealised_loss_cents(bank, r_pct, turn) / cet1  # money-exact: ratio
    u = uninsured_share(bank, data)
    if unreal <= rb.unrealised_share or u <= rb.uninsured_min:
        return 0.0
    pressure = min(1.0, (unreal - rb.unrealised_share) / rb.pressure_k)
    return rb.chance * pressure * (u - rb.uninsured_min) / (1.0 - rb.uninsured_min)


def risk_band(chance: float) -> str:
    """The Bank screen's run risk, never the chance itself (64.5's hidden-value rule)."""
    if chance <= 0:
        return "low"
    return "elevated" if chance < 0.03 else "high"  # tunable-exempt: the shown bands


def _run(
    state: GameState, bank: Bank, rng: RngFactory, r_pct: float, balance: Balance, data: GameData
) -> tuple[Bank, list[LedgerEntry], list[LogItem]]:
    chance = run_chance(bank, r_pct, state.turn, balance, data)
    if chance <= 0:
        return bank, [], []
    rb = balance.finserv.bank.run
    g = rng.stream(state.turn, "finserv", RUN_KEY, bank.id, state.turn)
    if float(g.random()) >= chance:
        return bank, [], []
    share = rb.withdraw.lo + (rb.withdraw.hi - rb.withdraw.lo) * float(g.random())
    u = file(data).banking.uninsured_share
    out_c = times(bank.consumer_deposits_cents, u[CONSUMER], share)
    out_b = times(bank.business_deposits_cents, u[BUSINESS], share)
    withdrawn = out_c + out_b
    entries: list[LedgerEntry] = []
    need = max(0, withdrawn - bank.reserves_cents)
    lots = list(bank.securities)
    realised = 0
    proceeds = 0
    book_sold = 0
    kept: list[SecurityLot] = []
    for lot in lots:
        if need <= 0:
            kept.append(lot)
            continue
        value = lot_value_cents(lot, r_pct, state.turn)
        if value <= need or value == 0:
            proceeds += value
            book_sold += lot.amount_cents
            need -= value
            continue
        # sell part of the lot: the fraction that raises `need`
        part = round_half_even(lot.amount_cents * need, value)
        proceeds += need
        book_sold += part
        kept.append(replace(lot, amount_cents=lot.amount_cents - part))
        need = 0
    realised = book_sold - proceeds
    if book_sold:
        e = _entry(
            state,
            bank,
            "Securities sold in a run",
            (RESERVES, proceeds),
            (SECURITIES_GAINS, realised),
            (SECURITIES, -book_sold),
        )
        if e:
            entries.append(e)
    paid = min(withdrawn, bank.reserves_cents + proceeds)
    e = _entry(state, bank, "Deposits withdrawn in a run", (DEPOSITS, paid), (RESERVES, -paid))
    if e:
        entries.append(e)
    scale_c = round_half_even(out_c * paid, withdrawn) if withdrawn else 0
    bank = replace(
        bank,
        securities=tuple(kept),
        reserves_cents=bank.reserves_cents + proceeds - paid,
        consumer_deposits_cents=bank.consumer_deposits_cents - scale_c,
        business_deposits_cents=bank.business_deposits_cents - (paid - scale_c),
        year_profit_cents=bank.year_profit_cents - realised,
    )
    failed = bank.equity_cents <= 0 or paid < withdrawn
    bank = replace(bank, runs=(*bank.runs, RunRecord(state.turn, paid, realised, failed)))
    logs = [_inbox(state, bank, "bank_run", data, withdrawn_cents=paid, loss_cents=realised)]
    if failed:
        bank, fail_entries, fail_logs = fail(state, bank, data)
        entries += fail_entries
        logs += fail_logs
    return bank, entries, logs


def fail(
    state: GameState, bank: Bank, data: GameData
) -> tuple[Bank, list[LedgerEntry], list[LogItem]]:
    """The regulator takes the bank: its books leave the company (the difference to 4930)."""
    lines = [
        (DEPOSITS, bank.deposits_cents),
        (RESERVES, -bank.reserves_cents),
        (LOANS, -bank.loans_cents),
        (SECURITIES, -bank.securities_cents),
        (DISPOSAL, bank.assets_cents - bank.deposits_cents),
    ]
    e = _entry(state, bank, "Bank failed: taken by its regulator", *lines)
    gone = replace(
        bank,
        status="failed",
        consumer_deposits_cents=0,
        business_deposits_cents=0,
        loans=(),
        securities=(),
        reserves_cents=0,
    )
    return gone, [e] if e else [], [_inbox(state, bank, "bank_failed", data)]


def lose_accounts(
    state: GameState, company_id: int, region: str, balance: Balance, data: GameData
) -> GameState:
    """A failed bank's accounts go with it: its company's banking lines' customers there."""
    home = home_region_of(state, balance, data)
    cat = balance.finserv.banking_category
    rows: list[ProductSegment] = []
    regional: list[RegionalSegment] = []
    for p in state.company_products(company_id):
        if p.category != cat:
            continue
        if region == home:
            rows += [replace(s, customers=0.0) for s in state.segments_of(p.id)]
        regional += [
            replace(r, customers=0.0)
            for r in state.regional_segments_of(p.id)
            if r.region == region
        ]
    if not rows and not regional:
        return state
    return with_segments(state, rows, regional)
