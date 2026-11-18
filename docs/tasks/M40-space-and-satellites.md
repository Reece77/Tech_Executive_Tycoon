# M40: Space and satellites (v5, lane I)

**Goal:** the player can go to orbit. It builds launch vehicles, with reusability as a long R&D path that cuts the cost per kg. It builds satellites and constellations on its own chips, and sells satellite broadband, then direct-to-device service, region by region under licences. It's capital-heavy and launches fail, with SpaceX, Blue Origin, Rocket Lab, CASC, OneWeb and Kuiper as rivals.

**Formulas:** `docs/formulas.md` §56 (all), with §21, §22, §26, §39, §46, §54 · **ADRs:** 0002, 0003, 0013 (stream `space` 68), 0020 · **Research:** `docs/v5-research/space-dossier.md` · **Depends on:** M32 (power), M43a's market sizes for calibration · **Lane:** I, alongside M43a (lane G) and M42 (lane H)

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m40-space` from `main`.
- **Merges after M43a and M42.** Then merge `main`, re-parent the migration, re-record fixtures with reasons, and re-run every guard.
- **M40 owns:**
  - new `backend/tst/sim/space/` (vehicles, launches, failures, reusability, satellites, constellations, coverage, broadband, direct-to-device, licences);
  - `space.yaml` (new);
  - the `launch`, `satellite_broadband` and Earth-observation categories;
  - the satellite-plant and launch-site facility kinds;
  - the `reusability` domain;
  - the Space screens;
  - `tst/balance/m40.py` (new).
- **M40 must not edit:** M43a's market-growth code and keys (size space markets through M43a's mechanism, and merge `main` often); M42's `pharma/`.
- **Shared files:** `categories.yaml`, `tech_frontier.yaml`, `chain_companies.yaml` and `incumbents.yaml`, `balance.yaml` (add `space.*`), `docs/formulas.md` (notes in §56 only), CHANGELOG, data dictionary, ADR-0013. Keep both sides.
- **CLAUDE.md §9's decision rules apply.** A company without space must play exactly as before.

## Out of scope

Defence and government contracts (M44); crewed spaceflight and tourism (follow-up); space mining (follow-up); automating space decisions (a follow-up automation area).

## Sub-tasks (commit after each)

1. **Research and data:**
   - `space.yaml` from the dossier (cost per kg by vehicle and year, launches a year by provider, reuse milestones, early failure rates, Starlink's satellites and subscribers by year, OneWeb, Kuiper, direct-to-device dates, market sizes), with every value cited;
   - `space.*` keys and stream `space`;
   - migration and data dictionary.
2. **Launch** (§56.1): vehicles, cadence, the reusability domain, failures (a critical event with the player's own satellites aboard), launch sites.
   - **Hidden-value test:** no failure draw reaches the API or a prompt.
3. **Satellites and constellations** (§56.2): satellite plants, shells, coverage, replacements, debris rules.
4. **Connectivity and services** (§56.3): broadband subscribers with terminals and licences, capacity and congestion, direct-to-device from its era, Earth observation; rivals.
   - **Property test:** books balance through launches, losses with insurance, and subscriptions.
5. **Screens:**
   - a **Space** screen (vehicles, launches, cost per kg, constellations and coverage maps, subscribers by region, licences);
   - M29 unlocks;
   - glossary entries (LEO, cost per kg, reusability, constellation, shell, direct-to-device);
   - Explain on a launch's price and a constellation's payback.
6. **API, CLI, e2e, balance and close-out:**
   - `tst space`;
   - **Playwright:** (a) design a vehicle and launch a satellite, (b) a launch failure with own satellites aboard arrives as a critical event, (c) broadband coverage opens a region once a shell is complete;
   - **a practice save** `pt-space`: a chip and devices group in 2026 with $20B cash and a reusability research lead;
   - **§56.4 targets** printed and recorded, tuning only `space.*` (rule 1); re-run every earlier guard;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `space.yaml` cites a source for every value.
- [ ] A company without space plays exactly as before; every earlier guard is unchanged on the combined code (or explained under rules 1–4).
- [ ] No launch-failure draw, seeded policy or rival plan reaches the API or a prompt (hidden-value test).
- [ ] §56.4 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m40-done`.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
