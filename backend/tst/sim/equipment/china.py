"""Chinese foundries' EUV-class tools (docs/formulas.md 47.5 target 4; 41.5).

After 2025 a Chinese foundry (nodes.yaml foundries in China) reaches a node that needs EUV (an
EUV node without a DUV route, or a future node) only once it has EUV-class tools: ASML's
delivered to it (a rule lifted), or its own domestic tools, which arrive in equipment.yaml's
`china_tools` window at `start + floor(u x months)`, `u` one uniform on stream equipment key
(2, foundry position) at turn 0. While the bans hold it stops at the newest node it can make by
DUV (41.5's catch-up lag still shrinks; the reach waits).
"""

from __future__ import annotations

import math

from tst.sim.data_models import GameData
from tst.sim.equipment import data as ed
from tst.sim.equipment.draws import CHINA, gen
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def own_tools_turn(master_seed: int, data: GameData, foundry: str) -> int:
    """The month a Chinese foundry's domestic EUV-class tools arrive (hidden until then)."""
    assert data.nodes is not None
    keys = [f.key for f in data.nodes.foundries]
    ct = ed.equipment_file(data).china_tools
    u = float(gen(RngFactory(master_seed), 0, CHINA, keys.index(foundry)).random())
    return ct.start_turn + math.floor(u * ct.months)


def euv_capable(state: GameState, data: GameData, foundry: str, turn: int) -> bool:
    if not ed.enabled(data):
        return True
    if any(d.buyer == foundry and d.source == "asml" for d in state.tool_deliveries):
        return True
    return turn >= own_tools_turn(state.save_meta.master_seed, data, foundry)


def needs_euv(data: GameData, node: str) -> bool:
    assert data.nodes is not None
    n = data.nodes.node(node)
    if n is None:
        return True  # a future node
    return n.euv and not n.duv_route
