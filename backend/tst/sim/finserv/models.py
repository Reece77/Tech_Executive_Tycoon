"""Frozen financial services records (docs/formulas.md 64.1-64.3). GameState holds one
`FinservState`: the player's banks (with their balance sheets, in integer cents), payments
networks, insurers, their months, and the game-wide `FinservWorld` (drawn growth after 2025 and the
catastrophes that have happened). Persisted in `finserv_record` (migration 0069_m54).

Hidden values (64.5): a stress test's shock is drawn when the test runs (stream finserv (2, bank,
year)) and only its result is stored; a run's chance and draw are drawn each month (finserv (0,
bank, month)) and only a run that happened is stored; a catastrophe is drawn in its month (finserv
(1, region, year)) and stored once it has happened. The API shows run risk only as a band."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SecurityLot:
    """Fixed-rate securities bought in `turn` at the policy rate `rate` (% a year) plus the term
    premium, yielding `yield_bp` a year; `duration` years; repaid at par at `maturity_turn`."""

    amount_cents: int
    yield_bp: int
    rate: float
    duration: float
    turn: int
    maturity_turn: int


@dataclass(frozen=True, slots=True)
class StressResult:
    turn: int
    ratio_after: float  # CET1 / risk-weighted assets after the shock
    passed: bool


@dataclass(frozen=True, slots=True)
class RunRecord:
    turn: int
    withdrawn_cents: int
    realised_loss_cents: int
    failed: bool


@dataclass(frozen=True, slots=True)
class Bank:
    """A company's bank in a region (64.1): applying for a charter (`applying`, from `applied_turn`
    to `charter_turn`), chartered, or a fintech's partner-bank programme (`partner`: deposits held
    at the partner, a share of their interest kept, no capital), or `failed` (taken by its
    regulator). A chartered bank's books: reserves (1060), loans by kind (1310), securities lots
    (1320) and deposits by segment (2310), every amount integer cents."""

    id: int
    company_id: int
    region: str
    status: str  # applying, chartered, partner, failed
    applied_turn: int
    charter_turn: int | None = None
    product_id: int | None = None  # the company's banking line
    beta: float = 0.4  # tunable-exempt: a record default; set from finserv.bank at the charter
    loan_to_deposit: float = 0.7  # tunable-exempt: likewise
    securities_share: float = 0.25  # tunable-exempt: likewise
    duration: float = 4.0  # tunable-exempt: likewise (new securities' duration, years)
    consumer_deposits_cents: int = 0
    business_deposits_cents: int = 0
    loans: tuple[tuple[str, int], ...] = ()  # (loan kind, balance)
    # (loan kind, book yield bp a year) of fixed-rate kinds: the balance-weighted rate written
    fixed_yields: tuple[tuple[str, int], ...] = ()
    securities: tuple[SecurityLot, ...] = ()
    reserves_cents: int = 0
    capital_in_cents: int = 0  # the parent's capital less dividends paid
    frozen_until: int | None = None  # dividends frozen to this month (a failed stress test)
    restricted: bool = False  # the regulator has intervened: no growth until capital recovers
    stress: tuple[StressResult, ...] = ()
    runs: tuple[RunRecord, ...] = ()
    year_profit_cents: int = 0  # this year's profit so far (dividends each December)

    @property
    def deposits_cents(self) -> int:
        return self.consumer_deposits_cents + self.business_deposits_cents

    @property
    def loans_cents(self) -> int:
        return sum(v for _, v in self.loans)

    @property
    def securities_cents(self) -> int:
        return sum(x.amount_cents for x in self.securities)

    @property
    def assets_cents(self) -> int:
        return self.reserves_cents + self.loans_cents + self.securities_cents

    @property
    def equity_cents(self) -> int:
        """CET1 capital: assets less deposits (the bank's books balance by construction)."""
        return self.assets_cents - self.deposits_cents

    def loan(self, kind: str) -> int:
        return next((v for k, v in self.loans if k == kind), 0)

    def fixed_yield(self, kind: str) -> int | None:
        return next((y for k, y in self.fixed_yields if k == kind), None)


@dataclass(frozen=True, slots=True)
class BankMonth:
    turn: int
    bank_id: int
    deposits_cents: int
    loans_cents: int
    securities_cents: int
    securities_value_cents: int  # market value
    reserves_cents: int
    cet1_cents: int
    rwa_cents: int
    interest_income_cents: int
    deposit_interest_cents: int
    charge_offs_cents: int
    policy_rate: float
    deposit_rate: float
    uninsured_share: float
    requirement: float  # CET1 / RWA the rules ask for (minimum + buffers)

    @property
    def nii_cents(self) -> int:
        return self.interest_income_cents - self.deposit_interest_cents

    @property
    def profit_cents(self) -> int:
        return self.nii_cents - self.charge_offs_cents

    @property
    def ratio(self) -> float:
        # money-exact: ratio
        return self.cet1_cents / self.rwa_cents if self.rwa_cents > 0 else 0.0

    @property
    def nim(self) -> float:
        """Net interest margin, a year, of earning assets (loans, securities and reserves)."""
        assets = self.loans_cents + self.securities_cents + self.reserves_cents
        # money-exact: ratio
        return 12 * self.nii_cents / assets if assets > 0 else 0.0


@dataclass(frozen=True, slots=True)
class Network:
    """A company's card network in a region (64.2): its payments line sells card programmes
    there; `acceptance` is the share of merchants that take it, moving toward its share of cards
    ** acceptance_exponent (the two-sided effect)."""

    id: int
    company_id: int
    region: str
    turn: int
    acceptance: float = 0.0
    status: str = "live"


@dataclass(frozen=True, slots=True)
class PaymentsMonth:
    """A company's payments line in a region this month: card volume it carries as a network
    (`network_volume_cents`) and acquires for merchants (`acquired_cents`), its share of the
    region's network volume, fees, interchange and fraud."""

    turn: int
    company_id: int
    region: str
    network_volume_cents: int
    acquired_cents: int
    share: float
    acceptance: float
    interchange_cents: int  # paid (acquiring) or earned (issuing), positive
    fraud_cents: int
    rails_share: float


@dataclass(frozen=True, slots=True)
class Licence:
    region: str
    status: str  # applying, active
    turn: int  # applied
    active_turn: int | None = None


@dataclass(frozen=True, slots=True)
class Insurer:
    """A company's insurer (64.3): licences by region, capital and float held in 1330 against
    claims reserves (2320). Writes new business only where licensed and solvent."""

    id: int
    company_id: int
    licences: tuple[Licence, ...] = ()
    investments_cents: int = 0  # 1330: capital paid in, float and income, less claims paid
    reserves_cents: int = 0  # 2320: claims incurred not yet paid
    reserves_by_line: tuple[tuple[str, int], ...] = ()

    @property
    def own_funds_cents(self) -> int:
        return self.investments_cents - self.reserves_cents

    def licensed(self, region: str) -> bool:
        return any(x.region == region and x.status == "active" for x in self.licences)


@dataclass(frozen=True, slots=True)
class InsuranceMonth:
    turn: int
    company_id: int
    premiums_cents: int
    claims_cents: int
    paid_cents: int
    investment_income_cents: int
    float_cents: int  # claims reserves
    own_funds_cents: int
    required_cents: int
    combined_ratio: float
    catastrophe: bool


@dataclass(frozen=True, slots=True)
class Catastrophe:
    """A catastrophe that has happened after 2025 (drawn in its month; never stored before)."""

    turn: int
    region: str
    extra: float  # points on property's combined ratio for the year, booked this month


@dataclass(frozen=True, slots=True)
class FinservWorld:
    """Game-wide draws: each region's yearly growth after 2025 by kind (0 accounts, 1 policies,
    2 card volume), and catastrophes that have happened."""

    growth: tuple[tuple[int, int, int, float], ...] = ()  # (year, region index, kind, rate)
    cats: tuple[Catastrophe, ...] = ()

    def rate(self, year: int, region_index: int, kind: int) -> float | None:
        # M60: an index of the draws, built once per tuple (the first match, as a scan finds)
        from tst.sim.state import from_inputs

        def index() -> dict[tuple[int, int, int], float]:
            out: dict[tuple[int, int, int], float] = {}
            for y, r, k, g in self.growth:
                out.setdefault((y, r, k), g)
            return out

        return from_inputs(self.growth, "finserv_growth", index).get((year, region_index, kind))


@dataclass(frozen=True, slots=True)
class FinservState:
    banks: tuple[Bank, ...] = ()
    networks: tuple[Network, ...] = ()
    insurers: tuple[Insurer, ...] = ()
    bank_months: tuple[BankMonth, ...] = ()
    payments_months: tuple[PaymentsMonth, ...] = ()
    insurance_months: tuple[InsuranceMonth, ...] = ()
    world: FinservWorld = field(default_factory=FinservWorld)

    def bank(self, bank_id: int) -> Bank | None:
        return next((b for b in self.banks if b.id == bank_id), None)

    def bank_in(self, company_id: int, region: str) -> Bank | None:
        return next(
            (
                b
                for b in self.banks
                if b.company_id == company_id and b.region == region and b.status != "failed"
            ),
            None,
        )

    def network_in(self, company_id: int, region: str) -> Network | None:
        return next(
            (n for n in self.networks if n.company_id == company_id and n.region == region),
            None,
        )

    def insurer_of(self, company_id: int) -> Insurer | None:
        return next((i for i in self.insurers if i.company_id == company_id), None)

    def next_id(self) -> int:
        ids = [b.id for b in self.banks] + [n.id for n in self.networks]
        return max([*ids, *(i.id for i in self.insurers)], default=0) + 1
