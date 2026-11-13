"""Mining actions (ADR-0014; docs/formulas.md 35.1-35.3): found a subsidiary, transfer a project
or facility inside the group at book value, build a mine, choose its sales and safety, sign a
sale, care and maintenance or a restart, close it, and answer a rival's bid.

The founder acts for every company of the player's group (as in M18). Every draw is on stream
`mining` keyed by the mine's facility id (ADR-0013). The overrun and the deposit's truth are
stored on the mine and never leave the sim (35.2; ADR-0007)."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, spend_energy
from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import (
    InsufficientCashError,
    InvalidActionError,
    MiningRuleError,
    UnknownMineError,
)
from tst.sim.exploration import pipeline as xp
from tst.sim.exploration.geology import block_of
from tst.sim.exploration.models import Project
from tst.sim.facilities.models import Facility
from tst.sim.group.assets import check_country, crew_to, move_facility, place
from tst.sim.group.models import Ownership
from tst.sim.ledger import (
    ACCUMULATED_DEPRECIATION,
    ARO,
    CASH,
    COMMON_EQUITY,
    DEPLETION,
    EXPLORATION,
    INVESTMENT_SUBSIDIARIES,
    MINERAL_PROPERTIES,
    PPE,
    LedgerBalances,
    LedgerEntry,
    LedgerLine,
)
from tst.sim.log import inbox_item
from tst.sim.mining import formulas as mf
from tst.sim.mining import prices
from tst.sim.mining.config import SAFETY, SUBTYPES
from tst.sim.mining.draws import BUILD, OVERRUN, mining_draws
from tst.sim.mining.models import Mine, MineDeal
from tst.sim.money import format_money
from tst.sim.rivals.models import SUBSIDIARY_KEY
from tst.sim.rng import RngFactory
from tst.sim.state import (
    CompanyState,
    GameState,
    company_cash,
    listed_id,
    with_facility,
    with_mine,
    with_mine_deal,
    with_ownership,
    with_rival_bid,
)

LINK: Final = "mine"
KIND: Final = "mine"  # balance.facility.kinds key
MT: Final = 1e6  # tunable-exempt: t a Mt
GA: Final = "6900_general_admin"
DISPOSAL: Final = "4930_gain_on_disposal"


# --- Actions ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FoundSubsidiary:
    """35.1: a new, 100%-owned company with a cash injection from its parent (the group's
    listed company, or `parent_id` inside the group)."""

    actor_id: int
    name: str
    region: str
    cents: int
    parent_id: int | None = None
    country: str | None = None  # M23a: the country it sits in (default: the region's default)
    kind: Literal["found_subsidiary"] = "found_subsidiary"


@dataclass(frozen=True, slots=True)
class TransferAsset:
    """35.1: move an exploration project (its licence) or a facility to another company of the
    group at book value, paid in cash by the receiver."""

    actor_id: int
    to_company_id: int
    project_id: int | None = None
    facility_id: int | None = None
    kind: Literal["transfer_asset"] = "transfer_asset"


@dataclass(frozen=True, slots=True)
class BuildMine:
    """35.2: build a mine on a permitted project; `capacity_t` (product a year) within the
    study's range (default its design capacity)."""

    actor_id: int
    project_id: int
    capacity_t: float | None = None
    kind: Literal["build_mine"] = "build_mine"


@dataclass(frozen=True, slots=True)
class SetMineSales:
    """35.3: sell at spot (`buyer_id` None) or to a group company at a transfer price."""

    actor_id: int
    mine_id: int
    buyer_id: int | None = None
    price_kind: str = "market"
    margin: float | None = None
    kind: Literal["set_mine_sales"] = "set_mine_sales"


@dataclass(frozen=True, slots=True)
class StaffMine:
    """The unit whose mining engineers staff the mine: any company of the group may employ
    them (M19 decision); None unstaffs it. A unit staffs at most one facility."""

    actor_id: int
    mine_id: int
    unit_id: int | None
    kind: Literal["staff_mine"] = "staff_mine"


@dataclass(frozen=True, slots=True)
class SetMineSafety:
    actor_id: int
    mine_id: int
    safety: str
    kind: Literal["set_mine_safety"] = "set_mine_safety"


