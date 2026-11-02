"""M5 balance targets (formulas.md 15.7), printed and checked on 10 seeds. Run with `-s` to see
the table; the M5 brief's Decisions made records it.

1. Living market: with no player product, over 120 turns, no incumbent's share of a segment's
   served customers falls below half or rises above double its starting share, and on average
   at least one rival startup per category launches a product. Judged on the four v1
   categories; new-market disruption in fintech and AI models is intended (M8, M7c).
2. Rivals respond: in the M3a earn-and-burn script, an incumbent cuts a price or starts a push
   in a segment the player sells to within 24 turns of launch, on at least 7 of 10 seeds.
3. Still winnable: the earn-and-burn ARR at turn 36 is $500,000 to $4M on at least 8 of 10.
4. Poaching felt, not crushing: in the fast-growth script, 1 to 4 approaches a year on
   average, and 20% to 60% of uncountered approaches accepted.
5. Speed: 120 persisted turns with 25 player staff, every incumbent and the startups that
   appear, under 1 second a turn on average.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from tests.balance_scripts import earn_and_burn, start
from tests.integration.test_funding_diagnostics import play as funding_play
from tests.integration.test_market_balance import served_shares
from tst.loader import LoadedData

SEEDS = range(1, 11)
LIVING_TURNS = 120
RESPOND_WITHIN = 24
ARR_TURN = 36
ARR_BAND = (50_000_000, 400_000_000)
POACH_YEARS = 3
SPEED_TURNS = 120
SPEED_STAFF = 25
PUSHES = {"price_cut", "feature_push", "quality_push", "brand_push"}
# Target 1 judges the four v1 markets. Fintech and AI models (M8) are disrupted on purpose by
# their scheduled real entrants (Square, Stripe, Plaid, OpenAI, Anthropic): PayPal's consumer
# share and Fiserv's enterprise share fall below half there on every seed (M7c, Reece).
V1_CATEGORIES = frozenset({"b2b_saas", "dev_tools", "consumer_apps", "cybersecurity"})


@pytest.fixture(scope="module")
def living(loaded: LoadedData) -> tuple[int, float]:
    """Target 1's runs: (seeds with a share breach, launches per v1 category a seed)."""
    breaches, launches = 0, 0
    worst_low, worst_high = 1.0, 1.0
    categories = len(V1_CATEGORIES)
    for seed in SEEDS:
        run = start(loaded, seed)
        incumbents = {p.id for p in run.state.products}
        first = {
            k: v
            for k, v in served_shares(run.state).items()
            if k[2] in incumbents and k[0] in V1_CATEGORIES
        }
        broke = False
        for _ in range(LIVING_TURNS):
            run.turn()
            now = served_shares(run.state)
            for key, share in first.items():
                if share < 1.0:  # under a point to start: too small to judge
                    continue
                ratio = now.get(key, 0.0) / share
                worst_low, worst_high = min(worst_low, ratio), max(worst_high, ratio)
                broke = broke or not 0.5 <= ratio <= 2.0
        v1 = {p.id for p in run.state.products if p.category in V1_CATEGORIES}
        launched = sum(
            1 for m in run.state.rival_moves if m.action == "launched" and m.product_id in v1
        )
        launched += sum(
            1
            for c in run.state.companies
            if c.is_startup
            for p in run.state.company_products(c.id)
            if p.launched_turn is not None
            and p.category in V1_CATEGORIES
            and not any(
                m.action == "launched" and m.product_id == p.id for m in run.state.rival_moves
            )
        )
        startups = sum(1 for c in run.state.companies if c.is_startup)
        failed = sum(1 for c in run.state.companies if c.is_startup and c.failed_turn is not None)
        print(
            f"\n1 seed {seed:2d}: share ratios {worst_low:.2f}-{worst_high:.2f}, startups "
            f"{startups} (failed {failed}), launches {launched}"
        )
        breaches += broke
        launches += launched
    per_category = launches / len(SEEDS) / categories
    print(f"\n1 living market: breaches {breaches}/10, launches per category {per_category:.2f}")
    return breaches, per_category


