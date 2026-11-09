"""M19 (formulas.md 35.1-35.5): founding a subsidiary, transfers at book value, building and
running a mine, closure and reclamation, the critical events (seeded: the same seed gives the
same result), sales to the group at the transfer price, and rival miners."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from tst.balance import m19
from tst.balance.game import start_game
from tst.loader import LoadedData
from tst.sim.errors import MiningRuleError
from tst.sim.events.models import GameEvent
from tst.sim.ledger import (
    ARO,
    CASH,
    COMMODITY_REVENUE,
    DEPLETION,
    EXPLORATION,
    INTERCOMPANY_SALES,
    INVESTMENT_SUBSIDIARIES,
    MINERAL_PROPERTIES,
    ROYALTIES,
    LedgerEntry,
)
from tst.sim.mining import phase as mp
from tst.sim.mining import risk
from tst.sim.mining.actions import (
    AnswerRivalBid,
    BuildMine,
    CareMaintenance,
    CloseMine,
    FoundSubsidiary,
    SetMineSales,
    SignMineSale,
    TransferAsset,
    apply_mining,
)
from tst.sim.rng import RngFactory
from tst.sim.state import group_companies, life_of, listed_id, owner_at

SUB_CENTS = 100_000_000_000  # $1B


def _tuned(loaded: LoadedData, **mining: Any) -> LoadedData:
    mb = loaded.balance.mining.model_copy(update=mining)
    return replace(loaded, balance=loaded.balance.model_copy(update={"mining": mb}))


def _sum(entries: list[LedgerEntry], account: str, company: int | None = None) -> int:
    return sum(
        x.amount
        for e in entries
        if company is None or e.company_id == company
        for x in e.lines
        if x.account == account
    )


def _balanced(run: m19.Miner) -> None:
    for e in run.posted:
        assert sum(x.amount for x in e.lines) == 0, e.memo
    assert sum(run.balances.values()) == 0


def test_found_a_subsidiary(loaded: LoadedData) -> None:
    game = start_game(loaded, 4)
    run = m19.Miner(loaded, game.state, dict(game.balances))
    with pytest.raises(MiningRuleError, match="stage 3"):
        apply_mining(
            run.state,
            FoundSubsidiary(run.founder, "X Mining", "oceania", SUB_CENTS),
            run.rng,
            run.balances,
            loaded.balance,
            loaded.game_data,
        )
    run = m19.miner(loaded, 4)
    out = run.act(FoundSubsidiary(run.founder, "Ironbark Mining", "oceania", SUB_CENTS))
    assert out is not None, run.log
    sub = run.state.companies[-1]
    assert sub.name == "Ironbark Mining" and sub.parent_id == listed_id(run.state)
    city = next(c for c in loaded.game_data.cities if c.key == sub.hq_city)
    assert city.region == "oceania" and not sub.is_player and sub.personality is None
    assert sub.id in {c.id for c in group_companies(run.state, listed_id(run.state))}
    held = owner_at(run.state, sub.id)
    assert held is not None and held.owner_id == m19.PLAYER
    assert run.balances[(sub.id, CASH)] == SUB_CENTS
    assert run.balances[(m19.PLAYER, INVESTMENT_SUBSIDIARIES)] == SUB_CENTS
    _balanced(run)
    assert run.act(FoundSubsidiary(run.founder, "ironbark mining", "africa", SUB_CENTS)) is None


def test_transfer_a_project_and_a_mine_at_book_value(loaded: LoadedData) -> None:
    run = m19.miner(loaded, 5)
    run.act(FoundSubsidiary(run.founder, "Lode Mining", "latin_america", SUB_CENTS))
    sub = run.state.companies[-1].id
    project = m19.permitted_project(run, "copper")
    assert run.act(TransferAsset(run.founder, sub, project_id=project.id)) is not None, run.log
    assert run.state.projects[-1].company_id == sub
    mine = m19.build(run, "copper")  # a second project, built by the operating company
    for _ in range(3):
        run.month()
    mine = m19.mine_of(run, mine.id)
    book = mine.book_cents
    before = run.balances[(sub, CASH)]
    assert run.act(TransferAsset(run.founder, sub, facility_id=mine.id)) is not None, run.log
    assert m19.mine_of(run, mine.id).company_id == sub
    assert run.state.facility(mine.id).company_id == sub  # type: ignore[union-attr]
    assert run.balances[(sub, MINERAL_PROPERTIES)] == book
    assert run.balances[(m19.PLAYER, MINERAL_PROPERTIES)] == 0
    assert run.balances[(sub, CASH)] == before - book
    _balanced(run)


def test_build_hides_the_overrun_until_revised(loaded: LoadedData) -> None:
    def built() -> m19.Miner:
        run = m19.miner(loaded, 6)
        m19.build(run, "copper")
        return run

    a, b = built(), built()
    assert a.state.mines == b.state.mines  # seeded: same seed, same construction and overrun
    mine = a.state.mines[-1]
    project = a.state.projects[-1]
    assert mine.moved_cents == project.spent_cents > 0
    assert _sum(a.posted, MINERAL_PROPERTIES) == project.spent_cents
    assert _sum(a.posted, EXPLORATION) == 0  # spent, then capitalized
    rate = round(mine.estimate_cents / (mine.ready_turn - mine.ordered_turn))
    revealed_at = None
    while a.state.turn < mine.ready_turn:
        paid = m19.mine_of(a, mine.id).capex_paid_cents
        a.month()
        now = m19.mine_of(a, mine.id)
        if now.revised_cents is None:
            assert now.capex_paid_cents - paid == rate  # the estimate's rate: no overrun shown
        elif revealed_at is None:
            revealed_at = a.state.turn
            assert now.revised_cents == mine.hidden_total_cents
    final = m19.mine_of(a, mine.id)
    assert final.status == "producing" and revealed_at is not None
    assert final.capex_paid_cents == mine.hidden_total_cents
    _balanced(a)


def test_running_closing_and_reclamation(loaded: LoadedData) -> None:
    run = m19.miner(loaded, 7)
    mine = m19.build(run, "copper")
    m19.run_until(run, mine.ready_turn + 18)
    now = m19.mine_of(run, mine.id)
    assert now.product_t > 0 and len(now.history) > 0
    assert _sum(run.posted, COMMODITY_REVENUE) < 0  # credits: sales
    assert _sum(run.posted, ROYALTIES) > 0 and _sum(run.posted, DEPLETION) > 0
    assert -_sum(run.posted, ARO) == now.aro_cents > 0
    assert 0 < now.book_cents < now.capex_paid_cents + now.moved_cents
    assert now.ore_mined_mt <= now.hidden_ore_mt
    owed = now.aro_cents
    assert run.act(CloseMine(run.founder, mine.id)) is not None, run.log
    closed = m19.mine_of(run, mine.id)
    assert closed.status == "closed" and closed.book_cents == 0
    assert run.balances[(m19.PLAYER, MINERAL_PROPERTIES)] == 0
    months = loaded.balance.mining.reclamation_months
    for _ in range(months + 2):
        run.month()
    done = m19.mine_of(run, mine.id)
    assert done.aro_paid_cents == owed and run.balances.get((m19.PLAYER, ARO), 0) == 0
    _balanced(run)


def test_care_and_maintenance_and_restart(loaded: LoadedData) -> None:
    run = m19.miner(loaded, 8)
    mine = m19.build(run, "copper")
    m19.run_until(run, mine.ready_turn + 2)
    assert run.act(CareMaintenance(run.founder, mine.id)) is not None, run.log
    run.month()
    care = m19.mine_of(run, mine.id)
    assert care.status == "care" and care.history[-1].output_t == 0
    assert run.act(CareMaintenance(run.founder, mine.id, restart=True)) is not None, run.log
    for _ in range(loaded.balance.mining.crash.restart_months):
        run.month()
    assert m19.mine_of(run, mine.id).status == "producing"


def test_a_price_crash_raises_its_event(loaded: LoadedData) -> None:
    """35.4: the price under the mine's all-in cost for three months running (forced here by
    a sustaining cost far above any price); each answer, seeded."""
    tuned = _tuned(loaded, sustaining_share=5.0)
    outcomes = {}
    for answer in ("care", "hedge", "keep"):
        run = m19.miner(tuned, 9)
        run.answers["crash"] = answer
        mine = m19.build(run, "copper")
        m19.run_until(run, mine.ready_turn + 6)
        crashes = [e for e in run.events if e[1] == "crash"]
        assert crashes and crashes[0][0] >= mine.ready_turn + 3
        outcomes[answer] = m19.mine_of(run, mine.id)
    assert outcomes["care"].status == "care"
    assert outcomes["keep"].status == "producing"
    assert any(d.buyer.endswith("(hedge)") for d in m19.miner(tuned, 9).state.mine_deals) is False
    hedged = m19.miner(tuned, 9)
    hedged.answers["crash"] = "hedge"
    mine = m19.build(hedged, "copper")
    m19.run_until(hedged, mine.ready_turn + 6)
    assert [d.kind for d in hedged.state.mine_deals] == ["offtake"]


def test_accidents_are_seeded_and_answered(loaded: LoadedData) -> None:
    pit = loaded.balance.mining.subtypes
    every = {k: v.model_copy(update={"accident_base": 1.0}) for k, v in pit.items()}
    sharp = loaded.balance.mining.accident.model_copy(update={"skill_ref": 20.0})
    tuned = _tuned(loaded, subtypes=every, accident=sharp)  # about 60% a month

    def played(answer: str) -> m19.Miner:
        run = m19.miner(tuned, 10)
        run.answers["accident"] = answer
        mine = m19.build(run, "copper")
        m19.run_until(run, mine.ready_turn + 12)
        return run

    a, b = played("investigate"), played("investigate")
    assert a.events == b.events and a.state.mines == b.state.mines
    assert any(kind == "accident" for _, kind, _ in a.events)
    mine = a.state.mines[-1]
    assert mine.accidents > 0 and mine.stopped_until is not None
    fine = loaded.balance.mining.accident.fine_cents
    assert any(
        e.memo.startswith("Fine: an accident") and max(x.amount for x in e.lines) == fine
        for e in a.posted
    )
    c = played("compensate")
    founder = c.founder
    life = life_of(c.state, founder)
    assert life is not None and life.trait("beloved") > 0
    d = played("contest")
    life = life_of(d.state, d.founder)
    assert life is not None and life.trait("ruthless") > 0


def test_export_ban_history_and_a_seeded_takeover(loaded: LoadedData) -> None:
    """35.4: Zimbabwe's lithium ore ban (Dec 2022) limits an African lithium mine to its region;
    after 2025 a takeover comes on stream region_risk, the same on every replay."""
    rng = RngFactory(11)
    dec_2022 = 12 * 12 + 11
    events = risk.region_events(rng, dec_2022, loaded.balance, loaded.game_data)
    assert [(e.region, e.commodity, e.kind) for e in events] == [
        ("africa", "lithium_carbonate", "export_ban")
    ]
    tuned = _tuned(
        loaded,
        nationalization=loaded.balance.mining.nationalization.model_copy(
            update={"monthly_base": 1.0, "ban_share": 0.0}
        ),
    )
    after = risk.region_events(rng, 200, tuned.balance, tuned.game_data)
    assert after == risk.region_events(RngFactory(11), 200, tuned.balance, tuned.game_data)
    assert {e.kind for e in after} == {"nationalization"}
    results = {}
    for answer in ("partner", "fight", "sell_out"):
        run = m19.miner(tuned, 12)
        run.answers["takeover"] = answer
        run.state = replace(run.state, turn=190)
        try:
            mine = m19.build(run, "cobalt", "africa")
        except LookupError:
            pytest.skip("no free African cobalt deposit on this seed")
        m19.run_until(run, 193)
        results[answer] = (m19.mine_of(run, mine.id), run)
        _balanced(run)
    partner, _ = results["partner"]
    assert 0.3 <= partner.state_share <= 0.51 and partner.is_open
    fought, run = results["fight"]
    assert fought.status == "seized" and fought.arbitration_due is not None
    sold, _ = results["sell_out"]
    assert sold.status == "closed" and sold.close_reason == "sold_to_state"


def test_group_supply_at_the_transfer_price(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    """35.3: a group buyer's use is supplied at the transfer price: its outside purchase is
    reversed and it pays the mine; the rest sells at spot."""
    run = m19.miner(loaded, 13)
    run.act(FoundSubsidiary(run.founder, "Seam Mining", "oceania", SUB_CENTS))
    sub = run.state.companies[-1].id
    project = m19.permitted_project(run, "copper")
    run.act(TransferAsset(run.founder, sub, project_id=project.id))
    assert run.act(BuildMine(run.founder, project.id)) is not None, run.log
    mine = run.state.mines[-1]
    uid = m19.add_engineers(run, 3, 12.0)
    from tst.sim.mining.actions import StaffMine

    run.act(StaffMine(run.founder, mine.id, uid))
    run.act(SetMineSales(run.founder, mine.id, m19.PLAYER, "cost_plus", 0.1))
    m19.run_until(run, mine.ready_turn + 1)
    monkeypatch.setattr("tst.sim.commodities.costs.company_use", lambda *a, **k: {"copper": 50.0})
    start = len(run.posted)
    run.month()
    month = run.posted[start:]
    assert _sum(month, INTERCOMPANY_SALES, sub) < 0
    assert _sum(month, "5900_intercompany_purchases", m19.PLAYER) > 0
    assert _sum(month, "5000_cogs", m19.PLAYER) < 0  # the spot purchase reversed
    _balanced(run)


def test_rival_bids_and_capacity(loaded: LoadedData) -> None:
    tuned = _tuned(
        loaded,
        rivals=loaded.balance.mining.rivals.model_copy(update={"buy_monthly": 1.0}),
    )
    run = m19.miner(tuned, 14)
    for _ in range(12):  # a project somebody would pay for
        project = m19.permitted_project(run, "copper")
        if (project.npv_lo_cents or 0) > 0:
            break
    else:
        pytest.skip("no project with a positive low NPV")
    others = [p for p in run.state.projects if p.id != project.id]
    run.state = replace(
        run.state,
        projects=(*(replace(p, status="relinquished") for p in others), run.state.projects[-1]),
    )
    run.month()
    bids = [b for b in run.state.rival_bids if b.status == "open"]
    assert bids and bids[0].project_id == project.id and bids[0].cents > 0
    assert run.act(AnswerRivalBid(run.founder, bids[0].id, accept=True)) is not None, run.log
    assert next(p for p in run.state.projects if p.id == project.id).status == "sold"
    _balanced(run)
    at = replace(run.state, turn=150)  # July 2022: history, so every month is known
    caps = risk.rival_capacity(RngFactory(14), 150, at, loaded.balance, loaded.game_data)
    rb = loaded.balance.mining.rivals
    assert caps and all(
        rb.floor * c.start_share - 1e-9 <= c.capacity_share <= rb.cap * c.start_share + 1e-9
        for c in caps
    )
    assert any(c.capacity_share > c.start_share for c in caps)  # 2010s spikes expanded some


def test_seller_contract_takes_its_share(loaded: LoadedData) -> None:
    run = m19.miner(loaded, 15)
    mine = m19.build(run, "copper")
    m19.run_until(run, mine.ready_turn + 1)
    vol = m19.mine_of(run, mine.id).capacity_t / 4
    assert run.act(SignMineSale(run.founder, mine.id, "contract", vol, months=12)) is not None
    m19.run_until(run, run.state.turn + 3)
    deal = run.state.mine_deals[-1]
    assert deal.delivered_t > 0 and deal.floor_usd_t == deal.ceiling_usd_t


def test_a_company_that_never_mines_skips_mining(loaded: LoadedData) -> None:
    game = start_game(loaded, 16)
    rng = RngFactory(16)
    s, e, logs = mp.build_month(game.state, rng, loaded.balance, loaded.game_data)
    assert s is game.state and e == () and logs == ()
    s, e, logs = mp.operate_month(game.state, rng, loaded.balance, loaded.game_data)
    assert s is game.state and e == () and logs == ()


def test_an_event_step_without_its_mine_does_nothing(loaded: LoadedData) -> None:
    game = start_game(loaded, 17)
    event = GameEvent(
        id=0,
        company_id=1,
        turn=3,
        template_id="mine_takeover",
        category="mining",
        severity="critical",
        trigger="mining",
        strength=1.0,
    )
    state, entries, logs = risk.mining_step(
        game.state, event, "partner", loaded.balance, loaded.game_data
    )
    assert state == game.state and entries == [] and logs == []


def test_a_subsidiarys_protest_reaches_the_player(loaded: LoadedData) -> None:
    """M19 integration fix in M18's exploration phase: a protest on a project held by a group
    subsidiary is queued to the player's company (the director shows only its queue) and its
    answer reaches the project."""
    from tst.sim.exploration.phase import exploration_month, exploration_step

    tuned = replace(
        loaded,
        balance=loaded.balance.model_copy(
            update={
                "exploration": loaded.balance.exploration.model_copy(
                    update={
                        "permitting": loaded.balance.exploration.permitting.model_copy(
                            update={"protest_rate": 1.0}
                        )
                    }
                )
            }
        ),
    )
    run = m19.miner(tuned, 18)
    run.act(FoundSubsidiary(run.founder, "Vale Mining", "oceania", SUB_CENTS))
    sub = run.state.companies[-1].id
    project = m19.permitted_project(run, "copper")
    t = run.state.turn
    project = replace(
        project, status="active", stage="permitting", permit_start=t, hidden_due_turn=t + 30
    )
    run.state = replace(
        run.state,
        projects=tuple(project if p.id == project.id else p for p in run.state.projects),
    )
    assert run.act(TransferAsset(run.founder, sub, project_id=project.id)) is not None, run.log
    sure = tuple(  # a fully sensitive community: a protest this month for certain
        replace(b, true_sensitivity=1.0)
        if (b.region, b.index) == (project.region, project.block)
        else b
        for b in run.state.geo_blocks
    )
    run.state = replace(run.state, geo_blocks=sure)
    state, _, _ = exploration_month(run.state, run.rng, tuned.balance, tuned.game_data)
    queued = [
        q for q in state.queued if q.template_id in ("community_blockade", "permit_challenge")
    ]
    assert queued and queued[0].company_id == m19.PLAYER
    p = next(x for x in state.projects if x.id == project.id)
    assert p.company_id == sub and p.protest_turn == t + 1
    event = GameEvent(
        id=0,
        company_id=m19.PLAYER,
        turn=t + 1,
        template_id=queued[0].template_id,
        category="exploration",
        severity="critical",
        trigger="exploration",
        strength=1.0,
    )
    after, _, _ = exploration_step(
        replace(state, turn=t + 1), event, "benefit", tuned.balance, tuned.game_data
    )
    answered = next(x for x in after.projects if x.id == project.id)
    assert answered.protest_turn is None and answered.benefit
