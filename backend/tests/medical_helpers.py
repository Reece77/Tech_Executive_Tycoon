"""A game with one medical device of the player's (M41 tests), at any month without playing to
it: a new game moved to `turn`, the device live with a design, optional clearances and
installed customers in the home market."""

from __future__ import annotations

from dataclasses import replace

from tst.loader import LoadedData
from tst.sim.medical import data as md
from tst.sim.medical.models import Clearance, Design
from tst.sim.products.models import Product, ProductSegment
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import GameState, with_product, with_product_segment

PID = 990_400


_BASES: dict[tuple[int, int], GameState] = {}


def _base(loaded: LoadedData, seed: int) -> GameState:
    if (id(loaded), seed) in _BASES:
        return _BASES[(id(loaded), seed)]
    found = loaded.game_data.scenario("ex_big_tech_founders")
    assert found is not None
    state, _ = new_game(
        save_name="medical",
        master_seed=seed,
        scenario=found,
        difficulty="standard",
        company_name="Medical Co",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
    )
    _BASES[(id(loaded), seed)] = state
    return state


def medical_state(
    loaded: LoadedData,
    category: str = "surgical_robotics",
    use: str | None = None,
    turn: int = 0,
    seed: int = 1,
    cleared: tuple[str, ...] = (),
    customers: float = 0.0,
    quality: float = 70.0,
) -> GameState:
    d = loaded.game_data
    state = replace(_base(loaded, seed), turn=turn)
    cat = d.category(category)
    sub = md.subcategory(d, category)
    assert sub is not None
    product = Product(
        id=PID, company_id=state.player.id, category=category, name="Device", status="live",
        quality=quality, feature_points=0.0, brand=50.0, marketing_budget_cents=0,
        created_turn=max(0, turn - 24), launched_turn=turn, held_feature=60.0,
    )  # fmt: skip
    state = with_product(state, product)
    m = cat.markets[0]
    state = with_product_segment(
        state, ProductSegment(PID, m.segment, m.reference_price_cents, customers)
    )
    design = Design(PID, use or sub.uses[0].key)
    rows = tuple(Clearance(PID, key, md.regulator(d, key).region, turn, "test") for key in cleared)
    return replace(state, med_designs=(design,), med_clearances=rows)
