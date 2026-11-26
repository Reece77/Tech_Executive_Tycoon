"""M55 sub-task 3 property test (formulas.md 65.2): the books balance through capitalisation,
amortisation and write-offs. For any kind, budget, seed and months (and a cancel at any point):
every entry balances; the net 1560 postings for a title equal its carried book; the book never goes
negative; spent = book + amortised + written off; a title's book is cleared by the end of its
schedule; and its audience is drawn only at release."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.media import titles
from tst.sim.media.models import Title
from tst.sim.rng import RngFactory

PLAYER = 1


@settings(
    max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    kind=st.sampled_from(["series", "film", "game"]),
    mult=st.floats(0.25, 3.0),
    seed=st.integers(1, 10_000),
    cancel_at=st.one_of(st.none(), st.integers(0, 40)),
    f2p=st.booleans(),
)
def test_books_balance_through_a_title(
    loaded: LoadedData, kind: str, mult: float, seed: int, cancel_at: int | None, f2p: bool
) -> None:
    balance = loaded.balance
    state = fresh_game(loaded, seed=3)
    k = balance.media.kind(kind)
    budget = max(1, round(titles.typical_budget_cents(k, balance) * mult))
    title = Title(
        id=1,
        company_id=PLAYER,
        name="T",
        kind=kind,
        genre="drama",
        budget_cents=budget,
        greenlit_turn=state.turn,
        dev_months=k.dev_months,
        release_turn=state.turn + k.dev_months,
        platforms=("pc", "console") if kind == "game" else (),
        monetisation="free_to_play" if kind == "game" and f2p else "premium",
        live_service=kind == "game" and f2p,
    )
    state = replace(state, media=replace(state.media, titles=(title,)))
    rng = RngFactory(seed)
    content = 0
    months = k.dev_months + len(k.amortisation) * 12 + 2
    for m in range(months):
        state = replace(state, turn=state.turn + 1)
        t = state.media.title(1)
        assert t is not None
        if cancel_at is not None and m == cancel_at and t.stage == "development":
            t, entries = titles.cancel(t, state)
            state = replace(state, media=replace(state.media, titles=(t,)))
        else:
            state, entries, _ = titles.month(state, rng, balance, loaded.game_data)
        for e in entries:
            assert sum(line.amount for line in e.lines) == 0
            content += sum(line.amount for line in e.lines if line.account == titles.CONTENT)
        t = state.media.title(1)
        assert t is not None
        assert t.book_cents >= 0
        assert content == t.book_cents
        assert t.spent_cents == t.book_cents + t.amortised_cents + t.written_off_cents
        if t.stage == "development":
            assert t.audience is None and t.expected is None
    t = state.media.title(1)
    assert t is not None
    assert t.book_cents == 0
    if t.stage == "released":
        assert t.audience is not None and t.audience > 0
        assert t.spent_cents == budget
