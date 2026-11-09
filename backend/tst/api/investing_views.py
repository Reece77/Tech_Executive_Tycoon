"""Views of the founder's own investments (M26, formulas.md 37.7). Built from public records
only: never a trade's `risk`, `public_turn`, `investigate_turn` or `gain_cents` before a
finding, a stake's `coi_found_turn`, the manager's true skill or a startup's true value."""

from __future__ import annotations

from tst.api.schemas.investing import (
    AngelStakeOut,
    CategoryOptionOut,
    FamilyOfficeFormOut,
    FamilyOfficeOut,
    HoldingOut,
    IndexPointOut,
    InvestingRulesOut,
    InvestmentsOut,
    ListedOut,
    NetworkPersonOut,
    NetWorthOut,
    NetWorthPointOut,
    OfficeReturnOut,
    OpenRoundOut,
    StartupRoundOut,
    TradeOut,
)
from tst.api.views import person_name, role_label
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.finance.captable import person_shares
from tst.sim.founder import angel, personal, shares, wealth
from tst.sim.founder.family_office import MANAGER_SKILL
from tst.sim.founder.investing_models import MANDATES, STAKE_FULL
from tst.sim.ledger import LedgerBalances
from tst.sim.mna.valuation import is_listed
from tst.sim.people.reveal import revealed_range
from tst.sim.rivals import formulas as rf
from tst.sim.rivals.decisions import cash_months
from tst.sim.state import GameState, angel_stake_of, family_office_of, listed_id, rounds_of

PCT = 100  # tunable-exempt: percent
HISTORY_INDEX = 60  # tunable-exempt: months of the index shown
RETURNS_SHOWN = 24  # tunable-exempt: months of family-office returns shown
YEAR = 12  # tunable-exempt: calendar


def _category(state: GameState, company_id: int, data: LoadedData) -> str:
    products = state.company_products(company_id)
    if not products:
        return ""
    return data.game_data.category(products[0].category).label


def _conflict(answer: str | None) -> str | None:
    return {"disclose": "disclosed", "conceal": "concealed", "found": "found"}.get(answer or "")