@dataclass(frozen=True, slots=True)
class SignMineSale:
    """35.3: the mine as seller: a fixed-price contract (`months`) or an offtake (`years`)
    with a buyer, on `volume_t_year` of its output."""

    actor_id: int
    mine_id: int
    deal_kind: str  # contract or offtake
    volume_t_year: float
    months: int | None = None
    years: int | None = None
    buyer: str | None = None
    kind: Literal["sign_mine_sale"] = "sign_mine_sale"


@dataclass(frozen=True, slots=True)
class CareMaintenance:
    """35.4: put a producing mine on care and maintenance, or restart one."""

    actor_id: int
    mine_id: int
    restart: bool = False
    kind: Literal["care_maintenance"] = "care_maintenance"


@dataclass(frozen=True, slots=True)
class CloseMine:
    actor_id: int
    mine_id: int
    kind: Literal["close_mine"] = "close_mine"


@dataclass(frozen=True, slots=True)
class AnswerRivalBid:
    actor_id: int
    bid_id: int
    accept: bool
    kind: Literal["answer_rival_bid"] = "answer_rival_bid"


type MiningAction = (
    FoundSubsidiary
    | TransferAsset
    | BuildMine
    | SetMineSales
    | StaffMine
    | SetMineSafety
    | SignMineSale
    | CareMaintenance
    | CloseMine
    | AnswerRivalBid
)

ACTION_TYPES: Final[dict[str, type]] = {
    "found_subsidiary": FoundSubsidiary,
    "transfer_asset": TransferAsset,
    "build_mine": BuildMine,
    "set_mine_sales": SetMineSales,
    "staff_mine": StaffMine,
    "set_mine_safety": SetMineSafety,
    "sign_mine_sale": SignMineSale,
    "care_maintenance": CareMaintenance,
    "close_mine": CloseMine,
    "answer_rival_bid": AnswerRivalBid,
}


# --- Who acts --------------------------------------------------------------------------------


def group_ids(state: GameState) -> set[int]:
    return {c.id for c in xp.explorers(state)}


def _founder(state: GameState, actor_id: int) -> None:
    founder = state.founder_of(state.player.id)
    if founder is None or founder.id != actor_id:
        raise InvalidActionError("only the founder acts for the group's mines")


def _stage(state: GameState) -> int:
    return max(c.stage for c in xp.explorers(state))


def own_mine(state: GameState, actor_id: int, mine_id: int) -> Mine:
    _founder(state, actor_id)
    mine = state.mine(mine_id)
    if mine is None or mine.company_id not in group_ids(state):
        raise UnknownMineError(f"no mine {mine_id}")
    return mine


def mine_name(mine: Mine, data: GameData) -> str:
    assert data.geology is not None
    label = data.geology.commodity(mine.commodity).label
    region = data.region(mine.region).label
    return f"{label} mine #{mine.id}, {region}"


def _pay(company_id: int, turn: int, memo: str, debit: str, cents: int) -> LedgerEntry:
    return LedgerEntry.transfer(
        turn=turn, company_id=company_id, memo=memo, debit=debit, credit=CASH, amount=cents
    )


# --- 35.1 Founding a subsidiary and moving assets into it ------------------------------------


