"""Phase 7 for deals (docs/formulas.md 28.2-28.5, M14): diligence findings, ended antitrust
reviews, and closings. At closing the price posts (cash out, or new shares), goodwill goes to
1800, and the target becomes a kept brand or is integrated (tst.sim.mna.integration)."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, LedgerBalances, LedgerEntry, account_balance, apply_entries
from tst.sim.log import LogItem, inbox_item
from tst.sim.mna import antitrust, deals, integration
from tst.sim.mna.models import Acquisition, Deal, Problem
from tst.sim.money import format_money
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, target_file, with_acquisition, with_deal, with_target_file


def mna_month(
    state: GameState,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Diligence, reviews, then every deal due to close this month, by deal id."""
    if not (state.target_files or state.deals):
        return state, (), ()
    state, logs = deals.diligence_month(state, balance)
    state, reviewed = antitrust.review_month(state, balance, data)
    logs += reviewed
    entries: list[LedgerEntry] = []
    for deal in state.deals:
        # phase 7 of month T is its end: a deal due at T + 1 closes now (28.3)
        if deal.status != "accepted" or deal.close_turn is None or deal.close_turn > state.turn + 1:
            continue
        state, posted, logged = close_deal(state, deal, rng, balances, balance, data)
        balances = apply_entries(balances, posted)
        entries += posted
        logs += logged
    return state, tuple(entries), tuple(logs)


def close_deal(
    state: GameState,
    deal: Deal,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Close one deal (28.3): the cash part must be on hand; the price posts with goodwill,
    the target's problems come to light, and the chosen mode runs (28.5)."""
    name = state.company(deal.target_id).name
    cash_part = deals.cash_part_cents(deal.price_cents, deal.cash_share)
    if account_balance(balances, deal.acquirer_id, CASH) < cash_part:
        state = with_deal(state, replace(deal, status="abandoned", resolved_turn=state.turn))
        log = deals._update(
            state,
            deal.acquirer_id,
            f"The deal for {name} fell through",
            f"There was not {format_money(cash_part)} in cash at closing.",
            deal.target_id,
        )
        return state, [], [log] if state.company(deal.acquirer_id).is_player else []
    mode = deal.mode or "integrate"
    from tst.sim.mna.integration import can_integrate

    if mode == "integrate" and not can_integrate(state, deal.target_id, balance):
        mode = "brand"  # it grew past integration.max_staff before closing (2026-11-05)
    deal = replace(deal, mode=mode, status="closed", resolved_turn=state.turn)
    found = deals.file_of(state, deal.acquirer_id, deal.target_id, balance)
    state = with_target_file(
        state, replace(found, diligence_done_turn=found.diligence_done_turn or state.turn)
    )
    state, posted, acquisition = settle(state, deal, found.problems, balances, balance, data)
    state, acquisition, more, logs = integration.after_closing(
        state, acquisition, rng, apply_entries(balances, posted), balance, data
    )
    state = with_acquisition(state, acquisition)
    from tst.sim.rivals.characters import reset_feud

    state = reset_feud(state, deal.target_id)  # a bought company is no one's rival (2026-11-05)
    posted += more
    if not state.company(deal.acquirer_id).is_player:  # market news (28.6)
        logs.insert(
            0,
            inbox_item(
                state.turn,
                state.player.id,
                "rival_acquired",
                acquirer=state.company(deal.acquirer_id).name,
                target=name,
                price=format_money(deal.price_cents),
            ),
        )
    if state.company(deal.acquirer_id).is_player:
        problems = ", ".join(p.replace("_", " ") for p in acquisition.problems) or "none"
        how = "kept as a brand" if mode == "brand" else "being integrated"
        logs.insert(
            0,
            deals._update(
                state,
                deal.acquirer_id,
                f"Acquisition closed: {name}",
                f"You paid {format_money(deal.price_cents)}; {name} is {how}. Problems found: "
                f"{problems}.",
                deal.target_id,
            ),
        )
    return state, posted, logs


def settle(
    state: GameState,
    deal: Deal,
    problems: tuple[Problem, ...],
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], Acquisition]:
    """The price at closing, once (28.3): the acquirer's postings (cash out, new shares,
    goodwill, the brand's book equity in 1810 or its books moved over), the shares issued, and
    the closed deal with its acquisition record. Shared by a closing and by a sale after a
    takeover bid (M15r, Codex review 4 finding 1)."""
    posted = list(deals.closing_entries(state, deal, balances, data))
    state = deals.issue_shares(state, deal)
    acquisition = Acquisition(
        deal_id=deal.id,
        acquirer_id=deal.acquirer_id,
        target_id=deal.target_id,
        mode=deal.mode or "integrate",
        closed_turn=state.turn,
        price_cents=deal.price_cents,
        cost_before_cents=deals.monthly_costs_cents(state, deal.target_id, balance, data),
        problems=problems,
    )
    if acquisition.mode == "brand":  # M16 (31.1): the holding opens at closing
        from tst.sim.group.ownership import acquire

        state = acquire(state, deal.target_id, deal.acquirer_id, balances, data)
    return with_deal(state, deal), posted, acquisition


def file_known(state: GameState, acquirer_id: int, target_id: int) -> bool:
    found = target_file(state, acquirer_id, target_id)
    return found is not None and found.diligenced