@pytest.mark.nightly  # statistical balance target (M7a: nightly, D4a)
def test_1_living_market(living: tuple[int, float]) -> None:
    assert living[0] == 0


@pytest.mark.nightly
def test_1_living_market_launches(living: tuple[int, float]) -> None:
    assert living[1] >= 1.0


@pytest.mark.nightly  # statistical balance target (M7a: nightly, D4a)
def test_2_and_3_rivals_respond_and_still_winnable(loaded: LoadedData) -> None:
    responded, winnable = 0, 0
    for seed in SEEDS:
        run = earn_and_burn(loaded, seed, ARR_TURN + 1)
        launch = run.launched_turn or 0
        product = next(p for p in run.state.company_products(1))
        mine = {s.segment for s in run.state.segments_of(product.id)}
        category = product.category
        products = {p.id: p for p in run.state.products}
        answer = [
            m
            for m in run.state.rival_moves
            if m.action in PUSHES
            and launch <= m.turn <= launch + RESPOND_WITHIN
            and m.segment in mine
            and products.get(m.product_id or -1) is not None
            and products[m.product_id or -1].category == category
        ]
        arr = run.snapshots[ARR_TURN].arr_cents
        ok = ARR_BAND[0] <= arr <= ARR_BAND[1]
        print(
            f"\n2-3 seed {seed:2d}: launch {launch}, first answer "
            f"{answer[0].turn if answer else None} ({answer[0].detail if answer else '-'}), "
            f"ARR at 36 ${arr / 100:,.0f} {'ok' if ok else 'OUT'}"
        )
        responded += bool(answer)
        winnable += ok
    print(f"\n2 rivals respond: {responded}/10 | 3 still winnable: {winnable}/10")
    assert responded >= 7
    assert winnable >= 8


@pytest.mark.nightly  # statistical balance target (M7a: nightly, D4a)
def test_4_poaching_felt_not_crushing(loaded: LoadedData) -> None:
    made, decided, accepted = 0, 0, 0
    for seed in SEEDS:
        run_out = funding_play(
            loaded, seed, 12 * POACH_YEARS, grow=True, raise_a=True, keep_run=True
        )
        run = run_out.run
        assert run is not None
        approaches = run_out.approaches
        made += len(approaches)
        decided += sum(1 for a in approaches if a.status in ("accepted", "declined", "joined"))
        accepted += sum(1 for a in approaches if a.status in ("accepted", "joined"))
        print(
            f"\n4 seed {seed:2d}: approaches {len(approaches)}, accepted "
            f"{sum(1 for a in approaches if a.status in ('accepted', 'joined'))}"
        )
    per_year = made / len(SEEDS) / POACH_YEARS
    rate = accepted / decided if decided else 0.0
    print(f"\n4 poaching: {per_year:.2f} approaches a year, {rate:.0%} of answered accepted")
    assert 1.0 <= per_year <= 4.0
    assert 0.10 <= rate <= 0.40  # re-banded in M10d (product manager, 2026-11-02)


def test_5_speed(tmp_path: Path, loaded: LoadedData) -> None:
    from tests.helpers import play_turn
    from tests.integration.test_api_products import staff
    from tst.db.mappers import entry_to_row
    from tst.db.repository import create_save, open_session
    from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry

    path = create_save(
        "speed", 3, "funded_spinout", company_name="Speed Co", data=loaded, save_dir=tmp_path
    )
    staff(path, loaded, ("software_engineer",) * SPEED_STAFF)
    with open_session(path) as session, session.begin():  # enough cash for 120 months
        session.add(
            entry_to_row(
                LedgerEntry.transfer(
                    turn=0,
                    company_id=1,
                    memo="Test cash",
                    debit=CASH,
                    credit=COMMON_EQUITY,
                    amount=100_000_000_000,
                )
            )
        )
    start_time = time.perf_counter()
    for _ in range(SPEED_TURNS):
        play_turn(path, loaded)  # answers a critical event first (M10b: key exits)
    per_turn = (time.perf_counter() - start_time) / SPEED_TURNS
    print(f"\n5 speed: {per_turn * 1000:.0f} ms a turn over {SPEED_TURNS} turns")
    assert per_turn < 1.0
