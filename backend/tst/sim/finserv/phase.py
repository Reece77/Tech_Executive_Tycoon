"""Financial services' place in the turn (docs/formulas.md 64).

- **New game** (`new_game`): the finance markets' demand and history for the first month, and each
  finance incumbent's opening capital.
- **Phase 5** before the markets (`with_effects`): where the player's finance lines may win
  customers (a bank's line only with a charter or a partner bank there, an insurer's only where
  licensed and solvent, card programmes only where its network runs, at its acceptance's appeal);
  after the markets (`after_sales`): banks' month, payments' fees, interchange and fraud,
  insurers' claims and float, and rivals' interest, interchange and claims.
- **Phase 5**, first (`open_month`, M57r-A): growth draws, demand and the history's pin for
  this month, before its sales.
- **Phase 9** (`demand_month`): networks' acceptance, then the history's pin at the month's end.

A save without the finance markets (made before M54) does nothing here, and a company without a
bank, network or insurer plays exactly as before (64.6 target 1).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.finserv import banks, demand, gates, history, insurance, payments, regulation
from tst.sim.finserv.config import series_at
from tst.sim.finserv.data import MONTHS, PCT, enabled, file, is_finance_rival, year_at
from tst.sim.finserv.models import Bank, BankMonth, FinservState, InsuranceMonth, Insurer
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import round_half_even, times
from tst.sim.platforms.phase import Effects
from tst.sim.products.models import SELLING
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def new_game(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    if not enabled(state, balance, data):
        return state, ()
    state = demand.set_demand(state, balance, data)
    state = history.pin(state, balance, data)
    entries = []
    cash = balance.finserv.rival_cash_cents
    for company in state.rivals():
        if cash > 0 and is_finance_rival(company, data):
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=company.id,
                    memo="Opening capital of the finance business",
                    debit=CASH,
                    credit=COMMON_EQUITY,
                    amount=cash,
                )
            )
    return state, tuple(entries)


def with_effects(
    base: Effects | None, state: GameState, balance: Balance, data: GameData
) -> Effects | None:
    if not enabled(state, balance, data):
        return base
    return gates.effects(base, state, balance, data)


def _banks_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem], list[BankMonth]]:
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    records: list[BankMonth] = []
    out: list[Bank] = []
    chartered_regions = set()
    for bank in state.finserv.banks:
        if (
            bank.status == "applying"
            and bank.charter_turn is not None
            and state.turn >= bank.charter_turn
        ):
            bank = replace(bank, status="chartered")
            chartered_regions.add((bank.company_id, bank.region))
            logs.append(
                inbox_item(
                    state.turn,
                    bank.company_id,
                    "bank_chartered",
                    region=data.region(bank.region).label,
                    regulator=file(data).regulators.bank[bank.region].name,
                )
            )
        out.append(bank)
    # a partner programme ends when its company's own charter comes
    out = [
        b
        for b in out
        if not (b.status == "partner" and (b.company_id, b.region) in chartered_regions)
    ]
    done: list[Bank] = []
    for bank in out:
        if bank.status == "chartered":
            bank, more, more_logs, record = banks.chartered_month(state, bank, rng, balance, data)
            entries += more
            logs += more_logs
            if record is not None:
                records.append(record)
            if bank.status == "failed":
                state = banks.lose_accounts(state, bank.company_id, bank.region, balance, data)
        elif bank.status == "partner":
            bank, more = banks.partner_month(state, bank, balance, data)
            entries += more
        done.append(bank)
    state = replace(state, finserv=replace(state.finserv, banks=tuple(done)))
    return state, entries, logs, records


def _insurers_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem], list[InsuranceMonth]]:
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    records: list[InsuranceMonth] = []
    out: list[Insurer] = []
    for ins in state.finserv.insurers:
        ins, more, more_logs, record = insurance.insurer_month(state, ins, balance, data)
        entries += more
        logs += more_logs
        records.append(record)
        out.append(ins)
    return (
        replace(state, finserv=replace(state.finserv, insurers=tuple(out))),
        entries,
        logs,
        records,
    )


def rival_interest(state: GameState, balance: Balance, data: GameData) -> list[LedgerEntry]:
    """Rivals' banking lines' net interest this month: their accounts' deposits x the US banks'
    margin of the year (finance_services.yaml nim) / 12."""
    cat = balance.finserv.banking_category
    home = home_region_of(state, balance, data)
    ledger = {c.id for c in state.ledger_companies() if not c.is_player}
    nim = series_at(file(data).banking.nim, year_at(state.turn)) / PCT
    per: dict[tuple[str, str], int] = {}
    by_company: dict[int, int] = {}
    for p in state.products:
        if p.category != cat or p.company_id not in ledger or p.status not in SELLING:
            continue
        rows = [(s.segment, home, s.customers) for s in state.segments_of(p.id)]
        rows += [(r.segment, r.region, r.customers) for r in state.regional_segments_of(p.id)]
        for seg, region, n in rows:
            if n <= 0:
                continue
            if (seg, region) not in per:
                per[(seg, region)] = banks.balance_per_account(state, seg, region, balance, data)
            deposits = times(per[(seg, region)], n)
            by_company[p.company_id] = by_company.get(p.company_id, 0) + round_half_even(
                times(deposits, nim), MONTHS
            )
    return [
        LedgerEntry.transfer(
            turn=state.turn,
            company_id=cid,
            memo="Net interest income",
            debit=CASH,
            credit=banks.INTEREST_INCOME,
            amount=v,
        )
        for cid, v in sorted(by_company.items())
        if v > 0
    ]


def _keep(rows: tuple, turn: int, keep: int) -> tuple:  # type: ignore[type-arg]
    return tuple(r for r in rows if r.turn > turn - keep)


def after_sales(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not enabled(state, balance, data):
        return state, [], []
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    state = insurance.draw_cats(state, rng, balance, data)
    for cat in state.finserv.world.cats:
        if cat.turn == state.turn:
            for c in state.companies:
                if c.is_player and state.finserv.insurer_of(c.id) is not None:
                    logs.append(
                        inbox_item(
                            state.turn,
                            c.id,
                            "insurance_catastrophe",
                            region=data.region(cat.region).label,
                        )
                    )
    state, review_logs = regulation.group_review_month(state, balance, data)
    logs += review_logs
    logs += regulation.news_month(state, balance, data)
    bank_records: list[BankMonth] = []
    if state.finserv.banks:
        state, more, more_logs, bank_records = _banks_month(state, rng, balance, data)
        entries += more
        logs += more_logs
    pay_entries, shown = payments.acquiring_entries(state, balance, data)
    entries += pay_entries
    ins_records: list[InsuranceMonth] = []
    if state.finserv.insurers:
        state, more, more_logs, ins_records = _insurers_month(state, balance, data)
        entries += more
        logs += more_logs
    entries += rival_interest(state, balance, data)
    entries += insurance.rival_claims(state, balance, data)
    pay_records = payments.months(state, shown, balance, data)
    keep = balance.finserv.history_months
    fs: FinservState = state.finserv
    if (
        bank_records
        or pay_records
        or ins_records
        or fs.bank_months
        or fs.payments_months
        or fs.insurance_months
    ):
        fs = replace(
            fs,
            bank_months=(*_keep(fs.bank_months, state.turn, keep), *bank_records),
            payments_months=(*_keep(fs.payments_months, state.turn, keep), *pay_records),
            insurance_months=(*_keep(fs.insurance_months, state.turn, keep), *ins_records),
        )
        state = replace(state, finserv=fs)
    return state, entries, logs


def open_month(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """Phase 5, before the markets (M57r-A, review 10 item 13): this month's growth draws, demand
    and dated caps (a new real-time rail's volume, the history's incumbent pin), so the month's
    sales meet this month's market."""
    if not enabled(state, balance, data):
        return state
    state = demand.draw_growth(state, rng, balance, data)
    state = demand.set_demand(state, balance, data)
    return history.pin(state, balance, data)


def demand_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    if not enabled(state, balance, data):
        return state, []
    state = payments.networks_month(state, balance, data)
    return history.pin(state, balance, data), []
