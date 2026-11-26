"""Telecom's place in the turn (docs/formulas.md 62).

- **New game** (`new_game`): the telecom markets' demand and history for the first month, and each
  telecom incumbent's opening capital.
- **Phase 5** before the markets (`open_month`): the history's dated openings (M43r);
  (`with_effects`): the player's lines' gates (coverage, spectrum, capacity, homes passed);
  after the markets (`after_sales`): auctions run, licences amortize and renew, a satellite
  partner's share, rip-and-replace orders that went live, sites switched off after a ban's
  deadline, coverage obligations.
- **Phase 9** (`demand_month`): growth draws, demand, 6G's month, auctions announced, seeded bans,
  fixed and wholesale trimmed to capacity, the networks' months, then the history's pin.

A save without the telecom markets (made before M53) does nothing here, and a company without
telecom plays exactly as before (62.5 target 1).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.calendar import ym_to_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.facilities.lifecycle import operating_cents
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.platforms.phase import Effects
from tst.sim.rng import RngFactory
from tst.sim.state import GameState
from tst.sim.telecom import demand, draws, equipment, history, regulation, services, spectrum
from tst.sim.telecom import networks as nw
from tst.sim.telecom.data import MONTHS, enabled, is_telecom_rival
from tst.sim.telecom.models import NetworkMonth


def new_game(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    if not enabled(state, balance, data):
        return state, ()
    state = demand.set_demand(state, balance, data)
    state = history.pin(state, balance, data)
    entries = []
    cash = balance.telecom.rival_cash_cents
    for company in state.rivals():
        if cash > 0 and is_telecom_rival(company, data):
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=company.id,
                    memo="Opening capital of the telecom business",
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
    return services.effects(base, state, balance, data)


def open_month(state: GameState, balance: Balance, data: GameData) -> GameState:
    if not enabled(state, balance, data):
        return state
    return history.pin(state, balance, data, openings_only=True)


def _replacements_live(state: GameState) -> GameState:
    """Rip-and-replace orders that went live count as replaced on their banned records."""
    t = state.telecom
    done: dict[int, int] = {}
    out = []
    for r in t.radios:
        if r.replaces_facility_id is None:
            out.append(r)
            continue
        f = state.facility(r.facility_id)
        live = f.live_capacity(state.turn) if f is not None else 0
        if live <= 0:
            out.append(r)
            continue
        done[r.replaces_facility_id] = done.get(r.replaces_facility_id, 0) + live
        out.append(replace(r, replaces_facility_id=None))
    if not done:
        return state
    radios = []
    for r in out:
        if r.facility_id in done:
            f = state.facility(r.facility_id)
            cap = f.capacity if f is not None else 0
            r = replace(r, replaced=min(cap, r.replaced + done[r.facility_id]))
        radios.append(r)
    return replace(state, telecom=replace(t, radios=tuple(radios)))


def after_sales(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not enabled(state, balance, data):
        return state, [], []
    t = state.telecom
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    if any(a.status == "announced" and a.turn == state.turn for a in t.auctions):
        state, more, more_logs = spectrum.run_month(state, rng, balance, data)
        entries += more
        logs += more_logs
    if state.telecom.licences:
        state, more, more_logs = spectrum.licences_month(state, balance, data)
        entries += more
        logs += more_logs
    if state.telecom.radios or state.telecom.settings:
        fees, _ = services.books(state, balance, data)
        entries += fees
    if state.telecom.radios:
        state = _replacements_live(state)
        state, dark_logs = equipment.dark_month(state, balance, data)
        logs += dark_logs
    if state.telecom.licences:
        state, more, more_logs = regulation.obligations_month(state, balance, data)
        entries += more
        logs += more_logs
    return state, entries, logs


def _g6_month(state: GameState, rng: RngFactory, balance: Balance) -> GameState:
    tb = balance.telecom
    t = state.telecom
    if state.turn != tb.start_turn or t.world.g6_turn is not None:
        return state
    g = draws.gen(rng, state.turn, draws.WORLD, draws.G6)
    w = tb.g6_window
    year = round(w.lo + (w.hi - w.lo) * g.random())
    month = int(g.integers(1, MONTHS + 1))
    world = replace(t.world, g6_turn=ym_to_turn(year, month))
    return replace(state, telecom=replace(t, world=world))


def _network_months(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Each of the player's networks' month (shown) and its cumulative cash (62.5 target 3):
    its lines' revenue less hosting and a partner's share, less the month's capex paid, operating
    cost and spectrum bought or renewed in the region."""
    t = state.telecom
    owners = (
        {r.company_id for r in t.radios}
        | {x.company_id for x in t.fibres}
        | {x.company_id for x in t.cables}
    )
    if not owners:
        return state
    tb = balance.telecom
    home = home_region_of(state, balance, data)
    _, revenue = services.books(state, balance, data)
    traffic = nw.traffic_gb(state, balance, data)
    cash = {(c, r): (v, capex) for c, r, v, capex in t.cash}
    months = []
    out_cash = []
    paid_back = dict(((c, r), turn) for c, r, turn in t.paid_back)
    for company_id in sorted(owners):
        for region in data.region_keys:
            facilities = [
                f
                for f in state.company_facilities(company_id)
                if f.region == region and f.kind in tb.kinds
            ]
            if not facilities:
                continue
            capex_total = sum(f.capex_paid_cents for f in facilities)
            before, before_capex = cash.get((company_id, region), (0, 0))
            opex = sum(operating_cents(f, state.turn, balance) for f in facilities)
            spectrum_spent = sum(
                x.paid_cents
                for x in t.licences
                if x.company_id == company_id and x.region == region and x.turn == state.turn
            )
            rev = revenue.get((company_id, region), 0)
            spend = (capex_total - before_capex) + opex + spectrum_spent
            total = before + rev - spend
            out_cash.append((company_id, region, total, capex_total))
            if total >= 0 and before < 0 and (company_id, region) not in paid_back:
                paid_back[(company_id, region)] = state.turn
            net = nw.network(state, company_id, region, balance, data)
            subs = services.company_customers(state, company_id, tb.mobile, home).get(region, 0.0)
            months.append(
                NetworkMonth(
                    turn=state.turn,
                    company_id=company_id,
                    region=region,
                    sites=net.sites,
                    coverage=net.coverage,
                    generation=net.best,
                    capacity_gb=net.capacity_gb,
                    demand_gb=subs * traffic,
                    homes_passed=net.homes_passed,
                    subscribers=subs,
                    revenue_cents=rev,
                    spend_cents=spend,
                )
            )
    keep = tb.history_months
    kept = tuple(m for m in t.months if m.turn > state.turn - keep) + tuple(months)
    t = replace(
        t,
        months=kept,
        cash=tuple(out_cash),
        paid_back=tuple(sorted((c, r, turn) for (c, r), turn in paid_back.items())),
    )
    return replace(state, telecom=t)


def demand_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    if not enabled(state, balance, data):
        return state, []
    logs: list[LogItem] = []
    state = demand.draw_growth(state, rng, balance, data)
    state = demand.set_demand(state, balance, data)
    state = _g6_month(state, rng, balance)
    state, more = spectrum.announce_month(state, rng, balance, data)
    logs += more
    state, more = equipment.seeded_bans_month(state, rng, balance, data)
    logs += more
    state = services.trim_to_capacity(state, balance, data)
    state = _network_months(state, balance, data)
    return history.pin(state, balance, data), logs
