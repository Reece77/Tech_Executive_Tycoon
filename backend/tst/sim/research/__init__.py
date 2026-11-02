"""The R&D tree and era milestones (docs/formulas.md 21, M11).

Modules: `data` (schemas), `models` (state records), `levels` (baselines, leads, the tech
factor), `eras` (arrival, boosts, the first mover), `projects` (phase 3 research),
`licensing` and `rivals` (incumbents' research action). Everything belongs to a
`company_id` (ADR-0020); this package's `__init__` stays import-light because
`tst.sim.data_models` imports `tst.sim.research.data`.
"""
