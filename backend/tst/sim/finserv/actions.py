"""The player's financial services actions (ADR-0014; docs/formulas.md 64.1-64.3). They take effect
at once and spend the actor's energy (`finserv.energy`). A line itself (banking, payments or
insurance) is made with `create_product` and launched as any product; it sells only where its
company's bank, network or insurer may (tst.sim.finserv.gates).

- **ApplyCharter** (`charter`): a bank charter in a region, for a company with a fintech or banking
  line: the application fee is paid, `bank.charter_capital_cents` moves from cash into the bank's
  reserves, and the region's regulator decides after its months (finance_services.yaml
  regulators, plus `bank.strict_months` under a strict regulator). A partner programme there ends
  when the charter comes.
- **PartnerBank** (`partner`): a chartered partner holds the company's banking lines' deposits in
  a region from this month (no capital; a share of the interest).
- **SetBank** (`setting`): a bank's deposit beta (within `bank.beta_range`), loans and securities
  as shares of deposits, and new securities' duration.
- **BankCapital** (`capital`): cash from the company into a chartered or applying bank's
  reserves (positive), or back out of a chartered bank's excess capital (negative).
- **LaunchNetwork** (`network`): a card network in a region for a company with a payments line
  (`payments.network_cost_cents`, expensed as development).
- **ApplyInsuranceLicence** (`licence`): an insurer's licence in a region for a company with an
  insurance line; the first one founds the insurer with `insurance.licence_capital_cents`.
- **InsurerCapital** (`capital`): cash into the insurer's investments, or back out of its own
  funds above the solvency rules.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import FinservRuleError, InsufficientCashError
from tst.sim.finserv import banks, insurance
from tst.sim.finserv.data import file
from tst.sim.finserv.models import Bank, Insurer, Licence, Network
from tst.sim.ledger import CASH, LedgerBalances, LedgerEntry, LedgerLine, account_balance
from tst.sim.log import inbox_item
from tst.sim.money import times
from tst.sim.products.models import SELLING
from tst.sim.state import GameState

GENERAL: Final = "6900_general_admin"
DEVELOPMENT: Final = "6500_research_development"
FINTECH: Final = "fintech"  # tunable-exempt: categories.yaml key


@dataclass(frozen=True, slots=True)
class ApplyCharter:
    actor_id: int
    region: str
    kind: Literal["apply_charter"] = "apply_charter"


@dataclass(frozen=True, slots=True)
class PartnerBank:
    actor_id: int
    region: str
    kind: Literal["partner_bank"] = "partner_bank"


@dataclass(frozen=True, slots=True)
class SetBank:
    actor_id: int
    bank_id: int
    beta: float
    loan_to_deposit: float
    securities_share: float
    duration: float
    kind: Literal["set_bank"] = "set_bank"


@dataclass(frozen=True, slots=True)
class BankCapital:
    actor_id: int
    bank_id: int
    amount_cents: int
    kind: Literal["bank_capital"] = "bank_capital"


@dataclass(frozen=True, slots=True)
class LaunchNetwork:
    actor_id: int
    region: str
    kind: Literal["launch_network"] = "launch_network"


@dataclass(frozen=True, slots=True)
class ApplyInsuranceLicence:
    actor_id: int
    region: str
    kind: Literal["apply_insurance_licence"] = "apply_insurance_licence"


@dataclass(frozen=True, slots=True)
class InsurerCapital:
    actor_id: int
    amount_cents: int
    kind: Literal["insurer_capital"] = "insurer_capital"


type FinservAction = (
    ApplyCharter
    | PartnerBank
    | SetBank
    | BankCapital
    | LaunchNetwork
    | ApplyInsuranceLicence
    | InsurerCapital
)
ACTION_TYPES: Final[dict[str, type]] = {
    "apply_charter": ApplyCharter,
    "partner_bank": PartnerBank,
    "set_bank": SetBank,
    "bank_capital": BankCapital,
    "launch_network": LaunchNetwork,
    "apply_insurance_licence": ApplyInsuranceLicence,
    "insurer_capital": InsurerCapital,
}


def _has_line(state: GameState, company: int, categories: tuple[str, ...]) -> bool:
    return any(
        p.company_id == company and p.category in categories and p.status != "retired"
        for p in state.products
    )


def _region(region: str, data: GameData) -> None:
    if region not in data.region_keys:
        raise FinservRuleError(f"unknown region {region!r}")


def _pay(
    state: GameState, company: int, memo: str, account: str, cents: int, balances: LedgerBalances
) -> LedgerEntry:
    if account_balance(balances, company, CASH) < cents:
        raise InsufficientCashError(f"{memo} needs {cents} cents")
    return LedgerEntry(
        turn=state.turn,
        company_id=company,
        memo=memo,
        lines=(LedgerLine(account, cents), LedgerLine(CASH, -cents)),
    )


def charter_months(state: GameState, region: str, balance: Balance, data: GameData) -> int:
    """The region's bank regulator's months to a charter (plus `strict_months` when strict)."""
    from tst.sim.finserv.regulation import strict

    base = file(data).regulators.bank[region].charter_months
    return base + (
        balance.finserv.bank.strict_months if strict(state, region, "bank", balance, data) else 0
    )


def apply_charter(
    state: GameState,
    action: ApplyCharter,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    _region(action.region, data)
    bb = balance.finserv.bank
    if not _has_line(state, company, (FINTECH, balance.finserv.banking_category)):
        raise FinservRuleError("a charter needs a fintech or banking line")
    old = state.finserv.bank_in(company, action.region)
    if old is not None and old.status in ("applying", "chartered"):
        raise FinservRuleError("the company already has a bank or an application there")
    need = bb.charter_fee_cents + bb.charter_capital_cents
    if account_balance(balances, company, CASH) < need:
        raise InsufficientCashError(f"a charter needs {need} cents (fee and opening capital)")
    state = spend_energy(
        state, action.actor_id, "apply_charter", balance, cost=balance.finserv.energy["charter"]
    )
    months = charter_months(state, action.region, balance, data)
    bank = Bank(
        id=state.finserv.next_id(),
        company_id=company,
        region=action.region,
        status="applying",
        applied_turn=state.turn,
        charter_turn=state.turn + months,
        beta=bb.default_beta,
        loan_to_deposit=bb.loan_to_deposit,
        securities_share=bb.securities_share,
        duration=bb.default_duration,
        reserves_cents=bb.charter_capital_cents,
        capital_in_cents=bb.charter_capital_cents,
    )
    rest = tuple(b for b in state.finserv.banks if b is not old)
    if old is not None:  # the partner programme runs until the charter
        rest = (*rest, old)
    state = replace(state, finserv=replace(state.finserv, banks=(*rest, bank)))
    fee = _pay(state, company, "Bank charter application", GENERAL, bb.charter_fee_cents, balances)
    capital = LedgerEntry(
        turn=state.turn,
        company_id=company,
        memo="Bank opening capital",
        lines=(
            LedgerLine(banks.RESERVES, bb.charter_capital_cents),
            LedgerLine(CASH, -bb.charter_capital_cents),
        ),
    )
    log = inbox_item(
        state.turn,
        company,
        "bank_charter_applied",
        region=data.region(action.region).label,
        regulator=file(data).regulators.bank[action.region].name,
        months=months,
        capital_cents=bb.charter_capital_cents,
    )
    return Outcome(state, (fee, capital), (log,))


def partner_bank(
    state: GameState, action: PartnerBank, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    _region(action.region, data)
    if not _has_line(state, company, (balance.finserv.banking_category,)):
        raise FinservRuleError("a partner bank holds a banking line's deposits: make one first")
    if state.finserv.bank_in(company, action.region) is not None:
        raise FinservRuleError("the company already has a bank or a partner there")
    state = spend_energy(
        state, action.actor_id, "partner_bank", balance, cost=balance.finserv.energy["partner"]
    )
    bb = balance.finserv.bank
    bank = Bank(
        id=state.finserv.next_id(),
        company_id=company,
        region=action.region,
        status="partner",
        applied_turn=state.turn,
        beta=bb.default_beta,
    )
    state = replace(state, finserv=replace(state.finserv, banks=(*state.finserv.banks, bank)))
    log = inbox_item(state.turn, company, "bank_partner", region=data.region(action.region).label)
    return Outcome(state, (), (log,))


def _own_bank(state: GameState, company: int, bank_id: int) -> Bank:
    bank = state.finserv.bank(bank_id)
    if bank is None or bank.company_id != company or bank.status == "failed":
        raise FinservRuleError("choose one of your banks")
    return bank


def set_bank(state: GameState, action: SetBank, balance: Balance) -> Outcome:
    company = acting_company(state, action.actor_id)
    bank = _own_bank(state, company, action.bank_id)
    bb = balance.finserv.bank
    if not bb.beta_range.lo <= action.beta <= bb.beta_range.hi:
        raise FinservRuleError(f"the deposit beta is {bb.beta_range.lo:.2f}-{bb.beta_range.hi:.2f}")
    if not 0.0 <= action.loan_to_deposit <= 1.0 or not 0.0 <= action.securities_share <= 1.0:
        raise FinservRuleError("loans and securities are shares of deposits, 0-100%")
    if action.loan_to_deposit + action.securities_share > 1.0 - bb.reserve_min:
        raise FinservRuleError(f"keep at least {bb.reserve_min:.0%} of deposits in reserves")
    if not bb.duration_years.lo <= action.duration <= bb.duration_years.hi:
        raise FinservRuleError(
            f"securities' duration is {bb.duration_years.lo:g}-{bb.duration_years.hi:g} years"
        )
    state = spend_energy(
        state, action.actor_id, "set_bank", balance, cost=balance.finserv.energy["setting"]
    )
    new = replace(
        bank,
        beta=action.beta,
        loan_to_deposit=action.loan_to_deposit,
        securities_share=action.securities_share,
        duration=action.duration,
    )
    return Outcome(with_bank(state, new))


def with_bank(state: GameState, bank: Bank) -> GameState:
    banks_ = tuple(bank if b.id == bank.id else b for b in state.finserv.banks)
    return replace(state, finserv=replace(state.finserv, banks=banks_))


def bank_capital(
    state: GameState,
    action: BankCapital,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    bank = _own_bank(state, company, action.bank_id)
    if bank.status not in ("chartered", "applying"):
        raise FinservRuleError("only a chartered bank (or one applying) holds capital")
    amount = action.amount_cents
    if amount == 0:
        raise FinservRuleError("choose an amount")
    if amount < 0:
        # M57r-A (review 10 item 9): no withdrawal before the charter, nor below its capital
        if bank.status != "chartered":
            raise FinservRuleError("capital can come back only once the bank is chartered")
        if bank.equity_cents + amount < balance.finserv.bank.charter_capital_cents:
            raise FinservRuleError("a bank keeps at least its charter capital")
        need = banks.requirement(bank, state.turn, data, balance)
        excess = bank.equity_cents - times(banks.rwa_cents(bank, data), need)
        if -amount > min(excess, bank.reserves_cents):
            raise FinservRuleError("only capital above the bank's requirement can come back")
        if bank.frozen_until is not None and state.turn <= bank.frozen_until:
            raise FinservRuleError("the bank's payments to the group are frozen")
    elif account_balance(balances, company, CASH) < amount:
        raise InsufficientCashError(f"that needs {amount} cents")
    state = spend_energy(
        state, action.actor_id, "bank_capital", balance, cost=balance.finserv.energy["capital"]
    )
    new = replace(
        bank,
        reserves_cents=bank.reserves_cents + amount,
        capital_in_cents=bank.capital_in_cents + amount,
    )
    e = LedgerEntry(
        turn=state.turn,
        company_id=company,
        memo="Capital into the bank" if amount > 0 else "Capital from the bank",
        lines=(LedgerLine(banks.RESERVES, amount), LedgerLine(CASH, -amount)),
    )
    return Outcome(with_bank(state, new), (e,))


def launch_network(
    state: GameState,
    action: LaunchNetwork,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    _region(action.region, data)
    if not _has_line(state, company, (balance.finserv.payments_category,)):
        raise FinservRuleError("a card network needs a payments line")
    if state.finserv.network_in(company, action.region) is not None:
        raise FinservRuleError("the company already runs a network there")
    cost = balance.finserv.payments.network_cost_cents
    e = _pay(state, company, "Card network build-out", DEVELOPMENT, cost, balances)
    state = spend_energy(
        state, action.actor_id, "launch_network", balance, cost=balance.finserv.energy["network"]
    )
    net = Network(
        id=state.finserv.next_id(), company_id=company, region=action.region, turn=state.turn
    )
    state = replace(state, finserv=replace(state.finserv, networks=(*state.finserv.networks, net)))
    log = inbox_item(
        state.turn, company, "network_launched", region=data.region(action.region).label
    )
    return Outcome(state, (e,), (log,))


def apply_licence(
    state: GameState,
    action: ApplyInsuranceLicence,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    _region(action.region, data)
    ib = balance.finserv.insurance
    if not _has_line(state, company, (balance.finserv.insurance_category,)):
        raise FinservRuleError("a licence needs an insurance line")
    insurer = state.finserv.insurer_of(company)
    if insurer is not None and any(x.region == action.region for x in insurer.licences):
        raise FinservRuleError("the insurer already holds or has applied for a licence there")
    capital = ib.licence_capital_cents if insurer is None else 0
    if account_balance(balances, company, CASH) < ib.licence_fee_cents + capital:
        raise InsufficientCashError(f"a licence needs {ib.licence_fee_cents + capital} cents")
    state = spend_energy(
        state,
        action.actor_id,
        "apply_insurance_licence",
        balance,
        cost=balance.finserv.energy["licence"],
    )
    months = file(data).regulators.insurance[action.region].licence_months
    lic = Licence(action.region, "applying", state.turn, state.turn + months)
    entries = [
        _pay(
            state, company, "Insurance licence application", GENERAL, ib.licence_fee_cents, balances
        )
    ]
    if insurer is None:
        insurer = Insurer(id=state.finserv.next_id(), company_id=company, investments_cents=capital)
        entries.append(
            LedgerEntry(
                turn=state.turn,
                company_id=company,
                memo="Insurer's opening capital",
                lines=(LedgerLine(insurance.INVESTMENTS, capital), LedgerLine(CASH, -capital)),
            )
        )
        insurers = (*state.finserv.insurers, replace(insurer, licences=(lic,)))
    else:
        new = replace(insurer, licences=(*insurer.licences, lic))
        insurers = tuple(new if i.id == insurer.id else i for i in state.finserv.insurers)
    state = replace(state, finserv=replace(state.finserv, insurers=insurers))
    log = inbox_item(
        state.turn,
        company,
        "insurance_licence_applied",
        region=data.region(action.region).label,
        regulator=file(data).regulators.insurance[action.region].name,
        months=months,
    )
    return Outcome(state, tuple(entries), (log,))


def insurer_capital(
    state: GameState,
    action: InsurerCapital,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    insurer = state.finserv.insurer_of(company)
    if insurer is None:
        raise FinservRuleError("the company has no insurer")
    amount = action.amount_cents
    if amount == 0:
        raise FinservRuleError("choose an amount")
    if amount < 0:
        spare = insurer.own_funds_cents - insurance.required_cents(state, insurer, balance, data)
        if -amount > spare:
            raise FinservRuleError("only own funds above the solvency rules can come back")
    elif account_balance(balances, company, CASH) < amount:
        raise InsufficientCashError(f"that needs {amount} cents")
    state = spend_energy(
        state, action.actor_id, "insurer_capital", balance, cost=balance.finserv.energy["capital"]
    )
    new = replace(insurer, investments_cents=insurer.investments_cents + amount)
    insurers = tuple(new if i.id == insurer.id else i for i in state.finserv.insurers)
    e = LedgerEntry(
        turn=state.turn,
        company_id=company,
        memo="Capital into the insurer" if amount > 0 else "Capital from the insurer",
        lines=(LedgerLine(insurance.INVESTMENTS, amount), LedgerLine(CASH, -amount)),
    )
    return Outcome(replace(state, finserv=replace(state.finserv, insurers=insurers)), (e,))


def apply_finserv(
    state: GameState,
    action: FinservAction,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    if data.finserv is None:
        raise FinservRuleError("this game has no financial services")
    match action:
        case ApplyCharter():
            return apply_charter(state, action, balance, data, balances)
        case PartnerBank():
            return partner_bank(state, action, balance, data)
        case SetBank():
            return set_bank(state, action, balance)
        case BankCapital():
            return bank_capital(state, action, balance, data, balances)
        case LaunchNetwork():
            return launch_network(state, action, balance, data, balances)
        case ApplyInsuranceLicence():
            return apply_licence(state, action, balance, data, balances)
        case InsurerCapital():
            return insurer_capital(state, action, balance, data, balances)


_ = SELLING
