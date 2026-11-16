"""M30's long state-cache check (docs/tasks/M30-performance-at-scale.md sub-task 1): seeds 1-3
under three strategies, 360 months each, every month's full-state digest equal to the one
recorded before any M30 change (tests/fixtures/m30_state_hashes.json, tools/m30_state_hashes.py).
A speed-up never changes a result. Nightly: the nine runs take the nightly shards' time.

`--update-state-cache` (M35a) re-records the fixture instead of comparing with it, by the rule
`--update-golden` follows: only for an intentional change of results, with the reason in
CHANGELOG.md. The digest's own checks (a repeat gives the same digests; the memo equals a fresh
digest) run with or without it:

    uv run pytest tests/balance/test_m30_state_cache.py --update-state-cache
"""

from __future__ import annotations

import os

import pytest

from tst.balance import m30
from tst.balance.game import start_game
from tst.balance.report import SCENARIO


def _updating(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-state-cache"))


def test_update_the_fixture(request: pytest.FixtureRequest) -> None:
    """With --update-state-cache: play the nine runs and write the fixture."""
    if not _updating(request):
        pytest.skip("only with --update-state-cache")
    m30.write(m30.all_hashes(os.cpu_count() or 1))


@pytest.mark.nightly
@pytest.mark.parametrize(("name", "seed"), m30.jobs(), ids=lambda v: str(v))
def test_360_months_identical_to_the_fixture(
    name: str, seed: int, request: pytest.FixtureRequest
) -> None:
    if _updating(request):
        pytest.skip("re-recording the fixture (test_update_the_fixture)")
    want = m30.recorded()[m30.key(name, seed)]
    got = m30.run_hashes((name, seed))
    assert m30.first_difference(got, want) is None, m30.first_difference(got, want)


def test_the_digest_is_canonical_and_sees_every_change() -> None:
    """Sets and mappings hash alike whatever their order; tuples, floats and fields do not."""
    d = m30.Digester()
    assert d.digest(frozenset({"a", "b", "c"})) == d.digest(frozenset({"c", "b", "a"}))
    assert d.digest({"x": 1, "y": 2}) == d.digest({"y": 2, "x": 1})
    assert d.digest((1, 2)) != d.digest((2, 1))
    assert d.digest(0.1 + 0.2) != d.digest(0.3)
    assert d.digest(1) != d.digest(1.0) != d.digest("1")
    assert m30.first_difference(["a", "b"], ["a", "c"]) == "first differs after turn 1: b != c"
    assert m30.first_difference(["a"], ["a", "b"]) == "1 months played, 2 recorded"


def test_a_short_run_repeats_and_its_memo_matches_a_fresh_digest(
    request: pytest.FixtureRequest,
) -> None:
    """The same seed gives the same digests; the identity memo gives what a digester with no
    memo gives for the same state."""
    first = m30.run_hashes(("research_heavy", 1), turns=6)
    assert first == m30.run_hashes(("research_heavy", 1), turns=6)
    if not _updating(request):  # the fixture may be being re-recorded
        assert first == m30.recorded()[m30.key("research_heavy", 1)][:6]
    game = start_game(m30.loaded(), 1, SCENARIO)
    script, running = m30.strategy("research_heavy"), m30.Digester()
    for _ in range(4):
        script(game)
        game.turn()
        memoised = m30.month_digest(running, game)
    assert memoised == m30.month_digest(m30.Digester(), game) == first[3]
