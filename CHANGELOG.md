# Changelog

All notable changes to this project are recorded here. Golden snapshot regenerations must be listed with their reason.

## Unreleased

- Docs (M1b prep): M1b split into M1b (rules, API, CLI) and M1c (screens); sweep against M1a's code adds live-state-only candidates, stored id counters, an option pool (200 bp per offer, 1,000 bp total), M1 negative-cash rules, overview KPIs, offer and founder preview endpoints, and new-game metadata; wireframes add New-game setup and Overview.
- M0 foundation: repository tooling, pure sim primitives, data loading, persistence, CLI, golden tests, API, and front-end shell.
- M1 prep: drafted seed data for M1a (skills, personality, interests, regions, roles, tags, backgrounds), checked against formulas.md; mentor tag boost now uses personality; GitHub Actions runs `make check` on every push; M1a brief adds the hard-coded number check as sub-task 0.
- Docs (M1 sweep): ADR-0013 (one RNG stream name per call site, entity keys), ADR-0014 (immediate player actions, pending offers, energy timing); ADR-0007 clarified (per-observer tag reveals, exact forbidden field names); formulas.md and the M1a/M1b briefs fixed for 16 inconsistencies found before M1a.
- Golden snapshots: first generation for seeds 1..10 (24 turns, garage bootstrap). In M0 no subsystem draws random numbers yet, so all ten files are identical; they diverge once M1a adds people generation.
- M1a people model: founder, person generator, reveal engine, monthly growth, people tables (migration `0002_people`).
- Golden snapshots regenerated (M1a.8): `headcount` is now 1 on every turn because the founder has an employment row from turn 0 (formulas.md section 5). Cash and burn are unchanged.
- Golden fixtures added (M1a.9): `seed_NN.founder_ca.json` records the founder's current ability after each of the 24 turns. CA is hidden (ADR-0007), so it lives in its own fixture rather than in `turn_snapshot`, which the API returns.
- Growth noise is now multiplicative (M1a, after review): role skills grow by the section 3 term times `max(0, 1 + Normal(0, growth.noise_rel_sd))`, with `noise_rel_sd = 0.25` replacing the additive `growth.noise_sd`; skills outside the role change only by `−d(age)` with no noise. Golden `seed_NN.founder_ca.json` fixtures regenerated for this reason; `seed_NN.json` snapshots (cash, burn, headcount) are unchanged.
- Golden snapshots regenerated (M1b.4): phase 6 now posts payroll, office and job-post costs and base overhead drops to $500, so a solo founder costs $1,100 a month instead of $2,000; snapshots also gain `payroll_cents` and `avg_morale`. The founder-CA fixtures are unchanged.
