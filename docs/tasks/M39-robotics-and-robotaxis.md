# M39: Robotics and robotaxis (v5, lane F)

**Goal:** robots join the game. The player can build industrial robots and sell them to factories, or install them in its own plants to cut labour cost. It can build humanoids once their era arrives, powered by its AI models and chips. It can run robotaxi services on M38's L4 cars, city by city, where regulators approve zones and utilisation decides the economics. History to 2025 is unchanged.

**Formulas:** `docs/formulas.md` §53 (all), with §2, §26, §38, §46, §48, §49 · **ADRs:** 0002, 0003, 0013 (stream `robotics` 66), 0020 · **Research:** `docs/v5-research/robotics-dossier.md` · **Outline:** `docs/v5-outline.md` · **Depends on:** M38 (`m38-done`) · **Lane:** F, alongside M41 and M37

## Reece's decisions (2026-11-14 and 2026-11-15)

- **Robotics among the first new industries,** with robotaxis in the same milestone.
- **Markets and money at the game's scale.**

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m39-robotics` from `main`.
- **Merges after M41 and M37.** Then merge `main`, re-parent the migration, re-record the M30 fixture with `--update-state-cache` and the reason, and re-run every guard.
- **M39 owns:**
  - new `backend/tst/sim/robotics/` (industrial robots, plant automation, humanoids, robotaxi fleets, zones, depots, rides, incidents);
  - `robotics.yaml` (new);
  - the `industrial_robots`, `humanoid_robots` and `mobility` categories;
  - the depot facility kind;
  - the plant-automation hook in the plant cost models (a read of the plant's automation level);
  - the Robotics screens;
  - `tst/balance/m39.py` (new).
- **M39 must not edit:** M41's `medical/`, M37's `dynasty/`, or M38's `vehicles/` beyond reading cars and autonomy levels through their interfaces.
- **Shared files:** `categories.yaml`, `regulation.yaml` (zone approvals under the `automotive` kind), `balance.yaml` (add `robotics.*`), `docs/formulas.md` (notes in §53 only), CHANGELOG, data dictionary, ADR-0013. Keep both sides.
- **CLAUDE.md §9's decision rules apply.** §53.4 target 1 (history holds; a company without robots plays exactly as before) is the guard. The turn-time guards are 500 ms on both V6 saves.

## Out of scope

Home humanoids before their seeded window; drones and delivery robots (follow-up); surgical robots (M41's); automating robotics decisions (a follow-up automation area).

## Sub-tasks (commit after each)

1. **Research and data:**
   - `robotics.yaml` from the dossier (installations by region and year, prices, makers and shares, humanoid announcements, robotaxi services' dates, cities and ride volumes, Cruise's end), with every value cited;
   - the three categories sized to the game's scale, with the derivation;
   - `robotics.*` keys and stream `robotics`;
   - migration and data dictionary.
2. **Industrial robots and plant automation** (§53.1). **Property test:** plant books balance with robots installed.
3. **Humanoids** (§53.2): the era-gated category, capability from hardware, AI and chips, labour-price demand, actuators as a learning-curve good.
4. **Robotaxis** (§53.3): the `mobility` category, fleets, zones with approvals, depots, rides and utilisation, incidents and suspensions (a critical event).
   - **Hidden-value test:** no incident or approval draw reaches the API or a prompt.
5. **Screens:**
   - a **Robotics** screen (markets, the player's robots, plant automation levels);
   - a **Mobility** screen (fleets by city, zones and permits, rides, utilisation, incidents);
   - M29 unlocks;
   - glossary entries (cobot, robot density, utilisation, zone, remote assistance);
   - Explain on a plant's automation saving and a robotaxi's contribution per ride.
6. **API, CLI, e2e, balance and close-out:**
   - `tst robotics`, `tst mobility`;
   - **Playwright:** (a) automate a vehicle plant with own robots and see unit cost fall, (b) launch a robotaxi zone in a city with an approval, (c) an incident suspends a zone;
   - **a practice save** `pt-robotics`: an EV maker in 2027 with L3 cars, a vehicle plant in a high-wage region and AI models;
   - **§53.4 targets** printed and recorded, tuning only `robotics.*` (rule 1); re-run every earlier guard;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `robotics.yaml` cites a source for every value, and history to 2025 follows it (tests).
- [ ] A company without robots plays exactly as before; every earlier guard is unchanged on the combined code (or explained under rules 1–4).
- [ ] No incident, approval or seeded draw reaches the API or a prompt (hidden-value test).
- [ ] §53.4 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m39-done`.

## Manual check (Reece, after merge)

Load `pt-robotics`. Automate your vehicle plant, then launch robotaxis in Phoenix and San Francisco. Watch utilisation, and what an incident does.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
