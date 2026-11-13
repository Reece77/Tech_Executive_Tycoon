"""M21 (formulas.md 38.2): through a fab's construction and operations the ledger balances and
its books hold, for any node, region, size, start month and length. Every LedgerEntry checks its
own balance when built; these check what that cannot: the fab's cash lines are exactly its
capex payments, running costs and slot sales; depreciation never exceeds what was paid (book
value is never negative); starts run stay within what it could run."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tst.balance import m21
from tst.sim.calendar import ym_to_turn
from tst.sim.errors import SimError
from tst.sim.fabs import market as fm
from tst.sim.fabs.actions import BuildFab
from tst.sim.geopolitics import fabs as geo_fabs
from tst.sim.ledger import COGS, FOUNDRY_SALES, PPE
from tst.sim.state import GameState

NODES = ["n65", "n40", "n28", "n20", "n16", "n10", "n7"]
REGIONS = list(m21.loaded().game_data.region_keys)
SIZES = [10_000, 25_000]
EPS = 1e-6


def _fab_lines(game: m21.Game, before: dict[tuple[int, str], int], account: str) -> int:
    return game.balances.get((1, account), 0) - before.get((1, account), 0)


@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    node=st.sampled_from(NODES),
    pick=st.data(),
    size=st.sampled_from(SIZES),
    year=st.integers(min_value=2019, max_value=2024),
    months=st.integers(min_value=1, max_value=6),
    ready=st.booleans(),
    staffed=st.booleans(),
)
def test_a_fab_keeps_its_books(
    node: str,
    pick: st.DataObject,
    size: int,
    year: int,
    months: int,
    ready: bool,
    staffed: bool,
) -> None:
    game = m21.game_at(11, ym_to_turn(year, 1))
    # only regions where the export controls allow this build (M22): a refused order has no
    # books to keep; the refusal is test_controls_refuse_an_advanced_fab_in_china
    allowed = [r for r in REGIONS if _orderable(game, node, r)]
    assert allowed  # North America never controls its own fabs
    region = pick.draw(st.sampled_from(allowed), label="region")
    fid = m21.build(game, node, region, size, ready_now=ready)
    if not staffed:
        f = game.state.facility(fid)
        assert f is not None
        game.notes.pop(f"staff:{fid}")
        game.state = m21.with_facility(game.state, replace(f, unit_id=None))
    for _ in range(months):
        before = dict(game.balances)
        paid_before = _paid(game.state, fid)
        m21.play(game)
        fab = fm.fab_of(game.state, fid)
        f = game.state.facility(fid)
        assert fab is not None and f is not None and fab.month is not None
        m = fab.month
        # depreciation never above cost; book value never negative
        assert 0 <= f.depreciated_cents <= f.capex_paid_cents
        assert f.book_value_cents >= 0
        assert f.capex_paid_cents <= f.capex_cents + fab.upgrade_cents
        # capex moved cash into PPE one for one
        assert _fab_lines(game, before, PPE) == f.capex_paid_cents - paid_before
        # the fab's costs and sales are in the ledger as posted
        assert _fab_lines(game, before, FOUNDRY_SALES) == -m.revenue_cents
        cogs = _fab_lines(game, before, COGS)
        assert cogs >= m.fixed_cents + m.materials_cents + m.power_cents
        assert 0 <= m.own + m.sold <= m.available + EPS
        assert m.revenue_cents >= 0 and m.materials_cents >= 0 and m.power_cents >= 0
        if not staffed:
            assert m.available == 0 and m.revenue_cents == 0


def _paid(state: GameState, fid: int) -> int:
    f = state.facility(fid)
    assert f is not None
    return f.capex_paid_cents


def _orderable(game: m21.Game, node: str, region: str) -> bool:
    loaded = m21.loaded()
    country = geo_fabs.fab_country(game.state, region, None, loaded.game_data)
    try:
        geo_fabs.check_order(game.state, 1, country, node, False, loaded.balance, loaded.game_data)
    except SimError:
        return False
    return True


def test_controls_refuse_an_advanced_fab_in_china() -> None:
    """The case the property test leaves out: October 2022's equipment controls (M22) refuse a
    16 nm fab in East Asia's default country (China) in 2023, and the order changes nothing."""
    game = m21.game_at(11, ym_to_turn(2023, 1))
    assert not _orderable(game, "n16", "east_asia")
    before = (dict(game.balances), game.state.facilities)
    assert not game.act(BuildFab(game.founder_id, "n16", "east_asia", 10_000))
    assert (dict(game.balances), game.state.facilities) == before
