"""M55 sub-task 2's guard (formulas.md 65.8 target 1): a do-nothing game's consumer_apps market to
December 2025 (every consumer_apps line's customers and prices, and the market's size, each month),
hashed by year. Run on `main` to record tests/fixtures/m55_consumer_apps.json; the test compares the
branch's (consumer_apps' revenue a user is unchanged before 2026).

    uv run --project backend python tools/m55_consumer_apps.py 1 2 3 > backend/tests/fixtures/m55_consumer_apps.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from tst.balance.game import start_game
from tst.loader import load_all
from tst.sim.calendar import turn_to_ym, ym_to_turn

DATA = Path(__file__).resolve().parents[1] / "backend" / "data"
CATEGORY = "consumer_apps"


def lines(state) -> list[str]:  # type: ignore[no-untyped-def]
    out = []
    for m in state.markets:
        if m.category == CATEGORY:
            out.append(f"m|{m.segment}|{m.addressable!r}")
    for m in state.regional_markets:
        if m.category == CATEGORY:
            out.append(f"r|{m.region}|{m.segment}|{m.addressable!r}")
    for p in state.products:
        if p.category != CATEGORY:
            continue
        company = state.company(p.company_id)
        name = company.name if company is not None else "?"
        out.append(f"p|{name}|{p.name}|{p.status}|{p.quality!r}|{p.brand!r}")
        for s in state.segments_of(p.id):
            out.append(f"s|{name}|{p.name}|{s.segment}|{s.price_cents}|{s.customers!r}")
        for s in state.regional_segments_of(p.id):
            out.append(f"rs|{name}|{p.name}|{s.region}|{s.segment}|{s.price_cents}|{s.customers!r}")
    return out


def fingerprint(seed: int, last_turn: int = ym_to_turn(2025, 12)) -> dict[str, str]:
    game = start_game(load_all(DATA), seed)
    hashes: dict[int, hashlib._Hash] = {}
    while game.state.turn <= last_turn:
        year = turn_to_ym(game.state.turn)[0]
        h = hashes.setdefault(year, hashlib.sha256())
        for line in lines(game.state):
            h.update(line.encode())
            h.update(b"\n")
        game.turn()
    return {str(y): h.hexdigest() for y, h in sorted(hashes.items())}


if __name__ == "__main__":
    seeds = [int(s) for s in sys.argv[1:]] or [1]
    print(json.dumps({str(s): fingerprint(s) for s in seeds}, indent=1, sort_keys=True))
