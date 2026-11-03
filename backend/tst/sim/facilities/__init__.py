"""Facilities, market goods and compute (docs/formulas.md 22, M12a; ADR-0020).

A generic facility model whose first kinds are general and GPU data centres; component goods
(server, GPU) with history then seeded shocks; compute units bought on spot or served from
your own capacity; spare capacity sold in the Cloud hosting market; outages.

Kept import-free: `tst.sim.data_models` imports `tst.sim.facilities.config`.
"""