def investments_out(state: GameState, balances: LedgerBalances, data: LoadedData) -> InvestmentsOut:
    b, gd = data.balance, data.game_data
    founder = state.founder_of(state.player.id)
    fid = founder.id if founder is not None else 0
    point = wealth.net_worth(state, fid, balances, b, gd)
    stakes = []
    for s in state.angel_stakes:
        if s.person_id != fid:
            continue
        company = state.company(s.company_id)
        band = None
        if company.alive and s.status == "open":
            band = rf.money_label(cash_months(state, company.id, balances, b, gd), b.rivals)
        stakes.append(
            AngelStakeOut(
                id=s.id,
                company_id=company.id,
                company=company.name,
                category_label=_category(state, company.id, data),
                status=s.status,
                stake_pct=round(s.stake_ppm / STAKE_FULL * PCT, 2),
                cost_cents=s.cost_cents,
                worth_cents=wealth.stake_value_cents(s) if s.status == "open" else 0,
                proceeds_cents=s.proceeds_cents,
                backed=s.backed,
                founder_known=s.founder_known,
                since_label=format_turn(s.from_turn),
                closed_label=format_turn(s.closed_turn) if s.closed_turn is not None else None,
                cash_band=band,
                funding=[
                    StartupRoundOut(
                        date_label=format_turn(r.turn),
                        raised_cents=r.raised_cents,
                        post_cents=r.post_cents,
                        source=r.source,
                    )
                    for r in rounds_of(state, company.id)
                ],
                conflict=_conflict(s.coi_answer) if s.coi_turn is not None else None,
            )
        )
    open_rounds = []
    for c in state.companies:
        if not c.is_startup or c.is_player or not c.alive or c.parent_id is not None:
            continue
        rnd = angel.open_round(state, c.id, b)
        last = angel.latest_round(state, c.id)
        if rnd is None or last is None or is_listed(state, c.id, gd):
            continue
        held = angel_stake_of(state, fid, c.id)
        open_rounds.append(
            OpenRoundOut(
                company_id=c.id,
                company=c.name,
                category_label=_category(state, c.id, data),
                date_label=format_turn(rnd.turn),
                raised_cents=rnd.raised_cents,
                post_cents=last.post_cents,
                max_cents=rnd.raised_cents,
                held_pct=round(held.stake_ppm / STAKE_FULL * PCT, 2) if held else 0.0,
            )
        )
    candidates = {c.person_id for c in state.open_candidates(state.player.id)}
    network = [
        NetworkPersonOut(
            person_id=p.id,
            name=person_name(p),
            role_label=role_label(p.role, data) or "",
            source="candidate" if p.id in candidates else "former",
            known=angel.known_well(state, p.id, gd, b),
        )
        for p in angel.network(state)
    ]
    categories = [
        CategoryOptionOut(key=c.key, label=c.label)
        for c in gd.categories
        if not (c.capacity_market or c.sells_units or c.assembly_market)
    ]
    own_id = listed_id(state) if founder is not None else None
    holdings = []
    for h in state.public_holdings:
        if h.person_id != fid or h.shares <= 0:
            continue
        price = wealth.share_price_cents(state, h.company_id, balances, b, gd)
        holdings.append(
            HoldingOut(
                company_id=h.company_id,
                company=state.company(h.company_id).name,
                shares=h.shares,
                price_cents=price,
                worth_cents=h.shares * price if price is not None else h.cost_cents,
                cost_cents=h.cost_cents,
                own=h.company_id == own_id,
            )
        )
    listed = []
    preparing = shares.preparing(state)
    for c in state.companies:
        if not is_listed(state, c.id, gd):
            continue
        price = wealth.share_price_cents(state, c.id, balances, b, gd)
        if price is None:
            continue
        own = shares.is_own(state, c.id)
        listed.append(
            ListedOut(
                company_id=c.id,
                company=c.name,
                price_cents=price,
                own=own,
                window_open=not (own and shares.window_closed(state)),
                sensitive=c.id in preparing or (own and bool(preparing)),
            )
        )
    trades = [
        TradeOut(
            id=t.id,
            date_label=format_turn(t.turn),
            company_id=t.company_id,
            company=state.company(t.company_id).name,
            side=t.side,
            shares=t.shares,
            price_cents=t.price_cents,
            filed=t.filed,
            sensitive=t.sensitive_target_id is not None,
            investigation=(
                "finding"
                if t.finding_turn is not None and state.turn > t.finding_turn
                else "open"
                if t.investigated_turn is not None
                else None
            ),
        )
        for t in sorted(state.personal_trades, key=lambda t: -t.id)
        if t.person_id == fid
    ]
    office = family_office_of(state, fid)
    office_out = None
    if office is not None:
        manager = state.person(office.manager_id)
        reveal = state.reveal(state.player.id, manager.id)
        lo, hi = revealed_range(manager, reveal, MANAGER_SKILL) if reveal else (1, 20)
        year = office.returns[-YEAR:]
        trailing = None
        index_year = None
        if len(year) == YEAR:
            growth = 1.0
            for _, r in year:
                growth *= 1 + r
            trailing = round((growth - 1) * PCT, 1)
            pts = state.market_index
            if len(pts) > YEAR and pts[-1 - YEAR].level > 0:
                index_year = round((pts[-1].level / pts[-1 - YEAR].level - 1) * PCT, 1)
        office_out = FamilyOfficeOut(
            formed_label=format_turn(office.formed_turn),
            mandate=office.mandate,
            balance_cents=wealth.family_office_cents(state, fid),
            manager_id=manager.id,
            manager_name=person_name(manager),
            manager_skill_low=lo,
            manager_skill_high=hi,
            returns=[
                OfficeReturnOut(turn=t, date_label=format_turn(t), return_pct=round(r * PCT, 2))
                for t, r in office.returns[-RETURNS_SHOWN:]
            ],
            trailing_year_pct=trailing,
            index_year_pct=index_year,
        )
    worth = point.total_cents - point.own_stake_cents
    return InvestmentsOut(
        personal_cash_cents=personal.cash_cents(state, fid),
        net_worth=NetWorthOut(
            total_cents=point.total_cents,
            cash_cents=point.cash_cents,
            angel_cents=point.angel_cents,
            public_cents=point.public_cents,
            family_office_cents=point.family_office_cents,
            own_stake_cents=point.own_stake_cents,
        ),
        history=[
            NetWorthPointOut(
                turn=w.turn,
                date_label=format_turn(w.turn),
                total_cents=w.total_cents,
                own_stake_cents=w.own_stake_cents,
            )
            for w in state.wealth_points
            if w.person_id == fid
        ],
        stakes=stakes,
        open_rounds=open_rounds,
        network=network,
        categories=categories,
        holdings=holdings,
        listed=listed,
        trades=trades,
        family_office=office_out,
        family_office_form=FamilyOfficeFormOut(
            can_form=office is None and worth >= b.family_office.min_cents,
            min_cents=b.family_office.min_cents,
            wealth_cents=worth,
            energy=b.family_office.energy,
            move_energy=b.family_office.move_energy,
            mandates=list(MANDATES),
        ),
        index=[
            IndexPointOut(turn=p.turn, date_label=format_turn(p.turn), level=round(p.level, 4))
            for p in state.market_index[-HISTORY_INDEX:]
        ],
        rules=InvestingRulesOut(
            join_energy=b.angel.energy,
            back_energy=b.angel.back_energy,
            trade_energy=b.personal.trade_energy,
            round_min_cents=b.angel.round_min_cents,
            min_cheque_cents=b.angel.min_cheque_cents,
            seed_stake_low_pct=b.angel.seed_stake[0] * PCT,
            seed_stake_high_pct=b.angel.seed_stake[1] * PCT,
            seed_full_cents=b.angel.seed_full_cents,
            trade_cost_pct=b.personal.trade_cost * PCT,
        ),
    )


def own_shares(state: GameState) -> int:
    founder = state.founder_of(state.player.id)
    return person_shares(state, listed_id(state), founder.id) if founder else 0