def found_subsidiary(
    state: GameState,
    action: FoundSubsidiary,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    fb = balance.mining.found
    _founder(state, action.actor_id)
    if _stage(state) < fb.min_stage:
        raise MiningRuleError(f"founding a subsidiary opens at stage {fb.min_stage}")
    name = action.name.strip()
    if not name:
        raise MiningRuleError("a subsidiary needs a name")
    if any(c.name.casefold() == name.casefold() for c in state.companies):
        raise MiningRuleError(f"a company called {name!r} already exists")
    if action.region not in data.region_keys:
        raise MiningRuleError(f"unknown region {action.region!r}")
    check_country(data, action.region, action.country)
    parent = action.parent_id if action.parent_id is not None else listed_id(state)
    if parent not in group_ids(state):
        raise MiningRuleError("the parent is a company of your group")
    if action.cents < fb.min_cents:
        raise MiningRuleError(f"inject at least {format_money(fb.min_cents)}")
    if company_cash(balances, parent) < action.cents:
        raise InsufficientCashError(f"the injection needs {format_money(action.cents)} in cash")
    state = spend_energy(state, action.actor_id, action.kind, balance, cost=fb.energy)
    turn = state.turn
    cid = max(c.id for c in state.companies) + 1
    founded = sum(1 for c in state.companies if c.rival_key[:1] == (SUBSIDIARY_KEY,))
    city = next(
        (
            c.key
            for c in data.cities
            if c.region == action.region and (action.country is None or c.country == action.country)
        ),
        None,
    )
    company = CompanyState(
        id=cid,
        name=name,
        is_player=False,
        stage=1,
        founded_turn=turn,
        stage_history=((1, turn),),
        hq_city=city,
        parent_id=parent,
        rival_key=(SUBSIDIARY_KEY, founded),  # a stable identity for its streams (ADR-0013)
    )
    state = replace(state, companies=(*state.companies, company))
    state = place(state, "company", cid, action.country)
    state = with_ownership(
        state,
        Ownership(
            id=0,
            company_id=cid,
            owner_id=parent,
            from_turn=turn - 1,  # a new company: nothing of its own before the injection
            book_cents=0,
            equity_cents=0,
        ),
    )
    entries = (
        LedgerEntry.transfer(
            turn=turn,
            company_id=parent,
            memo=f"Founded {name}",
            debit=INVESTMENT_SUBSIDIARIES,
            credit=CASH,
            amount=action.cents,
        ),
        LedgerEntry.transfer(
            turn=turn,
            company_id=cid,
            memo=f"Share capital from {state.company(parent).name}",
            debit=CASH,
            credit=COMMON_EQUITY,
            amount=action.cents,
        ),
    )
    log = inbox_item(
        turn,
        state.player.id,
        "subsidiary_founded",
        link_kind="group",
        name=name,
        region=data.region(action.region).label,
        amount_cents=action.cents,
    )
    return Outcome(state, entries, (log,))


def transfer_asset(
    state: GameState, action: TransferAsset, balances: LedgerBalances, data: GameData
) -> Outcome:
    _founder(state, action.actor_id)
    group = group_ids(state)
    to = action.to_company_id
    if to not in group:
        raise MiningRuleError("assets move only between companies of your group")
    if (action.project_id is None) == (action.facility_id is None):
        raise MiningRuleError("transfer one project or one facility")
    turn = state.turn
    receiver = state.company(to).name
    if action.project_id is not None:
        project = xp.project_of(state, action.project_id)
        if project.company_id not in group:
            raise MiningRuleError("that project is not your group's")
        if project.company_id == to:
            raise MiningRuleError(f"{receiver} already holds it")
        if project.status not in ("active", "permitted"):
            raise MiningRuleError("only a live licence or a permitted project can move")
        if any(m.project_id == project.id for m in state.mines):
            raise MiningRuleError("a mine stands on it: move the mine instead")
        # exploration is expensed as spent (M18): a project's book value is nil
        state = xp.with_project(state, replace(project, company_id=to))
        log = inbox_item(
            turn,
            state.player.id,
            "asset_transferred",
            link_kind="exploration",
            link_id=project.id,
            asset=xp.label_of(project),
            to=receiver,
            amount_cents=0,
        )
        return Outcome(state, (), (log,))
    assert action.facility_id is not None
    facility = state.facility(action.facility_id)
    if facility is None or facility.company_id not in group or facility.status == "closed":
        raise MiningRuleError(f"no facility {action.facility_id} in your group")
    if facility.company_id == to:
        raise MiningRuleError(f"{receiver} already owns it")
    seller = facility.company_id
    mine = state.mine(facility.id)
    entries: list[LedgerEntry] = []
    if mine is not None:
        if not mine.is_open:
            raise MiningRuleError("that mine is closed")
        book = mine.book_cents
        owed = mine.aro_cents - mine.aro_paid_cents
        cash = book - owed
        lines_out = [LedgerLine(MINERAL_PROPERTIES, -book), LedgerLine(ARO, owed)]
        lines_in = [LedgerLine(MINERAL_PROPERTIES, book), LedgerLine(ARO, -owed)]
        name = mine_name(mine, data)
    else:
        book = facility.book_value_cents
        cash = book
        lines_out = [
            LedgerLine(PPE, -facility.capex_paid_cents),
            LedgerLine(ACCUMULATED_DEPRECIATION, facility.depreciated_cents),
        ]
        lines_in = [
            LedgerLine(PPE, facility.capex_paid_cents),
            LedgerLine(ACCUMULATED_DEPRECIATION, -facility.depreciated_cents),
        ]
        name = f"facility #{facility.id}"
    if cash > 0 and company_cash(balances, to) < cash:
        raise InsufficientCashError(f"{receiver} needs {format_money(cash)} to pay book value")
    memo = f"Transfer at book value: {name}"
    out = [line for line in [*lines_out, LedgerLine(CASH, cash)] if line.amount]
    inn = [line for line in [*lines_in, LedgerLine(CASH, -cash)] if line.amount]
    if out:
        entries.append(LedgerEntry(turn, seller, f"{memo}, to {receiver}", tuple(out)))
    if inn:
        entries.append(LedgerEntry(turn, to, memo, tuple(inn)))
    state = move_facility(state, facility.id, to)  # M23a: every record and its crew
    log = inbox_item(
        turn,
        state.player.id,
        "asset_transferred",
        link_kind="mine" if mine is not None else "group",
        link_id=facility.id if mine is not None else None,
        asset=name,
        to=receiver,
        amount_cents=book,
    )
    return Outcome(state, tuple(entries), (log,))


# --- 35.2 Building a mine --------------------------------------------------------------------


def subtype_of(project: Project, depth_m: float, balance: Balance) -> str:
    """Brine deposits are brine operations; placers and shallow hard rock open pits; hard rock
    whose top is deeper than `mining.underground_depth_m` underground."""
    kind = project.kind or "hard_rock"
    if kind == "brine":
        return "brine"
    if kind == "hard_rock" and depth_m > balance.mining.underground_depth_m:
        return "underground"
    return "open_pit"


@dataclass(frozen=True, slots=True)
class MineQuote:
    """What a build would be, from revealed numbers only (the overrun is never in it)."""

    project_id: int
    subtype: str
    design_t: float
    capacity_lo_t: float
    capacity_hi_t: float
    capacity_t: float
    estimate_cents: int
    construction_lo: int
    construction_hi: int
    overrun_lo: float
    overrun_hi: float
    staff_needed: int


def design_capacity_t(project: Project) -> float:
    """The study's design capacity: estimated tonnage x grade x recovery (centres) over the
    feasibility life, a year (34.2's capex basis)."""
    assert project.est_tonnage_center is not None and project.est_grade_center is not None
    assert project.recovery_center is not None
    ore = math.exp(project.est_tonnage_center) * MT
    return ore * math.exp(project.est_grade_center) * project.recovery_center


def quote(
    state: GameState, project: Project, capacity_t: float | None, balance: Balance, data: GameData
) -> MineQuote:
    mb = balance.mining
    if project.status != "permitted":
        raise MiningRuleError("a mine is built on a permitted project")
    if project.level is None or project.capex_center is None:
        raise MiningRuleError("a mine needs a feasibility study")
    if any(m.project_id == project.id and m.status != "closed" for m in state.mines):
        raise MiningRuleError("a mine already stands on that project")
    ended = {m.close_reason for m in earlier_mines(state, project.id)}
    if "depleted" in ended:
        raise MiningRuleError("that deposit is exhausted: its mine closed when the ore ran out")
    if ended & DISPOSED:
        raise MiningRuleError("that deposit's mine was sold or seized: it is no longer the group's")
    block = block_of(state, project.region, project.block)
    assert block is not None
    sub = subtype_of(project, block.depth_m, balance)
    fb = balance.exploration.feasibility
    design = design_capacity_t(project) / fb.life_years
    lo, hi = mf.capacity_bounds(design, mb)
    cap = design if capacity_t is None else capacity_t
    if not lo * (1 - 1e-9) <= cap <= hi * (1 + 1e-9):  # tunable-exempt: float tolerance
        raise MiningRuleError(f"capacity is {lo:,.0f}-{hi:,.0f} t a year")
    estimate = mf.capex_for(
        round(math.exp(project.capex_center) * 100), cap, design, mb.capex_scale
    )
    span = mb.subtypes[sub].construction_months
    over = mb.overrun[project.level]
    return MineQuote(
        project_id=project.id,
        subtype=sub,
        design_t=design,
        capacity_lo_t=lo,
        capacity_hi_t=hi,
        capacity_t=cap,
        estimate_cents=estimate,
        construction_lo=round(span.lo),
        construction_hi=round(span.hi),
        overrun_lo=over.lo,
        overrun_hi=over.hi,
        staff_needed=mf.staff_needed(cap, mb.staff_per_kt),
    )


DISPOSED: Final = frozenset({"sold", "sold_to_state", "seized"})


def earlier_mines(state: GameState, project_id: int) -> list[Mine]:
    """Mines built on the project before, closed (M23a: the deposit's history)."""
    return [m for m in state.mines if m.project_id == project_id and m.status == "closed"]


def deposit_history(state: GameState, project: Project) -> tuple[float, int]:
    """(ore its closed mines took, spend already capitalized): the project's own record. A mine's
    `ore_mined_mt` is the deposit's cumulative extraction, so for a save from before M23r (no
    record on the project) the latest closed mine's counter is the deposit's, never their sum;
    each mine's `moved_cents` is its own, so their sum is what was capitalized."""
    earlier = earlier_mines(state, project.id)
    mined = max([project.depleted_mt, *(m.ore_mined_mt for m in earlier)])
    capitalized = max(project.capitalized_cents, sum(m.moved_cents for m in earlier))
    return mined, capitalized


def build_mine(
    state: GameState,
    action: BuildMine,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    _founder(state, action.actor_id)
    project = xp.project_of(state, action.project_id)
    if project.company_id not in group_ids(state):
        raise MiningRuleError("that project is not your group's")
    q = quote(state, project, action.capacity_t, balance, data)
    mb = balance.mining
    sub = mb.subtypes[q.subtype]
    company = project.company_id
    span = sub.construction_months
    first = q.estimate_cents / max(1.0, span.lo)
    if company_cash(balances, company) < first:
        raise InsufficientCashError(f"the first capex payment needs {format_money(round(first))}")
    state = spend_energy(state, action.actor_id, action.kind, balance, cost=mb.build_energy)
    fid, ids = state.next_ids.take("facility")
    state = replace(state, next_ids=ids)
    turn = state.turn
    months = mf.construction_months(
        float(mining_draws(rng, turn, fid, BUILD).random()), span.lo, span.hi
    )
    over = mb.overrun[project.level or "definitive"]
    hidden = mf.overrun(float(mining_draws(rng, turn, fid, OVERRUN).random()), over.lo, over.hi)
    block, hit = xp._truth(state, project, data)
    assert data.geology is not None and project.commodity is not None
    c = data.geology.commodity(project.commodity)
    assert project.est_grade_center is not None and project.recovery_center is not None
    ready = turn + months
    # M23a (Codex review 5 finding 2), M23r (review 6 finding 1): depletion and capitalized
    # exploration are the deposit's, kept on the project across mine lifetimes. A mine rebuilt
    # after a chosen closure starts where the last one stopped and capitalizes only the
    # project's spend not yet moved to 1520.
    mined, capitalized = deposit_history(state, project)
    moved = max(0, project.spent_cents - capitalized)
    state = xp.with_project(state, replace(project, capitalized_cents=capitalized + moved))
    mine = Mine(
        id=fid,
        company_id=company,
        project_id=project.id,
        region=project.region,
        block=project.block,
        commodity=project.commodity,
        subtype=q.subtype,
        level=project.level or "definitive",
        capacity_t=q.capacity_t,
        design_grade=math.exp(project.est_grade_center),
        design_recovery=project.recovery_center,
        ordered_turn=turn,
        ready_turn=ready,
        estimate_cents=q.estimate_cents,
        hidden_overrun=hidden,
        hidden_ore_mt=xp._tonnage_truth(block, hit, c),
        hidden_grade=xp._grade_truth(block, hit, c),
        hidden_recovery=block.true_recovery if hit else sum(c.recovery) / 2,
        moved_cents=moved,
        ore_mined_mt=mined,
    )
    facility = Facility(
        id=fid,
        company_id=company,
        kind=KIND,
        region=project.region,
        capacity=round(q.capacity_t),
        on_time=round(q.capacity_t),
        ordered_turn=turn,
        ready_turn=ready,
        late_turn=ready,
        capex_cents=q.estimate_cents,  # the estimate: the overrun is the mine's, hidden
        input_index=1.0,
    )
    state = with_mine(with_facility(state, facility), mine)
    entries: tuple[LedgerEntry, ...] = ()
    if moved:  # 35.2: the project's exploration and study spend is capitalized (once)
        entries = (
            LedgerEntry.transfer(
                turn=turn,
                company_id=company,
                memo=f"Capitalized exploration: {xp.label_of(project)}",
                debit=MINERAL_PROPERTIES,
                credit=EXPLORATION,
                amount=moved,
            ),
        )
    log = inbox_item(
        turn,
        state.player.id,
        "mine_ordered",
        link_kind=LINK,
        link_id=fid,
        mine=mine_name(mine, data),
        capex_cents=q.estimate_cents,
        years=f"{months / MONTHS_PER_YEAR:.1f}",
    )
    return Outcome(state, entries, (log,))


# --- 35.3 Sales, safety and contracts --------------------------------------------------------


def set_mine_sales(state: GameState, action: SetMineSales, balance: Balance) -> Outcome:
    mine = own_mine(state, action.actor_id, action.mine_id)
    if action.buyer_id is not None:
        if action.buyer_id not in group_ids(state) or action.buyer_id == mine.company_id:
            raise MiningRuleError("the buyer is another company of your group")
        if action.price_kind not in balance.mining.transfer_kinds:
            raise MiningRuleError(f"a transfer price is one of {balance.mining.transfer_kinds}")
        if action.margin is not None and not 0 <= action.margin <= 1:
            raise MiningRuleError("a cost-plus margin is 0-100%")
    state = spend_energy(
        state, action.actor_id, action.kind, balance, cost=balance.mining.sale_energy
    )
    mine = replace(
        mine,
        buyer_id=action.buyer_id,
        price_kind=action.price_kind if action.buyer_id is not None else "market",
        margin=action.margin if action.buyer_id is not None else None,
    )
    return Outcome(with_mine(state, mine))


def staff_mine(state: GameState, action: StaffMine, balance: Balance) -> Outcome:
    mine = own_mine(state, action.actor_id, action.mine_id)
    facility = state.facility(mine.id)
    if facility is None or not mine.is_open:
        raise MiningRuleError("that mine is closed")
    if action.unit_id is not None:
        unit = state.unit(action.unit_id)
        if unit is None or unit.company_id not in group_ids(state):
            raise MiningRuleError(f"no unit {action.unit_id} in your group")
        if any(f.unit_id == action.unit_id and f.id != mine.id for f in state.facilities):
            raise MiningRuleError("that unit already staffs another facility")
    if facility.unit_id == action.unit_id:
        raise MiningRuleError("that unit already staffs it")
    state = spend_energy(
        state, action.actor_id, action.kind, balance, cost=balance.facility.assign_energy
    )
    if action.unit_id is not None:  # M23r (finding 2): the mine's owner pays the crew it counts
        state = crew_to(state, action.unit_id, mine.company_id)
    return Outcome(with_facility(state, replace(facility, unit_id=action.unit_id)))


def set_mine_safety(state: GameState, action: SetMineSafety) -> Outcome:
    mine = own_mine(state, action.actor_id, action.mine_id)
    if action.safety not in SAFETY:
        raise MiningRuleError(f"safety spend is one of {list(SAFETY)}")
    return Outcome(with_mine(state, replace(mine, safety=action.safety)))


def sign_mine_sale(
    state: GameState, action: SignMineSale, balance: Balance, data: GameData
) -> Outcome:
    mine = own_mine(state, action.actor_id, action.mine_id)
    sb = balance.mining.sale
    if not mine.is_open:
        raise MiningRuleError("that mine is closed")
    if action.volume_t_year <= 0:
        raise MiningRuleError("a sale needs a volume")
    committed = sum(
        d.volume_t_year
        for d in state.mine_deals
        if d.mine_id == mine.id and d.end_turn >= state.turn
    )
    if committed + action.volume_t_year > mine.capacity_t * (1 + 1e-9):  # tunable-exempt: tolerance
        raise MiningRuleError("the mine's sales would exceed its capacity")
    spot = prices.spot_usd_t(state, mine.commodity, data, balance)
    if action.deal_kind == "contract":
        months = action.months or 0
        if not sb.contract_months.lo <= months <= sb.contract_months.hi:
            raise MiningRuleError(
                f"a contract runs {sb.contract_months.lo:g}-{sb.contract_months.hi:g} months"
            )
        floor = ceiling = spot
        buyer = action.buyer or "Metals traders"
    elif action.deal_kind == "offtake":
        years = action.years or 0
        if not sb.offtake_years.lo <= years <= sb.offtake_years.hi:
            raise MiningRuleError(
                f"an offtake runs {sb.offtake_years.lo:g}-{sb.offtake_years.hi:g} years"
            )
        months = years * MONTHS_PER_YEAR
        floor, ceiling = spot * (1 - sb.collar), spot * (1 + sb.collar)
        buyer = action.buyer or "A refiner"
    else:
        raise MiningRuleError("a sale is a contract or an offtake")
    state = spend_energy(
        state, action.actor_id, action.kind, balance, cost=balance.mining.sale_energy
    )
    deal = MineDeal(
        id=max((d.id for d in state.mine_deals), default=0) + 1,
        mine_id=mine.id,
        kind="contract" if action.deal_kind == "contract" else "offtake",
        buyer=buyer,
        signed_turn=state.turn,
        end_turn=state.turn + months - 1,
        volume_t_year=action.volume_t_year,
        signing_usd_t=spot,
        floor_usd_t=floor,
        ceiling_usd_t=ceiling,
        last_usd_t=spot,
    )
    return Outcome(with_mine_deal(state, deal))


def care_maintenance(
    state: GameState,
    action: CareMaintenance,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    """35.4: care and maintenance stops output (fixed cost x care_fixed); a restart costs
    restart_cents_per_kt a thousand t of capacity and takes restart_months."""
    mine = own_mine(state, action.actor_id, action.mine_id)
    cb = balance.mining.crash
    turn = state.turn
    entries: tuple[LedgerEntry, ...] = ()
    if action.restart:
        if mine.status != "care":
            raise MiningRuleError("only a mine on care and maintenance restarts")
        cost = round(mine.capacity_t / 1000 * cb.restart_cents_per_kt)  # tunable-exempt: t to kt
        if company_cash(balances, mine.company_id) < cost:
            raise InsufficientCashError(f"a restart needs {format_money(cost)}")
        if cost:
            entries = (_pay(mine.company_id, turn, f"Restart: {mine_name(mine, data)}", GA, cost),)
        mine = replace(mine, status="restarting", restart_due=turn + cb.restart_months)
        template = "mine_restarting"
    else:
        if mine.status != "producing":
            raise MiningRuleError("only a producing mine goes on care and maintenance")
        mine = replace(mine, status="care", care_since=turn)
        template = "mine_care"
    state = spend_energy(
        state, action.actor_id, action.kind, balance, cost=balance.mining.care_energy
    )
    log = inbox_item(
        turn, state.player.id, template, link_kind=LINK, link_id=mine.id, mine=mine_name(mine, data)
    )
    return Outcome(with_mine(state, mine), entries, (log,))


def close_entries(state: GameState, mine: Mine, data: GameData) -> list[LedgerEntry]:
    """Closing: what is left of the mineral property is written off to 6750."""
    if mine.book_cents <= 0:
        return []
    return [
        LedgerEntry.transfer(
            turn=state.turn,
            company_id=mine.company_id,
            memo=f"Closure write-off: {mine_name(mine, data)}",
            debit=DEPLETION,
            credit=MINERAL_PROPERTIES,
            amount=mine.book_cents,
        )
    ]


def closed(state: GameState, mine: Mine, reason: str) -> GameState:
    """The mine and its facility close; reclamation is paid over the months after (35.3)."""
    mine = replace(
        mine,
        status="closed",
        closed_turn=state.turn,
        close_reason=reason,  # type: ignore[arg-type]
        depleted_cents=mine.capex_paid_cents + mine.moved_cents,
        crash_turn=None,
        takeover_turn=None,
        accident_turn=None,
    )
    state = with_mine(state, mine)
    project = next((p for p in state.projects if p.id == mine.project_id), None)
    if project is not None:  # M23r: the deposit keeps its depletion for a rebuild
        depleted = max(project.depleted_mt, mine.ore_mined_mt)
        state = xp.with_project(state, replace(project, depleted_mt=depleted))
    facility = state.facility(mine.id)
    if facility is not None:
        state = with_facility(
            state, replace(facility, status="closed", closed_turn=state.turn, unit_id=None)
        )
    return state


def close_mine(state: GameState, action: CloseMine, balance: Balance, data: GameData) -> Outcome:
    mine = own_mine(state, action.actor_id, action.mine_id)
    if not mine.is_open:
        raise MiningRuleError("that mine is already closed")
    state = spend_energy(
        state, action.actor_id, action.kind, balance, cost=balance.mining.close_energy
    )
    entries = close_entries(state, mine, data)
    # unpaid capex of a mine still building is cancelled
    state = closed(state, mine, "chosen")
    log = inbox_item(
        state.turn,
        state.player.id,
        "mine_closed",
        link_kind=LINK,
        link_id=mine.id,
        mine=mine_name(mine, data),
        reclamation_cents=mine.aro_cents - mine.aro_paid_cents,
    )
    return Outcome(state, tuple(entries), (log,))


def answer_rival_bid(
    state: GameState, action: AnswerRivalBid, balance: Balance, data: GameData
) -> Outcome:
    """35.5: accept a rival's bid for a permitted project (as M18's sale, at the bid) or a
    mine (cash for its book value and its reclamation duty), or decline it."""
    _founder(state, action.actor_id)
    bid = next((b for b in state.rival_bids if b.id == action.bid_id), None)
    if bid is None or bid.status != "open" or bid.company_id not in group_ids(state):
        raise MiningRuleError(f"no open bid {action.bid_id}")
    if not action.accept:
        return Outcome(with_rival_bid(state, replace(bid, status="declined")))
    turn = state.turn
    entries: list[LedgerEntry] = []
    name = ""
    if bid.project_id is not None:
        project = xp.project_of(state, bid.project_id)
        if project.status != "permitted" or project.company_id != bid.company_id:
            raise MiningRuleError("that project is no longer for sale")
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=bid.company_id,
                memo=f"Project sold: {xp.label_of(project)}",
                debit=CASH,
                credit=DISPOSAL,
                amount=bid.cents,
            )
        )
        state = xp.with_project(
            state,
            replace(
                project,
                status="sold",
                sold_to=bid.supplier,
                sale_cents=bid.cents,
                ended_turn=turn,
            ),
        )
        name = xp.label_of(project)
    else:
        assert bid.mine_id is not None
        mine = state.mine(bid.mine_id)
        if mine is None or not mine.is_open or mine.company_id != bid.company_id:
            raise MiningRuleError("that mine is no longer for sale")
        owed = mine.aro_cents - mine.aro_paid_cents
        gain = bid.cents - (mine.book_cents - owed)
        lines = [
            LedgerLine(CASH, bid.cents),
            LedgerLine(ARO, owed),
            LedgerLine(MINERAL_PROPERTIES, -mine.book_cents),
            LedgerLine(DISPOSAL, -gain),
        ]
        entries.append(
            LedgerEntry(
                turn,
                mine.company_id,
                f"Mine sold: {mine_name(mine, data)}",
                tuple(x for x in lines if x.amount),
            )
        )
        mine = replace(mine, aro_paid_cents=mine.aro_cents)  # the buyer takes the duty
        state = closed(state, replace(mine, depleted_cents=0), "sold")
        name = mine_name(mine, data)
    state = with_rival_bid(state, replace(bid, status="accepted"))
    log = inbox_item(
        turn,
        state.player.id,
        "rival_bid_accepted",
        link_kind=LINK if bid.mine_id is not None else "exploration",
        link_id=bid.mine_id if bid.mine_id is not None else bid.project_id,
        asset=name,
        amount_cents=bid.cents,
    )
    return Outcome(state, tuple(e for e in entries if len(e.lines) >= 2), (log,))


def apply_mining(
    state: GameState,
    action: MiningAction,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    match action:
        case FoundSubsidiary():
            return found_subsidiary(state, action, balances, balance, data)
        case TransferAsset():
            return transfer_asset(state, action, balances, data)
        case BuildMine():
            return build_mine(state, action, rng, balances, balance, data)
        case SetMineSales():
            return set_mine_sales(state, action, balance)
        case StaffMine():
            return staff_mine(state, action, balance)
        case SetMineSafety():
            return set_mine_safety(state, action)
        case SignMineSale():
            return sign_mine_sale(state, action, balance, data)
        case CareMaintenance():
            return care_maintenance(state, action, balances, balance, data)
        case CloseMine():
            return close_mine(state, action, balance, data)
        case AnswerRivalBid():
            return answer_rival_bid(state, action, balance, data)


__all__ = ["ACTION_TYPES", "SUBTYPES", "MiningAction", "apply_mining"]
