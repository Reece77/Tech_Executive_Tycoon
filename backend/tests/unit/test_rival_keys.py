"""ADR-0013 amendment (M12a): rivals' RNG keys are stable identities, so appending a company
to the data reseeds no one else.

Incumbents are keyed (0, position in incumbents.yaml), scheduled entrants (1, position in
entrants.yaml), startups (2, category index, n-th founded in that category); a new game's
incumbents take product and people ids in blocks by their position. A new incumbent still
competes in its own category, so the test compares every rival outside that category."""

from __future__ import annotations

from dataclasses import replace

from tst.balance.game import start_game
from tst.loader import LoadedData
from tst.sim.hiring.models import INCUMBENT_PRODUCT_IDS_FROM
from tst.sim.rivals.models import ENTRANT_KEY, INCUMBENT_KEY, STARTUP_KEY

TURNS = 24
NEW_CATEGORY = "fintech"


def _appended(loaded: LoadedData) -> LoadedData:
    """The data with one more incumbent at the end: a fintech seller in Africa only."""
    gd = loaded.game_data
    base = next(i for i in gd.incumbents if i.name == "Infosys")
    product = base.products[0].model_copy(update={"regions": ("africa",), "name": "Test Ledger"})
    extra = base.model_copy(update={"name": "Test Bank", "products": (product,)})
    return replace(loaded, game_data=gd.model_copy(update={"incumbents": (*gd.incumbents, extra)}))


def _moves(loaded: LoadedData, seed: int) -> tuple[list[tuple[int, str, str, str]], set[str]]:
    game = start_game(loaded, seed)
    for _ in range(TURNS):
        game.turn()
    names = {c.id: c.name for c in game.state.companies}
    in_category = {
        names[p.company_id]
        for p in game.state.products
        if p.category == NEW_CATEGORY and p.company_id in names
    }
    moves = [
        (m.turn, names[m.company_id], m.action, m.detail)
        for m in sorted(game.state.rival_moves, key=lambda m: m.id)
    ]
    return moves, in_category


def test_appending_an_incumbent_reseeds_no_one_else(loaded: LoadedData) -> None:
    before, fintech = _moves(loaded, 3)
    after, _ = _moves(_appended(loaded), 3)
    outside = [m for m in before if m[1] not in fintech]
    assert outside, "rivals outside the new incumbent's category made moves"
    assert [m for m in after if m[1] not in fintech | {"Test Bank"}] == outside


def test_keys_and_id_blocks(loaded: LoadedData) -> None:
    game = start_game(loaded, 3)
    state = game.state
    incumbents = [c for c in state.companies if c.rival_key[:1] == (INCUMBENT_KEY,)]
    assert [c.rival_key[1] for c in incumbents] == list(range(len(loaded.game_data.incumbents)))
    assert state.player.rival_key == ()
    for c in incumbents:  # products in the incumbent's block, by data position
        for p in state.company_products(c.id):
            assert p.id // 10 == (INCUMBENT_PRODUCT_IDS_FROM + 10 * c.rival_key[1]) // 10
    assert state.next_ids.product == 1  # the player's products no longer follow incumbents
    for _ in range(40):  # Square (Mar 2010) and Stripe (Sep 2011) arrive; startups found
        game.turn()
    keys = [c.rival_key for c in game.state.companies if c.is_startup]
    assert (ENTRANT_KEY, 0) in keys and (ENTRANT_KEY, 1) in keys
    startups = [k for k in keys if k[:1] == (STARTUP_KEY,)]
    assert startups and len(set(startups)) == len(startups)
    for category in {k[1] for k in startups}:
        assert sorted(k[2] for k in startups if k[1] == category) == list(
            range(sum(1 for k in startups if k[1] == category))
        )
